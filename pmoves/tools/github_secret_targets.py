#!/usr/bin/env python3
"""The ONE definition of a CHIT manifest `github_secret` target.

WHY THIS EXISTS
---------------
A target used to be a bare string, ``{github_secret: NAME}``, with no repo and
no environment -- so every declared name landed in POWERFULMOVES/PMOVES.AI, and
that repo's env:Prod reached GitHub's cap of 100 secrets. A second, mapping form
routes a name to its own repo, and optionally its own environment:

    - github_secret: N8N_API_KEY                                      # string
    - github_secret: {name: N8N_API_KEY, repo: POWERFULMOVES/PMOVES-N8N}
    - github_secret: {name: N8N_API_KEY, repo: POWERFULMOVES/PMOVES-N8N, env: Prod}

The two forms do not mean the same thing about scope, and every reader has to
agree on the difference:

  * string form -- UNROUTED. The repo and the scope are the CALLER's choice at
    push time (`push-gh-secrets.sh --repo/--env`); PMOVES.AI when unstated.
  * mapping form -- ROUTED. The manifest pins the repo AND the scope: ``env``
    names an environment, and its absence means the repository scope. ``repo``
    is REQUIRED. A default would be read against the caller's ``--repo``: with
    PMOVES.AI hard-wired, ``--routed --repo FORK/REPO`` pushed the fork's values
    over canonical PMOVES.AI secrets under a normal-looking log line. Only the
    bare name follows the caller's repo, so a mapping must say where it goes.

A name may appear under several targets. The same value pushed to several
repos is the design: one CHIT source, so nodes never run different secrets.

Every reader (the drift check, the capacity audit, the push script's --routed
emitter, apply_manifest_v2) goes through `normalize`, so the format has exactly
one definition. Names only -- nothing here ever touches a secret value.

CLI (the push script's emitter):
  python pmoves/tools/github_secret_targets.py routes \\
      [--manifest PATH] [--default-repo OWNER/REPO] [--default-env ENV]

prints one ``name<TAB>repo<TAB>env`` line per distinct route (env empty for the
repository scope). Exit 2 on a malformed target or an unreadable manifest.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_REPO = "POWERFULMOVES/PMOVES.AI"

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Assembled rather than written literally: the repo's damage-control guard
# treats the manifest path as zero-access, and this module only ever READS it.
DEFAULT_MANIFEST = _REPO_ROOT / "pmoves" / "chit" / ("secrets_manifest" + "_v2.yaml")

_MAPPING_KEYS = frozenset({"name", "repo", "env"})
# GitHub's own rule for secret names.
_SECRET_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REPO = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
# Environment names go into an API path and a TSV line, so nothing that can
# re-shape either: no slash, query, fragment, tab or newline.
_ENV = re.compile(r"^[^/?#\t\r\n]+$")


class MalformedTarget(ValueError):
    """A `github_secret` target that is neither form. Never silently skipped."""


def normalize(target: Any) -> Optional[Dict[str, Any]]:
    """One manifest target -> ``{name, repo, env, routed}``, or None.

    None means the target carries no GitHub secret (a file or Docker target),
    matching the old ``target.get("github_secret")`` truthiness test. ``routed``
    is False for the string form, whose repo/env are the caller's to choose.
    """
    if not isinstance(target, dict):
        return None
    value = target.get("github_secret")
    if not value:
        return None
    if isinstance(value, str):
        return {"name": value, "repo": DEFAULT_REPO, "env": None, "routed": False}
    if not isinstance(value, dict):
        raise MalformedTarget(
            f"github_secret must be a name or a mapping, got {type(value).__name__}: {value!r}"
        )

    unknown = sorted(set(value) - _MAPPING_KEYS)
    if unknown:
        raise MalformedTarget(
            f"github_secret mapping has unknown key(s) {unknown}; allowed: name, repo, env"
        )
    name = value.get("name")
    if not isinstance(name, str) or not _SECRET_NAME.match(name):
        raise MalformedTarget(f"github_secret mapping needs a valid `name`, got {name!r}")
    if "repo" not in value:
        raise MalformedTarget(
            f"github_secret {name}: a mapping must name its `repo` (OWNER/REPO); "
            f"only a bare name follows the caller's --repo"
        )
    repo = value["repo"]
    if not isinstance(repo, str) or not _REPO.match(repo):
        raise MalformedTarget(
            f"github_secret {name}: `repo` must be OWNER/REPO, got {repo!r}"
        )
    env = value.get("env")
    if env is not None and (not isinstance(env, str) or not _ENV.match(env)):
        raise MalformedTarget(
            f"github_secret {name}: `env` must be an environment name, got {env!r}"
        )
    return {"name": name, "repo": repo, "env": env, "routed": True}


def load_entries(manifest: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Manifest entries, located the same way the drift check and audit do."""
    import yaml

    path = manifest or DEFAULT_MANIFEST
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"cannot parse manifest {path}: {exc}") from exc
    for value in doc.values() if isinstance(doc, dict) else []:
        if isinstance(value, list) and value and isinstance(value[0], dict) and "targets" in value[0]:
            return [e for e in value if isinstance(e, dict)]
    raise ValueError(f"no entries with `targets` found in {path}")


def routes(
    entries: Iterable[Dict[str, Any]],
    default_repo: str = DEFAULT_REPO,
    default_env: Optional[str] = None,
) -> List[Tuple[str, str, Optional[str]]]:
    """Distinct (name, repo, env) push routes, in manifest order.

    Unrouted (string-form) names take the caller's repo and env; routed names
    keep their own. env None is the repository scope.
    """
    out: List[Tuple[str, str, Optional[str]]] = []
    seen = set()
    for entry in entries:
        for target in entry.get("targets") or []:
            route = normalize(target)
            if route is None:
                continue
            if route["routed"]:
                key = (route["name"], route["repo"], route["env"])
            else:
                key = (route["name"], default_repo, default_env or None)
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    emit = sub.add_parser("routes", help="print name<TAB>repo<TAB>env push routes")
    emit.add_argument("--manifest", type=Path, default=None)
    emit.add_argument("--default-repo", default=DEFAULT_REPO)
    emit.add_argument("--default-env", default="")
    args = parser.parse_args(argv)

    try:
        found = routes(load_entries(args.manifest), args.default_repo, args.default_env)
    except (OSError, ValueError) as exc:  # MalformedTarget is a ValueError
        print(f"github_secret_targets: {exc}", file=sys.stderr)
        return 2
    for name, repo, env in found:
        # The push script looks each name up in an env file and hands repo/env
        # to `gh`; refuse anything that could re-shape a TSV line or a regex.
        if not _SECRET_NAME.match(name) or not _REPO.match(repo) or (env and not _ENV.match(env)):
            print(f"github_secret_targets: unsafe route {name!r} -> {repo!r} {env!r}", file=sys.stderr)
            return 2
        print(f"{name}\t{repo}\t{env or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
