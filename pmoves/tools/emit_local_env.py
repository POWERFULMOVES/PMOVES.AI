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
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.chit.codec import decode_secret_map, load_cgp  # noqa: E402
from pmoves.tools._secrets_common import (  # noqa: E402
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
        # Every name that reaches `skipped` passes through _valid_env_key first,
        # so the reported list can only ever contain env-key-shaped names. A
        # malformed entry -- which is exactly the case where the "key" might not
        # be a key at all -- is counted, never echoed. Names are the useful
        # diagnostic; the values behind them are never reportable.
        if not _valid_env_key(key):
            skipped.append("<non-conforming-key>")
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


def _write_replace(local_env: Path, emit: Mapping[str, str]) -> None:
    """Write local.env as EXACTLY the emittable bundle keys (replacement, not merge).

    Replacement is load-bearing for the ``secrets-funnel-from-prod`` path, which
    force-hydrates env.shared from this file. If a secret is removed from / emptied
    in the prod bundle, a *merge* would keep its stale local.env entry and the
    downstream ``secrets-local-hydrate FORCE=1`` would copy that dead credential
    back into env.shared (Codex P1, PR #2602). local.env is the prod-secrets
    overlay — its contents mirror the bundle, nothing else; genuinely node-local
    overrides belong in env.shared, not here. (An empty bundle yields no emittable
    keys, so ``emit`` skips the write entirely and local.env is left untouched.)

    The file holds production secrets in cleartext, so it is installed 0600 inside
    a 0700 directory, written atomically (temp file + ``os.replace``) — matching the
    owner-only permissions ``sync-secrets-local.yml`` uses on a runner. chmod is
    best-effort (a no-op on filesystems without POSIX modes, e.g. Windows).
    """
    local_env.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(local_env.parent, stat.S_IRWXU)  # 0700
    except OSError:
        pass

    lines = [
        "# Auto-generated from the CHIT bundle by pmoves.tools.emit_local_env.",
        "# Replacement overlay: contents mirror the prod bundle (no merge).",
    ]
    for key in sorted(emit):
        lines.append(f"{key}={emit[key]}")
    text = "\n".join(lines) + "\n"

    fd, tmp = tempfile.mkstemp(dir=str(local_env.parent), prefix=".local.env.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        os.replace(tmp, local_env)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def emit(cgp_path: Path, local_env: Path, *, dry_run: bool = False) -> Dict[str, str]:
    """Decode ``cgp_path`` and write its emittable secrets to ``local_env`` (replacement)."""
    secrets = decode_secret_map(load_cgp(cgp_path))
    emittable, skipped = select_emittable(secrets)
    if skipped:
        # Key names only, and only names that already passed _valid_env_key --
        # see select_emittable. A non-conforming entry is reported as a
        # placeholder token, so nothing that failed key validation is echoed.
        print(
            f"ℹ Skipped {len(skipped)} non-emittable entry/entries "
            f"(placeholder/invalid-key/malformed): {', '.join(sorted(skipped))}",
            file=sys.stderr,
        )
    if emittable and not dry_run:
        _write_replace(local_env, emittable)
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
