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
  1  blocking (cycle, undefined dependency, unreadable/missing input)
  3  advisory only (healthcheck gaps, weak waits, unsafe shutdown)

Advisory is 3, NOT 2, on purpose. Exit 2 is what a FAILED RUNNER returns —
argparse errors use it, and `uv` returns it when it cannot start the script (for
example when PyYAML cannot be fetched offline). If advisory were 2, a caller
could not tell "the graph has advice" from "the tool never ran", and would
happily accept an empty result as success.
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

# Services that actually PERSIST state and therefore need a clean stop. Kept as an
# explicit set rather than a substring match: the first version flagged
# nats-echo-req, a2ui-nats-bridge and nats-init purely because "nats" appears in
# their names. An over-reporting check trains people to ignore it, which is how a
# real finding gets missed.
STATEFUL_SERVICES = {
    "supabase-db", "archon-postgres", "neo4j", "qdrant", "minio", "meilisearch",
    "tensorzero-clickhouse", "nats", "open-notebook-surrealdb-ext",
    "open-notebook-surrealdb", "juicefs-redis",
}


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
    shutdown_risks = []
    for name, spec in sorted(services.items()):
        if name not in STATEFUL_SERVICES:
            continue
        grace = spec.get("stop_grace_period")
        sig = spec.get("stop_signal")
        if grace is None:
            shutdown_risks.append(
                "{} has no stop_grace_period - Docker SIGKILLs it 10s after SIGTERM".format(name)
            )
        if any(pg in name for pg in ("postgres", "supabase-db")) and sig != "SIGINT":
            shutdown_risks.append(
                "{} uses {} - PostgreSQL treats SIGTERM as SMART shutdown (waits for ALL sessions to end); "
                "SIGINT is FAST shutdown (aborts transactions, exits cleanly)".format(name, sig or "the SIGTERM default")
            )
    return {
        "shutdown_risks": shutdown_risks,
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
    ap.add_argument("--format", choices=["text", "markdown", "json", "shutdown"], default="text")
    a = ap.parse_args()

    paths = [Path(f) for f in a.files] or [Path("pmoves/docker-compose.yml")]
    # A missing input must be REPORTED, not filtered away. Dropping it silently
    # meant a misspelled or deleted overlay produced a smaller-but-successful
    # matrix: the `if not paths` guard never fires while any other input exists,
    # so an incomplete graph publishes as if it were complete.
    missing = [str(p) for p in paths if not p.exists()]
    paths = [p for p in paths if p.exists()]
    if not paths:
        sys.stderr.write("no compose files found\n")
        return 1

    services, read_problems = load_compose(paths)
    read_problems = ["{}: input not found".format(m) for m in missing] + read_problems
    r = analyze(services)

    if a.format == "shutdown":
        # Reverse layer order. Dependants stop BEFORE the things they depend on,
        # so a data store is never killed while a client still holds a session.
        print("# Graceful shutdown order (reverse of bring-up)")
        print("")
        for i, lyr in enumerate(reversed(r["layers"])):
            print("## Stop group {} (was layer {})".format(i, len(r["layers"]) - 1 - i))
            print("")
            for sname in lyr:
                print("- `{}`".format(sname))
            print("")
        return 0
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
    advisory = bool(r["health_gaps"] or r["weak_waits"] or r["shutdown_risks"])
    if a.format != "json":
        groups = (
            ("UNREADABLE", read_problems),
            ("CYCLE", r["cyclic"]),
            ("UNDEFINED DEPENDENCY", r["undefined"]),
            ("HEALTHCHECK GAP", r["health_gaps"]),
            ("WEAK WAIT", r["weak_waits"]),
            ("UNSAFE SHUTDOWN", r["shutdown_risks"]),
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
    return 3 if advisory else 0


if __name__ == "__main__":
    raise SystemExit(main())
