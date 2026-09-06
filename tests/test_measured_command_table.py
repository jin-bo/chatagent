r"""NAME-02's measured command tables — the properties the rule resolves against.

The tables are data produced by ``scripts/windows_command_table_probe.py`` and never hand
edited. These tests do not re-measure anything; they assert the structure NAME-02 depends on,
so a regenerated table that lost a property fails here rather than in a shell call.

Everything here runs on every platform: the *measurement* needs Windows, the *shape* does not.
"""

from __future__ import annotations

import pytest

from agentao.capabilities.shell_spec import ResolvedImage, Subject
from agentao.permissions_hardline._measured_commands import MEASURED
from agentao.permissions_hardline._trust import (
    MEASURED_COMMAND_TABLES,
    InterpreterIdentity,
    LauncherIdentity,
    identity_measured,
    measured_table,
)

_KINDS = {"alias", "function", "cmdlet"}


def _identity(edition: str, version: str) -> InterpreterIdentity:
    image = ResolvedImage(
        canonical_path="C:\\i.exe",           # type: ignore[arg-type]
        filesystem_identity="dev:1",           # type: ignore[arg-type]
        execution_subject=Subject("s"),
    )
    return InterpreterIdentity(
        image=image, launcher_hash="h",        # type: ignore[arg-type]
        edition=edition, version=version,
        pshome="C:\\PSHOME",                   # type: ignore[arg-type]
    )


def test_both_measured_editions_are_present():
    """A Desktop and a Core table, because one shared across editions either trusts a name
    that is not there or misses one that is."""
    editions = {edition for edition, _ in MEASURED}
    assert editions == {"Desktop", "Core"}


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_every_row_has_a_kind_name_02_resolves(key):
    for name, kind, _target in MEASURED[key]:
        assert kind in _KINDS, f"{name}: {kind}"
        assert name, "a nameless row cannot be resolved against"


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_only_aliases_carry_a_target(key):
    """The target is what NAME-02 follows for an alias; on anything else it would be noise
    that a reader would eventually start trusting."""
    for name, kind, target in MEASURED[key]:
        if kind == "alias":
            assert target, f"{name} is an alias with no target"
        else:
            assert target == "", f"{name} is a {kind} carrying a target"


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_a_name_appears_at_most_once_per_kind(key):
    """Shadowing is *across* kinds — a function hiding a cmdlet is the case NAME-02 is written
    for — so a repeat within one kind is a broken measurement rather than a real ambiguity."""
    seen = set()
    for name, kind, _ in MEASURED[key]:
        assert (name.lower(), kind) not in seen, f"{name} listed twice as {kind}"
        seen.add((name.lower(), kind))


#: Measured, not chosen. Desktop defines these aliases while their targets are *not*
#: resolvable in the pinned startup state — four WMI cmdlets that PowerShell 5.1 no longer
#: exposes there, and one alias onto an external program. An alias exists in the session
#: whether or not its target does, which is precisely the case NAME-02 handles by resolving
#: the alias and then taking the *target's* entry: with no entry, the word falls through to
#: the external-program search on the target name and is opaque unless that finds an image.
_DANGLING = {
    ("Desktop", "5.1.26100.33296"): {"gwmi", "ise", "iwmi", "rwmi", "swmi"},
    ("Core", "7.6.5"): set(),
}


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_the_aliases_whose_targets_are_not_in_the_table_are_the_measured_ones(key):
    """Pinned because a change here is a change in what the interpreter offers.

    `_powershell_name` sends these down `_external(target, ...)`, so `ise` is answered by
    `powershell_ise.exe`'s image rather than by the alias's name — a trusted alias must not
    launder its target — and `gwmi` is opaque because no such program exists.
    """
    names = {name.lower() for name, _, _ in MEASURED[key]}
    dangling = {
        name for name, kind, target in MEASURED[key]
        if kind == "alias" and target.lower() not in names
    }
    assert dangling == _DANGLING[key]


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_nothing_shadows_anything_in_the_pinned_startup_state(key):
    """A measured fact, and a slightly surprising one.

    NAME-02 spends a clause on alias before function before cmdlet, and in the pinned startup
    state no name is carried by more than one kind — profiles are off, auto-loading is off,
    and only three modules are imported, so there is nothing left to shadow with. The clause
    is still needed and is exercised against synthetic tables in
    ``tests/test_trusted_resolution.py``; what this pins is that the *shipped* data does not
    exercise it, so nobody reads a green run here as evidence that it works.
    """
    by_name: dict = {}
    for name, kind, _ in MEASURED[key]:
        by_name.setdefault(name.lower(), set()).add(kind)
    assert [n for n, kinds in by_name.items() if len(kinds) > 1] == []


def test_the_runtime_table_matches_the_data_file():
    assert set(MEASURED_COMMAND_TABLES) == set(MEASURED)
    for key, rows in MEASURED.items():
        built = MEASURED_COMMAND_TABLES[key]
        assert len(built) == len(rows)
        assert built[0].name == rows[0][0]
        assert built[0].kind == rows[0][1]


def test_an_alias_targets_none_rather_than_empty_string():
    """`MeasuredEntry.alias_target` is Optional, and "" is not None: a consumer testing
    truthiness and one testing `is None` would disagree about a non-alias row."""
    for rows in MEASURED_COMMAND_TABLES.values():
        for row in rows:
            if row.kind != "alias":
                assert row.alias_target is None


@pytest.mark.parametrize("key", sorted(MEASURED))
def test_identity_measured_is_true_for_a_measured_build(key):
    edition, version = key
    assert identity_measured(_identity(edition, version)) is True
    assert len(measured_table(_identity(edition, version))) == len(MEASURED[key])


def test_an_unmeasured_build_degrades_rather_than_breaks():
    """The failure mode this file is allowed to have: no table means every bare word is
    opaque and the rung still serves explicit paths, not that anything raises."""
    unknown = _identity("Core", "9.9.9-not-measured")
    assert identity_measured(unknown) is False
    assert measured_table(unknown) == ()


def test_a_launcher_without_an_interpreter_identity_has_no_table():
    """A cmd or Git Bash launcher reaches these helpers too, and neither has an edition."""
    image = ResolvedImage(
        canonical_path="C:\\cmd.exe",          # type: ignore[arg-type]
        filesystem_identity="dev:2",           # type: ignore[arg-type]
        execution_subject=Subject("s"),
    )
    plain = LauncherIdentity(image=image, launcher_hash="h")  # type: ignore[arg-type]
    assert identity_measured(plain) is False
    assert measured_table(plain) == ()


def test_the_names_powershell_really_ships_survived_generation():
    r"""``cd\`` broke the first generator, which quoted by wrapping rather than serialising.
    These are real function names and a table missing them is a table that was mangled."""
    desktop = {name for name, _, _ in MEASURED[("Desktop", "5.1.26100.33296")]}
    assert {"cd\\", "cd..", "C:"} <= desktop
