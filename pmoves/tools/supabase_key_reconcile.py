#!/usr/bin/env python3
"""Converge the Supabase key SOURCES onto what the RUNNING Supabase verifies.

KNOWN ROAD: `make -C pmoves supabase-key-reconcile` (mk/codex.mk). DRY_RUN is the default.

DIRECTION, and why. The running Supabase holds the users, their sessions and the
data. Its effective JWT secret is what GoTrue, PostgREST, Realtime, Storage and
Studio AGREE on (GOTRUE_JWT_SECRET, PGRST_JWT_SECRET, ...). This tool NEVER changes
that secret. Rotating it invalidates every issued access token and every key
signed with it, so every user is logged out. It would also force a re-mint of the
anon and service keys and a restart of every reader (Supabase self-hosting docs,
"API keys" / JWT secret). Instead the tool re-labels the SOURCE keys
(env.shared, then the tier files that carry them) to values the live stack already
accepts:
  JWT secret keys    SUPABASE_JWT_SECRET, JWT_SECRET            -> the live secret
  service-role keys  SUPABASE_SERVICE_ROLE_KEY, SUPABASE_SERVICE_KEY, SERVICE_ROLE_KEY
                     -> a service_role JWT that verifies under it (preferring the one
                        the running Kong already serves, so Kong is not perturbed)
  anon keys          SUPABASE_ANON_KEY, ANON_KEY -> an anon JWT that verifies under it
  opaque pair        SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY -> CLEARED when
                     they hold a JWT nothing can verify (Supabase ships them empty;
                     Kong's entrypoint strips blank entries)
POSTGRES_PASSWORD is not touched: changing it on a live volume needs a matching
ALTER ROLE, and on B850 the source and the live roles already agree (SCRAM-checked
2026-10-02).

Composes: make secrets-rotate KEY=.. (and CLEAR=1), make env-tiers-sync-keys,
make recreate-svc SVC=supabase-kong (only with --recreate-kong).
Gate after the change: no supabase-* service's effective JWT secret may change, Kong's
rendered service consumer must still verify, and no key outside this family may change.
On gate failure the previous source values (env.shared and every tier) are restored.

Idempotent: a reconciled node plans zero changes. Values are never printed.
Exit: 0 reconciled or nothing to do, 1 refused or rolled back, 3 could-not-measure, 5 rollback failed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coordinated_rotate import (  # noqa: E402
    EXIT_CNM, EXIT_FINDINGS, EXIT_OK, EXIT_ROLLBACK_FAILED, SUPABASE_LIVE_SECRET_KEYS,
    CouldNotMeasure, Runtime, _env_of, iter_services, jwt_claims, jwt_verifies,
    live_supabase_secret, load_stacks, mask, supabase_findings,
)
from merge_shared_to_tiers import DEFAULT_TIERS, sync_keys  # noqa: E402

PMOVES_DIR = Path(__file__).resolve().parents[1]
SECRET_NAMES = ("SUPABASE_JWT_SECRET", "JWT_SECRET")
SERVICE_NAMES = ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "SERVICE_ROLE_KEY")
ANON_NAMES = ("SUPABASE_ANON_KEY", "ANON_KEY")
OPAQUE_NAMES = ("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY")
ALL_NAMES = SECRET_NAMES + SERVICE_NAMES + ANON_NAMES + OPAQUE_NAMES
FAMILY_RE = re.compile(r"JWT|ANON|SERVICE_ROLE|SERVICE_KEY|SUPABASE_KEY|PUBLISHABLE|SUPABASE_SECRET_KEY")


def read_env(path: Path) -> Dict[str, str]:
    """Last-wins, like the funnel's own parser (bootstrap_env.read_env_value)."""
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if s and not s.startswith("#") and "=" in s:
            name, value = s.split("=", 1)
            out[name.strip()] = value.strip()
    return out


def choose_key(role: str, live: str, preferred: List[str], pool: List[str]) -> Optional[str]:
    """First preferred value that verifies with the right role, else the most common
    verifying value in the pool (ties broken by masked class, so the choice is stable)."""
    def ok(v: str) -> bool:
        claims = jwt_claims(v) or {}
        return claims.get("role") == role and jwt_verifies(v, live)

    for v in preferred:
        if v and ok(v):
            return v
    counts = Counter(v for v in pool if v and ok(v))
    if not counts:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], mask(kv[0])))[0][0]


def desired_state(live: str, service: str, anon: str, current: Dict[str, str]) -> Dict[str, Optional[str]]:
    """name -> desired value ("" means clear). Only names that differ from current."""
    want: Dict[str, str] = {}
    for n in SECRET_NAMES:
        want[n] = live
    for n in SERVICE_NAMES:
        want[n] = service
    for n in ANON_NAMES:
        want[n] = anon
    for n in OPAQUE_NAMES:
        v = current.get(n, "")
        if v and jwt_claims(v) is not None and not jwt_verifies(v, live):
            want[n] = ""
    return {n: v for n, v in want.items() if current.get(n, "") != v}


def gate(before: dict, after: dict, live: str, desired_values: set) -> List[str]:
    problems = []
    for svc, spec in after.items():
        env, old = _env_of(spec), _env_of(before.get(svc, {}))
        k = SUPABASE_LIVE_SECRET_KEYS.get(svc)
        if k and env.get(k) and env[k] != live:
            problems.append(f"{svc}: {k} would become {mask(env[k])}; live is {mask(live)} (users would be logged out)")
        for name in sorted(set(env) | set(old)):
            o, n = old.get(name, ""), env.get(name, "")
            if o != n and not (FAMILY_RE.search(name) and (n in desired_values or n == "" or jwt_verifies(n, live))):
                problems.append(f"{svc}: {name} changed {mask(o)} -> {mask(n)} outside the reconcile")
    kong = _env_of(after.get("supabase-kong", {}))
    if kong and not jwt_verifies(kong.get("SUPABASE_SERVICE_KEY", ""), live):
        problems.append("supabase-kong: rendered SUPABASE_SERVICE_KEY does not verify under the live secret")
    return problems


def kong_probe(url: str, service: str, anon: str) -> List[str]:
    def status(key: str) -> object:
        req = urllib.request.Request(url.rstrip("/") + "/rest/v1/", headers={"apikey": key, "Authorization": f"Bearer {key}"})
        try:
            return urllib.request.urlopen(req, timeout=10).status  # noqa: S310 - loopback Kong
        except urllib.error.HTTPError as e:
            return e.code
        except OSError as e:
            return type(e).__name__
    out = []
    for role, key in (("service_role", service), ("anon", anon)):
        st = status(key)
        if st != 200:
            out.append(f"kong /rest/v1 with the reconciled {role} key ({mask(key)}) returned {st}")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stack", required=True, help="main=<compose command>")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--node", default=os.environ.get("PMOVES_NODE") or socket.gethostname().split(".")[0])
    ap.add_argument("--recreate-kong", action="store_true")
    ap.add_argument("--kong-url", default="http://127.0.0.1:8000")
    ap.add_argument("--root", type=Path, default=PMOVES_DIR, help="pmoves/ (env.shared + tier files)")
    ap.add_argument("--state-dir", type=Path, default=Path.home() / ".config" / "pmoves" / "rotation-state")
    ap.add_argument("--docker", default="docker")
    ap.add_argument("--make", default="make")
    ap.add_argument("--fixture", default="", help="rendered.json:noint.json (tests)")
    ap.add_argument("--gate-fixture", default="", help="rendered.json:noint.json for the post-change render (tests)")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    verdict: dict = {"node": args.node, "mode": "execute" if args.execute else "dry-run"}

    def finish(code: int) -> int:
        verdict["exit_code"] = code
        if args.json:
            args.json.write_text(json.dumps(verdict, indent=2))
        return code

    rt = Runtime(docker=args.docker, make=args.make, make_dir=args.root)
    fx = {"main": tuple(args.fixture.split(":", 1))} if args.fixture else {}
    try:
        stack = load_stacks(rt, [args.stack], fx)[0]
        running = rt.running()
        live, findings = live_supabase_secret(rt, running)
    except CouldNotMeasure as exc:
        print(f"COULD-NOT-MEASURE: {exc}")
        return finish(EXIT_CNM)
    if findings:
        for f in findings:
            print(f"REFUSE {f}")
        verdict["refusals"] = findings
        return finish(EXIT_FINDINGS)
    if not live:
        print("COULD-NOT-MEASURE: no running Supabase service exposes its JWT secret; nothing to converge onto")
        return finish(EXIT_CNM)

    kong_cid = running.get((stack.project, "supabase-kong"))
    kong_env = {}
    if kong_cid:
        kong_env = dict(e.split("=", 1) for e in (rt.inspect(kong_cid).get("Config") or {}).get("Env") or [] if "=" in e)
    pool = [v for _, svc in iter_services([stack]) for k, v in _env_of(stack.rendered[svc]).items()
            if k in SERVICE_NAMES + ANON_NAMES + ("NEXT_PUBLIC_SUPABASE_ANON_KEY",)]
    service = choose_key("service_role", live, [kong_env.get("SUPABASE_SERVICE_KEY", "")], pool)
    anon = choose_key("anon", live, [kong_env.get("SUPABASE_ANON_KEY", "")], pool)
    print(f"== LIVE Supabase JWT secret class {mask(live)} (agreed by {sorted(s for (_, s) in running if s in SUPABASE_LIVE_SECRET_KEYS)})")
    print(f"   service_role key: {mask(service) if service else 'NONE verifies'}   anon key: {mask(anon) if anon else 'NONE verifies'}")
    if not service or not anon:
        print("REFUSE: no verifying key for a role; minting one means a JWT signed by the live secret. "
              "That is an operator step (scripts/supabase/generate-keys.sh with the LIVE secret), not this road")
        verdict["refusals"] = ["no-verifying-key"]
        return finish(EXIT_FINDINGS)

    shared_path = args.root / "env.shared"
    current = read_env(shared_path)
    changes = desired_state(live, service, anon, current)
    tiers = {t: read_env(args.root / t) for t in DEFAULT_TIERS}
    tier_drift = sorted(f"{t}:{n} {mask(v)}" for t, env in tiers.items() for n, v in env.items()
                        if n in ALL_NAMES and v != (changes.get(n, current.get(n, ""))))
    verdict["plan"] = {"env_shared": {n: f"{mask(current.get(n, ''))} -> {mask(v) if v else 'CLEAR'}" for n, v in changes.items()},
                       "tier_drift": tier_drift}
    print("== PLAN")
    for n, v in changes.items():
        print(f"   env.shared {n}: {mask(current.get(n, ''))} -> {mask(v) if v else 'CLEAR'}")
    for d in tier_drift:
        print(f"   tier {d} -> synced from env.shared")
    if args.recreate_kong:
        print("   then: make recreate-svc SVC=supabase-kong, probe /rest/v1 with both keys")
    expected = f"RECONCILE SUPABASE KEYS @ {args.node}"
    if not changes and not tier_drift:
        print("== already reconciled; nothing to do")
        return finish(EXIT_OK)
    print(f"   execute with: DRY_RUN=0 CONFIRM='{expected}'")
    if not args.execute:
        return finish(EXIT_OK)
    if args.confirm != expected:
        print(f"REFUSED: CONFIRM must be exactly {expected!r}")
        return finish(EXIT_FINDINGS)

    # state: everything needed to put the sources back exactly
    args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path = args.state_dir / f"supabase-reconcile-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    fd = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"env_shared": {n: current.get(n, "") for n in ALL_NAMES},
                   "tiers": {t: {n: v for n, v in env.items() if n in ALL_NAMES} for t, env in tiers.items()}}, fh)
    log: List[str] = []

    def apply(values: Dict[str, str]) -> bool:
        for n, v in values.items():
            if v:
                rc = rt.make(["secrets-rotate", f"KEY={n}"], {"PMOVES_ROTATE_VALUE": v})
            else:
                rc = rt.make(["secrets-rotate", f"KEY={n}", "CLEAR=1"])
            log.append(f"secrets-rotate KEY={n} -> {mask(v) if v else 'CLEAR'} rc={rc}")
            if rc != 0:
                return False
        rc = rt.make(["env-tiers-sync-keys", "KEYS=" + ",".join(ALL_NAMES)])
        log.append(f"env-tiers-sync-keys rc={rc}")
        return rc == 0

    def restore() -> bool:
        saved = json.loads(state_path.read_text())
        ok = apply({n: v for n, v in saved["env_shared"].items() if read_env(shared_path).get(n, "") != v})
        for t, vals in saved["tiers"].items():  # put tier-only values back exactly
            if (args.root / t).exists():
                sync_keys(args.root / t, vals)
        return ok

    ok = apply(changes)
    problems: List[str] = []
    if ok:
        gfx = {"main": tuple(args.gate_fixture.split(":", 1))} if args.gate_fixture else {}
        after = load_stacks(rt, [args.stack], gfx)[0]
        problems = gate(stack.rendered, after.rendered, live, {live, service, anon})
    if ok and not problems and args.recreate_kong:
        if rt.make(["recreate-svc", "SVC=supabase-kong"]) != 0:
            problems.append("recreate-svc supabase-kong failed")
        else:
            time.sleep(5)
            problems += kong_probe(args.kong_url, service, anon)
    if ok and not problems:
        state_path.unlink()
        for line in log:
            print(f"   {line}")
        print("== RECONCILED (no container recreated" + (" except supabase-kong)" if args.recreate_kong else ")"))
        verdict["outcome"] = "reconciled"
        return finish(EXIT_OK)
    for p in problems:
        log.append(f"GATE: {p}")
    restored = restore()
    if restored and args.recreate_kong:
        restored = rt.make(["recreate-svc", "SVC=supabase-kong"]) == 0
    for line in log:
        print(f"   {line}")
    verdict.update(outcome="rolled-back" if restored else "rollback-FAILED", log=log)
    if restored:
        state_path.unlink()
        print("== ROLLED BACK: sources restored to their previous values")
        return finish(EXIT_FINDINGS)
    print(f"== ROLLBACK FAILED: previous values kept at {state_path} (0600)")
    return finish(EXIT_ROLLBACK_FAILED)


if __name__ == "__main__":
    sys.exit(main())
