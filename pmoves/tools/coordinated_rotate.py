#!/usr/bin/env python3
"""Coordinated secret rotation: rotate ONE secret and recreate everything that holds it, together.

KNOWN ROAD: `make -C pmoves secret-rotate-coordinated KEY=<name>` (mk/codex.mk).

WHY THIS EXISTS. `secrets-rotate` ends by printing "STILL TO DO: restart
consumers". For a secret that a SERVER enforces (NATS_PASSWORD is a CLI flag on
nats-server, so there is no dual-credential overlap window), the consumers are
not a to-do list. Every client still holding the old value is an outage the
moment the server restarts. And "restart consumers" by hand on this stack meant
discovering, on 2026-10-01, that recreating ~15 NATS clients would ALSO apply
25-74 unrelated drifted keys each. That included a Supabase service key the live
Kong rejects, and image tags that were not on the box. So rotation became a
redeploy that nobody had planned.

This tool composes the existing roads and does not replace them:
  mint + re-materialize   make secrets-rotate KEY=<label>   (codex.mk; bootstrap_env --rotate,
                          chit-export, secrets-funnel), once per label carrying the value
  recreate                make recreate-svc SVC=<s>, or the per-service road in
                          config/coordinated_recreate.yaml (up-a0-archon-scoped, up-yt-cookies-recreate, ...)
  record                  make register-note, make sign-trail

Phases: DISCOVER -> PREFLIGHT (fail-closed) -> PLAN (DRY_RUN stops here, the default)
-> EXECUTE (needs CONFIRM='ROTATE <KEY> @ <node>') -> VERIFY -> AUTO-ROLLBACK on failure.

Consumers are DERIVED, never listed:
  server    the rendered command/entrypoint contains the current value (nats `--pass`)
  declared  the un-interpolated compose references ${KEY} or a linked key (${NATS_URL})
  observed  a live probe sees the container using it (NATS: /connz on the monitor port)
  carrier   the value reaches the container env only by env_file inheritance. Listed,
            NOT recreated (INCLUDE= to opt in). A carrier keeps the stale value.
Linked keys are any rendered key whose value CONTAINS the secret (NATS_URL userinfo).
Those that are CHIT manifest labels are rotated with it; the rest are compose-interpolated
and follow automatically. The post-funnel gate proves that.

Every subprocess (compose render, make) runs in a CLEAN environment (HOME, PATH,
DOCKER_*). Shell env beats --env-file in compose interpolation, and an agent
session that inherited 200+ exported credentials renders a different stack than
the files describe (measured 2026-10-02: 18 keys).

Never prints a secret: values appear as sha256[:4] equality classes.

Exit codes: 0 done / plan clean, 1 refused or rolled back, 3 could-not-measure,
5 ROLLBACK FAILED (state file kept; human needed). make collapses nonzero exits
to 2, so read the JSON verdict (--json) for the real one.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets as _secrets
import shlex
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

PMOVES_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PMOVES_DIR / "config" / "coordinated_recreate.yaml"
DEFAULT_MANIFEST = PMOVES_DIR / "chit" / "secrets_manifest.yaml"
DEFAULT_STATE_DIR = Path.home() / ".config" / "pmoves" / "rotation-state"

EXIT_OK, EXIT_FINDINGS, EXIT_CNM, EXIT_ROLLBACK_FAILED = 0, 1, 3, 5

# Keys in a rendered env that must agree with the RUNNING Supabase before a
# consumer may be recreated. JWT-shaped values must verify under the live secret.
SUPABASE_SECRET_KEYS = ("SUPABASE_JWT_SECRET",)
SUPABASE_JWT_KEY_RE = re.compile(
    r"(^|_)(SERVICE_ROLE_KEY|SERVICE_KEY|ANON_KEY|SUPABASE_KEY|PUBLISHABLE_KEY|SUPABASE_SECRET_KEY)$"
)
# Where each running Supabase service reads its JWT secret. The live secret is the
# one these AGREE on, and NOT the generic SUPABASE_JWT_SECRET they merely inherit
# (that confusion produced a false "mismatch" on 2026-10-01).
SUPABASE_LIVE_SECRET_KEYS = {
    "supabase-gotrue": "GOTRUE_JWT_SECRET",
    "supabase-postgrest": "PGRST_JWT_SECRET",
    "supabase-realtime": "API_JWT_SECRET",
    "supabase-storage": "PGRST_JWT_SECRET",
    "supabase-studio": "AUTH_JWT_SECRET",
}


def mask(value: Optional[str]) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:4] if value else "----"


def _b64url_decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def jwt_claims(token: str) -> Optional[dict]:
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    try:
        return json.loads(_b64url_decode(parts[1]))
    except Exception:
        return None


def jwt_verifies(token: str, secret: str) -> bool:
    """HS256 signature check. False for non-JWTs and for any other algorithm."""
    parts = (token or "").split(".")
    if len(parts) != 3 or not secret:
        return False
    try:
        if json.loads(_b64url_decode(parts[0])).get("alg") != "HS256":
            return False
    except Exception:
        return False
    sig = hmac.new(secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
    return hmac.compare_digest(base64.urlsafe_b64encode(sig).rstrip(b"=").decode(), parts[2])


def _flatten(obj) -> str:
    return json.dumps(obj, sort_keys=True) if obj is not None else ""


def _env_of(service: dict) -> Dict[str, str]:
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) if "=" in item else (item, "") for item in env)
    return {k: (v if v is not None else "") for k, v in env.items()}


# --------------------------------------------------------------------------- runtime
class Runtime:
    """Every side effect goes through here, so tests can point it at stub binaries."""

    def __init__(self, docker: str = "docker", make: str = "make", make_dir: Path = PMOVES_DIR,
                 fetch_json: Optional[Callable[[str], dict]] = None):
        self.docker_bin = docker
        self.make_bin = make
        self.make_dir = make_dir
        self._fetch_json = fetch_json or self._urlopen_json

    @staticmethod
    def clean_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = {k: os.environ[k] for k in ("HOME", "PATH", "USER", "LANG", "DOCKER_HOST",
                                          "DOCKER_CONFIG", "DOCKER_CONTEXT") if k in os.environ}
        env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
        env.update(extra or {})
        return env

    def _docker(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([self.docker_bin, *args], capture_output=True, text=True,
                              env=self.clean_env())

    def running(self) -> Dict[Tuple[str, str], str]:
        fmt = '{{.ID}}|{{.Label "com.docker.compose.project"}}|{{.Label "com.docker.compose.service"}}'
        out = self._docker("ps", "--format", fmt)
        if out.returncode != 0:
            raise CouldNotMeasure(f"docker ps failed: {out.stderr.strip()[:200]}")
        found = {}
        for line in out.stdout.splitlines():
            parts = line.split("|")
            if len(parts) == 3 and parts[1] and parts[2]:
                found[(parts[1], parts[2])] = parts[0]
        return found

    def inspect(self, cid: str) -> dict:
        out = self._docker("inspect", cid)
        if out.returncode != 0:
            return {}
        data = json.loads(out.stdout or "[]")
        return data[0] if data else {}

    def image_present(self, ref: str) -> bool:
        return self._docker("image", "inspect", ref).returncode == 0

    def image_pullable(self, ref: str) -> bool:
        return self._docker("manifest", "inspect", ref).returncode == 0

    def render(self, cmd: List[str], interpolate: bool = True) -> dict:
        args = [*cmd, "--profile", "*", "config", "--format", "json"]
        if not interpolate:
            args.insert(-2, "--no-interpolate")
        out = subprocess.run(args, capture_output=True, text=True, cwd=self.make_dir,
                             env=self.clean_env())
        if out.returncode != 0:
            raise CouldNotMeasure(f"compose render failed: {out.stderr.strip()[:300]}")
        return json.loads(out.stdout).get("services", {})

    def make(self, target: List[str], extra_env: Optional[Dict[str, str]] = None) -> int:
        return subprocess.run([self.make_bin, "-C", str(self.make_dir), "--no-print-directory", *target],
                              env=self.clean_env(extra_env)).returncode

    def fetch_json(self, url: str) -> dict:
        return self._fetch_json(url)

    @staticmethod
    def _urlopen_json(url: str) -> dict:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - loopback monitor
            return json.loads(resp.read())


class CouldNotMeasure(RuntimeError):
    pass


# --------------------------------------------------------------------------- stacks
@dataclass
class Stack:
    name: str
    project: str
    cmd: List[str]
    rendered: dict = field(default_factory=dict)
    noint: dict = field(default_factory=dict)


def parse_stack_arg(spec: str) -> Tuple[str, List[str]]:
    name, _, cmd = spec.partition("=")
    if not name or not cmd:
        raise SystemExit(f"--stack expects NAME=<compose command>, got {spec!r}")
    return name, shlex.split(cmd)


def project_of(cmd: List[str]) -> str:
    for i, tok in enumerate(cmd):
        if tok in ("-p", "--project-name") and i + 1 < len(cmd):
            return cmd[i + 1]
    return "pmoves"


def load_stacks(rt: Runtime, specs: List[str], fixtures: Dict[str, Tuple[str, str]]) -> List[Stack]:
    stacks = []
    for spec in specs:
        name, cmd = parse_stack_arg(spec)
        st = Stack(name=name, project=project_of(cmd), cmd=cmd)
        if name in fixtures:
            rendered_path, noint_path = fixtures[name]
            st.rendered = json.loads(Path(rendered_path).read_text())["services"]
            st.noint = json.loads(Path(noint_path).read_text())["services"]
        else:
            st.rendered = rt.render(cmd, interpolate=True)
            st.noint = rt.render(cmd, interpolate=False)
        stacks.append(st)
    return stacks


def iter_services(stacks: List[Stack]) -> Iterable[Tuple[Stack, str]]:
    """Each service once: the first stack that defines it owns it (extra stacks that
    re-include docker-compose.yml contribute only their own services)."""
    seen = set()
    for st in stacks:
        for svc in sorted(st.rendered):
            if svc in seen:
                continue
            seen.add(svc)
            yield st, svc


# --------------------------------------------------------------------------- discovery
@dataclass
class Consumer:
    stack: str
    project: str
    service: str
    roles: set = field(default_factory=set)

    @property
    def ident(self) -> str:
        return f"{self.stack}/{self.service}"


@dataclass
class Discovery:
    key: str
    value: str
    linked: Dict[str, str]          # linked key -> its current rendered value
    manifest_labels: List[str]      # labels to rotate, KEY first
    derived: List[str]              # linked keys that follow by interpolation
    consumers: Dict[str, Consumer]  # ident -> consumer

    def masked(self) -> dict:
        return {
            "key": self.key,
            "value_class": mask(self.value),
            "rotate_labels": self.manifest_labels,
            "derived_keys": self.derived,
            "consumers": {c.ident: sorted(c.roles) for c in self.consumers.values()},
        }


def load_manifest_labels(path: Path) -> set:
    import yaml  # local import: only the CLI path needs it

    data = yaml.safe_load(path.read_text())
    return {e.get("source", {}).get("label") for e in data.get("entries", []) if e.get("source")}


# Userinfo inside any URL-shaped substring, including URLs embedded in JSON values
# (A0_SET_mcp_servers). Matching is STRUCTURAL, never a bare substring: the leaked
# NATS default is the word "pmoves", which also appears in PMOVES_NETWORKS,
# image names and paths.
_USERINFO_RE = re.compile(r"([a-z][a-z0-9+.-]*://[^:/@\s\"']*:)([^@/\s\"']*)(@)", re.I)


def _contains_secret(value: str, secret: str) -> bool:
    """True when *value* carries *secret* as a URL userinfo password (not when equal)."""
    if not value or not secret or value == secret:
        return False
    return any(urllib.parse.unquote(m.group(2)) == secret for m in _USERINFO_RE.finditer(value))


def carries(value: str, secret: str) -> bool:
    return bool(value) and (value == secret or _contains_secret(value, secret))


def replace_secret(value: str, old: str, new: str) -> str:
    """Swap *old* for *new* only where it is the whole value or a userinfo password."""
    if value == old:
        return new
    return _USERINFO_RE.sub(
        lambda m: m.group(1) + (urllib.parse.quote(new, safe="") if urllib.parse.unquote(m.group(2)) == old
                                else m.group(2)) + m.group(3), value)


def _argv_tokens(spec) -> List[str]:
    if spec is None:
        return []
    if isinstance(spec, str):
        spec = shlex.split(spec)
    out = []
    for tok in spec:
        tok = str(tok)
        out.append(tok.split("=", 1)[1] if tok.startswith("--") and "=" in tok else tok)
    return out


def argv_carries(spec, secret: str) -> bool:
    return any(t == secret or _contains_secret(t, secret) for t in _argv_tokens(spec))


def argv_masked(spec, secret: str) -> List[str]:
    return ["<SECRET>" if (t == secret or _contains_secret(t, secret)) else t for t in _argv_tokens(spec)]


def discover(stacks: List[Stack], key: str, manifest_labels: set) -> Discovery:
    values = {_env_of(st.rendered[s]).get(key) for st, s in iter_services(stacks)}
    values.discard(None)
    values.discard("")
    if not values:
        raise CouldNotMeasure(f"{key} is not set in any rendered service; nothing to rotate")
    if len(values) > 1:
        raise Refusal("key-inconsistent",
                      f"{key} renders to {len(values)} different values "
                      f"({', '.join(sorted(mask(v) for v in values))}); reconcile the source first")
    value = values.pop()

    linked: Dict[str, str] = {}
    for st, svc in iter_services(stacks):
        for k, v in _env_of(st.rendered[svc]).items():
            if k != key and _contains_secret(v, value):
                if k in linked and linked[k] != v:
                    raise Refusal("linked-inconsistent",
                                  f"linked key {k} renders to more than one value; cannot derive its rotation")
                linked[k] = v
    labels = [key] + sorted(k for k in linked if k in manifest_labels)
    derived = sorted(k for k in linked if k not in manifest_labels)
    names = [key] + sorted(linked)
    ref = re.compile(r"\$\{?(" + "|".join(re.escape(n) for n in names) + r")\b")

    consumers: Dict[str, Consumer] = {}
    for st, svc in iter_services(stacks):
        rsvc, nsvc = st.rendered[svc], st.noint.get(svc, {})
        roles = set()
        if argv_carries(rsvc.get("command"), value) or argv_carries(rsvc.get("entrypoint"), value):
            roles.add("server")
        blob = _flatten(_env_of(nsvc)) + _flatten(nsvc.get("command")) + _flatten(nsvc.get("entrypoint"))
        if ref.search(blob):
            roles.add("declared")
        env = _env_of(rsvc)
        if not roles and any(carries(env.get(n, ""), value) for n in names):
            roles.add("carrier")
        if roles:
            consumers[f"{st.name}/{svc}"] = Consumer(st.name, st.project, svc, roles)
    return Discovery(key, value, linked, labels, derived, consumers)


# --------------------------------------------------------------------------- probes
class NatsProbe:
    """Observe clients via the monitor port; prove credentials by a raw CONNECT."""

    def __init__(self, rt: Runtime, monitor_url: str, port: int = 4222, user_key: str = "NATS_USER",
                 host: str = "127.0.0.1"):
        self.rt, self.monitor_url, self.port, self.user_key, self.host = rt, monitor_url, port, user_key, host

    def connections(self, running: Dict[Tuple[str, str], str]) -> Dict[Tuple[str, str], int]:
        ip_to = {}
        for ident, cid in running.items():
            for net in (self.rt.inspect(cid).get("NetworkSettings", {}).get("Networks") or {}).values():
                if net.get("IPAddress"):
                    ip_to[net["IPAddress"]] = ident
        data = self.rt.fetch_json(self.monitor_url.rstrip("/") + "/connz?limit=4096")
        counts: Dict[Tuple[str, str], int] = {}
        for conn in data.get("connections", []):
            ident = ip_to.get(conn.get("ip"))
            if ident:
                counts[ident] = counts.get(ident, 0) + 1
        return counts

    def auth_accepted(self, user: str, password: str) -> Optional[bool]:
        try:
            with socket.create_connection((self.host, self.port), timeout=5) as sock:
                sock.recv(4096)  # INFO
                connect = json.dumps({"user": user, "pass": password, "verbose": False, "pedantic": False})
                sock.sendall(f"CONNECT {connect}\r\nPING\r\n".encode())
                reply = sock.recv(4096).decode(errors="replace")
        except OSError:
            return None
        return "PONG" in reply and "-ERR" not in reply


# --------------------------------------------------------------------------- preflight
class Refusal(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


@dataclass
class Member:
    consumer: Consumer
    container: str
    image_ref: str
    image_var: Optional[str]
    baseline_health: str
    baseline_conns: int = 0


def image_of(stack: Stack, svc: str) -> Tuple[str, Optional[str]]:
    ref = stack.rendered[svc].get("image") or f"{stack.project}-{svc}"
    raw = str(stack.noint.get(svc, {}).get("image") or "")
    m = re.match(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?-[^}]*)?\}$", raw)
    return ref, (m.group(1) if m else None)


def health_of(info: dict) -> str:
    state = info.get("State") or {}
    if not state.get("Running"):
        return "not-running"
    return (state.get("Health") or {}).get("Status") or "running"


def drift_of(info: dict, rendered_env: Dict[str, str], ignore: set) -> Tuple[List[str], List[str]]:
    have = dict(e.split("=", 1) if "=" in e else (e, "") for e in (info.get("Config") or {}).get("Env") or [])
    changed = sorted(k for k, v in rendered_env.items() if k in have and have[k] != v and k not in ignore)
    new = sorted(k for k in rendered_env if k not in have and k not in ignore)
    return changed, new


def live_supabase_secret(rt: Runtime, running: Dict[Tuple[str, str], str]) -> Tuple[Optional[str], List[str]]:
    """The JWT secret the running Supabase services AGREE on, or (None, findings)."""
    seen, findings = {}, []
    for (_, svc), cid in running.items():
        k = SUPABASE_LIVE_SECRET_KEYS.get(svc)
        if not k:
            continue
        env = dict(e.split("=", 1) for e in (rt.inspect(cid).get("Config") or {}).get("Env") or [] if "=" in e)
        if env.get(k):
            seen[svc] = env[k]
    if not seen:
        return None, []
    if len(set(seen.values())) > 1:
        findings.append("running Supabase services disagree on their JWT secret: "
                        + ", ".join(f"{s}={mask(v)}" for s, v in sorted(seen.items())))
        return None, findings
    return next(iter(seen.values())), findings


def supabase_findings(rendered_env: Dict[str, str], live: str) -> List[str]:
    out = []
    for k in SUPABASE_SECRET_KEYS:
        v = rendered_env.get(k)
        if v and v != live:
            out.append(f"{k}={mask(v)} but the running Supabase verifies with {mask(live)}")
    for k, v in sorted(rendered_env.items()):
        if SUPABASE_JWT_KEY_RE.search(k) and v and jwt_claims(v) is not None and not jwt_verifies(v, live):
            out.append(f"{k}={mask(v)} is a JWT the running Supabase cannot verify")
    return out


@dataclass
class Preflight:
    members: List[Member]
    carriers: List[str]
    not_running: List[str]
    refusals: List[Tuple[str, str]]
    warnings: List[str]
    probe_baseline: Dict[str, int]


def preflight(rt: Runtime, stacks: List[Stack], disc: Discovery, *, ack_drift: set, include: set,
              pins: Dict[str, str], probe: Optional[NatsProbe], roads: "Roads") -> Preflight:
    running = rt.running()
    by_name = {st.name: st for st in stacks}
    refusals: List[Tuple[str, str]] = []
    warnings: List[str] = []
    members, carriers, not_running = [], [], []
    ignore = {disc.key, *disc.linked}  # keys whose value carries the secret change by design
    live, sb_findings = live_supabase_secret(rt, running)
    refusals += [("supabase-live-inconsistent", f) for f in sb_findings]
    conns = {}
    if probe is not None:
        try:
            conns = probe.connections(running)
        except Exception as exc:  # noqa: BLE001 - surfaced as could-not-measure below
            refusals.append(("probe-unavailable", f"baseline probe failed: {exc}"))

    for ident, c in sorted(disc.consumers.items()):
        st = by_name[c.stack]
        observed = conns.get((c.project, c.service), 0)
        if observed:
            c.roles.add("observed")
        wanted = bool(c.roles & {"server", "declared", "observed"}) or c.service in include or ident in include
        cid = running.get((c.project, c.service))
        if not wanted:
            carriers.append(ident)
            continue
        if not cid:
            not_running.append(ident)
            continue
        if roads.road_for(c) is None:
            refusals.append(("no-road", f"{ident}: no recreate road configured for stack {c.stack!r}"))
        info = rt.inspect(cid)
        renv = _env_of(st.rendered[c.service])
        # Only the key itself may EQUAL the value: the leaked default is a common word
        # ("pmoves" is also a database name), so equality elsewhere means nothing.
        target_ignore = ignore | {k for k, v in renv.items() if _contains_secret(v, disc.value)}
        changed, new = drift_of(info, renv, target_ignore)
        if (changed or new) and c.service not in ack_drift and ident not in ack_drift:
            refusals.append(("drift", f"{ident}: {len(changed)} non-target keys differ, {len(new)} new "
                                      f"(changed={changed[:12]}{'...' if len(changed) > 12 else ''}). "
                                      f"Acknowledge with ACK_DRIFT={c.service} or reconcile first"))
        ref, var = image_of(st, c.service)
        if c.service in pins:
            if not var:
                refusals.append(("pin-impossible", f"{ident}: image is not parameterised; PIN cannot apply"))
            ref = pins[c.service]
        if not rt.image_present(ref) and not rt.image_pullable(ref):
            refusals.append(("image", f"{ident}: image {ref} is neither present nor pullable. "
                                      f"PIN={c.service}=<local image> (var {var or 'NONE'}) or build it first"))
        if live:
            for f in supabase_findings(renv, live):
                refusals.append(("supabase", f"{ident}: {f}. Run `make -C pmoves supabase-key-reconcile` first"))
        members.append(Member(c, cid, ref, var, health_of(info), observed))
    if not any("server" in m.consumer.roles for m in members):
        warnings.append("no running SERVER consumer found: nothing enforces this secret, so rotating it changes only clients")
    for m in members:
        if m.baseline_health not in ("healthy", "running"):
            warnings.append(f"{m.consumer.ident} is {m.baseline_health} BEFORE rotation; verify will not demand better")
    baseline = {f"{p}/{s}": n for (p, s), n in conns.items()}
    return Preflight(members, carriers, not_running, refusals, warnings, baseline)


# --------------------------------------------------------------------------- roads + plan
class Roads:
    def __init__(self, cfg: dict):
        self.default = cfg.get("default", {})
        self.overrides = cfg.get("overrides", [])

    def road_for(self, c: Consumer) -> Optional[Tuple[str, str]]:
        """(batch-id, target template) or None when the stack has no road."""
        for i, o in enumerate(self.overrides):
            if c.service in o.get("services", []) and o.get("stack", "main") == c.stack:
                return f"override-{i}", o["target"]
        tpl = self.default.get(c.stack)
        return (f"svc-{c.ident}", tpl) if tpl else None


def depth(stack: Stack, svc: str, within: set, memo: dict) -> int:
    if svc in memo:
        return memo[svc]
    memo[svc] = 0
    deps = stack.rendered.get(svc, {}).get("depends_on") or {}
    names = deps if isinstance(deps, (list, dict)) else []
    memo[svc] = max([depth(stack, d, within, memo) + 1 for d in names if d in within] or [0])
    return memo[svc]


def plan_batches(stacks: List[Stack], members: List[Member], roads: Roads) -> List[dict]:
    order = {st.name: i for i, st in enumerate(stacks)}
    by_stack: Dict[str, set] = {}
    for m in members:
        by_stack.setdefault(m.consumer.stack, set()).add(m.consumer.service)
    memo: Dict[str, dict] = {}
    st_by = {st.name: st for st in stacks}

    def key(m: Member):
        c = m.consumer
        d = depth(st_by[c.stack], c.service, by_stack[c.stack], memo.setdefault(c.stack, {}))
        return (0 if "server" in c.roles else 1, order[c.stack], d, c.service)

    batches: List[dict] = []
    index: Dict[str, dict] = {}
    for m in sorted(members, key=key):
        bid, tpl = roads.road_for(m.consumer)
        if bid not in index:
            index[bid] = {"road": tpl, "members": []}
            batches.append(index[bid])
        index[bid]["members"].append(m)
    for b in batches:
        svcs = [m.consumer.service for m in b["members"]]
        b["target"] = shlex.split(b["road"].format(service=svcs[0], services=" ".join(svcs)))
        b["pins"] = {m.image_var: m.image_ref for m in b["members"] if m.image_var}
    return batches


# --------------------------------------------------------------------------- execute
@dataclass
class Outcome:
    status: str
    exit_code: int
    detail: List[str] = field(default_factory=list)


class Executor:
    def __init__(self, rt: Runtime, stacks: List[Stack], disc: Discovery, pf: Preflight,
                 batches: List[dict], *, probe: Optional[NatsProbe], state_dir: Path,
                 verify_timeout: float, poll: float, gate_renderer: Callable[[], List[Stack]]):
        self.rt, self.stacks, self.disc, self.pf, self.batches = rt, stacks, disc, pf, batches
        self.probe, self.state_dir, self.timeout, self.poll = probe, state_dir, verify_timeout, poll
        self.gate_renderer = gate_renderer
        self.log: List[str] = []

    # values -----------------------------------------------------------
    def label_values(self, secret: str) -> Dict[str, str]:
        out = {self.disc.key: secret}
        for label in self.disc.manifest_labels[1:]:
            out[label] = replace_secret(self.disc.linked[label], self.disc.value, secret)
        return out

    def save_state(self, new: str) -> Path:
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_dir, 0o700)
        path = self.state_dir / f"{self.disc.key}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"key": self.disc.key, "restore": self.label_values(self.disc.value),
                       "old_class": mask(self.disc.value), "new_class": mask(new),
                       "batches": [[m.consumer.ident for m in b["members"]] for b in self.batches]}, fh)
        return path

    # steps ------------------------------------------------------------
    def rotate_to(self, values: Dict[str, str]) -> bool:
        for label, value in values.items():
            self.log.append(f"secrets-rotate KEY={label} -> class {mask(value)}")
            if self.rt.make(["secrets-rotate", f"KEY={label}"], {"PMOVES_ROTATE_VALUE": value}) != 0:
                self.log.append(f"secrets-rotate KEY={label} FAILED")
                return False
        return True

    def gate(self, before: List[Stack], expect_secret: str) -> List[str]:
        """After the funnel: only keys whose value carried the secret may change."""
        after = {st.name: st for st in self.gate_renderer()}
        problems = []
        for st in before:
            new_st = after.get(st.name)
            if new_st is None:
                problems.append(f"stack {st.name} no longer renders")
                continue
            for svc, spec in st.rendered.items():
                old_env, new_env = _env_of(spec), _env_of(new_st.rendered.get(svc, {}))
                for k in sorted(set(old_env) | set(new_env)):
                    o, n = old_env.get(k, ""), new_env.get(k, "")
                    if o == n:
                        continue
                    target = k == self.disc.key or k in self.disc.linked or _contains_secret(o, self.disc.value)
                    if not target or not carries(n, expect_secret):
                        problems.append(f"{st.name}/{svc}: {k} changed {mask(o)} -> {mask(n)} (not the target)")
                if argv_masked(spec.get("command"), self.disc.value) != \
                        argv_masked(new_st.rendered.get(svc, {}).get("command"), expect_secret):
                    problems.append(f"{st.name}/{svc}: command changed beyond the secret")
        return problems

    def recreate(self) -> bool:
        for b in self.batches:
            self.log.append(f"make {' '.join(b['target'])} (pins: {sorted(b['pins'])})")
            if self.rt.make(b["target"], b["pins"]) != 0:
                self.log.append(f"recreate FAILED at {b['target']}")
                return False
        return True

    def verify(self, secret: str) -> List[str]:
        deadline = time.monotonic() + self.timeout
        user = None
        if self.probe is not None:
            for st in self.stacks:
                for spec in st.rendered.values():
                    user = user or _env_of(spec).get(self.probe.user_key)
        while True:
            problems = []
            running = self.rt.running()
            for m in self.pf.members:
                cid = running.get((m.consumer.project, m.consumer.service))
                if not cid:
                    problems.append(f"{m.consumer.ident}: not running")
                    continue
                if cid == m.container:
                    problems.append(f"{m.consumer.ident}: same container as before (not recreated)")
                    continue
                h = health_of(self.rt.inspect(cid))
                if m.baseline_health in ("healthy", "running") and h not in ("healthy", "running"):
                    problems.append(f"{m.consumer.ident}: {h}")
            if self.probe is not None:
                try:
                    conns = self.probe.connections(running)
                    for m in self.pf.members:
                        if m.baseline_conns and not conns.get((m.consumer.project, m.consumer.service)):
                            problems.append(f"{m.consumer.ident}: had {m.baseline_conns} bus connection(s), now 0")
                    if self.probe.auth_accepted(user or "", secret) is not True:
                        problems.append("server does not accept the expected credential")
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"probe failed: {exc}")
            if not problems or time.monotonic() >= deadline:
                return problems
            time.sleep(self.poll)

    def run(self) -> Outcome:
        new = _secrets.token_urlsafe(36)
        state = self.save_state(new)
        self.log.append(f"state saved (0600): {state}")
        if not self.rotate_to(self.label_values(new)):
            return self.rollback("mint failed", recreate=False, state=state)
        problems = self.gate(self.stacks, new)
        if problems:
            self.log += [f"GATE: {p}" for p in problems[:40]]
            return self.rollback("post-funnel gate found non-target changes", recreate=False, state=state)
        if not self.recreate():
            return self.rollback("recreate failed", recreate=True, state=state)
        problems = self.verify(new)
        if problems:
            self.log += [f"VERIFY: {p}" for p in problems]
            return self.rollback("verify failed", recreate=True, state=state)
        state.unlink()
        return Outcome("rotated", EXIT_OK, [f"{self.disc.key} {mask(self.disc.value)} -> {mask(new)}"])

    def rollback(self, why: str, *, recreate: bool, state: Path) -> Outcome:
        self.log.append(f"ROLLBACK ({why})")
        old = json.loads(state.read_text())["restore"]
        ok = self.rotate_to(old)
        residue = self.gate(self.stacks, self.disc.value) if ok else []
        if residue:
            # The value is back, but the funnel changed something else (typically a
            # CI bundle became a local export and prod-only keys dropped out).
            self.log += [f"RESIDUE: {p}" for p in residue[:40]]
            return Outcome("rollback-INCOMPLETE", EXIT_ROLLBACK_FAILED,
                           [why, "old value restored but env files still differ from before the rotation; "
                                 "restore the bundle: PMOVES_NODE=<node> make -C pmoves secrets-pull && "
                                 "make -C pmoves secrets-funnel-sync-from-bundle",
                            f"restore values kept at {state} (0600)"])
        if ok and recreate:
            for m in self.pf.members:  # the containers from the failed attempt are the new baseline
                cid = self.rt.running().get((m.consumer.project, m.consumer.service))
                m.container = cid or m.container
            ok = self.recreate() and not self.verify(self.disc.value)
        if ok:
            state.unlink()
            return Outcome("rolled-back", EXIT_FINDINGS, [why])
        return Outcome("rollback-FAILED", EXIT_ROLLBACK_FAILED,
                       [why, f"restore values kept at {state} (0600); restore with secrets-rotate per label"])


# --------------------------------------------------------------------------- record
def record(rt: Runtime, key: str, outcome: Outcome, node: str, owner: str, members: List[Member]) -> List[str]:
    summary = (f"coordinated rotation {key} @ {node}: {outcome.status}; "
               f"{'; '.join(d for d in outcome.detail if 'rotation-state' not in d)}; "
               f"recreate set {len(members)}: " + ", ".join(m.consumer.ident for m in members))
    # make re-parses SCOPE; keep shell-active characters out of it.
    summary = re.sub(r"[`$\\\"']", "", summary)
    notes = []
    if rt.make(["register-note", f"OWNER={owner}", f"SCOPE={summary}"]) != 0:
        notes.append("register-note FAILED (record the outcome by hand)")
    if rt.make(["sign-trail"], {"AGENT": owner, "SUMMARY": summary, "PHASE": "secret-rotation"}) != 0:
        notes.append("sign-trail FAILED (sign the trail by hand)")
    return notes


# --------------------------------------------------------------------------- cli
def load_config(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text()) or {}


def build_probe(rt: Runtime, cfg: dict, key: str) -> Optional[NatsProbe]:
    spec = (cfg.get("probes") or {}).get(key)
    if not spec or spec.get("kind") == "none":
        return None
    if spec.get("kind") == "nats":
        return NatsProbe(rt, spec["monitor_url"], int(spec.get("port", 4222)), spec.get("user_key", "NATS_USER"))
    raise SystemExit(f"unknown probe kind {spec.get('kind')!r} for {key}")


def _csv(s: Optional[str]) -> set:
    return {x.strip() for x in (s or "").split(",") if x.strip()}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--key", required=True)
    ap.add_argument("--stack", action="append", required=True, help="NAME=<compose command> (first = main)")
    ap.add_argument("--execute", action="store_true", help="act; default is DRY_RUN (plan only)")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--node", default=os.environ.get("PMOVES_NODE") or socket.gethostname().split(".")[0])
    ap.add_argument("--owner", default="B850-CLAUDE (Knuckles)")
    ap.add_argument("--ack-drift", default="")
    ap.add_argument("--include", default="")
    ap.add_argument("--pin", default="", help="svc=image,... (overrides the service's ${*_IMAGE} var)")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    ap.add_argument("--verify-timeout", type=float, default=180.0)
    ap.add_argument("--poll", type=float, default=5.0)
    ap.add_argument("--root", type=Path, default=PMOVES_DIR, help="pmoves/ dir: compose cwd and make -C target")
    ap.add_argument("--docker", default="docker")
    ap.add_argument("--make", default="make")
    ap.add_argument("--fixture", action="append", default=[],
                    help="NAME=rendered.json:noint.json (tests; skips compose)")
    ap.add_argument("--gate-fixture", action="append", default=[], help="NAME=rendered.json:noint.json for the post-funnel render (tests)")
    ap.add_argument("--chit-bundle", type=Path, help="CHIT_EXPORT_PATH; a CI provenance marker beside it needs --ack-bundle-local")
    ap.add_argument("--ack-bundle-local", action="store_true")
    ap.add_argument("--no-record", action="store_true")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)

    verdict: dict = {"key": args.key, "node": args.node, "mode": "execute" if args.execute else "dry-run"}

    def finish(code: int) -> int:
        verdict["exit_code"] = code
        if args.json:
            args.json.write_text(json.dumps(verdict, indent=2, default=sorted))
        return code

    rt = Runtime(docker=args.docker, make=args.make, make_dir=args.root)

    def fixtures(specs):
        out = {}
        for spec in specs:
            name, _, paths = spec.partition("=")
            r, _, n = paths.partition(":")
            out[name] = (r, n)
        return out

    try:
        cfg = load_config(args.config)
        roads = Roads(cfg.get("roads") or {})
        stacks = load_stacks(rt, args.stack, fixtures(args.fixture))
        disc = discover(stacks, args.key, load_manifest_labels(args.manifest))
        probe = build_probe(rt, cfg, args.key)
        pins = dict(p.split("=", 1) for p in _csv(args.pin))
        pf = preflight(rt, stacks, disc, ack_drift=_csv(args.ack_drift), include=_csv(args.include),
                       pins=pins, probe=probe, roads=roads)
    except Refusal as r:
        print(f"REFUSED [{r.code}] {r.detail}")
        verdict["refusals"] = [[r.code, r.detail]]
        return finish(EXIT_FINDINGS)
    except CouldNotMeasure as exc:
        print(f"COULD-NOT-MEASURE: {exc}")
        verdict["could_not_measure"] = str(exc)
        return finish(EXIT_CNM)

    if args.chit_bundle and Path(f"{args.chit_bundle}.provenance").exists() and not args.ack_bundle_local:
        pf.refusals.append(("bundle-provenance",
                            "the CHIT bundle is CI-pulled; secrets-rotate re-exports it LOCALLY and prod-only keys "
                            "drop out of every tier file. The post-funnel gate would catch it and roll back. "
                            "Acknowledge with ACK_BUNDLE_LOCAL=1, or rotate at the producer and secrets-pull"))
    verdict["discovery"] = disc.masked()
    print(f"== DISCOVER {args.key} (class {mask(disc.value)})")
    print(f"   rotate labels (CHIT manifest): {disc.manifest_labels}")
    print(f"   derived keys (follow by interpolation): {disc.derived}")
    for ident, c in sorted(disc.consumers.items()):
        print(f"   {ident:40} {','.join(sorted(c.roles))}")
    print(f"== PREFLIGHT  members={len(pf.members)} carriers(not recreated)={len(pf.carriers)} "
          f"not-running(pick up on next start)={len(pf.not_running)}")
    for w in pf.warnings:
        print(f"   WARN {w}")
    for code, detail in pf.refusals:
        print(f"   REFUSE [{code}] {detail}")
    verdict.update(carriers=pf.carriers, not_running=pf.not_running, warnings=pf.warnings,
                   refusals=pf.refusals, probe_baseline=pf.probe_baseline)

    batches = plan_batches(stacks, pf.members, roads) if pf.members else []
    expected = f"ROTATE {args.key} @ {args.node}"
    print("== PLAN (recreate set, in order; rollback replays the same set after restoring the old value)")
    for i, b in enumerate(batches, 1):
        print(f"   {i:2}. make {' '.join(b['target'])}"
              + (f"   pins: {', '.join(f'{k}={v}' for k, v in b['pins'].items())}" if b["pins"] else ""))
    print(f"   mint: make secrets-rotate KEY=<label> for {disc.manifest_labels} (value via PMOVES_ROTATE_VALUE)")
    print(f"   execute with: DRY_RUN=0 CONFIRM='{expected}'")
    verdict["plan"] = [{"target": b["target"], "members": [m.consumer.ident for m in b["members"]]} for b in batches]

    if pf.refusals:
        return finish(EXIT_CNM if all(c == "probe-unavailable" for c, _ in pf.refusals) else EXIT_FINDINGS)
    if not args.execute:
        return finish(EXIT_OK)
    if args.confirm != expected:
        print(f"REFUSED: CONFIRM must be exactly {expected!r}")
        verdict["refusals"] = [["confirm", "confirmation string mismatch"]]
        return finish(EXIT_FINDINGS)

    gate_fx = fixtures(args.gate_fixture)
    ex = Executor(rt, stacks, disc, pf, batches, probe=probe, state_dir=args.state_dir,
                  verify_timeout=args.verify_timeout, poll=args.poll,
                  gate_renderer=lambda: load_stacks(rt, args.stack, gate_fx))
    outcome = ex.run()
    for line in ex.log:
        print(f"   {line}")
    print(f"== {outcome.status.upper()}: {'; '.join(outcome.detail)}")
    verdict.update(outcome=outcome.status, log=ex.log)
    if not args.no_record:
        for note in record(rt, args.key, outcome, args.node, args.owner, pf.members):
            print(f"   WARN {note}")
    return finish(outcome.exit_code)


if __name__ == "__main__":
    sys.exit(main())
