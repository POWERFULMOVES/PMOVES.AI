#!/usr/bin/env python3
"""Validate-dockerfile-paths ratchet.

No-network scan of every `pmoves/docker-compose*.yml` overlay + every
`Dockerfile*` under `pmoves/`. Closes the third pattern from the
operator's #2358 meta-callout:

> "the file the developer touched ≠ the file the runner builds"

Same shape as the other two ratchets (fork-registry, validate-tac,
validate-composes): static analysis, no GitHub API, no token
privilege, ~100ms on the full fleet. Fails (exit 1) on:

  1. BROKEN_BUILD — a compose `build:` stanza points at a Dockerfile
     that doesn't exist on disk. This is the #2358 shape: a PR
     "fixed" the Dockerfile in the wrong file, compose built a stale
     one, the operator didn't notice until bring-up. The ratchet
     catches it at PR time, before any node executes.

  2. ORPHAN_DOCKERFILE — a Dockerfile exists in `pmoves/` but is not
     referenced by any compose `build:`. Most are intentional
     (alternative variants, legacy, base images, side-channel CI
     paths) and live in the baseline. New orphans are caught
     immediately.

The ratchet only goes DOWN over time. The baseline file is committed
and reviewable in PR diffs. Adding to the baseline requires a clear
reason; removing from the baseline is a one-line win that should ship
in a fixup commit.

Usage:
    python3 pmoves/tools/validate_dockerfile_paths.py
    python3 pmoves/tools/validate_dockerfile_paths.py --json
    python3 pmoves/tools/validate_dockerfile_paths.py --list-orphans
    python3 pmoves/tools/validate_dockerfile_paths.py \
        --compose pmoves/docker-compose.yml
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES_DIR = REPO_ROOT / "pmoves"
COMPOSE_GLOB = "docker-compose*.yml"
DOCKERFILE_GLOB = "Dockerfile*"

# Where the operator-acknowledged orphan set lives. The ratchet
# allows anything listed here without complaint; the operator's
# job is to shrink it over time. Format: { "dockerfile/path: reason"
# } so the same file is human-readable AND machine-parseable.
BASELINE_PATH = (
    REPO_ROOT / "pmoves" / "configs" / "dockerfiles" / "_known_orphans.yaml"
)

# Directories under pmoves/ where we look for Dockerfiles. Anything
# outside this set is ignored (docs/, plans/, .git/, node_modules/,
# submodules, etc.). This is a separate allowlist rather than a
# denylist so the ratchet doesn't scan every byte of pmoves/ — the
# 100ms budget is for the real fleet, not for `pmoves/docs/`.
DOCKERFILE_PARENT_DIRS = (
    "services",
    "images",
    "integrations",
    "docker",
    "compose",
    "ui",
)

# We also pick up a top-level `pmoves/Dockerfile` if one exists.
TOP_LEVEL_DOCKERFILE = PMOVES_DIR / "Dockerfile"


def _yaml_safe_load_with_compose_tags(text):
    """Compose uses !override / !reset as merge markers. PyYAML's
    SafeLoader doesn't know about them, so we register no-op
    constructors before loading. Without this, every overlay that
    uses `!override` would fail to parse."""
    import yaml

    def _noop(loader, node):
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node)
        return loader.construct_scalar(node)

    for tag in ("!override", "!reset"):
        yaml.SafeLoader.add_constructor(tag, _noop)
    return yaml.safe_load(text)


def _all_compose_files() -> list[Path]:
    if not PMOVES_DIR.exists():
        return []
    return sorted(PMOVES_DIR.glob(COMPOSE_GLOB))


def _all_dockerfile_paths() -> list[Path]:
    """Walk the allowlist dirs + the top-level `pmoves/Dockerfile`.
    Returns paths relative to REPO_ROOT for stable output."""
    out: list[Path] = []
    for parent in DOCKERFILE_PARENT_DIRS:
        d = PMOVES_DIR / parent
        if not d.exists():
            continue
        for p in d.rglob(DOCKERFILE_GLOB):
            if not p.is_file():
                continue
            out.append(p)
    if TOP_LEVEL_DOCKERFILE.exists() and TOP_LEVEL_DOCKERFILE.is_file():
        out.append(TOP_LEVEL_DOCKERFILE)
    return sorted(out)


def _is_in_scope_build_target(abs_path: Path) -> bool:
    """Decide if a compose build target is in-scope for the ratchet.

    IN scope (will be checked + flagged if missing):
      - paths under pmoves/{services,images,integrations,docker,compose,ui}/
      - the top-level pmoves/Dockerfile

    OUT of scope (skipped):
      - paths under pmoves/vendor/  (external repos, brought in
        via `make submodules` or manual clone at bring-up)
      - paths under CATACLYSM_STUDIOS_INC / provisions
        (operator-side workspace, gitignored or sibling clone)
      - paths into sibling submodules (PMOVES-Archon, PMOVES.YT,
        Pmoves-cipher, PMOVES-transcribe-and-fetch,
        PMOVES-llama-throughput-lab, PMOVES-n8n, PMOVES-ToKenism-Multi,
        etc.) — these don't have their Dockerfiles in this repo at
        all, so the ratchet can't statically check them
      - any ${VAR} that resolves to a non-pmoves/ path

    The ratchet only flags in-scope broken builds. Out-of-scope
    paths are the operator's responsibility to keep synced; we just
    don't pretend to know whether they're correct.
    """
    if not abs_path.is_absolute():
        abs_path = (REPO_ROOT / abs_path).resolve()
    try:
        rel = abs_path.relative_to(REPO_ROOT)
    except ValueError:
        return False
    parts = rel.parts
    if not parts or parts[0] != "pmoves":
        return False
    if len(parts) < 2:
        return False
    # pmoves/ subdirs we DON'T scan: vendor/, CATACLYSM_STUDIOS_INC/
    # (under the operator's home), and any other sibling repo
    # referenced as a submodule/provisions workspace.
    if parts[1] in {"vendor"}:
        return False
    if "provisions" in parts:
        return False
    # Sibling-submodule patterns: PMOVES-Archon, PMOVES.YT, etc.
    # We only scan under pmoves/{services,images,integrations,docker,compose,ui}.
    if parts[1] in DOCKERFILE_PARENT_DIRS:
        return True
    if len(parts) == 2 and parts[1] == "Dockerfile":
        return True
    return False


def _load_baseline() -> set[str]:
    """Read the operator-acknowledged orphan set.

    The baseline file is a YAML mapping {path: reason}. The KEYS are
    the orphan paths (relative to repo root); the VALUES are the
    operator's reason for keeping this file orphaned. Anything not
    in the baseline AND not referenced by any compose is a ratchet
    failure.

    If the file is missing or malformed, the ratchet behaves as if
    the baseline is empty (fail-closed) — operators have to commit
    the baseline for the ratchet to know which orphans are
    intentional. This is the same shape as validate_tac.
    """
    if not BASELINE_PATH.exists():
        return set()
    import yaml
    try:
        with BASELINE_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return set()
    if not data:
        return set()
    if isinstance(data, dict):
        return {str(k) for k in data.keys()}
    if isinstance(data, list):
        return {str(x) for x in data if x}
    return set()


def _resolve_build_target(
    compose_file: Path,
    service: str,
    build_field,
) -> tuple[Path, str] | None:
    """Resolve a `build:` stanza into a (path, context) tuple.

    `build:` can be:
      - a string: shorthand for { context: <string> }
      - a mapping: { context: ./foo, dockerfile: Dockerfile.bar }
      - null: skip (use prebuilt `image:` instead)

    Default `dockerfile` is `Dockerfile` (relative to context).
    Default `context` is `.` (relative to the compose file's
    directory, which is `pmoves/` for every overlay in this repo).

    Env-var defaults of the form `${VAR:-default}` are resolved to
    their default value (the ratchet can't actually evaluate the
    env at scan time, but the default is what compose would use
    when the env var is unset, which is the most common case).

    Returns the resolved path (absolute) + the context string for
    diagnostics, or None if the service isn't a `build:` service.
    """
    if build_field is None:
        return None
    if isinstance(build_field, str):
        context = _resolve_env_default(build_field)
        dockerfile = "Dockerfile"
    elif isinstance(build_field, dict):
        context = _resolve_env_default(build_field.get("context", "."))
        dockerfile = _resolve_env_default(build_field.get("dockerfile", "Dockerfile"))
    else:
        return None

    # `context` is relative to the compose file's directory, which is
    # always `pmoves/` in this repo. If someone ever adds a compose
    # at a different depth we'll need to walk up; today every overlay
    # sits directly in `pmoves/`.
    compose_dir = compose_file.parent
    context_path = (compose_dir / context).resolve()
    dockerfile_path = (context_path / dockerfile).resolve()
    return dockerfile_path, context


# Env-var default pattern: ${VAR} or ${VAR:-default}. The ratchet
# substitutes the default (or the literal `default` for ${VAR:-default}
# form). Patterns that are more exotic (${VAR-default} with no colon,
# nested expansions) are out of scope — the ratchet keeps the literal
# string and the path check will fall through, but most real PMOVES
# compose uses the canonical ${VAR:-default} form.
_ENV_DEFAULT_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?-)?([^}]*)\}")


def _resolve_env_default(value: str) -> str:
    """Substitute `${VAR:-default}` (and `${VAR}`) with the default
    value. If the variable has no default, the literal `${VAR}` is
    preserved so the ratchet can still surface a finding (the
    dockerfile path won't exist on disk)."""
    def _sub(m: re.Match) -> str:
        var_name = m.group(1)
        default = m.group(2)
        # ${VAR} with no default: keep the literal so the ratchet
        # can surface the unresolved reference.
        if default is None:
            return m.group(0)
        return default
    return _ENV_DEFAULT_RE.sub(_sub, value)


def _scan_compose_for_builds(compose_file: Path) -> list[dict]:
    """Return the list of (service, dockerfile_path) for every
    service with a `build:` stanza. Path is absolute; the caller's
    job to make it repo-relative for output."""
    try:
        with compose_file.open(encoding="utf-8") as fh:
            data = _yaml_safe_load_with_compose_tags(fh)
    except Exception as e:
        return [{
            "kind": "parse-error",
            "file": str(compose_file.relative_to(REPO_ROOT)),
            "service": "<root>",
            "detail": f"could not parse YAML: {e}",
        }]
    if not isinstance(data, dict):
        return []
    services = data.get("services") or {}
    if not isinstance(services, dict):
        return []
    out: list[dict] = []
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        build = svc.get("build")
        if build is None:
            # prebuilt `image:` service; no build target to validate
            continue
        resolved = _resolve_build_target(compose_file, svc_name, build)
        if resolved is None:
            continue
        dockerfile_abs, context = resolved
        out.append({
            "compose_file": str(compose_file.relative_to(REPO_ROOT)),
            "service": str(svc_name),
            "dockerfile_abs": dockerfile_abs,
            "dockerfile_rel": _try_relative(dockerfile_abs),
            "context": context,
        })
    return out


def _try_relative(path: Path) -> str:
    """Best-effort conversion to repo-relative path. Falls back to
    the absolute path if the file is outside the repo (shouldn't
    happen, but defensive against hand-crafted compose contexts).
    Always uses forward slashes so the path matches the baseline
    YAML keys (which also use forward slashes per YAML convention)."""
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return str(path).replace("\\", "/")
    # pathlib returns PosixPath on Linux (forward slashes) and
    # WindowsPath on Windows (backslashes); as_posix() normalizes
    # both cases to forward slashes.
    return rel.as_posix()


def _scan_one_compose(path: Path) -> list[dict]:
    """Scan a single compose file, returning build-target findings
    as a list of (compose_file, service, dockerfile_rel) tuples +
    any parse errors."""
    return _scan_compose_for_builds(path)


def _summary(by_kind: dict[str, int]) -> str:
    if not by_kind:
        return "no findings"
    parts = ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items()))
    return parts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list-orphans",
        action="store_true",
        help="only list orphan Dockerfiles (Dockerfiles not referenced by any compose, not in baseline); don't fail",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    parser.add_argument(
        "--compose",
        type=Path,
        help="scan a single compose file (test-only path; for CI use the default glob)",
    )
    parser.add_argument(
        "--baseline-add",
        type=str,
        default=None,
        help=(
            "add a single dockerfile path (relative to repo root) to "
            "the baseline file with a default reason; creates the "
            "baseline dir if missing. This is a convenience for "
            "the initial seed; once the baseline exists, edit it "
            "by hand so the reason is meaningful."
        ),
    )
    args = parser.parse_args()

    # baseline-add convenience path: write a single key then exit
    if args.baseline_add:
        return _baseline_add(args.baseline_add)

    compose_files = [args.compose] if args.compose else _all_compose_files()
    dockerfiles = _all_dockerfile_paths()
    baseline = _load_baseline()

    # Build a (compose_file, service) -> dockerfile_rel map and a
    # set of referenced dockerfile paths (repo-relative).
    compose_findings: list[dict] = []
    referenced: set[str] = set()
    for cf in compose_files:
        if not cf.exists():
            continue
        compose_findings.extend(_scan_one_compose(cf))
    for f in compose_findings:
        if "dockerfile_rel" in f:
            referenced.add(f["dockerfile_rel"])

    # BROKEN_BUILD: a compose build target that doesn't exist on disk
    # AND is in-scope for the ratchet (not a sibling submodule / vendor /
    # provisions path — those are external repos the ratchet can't
    # statically check).
    broken: list[dict] = []
    for f in compose_findings:
        if f.get("kind") == "parse-error":
            broken.append(f)
            continue
        rel = f.get("dockerfile_rel", "")
        if not rel:
            continue
        abs_p = REPO_ROOT / rel
        if abs_p.exists():
            continue
        if not _is_in_scope_build_target(abs_p):
            # Sibling submodule / vendor / provisions — out of scope.
            # The ratchet is not the right place to fail on those;
            # the operator keeps them synced via `make submodules`.
            continue
        broken.append({
            "kind": "broken-build",
            "file": f["compose_file"],
            "service": f["service"],
            "dockerfile": rel,
            "context": f["context"],
            "detail": (
                f"compose build points at {rel} but no such file exists. "
                f"Check the service's `build.context` and `build.dockerfile` "
                f"in {f['compose_file']} — a stale or renamed Dockerfile "
                f"will silently build the wrong image."
            ),
        })

    # ORPHAN_DOCKERFILE: a Dockerfile in the repo that no compose
    # references AND isn't in the baseline
    orphan_set: set[str] = set()
    for d in dockerfiles:
        rel = _try_relative(d)
        if rel in referenced:
            continue
        if rel in baseline:
            continue
        orphan_set.add(rel)

    orphan_list = sorted(orphan_set)
    if args.list_orphans:
        # listing path: emit orphans + baseline + always exit 0 so
        # operators can grep / pipe the result.
        out = {
            "orphans_not_in_baseline": orphan_list,
            "baseline_count": len(baseline),
            "referenced_count": len(referenced),
            "total_dockerfiles": len(dockerfiles),
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"# orphans not in baseline: {len(orphan_list)}")
            for o in orphan_list:
                print(f"  {o}")
            print(f"# baseline size: {len(baseline)}")
            print(f"# referenced by compose: {len(referenced)}")
            print(f"# total dockerfiles: {len(dockerfiles)}")
        return 0

    problems: list[dict] = list(broken)
    for o in orphan_list:
        problems.append({
            "kind": "orphan-dockerfile",
            "file": o,
            "service": None,
            "dockerfile": o,
            "context": None,
            "detail": (
                f"{o} is not referenced by any compose build target. "
                f"Either wire it into a compose service's `build.dockerfile`, "
                f"or add it to pmoves/configs/dockerfiles/_known_orphans.yaml "
                f"with a reason for keeping it orphaned."
            ),
        })

    by_kind: dict[str, int] = {}
    for p in problems:
        by_kind[p["kind"]] = by_kind.get(p["kind"], 0) + 1

    if args.json:
        print(json.dumps({
            "ok": not problems,
            "problems": problems,
            "summary": by_kind,
            "baseline_count": len(baseline),
            "referenced_count": len(referenced),
            "total_dockerfiles": len(dockerfiles),
        }, indent=2))
    else:
        if not problems:
            print(f"validate-dockerfile-paths: OK ({len(dockerfiles)} dockerfiles, {len(referenced)} referenced, {len(baseline)} baseline)")
            return 0
        print(f"validate-dockerfile-paths: FAIL ({_summary(by_kind)})", file=sys.stderr)
        for p in problems:
            where = p.get("file", "?")
            svc = p.get("service") or "-"
            df = p.get("dockerfile", "?")
            print(f"  - [{p['kind']}] {where} (service={svc}) {df}", file=sys.stderr)
            if p.get("detail"):
                print(f"      {p['detail']}", file=sys.stderr)

    # JSON mode also returns the right exit code so the test
    # suite (and CI) can assert on it. (Non-JSON mode returns
    # from inside the `else` branch above; this return is for
    # the JSON path.)
    return 0 if not problems else 1


def _baseline_add(rel_path: str) -> int:
    """Convenience path: add a single key to the baseline file. Only
    used during the initial seed; once the baseline is shaped, edit
    it by hand so the reason is meaningful."""
    if not rel_path.startswith("pmoves/"):
        print(f"--baseline-add expects a path relative to repo root starting with pmoves/; got {rel_path!r}", file=sys.stderr)
        return 2
    if not (REPO_ROOT / rel_path).exists():
        print(f"path {rel_path!r} does not exist in repo", file=sys.stderr)
        return 2
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    if BASELINE_PATH.exists():
        with BASELINE_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    else:
        data = {}
    if not isinstance(data, dict):
        print(f"baseline file is malformed (not a mapping); fix by hand: {BASELINE_PATH}", file=sys.stderr)
        return 2
    if rel_path in data:
        print(f"{rel_path} already in baseline", file=sys.stderr)
        return 0
    data[rel_path] = "seed: orphan at initial baseline creation; replace reason when wired up or removed"
    with BASELINE_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            data,
            fh,
            sort_keys=True,
            default_flow_style=False,
            allow_unicode=True,
        )
    print(f"added {rel_path} to {BASELINE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
