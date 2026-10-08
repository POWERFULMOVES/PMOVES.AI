#!/usr/bin/env python3
"""Render the NATS dual-credential auth conf from funnel-provided env.

The credential rotation lane (fix/nats-credential-rotation-2026-10-01,
operator decision B 2026-10-03) rotates the leaked default NATS password
without a fleet-wide client recreation wave:

  * the conf carries BOTH the current user (NATS_USER/NATS_PASSWORD) and the
    rotation target (NATS_USER_V2/NATS_PASSWORD_V2);
  * the server adopts it once (one recreate of the SERVER container only —
    clients auto-reconnect);
  * clients pick up the new credential as each is naturally recreated;
  * once monitoring shows zero connections on the old user, `--drop-old`
    re-renders a single-user conf and the make road SIGHUP-reloads it —
    authorization/users is in the vendor-documented reloadable set, applied
    in place with no client disconnects (docs.nats.io:
    running-a-nats-service/configuration/loading; deployment/config-management).

Both passwords are bcrypt-hashed (cost 11) before touching disk: the conf is
runtime data, but a hash means a stray read or backup never yields a usable
credential. bcrypt hashes contain "$" and MUST be quoted in the conf (either
quote character; the emitted form is double-quoted) — an unquoted $NAME token
resolves as a config env variable (documented NATS gotcha).
golang.org/x/crypto/bcrypt (nats-server) verifies $2a$/$2b$.

Fail-closed: an unset or empty password on either user, or a bcrypt failure,
exits non-zero BEFORE any file is written. The output file is 0600.
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "data" / "nats" / "auth.conf"

CONF_TEMPLATE = """\
# Rendered by pmoves/scripts/nats_auth_render.py — DO NOT EDIT BY HAND.
# Rotation road: make nats-auth-render / nats-auth-reload (see
# docs/operations/NATS_CREDENTIAL_ROTATION.md). Vendor basis:
# authorization / users is reloadable via SIGHUP with no client disconnect.
port: 4222
monitor_port: 8222
jetstream {{
  store_dir: /data/js
}}
authorization {{
  # bcrypt hashes are QUOTED (double): unquoted $ tokens resolve as env vars.
  users: [
{users_block}  ]
}}
"""


def _fail(message: str) -> "None":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        _fail(
            f"{name} is unset or empty. Load the funnel env "
            "(bash pmoves/scripts/with-env.sh ...) and fill the slot; "
            "refusing to render a conf with a missing credential."
        )
    return value


def _current_credential() -> tuple[str, str]:
    """The CURRENT bus credential: NATS_USER/NATS_PASSWORD if the funnel set
    them, else parsed out of NATS_URL's userinfo (env.shared carries the
    credential there; the compose CLI args took the same pair)."""
    user = os.environ.get("NATS_USER", "").strip() or "nats"
    password = os.environ.get("NATS_PASSWORD", "").strip()
    if not password:
        url = os.environ.get("NATS_URL", "").strip()
        if "@" in url and "://" in url:
            userinfo = url.split("://", 1)[1].split("@", 1)[0]
            if ":" in userinfo:
                user, password = userinfo.split(":", 1)
    if not password:
        _fail(
            "no current credential: NATS_PASSWORD unset and NATS_URL carries "
            "no userinfo. Load the funnel env and retry; refusing to render "
            "a conf with a missing credential."
        )
    return user, password


def _bcrypt(value: str) -> str:
    try:
        import bcrypt  # tooling venv: uv pip install --python .venv-pmoves/bin/python bcrypt
    except ImportError:
        _fail(
            "the bcrypt package is not installed in this interpreter. "
            "Install it into the pinned tooling venv: "
            "uv pip install --python .venv-pmoves/bin/python bcrypt"
        )
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt(rounds=11)).decode()


def render(out: Path, drop_old: bool) -> None:
    """Bridge mode: BOTH the current (leaked) credential and the rotation
    target, so clients keep working while they migrate. --drop-old (final
    phase): ONLY the rotation target — the leaked user is evicted, which is
    the entire point of the rotation. The target credential is required in
    BOTH modes; a final render that silently kept the leaked user because
    NATS_PASSWORD_V2 was empty would be the inversion this lane exists to
    prevent."""
    target_user = os.environ.get("NATS_USER_V2", "").strip() or "nats-v2"
    target_pass = _required("NATS_PASSWORD_V2")

    blocks = [f'    {{ user: "{target_user}", password: "{_bcrypt(target_pass)}" }}\n']
    if not drop_old:
        old_user, old_pass = _current_credential()
        blocks.insert(
            0, f'    {{ user: "{old_user}", password: "{_bcrypt(old_pass)}" }}\n'
        )

    conf = CONF_TEMPLATE.format(users_block="".join(blocks))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(conf)
    out.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600: hashes only, but keep it tight
    mode = "final (leaked user EVICTED, target only)" if drop_old else "dual-user bridge"
    print(f"rendered {out} ({mode})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--drop-old",
        action="store_true",
        help="final phase: render WITHOUT the old user (run only after "
        "nats-auth-status shows zero connections on it)",
    )
    args = parser.parse_args(argv)
    render(args.out, args.drop_old)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
