"""G09-03: the instrument LADDER-04's replacement gate collects.

The gate cannot collect a percentage, because the number it wants — how much ordinary Windows
work becomes a prompt after the flip — is a fact about usage and only exists after shipping.
What it collects instead is a way to read that number off refusals the runtime already emits.

These tests are written against what the floor **emits**, not against the reason literals in
the source. The two are not the same population: ``opaque()`` renders ``{detail or rule}``, so
a rule ID written at the call site does not necessarily appear in the string that comes out.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import dataclasses

from agentao.capabilities.shell_spec import (
    LauncherIdentity,
    PinnedEnv,
    Platform,
    ResolvedImage,
    Rung,
    Sha256,
    ShellDialect,
    Subject,
    legacy_spec,
)
from agentao.permissions_hardline import hardline_check
from agentao.permissions_hardline._refusals import (
    Refusal,
    RefusalFamily,
    classify_refusal,
    tally,
)

SUBJ = Subject("subject")

# Bodies chosen to reach different families, not to be representative — a representative
# corpus is the thing that does not exist yet, and pretending otherwise is what the gate was
# replaced for.
POSIX_BODIES = [
    "rm -rf /",                      # dangerous, POSIX table
    "mkfs.ext4 /dev/sda1",           # dangerous, POSIX table
    "echo $(rm -rf /)",              # floor, BASH-01
    "git status",                    # passes
]
CMD_BODIES = [
    "format C:",                     # dangerous, Windows table
    "vssadmin delete shadows /all",  # dangerous, Windows table
    "call foo.bat",                  # floor, CMD-01
    "start x.exe",                   # floor, WRAP-05
    "echo %PATH%",                   # floor, TOK-02
    "dir /b",                        # passes
]


def policy_on_cmd_spec():
    """A policy-enabled `cmd` rung. LADDER-05 keeps the new floor off the pre-flip rungs, so a
    corpus run against `legacy_cmd` reaches the danger tables and nothing else — which is how
    the first version of this file passed its coverage assertion while covering one family."""
    base = legacy_spec(ShellDialect.CMD, Rung.legacy_cmd, Platform.WINDOWS, SUBJ)
    launcher = LauncherIdentity(
        image=ResolvedImage(
            canonical_path="C:\\Windows\\System32\\cmd.exe",  # type: ignore[arg-type]
            filesystem_identity="1:2",  # type: ignore[arg-type]
            execution_subject=SUBJ,
        ),
        launcher_hash=Sha256("h"),
    )
    return dataclasses.replace(
        base, rung=Rung.cmd, policy_enabled=True, launcher=launcher, pinned_env=PinnedEnv()
    )


def _reasons(bodies, spec):
    out = []
    for body in bodies:
        reason = hardline_check("run_shell_command", {"command": body}, shell_spec=spec)
        if reason is not None:
            out.append(reason)
    return out


def emitted_reasons():
    posix = legacy_spec(ShellDialect.POSIX, Rung.system_posix, Platform.POSIX, SUBJ)
    return _reasons(POSIX_BODIES, posix) + _reasons(CMD_BODIES, policy_on_cmd_spec())


# ------------------------------------------------------------------ coverage


def test_every_reason_the_floor_emits_has_a_family():
    """The instrument has to cover the population it quantifies over.

    An unclassified reason does not vanish — it lands in ``unknown`` under its own key — but a
    distribution whose largest bucket is "unknown" answers nothing, so this is the assertion
    that keeps the instrument honest as the reason vocabulary grows.
    """
    emitted = emitted_reasons()
    assert emitted, "the corpus refused nothing, so this test would pass vacuously"
    unknown = [r for r in emitted if classify_refusal(r).family is RefusalFamily.unknown]
    assert unknown == [], unknown


def test_every_reason_literal_in_the_package_has_a_family():
    """The other half of the population: paths the corpus above does not reach.

    Scanning the source finds reasons no test drives — the launch-attestation family in
    particular, which needs a real spawn. Both halves are needed: the corpus covers what is
    emitted, this covers what is written.
    """
    from agentao.permissions_hardline._patterns import _HARDLINE_PATTERNS
    from agentao.permissions_hardline._windows import WINDOWS_DANGEROUS

    literals = {"hardline:" + desc for _, desc in _HARDLINE_PATTERNS}
    literals |= {reason for _, reason in WINDOWS_DANGEROUS}
    for path in sorted(pathlib.Path("agentao").rglob("*.py")):
        if path.name == "_refusals.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.startswith("hardline:") and len(node.value) > len("hardline:"):
                    literals.add(node.value)

    unknown = sorted(x for x in literals
                     if classify_refusal(x).family is RefusalFamily.unknown)
    assert unknown == [], unknown
    assert len(literals) > 50, len(literals)  # the scan actually found the vocabulary


# ------------------------------------------------------------------ the families


@pytest.mark.parametrize(
    "reason,family",
    [
        ("hardline:cmd-opaque:CMD-01:call", RefusalFamily.floor),
        ("hardline:cmd-opaque:executes_input", RefusalFamily.floor),
        ("hardline:format-volume", RefusalFamily.dangerous),
        ("hardline:recursive delete of root / system directory / home", RefusalFamily.dangerous),
        ("hardline:launch-attest:content-identity:C:\\x.exe", RefusalFamily.launch),
        ("hardline:no-trusted-rung-opaque:every rung refused", RefusalFamily.no_rung),
        ("hardline:unknown-rung-opaque", RefusalFamily.spec),
        ("permission-rule:deny", RefusalFamily.unknown),
        ("", RefusalFamily.unknown),
    ],
)
def test_each_family_is_recognised(reason, family):
    assert classify_refusal(reason).family is family


def test_a_free_form_danger_description_is_not_parsed_as_structure():
    """23 of the shipped reasons are English sentences, and colons in them mean nothing.

    The gate row used to say every reason looked like
    ``hardline:<dialect>-opaque:<rule>[:<detail>]``. That is one family of six. Recognising the
    danger families by *membership in the tables* rather than by shape is what keeps a reworded
    description from silently moving to another bucket.
    """
    reason = "hardline:recursive delete of root / system directory / home"
    parsed = classify_refusal(reason)
    assert parsed.family is RefusalFamily.dangerous
    assert parsed.rule is None and parsed.dialect is None
    assert parsed.detail == "recursive delete of root / system directory / home"


def test_a_reason_from_another_gate_stays_visible_rather_than_folded():
    """Permission rules, hooks and host callbacks all produce reasons this floor did not.

    Folding them into a neighbouring bucket is how the measurement would start lying while
    still rendering. They keep their own key instead.
    """
    parsed = classify_refusal("hook:PreToolUse:deny")
    assert parsed.family is RefusalFamily.unknown
    assert parsed.bucket == "unknown:hook:PreToolUse:deny"


# ------------------------------------------------------------------ the bucket


def test_the_bucket_does_not_collapse_refusals_that_differ():
    """``opaque()`` renders ``{detail or rule}``, so a detail *replaces* the rule ID.

    Keying those on the missing rule would put ``executes_input``, ``name`` and ``image`` in
    one bucket — a histogram that renders cleanly and says nothing.
    """
    buckets = {classify_refusal(r).bucket for r in (
        "hardline:cmd-opaque:executes_input",
        "hardline:cmd-opaque:name",
        "hardline:cmd-opaque:image",
    )}
    assert len(buckets) == 3, buckets


def test_the_bucket_is_coarser_than_the_raw_reason():
    """A detail carries paths and command words, so counting raw strings gives one row a call."""
    a = classify_refusal("hardline:cmd-opaque:CMD-01:call")
    b = classify_refusal("hardline:cmd-opaque:CMD-01:goto")
    assert a.raw != b.raw and a.bucket == b.bucket == "floor:cmd:CMD-01"


# ------------------------------------------------------------------ the tally


def test_the_tally_is_ordered_so_two_runs_can_be_diffed():
    counts = tally([
        "hardline:cmd-opaque:CMD-01:call",
        "hardline:cmd-opaque:CMD-01:goto",
        "hardline:format-volume",
        "hardline:cmd-opaque:executes_input",
    ])
    assert list(counts.items()) == [
        ("floor:cmd:CMD-01", 2),
        ("dangerous:format-volume", 1),
        ("floor:cmd:executes_input", 1),
    ]


def test_the_tally_over_the_emitted_corpus_reads_as_a_distribution():
    """The end the gate actually asks for: refusals in, a readable distribution out."""
    counts = tally(emitted_reasons())
    assert counts and all(isinstance(v, int) and v > 0 for v in counts.values())
    assert not any(k.startswith("unknown:") for k in counts), counts
    assert any(k.startswith("dangerous:") for k in counts), counts
    assert any(k.startswith("floor:") for k in counts), counts


def test_a_refusal_record_is_frozen():
    """It travels to a host; a mutable one would let a reader edit the measurement."""
    parsed = classify_refusal("hardline:format-volume")
    with pytest.raises(Exception):
        parsed.family = RefusalFamily.floor  # type: ignore[misc]
    assert isinstance(parsed, Refusal)
