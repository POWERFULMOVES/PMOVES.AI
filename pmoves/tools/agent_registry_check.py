#!/usr/bin/env python3
"""agent_registry_check.py - assert the agent registry describes reality.

WHY THIS EXISTS
---------------
`pmoves/config/agent_registry.yaml` is read by humans and by tooling as the
answer to "what is this component and how do I reach it". When an entry drifts
from the code, it does not fail loudly - it quietly sends people somewhere that
does not exist.

Two entries had drifted (found 2026-08-21):

  pmoves_nats_mcp / pmoves_tailscale_mcp
    submodule: "pmoves-nats-mcp"    -> first-party in-repo code, not a gitlink.
                                      Reading this, an operator runs
                                      `git submodule update --init` and gets
                                      nothing, because there is nothing to init.
    transport: "sse"               -> the servers are stdio; server.py uses
                                      mcp.server.stdio.stdio_server().
    endpoint:  http://...:8080/sse -> nothing listens on 8080 and no compose
                                      file defines that host.

None of that was caught by anything, because nothing checked. This does.

CHECKS
  1. every `submodule:` claim appears as a real path in .gitmodules
  2. every `path:` exists on disk and is NOT declared as a submodule
  3. `transport: sse|http` REQUIRES an endpoint (otherwise it cannot be dialled),
     UNLESS the entry is marked status: planned/proposed/deprecated - recording
     an intended transport is fine; publishing an address nothing answers is not
  4. `transport: stdio` must NOT carry an endpoint (a stdio bridge is spawned by
     the client, never dialled - an endpoint here is fiction)

  5. two entries describing the SAME component must not make contradictory
     reachability claims. Found 2026-08-22, after this tool had reported the
     file "clean": `pmoves-e2b-mcp-server` has two entries -

         pmoves_e2b_mcp_server:  port: null   # stdio transport, no HTTP port
         pmoves_e2b_mcp:         transport: sse
                                 endpoint: http://pmoves-e2b-mcp:8080/sse

     Both pass checks 1-4 in isolation. Nothing compared them, so the file says
     both "there is no port" and "dial it here" about one component, and a
     reader has no way to know which is true. This is the same shape as the
     dependency audit that prompted it: two declarations of one thing, and no
     check that they agree.

     Deliberately NOT flagged: two entries for one submodule that simply do not
     conflict. A repo can legitimately host several services. Flagging mere
     duplication would be the over-reporting that trains people to ignore a
     check.

Exit 0 clean, 1 on any finding. This is a truth check, not a style check, so
every finding is blocking.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML required: uv run --with pyyaml python <this file>\n")
    raise SystemExit(1)

def _repo_root() -> Path:
    """Locate the repo root regardless of cwd.

    `make -C pmoves` runs with cwd=pmoves/, while CI and humans usually run from
    the repo root. Resolving from __file__ means the tool works from either
    without the caller having to know.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pmoves" / "config" / "agent_registry.yaml").exists():
            return parent
    return Path.cwd()


ROOT = _repo_root()
REGISTRY = ROOT / "pmoves" / "config" / "agent_registry.yaml"
GITMODULES = ROOT / ".gitmodules"


def walk_entries(obj, key=None):
    """Yield (identifier, mapping) for every dict that looks like a component entry."""
    if isinstance(obj, dict):
        if any(k in obj for k in ("submodule", "path", "transport", "endpoint")) and (
            "name" in obj or key
        ):
            yield (obj.get("name") or key), obj
        for k, v in obj.items():
            yield from walk_entries(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_entries(v, key)


def main() -> int:
    if not REGISTRY.exists():
        sys.stderr.write("not found: {} (run from the repo root)\n".format(REGISTRY))
        return 1
    reg = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    gm = GITMODULES.read_text(encoding="utf-8") if GITMODULES.exists() else ""

    problems = []
    seen = set()
    targets = {}   # submodule/path -> [(entry key, endpoint or None)]
    for name, entry in walk_entries(reg):
        ident = str(name)
        if ident in seen:
            continue
        seen.add(ident)

        target = entry.get("submodule") or entry.get("path")
        if isinstance(target, str):
            targets.setdefault(target, []).append((ident, entry.get("endpoint")))

        sm = entry.get("submodule")
        if isinstance(sm, str) and ("path = " + sm) not in gm:
            kind = "exists on disk as regular files" if (ROOT / sm).is_dir() else "does not exist"
            problems.append(
                "{}: declares submodule '{}' but it is not in .gitmodules ({}). "
                "Use `path:` for first-party in-repo code.".format(ident, sm, kind)
            )

        pth = entry.get("path")
        if isinstance(pth, str):
            if not (ROOT / pth).exists():
                problems.append("{}: path '{}' does not exist".format(ident, pth))
            elif ("path = " + pth) in gm:
                problems.append(
                    "{}: '{}' IS a submodule — declare it with `submodule:`, not `path:`".format(ident, pth)
                )

        transport = entry.get("transport")
        endpoint = entry.get("endpoint")
        # An entry recording INTENT may name a transport it does not yet serve.
        # What it must not do is publish an address nothing answers on.
        planned = str(entry.get("status", "")).lower() in ("planned", "proposed", "deprecated")
        if transport in ("sse", "http", "https") and not endpoint and not planned:
            problems.append(
                "{}: transport '{}' requires an endpoint — it cannot be dialled without one".format(ident, transport)
            )
        if transport == "stdio" and endpoint:
            problems.append(
                "{}: transport 'stdio' must not carry an endpoint ('{}') — a stdio bridge is "
                "spawned by the client, never dialled".format(ident, endpoint)
            )

    # 5. contradictory reachability claims about the same component
    for target, claims in sorted(targets.items()):
        reachable = [(k, e) for k, e in claims if e]
        portless = [(k, e) for k, e in claims if not e]
        if reachable and portless:
            r = ", ".join("{} -> {}".format(k, e) for k, e in reachable)
            n = ", ".join(k for k, _ in portless)
            problems.append(
                "{}: contradictory reachability. {} declares no port/endpoint while {} "
                "says it is dialable. One component cannot be both; a reader has no way "
                "to tell which is true.".format(target, n, r)
            )

    if problems:
        print("agent-registry check: {} problem(s)".format(len(problems)))
        for p in problems:
            print("  - {}".format(p))
        return 1
    print("agent-registry check: clean ({} entries verified)".format(len(seen)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
