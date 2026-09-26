#!/usr/bin/env python3
"""Does the sync-secrets-local map read every secret GitHub holds?

The CHIT bundle (``env.cgp.json``) that every node consumes -- Linux runners and
the Windows 4090/5090 alike -- is built from exactly one place: the ``env:``
block of the "Sync Secrets to Local" step in
``.github/workflows/sync-secrets-local.yml``. A secret stored in GitHub but read
by no row there never reaches any node, while every other layer (manifest,
inventory, compose) can look correct. That is PR #2888 (COMPOSIO_API_KEY), and
it recurred at 32 names on 2026-09-26.

Every node is a full copy of PMOVES.AI, so the map must cover the FULL
repository + deployment-environment secret name set. The only exceptions are
listed in ``EXCEPTIONS`` with a reason.

The step builds the bundle from an explicit ALLOWLIST -- the env: keys it
declares, via ``declared_env_keys()`` below -- not from ``os.environ`` minus a
prefix skip list. The skip list both dropped a mapped secret
(CI_GHCR_NAMESPACE, prefix ``CI``) and let runner variables (HOSTNAME, LABELS,
``_``, proxies) into every node's bundle (#3188 review P2).

This tool works on NAMES only. It never reads a secret value: ``gh secret list``
returns names and timestamps, and ``--bundle`` reads only the ``label`` field of
each bundle point.

Exit codes: 0 clean, 1 findings, 3 could-not-measure.

Usage:
    python pmoves/tools/secrets_bundle_map_gap.py --live
    python pmoves/tools/secrets_bundle_map_gap.py --names-file repo.txt --names-file prod.txt
    python pmoves/tools/secrets_bundle_map_gap.py --live --bundle ~/.config/pmoves/chit/env.cgp.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "sync-secrets-local.yml"
STEP_NAME = "Sync Secrets to Local"

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_COULD_NOT_MEASURE = 3

# GitHub secret names the map deliberately does NOT read. Each needs a reason a
# reviewer can check. Operator rule (2026-09-26): only names that make no sense
# as a node env value qualify -- not "only CI uses it", not "unreferenced".
EXCEPTIONS: Dict[str, str] = {
    "GITHUB_TOKEN": (
        "GitHub-minted per-job token, not a stored secret; meaningless on a node."
    ),
    "ANTHROPIC_API_KEY": (
        "The Prod slot holds an sk-ant-oat01 OAuth token parked there for lack of a "
        "free slot; shipped as ANTHROPIC_API_KEY it makes Claude Code hang. The label "
        "stays in the map, emitted empty; see the comment on that row."
    ),
}

# Node-local topology (#3188 review P1). Registered in GitHub Prod, but a Prod
# address is wrong on every node: each node resolves these to its OWN services
# via its Tailscale name (pmoves/config/node_local_keys.yaml, the one
# declaration; a test pins this tuple to it). The workflow must carry NO row
# for them -- a row is reported as a finding.
NODE_LOCAL_REASON = "node-local topology, resolved per node via TS_<NODE>"
NODE_LOCAL: Tuple[str, ...] = (
    "NATS_URL", "NATS_URL_TAILNET", "SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL",
    "POSTGRES_HOSTNAME", "POSTGRES_DB", "OLLAMA_BASE_URL", "OPENAI_COMPATIBLE_BASE_URL",
)
EXCEPTIONS.update({name: NODE_LOCAL_REASON for name in NODE_LOCAL})

# Declared env rows that are not bundle material: OUTPUT_FORMAT is a workflow
# input that selects the log format.
NON_SECRET_ROWS = frozenset({"OUTPUT_FORMAT"})

_SECRET_REF = re.compile(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)")
_KEY_LINE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):")


class CouldNotMeasure(RuntimeError):
    """An input the verdict depends on could not be read."""


@dataclass
class BundleMap:
    """Labels written to the bundle and the GitHub secrets each one reads."""

    rows: Dict[str, Set[str]]
    environment: Optional[str]

    @property
    def sources(self) -> Set[str]:
        out: Set[str] = set()
        for refs in self.rows.values():
            out |= refs
        return out


@dataclass
class Report:
    registered: Set[str]
    uncovered: List[str] = field(default_factory=list)
    node_local_mapped: List[str] = field(default_factory=list)
    mapped_not_registered: List[str] = field(default_factory=list)
    not_in_bundle: Optional[List[str]] = None

    @property
    def findings(self) -> bool:
        return bool(self.uncovered or self.node_local_mapped or self.not_in_bundle)


def _find_step(doc: dict) -> Tuple[dict, dict]:
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if step.get("name") == STEP_NAME:
                return job, step
    raise CouldNotMeasure(f"step {STEP_NAME!r} not found in {WORKFLOW.name}")


def declared_env_keys(path: Path = WORKFLOW) -> Set[str]:
    """Names declared in the step's ``env:`` block -- stdlib only.

    The workflow step itself calls this to build its allowlist, and the runner
    Python there is not guaranteed to have PyYAML. It reads key NAMES by
    indentation only; ``test_secrets_bundle_map_gap`` pins it to the YAML
    parse in ``load_map``. Raises ``CouldNotMeasure`` if the block is not
    found or is empty, so a caller can fail closed.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CouldNotMeasure(f"cannot read {path}: {exc}") from exc
    marker = re.compile(r"^(\s*)-\s+name:\s*" + re.escape(STEP_NAME) + r"\s*$")
    keys: Set[str] = set()
    i = 0
    while i < len(lines):
        m = marker.match(lines[i])
        i += 1
        if not m:
            continue
        step_indent = len(m.group(1)) + 2
        env_indent = key_indent = None
        for line in lines[i:]:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            km = _KEY_LINE.match(line)
            indent = len(line) - len(line.lstrip())
            if env_indent is None:
                if indent < step_indent or line.lstrip().startswith("- "):
                    break
                if km and indent == step_indent and km.group(2) == "env":
                    env_indent = indent
                continue
            if indent <= env_indent:
                break
            if km and (key_indent is None or indent == key_indent):
                key_indent = indent
                keys.add(km.group(2))
        break
    if not keys:
        raise CouldNotMeasure(f"no env: keys found for step {STEP_NAME!r} in {path}")
    return keys


def load_map(path: Path = WORKFLOW) -> BundleMap:
    """Parse the step's env: block and job environment."""
    import yaml  # lazy: declared_env_keys() must stay stdlib-only

    try:
        text = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
    except (OSError, yaml.YAMLError) as exc:
        raise CouldNotMeasure(f"cannot parse {path}: {exc}") from exc
    job, step = _find_step(doc)
    env = step.get("env") or {}
    rows = {str(k): set(_SECRET_REF.findall(str(v))) for k, v in env.items()}
    environment = job.get("environment")
    if isinstance(environment, dict):
        environment = environment.get("name")
    return BundleMap(rows, environment)


def _gh_names(extra: Sequence[str]) -> Set[str]:
    cmd = ["gh", "secret", "list", "--json", "name", *extra]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CouldNotMeasure(f"{' '.join(cmd)}: {exc}") from exc
    if out.returncode != 0:
        # stderr from gh carries no secret material (names-only listing).
        raise CouldNotMeasure(f"{' '.join(cmd)} exited {out.returncode}: {out.stderr.strip()[:200]}")
    try:
        return {row["name"] for row in json.loads(out.stdout or "[]")}
    except (ValueError, KeyError, TypeError) as exc:
        raise CouldNotMeasure(f"unparseable gh output: {exc}") from exc


def live_names(environment: Optional[str]) -> Dict[str, Set[str]]:
    """Repo-level names plus the job environment's names, via gh (names only)."""
    scopes = {"repo": _gh_names([])}
    if environment:
        scopes[f"env:{environment}"] = _gh_names(["--env", environment])
    return scopes


def read_names_file(path: Path) -> Set[str]:
    try:
        return {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except OSError as exc:
        raise CouldNotMeasure(f"cannot read {path}: {exc}") from exc


def bundle_labels(path: Path) -> Set[str]:
    """Labels of an installed bundle. Reads the ``label`` field only."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return {p["label"] for p in doc["points"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CouldNotMeasure(f"cannot read bundle labels from {path}: {exc}") from exc


def analyse(bmap: BundleMap, registered: Set[str], bundle: Optional[Set[str]] = None) -> Report:
    rep = Report(registered=registered)
    rep.uncovered = sorted(registered - bmap.sources - set(EXCEPTIONS))
    rep.node_local_mapped = sorted(set(NODE_LOCAL) & set(bmap.rows))
    rep.mapped_not_registered = sorted(bmap.sources - registered)
    if bundle is not None:
        # A row whose source is registered should produce a bundle label.
        expected = {
            label
            for label, refs in bmap.rows.items()
            if refs & registered
        }
        rep.not_in_bundle = sorted(expected - bundle)
    return rep


def _print(rep: Report, bmap: BundleMap, scopes: Dict[str, Set[str]], bundle: Optional[Set[str]]) -> None:
    sizes = ", ".join(f"{k}={len(v)}" for k, v in scopes.items())
    print(f"inputs: {sizes}, registered_union={len(rep.registered)}, "
          f"map_rows={len(bmap.rows)}, map_sources={len(bmap.sources)}"
          + (f", bundle_labels={len(bundle)}" if bundle is not None else ""))
    print(f"uncovered (registered in GitHub, read by no map row): {len(rep.uncovered)}")
    for n in rep.uncovered:
        print(f"  - {n}")
    print(f"exceptions honoured: {sorted(set(EXCEPTIONS) & rep.registered)}")
    if rep.node_local_mapped:
        print(f"node-local labels carried by the map (must not be; {NODE_LOCAL_REASON}): "
              f"{rep.node_local_mapped}")
    if rep.mapped_not_registered:
        print(f"info: map reads names GitHub does not hold ({len(rep.mapped_not_registered)}): "
              f"{rep.mapped_not_registered}")
    if rep.not_in_bundle is not None:
        print(f"mapped + registered but absent from the bundle ({len(rep.not_in_bundle)}): "
              f"{rep.not_in_bundle}")
        if rep.not_in_bundle:
            print("  (either the bundle predates the row, or the GitHub value resolves empty)")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--live", action="store_true", help="list names via gh (repo + job environment)")
    src.add_argument("--names-file", action="append", type=Path, help="one secret name per line; repeatable")
    ap.add_argument("--workflow", type=Path, default=WORKFLOW)
    ap.add_argument("--bundle", type=Path, help="also check an installed env.cgp.json (labels only)")
    args = ap.parse_args(argv)
    try:
        bmap = load_map(args.workflow)
        if args.live:
            scopes = live_names(bmap.environment)
        else:
            scopes = {str(p): read_names_file(p) for p in args.names_file}
        registered: Set[str] = set().union(*scopes.values())
        if not registered:
            raise CouldNotMeasure("zero registered names read -- refusing to call that clean")
        bundle = bundle_labels(args.bundle) if args.bundle else None
    except CouldNotMeasure as exc:
        print(f"COULD-NOT-MEASURE: {exc}", file=sys.stderr)
        return EXIT_COULD_NOT_MEASURE
    rep = analyse(bmap, registered, bundle)
    _print(rep, bmap, scopes, bundle)
    return EXIT_FINDINGS if rep.findings else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
