r"""IMG-06's two access-mask questions, answered against a real Windows token.

This is the hard half of a native identity oracle. IMG-01 asks whether **the token the child
will run as** can replace a path or any ancestor up to the volume root, and IMG-06a spells
that out as two masks rather than the word "writable" — a target mask for the path itself
(and, for a file, the directory holding it) and a narrower ancestor mask for everything
above.

**Deliberately not a complete oracle.** ``oracle_complete`` requires every method in
``ORACLE_METHODS``, and this class answers a subset. That is not an oversight: a policy-on
rung refuses an incomplete oracle by design, so this can land, be measured, and be tested
against real ACLs while the remaining answers are written. Wiring it in as the ladder's
oracle before it is complete would empty the ladder, and LADDER-03 turns an empty ladder into
a denial on every shell call.

**Stdlib only, by necessity.** An optional dependency cannot gate an oracle: missing, it does
not degrade to "unattested", it degrades to "no shell at all". So the Win32 surface is reached
through ``ctypes`` and pywin32 could only ever be a faster path behind this one.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes
from typing import FrozenSet, Mapping, Optional, Tuple

from ..capabilities.shell_spec import (
    AbsDir,
    AbsFile,
    AbsPath,
    DriveSpec,
    FsId,
    PinnedEnv,
    Platform,
    ResolvedImage,
    RootRelPath,
    Rung,
    Sha256,
    Subject,
)
from ._trust import ReparseResult, ReparseState

__all__ = [
    "ANCESTOR_MASK",
    "REPLACE_PRIVILEGES",
    "TARGET_DIRECTORY_MASK",
    "TARGET_FILE_MASK",
    "WindowsAccessOracle",
    "token_privileges",
    "token_sid",
]

# --------------------------------------------------------------- IMG-06a's masks
#
# FILE_WRITE_DATA and FILE_ADD_FILE are the same bit, as are FILE_APPEND_DATA and
# FILE_ADD_SUBDIRECTORY: the pair of names says what the bit means on a file versus a
# directory, not two different rights.

_FILE_WRITE_DATA = _FILE_ADD_FILE = 0x0002
_FILE_APPEND_DATA = _FILE_ADD_SUBDIRECTORY = 0x0004
_FILE_DELETE_CHILD = 0x0040
_DELETE = 0x00010000
_WRITE_DAC = 0x00040000
_WRITE_OWNER = 0x00080000

TARGET_FILE_MASK = _FILE_WRITE_DATA | _FILE_APPEND_DATA | _DELETE | _WRITE_DAC | _WRITE_OWNER
TARGET_DIRECTORY_MASK = (
    _FILE_ADD_FILE | _FILE_ADD_SUBDIRECTORY | _FILE_DELETE_CHILD
    | _DELETE | _WRITE_DAC | _WRITE_OWNER
)
ANCESTOR_MASK = _FILE_DELETE_CHILD | _DELETE | _WRITE_DAC | _WRITE_OWNER
"""IMG-06a: no ADD bits. Creating a sibling cannot replace an already-resolved link, and a
stock volume root grants exactly that right to every standard user (evidence §3.23)."""

REPLACE_PRIVILEGES: FrozenSet[str] = frozenset({
    "SeRestorePrivilege",       # write any file, DACL ignored
    "SeTakeOwnershipPrivilege",  # take ownership, then rewrite the DACL
    "SeBackupPrivilege",        # read any file, and the pair with SeRestore is the point
    "SeDebugPrivilege",         # open any process, including one holding the image open
    "SeImpersonatePrivilege",   # become a token that can do the above
    "SeLoadDriverPrivilege",    # kernel code, which ends every argument about file ACLs
})
"""Privileges that amount to "can replace" whatever a DACL says.

``AccessCheck`` accounts for ``SeTakeOwnershipPrivilege`` and nothing else here: the file
system consults ``SeRestorePrivilege`` and ``SeBackupPrivilege`` when a handle is opened, long
after this call. So a token holding one of these would pass a pure mask check and still be
able to replace the image — which is exactly how an elevated agentao becomes its own
attacker. **Presence, not enabled-state**: a token that holds a privilege can enable it.
"""

_AMBIENT_PATH_KEYS = (
    "XDG_CONFIG_HOME", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "PSModulePath",
    "PYTHONPATH", "NODE_PATH", "NODE_OPTIONS", "VIRTUAL_ENV", "CONDA_PREFIX",
    "JAVA_HOME", "CARGO_HOME", "RUSTUP_HOME", "GOPATH", "GOROOT", "DOTNET_ROOT",
)
"""ENV-06b: environment keys that carry a *path* and that this table does not register.

Not "every key in the environment" — that would report a novel unknown on every machine and
say nothing. These are the ones a rule would have to depend on if it registered them, which
is the criterion ENV-06g wrote down.
"""

_MAXIMUM_ALLOWED = 0x02000000
_FILE_ATTRIBUTE_DIRECTORY = 0x0010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
_TOKEN_QUERY = 0x0008
_TOKEN_DUPLICATE = 0x0002
_TokenUser = 1
_TokenPrivileges = 3
_SecurityImpersonation = 2
_SE_FILE_OBJECT = 1
_OWNER_INFO = 0x00000001
_GROUP_INFO = 0x00000002
_DACL_INFO = 0x00000004


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TOKEN_USER(ctypes.Structure):
    _fields_ = [("User", _SID_AND_ATTRIBUTES)]


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", _LUID), ("Attributes", wintypes.DWORD)]


class _GENERIC_MAPPING(ctypes.Structure):
    _fields_ = [
        ("GenericRead", wintypes.DWORD), ("GenericWrite", wintypes.DWORD),
        ("GenericExecute", wintypes.DWORD), ("GenericAll", wintypes.DWORD),
    ]


class _PRIVILEGE_SET(ctypes.Structure):
    """Sized for several entries: ``AccessCheck`` fails outright if this buffer is short."""

    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD), ("Control", wintypes.DWORD),
        ("Privilege", _LUID_AND_ATTRIBUTES * 16),
    ]


def _bind() -> Tuple[ctypes.WinDLL, ctypes.WinDLL]:
    """Load and declare the Win32 surface.

    Every prototype is spelled out. Undeclared, ``ctypes`` assumes a C ``int`` return, which
    truncates handles on 64-bit and turns ``GetFileAttributesW``'s INVALID_FILE_ATTRIBUTES
    into -1 so the failure test never fires — a trust check that silently measures the wrong
    thing is worse than one that refuses to run.
    """
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psid = ctypes.c_void_p
    psd = ctypes.c_void_p

    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetFileAttributesW.restype = wintypes.DWORD
    kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    kernel32.LocalFree.restype = ctypes.c_void_p
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.DuplicateToken.restype = wintypes.BOOL
    advapi32.DuplicateToken.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [psid, ctypes.POINTER(wintypes.LPWSTR)]
    advapi32.LookupPrivilegeNameW.restype = wintypes.BOOL
    advapi32.LookupPrivilegeNameW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(_LUID), wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD)]
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.POINTER(psid), ctypes.POINTER(psid),
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(psd)]
    advapi32.AccessCheck.restype = wintypes.BOOL
    advapi32.AccessCheck.argtypes = [
        psd, wintypes.HANDLE, wintypes.DWORD,
        ctypes.POINTER(_GENERIC_MAPPING), ctypes.POINTER(_PRIVILEGE_SET),
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.BOOL)]
    return advapi32, kernel32


def _token_information(advapi32: ctypes.WinDLL, token: wintypes.HANDLE,
                       cls: int) -> Optional[ctypes.Array]:
    size = wintypes.DWORD()
    advapi32.GetTokenInformation(token, cls, None, 0, ctypes.byref(size))
    if size.value == 0:
        return None
    buf = ctypes.create_string_buffer(size.value)
    if not advapi32.GetTokenInformation(token, cls, buf, size, ctypes.byref(size)):
        return None
    return buf


def _filesystem_identity(path: str) -> Optional[FsId]:
    """SPEC-04's identity, and ``st_ino == 0`` is not one.

    Python documents the field as identifying a file only when non-zero, and Windows reports
    zero whenever the file index is unavailable. Passing it through would give every such
    file the identity ``<dev>:0``, so a swap between two of them would compare equal and the
    re-check before spawning would report a clean result while proving nothing.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    if not st.st_ino:
        return None
    return FsId(f"{st.st_dev}:{st.st_ino}")


def token_sid() -> Optional[str]:
    """The current process token's user SID, as a string — the subject a child inherits."""
    advapi32, kernel32 = _bind()
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), _TOKEN_QUERY,
                                     ctypes.byref(token)):
        return None
    try:
        buf = _token_information(advapi32, token, _TokenUser)
        if buf is None:
            return None
        user = ctypes.cast(buf, ctypes.POINTER(_TOKEN_USER)).contents
        out = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(user.User.Sid, ctypes.byref(out)):
            return None
        try:
            return out.value
        finally:
            kernel32.LocalFree(out)
    finally:
        kernel32.CloseHandle(token)


def token_privileges() -> FrozenSet[str]:
    """Every privilege the current token *holds*, enabled or not.

    Enabled-state is not the question: a token that holds a privilege can enable it whenever
    it likes, so holding one is the fact that matters.
    """
    advapi32, kernel32 = _bind()
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), _TOKEN_QUERY,
                                     ctypes.byref(token)):
        return frozenset()
    try:
        buf = _token_information(advapi32, token, _TokenPrivileges)
        if buf is None:
            return frozenset()
        count = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value
        offset = ctypes.sizeof(wintypes.DWORD)
        array = ctypes.cast(
            ctypes.byref(buf, offset), ctypes.POINTER(_LUID_AND_ATTRIBUTES * count)).contents
        names = set()
        for entry in array:
            name = ctypes.create_unicode_buffer(256)
            length = wintypes.DWORD(256)
            if advapi32.LookupPrivilegeNameW(None, ctypes.byref(entry.Luid), name,
                                             ctypes.byref(length)):
                names.add(name.value)
        return frozenset(names)
    finally:
        kernel32.CloseHandle(token)


class WindowsAccessOracle:
    r"""IMG-06's file questions, against the token this process will hand its children.

    Bound to one subject (SPEC-05): every method that takes one refuses to answer for a
    different token, because an oracle that answered about some other machine's files for
    some other process would be attesting the wrong thing.

    **Every failure answers "can replace".** Not knowing is not "no": an unreadable security
    descriptor, a path that vanished, an ``AccessCheck`` that will not run — each of those is
    a chain nobody examined, and IMG-06c's whole point is that such a chain must not be walked
    as though it had been read and found ordinary.
    """

    #: ENV-06b — the environment keys this table registers, in `PinnedEnv` field order.
    #: A key present in the environment and absent here lands in ``unknown_keys``, which is
    #: how "the oracle handed back something nobody validated" stays visible.
    _PINNED_KEYS = (
        "SystemRoot", "windir", "SystemDrive", "ProgramData", "ProgramFiles",
        "ProgramFiles(x86)", "ProgramW6432", "CommonProgramFiles",
        "CommonProgramFiles(x86)", "ALLUSERSPROFILE", "PUBLIC", "ComSpec",
        "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
        "TEMP", "TMP", "TMPDIR",
    )

    #: IMG-05 (a): where a rung's interpreter is looked for. **Not PATH** — a PATH hit is not
    #: a candidate, because PATH is exactly what an attacker controls and ENV-01 exists to
    #: filter it. These are the install locations the interpreters actually use.
    _WELL_KNOWN = {
        Rung.pwsh: (
            r"%ProgramFiles%\PowerShell\7\pwsh.exe",
            r"%ProgramFiles%\PowerShell\6\pwsh.exe",
            r"%ProgramW6432%\PowerShell\7\pwsh.exe",
        ),
        Rung.powershell: (
            r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe",
        ),
        Rung.git_bash: (
            r"%ProgramFiles%\Git\bin\bash.exe",
            r"%ProgramFiles(x86)%\Git\bin\bash.exe",
            r"%ProgramW6432%\Git\bin\bash.exe",
        ),
        Rung.cmd: (
            r"%SystemRoot%\System32\cmd.exe",
        ),
    }

    def __init__(self, subject: Subject, project_root: Optional[str] = None) -> None:
        self._subject = subject
        self._project_root = project_root
        self._advapi32, self._kernel32 = _bind()
        self._client: Optional[wintypes.HANDLE] = None
        # Held privileges decide every answer before a DACL is read, so they are read once.
        # `AccessCheck` consults SeTakeOwnershipPrivilege and nothing else here — the file
        # system checks SeRestore and SeBackup when a handle opens, long after this call.
        self._privileged = bool(token_privileges() & REPLACE_PRIVILEGES)

    # -------------------------------------------------------------- the two masks

    def subject_can_replace(self, path: AbsPath, subject: Subject) -> bool:
        """IMG-06a's target mask: this path itself, and the directory holding a file."""
        if subject != self._subject:
            return True
        attributes = self._attributes(path)
        if attributes is None:
            return True
        mask = (TARGET_DIRECTORY_MASK if attributes & _FILE_ATTRIBUTE_DIRECTORY
                else TARGET_FILE_MASK)
        return self._granted_any(path, mask)

    def subject_can_replace_entries(self, path: AbsPath, subject: Subject) -> bool:
        """IMG-06a's ancestor mask: can this link be deleted, renamed or taken over."""
        if subject != self._subject:
            return True
        return self._granted_any(path, ANCESTOR_MASK)

    # -------------------------------------------------------------- the easy answers

    def canonicalize(self, path: str) -> Optional[AbsPath]:
        """IMG-06b. ``realpath`` resolves 8.3 short names, case and reparse points here.

        An alternate data stream is refused outright rather than normalised away: ``a.exe:x``
        names a different byte stream from ``a.exe`` and nothing downstream distinguishes them.
        """
        if not path or "\x00" in path:
            return None
        # A drive letter is the only legitimate colon in a Windows path. Every other colon
        # names an alternate data stream, and `a.exe:x` is a different byte sequence from
        # `a.exe` that nothing downstream tells apart — so it is refused, not normalised.
        drive, rest = os.path.splitdrive(path)
        if ":" in rest:
            return None
        if drive and not drive.startswith("\\") and not (
            len(drive) == 2 and drive[0].isalpha() and drive[1] == ":"
        ):
            return None
        try:
            resolved = os.path.realpath(path)
        except (OSError, ValueError):
            return None
        return AbsPath(resolved) if os.path.isabs(resolved) else None

    def resolves_on_target(self, path: AbsPath) -> bool:
        return os.path.exists(path)

    def content_hash(self, path: AbsPath) -> Sha256:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return Sha256(digest.hexdigest())

    def resolve_reparse(self, path: AbsPath) -> ReparseResult:
        """IMG-06c's three states. ``error`` is not ``not_reparse``."""
        attributes = self._attributes(path)
        if attributes is None:
            return ReparseResult(ReparseState.error)
        if not attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            return ReparseResult(ReparseState.not_reparse)
        try:
            target = os.path.realpath(path)
        except (OSError, ValueError):
            return ReparseResult(ReparseState.error)
        if not target or target == path or not os.path.isabs(target):
            return ReparseResult(ReparseState.error)
        return ReparseResult(ReparseState.resolved, AbsPath(target))

    # -------------------------------------------------------------- the target's shape

    def target_platform(self) -> Platform:
        return Platform.WINDOWS

    def target_filesystem_is_local(self) -> Optional[bool]:
        """SPEC-04a. This oracle only ever describes the machine it runs on."""
        return True

    def target_project_root(self) -> Optional[AbsPath]:
        return None if self._project_root is None else self.canonicalize(self._project_root)

    def target_base_env(self, subject: Subject) -> Optional[Mapping[str, str]]:
        if subject != self._subject:
            return None
        return dict(os.environ)

    def target_path_entries(self, subject: Subject) -> Optional[Tuple[AbsPath, ...]]:
        """ENV-01's raw material: the entries, canonical, in order, duplicates dropped.

        Canonicalising here rather than at the filter is the point of `canonicalize` having a
        caller at all: `path_within` is documented to take already-canonical paths, while a
        PATH entry is a raw environment string that may reach a directory through ``..``, an
        8.3 short name, or a junction.
        """
        if subject != self._subject:
            return None
        entries: list = []
        for raw in os.environ.get("PATH", "").split(os.pathsep):
            if not raw.strip():
                continue
            canonical = self.canonicalize(os.path.expandvars(raw.strip().strip('"')))
            if canonical is not None and canonical not in entries:
                entries.append(canonical)
        return tuple(entries)

    def target_pinned_env(self, subject: Subject) -> Optional[PinnedEnv]:
        """ENV-06: the closed set, read off the environment and typed by field.

        A key this table does not register goes into ``unknown_keys`` rather than being
        dropped: dropping it would report a validated environment when one key was never
        looked at, which is the failure ENV-06a is written against.
        """
        if subject != self._subject:
            return None
        get = os.environ.get

        def directory(name: str) -> Optional[AbsDir]:
            value = get(name)
            return AbsDir(value) if value else None

        unknown = frozenset(
            key for key in os.environ
            if key.upper() in {k.upper() for k in _AMBIENT_PATH_KEYS}
            and key.upper() not in {k.upper() for k in self._PINNED_KEYS}
        )
        return PinnedEnv(
            system_root=directory("SystemRoot"),
            windir=directory("windir"),
            system_drive=DriveSpec(get("SystemDrive")) if get("SystemDrive") else None,
            program_data=directory("ProgramData"),
            program_files=directory("ProgramFiles"),
            program_files_x86=directory("ProgramFiles(x86)"),
            program_w6432=directory("ProgramW6432"),
            common_program_files=directory("CommonProgramFiles"),
            common_program_files_x86=directory("CommonProgramFiles(x86)"),
            all_users_profile=directory("ALLUSERSPROFILE"),
            public=directory("PUBLIC"),
            com_spec=AbsFile(get("ComSpec")) if get("ComSpec") else None,
            home=AbsDir(get("USERPROFILE") or ""),
            user_profile=directory("USERPROFILE"),
            home_drive=DriveSpec(get("HOMEDRIVE")) if get("HOMEDRIVE") else None,
            home_path=RootRelPath(get("HOMEPATH")) if get("HOMEPATH") else None,
            appdata=directory("APPDATA"),
            local_appdata=directory("LOCALAPPDATA"),
            temp=AbsDir(get("TEMP") or ""),
            tmp=AbsDir(get("TMP") or ""),
            tmpdir=None,  # a Windows target has no TMPDIR field (ENV-06f)
            unknown_keys=unknown,
        )

    # -------------------------------------------------------------- images

    def resolve_image(self, path: AbsPath, subject: Subject) -> Optional[ResolvedImage]:
        """A path is a name for a file; this is the file. SPEC-04's filesystem identity is
        what makes "the same image" a question the executor can re-ask before it spawns."""
        if subject != self._subject:
            return None
        canonical = self.canonicalize(path)
        if canonical is None or not os.path.isfile(canonical):
            return None
        identity = _filesystem_identity(canonical)
        if identity is None:
            return None  # unidentifiable is not identified
        return ResolvedImage(
            canonical_path=canonical,
            filesystem_identity=identity,
            execution_subject=subject,
        )

    def discover(self, rung: Rung, subject: Subject) -> Optional[ResolvedImage]:
        """IMG-05 (a): the install locations, never PATH.

        A PATH hit is not a candidate. PATH is the thing an attacker gets to shape, and
        ENV-01 exists to filter it — resolving the interpreter through it would put the
        answer back in the attacker's hands before any filtering happened.
        """
        if subject != self._subject:
            return None
        for template in self._WELL_KNOWN.get(rung, ()):
            expanded = os.path.expandvars(template)
            if "%" in expanded:
                continue  # an unset variable, not a path
            image = self.resolve_image(AbsPath(expanded), subject)
            if image is not None:
                return image
        return None

    # -------------------------------------------------------------- internals

    def _attributes(self, path: str) -> Optional[int]:
        value = self._kernel32.GetFileAttributesW(path)
        return None if value == 0xFFFFFFFF else int(value)

    def _client_token(self) -> Optional[wintypes.HANDLE]:
        if self._client is not None:
            return self._client
        token = wintypes.HANDLE()
        if not self._advapi32.OpenProcessToken(
            self._kernel32.GetCurrentProcess(), _TOKEN_QUERY | _TOKEN_DUPLICATE,
            ctypes.byref(token),
        ):
            return None
        try:
            dup = wintypes.HANDLE()
            # `AccessCheck` takes a *client* token, so the process token is duplicated to an
            # impersonation one. Nothing impersonates: the duplicate is only a shape.
            if not self._advapi32.DuplicateToken(token, _SecurityImpersonation,
                                                 ctypes.byref(dup)):
                return None
            self._client = dup
            return dup
        finally:
            self._kernel32.CloseHandle(token)

    def _granted_any(self, path: str, mask: int) -> bool:
        if self._privileged:
            return True  # a held privilege outranks every DACL on the machine
        client = self._client_token()
        if client is None:
            return True
        owner = ctypes.c_void_p()
        descriptor = ctypes.c_void_p()
        error = self._advapi32.GetNamedSecurityInfoW(
            path, _SE_FILE_OBJECT, _OWNER_INFO | _GROUP_INFO | _DACL_INFO,
            ctypes.byref(owner), None, None, None, ctypes.byref(descriptor),
        )
        if error != 0:
            return True
        try:
            mapping = _GENERIC_MAPPING(0x120089, 0x120116, 0x1200A0, 0x1F01FF)
            privileges = _PRIVILEGE_SET()
            length = wintypes.DWORD(ctypes.sizeof(_PRIVILEGE_SET))
            granted = wintypes.DWORD()
            status = wintypes.BOOL()
            ok = self._advapi32.AccessCheck(
                descriptor, client, _MAXIMUM_ALLOWED, ctypes.byref(mapping),
                ctypes.byref(privileges), ctypes.byref(length),
                ctypes.byref(granted), ctypes.byref(status),
            )
            if not ok:
                return True
            return bool(granted.value & mask)
        finally:
            self._kernel32.LocalFree(descriptor)
