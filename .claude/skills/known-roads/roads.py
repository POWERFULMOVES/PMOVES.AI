#!/usr/bin/env python3
"""Answer "what is off limits, and what is the sanctioned route" WITHOUT tripping
the guard to find out.

Everything here is DERIVED at runtime from the two existing sources of truth:

  .claude/hooks/damage-control/known_roads.py   domain predicates, reason
                                                provability, trail recording
  .claude/hooks/damage-control/patterns.yaml    the protected path classes

Nothing is hardcoded and nothing is reimplemented. A domain added to
DOMAIN_PATTERNS, or a path class added to patterns.yaml, shows up here on the
next run -- which is the whole point: a catalog that can go stale would put the
protected set back into the "known unknown" bucket it is meant to empty.

Subcommands:
  domains              every Known Road domain and what it opens
  protected            every protected path class, with counts
  check <path> [...]   is this path protected, and which road opens it
  reason <reason>      is this reason provable (the existing gate decides)
  status               the grant active right now, if any
  trail [n]            the last n roads actually taken (audit log)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".claude" / "hooks" / "damage-control").is_dir():
            return parent
    return Path.cwd()


ROOT = _repo_root()
GUARD_DIR = ROOT / ".claude" / "hooks" / "damage-control"
sys.path.insert(0, str(GUARD_DIR))

try:
    import known_roads as kr
except ImportError as exc:                                  # pragma: no cover
    print(f"cannot import known_roads from {GUARD_DIR}: {exc}", file=sys.stderr)
    raise SystemExit(3)


def _load_patterns() -> dict:
    try:
        import yaml
    except ImportError:
        print("pyyaml not available -- run via `uv run roads.py` or install pyyaml",
              file=sys.stderr)
        raise SystemExit(3)
    path = GUARD_DIR / "patterns.yaml"
    if not path.is_file():
        print(f"patterns.yaml not found at {path}", file=sys.stderr)
        raise SystemExit(3)
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _summary(predicate) -> str:
    doc = (predicate.__doc__ or "").strip().splitlines()
    return doc[0].strip() if doc else "(undocumented)"


def cmd_domains(_args) -> int:
    print("KNOWN ROAD DOMAINS — a provable, recorded bypass exists for each of these.")
    print("Source: known_roads.DOMAIN_PATTERNS\n")
    for domain in sorted(kr.DOMAIN_PATTERNS):
        print(f"  {domain}")
        print(f"      {_summary(kr.DOMAIN_PATTERNS[domain])}")
        print(f"      open with: KNOWN_ROAD={domain}:<reason>")
    print("\nA reason must be provable. See: roads.py reason <reason>")
    print("Every granted bypass appends to known-roads.jsonl; one that cannot be")
    print("recorded is denied (fail-closed).")
    return 0


def cmd_protected(_args) -> int:
    cfg = _load_patterns()
    classes = [
        ("zeroAccessPaths", "no operation at all, reads included; no Known Road"),
        ("readOnlyPaths", "reads fine, any modification refused"),
        ("noDeletePaths", "read/write/edit fine, deletion refused"),
        ("repoScopedPaths", "subset of readOnlyPaths that applies INSIDE this repo only"),
        ("chitSafePaths", "exempt from read-only (CHIT archives and data dirs)"),
        ("bashDeleteAllowlist", "whole-command exceptions to the delete blocks"),
        ("chitBypassPatterns", "CHIT tooling may reach the files it encodes"),
        ("bashToolPatterns", "command-shape rules, independent of any path"),
    ]
    print(f"PROTECTED PATH CLASSES  ({GUARD_DIR / 'patterns.yaml'})\n")
    for key, meaning in classes:
        entries = cfg.get(key) or []
        print(f"  {key:22s} {len(entries):4d}  {meaning}")
    print("\nFull listing of one class:")
    print("  python3 -c \"import yaml,sys;"
          "print('\\n'.join(str(e) for e in yaml.safe_load(open(sys.argv[1]))[sys.argv[2]]))\""
          f" {GUARD_DIR / 'patterns.yaml'} readOnlyPaths")
    print("\nNOTE ON SHAPE: a path class is matched against RESOLVED PATHS by all three")
    print("guards. Prose that merely names a protected path is not a target, and an")
    print("entry listed in repoScopedPaths does not reach identically-named")
    print("directories elsewhere on the host.")
    return 0


def _describe(path: str) -> dict:
    normalized = os.path.normpath(os.path.expanduser(path)).replace("\\", "/")
    if not os.path.isabs(normalized):
        normalized = os.path.normpath(str(ROOT / normalized)).replace("\\", "/")
    hits = [d for d, p in sorted(kr.DOMAIN_PATTERNS.items()) if p(normalized)]
    return {"input": path, "resolved": normalized, "domains": hits}


def cmd_check(args) -> int:
    if not args:
        print("usage: roads.py check <path> [<path> ...]", file=sys.stderr)
        return 2
    cfg = _load_patterns()
    worst = 0
    for path in args:
        info = _describe(path)
        print(f"\n{info['input']}")
        print(f"  resolved: {info['resolved']}")
        classes = []
        for key in ("zeroAccessPaths", "readOnlyPaths", "noDeletePaths"):
            for entry in cfg.get(key) or []:
                if _covers(info["resolved"], entry):
                    classes.append((key, entry))
        if classes:
            for key, entry in classes:
                scope = ""
                if entry in (cfg.get("repoScopedPaths") or []):
                    scope = "  [repo-scoped: applies inside this repo only]"
                print(f"  protected by: {key} <- {entry}{scope}")
        else:
            print("  protected by: nothing in patterns.yaml covers this path")
        if info["domains"]:
            for domain in info["domains"]:
                print(f"  KNOWN ROAD:   KNOWN_ROAD={domain}:<reason>   (domain '{domain}')")
            worst = max(worst, 1)
        elif classes:
            print("  KNOWN ROAD:   none for this path. If the edit is legitimate, the")
            print("                route is a new domain predicate in known_roads.py,")
            print("                agreed with the operator -- not a bypass.")
            worst = max(worst, 1)
    print()
    return 0 if worst == 0 else 0


def _covers(resolved: str, entry: str) -> bool:
    """Reuse the guard's own path matcher so this cannot drift from it."""
    sys.path.insert(0, str(GUARD_DIR))
    import path_scope
    return path_scope.token_matches_entry(resolved, entry)


def cmd_reason(args) -> int:
    if not args:
        print("usage: roads.py reason <reason>   e.g. pr:3011 | issue:42 | handoff:X.md",
              file=sys.stderr)
        return 2
    rc = 0
    for reason in args:
        provable, detail = kr._reason_is_provable(reason)
        if provable:
            print(f"  PROVABLE      {reason}")
        else:
            print(f"  NOT PROVABLE  {reason}\n                {detail}")
            rc = 1
    return rc


def cmd_status(_args) -> int:
    grant = kr._active_grant()
    env = os.environ.get("KNOWN_ROAD", "").strip()
    grant_file = kr._grant_file()
    print(f"KNOWN_ROAD env var : {env or '(unset)'}")
    print(f"file grant         : {grant_file}")
    print(f"                     {'present' if grant_file.is_file() else 'absent'}")
    print(f"active grant       : {grant or '(none)'}")
    if not grant:
        print("\nNo road is open. Domains: " + kr.known_road_domains())
        return 0
    domain, _, reason = grant.partition(":")
    provable, detail = kr._reason_is_provable(reason)
    print(f"  domain  : {domain}"
          f"{'' if domain in kr.DOMAIN_PATTERNS else '   <- NOT a known domain'}")
    print(f"  reason  : {reason}  ->  {'provable' if provable else 'NOT provable: ' + detail}")
    return 0


def cmd_trail(args) -> int:
    limit = int(args[0]) if args else 10
    path = kr._trail_path()
    print("known-roads.jsonl is an AUDIT LOG of roads TAKEN -- not a catalog of what")
    print("is protected. For the catalog use: roads.py domains / roads.py protected.\n")
    if not path.is_file():
        print(f"(no trail yet at {path})")
        return 0
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    print(f"{len(rows)} recorded crossing(s); last {min(limit, len(rows))}:\n")
    for row in rows[-limit:]:
        print(f"  {row.get('ts','?'):20s} {row.get('domain','?'):11s} "
              f"{row.get('tool','?'):6s} {row.get('reason','?'):24s} {row.get('file','?')}")
    by_domain = {}
    for row in rows:
        by_domain[row.get("domain", "?")] = by_domain.get(row.get("domain", "?"), 0) + 1
    print("\n  by domain: " + ", ".join(f"{k}={v}" for k, v in sorted(by_domain.items())))
    return 0


COMMANDS = {
    "domains": cmd_domains,
    "protected": cmd_protected,
    "check": cmd_check,
    "reason": cmd_reason,
    "status": cmd_status,
    "trail": cmd_trail,
}


def main(argv) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    name, rest = argv[0], argv[1:]
    handler = COMMANDS.get(name)
    if handler is None:
        print(f"unknown subcommand {name!r}. one of: {', '.join(COMMANDS)}", file=sys.stderr)
        return 2
    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
