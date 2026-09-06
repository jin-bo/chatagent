"""G09-03: turn a refusal reason into something a distribution can be taken over.

LADDER-04's replacement gate collects an *instrument*, not a percentage. The number it wants
— how much ordinary Windows work becomes a prompt after the flip — is a fact about usage, so
it can only exist after shipping. What can exist beforehand is a way to read it off refusals
the runtime already emits, and that is this module.

**The reason space is six families, not one.** The gate row used to say every reason looked
like ``hardline:<dialect>-opaque:<rule>[:<detail>]``; that is one family of six, and 23 of the
shipped reasons are free-form English from the POSIX danger table
(``hardline:recursive delete of root / system directory / home``), where colons and spaces
carry no structure at all. A classifier built on the assumed shape would have bucketed most
refusals by accident, which is exactly the failure a distribution cannot survive: a number
that is wrong in a way nothing reports.

So the two danger families are recognised by **membership in the tables themselves** rather
than by pattern. Adding an entry to a table cannot create an unknown, and rewording one cannot
silently move it to another bucket.

An unrecognised reason is ``unknown`` and stays visible under its own key. Folding it into a
neighbouring bucket is how the measurement would start lying, and the point of building this
before the flip is that it can be wrong loudly instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, Iterable, Optional

from ._patterns import REASON_HARDLINE

__all__ = ["RefusalFamily", "Refusal", "classify_refusal", "tally"]

_PREFIX = f"{REASON_HARDLINE}:"

# The design's own rule-ID shape (`FAM-NN`, optional sub-rule letter). Anything else in that
# position is a detail, not a rule — guessing would invent rule IDs that no gate can point at.
_RULE = re.compile(r"^[A-Z]{2,6}-\d{2}[a-z]?$")


def _danger_reasons() -> FrozenSet[str]:
    """Every reason the two irrecoverable-loss tables can emit, from the tables.

    Read lazily and cached: ``_windows`` is a data module, but importing it at module scope
    would put a second edge into a package whose import direction is guarded (PR #175).
    """
    global _DANGER
    if _DANGER is None:
        from ._patterns import _HARDLINE_PATTERNS
        from ._windows import WINDOWS_DANGEROUS

        out = {desc for _, desc in _HARDLINE_PATTERNS}
        out |= {reason[len(_PREFIX):] for _, reason in WINDOWS_DANGEROUS
                if reason.startswith(_PREFIX)}
        _DANGER = frozenset(out)
    return _DANGER


_DANGER: Optional[FrozenSet[str]] = None


class RefusalFamily(Enum):
    """Why the call was refused, at the coarsest level a distribution is worth reading at."""

    floor = "floor"          # a dialect's own gate or the closed set; carries a rule ID
    dangerous = "dangerous"  # the irrecoverable-loss tables, POSIX and Windows
    launch = "launch"        # LAUNCH-01's re-check between the decision and the spawn
    no_rung = "no-rung"      # LADDER-03: every rung refused, so the ladder ran empty
    spec = "spec"            # SPEC-01 / SPEC-02: the spec itself could not be used
    unknown = "unknown"      # not this floor's, or a shape this classifier does not know


@dataclass(frozen=True)
class Refusal:
    """One refusal, parsed as far as its family actually permits and no further."""

    family: RefusalFamily
    raw: str
    dialect: Optional[str] = None
    rule: Optional[str] = None
    detail: Optional[str] = None

    @property
    def bucket(self) -> str:
        """The aggregation key — deliberately coarser than ``raw``.

        Details carry paths, command words and quoted text, so counting ``raw`` would produce
        a histogram with one entry per call. The bucket keeps what a reader can act on: which
        family, which dialect, which rule.
        """
        if self.family is RefusalFamily.floor:
            # The rule ID is not always recoverable. ``opaque()`` renders
            # ``{detail or rule}``, so a refusal that carries a detail has *no* rule in its
            # reason at all — keying those on ``"?"`` would collapse ``executes_input``,
            # ``name`` and ``image`` into one bucket, which is the histogram quietly lying.
            return ":".join(x for x in ("floor", self.dialect, self.rule or self.detail) if x)
        if self.family is RefusalFamily.dangerous:
            return f"dangerous:{self.detail}"
        if self.family is RefusalFamily.launch:
            return f"launch:{self.detail or '?'}"
        if self.family is RefusalFamily.unknown:
            return f"unknown:{self.raw}"
        return self.family.value


def classify_refusal(reason: str) -> Refusal:
    """Parse one refusal reason. Never raises, and never guesses a family.

    A reason that does not start with the source tag belongs to some other gate — a permission
    rule, a hook, a host callback — and is reported as ``unknown`` rather than being forced
    into a bucket it was never emitted for.
    """
    if not isinstance(reason, str) or not reason.startswith(_PREFIX):
        return Refusal(RefusalFamily.unknown, raw=reason if isinstance(reason, str) else "")
    body = reason[len(_PREFIX):]

    if body in _danger_reasons():
        return Refusal(RefusalFamily.dangerous, raw=reason, detail=body)

    head, _, rest = body.partition(":")
    if head == "launch-attest":
        kind, _, extra = rest.partition(":")
        return Refusal(RefusalFamily.launch, raw=reason, detail=kind or None,
                       rule="LAUNCH-01" if kind else None)
    if head == "no-trusted-rung-opaque":
        return Refusal(RefusalFamily.no_rung, raw=reason, rule="LADDER-03",
                       detail=rest or None)
    if head in ("unknown-dialect-opaque", "unknown-rung-opaque"):
        return Refusal(RefusalFamily.spec, raw=reason,
                       rule="SPEC-01" if head.startswith("unknown-dialect") else "SPEC-02")
    if head.endswith("-opaque"):
        dialect = head[: -len("-opaque")] or None
        first, _, extra = rest.partition(":")
        if _RULE.match(first):
            return Refusal(RefusalFamily.floor, raw=reason, dialect=dialect,
                           rule=first, detail=extra or None)
        return Refusal(RefusalFamily.floor, raw=reason, dialect=dialect,
                       detail=rest or None)
    return Refusal(RefusalFamily.unknown, raw=reason)


def tally(reasons: Iterable[str]) -> Dict[str, int]:
    """The distribution G09-03 exists to make readable, keyed by :attr:`Refusal.bucket`.

    Ordered by descending count then by key, so two runs over the same data render the same
    way and a reader can diff them.
    """
    counts: Dict[str, int] = {}
    for reason in reasons:
        key = classify_refusal(reason).bucket
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
