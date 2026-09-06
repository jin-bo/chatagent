r"""The native oracle's two access-mask questions, against ACLs this test writes itself.

Most of this file only runs on Windows, and that is the point: the questions are about a real
token and a real security descriptor, and a fake of either would only restate what the code
already believes (there is no way to falsify a mask check with a stub that returns the mask).

**The runner is an administrator.** Measured, not assumed — see `docs/reference/
powershell-support-evidence.zh.md` §3.23. So the privilege short-circuit answers "can
replace" for everything there, which is correct and makes every DACL test vacuous. The tests
below therefore assert the short-circuit *once*, on its own, and then disable it so the mask
logic underneath can be exercised. Disabling it is honest here precisely because the thing
being tested is the DACL arithmetic, not the privilege rule.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from agentao.capabilities.shell_spec import Subject
from agentao.permissions_hardline._windows_identity import (
    ANCESTOR_MASK,
    REPLACE_PRIVILEGES,
    TARGET_DIRECTORY_MASK,
    TARGET_FILE_MASK,
    WindowsAccessOracle,
    token_privileges,
    token_sid,
)

windows_only = pytest.mark.skipif(os.name != "nt", reason="a Windows token and a real DACL")

_ADD_BITS = 0x0002 | 0x0004  # FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY


# --------------------------------------------------------------- everywhere


def test_the_ancestor_mask_drops_exactly_the_two_add_rights():
    r"""IMG-06a's split, stated as arithmetic so it cannot drift quietly.

    A stock ``C:\`` grants standard users FILE_ADD_SUBDIRECTORY and nothing else on this
    list, so an ancestor mask containing either ADD bit makes IMG-01 false for every path on
    every machine (evidence §3.23).
    """
    assert ANCESTOR_MASK & _ADD_BITS == 0
    assert TARGET_DIRECTORY_MASK & _ADD_BITS == _ADD_BITS
    assert ANCESTOR_MASK & TARGET_DIRECTORY_MASK == ANCESTOR_MASK  # strictly narrower


def test_the_file_target_mask_covers_writing_the_image_itself():
    assert TARGET_FILE_MASK & 0x0002  # FILE_WRITE_DATA — the same bit as FILE_ADD_FILE
    assert TARGET_FILE_MASK & 0x00010000  # DELETE


def test_the_privilege_list_names_the_ones_access_check_does_not_apply():
    """``AccessCheck`` consults SeTakeOwnershipPrivilege and no other on this list; the file
    system consults SeRestore and SeBackup when a handle opens, long after that call."""
    assert {"SeRestorePrivilege", "SeBackupPrivilege"} <= REPLACE_PRIVILEGES


# --------------------------------------------------------------- Windows only


def _icacls(path, *args: str) -> None:
    result = subprocess.run(
        ["icacls", str(path), *args], capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"icacls {args}: {result.stdout}{result.stderr}"


def _acl_of(path) -> str:
    """The effective ACL, for an assertion message that explains itself."""
    result = subprocess.run(["icacls", str(path)], capture_output=True, text=True, timeout=60)
    return result.stdout.strip() or result.stderr.strip()


_ADMINISTRATORS = "S-1-5-32-544"


def _disowned(path, subject: Subject, rights: str) -> None:
    r"""Give ``subject`` exactly ``rights`` on ``path``, and give ownership away.

    Two Windows facts make the obvious version of this silently do nothing.

    **Ownership implies WRITE_DAC**, which is in both of IMG-06a's masks: rewrite the DACL
    and you can grant yourself anything. A directory the test creates is owned by the very
    subject it asks about, so "can replace" is the right answer and a refusal cannot be
    observed until ownership moves. IMG-01 says this outright ("or ownership").

    **``/inheritance:r`` removes inherited ACEs, and the one that matters is not inherited.**
    A ``CREATOR OWNER`` ACE on the parent materialises as an *explicit* full-control ACE for
    the creator at creation time, so it survives that flag untouched. The explicit ACEs have
    to be removed by name, which is why this is four invocations and not one.

    Ownership goes last, because handing it away costs the WRITE_DAC the earlier steps need.
    ``icacls`` can still do it since the runner holds SeTakeOwnershipPrivilege — the same
    privilege the oracle short-circuits on, and that these tests disable.
    """
    _icacls(path, "/inheritance:r")
    _icacls(path, "/remove", f"*{subject}", f"*{_ADMINISTRATORS}")
    _icacls(path, "/grant", f"*{subject}:({rights})")
    _icacls(path, "/setowner", "NT AUTHORITY\\SYSTEM")


@pytest.fixture
def subject() -> Subject:
    sid = token_sid()
    assert sid, "the oracle cannot bind to a subject it cannot name"
    return Subject(sid)


@pytest.fixture
def oracle(subject, monkeypatch):
    """An oracle with the privilege short-circuit off, so the DACL arithmetic is reachable.

    Asserted separately by ``test_a_privileged_token_can_replace_everything``; without that
    pairing this fixture would be quietly weakening the thing it tests.
    """
    built = WindowsAccessOracle(subject)
    monkeypatch.setattr(built, "_privileged", False)
    return built


@windows_only
def test_a_privileged_token_can_replace_everything(subject, tmp_path):
    """The rule that makes an elevated agentao its own attacker, and the reason the trusted
    set is empty on this runner."""
    built = WindowsAccessOracle(subject)
    locked = tmp_path / "locked"
    locked.mkdir()
    _disowned(locked, subject, "RX")

    if token_privileges() & REPLACE_PRIVILEGES:
        assert built.subject_can_replace(str(locked), subject) is True
        assert built.subject_can_replace_entries(str(locked), subject) is True
    else:
        pytest.skip("this token holds none of the replace privileges; nothing to assert")


@windows_only
def test_a_read_execute_directory_is_not_replaceable(oracle, subject, tmp_path):
    target = tmp_path / "readonly"
    target.mkdir()
    _disowned(target, subject, "RX")

    acl = _acl_of(target)
    assert oracle.subject_can_replace(str(target), subject) is False, acl
    assert oracle.subject_can_replace_entries(str(target), subject) is False, acl


@windows_only
def test_a_modifiable_directory_is_replaceable_under_both_masks(oracle, subject, tmp_path):
    target = tmp_path / "writable"
    target.mkdir()
    _disowned(target, subject, "M")

    acl = _acl_of(target)
    assert oracle.subject_can_replace(str(target), subject) is True, acl
    assert oracle.subject_can_replace_entries(str(target), subject) is True, acl


@windows_only
def test_add_only_is_the_case_the_split_exists_for(oracle, subject, tmp_path):
    r"""The stock volume root's shape, reproduced in a directory this test owns.

    ``C:\`` grants standard users add-subdirectory and none of delete, delete-child,
    write-DAC or write-owner. Under one mask that made every ancestor chain fail; under two,
    it is replaceable *as a target* and harmless *as an ancestor*, which is exactly the
    distinction between planting something new and replacing what resolved.
    """
    target = tmp_path / "addonly"
    target.mkdir()
    _disowned(target, subject, "RX,AD,WD")

    acl = _acl_of(target)
    assert oracle.subject_can_replace(str(target), subject) is True, acl
    assert oracle.subject_can_replace_entries(str(target), subject) is False, acl


@windows_only
def test_delete_child_is_dangerous_under_both_masks(oracle, subject, tmp_path):
    """Deleting or renaming the next link *is* replacing it, so the narrow mask keeps this."""
    target = tmp_path / "deletechild"
    target.mkdir()
    _disowned(target, subject, "RX,DC")

    assert oracle.subject_can_replace_entries(str(target), subject) is True, _acl_of(target)


@windows_only
def test_ownership_alone_answers_can_replace(oracle, subject, tmp_path):
    r"""IMG-01's "or ownership", and the reason every other case here gives ownership away.

    An owner implicitly holds READ_CONTROL and WRITE_DAC whatever the DACL grants, so it can
    rewrite that DACL and then hold anything. This directory is granted read-execute only and
    keeps its owner, and both masks still answer "can replace" — which is the code being
    right. Without this case the ``_disowned`` helper looks like ceremony.
    """
    owned = tmp_path / "owned"
    owned.mkdir()
    _icacls(owned, "/inheritance:r", "/grant", f"*{subject}:(RX)")

    assert oracle.subject_can_replace(str(owned), subject) is True
    assert oracle.subject_can_replace_entries(str(owned), subject) is True


@windows_only
def test_a_different_subject_is_refused_rather_than_answered(oracle, tmp_path):
    """SPEC-05: an oracle bound to one subject may not answer about another one."""
    target = tmp_path / "readonly2"
    target.mkdir()
    assert oracle.subject_can_replace(str(target), Subject("S-1-5-21-0-0-0-1234")) is True


@windows_only
def test_a_path_that_does_not_exist_answers_can_replace(oracle, subject, tmp_path):
    """Not knowing is not "no" — an unexamined path must not be walked as examined."""
    assert oracle.subject_can_replace(str(tmp_path / "absent"), subject) is True


@windows_only
def test_a_file_uses_the_file_mask_and_a_directory_the_directory_mask(oracle, subject, tmp_path):
    """Add-file on a *file* is write-data, which is replacing it; on a directory it is not."""
    image = tmp_path / "img.exe"
    image.write_bytes(b"MZ")
    _disowned(image, subject, "RX,WD")

    assert oracle.subject_can_replace(str(image), subject) is True


@windows_only
def test_content_hash_matches_hashlib(oracle, tmp_path):
    import hashlib

    blob = tmp_path / "blob.bin"
    payload = os.urandom(3 * 1024 * 1024)   # larger than the read chunk
    blob.write_bytes(payload)
    assert oracle.content_hash(str(blob)) == hashlib.sha256(payload).hexdigest()


@windows_only
def test_an_alternate_data_stream_is_refused_not_normalised(oracle, tmp_path):
    """`a.exe:x` is a different byte stream from `a.exe`, and nothing downstream tells them
    apart, so canonicalisation refuses rather than dropping the suffix."""
    assert oracle.canonicalize(str(tmp_path / "a.exe") + ":stream") is None


@windows_only
def test_a_junction_resolves_and_a_plain_directory_does_not(oracle, tmp_path):
    from agentao.permissions_hardline._trust import ReparseState

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(real)],
                   capture_output=True, timeout=60, check=True)

    assert oracle.resolve_reparse(str(real)).state is ReparseState.not_reparse
    resolved = oracle.resolve_reparse(str(link))
    assert resolved.state is ReparseState.resolved
    assert os.path.normcase(resolved.target or "") == os.path.normcase(str(real))


@windows_only
def test_an_absent_path_is_an_error_state_not_not_a_reparse_point(oracle, tmp_path):
    from agentao.permissions_hardline._trust import ReparseState

    assert oracle.resolve_reparse(str(tmp_path / "gone")).state is ReparseState.error


# ------------------------------------------------- the target's shape and images


def test_every_oracle_method_is_answered():
    """SPEC-05c refuses an incomplete oracle, so the count is worth asserting rather than
    describing: it is what stops "partial" being reported as "done" in either direction."""
    from agentao.permissions_hardline._trust import ORACLE_METHODS, oracle_complete

    missing = {m for m in ORACLE_METHODS if not hasattr(WindowsAccessOracle, m)}
    assert missing == set()
    # Asked of the class rather than an instance: `oracle_complete` looks for callable
    # attributes and a class answers the same way, while building an instance needs a real
    # Windows token — so this runs on every platform the suite does, not just the one job.
    assert oracle_complete(WindowsAccessOracle) is True   # type: ignore[arg-type]


@windows_only
def test_path_entries_are_canonical_deduplicated_and_ordered(oracle, subject, tmp_path,
                                                             monkeypatch):
    r"""ENV-01's raw material. ``..`` and a repeat must collapse, because `path_within` is
    documented to take already-canonical paths while a PATH entry is a raw string."""
    real = tmp_path / "bin"
    real.mkdir()
    detour = str(tmp_path / "bin" / ".." / "bin")
    monkeypatch.setenv("PATH", os.pathsep.join([str(real), detour, str(real)]))

    entries = oracle.target_path_entries(subject)
    assert entries is not None
    assert [e for e in entries if "bin" in e] == [os.path.realpath(str(real))]


@windows_only
def test_path_entries_are_refused_for_another_subject(oracle):
    assert oracle.target_path_entries(Subject("S-1-5-21-0-0-0-9")) is None


@windows_only
def test_the_pinned_env_reports_a_path_key_it_does_not_register(oracle, subject, monkeypatch):
    """ENV-06b: an unregistered key is surfaced, not dropped. Dropping it would report a
    validated environment when one key was never looked at."""
    monkeypatch.setenv("CARGO_HOME", "C:\\cargo")
    pinned = oracle.target_pinned_env(subject)
    assert pinned is not None
    assert any(k.upper() == "CARGO_HOME" for k in pinned.unknown_keys)


@windows_only
def test_the_pinned_env_does_not_report_registered_keys_as_unknown(oracle, subject):
    pinned = oracle.target_pinned_env(subject)
    assert pinned is not None
    registered = {k.upper() for k in WindowsAccessOracle._PINNED_KEYS}
    assert not {k.upper() for k in pinned.unknown_keys} & registered


@windows_only
def test_a_windows_pinned_env_has_no_tmpdir_field(oracle, subject):
    """ENV-06f: TMPDIR is the POSIX target's field, and a value there fails the shape check."""
    pinned = oracle.target_pinned_env(subject)
    assert pinned is not None and pinned.tmpdir is None


@windows_only
def test_resolve_image_reports_a_filesystem_identity_not_just_a_path(oracle, subject, tmp_path):
    image = tmp_path / "img.exe"
    image.write_bytes(b"MZ")

    resolved = oracle.resolve_image(str(image), subject)
    assert resolved is not None
    assert resolved.filesystem_identity
    assert resolved.execution_subject == subject
    assert os.path.normcase(resolved.canonical_path) == os.path.normcase(str(image))


@windows_only
def test_resolve_image_refuses_a_directory_and_an_absent_path(oracle, subject, tmp_path):
    assert oracle.resolve_image(str(tmp_path), subject) is None
    assert oracle.resolve_image(str(tmp_path / "gone.exe"), subject) is None


@windows_only
def test_discover_finds_the_interpreters_this_runner_has(oracle, subject):
    from agentao.capabilities.shell_spec import Rung

    found = {rung: oracle.discover(rung, subject) for rung in
             (Rung.pwsh, Rung.powershell, Rung.cmd, Rung.git_bash)}
    # cmd and Windows PowerShell ship with the OS; pwsh and Git are runner-dependent, so a
    # missing one is a fact about the image rather than a failure.
    assert found[Rung.cmd] is not None
    assert found[Rung.powershell] is not None
    for rung, image in found.items():
        if image is not None:
            assert os.path.isfile(image.canonical_path), rung


@windows_only
def test_discover_does_not_consult_path(oracle, subject, tmp_path, monkeypatch):
    r"""IMG-05 (a): a PATH hit is not a candidate. PATH is the thing an attacker shapes, and
    ENV-01 exists to filter it — resolving through it would answer before any filtering."""
    from agentao.capabilities.shell_spec import Rung

    planted = tmp_path / "pwsh.exe"
    planted.write_bytes(b"MZ")
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "nothing-here"))
    monkeypatch.setenv("ProgramW6432", str(tmp_path / "nothing-here"))

    assert oracle.discover(Rung.pwsh, subject) is None


# ------------------------------------------------- signing and the interpreter


@windows_only
def test_an_unsigned_file_has_no_signer_and_no_trusted_publisher(oracle, tmp_path):
    """Both routes must refuse a file nobody signed, and refuse it the same way."""
    blob = tmp_path / "unsigned.exe"
    blob.write_bytes(b"MZ" + b"\x00" * 1024)

    assert oracle.publisher_trusted(str(blob)) is False
    assert oracle.image_signer(str(blob)) is None


@windows_only
def test_a_catalog_signed_system_binary_verifies_and_reports_a_signer(oracle):
    r"""``cmd.exe`` carries no embedded PKCS#7 — its signature lives in a ``.cat``.

    This is the case that caught an embedded-only check: it reported the ladder's own
    interpreters as unsigned, which would have made the trust-store route decorative for
    exactly the files it exists to admit.
    """
    cmd = r"C:\Windows\System32\cmd.exe"
    assert oracle.publisher_trusted(cmd) is True, "a catalog signature must verify"
    signer = oracle.image_signer(cmd)
    assert signer, "the signer name is how an allowlist PublisherTrust entry is matched"
    assert "Microsoft" in signer


@windows_only
def test_the_catalog_lookup_finds_a_catalog_for_a_system_binary(oracle):
    """The half that would otherwise fail silently: "no catalog found" and "not signed"
    reach the caller as the same answer, and only one of them is a fact about the file."""
    found = oracle._catalog_for(r"C:\Windows\System32\cmd.exe")
    assert found is not None
    catalog, tag = found
    assert catalog.lower().endswith(".cat")
    assert len(tag) >= 40 and all(c in "0123456789ABCDEF" for c in tag)


@windows_only
def test_a_signer_is_only_read_after_the_chain_verifies(oracle, tmp_path, monkeypatch):
    """A name lifted from an unverified signature is an attacker-supplied string, and an
    allowlist matching it would be trusting the file it was asked to check."""
    monkeypatch.setattr(oracle, "_verify_trust", lambda path: 1)
    monkeypatch.setattr(oracle, "_signer_name",
                        lambda path: pytest.fail("read the name without verifying"))

    assert oracle.image_signer(r"C:\Windows\System32\cmd.exe") is None


@windows_only
def test_read_identity_returns_the_same_image_object(oracle, subject):
    """`select_rung` checks `identity.image is not img`, so an equal-but-rebuilt record
    would fail an identity test for no reason."""
    from agentao.capabilities.shell_spec import Rung, ShellDialect

    img = oracle.discover(Rung.cmd, subject)
    assert img is not None
    identity = oracle.read_identity(img, ShellDialect.CMD)
    assert identity is not None
    assert identity.image is img
    assert identity.launcher_hash == oracle.content_hash(img.canonical_path)


@windows_only
def test_read_identity_reads_the_four_powershell_facts(oracle, subject):
    from agentao.capabilities.shell_spec import InterpreterIdentity, Rung, ShellDialect

    img = oracle.discover(Rung.powershell, subject)
    assert img is not None
    identity = oracle.read_identity(img, ShellDialect.POWERSHELL)
    assert isinstance(identity, InterpreterIdentity)
    assert identity.edition in {"Desktop", "Core"}
    assert identity.version.count(".") >= 2
    assert os.path.isdir(identity.pshome)


@windows_only
def test_pshome_is_the_assembly_root_not_the_launchers_directory(oracle, subject):
    r"""§3.20: ``$PSHOME`` is the directory of the executing automation assembly. For Windows
    PowerShell those coincide; the assertion that matters is that it is read *from the
    interpreter* rather than derived from the launcher's path."""
    from agentao.capabilities.shell_spec import Rung

    img = oracle.discover(Rung.powershell, subject)
    assert img is not None
    pshome = oracle.resolve_pshome(img)
    assert pshome and os.path.isdir(pshome)
    assert os.path.isfile(os.path.join(pshome, "powershell.exe"))


@windows_only
def test_an_unreadable_config_source_reports_a_configuration_not_none(oracle, subject,
                                                                     tmp_path):
    """IMG-06c's discipline applied to IMG-08: an unexamined source must not be recorded as
    examined and empty. Reporting a configuration refuses the rung, which is the safe side."""
    (tmp_path / "powershell.config.json").write_text("{ not json", encoding="utf-8")

    assert oracle.read_config_sources(str(tmp_path), subject).session is not None


@windows_only
def test_a_config_naming_a_session_is_reported(oracle, subject, tmp_path):
    import json as _json

    (tmp_path / "powershell.config.json").write_text(
        _json.dumps({"ConsoleSessionConfigurationName": "Restricted"}), encoding="utf-8")

    assert oracle.read_config_sources(str(tmp_path), subject).session == "Restricted"


@windows_only
def test_config_sources_are_refused_for_another_subject(oracle, tmp_path):
    assert oracle.read_config_sources(
        str(tmp_path), Subject("S-1-5-21-0-0-0-9")).session is not None


@windows_only
def test_preflight_runs_the_prelude_and_reports_its_exit(oracle, subject):
    from agentao.capabilities.shell_spec import Rung, ShellDialect

    img = oracle.discover(Rung.powershell, subject)
    assert img is not None
    identity = oracle.read_identity(img, ShellDialect.POWERSHELL)
    assert identity is not None

    assert oracle.preflight(identity, "exit 0") is True
    assert oracle.preflight(identity, "exit 97") is False


def test_the_module_imports_on_every_platform():
    """It is reached from `permissions_hardline`, which POSIX hosts import; binding Win32 at
    call time rather than import time is what keeps that true."""
    assert sys.modules["agentao.permissions_hardline._windows_identity"]
