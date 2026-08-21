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
  3. `transport: sse|http` REQUIRES an endpoint (otherwise it cannot be dialled)
  4. `transport: stdio` must NOT carry an endpoint (a stdio bridge is spawned by
     the client, never dialled - an endpoint here is fiction)

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
    for name, entry in walk_entries(reg):
        ident = str(name)
        if ident in seen:
            continue
        seen.add(ident)

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
        if transport in ("sse", "http", "https") and not endpoint:
            problems.append(
                "{}: transport '{}' requires an endpoint — it cannot be dialled without one".format(ident, transport)
            )
        if transport == "stdio" and endpoint:
            problems.append(
                "{}: transport 'stdio' must not carry an endpoint ('{}') — a stdio bridge is "
                "spawned by the client, never dialled".format(ident, endpoint)
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
