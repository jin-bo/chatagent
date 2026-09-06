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
import json
import os
import subprocess
from ctypes import wintypes
from typing import Dict, FrozenSet, Mapping, Optional, Tuple

from ..capabilities.process import run_captured
from ..capabilities.shell_spec import (
    AbsDir,
    AbsFile,
    AbsPath,
    DriveSpec,
    FsId,
    PinnedEnv,
    Platform,
    InterpreterIdentity,
    LauncherIdentity,
    ResolvedImage,
    RootRelPath,
    Rung,
    Sha256,
    Subject,
)
from ..capabilities.shell_spec import ShellDialect
from ._trust import ReparseResult, ReparseState, SessionConfig

__all__ = [
    "ANCESTOR_MASK",
    "native_oracle",
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
        self._facts: Dict[str, Optional[Tuple[str, str, str]]] = {}
        self._trust: Dict[str, int] = {}
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

    # -------------------------------------------------------------- Authenticode

    def publisher_trusted(self, path: AbsPath) -> bool:
        r"""IMG-05 route (1): does this machine's own trust store vouch for the image.

        ``WinVerifyTrust`` under the generic-verify action is exactly that question: the
        signature must be intact *and* chain to a root this machine trusts. Anything short of
        ``ERROR_SUCCESS`` is a no — including "no signature", "untrusted root", and "the
        check could not run".

        **Embedded first, then the catalog.** Most of Windows is not signed in the file: a
        system binary's signature lives in a ``.cat`` under the catalog database, and a check
        that reads only the embedded PKCS#7 reports ``cmd.exe`` and ``powershell.exe`` as
        unsigned — which would make this route decorative for the exact interpreters the
        ladder targets. Measured on the Windows job, which is where it surfaced.
        """
        return self._verify_trust(path) == 0

    def image_signer(self, path: AbsPath) -> Optional[str]:
        r"""IMG-03b route (2): the signer's subject name, or ``None`` if there is not one.

        **Only read after the chain verifies.** A name lifted from an unverified signature is
        an attacker-supplied string, and an allowlist that matched it would be trusting the
        very file it was asked to check. So a failed ``WinVerifyTrust`` answers ``None`` here
        rather than "signed by whoever it says".
        """
        if self._verify_trust(path) != 0:
            return None
        embedded = self._signer_name(path)
        if embedded is not None:
            return embedded
        # A catalog-signed file carries no PKCS#7 of its own; the signature is on the
        # catalog, so that is where its signer's name is.
        catalog = self._catalog_for(path)
        return None if catalog is None else self._signer_name(catalog[0])

    # -------------------------------------------------------------- the interpreter

    def read_identity(
        self, img: ResolvedImage, dialect: ShellDialect
    ) -> Optional[LauncherIdentity]:
        """IMG-07: the launcher's hash, plus the four facts a PowerShell rung reads.

        ``image=img`` is the same object the caller passed, not an equal one: ``select_rung``
        checks ``identity.image is not img`` and a rebuilt record would fail that identity
        test for no reason.
        """
        try:
            launcher_hash = self.content_hash(img.canonical_path)
        except OSError:
            return None
        if dialect is not ShellDialect.POWERSHELL:
            return LauncherIdentity(image=img, launcher_hash=launcher_hash)

        facts = self._interpreter_facts(img.canonical_path)
        if facts is None:
            return None
        edition, version, pshome = facts
        resolved = self.canonicalize(pshome)
        if resolved is None:
            return None
        return InterpreterIdentity(
            image=img,
            launcher_hash=launcher_hash,
            edition=edition,
            version=version,
            pshome=resolved,
            session_config=self.read_config_sources(resolved, self._subject).session,
        )

    def resolve_pshome(self, img: ResolvedImage) -> Optional[AbsPath]:
        r"""IMG-08: the install root the *assembly* lives in, asked of the interpreter itself.

        Never the launcher's own directory. ``$PSHOME`` is defined as the directory of the
        executing ``System.Management.Automation.dll``, so when the launcher is a shim, a
        symlink or a copy it is somewhere else — and it is that other directory whose writer
        can change what the interpreter *is* without touching the hashed launcher (§3.20).
        """
        facts = self._interpreter_facts(img.canonical_path)
        return None if facts is None else self.canonicalize(facts[2])

    def read_config_sources(self, pshome: AbsPath, subject: Subject) -> SessionConfig:
        r"""IMG-08's three sources, read from disk before anything is launched.

        **A source that cannot be read reports a configuration rather than none**, which
        refuses the rung. The alternative is to report "no configuration" for a file nobody
        managed to open, and that is the same shape as IMG-06c's unreadable reparse point:
        an unexamined thing must not be recorded as examined and ordinary.

        Group Policy takes precedence over both files, and it is the upstream document that
        says so rather than an inference from the two files' scopes.
        """
        if subject != self._subject:
            return SessionConfig(session="<subject mismatch>")

        candidates = [os.path.join(pshome, "powershell.config.json")]
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(os.path.join(appdata, "powershell", "powershell.config.json"))

        for path in candidates:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8-sig") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                return SessionConfig(session=f"<unreadable: {path}>")
            if not isinstance(data, dict):
                return SessionConfig(session=f"<malformed: {path}>")
            for key in ("ConsoleSessionConfigurationName", "PSSessionConfigurationName"):
                value = data.get(key)
                if value:
                    return SessionConfig(session=str(value))

        policy = self._group_policy_session()
        if policy is not None:
            return SessionConfig(session=policy)
        return SessionConfig(session=None)

    def preflight(self, identity: InterpreterIdentity, prelude: str) -> bool:
        """IMG-09: run the very prelude a launch would run, and require a clean exit.

        The *same* string, not an equivalent one. The prelude's guard exits 97 when the
        interpreter is not the attested one and its relocation exits 98; running a simplified
        version here would establish something other than what the launch establishes.
        """
        try:
            result = run_captured(
                [str(identity.path), "-NoProfile", "-NonInteractive", "-Command", prelude],
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0

    # -------------------------------------------------------------- internals

    def _verify_trust(self, path: str) -> int:
        r"""``WinVerifyTrust``'s status, cached per path.

        ``WTD_UI_NONE`` because this runs headless: a prompt here would hang a turn rather
        than answer. State is opened and closed around the call as the API requires; leaking
        the close leaves the chain-engine context alive for the life of the process.
        """
        if path in self._trust:
            return self._trust[path]
        status = self._verify_trust_uncached(path)
        self._trust[path] = status
        return status

    def _verify_trust_uncached(self, path: str) -> int:
        embedded = self._verify_embedded(path)
        if embedded == 0:
            return embedded
        return self._verify_catalog(path)

    def _verify_embedded(self, path: str) -> int:
        try:
            wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
        except OSError:
            return -1  # no wintrust is "could not check", which is not "trusted"

        class _GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        class _FILE_INFO(ctypes.Structure):
            _fields_ = [("cbStruct", wintypes.DWORD), ("pcwszFilePath", wintypes.LPCWSTR),
                        ("hFile", wintypes.HANDLE), ("pgKnownSubject", ctypes.c_void_p)]

        class _WINTRUST_DATA(ctypes.Structure):
            _fields_ = [
                ("cbStruct", wintypes.DWORD), ("pPolicyCallbackData", ctypes.c_void_p),
                ("pSIPClientData", ctypes.c_void_p), ("dwUIChoice", wintypes.DWORD),
                ("fdwRevocationChecks", wintypes.DWORD), ("dwUnionChoice", wintypes.DWORD),
                ("pFile", ctypes.POINTER(_FILE_INFO)), ("dwStateAction", wintypes.DWORD),
                ("hWVTStateData", wintypes.HANDLE), ("pwszURLReference", wintypes.LPWSTR),
                ("dwProvFlags", wintypes.DWORD), ("dwUIContext", wintypes.DWORD),
                ("pSignatureSettings", ctypes.c_void_p),
            ]

        # WINTRUST_ACTION_GENERIC_VERIFY_V2
        action = _GUID(0xAAC56B, 0xCD44, 0x11D0,
                       (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
        info = _FILE_INFO(ctypes.sizeof(_FILE_INFO), path, None, None)
        data = _WINTRUST_DATA()
        data.cbStruct = ctypes.sizeof(_WINTRUST_DATA)
        data.dwUIChoice = 2            # WTD_UI_NONE
        data.fdwRevocationChecks = 0   # WTD_REVOKE_NONE: the chain, not the CRL round trip
        data.dwUnionChoice = 1         # WTD_CHOICE_FILE
        data.pFile = ctypes.pointer(info)
        data.dwStateAction = 1         # WTD_STATEACTION_VERIFY
        data.dwProvFlags = 0x00000010  # WTD_SAFER_FLAG

        wintrust.WinVerifyTrust.restype = wintypes.LONG
        wintrust.WinVerifyTrust.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_GUID), ctypes.c_void_p]
        status = wintrust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(data))
        data.dwStateAction = 2         # WTD_STATEACTION_CLOSE
        wintrust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(data))
        return int(status)

    def _catalog_context(self, algorithm: Optional[str]) -> Optional[ctypes.c_void_p]:
        """A ``CryptCATAdmin`` context, SHA-256 when the OS offers the newer entry point.

        ``CryptCATAdminAcquireContext`` hashes with SHA-1. Modern catalogs are SHA-256, and a
        SHA-1 member tag will not verify against one however well the enumeration worked —
        which is why the lookup can succeed and the verification still fail.
        """
        wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
        admin = ctypes.c_void_p()
        if algorithm is not None:
            try:
                wintrust.CryptCATAdminAcquireContext2.restype = wintypes.BOOL
                ok = wintrust.CryptCATAdminAcquireContext2(
                    ctypes.byref(admin), None, wintypes.LPCWSTR(algorithm), None, 0)
            except AttributeError:
                return None
            return admin if ok else None
        wintrust.CryptCATAdminAcquireContext.restype = wintypes.BOOL
        ok = wintrust.CryptCATAdminAcquireContext(ctypes.byref(admin), None, 0)
        return admin if ok else None

    def _file_hash_for_catalog(self, admin: ctypes.c_void_p, path: str):
        """``(buffer, length)`` of the catalog-member hash, or ``None``."""
        wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
        kernel32 = self._kernel32
        GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING = 0x80000000, 0x00000001, 3
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        handle = kernel32.CreateFileW(
            path, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, 0, None)
        if not handle or handle == ctypes.c_void_p(-1).value:
            return None
        try:
            size = wintypes.DWORD(0)
            wintrust.CryptCATAdminCalcHashFromFileHandle2.restype = wintypes.BOOL
            try:
                wintrust.CryptCATAdminCalcHashFromFileHandle2(
                    admin, wintypes.HANDLE(handle), ctypes.byref(size), None, 0)
                if size.value:
                    digest = (ctypes.c_ubyte * size.value)()
                    if wintrust.CryptCATAdminCalcHashFromFileHandle2(
                        admin, wintypes.HANDLE(handle), ctypes.byref(size), digest, 0,
                    ):
                        return digest, size
            except AttributeError:
                pass
            size = wintypes.DWORD(0)
            wintrust.CryptCATAdminCalcHashFromFileHandle.restype = wintypes.BOOL
            wintrust.CryptCATAdminCalcHashFromFileHandle(
                wintypes.HANDLE(handle), ctypes.byref(size), None, 0)
            if not size.value:
                return None
            digest = (ctypes.c_ubyte * size.value)()
            if not wintrust.CryptCATAdminCalcHashFromFileHandle(
                wintypes.HANDLE(handle), ctypes.byref(size), digest, 0,
            ):
                return None
            return digest, size
        finally:
            kernel32.CloseHandle(wintypes.HANDLE(handle))

    def _catalog_for(self, path: str) -> Optional[Tuple[str, str]]:
        """``(catalog file, member tag)`` for a catalog-signed file, or ``None``.

        The member tag is the file's hash as uppercase hex, which is how a catalog names its
        members. SHA-256 is tried first because that is what current catalogs use.
        """
        found = self._catalog_lookup(path)
        return None if found is None else (found[0], found[1])

    def _catalog_lookup(self, path: str):
        """``(catalog file, member tag, admin, digest, length)``, holding the context open.

        The admin handle is part of the answer rather than an implementation detail:
        ``WinVerifyTrust`` needs it to know which hash algorithm produced the member tag.
        """
        try:
            wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
        except OSError:
            return None
        for algorithm in ("SHA256", None):
            admin = self._catalog_context(algorithm)
            if admin is None:
                continue
            hashed = self._file_hash_for_catalog(admin, path)
            if hashed is None:
                wintrust.CryptCATAdminReleaseContext(admin, 0)
                continue
            digest, size = hashed
            wintrust.CryptCATAdminEnumCatalogFromHash.restype = ctypes.c_void_p
            info = wintrust.CryptCATAdminEnumCatalogFromHash(admin, digest, size, 0, None)
            if not info:
                wintrust.CryptCATAdminReleaseContext(admin, 0)
                continue
            try:
                class _CATALOG_INFO(ctypes.Structure):
                    _fields_ = [("cbStruct", wintypes.DWORD),
                                ("wszCatalogFile", ctypes.c_wchar * 260)]

                details = _CATALOG_INFO()
                details.cbStruct = ctypes.sizeof(_CATALOG_INFO)
                wintrust.CryptCATCatalogInfoFromContext.restype = wintypes.BOOL
                if not wintrust.CryptCATCatalogInfoFromContext(
                    ctypes.c_void_p(info), ctypes.byref(details), 0,
                ):
                    continue
                tag = "".join(f"{b:02X}" for b in digest)
                return details.wszCatalogFile, tag, admin, digest, size
            finally:
                wintrust.CryptCATAdminReleaseCatalogContext(admin, ctypes.c_void_p(info), 0)
        return None

    def _verify_catalog(self, path: str) -> int:
        """Verify ``path`` against the catalog that names it."""
        found = self._catalog_lookup(path)
        if found is None:
            return -2  # no catalog names this file; not the same fact as "not signed"
        catalog, tag, admin, digest, size = found
        try:
            wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
        except OSError:
            return -1

        class _GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        class _CATALOG_INFO_W(ctypes.Structure):
            _fields_ = [
                ("cbStruct", wintypes.DWORD), ("dwCatalogVersion", wintypes.DWORD),
                ("pcwszCatalogFilePath", wintypes.LPCWSTR),
                ("pcwszMemberTag", wintypes.LPCWSTR),
                ("pcwszMemberFilePath", wintypes.LPCWSTR),
                ("hMemberFile", wintypes.HANDLE),
                ("pbCalculatedFileHash", ctypes.c_void_p),
                ("cbCalculatedFileHash", wintypes.DWORD),
                ("pcCatalogContext", ctypes.c_void_p),
                ("hCatAdmin", ctypes.c_void_p),
            ]

        class _WINTRUST_DATA(ctypes.Structure):
            _fields_ = [
                ("cbStruct", wintypes.DWORD), ("pPolicyCallbackData", ctypes.c_void_p),
                ("pSIPClientData", ctypes.c_void_p), ("dwUIChoice", wintypes.DWORD),
                ("fdwRevocationChecks", wintypes.DWORD), ("dwUnionChoice", wintypes.DWORD),
                ("pCatalog", ctypes.POINTER(_CATALOG_INFO_W)),
                ("dwStateAction", wintypes.DWORD),
                ("hWVTStateData", wintypes.HANDLE), ("pwszURLReference", wintypes.LPWSTR),
                ("dwProvFlags", wintypes.DWORD), ("dwUIContext", wintypes.DWORD),
                ("pSignatureSettings", ctypes.c_void_p),
            ]

        try:
            action = _GUID(0xAAC56B, 0xCD44, 0x11D0,
                           (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
            info = _CATALOG_INFO_W()
            info.cbStruct = ctypes.sizeof(_CATALOG_INFO_W)
            info.pcwszCatalogFilePath = catalog
            info.pcwszMemberTag = tag
            info.pcwszMemberFilePath = path
            # Handing back the hash and the context is what tells WinVerifyTrust which
            # algorithm produced the tag; without them it assumes SHA-1 and a SHA-256
            # catalog never matches — the lookup succeeds and the verification fails.
            info.pbCalculatedFileHash = ctypes.cast(digest, ctypes.c_void_p)
            info.cbCalculatedFileHash = size
            info.hCatAdmin = admin
            data = _WINTRUST_DATA()
            data.cbStruct = ctypes.sizeof(_WINTRUST_DATA)
            data.dwUIChoice = 2
            data.fdwRevocationChecks = 0
            data.dwUnionChoice = 2  # WTD_CHOICE_CATALOG
            data.pCatalog = ctypes.pointer(info)
            data.dwStateAction = 1
            wintrust.WinVerifyTrust.restype = wintypes.LONG
            wintrust.WinVerifyTrust.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(_GUID), ctypes.c_void_p]
            status = wintrust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(data))
            data.dwStateAction = 2
            wintrust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(data))
            return int(status)
        finally:
            wintrust.CryptCATAdminReleaseContext(admin, 0)

    def _signer_name(self, path: str) -> Optional[str]:
        """The signing certificate's subject, via the file's PKCS#7 message."""
        try:
            crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        except OSError:
            return None

        CERT_QUERY_OBJECT_FILE = 1
        CERT_QUERY_CONTENT_FLAG_PKCS7_SIGNED_EMBED = 1 << 10
        CERT_QUERY_FORMAT_FLAG_BINARY = 1 << 1
        CMSG_SIGNER_CERT_INFO_PARAM = 7
        CERT_FIND_SUBJECT_CERT = 0x000B0000
        X509_ASN_ENCODING = 0x00000001
        PKCS_7_ASN_ENCODING = 0x00010000
        CERT_NAME_SIMPLE_DISPLAY_TYPE = 4

        store = ctypes.c_void_p()
        message = ctypes.c_void_p()
        crypt32.CryptQueryObject.restype = wintypes.BOOL
        if not crypt32.CryptQueryObject(
            CERT_QUERY_OBJECT_FILE, wintypes.LPCWSTR(path),
            CERT_QUERY_CONTENT_FLAG_PKCS7_SIGNED_EMBED, CERT_QUERY_FORMAT_FLAG_BINARY,
            0, None, None, None, ctypes.byref(store), ctypes.byref(message), None,
        ):
            return None
        try:
            size = wintypes.DWORD()
            crypt32.CryptMsgGetParam.restype = wintypes.BOOL
            if not crypt32.CryptMsgGetParam(
                message, CMSG_SIGNER_CERT_INFO_PARAM, 0, None, ctypes.byref(size),
            ):
                return None
            buf = ctypes.create_string_buffer(size.value)
            if not crypt32.CryptMsgGetParam(
                message, CMSG_SIGNER_CERT_INFO_PARAM, 0, buf, ctypes.byref(size),
            ):
                return None
            crypt32.CertFindCertificateInStore.restype = ctypes.c_void_p
            context = crypt32.CertFindCertificateInStore(
                store, X509_ASN_ENCODING | PKCS_7_ASN_ENCODING, 0,
                CERT_FIND_SUBJECT_CERT, buf, None,
            )
            if not context:
                return None
            try:
                crypt32.CertGetNameStringW.restype = wintypes.DWORD
                length = crypt32.CertGetNameStringW(
                    ctypes.c_void_p(context), CERT_NAME_SIMPLE_DISPLAY_TYPE, 0, None, None, 0)
                if length <= 1:
                    return None
                name = ctypes.create_unicode_buffer(length)
                crypt32.CertGetNameStringW(
                    ctypes.c_void_p(context), CERT_NAME_SIMPLE_DISPLAY_TYPE, 0, None,
                    name, length)
                return name.value or None
            finally:
                crypt32.CertFreeCertificateContext(ctypes.c_void_p(context))
        finally:
            if message:
                crypt32.CryptMsgClose(message)
            if store:
                crypt32.CertCloseStore(store, 0)

    def _interpreter_facts(self, path: str) -> Optional[Tuple[str, str, str]]:
        """``(edition, version, $PSHOME)``, read from the interpreter, cached per path.

        Cached because ``read_identity`` and ``resolve_pshome`` both want it and each call is
        a process launch; the cache is per oracle instance, which is per decision.
        """
        if path in self._facts:
            return self._facts[path]
        script = (
            "$ErrorActionPreference='Stop';"
            "Write-Output $PSVersionTable.PSEdition;"
            "Write-Output $PSVersionTable.PSVersion.ToString();"
            "Write-Output ([System.IO.Path]::GetFullPath($PSHOME))"
        )
        try:
            result = run_captured(
                [path, "-NoProfile", "-NonInteractive", "-Command", script], timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            self._facts[path] = None
            return None
        lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        facts = (
            (lines[0], lines[1], lines[2])
            if result.returncode == 0 and len(lines) >= 3 else None
        )
        self._facts[path] = facts
        return facts

    def _group_policy_session(self) -> Optional[str]:
        """The policy source, which outranks both files.

        Absent means absent; a registry that cannot be read reports a configuration, for the
        same reason an unreadable file does.
        """
        try:
            import winreg
        except ImportError:
            return "<no registry>"
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, r"SOFTWARE\Policies\Microsoft\PowerShellCore") as key:
                    value, _ = winreg.QueryValueEx(key, "ConsoleSessionConfigurationName")
                    if value:
                        return str(value)
            except FileNotFoundError:
                continue
            except OSError:
                return "<policy unreadable>"
        return None



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


def native_oracle(
    subject: Optional[Subject] = None, project_root: Optional[str] = None
) -> Optional[WindowsAccessOracle]:
    r"""The oracle for this machine, or ``None`` where there is not one.

    The seam PR-7 needs. Rung selection is the ladder's job and ``default_spec`` refuses to do
    it once the flip is set — deliberately, so the stage that flips the constant *replaces*
    that function rather than editing it. This exists so that stage has a factory to call
    instead of reaching into a private class.

    ``None`` off Windows, and ``None`` when the token cannot be named: an oracle that could
    not say whose access it was describing would be answering about nothing in particular,
    and SPEC-05 binds every answer to one subject.
    """
    if os.name != "nt":
        return None
    if subject is None:
        sid = token_sid()
        if sid is None:
            return None
        subject = Subject(sid)
    return WindowsAccessOracle(subject, project_root)
