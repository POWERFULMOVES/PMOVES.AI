"""Guard the recursive-make ARGS leak.

The defect
----------
`make -C pmoves chit-manifest-register ARGS='--check'` — the invocation the
target's OWN help text documents — failed before reaching the tool:

    bootstrap_light_env.py: error: unrecognized arguments: --check
    make[1]: *** [mk/preflight.mk:39: env-bootstrap-lite] Error 2

GNU Make propagates command-line variable assignments to sub-makes through
MAKEFLAGS, and a command-line override outranks any assignment inside the
child's own makefile. So `ARGS='--check'`, meant for chit_manifest_register.py,
also arrived at `env-bootstrap-lite`, whose recipe passes `$(ARGS)` to
bootstrap_light_env.py — a script with a completely different flag set.

The only thing that outranks an inherited command-line override is another
command-line assignment, so the fix is a literal `ARGS=` on the recursive
`$(MAKE)` line itself. Setting `ARGS =` inside preflight.mk would NOT work.

Seven targets were affected: chit-manifest-register, chit-manifest-sync,
chit-manifest-check, flight-check, flight-check-retro, topology-chit-gate,
topology-chit-gate-strict.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES = REPO_ROOT / "pmoves"

TARGET_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._/-]*)\s*:(?!=)")
ARGS_ASSIGN_RE = re.compile(r"\bARGS\s*=")

# Recursions where parent and child BOTH consume $(ARGS) and the pass-through is
# deliberate because both recipes drive the SAME tool with the same flag set.
# Anything not listed here is a leak: one ARGS cannot mean two different things.
SAME_TOOL_PASSTHROUGH = {("smoke-qwen-rerank", "smoke-gpu")}  # both run tools/smoke_gpu.py


def makefiles() -> list[Path]:
    return sorted(list((PMOVES / "mk").glob("*.mk")) + [PMOVES / "Makefile"])


def _scan():
    """-> (targets consuming $(ARGS), [(file, line, parent, child)] recursions)."""
    consumes: set[str] = set()
    owner: dict[tuple[str, int], str] = {}
    for path in makefiles():
        current = None
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.startswith("\t"):
                match = TARGET_RE.match(line)
                if match:
                    current = match.group(1)
                continue
            if current:
                owner[(path.as_posix(), lineno)] = current
                if "$(ARGS)" in line:
                    consumes.add(current)

    recursions = []
    for path in makefiles():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            index = line.find("$(MAKE)")
            if index < 0:
                continue
            rest = line[index + len("$(MAKE)"):]
            cleared = bool(ARGS_ASSIGN_RE.search(rest))
            child = None
            for token in rest.split():
                if token.startswith("-") or "=" in token.split('"')[0]:
                    continue
                child = token.strip("();")
                break
            recursions.append({
                "file": path.as_posix(), "line": lineno,
                "parent": owner.get((path.as_posix(), lineno)),
                "child": child, "cleared": cleared,
            })
    return consumes, recursions


def test_scanner_sees_the_makefiles():
    """If discovery ever breaks, every assertion below passes vacuously."""
    consumes, recursions = _scan()
    assert len(makefiles()) > 5
    assert len(consumes) > 20
    assert len(recursions) > 20


def test_no_recursion_into_env_bootstrap_lite_forwards_args():
    """The exact regression. env-bootstrap-lite runs bootstrap_light_env.py, which
    argparse-rejects any flag intended for a different tool — so an inherited
    ARGS does not degrade, it aborts the whole target."""
    _, recursions = _scan()
    offenders = [
        f"{r['file']}:{r['line']} ({r['parent']} -> env-bootstrap-lite)"
        for r in recursions
        if r["child"] == "env-bootstrap-lite" and not r["cleared"]
    ]
    assert not offenders, (
        "recursive $(MAKE) into env-bootstrap-lite without a literal `ARGS=`:\n  "
        + "\n  ".join(offenders)
    )


def test_env_bootstrap_lite_recursions_are_actually_present():
    """Paired with the test above: proves it is guarding real call sites rather
    than an empty set that would pass if the recursions were renamed away."""
    _, recursions = _scan()
    sites = [r for r in recursions if r["child"] == "env-bootstrap-lite"]
    assert len(sites) >= 7, f"expected >=7 call sites, found {len(sites)}"
    assert all(r["cleared"] for r in sites)


def test_args_consuming_parent_never_forwards_to_a_different_tool():
    """Broader class: when a parent that itself takes ARGS recurses into another
    ARGS-consuming target, one ARGS value has to serve two tools. Allowed only
    when both recipes drive the same script."""
    consumes, recursions = _scan()
    offenders = [
        f"{r['file']}:{r['line']} ({r['parent']} -> {r['child']})"
        for r in recursions
        if not r["cleared"]
        and r["child"] in consumes
        and r["parent"] in consumes
        and (r["parent"], r["child"]) not in SAME_TOOL_PASSTHROUGH
    ]
    assert not offenders, (
        "ARGS-consuming target forwards ARGS to a different tool:\n  "
        + "\n  ".join(offenders)
        + "\nAdd `ARGS=` to the recursive $(MAKE), or list the pair in "
          "SAME_TOOL_PASSTHROUGH if both recipes run the same script."
    )
