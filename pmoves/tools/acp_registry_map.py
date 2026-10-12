#!/usr/bin/env python3
"""Map the ACP agent registry fork against the PMOVES agent registry.

The ACP registry (fork: POWERFULMOVES/PMOVES-registry, upstream:
agentclientprotocol/registry) stores one ``<id>/agent.json`` per protocol
agent. The PMOVES registry (``pmoves/config/agent_registry.yaml``) describes
the fleet's own 100+ agents. Neither knows about the other — this tool is
the bridge:

  acp_id  <->  PMOVES agent <-> consuming repo

Outputs a deterministic mapping artifact plus a summary. Matching is
conservative (repo/name heuristics, never fuzzy guesses): an entry is
``linked`` only when a repo or name match is explicit.

Usage:
  python3 pmoves/tools/acp_registry_map.py [--registry PATH] [--out PATH]
                                           [--write | --check]

``--registry`` defaults to the ``PMOVES-registry`` submodule pinned in this
repo (populate it with ``git submodule update --init PMOVES-registry``);
``--out`` defaults to ``pmoves/configs/acp_registry_map.json``. Without
``--write`` the tool runs read-only and prints the summary. ``--check`` exits
1 when the committed artifact differs from a fresh build.

Fails closed (exit 2) on a missing OR empty registry. An uninitialized
submodule is an existing empty directory; it used to produce
``acp_entries: {}`` with exit 0, and a stale sibling clone silently dropped
newer entries (crush-acp, PR #3347). The artifact stamps the registry commit
so a regeneration from the wrong checkout is visible in the diff.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT / "PMOVES-registry"
DEFAULT_OUT = REPO_ROOT / "pmoves" / "configs" / "acp_registry_map.json"

# Explicit name bridges: ACP entry id (lowercase) -> PMOVES agent key or
# fork/submodule name. Only entries the fleet actually runs or forks belong
# here; extend deliberately, never by guesswork.
EXPLICIT_BRIDGES: dict[str, str] = {
    "spynel": "PMOVES-spynel",
    "kilo": "kilocode_glm",  # Kilo-Org/kilocode — the kilocode_glm harness agent
}


def _load_acp_entries(registry: pathlib.Path) -> list[dict]:
    entries = []
    for child in sorted(registry.iterdir()):
        agent_json = child / "agent.json"
        if not agent_json.is_file():
            continue
        try:
            data = json.loads(agent_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warn: unreadable entry {child.name}: {exc}", file=sys.stderr)
            continue
        data["_acp_id"] = child.name
        entries.append(data)
    return entries


def _registry_commit(registry: pathlib.Path) -> str | None:
    """HEAD of the registry checkout, or None when it is not a git checkout."""
    try:
        out = subprocess.run(
            ["git", "-C", str(registry), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def _repo_basename(url: str) -> str:
    tail = (url or "").rstrip("/").split("/")[-1].lower()
    return tail if len(tail) > 5 else ""


def _match(acp: dict, pmoves: dict[str, dict], fork_repos: dict[str, str]) -> tuple[str, str | None]:
    """Conservative matching ONLY on explicit bridges and exact repo basenames.

    Substring search over agent JSON is forbidden on purpose: it matched
    "harn" inside "harness" and "kilo" inside prose during the first run.
    An entry is linked/forked only when a repo basename matches exactly.
    """
    acp_id = acp["_acp_id"]
    if acp_id in EXPLICIT_BRIDGES:
        target = EXPLICIT_BRIDGES[acp_id]
        return ("linked" if target in pmoves else "forked"), target
    base = _repo_basename(acp.get("repository") or "")
    if not base:
        return "available", None
    for key in pmoves:
        if base == key.lower():
            return "linked", key
    for fork, upstream in fork_repos.items():
        if base == _repo_basename(upstream) or base == fork.lower().lstrip("pmoves-"):
            return "forked", fork
    return "available", None


def build_map(registry: pathlib.Path) -> tuple[dict, dict[str, int]]:
    import yaml

    acp_entries = _load_acp_entries(registry)
    pmoves_registry = yaml.safe_load(
        (REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml").read_text()
    )
    pmoves = pmoves_registry.get("agents") or {}
    if not isinstance(pmoves, dict):
        pmoves = {}
    fork_repos: dict[str, str] = {}
    try:
        fr = json.loads((REPO_ROOT / "pmoves" / "config" / "fork_registry.json").read_text())
        fork_repos = {
            name: (entry or {}).get("upstream", "")
            for name, entry in (fr.get("forks") or {}).items()
        }
    except (OSError, json.JSONDecodeError):
        pass

    mapping: dict[str, dict] = {}
    counts = {"linked": 0, "forked": 0, "available": 0}
    for acp in acp_entries:
        status, target = _match(acp, pmoves, fork_repos)
        counts[status] += 1
        mapping[acp["_acp_id"]] = {
            "name": acp.get("name"),
            "repository": acp.get("repository"),
            "version": acp.get("version"),
            "status": status,
            **({"pmoves": target} if target else {}),
        }
    commit = _registry_commit(registry)
    return {
        **({"registry_commit": commit} if commit else {}),
        "_doc": (
            "ACP registry <-> PMOVES mapping (generated by "
            "pmoves/tools/acp_registry_map.py; do not hand-edit). status: "
            "linked = PMOVES agent references the repo; forked = org fork "
            "exists (see fork_registry.json); available = no PMOVES presence."
        ),
        "acp_entries": mapping,
    }, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0] if __doc__ else "ACP registry mapper")
    ap.add_argument("--registry", type=pathlib.Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write the mapping artifact")
    mode.add_argument("--check", action="store_true",
                      help="exit 1 if the committed artifact differs from a fresh build")
    args = ap.parse_args()

    if not args.registry.is_dir():
        print(
            f"error: ACP registry not found at {args.registry}\n"
            "  run `git submodule update --init PMOVES-registry`, "
            "or pass --registry PATH",
            file=sys.stderr,
        )
        return 2

    artifact, counts = build_map(args.registry)
    total = sum(counts.values())
    if total == 0:
        print(
            f"error: no <id>/agent.json entries under {args.registry} -- an "
            "uninitialized submodule is an empty directory.\n"
            "  run `git submodule update --init PMOVES-registry`; refusing to "
            "emit an empty mapping",
            file=sys.stderr,
        )
        return 2
    print(f"ACP entries scanned: {total}")
    for status, n in counts.items():
        print(f"  {status:10s} {n}")
    linked = [k for k, v in artifact["acp_entries"].items() if v["status"] == "linked"]
    forked = [k for k, v in artifact["acp_entries"].items() if v["status"] == "forked"]
    if linked:
        print("linked:", ", ".join(sorted(linked)))
    if forked:
        print("forked:", ", ".join(sorted(forked)))

    rendered = json.dumps(artifact, indent=2, sort_keys=True) + "\n"
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.is_file() else ""
        if current != rendered:
            print(f"DRIFT: {args.out} differs from a build of {args.registry}; "
                  "run `make -C pmoves acp-registry-map`", file=sys.stderr)
            return 1
        print(f"ok: {args.out} matches the registry")
    elif args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n": on Windows the default would write CRLF, so a
        # regeneration there would rewrite every line of the artifact.
        args.out.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    else:
        print("(read-only; pass --write to update the artifact)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
