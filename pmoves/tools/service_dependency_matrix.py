#!/usr/bin/env python3
"""service_dependency_matrix.py - derive bring-up/shutdown order from the compose graph.

WHY THIS EXISTS
---------------
Layered bring-up and graceful shutdown both need one thing: a truthful dependency
order. We have ~52 compose files and ~170 `depends_on` edges. A hand-written order
cannot survive that - it drifts the moment someone adds a service, and a drifted
runbook is worse than none, because it reads as authoritative.

So the order is DERIVED from the compose files, never authored. Re-run it and the
matrix is current by construction.

WHAT IT CHECKS (the failures that hide behind a green bring-up)
---------------------------------------------------------------
1. CYCLES - a dependency cycle means there is no valid start order at all.

2. `service_healthy` pointing at a service with NO healthcheck. This is the one
   that matters most here. `depends_on: {x: {condition: service_healthy}}`
   promises the dependant waits for readiness - but if `x` declares no
   healthcheck, that promise cannot be kept as written. The graph LOOKS ordered
   and is not. Same family as a health endpoint returning 200 while the thing
   behind it is dark.

3. `service_started` on a data store. "Started" is process liveness, not
   readiness. Postgres accepting TCP is not Postgres accepting queries - on
   2026-08-19 a 6-minute fsync meant every dependant that waited only for
   "started" failed with SQLSTATE 57P03. Advisory, not blocking.

4. build: vs image: provenance - which services are built from source in-repo
   and which are pulled, so "built from source or hand-rolled?" is answered per
   service instead of per guess.

5. Dependencies referenced but never defined in the parsed files - usually a
   missing overlay, which is silent at parse time.

EXIT CODES
  0  clean
  1  blocking (cycle, undefined dependency, unreadable file)
  2  advisory only (healthcheck gaps, weak waits)
Blocking and advisory are separated so CI can gate on real breakage without
drowning in advice.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML required: uv run --with pyyaml python <this file>\n")
    raise SystemExit(1)

# Data stores where `service_started` is a weaker promise than the dependant needs.
# Deliberately not exhaustive - it lists what we have actually been bitten by.
STATEFUL_HINTS = (
    "postgres", "supabase-db", "mysql", "mariadb", "redis", "valkey", "neo4j",
    "qdrant", "clickhouse", "minio", "meilisearch", "surrealdb", "nats", "mongo",
)


def load_compose(paths):
    """Merge `services` across files. Later files win, mirroring compose overlay order."""
    services = {}
    problems = []
    for p in paths:
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception as e:  # noqa: BLE001 - one bad file must not abort the survey
            problems.append("{}: unreadable ({})".format(p.name, e))
            continue
        for name, spec in (doc.get("services") or {}).items():
            if not isinstance(spec, dict):
                continue
            services.setdefault(name, {})
            services[name].update(spec)
    return services, problems


def edges_of(spec):
    """Normalize both depends_on forms to {dependency: condition}."""
    dep = spec.get("depends_on")
    if not dep:
        return {}
    if isinstance(dep, list):
        return dict((d, "service_started") for d in dep)
    if isinstance(dep, dict):
        out = {}
        for d, cfg in dep.items():
            if isinstance(cfg, dict):
                out[d] = cfg.get("condition", "service_started")
            else:
                out[d] = "service_started"
        return out
    return {}


def layer(services):
    """Kahn layering. Returns (layers, cyclic_nodes)."""
    deps = {}
    for n, s in services.items():
        deps[n] = set(edges_of(s)) & set(services)
    layers = []
    placed = set()
    while True:
        ready = sorted(n for n, d in deps.items() if n not in placed and d <= placed)
        if not ready:
            break
        layers.append(ready)
        placed |= set(ready)
    return layers, sorted(set(services) - placed)


def analyze(services):
    layers, cyclic = layer(services)
    undefined = []
    health_gaps = []
    weak_waits = []
    provenance = {}
    for name, spec in sorted(services.items()):
        if spec.get("build"):
            provenance[name] = "build"
        elif spec.get("image"):
            provenance[name] = "image"
        else:
            provenance[name] = "UNDEFINED"
        for dep, cond in edges_of(spec).items():
            if dep not in services:
                undefined.append("{} -> {} (dependency not defined in parsed files)".format(name, dep))
                continue
            if cond == "service_healthy" and not services[dep].get("healthcheck"):
                health_gaps.append(
                    "{} waits on {} with condition=service_healthy, but {} declares NO healthcheck".format(name, dep, dep)
                )
            if cond == "service_started" and any(h in dep for h in STATEFUL_HINTS):
                weak_waits.append(
                    "{} waits on {} with condition=service_started (data store - 'started' is not 'ready')".format(name, dep)
                )
    return {
        "layers": layers,
        "cyclic": cyclic,
        "undefined": undefined,
        "health_gaps": health_gaps,
        "weak_waits": weak_waits,
        "provenance": provenance,
        "service_count": len(services),
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("files", nargs="*", help="compose files (default: pmoves/docker-compose.yml)")
    ap.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    a = ap.parse_args()

    paths = [Path(f) for f in a.files] or [Path("pmoves/docker-compose.yml")]
    paths = [p for p in paths if p.exists()]
    if not paths:
        sys.stderr.write("no compose files found\n")
        return 1

    services, read_problems = load_compose(paths)
    r = analyze(services)

    if a.format == "json":
        print(json.dumps(r, indent=2))
    elif a.format == "markdown":
        names = ", ".join(p.name for p in paths)
        print("# Service dependency matrix")
        print("")
        print("_Generated by `pmoves/tools/service_dependency_matrix.py` from {} - do not hand-edit._".format(names))
        print("")
        print("**{} services, {} layers.** Bring up in layer order; shut down in reverse.".format(
            r["service_count"], len(r["layers"])))
        print("")
        for i, lyr in enumerate(r["layers"]):
            print("## Layer {}".format(i))
            print("")
            for s in lyr:
                print("- `{}` ({})".format(s, r["provenance"][s]))
            print("")
    else:
        print("services={}  layers={}".format(r["service_count"], len(r["layers"])))
        for i, lyr in enumerate(r["layers"]):
            more = " ..." if len(lyr) > 8 else ""
            print("  layer {:>2} ({:>2}): {}{}".format(i, len(lyr), ", ".join(lyr[:8]), more))
        built = sum(1 for v in r["provenance"].values() if v == "build")
        pulled = sum(1 for v in r["provenance"].values() if v == "image")
        undef = sum(1 for v in r["provenance"].values() if v == "UNDEFINED")
        print("")
        print("provenance: {} built-from-source, {} pulled-image, {} UNDEFINED".format(built, pulled, undef))

    blocking = bool(r["cyclic"] or r["undefined"] or read_problems)
    advisory = bool(r["health_gaps"] or r["weak_waits"])
    if a.format != "json":
        groups = (
            ("UNREADABLE", read_problems),
            ("CYCLE", r["cyclic"]),
            ("UNDEFINED DEPENDENCY", r["undefined"]),
            ("HEALTHCHECK GAP", r["health_gaps"]),
            ("WEAK WAIT", r["weak_waits"]),
        )
        for label, items in groups:
            if items:
                print("")
                print("{} ({}):".format(label, len(items)))
                for it in items[:20]:
                    print("  - {}".format(it))
                if len(items) > 20:
                    print("  ... and {} more".format(len(items) - 20))
    if blocking:
        return 1
    return 2 if advisory else 0


if __name__ == "__main__":
    raise SystemExit(main())
