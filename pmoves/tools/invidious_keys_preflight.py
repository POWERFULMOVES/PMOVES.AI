#!/usr/bin/env python3
"""Make this node hold usable Invidious keys BEFORE compose interpolates.

Why it runs on every stack goal, not only up-invidious
------------------------------------------------------
Compose interpolates the whole project, including services whose profile is
off (measured, compose v5.6.0). So once the compose files declare
``${INVIDIOUS_HMAC_KEY:?}`` / ``${INVIDIOUS_COMPANION_KEY:?}``, a node that never
runs Invidious but lacks the keys loses EVERY ``up`` / ``down`` / ``ps``. Only
``make secrets-funnel`` minted them, and no ``up-*`` target runs the funnel.
This is the cheap, idempotent step that closes that window. The Makefile wires
it in front of the stack goals.

What counts as usable (vendor rules, iv-org/invidious @1c4b41f9,
iv-org/invidious-companion @fcb0456a)
- INVIDIOUS_COMPANION_KEY: exactly 16 of [A-Za-z0-9]. Invidious exits on any
  other length; the companion rejects any other character. brand_defaults used
  to mint it with token_urlsafe, so about 40% of those values carry '-' or '_'
  and the companion would refuse to start.
- INVIDIOUS_HMAC_KEY: non-empty, and not equal to the companion key (the vendor
  says not to reuse it).
- Neither may be a value published in this repo (``is_known_public``).

What it does, per key, in env.shared (the file compose reads first)
- absent or empty -> recover a live value from a running container if one
  holds it (secrets_harvest), else mint from the bootstrap registry.
- published or vendor-invalid -> rotate (registry generator). Nothing can be
  running on an invalid key, and a published one is the defect being fixed.
- a private, valid value -> untouched.

It never prints a value. Exit: 0 usable (possibly after fixing) / 1 compose
WILL fail and this could not fix it (needs an operator) / 3 could not measure.
It is built never to make a node worse than compose alone would: exit 1 is
reserved for states where ``${VAR:?}`` fails anyway, so blocking only swaps
compose's error for one that names the key and the fix. A key EXPORTED in the
shell wins over every --env-file and cannot be fixed by writing env.shared: an
empty export is exit 1, a non-empty unusable one is a warning (compose accepts
it; only Invidious is affected).

``--check`` reports without writing (exit 1 if anything needs fixing).
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional

_PMOVES = Path(__file__).resolve().parents[1]
_REPO_ROOT = _PMOVES.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pmoves.tools._secrets_common import is_known_public  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_be = _load("_bootstrap_env_for_invidious_preflight", _PMOVES / "scripts" / "bootstrap_env.py")
_sh = _load("_secrets_harvest_for_invidious_preflight", _PMOVES / "tools" / "secrets_harvest.py")

HMAC, COMPANION = "INVIDIOUS_HMAC_KEY", "INVIDIOUS_COMPANION_KEY"
KEYS = (HMAC, COMPANION)
COMPANION_RE = re.compile(r"[A-Za-z0-9]{16}")
EXIT_OK, EXIT_FINDINGS, EXIT_COULD_NOT_MEASURE = 0, 1, 3


def problem(key: str, value: Optional[str], others: Dict[str, Optional[str]]) -> Optional[str]:
    """Why *value* is unusable for *key*, or None when it is usable."""
    if not value:
        return "missing"
    if is_known_public(value):
        return "published in the repo"
    if key == COMPANION and not COMPANION_RE.fullmatch(value):
        return "not 16 alphanumeric characters"
    if key == HMAC and value == others.get(COMPANION):
        return "same value as INVIDIOUS_COMPANION_KEY"
    return None


def _rotate(key: str, env_path: Path, registry: Optional[str]) -> None:
    declared = _be._registry_generator(key, registry) or {}
    _be.rotate_secret(
        key,
        value=None,
        gen_type=declared.get("type") or "random_hex",
        length=int(declared.get("length") or (16 if key == COMPANION else 64)),
        env_path=env_path,
    )


def run(env_path: Path, *, check: bool, registry: Optional[str] = None, probe=None) -> int:
    if not env_path.exists():
        # A fresh checkout: ensure-env-shared / env-setup / the funnel create it.
        # Writing a file here would stop ensure-env-shared seeding the template.
        print(f"invidious-keys: {env_path.name} absent -- skipped (run make -C pmoves secrets-funnel)")
        return EXIT_OK

    findings = []
    for key in KEYS:
        shell = os.environ.get(key)
        if shell is None:
            continue
        values = {k: os.environ.get(k) or _be.read_env_value(k, env_path) for k in KEYS}
        why = problem(key, shell, values)
        if not why:
            continue
        message = (
            f"{key}: the value EXPORTED in this shell is {why}; it overrides every env file. "
            f"Unset it (unset {key}) and re-run."
        )
        if shell.strip():
            # Compose accepts a non-empty export, so only Invidious is affected:
            # warn, never block the rest of the stack over it.
            print(f"invidious-keys: WARNING {message}")
        else:
            # An EMPTY export fails ${VAR:?} for the whole project anyway.
            findings.append(message)

    values = {k: _be.read_env_value(k, env_path) for k in KEYS}
    todo = {k: problem(k, values[k], values) for k in KEYS}
    todo = {k: why for k, why in todo.items() if why}
    if check:
        for key, why in todo.items():
            findings.append(f"{key}: {why} (fix: make -C pmoves invidious-keys-preflight)")
        for f in findings:
            print(f"invidious-keys: {f}")
        if not findings:
            print("invidious-keys: usable")
        return EXIT_FINDINGS if findings else EXIT_OK

    missing = [k for k, why in todo.items() if why == "missing"]
    if missing:
        plan = _sh.build_plan(missing, env_path=env_path, probe=probe, registry_path=registry)
        refused = [d for d in plan if d.state == _sh.STATE_REFUSE]
        for d in refused:
            findings.append(f"{d.key}: {d.reason} -- {d.detail}")
        if not refused:
            for key in _sh.apply_plan(plan, env_path=env_path):
                print(f"invidious-keys: {key} recovered from a running container")
            for d in plan:
                if d.state == _sh.STATE_MINT:
                    _be.ensure_secret(d.key, env_path=env_path, registry_path=registry)
                    print(f"invidious-keys: {d.key} minted")

    # Re-read: a harvested value can itself be unusable (an old urlsafe key).
    values = {k: _be.read_env_value(k, env_path) for k in KEYS}
    for key in KEYS:
        why = problem(key, values[key], values)
        if why and why != "missing":
            _rotate(key, env_path, registry)
            values = {k: _be.read_env_value(k, env_path) for k in KEYS}
            print(f"invidious-keys: {key} rotated ({why})")
        elif why:
            findings.append(f"{key}: still missing after harvest/mint")

    for f in findings:
        print(f"invidious-keys: {f}")
    if findings:
        return EXIT_FINDINGS
    if todo:
        print(
            "invidious-keys: env.shared updated. Running containers keep their old keys until "
            "make -C pmoves up-invidious; run make -C pmoves secrets-funnel to seal the CHIT bundle."
        )
    return EXIT_OK


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report only; never write")
    parser.add_argument("--env-file", type=Path, default=_be.ENV_SHARED_PATH)
    parser.add_argument("--registry", default=None)
    args = parser.parse_args(argv)
    try:
        return run(args.env_file, check=args.check, registry=args.registry)
    except (OSError, ValueError) as exc:
        print(f"invidious-keys: COULD-NOT-MEASURE: {type(exc).__name__}")
        return EXIT_COULD_NOT_MEASURE


if __name__ == "__main__":
    sys.exit(main())
