#!/usr/bin/env python3
"""Validate-tac ratchet.

No-network scan of every `pmoves/configs/tac_trees/*.tac.yaml` for
unknown `action.type` values. Fails (exit 1) on any unknown type; the
runner-side check in `pmoves/tools/tac_runner.py` is FAIL-CLOSED on
unknown types too (PR #2373), so this ratchet just surfaces the
inert-assertion count before the runner does.

Why a separate ratchet: tac_runner.py is the executor — it runs the
probes. This script is the static analyzer that catches the same
pattern one layer earlier, in CI, before any node executes. Together:
the ratchet fails the PR on a new unknown type, the runner fails
the tree at execution. Two layers, same answer.

The 141 inert assertions in 18 of 43 trees that PR #2371 measured
all started life this way: a typo'd or future action type that the
runner didn't recognize. The runner used to silently keep them at
"pending", so the green tree summary was untrustworthy. This ratchet
+ the runner's else branch close that gap.

Usage:
    python3 pmoves/tools/validate_tac.py
    python3 pmoves/tools/validate_tac.py --json
    python3 pmoves/tools/validate_tac.py --tree pmoves/configs/tac_trees/soundcloud-ingest.tac.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TAC_DIR = REPO_ROOT / "pmoves" / "configs" / "tac_trees"
BASELINE_PATH = TAC_DIR / "_known_unknowns.yaml"

# Mirror of the if/elif dispatch in pmoves/tools/tac_runner.py.
# If you add a new type to the runner, add it here too (or the
# ratchet and the runner will disagree on what's allowed).
ALLOWED_ACTION_TYPES = frozenset({
    "file_exists",
    "grep",
    "command",
    "http",
    "manual",
})

# Treat `action: null` / `action: ~` as no-action, not as a type
# to validate. Same treatment as a node with no `action` key at all.
NO_ACTION_SENTINELS = frozenset({None, "", "null", "~"})


def _load_baseline() -> set[str]:
    """Read the operator-acknowledged set of unknown action types.

    The baseline file is a YAML list of action type names that the
    ratchet should NOT fail on (these are inert in the runner today;
    the operator has decided not to wire them up yet). Anything not
    in the baseline AND not in ALLOWED_ACTION_TYPES is a ratchet
    failure — exactly the ratchet-only-goes-down pattern.

    The baseline file is committed, so the ratchet count is
    reviewable in PR diffs.
    """
    if not BASELINE_PATH.exists():
        return set()
    import yaml
    try:
        with BASELINE_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return set()
    if data is None:
        return set()
    if isinstance(data, list):
        return {str(x) for x in data if x}
    if isinstance(data, dict):
        # support { type: { reason: ..., nodes: ... } } form for
        # richer bookkeeping; the keys are still the types
        return {str(k) for k in data.keys()}
    return set()


def _collect_nodes(node, path: tuple = ()):
    """Depth-first traversal of a TAC tree; yields (node, path) pairs
    where path is a tuple of child-id strings for diagnostics."""
    if not isinstance(node, dict):
        return
    yield node, path
    for i, child in enumerate(node.get("children") or []):
        yield from _collect_nodes(child, path + (str(i),))


def _scan_tree(path: Path) -> list[dict]:
    """Return list of problems for one TAC tree file."""
    import yaml

    def _compose_override_tag(loader, node):
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node)
        return loader.construct_scalar(node)

    for tag in ("!override", "!reset"):
        yaml.SafeLoader.add_constructor(tag, _compose_override_tag)

    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception as e:
        return [{
            "file": str(path.relative_to(REPO_ROOT)),
            "node": "<root>",
            "type": "<parse-error>",
            "detail": f"could not parse YAML: {e}",
        }]
    if not isinstance(data, dict):
        return []

    problems: list[dict] = []
    for node, path_tuple in _collect_nodes(data.get("root")):
        if not isinstance(node, dict):
            continue
        action = node.get("action")
        if not isinstance(action, dict):
            if action is None or action == "":
                continue
            problems.append({
                "file": str(path.relative_to(REPO_ROOT)),
                "node": node.get("id", "/".join(path_tuple) or "<unnamed>"),
                "type": "<non-dict-action>",
                "detail": (
                    f"action is {type(action).__name__} '{action!r}'; "
                    f"expected a mapping with a 'type' key."
                ),
            })
            continue
        action_type = action.get("type", "manual")
        if action_type in ALLOWED_ACTION_TYPES:
            continue
        problems.append({
            "file": str(path.relative_to(REPO_ROOT)),
            "node": node.get("id", "/".join(path_tuple) or "<unnamed>"),
            "type": action_type,
            "detail": (
                f"unknown action.type '{action_type}' "
                f"(allowed: {', '.join(sorted(ALLOWED_ACTION_TYPES))})"
            ),
        })
    return problems


def _all_trees() -> list[Path]:
    if not TAC_DIR.exists():
        return []
    return sorted(TAC_DIR.glob("*.tac.yaml"))


def _summary(problems: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in problems:
        # bucket by type so the operator sees which unknowns recur
        counts[p["type"]] = counts.get(p["type"], 0) + 1
    return counts


def _classify(problems: list[dict], baseline: set[str]) -> tuple[list[dict], list[dict]]:
    """Split problems into (failures, acknowledged).

    Failures are unknowns NOT in the baseline — those are new
    regressions the ratchet must surface. Acknowledged are in the
    baseline — those exist but the operator has decided they're
    acceptable for now (and they're tracked in the baseline so the
    ratchet count only goes down over time).
    """
    failures: list[dict] = []
    acknowledged: list[dict] = []
    for p in problems:
        if p["type"] in baseline:
            acknowledged.append(p)
        else:
            failures.append(p)
    return failures, acknowledged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tree",
        type=Path,
        help="scan a single tree instead of the whole pmoves/configs/tac_trees/ glob",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    args = parser.parse_args()

    if args.tree:
        if not args.tree.exists():
            print(f"tree not found: {args.tree}", file=sys.stderr)
            return 2
        files = [args.tree]
    else:
        files = _all_trees()
    if not files:
        print(f"no tac trees found under {TAC_DIR}", file=sys.stderr)
        return 2

    problems: list[dict] = []
    for f in files:
        problems.extend(_scan_tree(f))

    baseline = _load_baseline()
    failures, acknowledged = _classify(problems, baseline)

    if args.json:
        print(json.dumps({
            "files_scanned": [str(f.relative_to(REPO_ROOT)) for f in files],
            "files_total": len(files),
            "allowed_action_types": sorted(ALLOWED_ACTION_TYPES),
            "baseline_path": str(BASELINE_PATH.relative_to(REPO_ROOT)) if BASELINE_PATH.exists() else None,
            "baseline": sorted(baseline),
            "problems": problems,
            "failures": failures,
            "acknowledged": acknowledged,
            "summary": _summary(problems),
            "failure_summary": _summary(failures),
        }, indent=2))
    else:
        print(f"validate-tac: scanned {len(files)} trees")
        print(f"  baseline: {len(baseline)} acknowledged unknown type(s)")
        if not problems:
            print(f"  (clean — every action.type is in {{ {', '.join(sorted(ALLOWED_ACTION_TYPES))} }})")
        else:
            print(f"  total {len(problems)} unknown-type usage(s):")
            counts = _summary(problems)
            for kind, n in sorted(counts.items(), key=lambda x: -x[1]):
                marker = " (acknowledged)" if kind in baseline else ""
                print(f"    {kind}: {n}{marker}")
            if failures:
                print()
                print(f"  {len(failures)} FAILURE(S) — not in baseline:")
                for p in failures:
                    print(f"  [{p['type']}] {p['file']} :: {p['node']}")
                    print(f"      {p['detail']}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
