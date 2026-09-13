#!/usr/bin/env python3
"""Compose build-provenance audit — submodule builds over hand-rolled shims.

Operator doctrine (2026-09-12, pmoves/docs/operations/COMPOSE_BUILD_PROVENANCE.md):
a compose service that compiles code should build from a SUBMODULE Dockerfile
(fork, gitlink-pinned, fork-registry-declared, CHIT-tracked) or use a
digest-pinned IMAGE. Superproject ``context: .`` builds are hand-rolled shims
— acceptable only for PMOVES-original glue and only when baselined.

This tool enumerates every ``build:`` stanza in every compose file, classifies
it, and fails on any SUPERPROJECT-SHIM service absent from the baseline
(pmoves/configs/compose_provenance_baseline.json). New shims must be promoted
to fork submodules or added to the baseline with a PR-stated reason.

Usage:
    compose-provenance-audit          # audit (exit 1 on unregistered shims)
    compose-provenance-audit --json   # machine-readable
    compose-provenance-audit --baseline  # rewrite the baseline from current state
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader + Compose-spec long-form tags (!reset, !override, !reset-tags).

    docker compose treats these as merge instructions; plain safe_load raises
    "could not determine a constructor" and the file would silently drop out
    of the audit — exactly the blind spot a new shim could hide in. Decode
    them as their underlying value; classification only reads build contexts.
    """


def _tag_value(loader: yaml.Loader, node: yaml.Node):
    """Decode a Compose-spec long-form tag as its underlying scalar/collection."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=False)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=False)
    return None


for _tag in ("!reset", "!override", "!reset-tags"):
    _ComposeLoader.add_constructor(_tag, _tag_value)


PMOVES_DIR = Path(__file__).resolve().parents[1]
COMPOSE_GLOB = "docker-compose*.yml"
BASELINE = PMOVES_DIR / "configs" / "compose_provenance_baseline.json"

SUBMODULE, IMAGE, SHIM = "SUBMODULE", "IMAGE", "SUPERPROJECT-SHIM"


def _compose_files() -> list[Path]:
    return sorted(PMOVES_DIR.glob(COMPOSE_GLOB))


def _classify(build: object) -> str:
    """Classify one build stanza (dict or string) by its context."""
    ctx = build.get("context", ".") if isinstance(build, dict) else str(build or ".")
    # Any path component starting PMOVES/Pmoves points INTO a submodule
    # checkout (../PMOVES-Archon, ./PMOVES-ToKenism-Multi/pmoves-nextjs, or
    # deeper paths like ../PMOVES-nats-server/pmoves).
    norm = ctx.replace("\\", "/").strip()
    parts = [p for p in norm.split("/") if p not in ("", ".", "..")]
    if any(p.startswith("PMOVES") or p.startswith("Pmoves") for p in parts):
        return SUBMODULE
    return SHIM  # any other local path is superproject-tree relative


def collect() -> dict[str, dict]:
    """service -> {class, context, file} for every build stanza."""
    out: dict[str, dict] = {}
    for f in _compose_files():
        try:
            doc = yaml.load(f.read_text(encoding="utf-8"), Loader=_ComposeLoader)
        except yaml.YAMLError as exc:
            print(f"warn: {f.name}: unparseable ({exc}); skipped", file=sys.stderr)
            continue
        for name, svc in (doc.get("services") or {}).items():
            if not isinstance(svc, dict) or "build" not in svc:
                continue
            ctx = svc["build"]
            ctx_str = ctx.get("context", ".") if isinstance(ctx, dict) else str(ctx)
            # Same service may appear in multiple overlays; keep the strongest
            # classification (SUBMODULE beats IMAGE beats SHIM is irrelevant
            # here since only build stanzas are scanned — keep first-seen
            # submodule context, else first seen).
            cls = _classify(ctx)
            prev = out.get(name)
            if prev is None or (prev["class"] == SHIM and cls == SUBMODULE):
                out[name] = {"class": cls, "context": ctx_str, "file": f.name}
    return out


def _load_baseline() -> dict:
    if BASELINE.is_file():
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    return {"shims": []}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--baseline", action="store_true",
                    help="rewrite the baseline from current state (deliberate; say why in the PR)")
    args = ap.parse_args()

    found = collect()
    baseline = _load_baseline()
    known_shims = set(baseline.get("shims", []))

    shims = {k: v for k, v in found.items() if v["class"] == SHIM}
    subs = {k: v for k, v in found.items() if v["class"] == SUBMODULE}

    if args.baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps({
            "_doc": "Deliberate superproject-shim exceptions (see COMPOSE_BUILD_PROVENANCE.md). "
                    "Each entry: the service builds from the superproject tree on purpose.",
            "shims": sorted(shims),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"baseline written: {len(shims)} shims -> {BASELINE.relative_to(PMOVES_DIR)}")
        return 0

    unregistered = sorted(set(shims) - known_shims)
    retired = sorted(known_shims - set(shims))

    if args.json:
        print(json.dumps({
            "files_scanned": [f.name for f in _compose_files()],
            "submodule_builds": sorted(subs),
            "image_only_excluded": True,
            "shims_total": len(shims),
            "shims_baselined": len(set(shims) & known_shims),
            "unregistered_shims": unregistered,
            "retired_baseline_entries": retired,
        }, indent=2))
    else:
        print(f"compose build provenance: {len(subs)} SUBMODULE / {len(shims)} SUPERPROJECT-SHIM "
              f"({len(set(shims) & known_shims)} baselined)")
        if unregistered:
            print(f"\nUNREGISTERED SHIMS ({len(unregistered)}) — promote to a fork submodule or baseline deliberately:")
            for s in unregistered:
                print(f"  - {s}  ({shims[s]['context']} in {shims[s]['file']})")
        if retired:
            print(f"\nSTALE BASELINE — no longer shims ({len(retired)}); drop them:")
            for s in retired:
                print(f"  - {s}")

    if unregistered or retired:
        print("\nfix: promote the service to a fork submodule (docs/operations/COMPOSE_BUILD_PROVENANCE.md"
              " § Promotion recipe), or run: make -C pmoves compose-provenance-baseline")
        return 1
    print("OK: every superproject shim is a registered exception.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
