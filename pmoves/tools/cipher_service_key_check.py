#!/usr/bin/env python3
"""Will the key cipher presents for per-agent token lookups be admitted?

WHY THIS EXISTS
---------------
Every ``cipher_<uuid>`` bearer is resolved by ``Pmoves-cipher/src/pmoves/auth.ts``
with a PostgREST lookup that presents the shim's OWN service key
(``SUPABASE_SERVICE_KEY`` in the container). When that key is refused, every
agent on the node gets 503 at once and ``/health`` reads ``per_agent_auth:
unavailable, token lookup returned HTTP 401``. That message cannot say WHY.

Two gates judge the key, and they fail differently:

1. **Kong key-auth** (``PMOVES-supabase/docker/volumes/api/kong.yml``, route
   ``rest-v1``) wants an EXACT match with a ``service_role`` consumer key:
   ``$SUPABASE_SERVICE_KEY`` or ``$SUPABASE_SECRET_KEY`` as rendered from
   ``supabase-kong``'s env WHEN KONG STARTED. A different value, even a valid
   JWT, is refused (kong 3.x: 401 ``Unauthorized``) before PostgREST sees it.
2. **PostgREST** verifies the JWT signature against ``PGRST_JWT_SECRET``
   (``${SUPABASE_JWT_SECRET:-${JWT_SECRET:-}}``) and then its ``exp`` claim.

Measured on knuckles 2026-10-22: cipher presented ``CIPHER_DB_SERVICE_KEY``, a
service_role JWT hand-pasted into ``pmoves/.env.local`` per ``df0218537``. It
expired 2026-10-21. The funnel refresh (#3410) renews ``SUPABASE_SERVICE_ROLE_KEY``
and ``SERVICE_ROLE_KEY`` but never touches ``.env.local``, and the paste shadowed
both.

WHAT IT CHECKS (read-only; never prints a key, a digest, or a claim value other
than ``role``)
-----------------------------------------------------------------------------
STATIC (always). Expressions come from the compose file on disk, values from the
same ``--env-file`` list the Makefile hands ``docker compose`` (process env wins,
as in compose), so this judges what the NEXT ``up-cipher`` would present:

* ``present`` / ``key_source``   non-empty, and WHICH variable NAME supplied it
* ``role`` / ``exp_in_past``     decoded claims (signature not trusted for these)
* ``matches_kong_config``        the value equals one of Kong's CONFIGURED
                                 consumer keys, evaluated from the same env.
                                 NOT what the running Kong holds (see below)
* ``signature_verifies``         HS256 under PostgREST's secret expression
* ``jwt_secrets_agree``          JWT_SECRET == SUPABASE_JWT_SECRET (bool only)
* ``kong_order_drift``           other services that present a service key in
                                 the REVERSE of Kong's order
* ``CIPHER_DB_SERVICE_KEY`` set  -> WARN (retired; a stale paste). Also read from
                                 ``--env-local`` by presence only (names), since
                                 under SUPABASE_RUNTIME=compose the overlay is not
                                 in compose's env-file list

LIVE (``--container``, the authority on what is running). Reads the running
``cipher-api`` key's role/exp (decoded inside the container) and compares digests
in-process (never printed) with the env key and with the consumer keys the
running ``supabase-kong`` was started with. A funnel refresh without a Kong
recreate shows up here as ``kong_live_mismatch``. ``--probe`` performs cipher's
own lookup from inside the container (read-only ``GET ...?select=agent_id&limit=0``)
and classifies a refusal: Kong (``lookup_refused_gateway``), expired
(``PGRST303``), signature (``PGRST301``).

KNOWN LIMITS. A DB-backed Kong with seeded consumers (pre ``KONG_DATABASE=off``),
or a ``SUPABASE_REST_URL`` pointing cipher at a different Kong (remote, CLI
runtime), is visible ONLY to ``--probe``; the static and digest facets compare
against the compose-defined ``supabase-kong``.

Exit codes (``make`` collapses every nonzero exit to 2, so the last line is a
structured ``CIPHER_AUTH_VERDICT=<json>`` that survives it):
  0  every requested facet measured and clean
  1  findings: missing, expired, wrong role, wrong pair (Kong or signature),
     live Kong/cipher mismatch, or the running container's lookup is refused
  3  could not measure ANY requested facet (no env, unreadable compose, opaque
     key, container/probe unreadable, probe timed out, crash). NOT a pass

Usage:
  make -C pmoves cipher-auth-check                 # static (env + compose)
  make -C pmoves cipher-auth-check CONTAINER=1     # + running cipher-api and Kong
  make -C pmoves cipher-auth-check CONTAINER=1 PROBE=1
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

_TOOLS_DIR = Path(__file__).resolve().parent
_PMOVES_DIR = _TOOLS_DIR.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

# (service, variable) pairs read out of compose. Names, not values.
CIPHER = ("cipher-api", "SUPABASE_SERVICE_KEY")
GATEWAY = ("supabase-kong", "SUPABASE_SERVICE_KEY")
# kong.yml consumer service_role carries a second credential ($SUPABASE_SECRET_KEY,
# an opaque sb_secret_* key on nodes that have one).
GATEWAY_SECRET = ("supabase-kong", "SUPABASE_SECRET_KEY")
PGRST_SECRET = ("supabase-postgrest", "PGRST_JWT_SECRET")

RETIRED_OVERRIDE = "CIPHER_DB_SERVICE_KEY"
# Live names a service_role key travels under on this mesh. Probed by NAME for the
# wrong-pair diagnosis only; values never leave the process. The retired override
# is deliberately NOT a candidate: recommending it would steer back to the paste.
CANDIDATE_NAMES = ("SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY")
EXPECTED_ROLE = "service_role"
EXPIRY_WARN_S = 30 * 24 * 3600

# Kong's order: canonical first. The REVERSE order presents a different value
# from Kong's consumer key wherever the two names differ.
_REVERSED_ORDER = re.compile(r"\$\{SERVICE_ROLE_KEY:?-\$\{SUPABASE_SERVICE_ROLE_KEY")

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class Unresolvable(ValueError):
    """A ``${VAR:?}`` / ``${VAR?}`` guard fired. Carries the NAME only."""


# ── compose-style interpolation ─────────────────────────────────────────────


def _match_brace(text: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced ${ in expression")


def _eval_braced(body: str, env: Mapping[str, str]) -> Tuple[str, Optional[str]]:
    m = _NAME.match(body)
    if not m:
        raise ValueError("malformed ${...} in expression")
    name, rest = m.group(0), body[m.end():]
    set_ = name in env
    nonempty = bool(env.get(name))
    for op in (":-", ":?", ":+", "-", "?", "+"):
        if rest.startswith(op):
            arg = rest[len(op):]
            break
    else:
        if rest:
            raise ValueError("unsupported ${...} operator")
        return env.get(name, ""), (name if nonempty else None)
    if op in (":-", "-"):
        if nonempty or (op == "-" and set_):
            return env[name], name
        return interpolate_with_source(arg, env)
    if op in (":?", "?"):
        if nonempty or (op == "?" and set_):
            return env[name], name
        raise Unresolvable(name)
    # :+ / + : alternative value when set
    if nonempty or (op == "+" and set_):
        return interpolate_with_source(arg, env)
    return "", None


def interpolate_with_source(text: str, env: Mapping[str, str]) -> Tuple[str, Optional[str]]:
    """Compose-style ``${...}`` expansion -> (value, NAME that supplied it).

    The source is the variable whose value was taken when the whole expression
    is a single ``${...}`` chain (``${A:-${B:-}}`` -> ``A`` or ``B``); a mixed
    literal reports None. Only the name is ever surfaced, never the value.
    """
    out: List[str] = []
    sources: List[Optional[str]] = []
    literal = False
    i = 0
    while i < len(text):
        if text.startswith("$$", i):
            out.append("$")
            literal = True
            i += 2
        elif text.startswith("${", i):
            end = _match_brace(text, i + 1)
            value, src = _eval_braced(text[i + 2:end], env)
            out.append(value)
            sources.append(src)
            i = end + 1
        elif text[i] == "$" and _NAME.match(text, i + 1):
            m = _NAME.match(text, i + 1)
            assert m is not None
            name = m.group(0)
            out.append(env.get(name, ""))
            sources.append(name if env.get(name) else None)
            i = m.end()
        else:
            out.append(text[i])
            literal = True
            i += 1
    source = sources[0] if len(sources) == 1 and not literal else None
    return "".join(out), source


def interpolate(text: str, env: Mapping[str, str]) -> str:
    return interpolate_with_source(text, env)[0]


# ── compose + env loading ───────────────────────────────────────────────────


def compose_env_expr(docs: Sequence[Mapping[str, Any]], service: str, var: str) -> Optional[str]:
    """The raw (uninterpolated) expression ``service`` assigns to ``var``; last file wins."""
    found: Optional[str] = None
    for doc in docs:
        svc = ((doc or {}).get("services") or {}).get(service) or {}
        env = svc.get("environment")
        if isinstance(env, Mapping):
            if var in env:
                found = "" if env[var] is None else str(env[var])
        elif isinstance(env, list):
            for item in env:
                if isinstance(item, str) and item.split("=", 1)[0] == var:
                    found = item.split("=", 1)[1] if "=" in item else ""
    return found


def load_compose(paths: Sequence[Path]) -> List[Mapping[str, Any]]:
    import yaml  # local: only the CLI path needs it

    docs = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            docs.append(yaml.safe_load(fh) or {})
    return docs


def resolve_env(
    env_files: Sequence[Path],
    base: Mapping[str, str],
    parse: Optional[Callable[[Path], Dict[str, str]]] = None,
) -> Tuple[Dict[str, str], Dict[str, List[str]], List[str]]:
    """``(env, provenance, notes)`` with compose precedence.

    Later ``--env-file`` overrides earlier; the process environment overrides
    every file, INCLUDING when exported empty (compose treats set-but-empty as
    set — the shell-env-shadows-env-file trap). *provenance* maps a name to the
    files (basenames) and/or ``process-env`` that set it, for the WARN only.
    """
    if parse is None:
        from _secrets_common import parse_env_file as parse  # type: ignore[no-redef]
    merged: Dict[str, str] = {}
    provenance: Dict[str, List[str]] = {}
    notes: List[str] = []
    for path in env_files:
        if not path.is_file():
            notes.append(f"env file not found, skipped: {path.name}")
            continue
        for key, raw in parse(path).items():
            value = raw
            if "${" in raw or "$" in raw:
                try:
                    value = interpolate(raw, {**merged, **base})
                except (Unresolvable, ValueError):
                    value = raw
            merged[key] = value
            provenance.setdefault(key, []).append(path.name)
    for key, value in base.items():
        merged[key] = value
        provenance.setdefault(key, []).append("process-env")
    return merged, provenance, notes


# ── JWT inspection (claims only; signature check returns a bool) ────────────


def _b64url_decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def jwt_parts(value: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    parts = value.split(".")
    if len(parts) != 3:
        return None
    try:
        header = json.loads(_b64url_decode(parts[0]))
        claims = json.loads(_b64url_decode(parts[1]))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(header, dict) or not isinstance(claims, dict):
        return None
    return header, claims


def hs256_verifies(value: str, secret: str) -> Optional[bool]:
    """True/False for an HS256 JWT under *secret*; None if not HS256."""
    decoded = jwt_parts(value)
    if decoded is None or decoded[0].get("alg") != "HS256":
        return None
    signing_input, _, sig = value.rpartition(".")
    expected = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    try:
        given = _b64url_decode(sig)
    except ValueError:
        return False
    return hmac.compare_digest(expected, given)


# ── assessment ──────────────────────────────────────────────────────────────


def _finding(code: str, detail: str) -> Dict[str, str]:
    return {"code": code, "detail": detail}


def _safe_interp(expr: Optional[str], env: Mapping[str, str]) -> str:
    if expr is None:
        return ""
    try:
        return interpolate(expr, env)
    except (Unresolvable, ValueError):
        return ""


def _live_service_role(value: str, secret: str, now: int) -> bool:
    """Verifies under *secret*, role service_role, and not expired."""
    decoded = jwt_parts(value)
    if decoded is None or hs256_verifies(value, secret) is not True:
        return False
    claims = decoded[1]
    exp = claims.get("exp")
    return claims.get("role") == EXPECTED_ROLE and isinstance(exp, (int, float)) and exp > now


def kong_order_drift(docs: Sequence[Mapping[str, Any]]) -> List[str]:
    """``service:VAR`` for every env value presenting the service key in the
    REVERSE of Kong's order (``${SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_ROLE_KEY``),
    including values embedded in JSON (Agent Zero's postgrest MCP --apiKey)."""
    sites: List[str] = []
    for doc in docs:
        for svc_name, svc in ((doc or {}).get("services") or {}).items():
            env = (svc or {}).get("environment")
            items = (
                [f"{k}={'' if v is None else v}" for k, v in env.items()]
                if isinstance(env, Mapping) else (env or [])
            )
            for item in items:
                if isinstance(item, str) and _REVERSED_ORDER.search(item):
                    site = f"{svc_name}:{item.split('=', 1)[0]}"
                    if site not in sites:
                        sites.append(site)
    return sites


def assess(
    env: Mapping[str, str],
    exprs: Mapping[str, Optional[str]],
    provenance: Optional[Mapping[str, List[str]]] = None,
    now: Optional[int] = None,
    overlay_has_retired: Optional[bool] = None,
) -> Dict[str, Any]:
    """Verdict for the key the cipher expression resolves to in *env*.

    *exprs* holds the raw compose expressions under ``cipher``, ``gateway``,
    ``gateway_secret`` and ``pgrst_secret``. Nothing returned is a key, digest
    or secret.
    """
    now = int(time.time()) if now is None else now
    provenance = provenance or {}
    findings: List[Dict[str, str]] = []
    warnings: List[str] = []
    unmeasured: List[str] = []
    facets: Dict[str, Any] = {
        "present": None,
        "key_source": None,
        "shape": None,
        "role": None,
        "exp_in_past": None,
        "matches_kong_config": None,
        "signature_verifies": None,
        "jwt_secrets_agree": None,
    }

    cipher_expr = exprs.get("cipher")
    reads_retired = RETIRED_OVERRIDE in (cipher_expr or "")
    retire_road = " Remove it on the road: make -C pmoves env-local-unset KEY=CIPHER_DB_SERVICE_KEY"
    if env.get(RETIRED_OVERRIDE):
        where = ", ".join(sorted(set(provenance.get(RETIRED_OVERRIDE, [])))) or "environment"
        warnings.append(
            f"{RETIRED_OVERRIDE} is set ({where}). It is retired: a pasted value is "
            "never refreshed by the funnel and shadowed the refreshed keys when it "
            + ("expired. The compose cipher-api expression on disk STILL READS IT, so it "
               "decides the key below." if reads_retired else
               "expired. Compose no longer reads it, but a branch that does would.")
            + retire_road
        )
    elif overlay_has_retired:
        warnings.append(
            f"{RETIRED_OVERRIDE} is defined in the .env.local overlay, which is NOT in "
            "compose's env-file list on this runtime (SUPABASE_RUNTIME=compose without "
            "INCLUDE_ENV_LOCAL_IN_COMPOSE=1), so compose does not read it today. It "
            "would decide the key on a runtime or branch that does." + retire_road
        )

    a, b = env.get("JWT_SECRET"), env.get("SUPABASE_JWT_SECRET")
    if a and b:
        facets["jwt_secrets_agree"] = hmac.compare_digest(a.encode(), b.encode())
        if not facets["jwt_secrets_agree"]:
            warnings.append(
                "JWT_SECRET and SUPABASE_JWT_SECRET differ. Every Supabase verifier reads "
                "SUPABASE_JWT_SECRET first, and so does the funnel since #3433; a key minted "
                "under JWT_SECRET is admitted by Kong and refused by PostgREST (PGRST301)"
            )

    gateway_expr = exprs.get("gateway")
    if cipher_expr is None:
        unmeasured.append("compose has no cipher-api SUPABASE_SERVICE_KEY entry")
        return _verdict(facets, findings, warnings, unmeasured)

    facets["expressions_match"] = (
        None if gateway_expr is None else cipher_expr.strip() == gateway_expr.strip()
    )
    if facets["expressions_match"] is False:
        warnings.append(
            "compose wiring drift: cipher-api's SUPABASE_SERVICE_KEY expression is not "
            "supabase-kong's service_role consumer expression, so the two can resolve "
            "to different keys on any node"
        )
    drift = exprs.get("kong_order_drift")
    if drift is not None:
        facets["kong_order_drift"] = list(drift)
        if drift:
            warnings.append(
                "service keys presented in the REVERSE of Kong's order "
                "(${SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_ROLE_KEY...}) at: " + ", ".join(drift)
                + ". Wherever the two names differ these are refused by Kong (same defect class)"
            )

    try:
        key, source = interpolate_with_source(cipher_expr, env)
    except Unresolvable as exc:
        findings.append(_finding("missing", f"compose guard ${{{exc}:?}} fired; the key cannot resolve"))
        facets["present"] = False
        return _verdict(facets, findings, warnings, unmeasured)
    except ValueError:
        unmeasured.append("cipher expression could not be parsed")
        return _verdict(facets, findings, warnings, unmeasured)

    facets["present"] = bool(key)
    facets["key_source"] = source
    if not key:
        findings.append(_finding(
            "missing",
            "the cipher expression resolves to an empty value; auth.ts reports "
            "'SUPABASE_SERVICE_KEY not set' and every lookup is 503",
        ))
        return _verdict(facets, findings, warnings, unmeasured)

    decoded = jwt_parts(key)
    if decoded is None:
        facets["shape"] = "opaque"
        unmeasured.append("key is not a JWT (opaque sb_* style?): role/exp cannot be read")
    else:
        facets["shape"] = "jwt"
        claims = decoded[1]
        facets["role"] = claims.get("role") if isinstance(claims.get("role"), str) else None
        exp = claims.get("exp")
        if isinstance(exp, (int, float)):
            facets["exp_in_past"] = exp <= now
            if exp <= now:
                findings.append(_finding(
                    "expired",
                    f"the key supplied by {source or 'the cipher expression'} has expired; "
                    "PostgREST answers 401 to every lookup",
                ))
            elif exp - now < EXPIRY_WARN_S:
                warnings.append("key expires within 30 days")
        else:
            unmeasured.append("JWT carries no numeric exp claim")
        if facets["role"] != EXPECTED_ROLE:
            findings.append(_finding(
                "wrong_role",
                f"key role is {facets['role']!r}, not 'service_role'; "
                "the token table is not readable with it",
            ))

    if gateway_expr is None:
        unmeasured.append("compose has no supabase-kong SUPABASE_SERVICE_KEY entry")
    else:
        kong_keys = [k for k in (_safe_interp(gateway_expr, env),
                                 _safe_interp(exprs.get("gateway_secret"), env)) if k]
        if not kong_keys:
            unmeasured.append("Kong's service_role consumer keys do not resolve in this env")
        else:
            facets["matches_kong_config"] = any(
                hmac.compare_digest(k.encode(), key.encode()) for k in kong_keys
            )
            if not facets["matches_kong_config"]:
                findings.append(_finding(
                    "wrong_pair_gateway",
                    f"cipher presents {source or 'its expression'}'s value, but neither of the "
                    "consumer keys Kong is CONFIGURED with (SUPABASE_SERVICE_KEY, "
                    "SUPABASE_SECRET_KEY, same env) is that value; Kong key-auth refuses it "
                    "with 401 before PostgREST sees it",
                ))

    secret_expr = exprs.get("pgrst_secret")
    if decoded is not None and secret_expr is not None:
        secret = _safe_interp(secret_expr, env)
        if not secret:
            unmeasured.append("PostgREST's JWT secret does not resolve in this env")
        else:
            facets["signature_verifies"] = hs256_verifies(key, secret)
            if facets["signature_verifies"] is False:
                verifying = [
                    name for name in CANDIDATE_NAMES
                    if env.get(name) and _live_service_role(env[name], secret, now)
                ]
                facets["verifying_names"] = verifying
                cause = (
                    "JWT_SECRET and SUPABASE_JWT_SECRET differ (see WARN), so a key minted "
                    "under JWT_SECRET cannot verify. "
                    if facets["jwt_secrets_agree"] is False else ""
                )
                also = (
                    f"Live service_role keys that DO verify: {', '.join(verifying)} (Kong "
                    "still admits only its consumer key, so do not paste one of them). "
                    if verifying else "No live candidate key verifies. "
                )
                findings.append(_finding(
                    "wrong_pair_signature",
                    "the key's HS256 signature does not verify under the secret PostgREST "
                    "is configured with (PGRST_JWT_SECRET); PostgREST answers 401 PGRST301. "
                    + cause + also
                    + "Remedy: make -C pmoves secrets-funnel. It re-mints the key only if it is "
                    "provably funnel-minted (iss supabase-local) and SUPABASE_RUNTIME=compose "
                    "with local Supabase URLs; otherwise it leaves the key and WARNs by name. "
                    "Then recreate every consumer it lists (supabase-kong first)",
                ))
            elif facets["signature_verifies"] is None:
                unmeasured.append("key is not HS256; signature not checked")

    return _verdict(facets, findings, warnings, unmeasured)


def _verdict(facets, findings, warnings, unmeasured, gaps: Sequence[str] = ()) -> Dict[str, Any]:
    core_measured = (
        facets.get("present") is not None
        and (facets.get("present") is False
             or (facets.get("exp_in_past") is not None
                 and facets.get("matches_kong_config") is not None))
    )
    if findings:
        status, code = "finding", 1
    elif core_measured and not gaps:
        status, code = "ok", 0
    else:
        status, code = "could_not_measure", 3
    return {
        "tool": "cipher-auth-check",
        "status": status,
        "exit": code,
        "facets": facets,
        "findings": findings,
        "warnings": warnings,
        "unmeasured": unmeasured,
    }


# ── running containers (opt-in) ─────────────────────────────────────────────

# Runs INSIDE cipher-api with its own node. Emits JSON with role, exp, a digest
# for in-process comparison, and (optionally) the lookup's status + error code.
# No key, no body text beyond a PGRST code, leaves the container.
_NODE_SCRIPT = r"""
const k = process.env.SUPABASE_SERVICE_KEY || '';
const out = {present: !!k};
if (k) {
  out.sha256 = require('crypto').createHash('sha256').update(k).digest('hex');
  const p = k.split('.');
  if (p.length === 3) {
    try {
      const c = JSON.parse(Buffer.from(p[1], 'base64url').toString());
      out.role = typeof c.role === 'string' ? c.role : null;
      out.exp = typeof c.exp === 'number' ? c.exp : null;
    } catch (e) { out.decode_error = true; }
  } else { out.opaque = true; }
}
const done = () => console.log(JSON.stringify(out));
if (k && __PROBE__) {
  const u = (process.env.SUPABASE_REST_URL || 'http://supabase-kong:8000/rest/v1')
    + '/cipher_agent_tokens?select=agent_id&limit=0';
  fetch(u, {headers: {apikey: k, Authorization: 'Bearer ' + k, 'Accept-Profile': 'pmoves_core'},
            signal: AbortSignal.timeout(3000)})
    .then(async r => {
      const t = (await r.text()).slice(0, 2000);
      const m = t.match(/PGRST\d{3}/);
      // Kong key-auth wording: 3.x "Unauthorized" / "No API key found in request";
      // 2.x "Invalid authentication credentials". Python also treats any 401/403
      // without a PGRST code as the gateway.
      out.probe = {status: r.status, code: m ? m[0] : null,
                   expired: /expired/i.test(t),
                   kong: !m && /Unauthorized|No API key found|Invalid authentication credentials|no credentials/i.test(t)};
      done();
    })
    .catch(e => { out.probe = {error: e && e.name ? e.name : 'error'}; done(); });
} else { done(); }
"""

# Runs INSIDE supabase-kong (ubuntu-based image: sh + sha256sum). Emits one
# digest per consumer credential, or '-' when unset. Never the value.
_KONG_SCRIPT = (
    'for v in "$SUPABASE_SERVICE_KEY" "$SUPABASE_SECRET_KEY"; do '
    'if [ -n "$v" ]; then printf %s "$v" | sha256sum | cut -d" " -f1; else echo -; fi; done'
)

Runner = Callable[[List[str]], Tuple[int, str]]


def _default_runner(cmd: List[str]) -> Tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return proc.returncode, proc.stdout


def discover_container(runner: Runner, service: str = "cipher-api") -> Optional[str]:
    rc, out = runner([
        "docker", "ps", "--filter", f"label=com.docker.compose.service={service}",
        "--format", "{{.Names}}",
    ])
    names = [n for n in out.splitlines() if n.strip()] if rc == 0 else []
    return names[0].strip() if names else None


def classify_probe(probe: Mapping[str, Any]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """``(finding, unmeasured_note)`` for the in-container lookup result."""
    if "error" in probe:
        return None, f"in-container lookup could not complete ({probe['error']})"
    status = probe.get("status")
    if not isinstance(status, int):
        return None, "in-container lookup returned no HTTP status"
    if status == 200:
        return None, None
    code = probe.get("code")
    if code == "PGRST303" or (code and probe.get("expired")):
        return _finding("lookup_refused_expired", f"PostgREST: key expired (HTTP {status}, {code})"), None
    if code == "PGRST301":
        return _finding(
            "lookup_refused_signature",
            f"PostgREST: signature invalid under its secret (HTTP {status}, {code})",
        ), None
    if probe.get("kong") or (status in (401, 403) and not code):
        return _finding(
            "lookup_refused_gateway",
            f"Kong refused the running container's key (HTTP {status}, no PGRST code): it is "
            "not a service_role consumer key the running Kong holds. After a funnel refresh "
            "supabase-kong keeps the old key until it is recreated",
        ), None
    return _finding("lookup_http_error", f"lookup returned HTTP {status} ({code or 'no PGRST code'})"), None


def assess_container(
    verdict: Dict[str, Any],
    env_key: Optional[str],
    runner: Runner,
    probe: bool,
    now: Optional[int] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add the LIVE facets. Any requested live facet that cannot be measured is a
    gap, and a gap makes the verdict could-not-measure (3), never ok."""
    now = int(time.time()) if now is None else now
    gaps: List[str] = []

    def gap(note: str) -> None:
        gaps.append(note)
        verdict["unmeasured"].append(note)

    name = name or discover_container(runner)
    facet: Dict[str, Any] = {"name": name}
    verdict["facets"]["container"] = facet
    if not name:
        gap("no running cipher-api container found")
        return _reverdict(verdict, gaps)
    script = _NODE_SCRIPT.replace("__PROBE__", "true" if probe else "false")
    try:
        rc, out = runner(["docker", "exec", name, "node", "-e", script])
        report = json.loads(out.strip().splitlines()[-1]) if rc == 0 and out.strip() else None
    except (ValueError, IndexError, OSError, subprocess.SubprocessError):
        report = None
    if not isinstance(report, dict):
        gap("could not read the running container's key claims")
        return _reverdict(verdict, gaps)

    facet["present"] = bool(report.get("present"))
    facet["role"] = report.get("role")
    exp = report.get("exp")
    facet["exp_in_past"] = (exp <= now) if isinstance(exp, (int, float)) else None
    digest = report.get("sha256") if isinstance(report.get("sha256"), str) else None
    if not facet["present"]:
        verdict["findings"].append(_finding("container_missing", "running cipher-api has no SUPABASE_SERVICE_KEY"))
    else:
        if report.get("decode_error") or report.get("opaque") or facet["exp_in_past"] is None:
            gap("running cipher-api key claims could not be decoded (role/exp unread)")
        elif facet["exp_in_past"]:
            verdict["findings"].append(_finding("container_expired", "running cipher-api presents an expired key"))
        if facet["role"] is not None and facet["role"] != EXPECTED_ROLE:
            verdict["findings"].append(_finding("container_wrong_role", f"running cipher-api key role is {facet['role']!r}"))

    if env_key and digest:
        facet["matches_env"] = hmac.compare_digest(hashlib.sha256(env_key.encode()).hexdigest(), digest)
        if not facet["matches_env"]:
            verdict["warnings"].append(
                "the running cipher-api presents a different key than this env would "
                "deliver; it changes only when cipher-api is recreated (make -C pmoves up-cipher)"
            )

    # What the RUNNING Kong admits: digests of the consumer keys it was started with.
    kong_name = discover_container(runner, "supabase-kong")
    facet["kong"] = kong_name
    kong_digests: Optional[List[str]] = None
    if kong_name:
        try:
            rc, out = runner(["docker", "exec", kong_name, "sh", "-c", _KONG_SCRIPT])
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()] if rc == 0 else []
            if len(lines) == 2 and all(ln == "-" or re.fullmatch(r"[0-9a-f]{64}", ln) for ln in lines):
                kong_digests = [ln for ln in lines if ln != "-"]
        except (OSError, subprocess.SubprocessError):
            kong_digests = None
    if kong_digests is not None and digest:
        facet["kong_live_admits"] = any(hmac.compare_digest(d, digest) for d in kong_digests)
        if env_key:
            env_digest = hashlib.sha256(env_key.encode()).hexdigest()
            facet["kong_live_matches_env"] = any(hmac.compare_digest(d, env_digest) for d in kong_digests)
        if not facet["kong_live_admits"]:
            stale = (
                "supabase-kong is stale (it predates the current env: recreate it, "
                "make -C pmoves up-supabase)"
                if facet.get("matches_env") and facet.get("kong_live_matches_env") is False
                else "recreate whichever of supabase-kong / cipher-api predates the current env"
            )
            verdict["findings"].append(_finding(
                "kong_live_mismatch",
                "the RUNNING supabase-kong holds no consumer key equal to the key the RUNNING "
                f"cipher-api presents, so every lookup is refused at the gateway; {stale}",
            ))

    probe_ok = False
    if probe:
        result = report.get("probe")
        if not isinstance(result, dict):
            gap("in-container lookup did not run")
        else:
            facet["lookup_status"] = result.get("status")
            finding, note = classify_probe(result)
            if finding:
                verdict["findings"].append(finding)
            if note:
                gap(note)
            probe_ok = finding is None and note is None
    if "kong_live_admits" not in facet and not probe_ok:
        # Without a 200 from the probe, the running Kong's keys are the only live
        # evidence of what the gateway admits. Unread = not measured.
        gap("running supabase-kong consumer keys could not be read"
            + ("" if kong_name else " (no supabase-kong container: CLI runtime or remote Kong? "
               "only PROBE=1 can judge that gateway)"))
    return _reverdict(verdict, gaps)


def _reverdict(verdict: Dict[str, Any], gaps: Sequence[str]) -> Dict[str, Any]:
    fresh = _verdict(verdict["facets"], verdict["findings"], verdict["warnings"],
                     verdict["unmeasured"], gaps)
    verdict.update(status=fresh["status"], exit=fresh["exit"])
    return verdict


# ── .env.local overlay presence (names only) ────────────────────────────────


def overlay_defines(path: Path, key: str) -> Optional[bool]:
    """Is *key* defined in the node-local overlay? Uses env_local_key's own
    resolver and line matcher (the sanctioned reader), so 'defined' means what the
    loader would load. Returns None if the file cannot be read; never a value."""
    try:
        import env_local_key as elk  # type: ignore[import-not-found]

        target, _ = elk._resolve_target(path)
        data = elk._read(target)
    except Exception:  # noqa: BLE001 - presence is advisory; unreadable = unknown
        return None
    if data is None:
        return False
    defs, _ = elk._scan(elk._split(data), key)
    return bool(defs)


# ── CLI ─────────────────────────────────────────────────────────────────────


def render(verdict: Mapping[str, Any]) -> List[str]:
    f = verdict["facets"]
    yn = {True: "yes", False: "no", None: "unmeasured"}
    lines = [
        f"key present ............. {yn[f.get('present')]}"
        + (f" (from {f['key_source']})" if f.get("key_source") else ""),
        f"role .................... {f.get('role') or 'unmeasured'}",
        f"exp in past ............. {yn[f.get('exp_in_past')]}",
        f"matches Kong config ..... {yn[f.get('matches_kong_config')]} (env vs Kong's configured key; NOT the running Kong)",
        f"signature verifies ...... {yn[f.get('signature_verifies')]}",
        f"JWT secrets agree ....... {yn[f.get('jwt_secrets_agree')]}",
    ]
    if "expressions_match" in f:
        em = f["expressions_match"]
        lines.append("compose wiring .......... " + (
            "cipher == kong" if em else "DRIFT (cipher != kong)" if em is False else "unmeasured"))
    if "overlay_retired_key" in f:
        lines.append(f"retired key in overlay .. {f['overlay_retired_key']}")
    if "kong_order_drift" in f:
        lines.append(f"reverse-order sites ..... {len(f['kong_order_drift'])}")
    c = f.get("container")
    if c is None:
        lines.append("live gateway ............ not checked (CONTAINER=1 PROBE=1 is the authority)")
    else:
        lines.append(
            f"container ............... {c.get('name') or 'not found'}"
            + (f": exp in past {yn[c.get('exp_in_past')]}, role {c.get('role') or '?'}"
               f", matches env {yn[c.get('matches_env')]}" if c.get("name") and "present" in c else "")
        )
        if c.get("name"):
            lines.append(
                f"running Kong admits it .. {yn[c.get('kong_live_admits')]}"
                + (f" ({c['kong']})" if c.get("kong") else " (no supabase-kong container)")
            )
        if c.get("lookup_status") is not None:
            lines.append(f"live lookup ............. HTTP {c['lookup_status']}")
    for w in verdict["warnings"]:
        lines.append(f"WARN: {w}")
    for x in verdict["findings"]:
        lines.append(f"FINDING [{x['code']}]: {x['detail']}")
    for u in verdict["unmeasured"]:
        lines.append(f"UNMEASURED: {u}")
    return [f"[cipher-auth-check] {line}" for line in lines]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--compose", action="append", type=Path, dest="compose_files",
                        help="compose file(s) to read expressions from (default: pmoves/docker-compose.yml)")
    parser.add_argument("--scan", action="append", type=Path, default=[], dest="scan_files",
                        help="extra compose files scanned for wiring drift only")
    parser.add_argument("--env-file", action="append", type=Path, default=[], dest="env_files",
                        help="same list, same order, the Makefile passes docker compose")
    parser.add_argument("--env-local", type=Path, default=None,
                        help="node-local overlay checked for the retired key by presence only")
    parser.add_argument("--container", action="store_true", help="also read the running cipher-api and Kong")
    parser.add_argument("--probe", action="store_true",
                        help="with --container: run cipher's own lookup (read-only GET, limit=0)")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        compose_files = args.compose_files or [_PMOVES_DIR / "docker-compose.yml"]
        docs = load_compose(compose_files)
        scan_docs = load_compose(args.scan_files) if args.scan_files else []
        exprs: Dict[str, Any] = {
            "cipher": compose_env_expr(docs, *CIPHER),
            "gateway": compose_env_expr(docs, *GATEWAY),
            "gateway_secret": compose_env_expr(docs, *GATEWAY_SECRET),
            "pgrst_secret": compose_env_expr(docs, *PGRST_SECRET),
            "kong_order_drift": kong_order_drift(list(docs) + list(scan_docs)),
        }
        env, provenance, notes = resolve_env(args.env_files, dict(os.environ))
        overlay = overlay_defines(args.env_local, RETIRED_OVERRIDE) if args.env_local else None
        verdict = assess(env, exprs, provenance, overlay_has_retired=overlay)
        if args.env_local:
            # Say which of the three it was: a silent 'no WARN' must not stand in
            # for 'could not look'.
            verdict["facets"]["overlay_retired_key"] = (
                "present" if overlay else "absent" if overlay is False else "unreadable")
            if overlay is None:
                verdict["unmeasured"].append(
                    f"{args.env_local.name} could not be read for the retired-key presence check")
        for doc_path, doc in zip(args.scan_files, scan_docs):
            other = compose_env_expr([doc], *CIPHER)
            if other is not None and exprs["gateway"] is not None and other.strip() != exprs["gateway"].strip():
                verdict["warnings"].append(
                    f"compose wiring drift: cipher-api in {doc_path.name} does not present Kong's expression")
        verdict["unmeasured"].extend(notes)
        if args.container:
            env_key = _safe_interp(exprs["cipher"], env) or None
            verdict = assess_container(verdict, env_key, _default_runner, args.probe)
    except Exception as exc:  # noqa: BLE001 - a crash is could-not-measure, never a pass
        verdict = {"tool": "cipher-auth-check", "status": "could_not_measure", "exit": 3,
                   "facets": {}, "findings": [], "warnings": [],
                   "unmeasured": [f"check crashed ({type(exc).__name__})"]}
    if args.as_json:
        print(json.dumps(verdict, sort_keys=True))
    else:
        if verdict.get("facets"):
            print("\n".join(render(verdict)))
        else:
            print(f"[cipher-auth-check] UNMEASURED: {verdict['unmeasured'][0]}")
        print("CIPHER_AUTH_VERDICT=" + json.dumps(
            {"status": verdict["status"], "exit": verdict["exit"],
             "findings": [x["code"] for x in verdict["findings"]],
             "warnings": len(verdict["warnings"])}, sort_keys=True))
    return int(verdict["exit"])


if __name__ == "__main__":
    sys.exit(main())
