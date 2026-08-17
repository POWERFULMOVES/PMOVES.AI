#!/usr/bin/env python3
"""Materialize local.env from a CHIT CGP bundle (runnerless funnel gap fix).

On a runnerless node (5090, Z890) Pattern B pulls the CI CHIT bundle and
``secrets_sync.py`` materializes the *tier* env files from it — but nothing
regenerates the user-scoped ``local.env`` that ``secrets_local_hydrate`` reads
to overlay real values into ``env.shared``. So env.shared silently keeps the
stale value while the tier files carry the fresh one (the Hostinger key gap,
2026-08-14: bundle+tiers had fp 82fbcc, env.shared kept fp e81182).

This tool decodes the bundle and writes its secrets into ``local.env`` — exactly
what the ``sync-secrets-local.yml`` GitHub Actions workflow does on a *runner*,
reproduced locally. Wire it into ``secrets-funnel-from-prod`` so a runnerless
funnel refreshes local.env, then a (forced) ``secrets-local-hydrate`` lands the
fresh values in env.shared. That makes "ready after funnel" hold for env.shared
too, not just the tier files.

The emitted keys match ``env.shared`` key names (a CGP point's ``label`` *is* the
env-var name), so ``secrets_local_hydrate`` overlays them 1:1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.chit.codec import decode_secret_map, load_cgp
from pmoves.tools._secrets_common import (
    is_placeholder,
    local_env_path as _default_local_env,
    validate_secret_value,
)


def _masked(value: str) -> str:
    if len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _valid_env_key(key: str) -> bool:
    """Match ``_secrets_common.parse_env_file``'s key contract exactly.

    A local.env key that the hydrate parser would reject (lowercase, non-alnum)
    is pointless to emit — it would never be read back. Mirror that contract here
    so emit and hydrate agree on what a valid key is.
    """
    return bool(key) and key.isupper() and key.replace("_", "").isalnum()


def select_emittable(secrets: Mapping[str, str]) -> tuple[Dict[str, str], List[str]]:
    """Filter a decoded secret map to values safe for a line-based env file.

    Drops: placeholder/empty values (never overlay a blank over a real key),
    invalid env keys, and values that fail ``validate_secret_value`` (multi-line
    PEM/SSH keys, base64-concat corruption, Docker-Compose-hostile ``+``).
    """
    emit: Dict[str, str] = {}
    skipped: List[str] = []
    for key, value in secrets.items():
        if not _valid_env_key(key):
            skipped.append(key)
            continue
        if is_placeholder(value):
            skipped.append(key)
            continue
        ok, _ = validate_secret_value(key, value)
        if not ok:
            skipped.append(key)
            continue
        emit[key] = value
    return emit, skipped


def _write_merged(local_env: Path, emit: Mapping[str, str]) -> None:
    """Merge ``emit`` into local.env, preserving existing keys/comments/order.

    Merge (not overwrite) so a key present locally but absent from *this* bundle
    (e.g. a GH secret that was empty at bundle-build time) is not silently lost.
    Structure-preserving in-place update mirrors ``secrets_local_hydrate._write_updates``.
    """
    if local_env.exists():
        lines = local_env.read_text(encoding="utf-8", errors="ignore").splitlines()
    else:
        local_env.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Auto-generated from the CHIT bundle by pmoves.tools.emit_local_env"]

    index: Dict[str, int] = {}
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        index[stripped.split("=", 1)[0].strip()] = idx

    for key, value in emit.items():
        entry = f"{key}={value}"
        if key in index:
            lines[index[key]] = entry
        else:
            lines.append(entry)

    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    local_env.write_text(text, encoding="utf-8")


def emit(cgp_path: Path, local_env: Path, *, dry_run: bool = False) -> Dict[str, str]:
    """Decode ``cgp_path`` and merge its emittable secrets into ``local_env``."""
    secrets = decode_secret_map(load_cgp(cgp_path))
    emittable, skipped = select_emittable(secrets)
    if skipped:
        # Key names only (CodeQL-safe: no value taint).
        print(
            f"ℹ Skipped {len(skipped)} non-emittable entry/entries "
            f"(placeholder/invalid-key/malformed): {', '.join(sorted(skipped))}",
            file=sys.stderr,
        )
    if emittable and not dry_run:
        _write_merged(local_env, emittable)
    return emittable


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cgp",
        type=Path,
        required=True,
        help="Path to the CHIT CGP bundle (e.g. $APPDATA/pmoves/chit/env.cgp.json)",
    )
    parser.add_argument(
        "--local-env",
        type=Path,
        default=None,
        help="Path to local.env (default: platform-appropriate APPDATA/XDG path)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without touching local.env",
    )
    args = parser.parse_args(argv)

    cgp_path = args.cgp.expanduser().resolve()
    local_env = (args.local_env or _default_local_env()).expanduser().resolve()

    if not cgp_path.exists():
        print(f"⚠ CHIT bundle not found at {cgp_path}", file=sys.stderr)
        return 1

    emitted = emit(cgp_path, local_env, dry_run=args.dry_run)

    if not emitted:
        print(f"WARNING: bundle {cgp_path} yielded no emittable secrets", file=sys.stderr)
        return 0

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}Emitted {len(emitted)} secret(s) from {cgp_path.name} -> {local_env}:")
    for key in sorted(emitted):
        print(f"  {key}={_masked(emitted[key])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
