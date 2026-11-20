#!/usr/bin/env python3
"""Overlay real secrets from local.env into env.shared for empty/placeholder keys.

The GitHub Actions ``sync-secrets-local.yml`` workflow writes real API keys to
``$APPDATA/pmoves/secrets/local.env`` (Windows) or
``$XDG_CONFIG_HOME/pmoves/secrets/local.env`` (Unix).  This script merges those
values into ``env.shared`` **only** for keys that are currently empty or contain
placeholder values, preserving any values already set.

Intended to run **before** ``chit-export`` so the CHIT bundle contains real
credentials that flow through the rest of the secrets-funnel pipeline.

``--keys K1,K2`` restricts the run to an allowlist of key names, with or without
``--force``. That is how ONE rotated GitHub secret is pushed over its stale
local value without force-overwriting node-specific keys (SUPABASE_* and the
like) that this node pairs with its running services::

    make -C pmoves secrets-local-hydrate FORCE=1 KEYS=GH_APP_SEC
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Sequence

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools._secrets_common import (
    PROJECT_ROOT,
    is_placeholder,
    local_env_path as _default_local_env,
    parse_env_file as _parse_env,
    validate_secret_value,
)

# Single source of truth for the tombstone list — imported rather than
# reimplemented, so the writer (--clear) and the reader (hydrate) can never
# drift apart on the file's format.
from pmoves.scripts.bootstrap_env import (
    DEFAULT_REGISTRY_PATH,
    load_registry,
    pinned_variables,
    read_cleared_keys,
)


def _pinned_keys(registry_path: Path | None = None) -> set:
    """Registry keys whose value is fixed (the CA host-leak guards).

    Hydrate must never overlay them -- not even under force: env-shared-repair
    empties them as the funnel's first step, and an empty value is a
    placeholder here, so without this the very next step put a stale local.env
    value straight back (Codex/Kilo #3459).
    """
    return {v["key"] for v in pinned_variables(load_registry(registry_path or DEFAULT_REGISTRY_PATH))}

DEFAULT_ENV_SHARED = PROJECT_ROOT / "env.shared"


def _masked(value: str) -> str:
    if len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _invalid_keys(updates: Dict[str, str]) -> List[str]:
    """Names of values validate_secret_value rejects (they will NOT be written)."""
    return sorted(k for k, v in updates.items() if not validate_secret_value(k, v)[0])


def _write_updates(env_path: Path, updates: Dict[str, str]) -> List[str]:
    """Write updated values back into the env file, preserving structure.

    Returns the NAMES it skipped because validation failed. A skipped key was
    not written, and callers must not report it as hydrated.
    """
    lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    # Build index of key -> line number
    index: Dict[str, int] = {}
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        index[key] = idx

    validated_updates = {}
    skipped: List[str] = []
    for key, value in updates.items():
        # Validate each value before writing
        is_valid, error = validate_secret_value(key, value)
        if not is_valid:
            # Log only key name (CodeQL safe: no value taint, no error message)
            print(f"WARNING: Skipping malformed secret '{key}' (validation failed)", file=sys.stderr)
            skipped.append(key)
            continue
        validated_updates[key] = value

    for key, value in validated_updates.items():
        entry = f"{key}={value}"
        if key in index:
            lines[index[key]] = entry
        else:
            lines.append(entry)

    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    env_path.write_text(text, encoding="utf-8")
    return sorted(skipped)


class HydrateResult(NamedTuple):
    """written: keys that were (or, under dry_run, would be) written.
    skipped: keys selected for overlay whose value FAILED validation -- never
    written, never to be reported as hydrated."""

    written: Dict[str, str]
    skipped: List[str]


def hydrate(
    local_env_path: Path,
    env_shared_path: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    cleared_keys_path: Path | None = None,
    registry_path: Path | None = None,
    keys: Iterable[str] | None = None,
) -> Dict[str, str]:
    """Overlay local.env values into env.shared; returns the keys WRITTEN.

    Thin wrapper over :func:`hydrate_with_report`, which also returns the keys
    skipped for failing validation.
    """
    return hydrate_with_report(
        local_env_path,
        env_shared_path,
        dry_run=dry_run,
        force=force,
        cleared_keys_path=cleared_keys_path,
        registry_path=registry_path,
        keys=keys,
    ).written


def hydrate_with_report(
    local_env_path: Path,
    env_shared_path: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    cleared_keys_path: Path | None = None,
    registry_path: Path | None = None,
    keys: Iterable[str] | None = None,
) -> HydrateResult:
    """Overlay local.env values into env.shared for empty/placeholder keys.

    When force=True, overwrites ALL matching keys in env.shared with values
    from local.env, even if the current value is non-placeholder. This is
    needed when GH Secrets are rotated and the stale local value must be
    replaced.

    Keys listed in pmoves/configs/secrets_cleared.yaml are NEVER overlaid, not
    even under force. They were emptied deliberately via
    ``bootstrap_env.py --clear``, and the empty string is the first entry in
    PLACEHOLDER_VALUES — so without that list a deliberately-empty key is
    indistinguishable from a never-set one, and this function would restore the
    stale local value on the next `secrets-funnel` run, silently undoing the
    clear. force= exists to push a rotated GH Secret over a stale local value,
    which is a different intent from "this key is supposed to be empty".

    Registry-PINNED keys (bootstrap/registry.json ``"pinned": true``) are never
    overlaid either, for the same reason -- see ``_pinned_keys``.

    ``keys`` is an allowlist: when given, every key outside it is ignored, with
    or without force. It narrows; it never widens -- a cleared or pinned key
    named in ``keys`` is still skipped. ``keys=None`` means "all keys" (the
    pre-existing behaviour); an empty iterable means "no keys".

    A key whose local value already equals its env.shared value is not
    reported: under force it would be a no-op write, and the return value is
    the set of keys that would actually change.
    """
    local_values = _parse_env(local_env_path)
    shared_values = _parse_env(env_shared_path)
    cleared = set(read_cleared_keys(cleared_keys_path))
    pinned = _pinned_keys(registry_path)
    allow = None if keys is None else set(keys)

    updates: Dict[str, str] = {}
    for key, local_val in sorted(local_values.items()):
        if allow is not None and key not in allow:
            continue  # Outside the --keys allowlist
        if key in cleared:
            continue  # Deliberately empty — see secrets_cleared.yaml
        if key in pinned:
            continue  # Fixed by the registry — see _pinned_keys
        if is_placeholder(local_val):
            continue  # Don't overlay empty local values
        current = shared_values.get(key, "")
        if local_val == current:
            continue  # Already current -- nothing would change
        if force or is_placeholder(current):
            updates[key] = local_val

    # Validate BEFORE writing so a dry run reports the same skips a real run
    # would make. _write_updates re-validates (defence in depth) and its own
    # skip list is unioned in.
    skipped = set(_invalid_keys(updates))
    if updates and not dry_run:
        skipped |= set(_write_updates(env_shared_path, updates))
    written = {k: v for k, v in updates.items() if k not in skipped}
    return HydrateResult(written, sorted(skipped))


def _parse_keys_arg(raw: str) -> List[str]:
    """``"A, B,,C"`` -> ``["A", "B", "C"]`` (order kept, duplicates dropped)."""
    seen: List[str] = []
    for part in raw.split(","):
        name = part.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def _report_keys_scope(requested: List[str], local_env: Path) -> bool:
    """Explain the --keys scope on stderr (NAMES only). False = nothing usable.

    Returns False when none of the requested keys has a real value in
    local.env, which the caller turns into a nonzero exit: a scoped run that
    can touch nothing is almost certainly a typo or a missing delivery.
    """
    local_values = _parse_env(local_env)
    cleared = set(read_cleared_keys())
    pinned = _pinned_keys()

    absent = [k for k in requested if is_placeholder(local_values.get(k))]
    present = [k for k in requested if k not in absent]
    print(f"--keys scope: {', '.join(requested)}", file=sys.stderr)
    if absent:
        print(
            f"WARNING: --keys requested with no real value in {local_env}: {', '.join(absent)}",
            file=sys.stderr,
        )
    for key in requested:
        if key in cleared:
            print(
                f"NOTE: {key} is listed in secrets_cleared.yaml -- never overlaid, "
                "even when named in --keys",
                file=sys.stderr,
            )
        elif key in pinned:
            print(
                f"NOTE: {key} is registry-PINNED -- never overlaid, even when named in --keys",
                file=sys.stderr,
            )
    if not present:
        print(
            f"ERROR: none of the --keys requested exist in {local_env}; nothing to hydrate",
            file=sys.stderr,
        )
        return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local-env",
        type=Path,
        default=None,
        help="Path to local.env (default: platform-appropriate APPDATA/XDG path)",
    )
    parser.add_argument(
        "--env-shared",
        type=Path,
        default=DEFAULT_ENV_SHARED,
        help="Path to env.shared (default: pmoves/env.shared)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing non-placeholder values (use after rotating GH Secrets)",
    )
    parser.add_argument(
        "--keys",
        default=None,
        metavar="K1,K2",
        help=(
            "Comma-separated allowlist: only these keys are considered (with or "
            "without --force). Cleared and registry-pinned keys are still never "
            "overlaid. Exits 1 if none of them exist in local.env."
        ),
    )
    args = parser.parse_args(argv)

    requested: List[str] | None = None
    if args.keys is not None:
        requested = _parse_keys_arg(args.keys)
        if not requested:
            # An empty allowlist must never fall back to "all keys" -- that is
            # the exact clobber --keys exists to prevent.
            parser.error("--keys was given but names no keys")

    local_env = args.local_env or _default_local_env()
    env_shared = args.env_shared.expanduser().resolve()

    if not local_env.exists():
        if requested is not None:
            # A scoped run is an explicit rotation ask. Reporting success when
            # the source file is absent would claim a delivery that never
            # happened (the same fake-success shape as a validation skip).
            print(
                f"ERROR: --keys requested but {local_env} does not exist; "
                "no requested credential was delivered",
                file=sys.stderr,
            )
            return 1
        print(f"ℹ local.env not found at {local_env} — skipping hydration")
        print("  (Optional: run sync-secrets-local.yml workflow or provide --local-env path)")
        return 0

    if not env_shared.exists():
        print(f"⚠ env.shared not found at {env_shared}")
        return 1

    if requested is not None and not _report_keys_scope(requested, local_env):
        return 1

    prefix = "[dry-run] " if args.dry_run else ""
    if args.force:
        prefix = "[force] " + prefix
    result = hydrate_with_report(
        local_env, env_shared, dry_run=args.dry_run, force=args.force, keys=requested
    )
    updates, skipped = result.written, result.skipped

    rc = 0
    if skipped:
        verb = "would NOT be hydrated" if args.dry_run else "NOT hydrated"
        print(
            f"ERROR: {len(skipped)} key(s) {verb} (failed validation): {', '.join(skipped)}",
            file=sys.stderr,
        )
        print(f"{prefix}NOT hydrated (failed validation): {', '.join(skipped)}")
        # A forced or explicitly-scoped overwrite that silently does nothing is
        # the defect: the operator asked for THIS key and did not get it.
        if args.force or requested is not None:
            rc = 1

    if not updates and skipped:
        return rc

    if not updates:
        if args.force:
            local_values = _parse_env(local_env)
            if not local_values:
                print(f"WARNING: --force specified but {local_env} contains no keys", file=sys.stderr)
            else:
                real_count = sum(1 for v in local_values.values() if not is_placeholder(v))
                if real_count == 0:
                    print(f"WARNING: --force specified but all {len(local_values)} keys in {local_env} are placeholders", file=sys.stderr)
        print("No keys needed hydration — env.shared already has real values.")
        return 0

    if args.dry_run:
        # Names only: a dry run is for deciding, and a masked fragment is still
        # part of the secret.
        print(f"{prefix}Would hydrate {len(updates)} keys from {local_env} -> {env_shared}:")
        for key in sorted(updates):
            print(f"  {key}")
        return rc

    print(f"{prefix}Hydrated {len(updates)} keys from {local_env} -> {env_shared}:")
    for key in sorted(updates):
        print(f"  {key}={_masked(updates[key])}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
