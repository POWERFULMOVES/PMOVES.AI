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
- INVIDIOUS_HMAC_KEY: at least 32 characters, and not the companion key
  (reusing it is "NOT recommended" by the vendor).
- Neither may be a template placeholder or a value published in this repo.

This is the ONE owner of both keys: brand_defaults no longer writes them.
ensure_env_shared.py runs this right after brand_defaults in the mode its
caller asks for -- read-only GATE by default, since ensure-env-shared is a
prerequisite of read-only goals too (auth-check, a0-model-sync-check, ...);
the funnel's secrets-ensure-generated asks for FIX.

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

Modes. Default = FIX (mint / recover / rotate): only for goals that recreate
INVIDIOUS (up-invidious) and for the funnel -- rotating under a running
container that keeps its old key would be silent env/container drift.
``--mint`` is for every other goal that (re)creates containers: it writes
ABSENT keys only (so compose does not refuse), never rotates, warns on the rest. ``--gate`` is for read-only goals (ps, logs,
down, stop): never writes, exits 1 only when compose will refuse, warns on the
rest. ``--check`` reports every problem without writing (secrets-ensure-check).
FIX holds the per-directory env write lock (``env_write_lock``) so ``make -j``
cannot interleave it with ensure-env-shared. ``--exec -- CMD...`` runs CMD with
the keys exported from --env-file, for raw compose callers whose interpolation
source is not that file.
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

from pmoves.tools._secrets_common import env_write_lock, is_known_public, is_placeholder  # noqa: E402


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
# The vendor sets no HMAC length (it suggests `pwgen 20 1`). 32 is the floor
# brand_defaults enforced before this file took ownership, so every HMAC it
# ever wrote stays valid and no node is logged out just for this change.
HMAC_MIN_LENGTH = 32
EXIT_OK, EXIT_FINDINGS, EXIT_COULD_NOT_MEASURE = 0, 1, 3


def problem(key: str, value: Optional[str], others: Dict[str, Optional[str]]) -> Optional[str]:
    """Why *value* is unusable for *key*, or None when it is usable."""
    if not value:
        return "missing"
    if is_known_public(value):
        return "published in the repo"
    if is_placeholder(value):
        return "a template placeholder"
    if key == COMPANION and not COMPANION_RE.fullmatch(value):
        return "not 16 alphanumeric characters"
    if key == HMAC and len(value) < HMAC_MIN_LENGTH:
        return f"shorter than {HMAC_MIN_LENGTH} characters"
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


def _effective(key: str, env_path: Path) -> Optional[str]:
    """What compose will interpolate: a shell export beats every env file."""
    if key in os.environ:
        return os.environ[key]
    return _be.read_env_value(key, env_path)


def _gate(env_path: Path) -> int:
    """Read-only. Exit 1 only when compose's ${VAR:?} will fail; warn on the rest."""
    values = {k: _effective(k, env_path) for k in KEYS}
    fatal = []
    for key in KEYS:
        why = problem(key, values[key], values)
        if why == "missing":
            fatal.append(key)
        elif why:
            print(
                f"invidious-keys: WARNING {key} is {why}; not changed by this read-only goal "
                "(fixed by the next up/recreate goal or make -C pmoves invidious-keys-preflight)"
            )
    for key in fatal:
        print(f"invidious-keys: {key} is missing, so compose will refuse every service. "
              "Fix: make -C pmoves invidious-keys-preflight")
    return EXIT_FINDINGS if fatal else EXIT_OK


def run(env_path: Path, *, mode: str = "fix", registry: Optional[str] = None, probe=None) -> int:
    """mode: fix (mint/recover/rotate), mint (absent keys only; never rotates),
    check (report everything), gate (read-only, fatal only)."""
    if not env_path.exists():
        # A fresh checkout: ensure-env-shared / env-setup / the funnel create it.
        # Writing a file here would stop ensure-env-shared seeding the template.
        print(f"invidious-keys: {env_path.name} absent -- skipped (run make -C pmoves secrets-funnel)")
        return EXIT_OK
    if mode in ("gate", "check"):
        # Readers take the lock SHARED: never beside a writer's half-done cycle.
        with env_write_lock(env_path, shared=True):
            return _gate(env_path) if mode == "gate" else _check(env_path)
    with env_write_lock(env_path):
        return _fix(env_path, registry=registry, probe=probe, rotate=(mode == "fix"))


def _shell_findings() -> list:
    findings = []
    for key in KEYS:
        shell = os.environ.get(key)
        if shell is None:
            continue
        values = {k: os.environ.get(k) for k in KEYS}
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
    return findings


def _check(env_path: Path) -> int:
    findings = _shell_findings()
    values = {k: _be.read_env_value(k, env_path) for k in KEYS}
    for key in KEYS:
        why = problem(key, values[key], values)
        if why:
            findings.append(f"{key}: {why} (fix: make -C pmoves invidious-keys-preflight)")
    for f in findings:
        print(f"invidious-keys: {f}")
    if not findings:
        print("invidious-keys: usable")
    return EXIT_FINDINGS if findings else EXIT_OK


def _fix(env_path: Path, *, registry: Optional[str], probe, rotate: bool = True) -> int:
    findings = _shell_findings()
    values = {k: _be.read_env_value(k, env_path) for k in KEYS}
    todo = {k: problem(k, values[k], values) for k in KEYS}
    todo = {k: why for k, why in todo.items() if why}

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
        if why and why != "missing" and not rotate:
            # MINT mode: this goal does not (re)create Invidious, so a rotation
            # here would leave running invidious/companion containers on the old
            # key -- silent drift. Only up-invidious and the funnel rotate.
            print(
                f"invidious-keys: WARNING {key} is {why}; left as is by this goal "
                "(rotated by make -C pmoves up-invidious or make -C pmoves secrets-funnel)"
            )
        elif why and why != "missing":
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
            f"invidious-keys: {env_path.name} updated. Running containers keep their old keys until "
            "they are recreated (make -C pmoves up-invidious); make -C pmoves secrets-funnel seals the CHIT bundle."
        )
    return EXIT_OK


def _exec(cmd: list, env_path: Path) -> int:
    """Replace this process with *cmd*, the Invidious keys exported from *env_path*.

    For raw compose callers whose interpolation source is not the env file the
    preflight maintains (deploy-compose.sh relies on compose's default .env
    lookup). Values go only into the child's environment, never to output. A
    key already exported in the shell is left alone -- it already wins.
    """
    child = dict(os.environ)
    for key in KEYS:
        if key not in child:
            value = _be.read_env_value(key, env_path) if env_path.exists() else None
            if value:
                child[key] = value
    os.execvpe(cmd[0], cmd, child)
    return EXIT_COULD_NOT_MEASURE  # pragma: no cover - execvpe does not return


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="report every problem; never write (exit 1 on any)")
    group.add_argument(
        "--mint", action="store_true",
        help="goals that recreate containers but not Invidious: write ABSENT keys only, never rotate",
    )
    group.add_argument(
        "--gate", action="store_true",
        help="read-only goals (ps/logs/down/stop): never write; exit 1 only if compose will refuse",
    )
    parser.add_argument("--env-file", type=Path, default=_be.ENV_SHARED_PATH)
    parser.add_argument("--registry", default=None)
    parser.add_argument(
        "--exec", dest="exec_flag", action="store_true",
        help="--exec -- CMD...: after a non-fatal result, exec CMD with the keys exported from --env-file",
    )
    # Everything after --exec is the command, verbatim. Split it off by hand:
    # argparse.REMAINDER mishandles a leading "--".
    argv = list(sys.argv[1:] if argv is None else argv)
    exec_cmd: list = []
    if "--exec" in argv:
        at = argv.index("--exec")
        exec_cmd = argv[at + 1:]
        if exec_cmd[:1] == ["--"]:
            exec_cmd = exec_cmd[1:]
        argv = argv[: at + 1]
    args = parser.parse_args(argv)
    mode = "check" if args.check else "gate" if args.gate else "mint" if args.mint else "fix"
    if args.exec_flag:
        # Keep compose's stdout clean (pipes, grep, --format json): every message
        # this tool prints goes to stderr when it is about to exec a command.
        sys.stdout = sys.stderr
    try:
        rc = run(args.env_file, mode=mode, registry=args.registry)
    except Exception:  # noqa: BLE001 - closed message by design
        # Env files hold secrets; an exception message or traceback could quote
        # one. Report a fixed message and exit 3 (could not measure) instead.
        print("invidious-keys: COULD-NOT-MEASURE: internal error (no detail by design)")
        rc = EXIT_COULD_NOT_MEASURE
    if args.exec_flag:
        if rc == EXIT_FINDINGS:
            return rc
        if not exec_cmd:
            parser.error("--exec needs a command: --exec -- CMD...")
        return _exec(exec_cmd, args.env_file)
    return rc


if __name__ == "__main__":
    sys.exit(main())
