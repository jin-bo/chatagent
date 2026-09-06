r"""Measure NAME-02's command table in the pinned startup state.

NAME-02 resolves a PowerShell bare word against "every alias, function and cmdlet measured
with ``Get-Command -All`` **in the pinned startup state**", and until that table exists for
an interpreter identity every bare word is opaque and the rung serves explicit paths only.
This is the measurement that fills it, and it is the last thing standing between the ladder
and useful PowerShell rungs.

**The state is built by the product, not restated here.** The prelude comes from
``prelude_for`` — the same string a launch would run — so the table cannot be measured in
one state and used in another. That matters more than it sounds: measuring with module
auto-loading *on* would record names the child then fails to find, and the whole reason
LAUNCH-05 has four clauses is that turning auto-loading off leaves nothing outside
``Microsoft.PowerShell.Core`` resolvable until two modules are explicitly imported
(evidence §3.20a).

Every row is verified resolvable in that same state, as NAME-02 requires, by asking the
interpreter rather than by assuming the enumeration implies it.

Output is one JSON document: the identity it was measured for, and the rows. Nothing is
interpreted here; the reading happens in review, and the table is checked in keyed by the
exact ``(edition, version)`` it was measured on. Any other identity keeps failing closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform != "win32":  # pragma: no cover - the state only exists there
    raise SystemExit("the pinned startup state is a Windows state; run this on the runner")

from agentao.capabilities.shell_spec import Rung, ShellDialect  # noqa: E402
from agentao.permissions_hardline._trust import (  # noqa: E402
    _parent_dir,
    encode_workdir,
    prelude_for,
)
from agentao.permissions_hardline._windows_identity import native_oracle  # noqa: E402

# One statement per line of output, tab-separated, so nothing has to be parsed out of
# PowerShell's display formatting. `Get-Command -All` is NAME-02's own spelling.
_ENUMERATE = (
    "$ErrorActionPreference='Stop'; "
    "Get-Command -All | Where-Object { $_.CommandType -in 'Alias','Function','Cmdlet' } | "
    "ForEach-Object { "
    "$t = if ($_.CommandType -eq 'Alias') { $_.Definition } else { '' }; "
    "Write-Output ($_.Name + \"`t\" + $_.CommandType + \"`t\" + $t) }"
)

# NAME-02: "every row verified resolvable in that state". Asked of the interpreter, because
# an enumeration proving resolvability is an assumption, not a measurement.
# `<NAMES>` rather than a `str.format` field: this script is full of PowerShell braces, and
# `.format` reads every one of them as a replacement field.
_VERIFY = (
    "$ErrorActionPreference='Stop'; "
    "$names = @(<NAMES>); "
    "$missing = @($names | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) }); "
    "Write-Output ('MISSING=' + $missing.Count); "
    "$missing | ForEach-Object { Write-Output ('MISS ' + $_) }"
)


def _run(interpreter: str, script: str):
    from agentao.capabilities.process import run_captured

    return run_captured(
        [interpreter, "-NoProfile", "-NonInteractive", "-Command", script], timeout=180,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="write the JSON here instead of stdout")
    parser.add_argument("--rung", default="powershell", choices=["powershell", "pwsh"])
    args = parser.parse_args()

    oracle = native_oracle()
    if oracle is None:
        raise SystemExit("no native oracle on this machine")
    subject = oracle._subject
    rung = Rung.powershell if args.rung == "powershell" else Rung.pwsh

    image = oracle.discover(rung, subject)
    if image is None:
        raise SystemExit(f"no interpreter discovered for {rung.value}")
    identity = oracle.read_identity(image, ShellDialect.POWERSHELL)
    if identity is None:
        raise SystemExit("the interpreter's identity could not be read")

    home = _parent_dir(identity.path, oracle.target_platform())
    literal = encode_workdir(home, ShellDialect.POWERSHELL) if home is not None else None
    prelude = prelude_for(identity, literal) if literal is not None else None
    if prelude is None:
        raise SystemExit("the prelude could not be built for this identity")

    listing = _run(str(identity.path), f"{prelude}; {_ENUMERATE}")
    rows = []
    for line in (listing.stdout or "").splitlines():
        parts = line.rstrip("\r").split("\t")
        if len(parts) != 3 or not parts[0]:
            continue
        name, kind, target = parts
        rows.append({
            "name": name,
            "kind": kind.strip().lower(),
            "alias_target": target.strip() or None,
        })

    quoted = ",".join("'" + r["name"].replace("'", "''") + "'" for r in rows)
    verify = _run(str(identity.path), f"{prelude}; " + _VERIFY.replace("<NAMES>", quoted))
    missing = [
        line.split(" ", 1)[1].strip()
        for line in (verify.stdout or "").splitlines()
        if line.startswith("MISS ")
    ]

    report = {
        "probe_version": 1,
        "rung": rung.value,
        "identity": {
            "edition": identity.edition,
            "version": identity.version,
            "pshome": str(identity.pshome),
            "path": str(identity.path),
        },
        "prelude": prelude,
        "enumerate_returncode": listing.returncode,
        "verify_returncode": verify.returncode,
        "row_count": len(rows),
        # NAME-02 requires every row resolvable in the measured state. A non-empty list here
        # means the table must not be checked in as measured: it would admit a bare word the
        # child then fails to find.
        "unresolvable": missing,
        "rows": sorted(rows, key=lambda r: (r["kind"], r["name"].lower())),
    }
    if listing.returncode != 0:
        report["enumerate_stderr"] = (listing.stderr or "")[:4000]
    if verify.returncode != 0:
        report["verify_stderr"] = (verify.stderr or "")[:4000]

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as handle:
            handle.write(text + "\n")
        print(f"wrote {args.out}: {len(rows)} rows, {len(missing)} unresolvable")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
