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
   ``rest-v1``) wants an EXACT match with the ``service_role`` consumer key,
   which compose renders from ``supabase-kong``'s ``SUPABASE_SERVICE_KEY``.
   A different value — even a valid JWT — is refused before PostgREST sees it.
2. **PostgREST** verifies the JWT signature against ``PGRST_JWT_SECRET`` and
   then its ``exp`` claim.

Measured on knuckles 2026-10-22: cipher presented ``CIPHER_DB_SERVICE_KEY``, a
service_role JWT hand-pasted into ``pmoves/.env.local`` per ``df0218537``. It
expired 2026-10-21. The funnel refresh (#3410) renews ``SUPABASE_SERVICE_ROLE_KEY``
and ``SERVICE_ROLE_KEY`` but never touches ``.env.local``, and the paste shadowed
both. Earlier the same knob flipped meaning between nodes and days (2026-09-22:
the legacy pair verified; 2026-09-23: the legacy pair was refused). A per-node
value paste cannot be kept right across a mesh.

WHAT IT CHECKS (read-only; never prints a key, a hash, or a claim value other
than ``role``)
-----------------------------------------------------------------------------
The expressions come from the compose file on disk, and the values from the same
``--env-file`` list the Makefile hands ``docker compose`` (process env wins, as in
compose), so this resolves what the next ``make -C pmoves up-cipher`` presents.

* ``present``             the cipher expression resolves to a non-empty value
* ``key_source``          WHICH variable NAME supplied it
* ``role`` / ``exp_in_past``  decoded claims, signature NOT verified here
* ``gateway_admits``      value equals Kong's service_role consumer key
* ``signature_verifies``  HS256 signature verifies under PostgREST's secret
* ``CIPHER_DB_SERVICE_KEY`` set anywhere -> WARN (retired; a stale paste)

``--container`` additionally reads the RUNNING ``cipher-api`` container: its
key's role/exp (decoded inside the container) and whether it equals the key the
env would deliver now (compared by digest in-process, digest never printed).
``--probe`` (needs ``--container``) performs the lookup cipher performs, as a
read-only ``GET ...cipher_agent_tokens?select=agent_id&limit=0`` from inside
the container, and classifies the answer: Kong refusal / expired / signature.

Exit codes (``make`` collapses every nonzero exit to 2, so the last line is a
structured ``CIPHER_AUTH_VERDICT=<json>`` that survives it):
  0  key present, live, admitted by the gateway
  1  findings: missing, expired, wrong role, wrong pair (gateway or signature),
     or the running container's lookup is refused
  3  could not measure (no env, unreadable compose, opaque key, crash). NOT a pass

Usage:
  make -C pmoves cipher-auth-check                 # env + compose only
  make -C pmoves cipher-auth-check CONTAINER=1     # + running container
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
PGRST_SECRET = ("supabase-postgrest", "PGRST_JWT_SECRET")

RETIRED_OVERRIDE = "CIPHER_DB_SERVICE_KEY"
# Every name a service_role key has travelled under on this mesh (legacy pair,
# newer pair, funnel canonical, retired override). Probed by NAME for the
# wrong-pair diagnosis only; values never leave the process.
CANDIDATE_NAMES = (
    "SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", RETIRED_OVERRIDE,
)
EXPECTED_ROLE = "service_role"
EXPIRY_WARN_S = 30 * 24 * 3600

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


def assess(
    env: Mapping[str, str],
    exprs: Mapping[str, Optional[str]],
    provenance: Optional[Mapping[str, List[str]]] = None,
    now: Optional[int] = None,
) -> Dict[str, Any]:
    """Verdict for the key the cipher expression resolves to in *env*.

    *exprs* holds the raw compose expressions under ``cipher``, ``gateway`` and
    ``pgrst_secret``. Nothing in the returned dict is a key, digest or secret.
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
        "gateway_admits": None,
        "signature_verifies": None,
    }

    if env.get(RETIRED_OVERRIDE):
        where = ", ".join(sorted(set(provenance.get(RETIRED_OVERRIDE, [])))) or "environment"
        reads = RETIRED_OVERRIDE in (exprs.get("cipher") or "")
        warnings.append(
            f"{RETIRED_OVERRIDE} is set ({where}). It is retired: a pasted value is "
            "never refreshed by the funnel and shadowed the refreshed keys when it "
            + ("expired. The compose cipher-api expression on disk STILL READS IT, so it "
               "decides the key below." if reads else
               "expired. Compose no longer reads it, but a branch that does would.")
            + " Remove it on the road: make -C pmoves env-local-unset KEY=CIPHER_DB_SERVICE_KEY"
        )

    cipher_expr = exprs.get("cipher")
    gateway_expr = exprs.get("gateway")
    if cipher_expr is None:
        unmeasured.append("compose has no cipher-api SUPABASE_SERVICE_KEY entry")
        return _verdict(facets, findings, warnings, unmeasured, exprs)

    facets["expressions_match"] = (
        None if gateway_expr is None else cipher_expr.strip() == gateway_expr.strip()
    )
    if facets["expressions_match"] is False:
        warnings.append(
            "compose wiring drift: cipher-api's SUPABASE_SERVICE_KEY expression is not "
            "supabase-kong's service_role consumer expression, so the two can resolve "
            "to different keys on any node"
        )

    try:
        key, source = interpolate_with_source(cipher_expr, env)
    except Unresolvable as exc:
        findings.append(_finding("missing", f"compose guard ${{{exc}:?}} fired; the key cannot resolve"))
        facets["present"] = False
        return _verdict(facets, findings, warnings, unmeasured, exprs)
    except ValueError:
        unmeasured.append("cipher expression could not be parsed")
        return _verdict(facets, findings, warnings, unmeasured, exprs)

    facets["present"] = bool(key)
    facets["key_source"] = source
    if not key:
        findings.append(_finding(
            "missing",
            "the cipher expression resolves to an empty value; auth.ts reports "
            "'SUPABASE_SERVICE_KEY not set' and every lookup is 503",
        ))
        return _verdict(facets, findings, warnings, unmeasured, exprs)

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
        try:
            gateway_key = interpolate(gateway_expr, env)
        except (Unresolvable, ValueError):
            gateway_key = ""
        if not gateway_key:
            unmeasured.append("Kong's service_role consumer key does not resolve in this env")
        else:
            facets["gateway_admits"] = hmac.compare_digest(gateway_key.encode(), key.encode())
            if not facets["gateway_admits"]:
                findings.append(_finding(
                    "wrong_pair_gateway",
                    f"cipher presents {source or 'its expression'}'s value but Kong's "
                    "service_role consumer key is a different value; Kong key-auth "
                    "refuses it with 401 before PostgREST sees it",
                ))

    secret_expr = exprs.get("pgrst_secret")
    if decoded is not None and secret_expr is not None:
        try:
            secret = interpolate(secret_expr, env)
        except (Unresolvable, ValueError):
            secret = ""
        if not secret:
            unmeasured.append("PostgREST's JWT secret does not resolve in this env")
        else:
            facets["signature_verifies"] = hs256_verifies(key, secret)
            if facets["signature_verifies"] is False:
                # Which candidate NAMES would verify (booleans over names only).
                # The 2026-09-22 compose comment: PGRST301 on the SUPABASE_* pair,
                # legacy SERVICE_ROLE_KEY verifies. If a different name verifies
                # here, cipher still cannot present it: Kong admits only its own
                # consumer key. The fix is aligning that name in the funnel.
                verifying = [
                    name for name in CANDIDATE_NAMES
                    if env.get(name) and hs256_verifies(env[name], secret)
                ]
                facets["verifying_names"] = verifying
                findings.append(_finding(
                    "wrong_pair_signature",
                    "the key's HS256 signature does not verify under the secret PostgREST "
                    "is configured with (PGRST_JWT_SECRET); PostgREST answers 401 PGRST301. "
                    + (f"Names that DO verify: {', '.join(verifying)}. Kong admits only its "
                       "consumer key, so re-mint the supplying name from the secret PostgREST "
                       "uses (funnel) and recreate supabase-kong; do not paste around it"
                       if verifying else "No candidate name verifies: the JWT secrets disagree"),
                ))
            elif facets["signature_verifies"] is None:
                unmeasured.append("key is not HS256; signature not checked")

    return _verdict(facets, findings, warnings, unmeasured, exprs)


def _verdict(facets, findings, warnings, unmeasured, exprs) -> Dict[str, Any]:
    core_measured = (
        facets.get("present") is not None
        and (facets.get("present") is False
             or (facets.get("exp_in_past") is not None and facets.get("gateway_admits") is not None))
    )
    if findings:
        status, code = "finding", 1
    elif core_measured:
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


# ── running container (opt-in) ─────────────────────────────────────────────

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
  }
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
      out.probe = {status: r.status, code: m ? m[0] : null,
                   expired: /expired/i.test(t),
                   kong: !m && /Invalid authentication credentials|No API key found|no credentials/i.test(t)};
      done();
    })
    .catch(e => { out.probe = {error: e && e.name ? e.name : 'error'}; done(); });
} else { done(); }
"""

Runner = Callable[[List[str]], Tuple[int, str]]


def _default_runner(cmd: List[str]) -> Tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return proc.returncode, proc.stdout


def discover_container(runner: Runner) -> Optional[str]:
    rc, out = runner([
        "docker", "ps", "--filter", "label=com.docker.compose.service=cipher-api",
        "--format", "{{.Names}}",
    ])
    names = [n for n in out.splitlines() if n.strip()] if rc == 0 else []
    return names[0].strip() if names else None


def classify_probe(probe: Mapping[str, Any]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """``(finding, unmeasured_note)`` for the in-container lookup result."""
    if "error" in probe:
        return None, f"in-container lookup could not complete ({probe['error']})"
    status = probe.get("status")
    if status == 200:
        return None, None
    code = probe.get("code")
    if probe.get("kong"):
        return _finding(
            "lookup_refused_gateway",
            f"Kong refused the running container's key (HTTP {status}): it is not the "
            "service_role consumer key Kong was started with. If the funnel refreshed "
            "the key, supabase-kong still holds the old one until it is recreated",
        ), None
    if code == "PGRST303" or probe.get("expired"):
        return _finding("lookup_refused_expired", f"PostgREST: key expired (HTTP {status}, {code})"), None
    if code == "PGRST301":
        return _finding(
            "lookup_refused_signature",
            f"PostgREST: signature invalid under its secret (HTTP {status}, {code})",
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
    now = int(time.time()) if now is None else now
    name = name or discover_container(runner)
    facet: Dict[str, Any] = {"name": name}
    verdict["facets"]["container"] = facet
    if not name:
        verdict["unmeasured"].append("no running cipher-api container found")
        return _reverdict(verdict, container_required=True)
    script = _NODE_SCRIPT.replace("__PROBE__", "true" if probe else "false")
    try:
        rc, out = runner(["docker", "exec", name, "node", "-e", script])
        report = json.loads(out.strip().splitlines()[-1]) if rc == 0 and out.strip() else None
    except (ValueError, IndexError, OSError, subprocess.SubprocessError):
        report = None
    if not isinstance(report, dict):
        verdict["unmeasured"].append("could not read the running container's key claims")
        return _reverdict(verdict, container_required=True)
    facet["present"] = bool(report.get("present"))
    facet["role"] = report.get("role")
    exp = report.get("exp")
    facet["exp_in_past"] = (exp <= now) if isinstance(exp, (int, float)) else None
    digest = report.get("sha256")
    if env_key and isinstance(digest, str):
        facet["matches_env"] = hmac.compare_digest(
            hashlib.sha256(env_key.encode()).hexdigest(), digest
        )
        if not facet["matches_env"]:
            verdict["warnings"].append(
                "the running cipher-api presents a different key than this env would "
                "deliver; it changes only when cipher-api is recreated (make -C pmoves up-cipher)"
            )
    if not facet["present"]:
        verdict["findings"].append(_finding("container_missing", "running cipher-api has no SUPABASE_SERVICE_KEY"))
    elif facet["exp_in_past"]:
        verdict["findings"].append(_finding("container_expired", "running cipher-api presents an expired key"))
    if probe:
        result = report.get("probe")
        if not isinstance(result, dict):
            verdict["unmeasured"].append("in-container lookup did not run")
        else:
            facet["lookup_status"] = result.get("status")
            finding, note = classify_probe(result)
            if finding:
                verdict["findings"].append(finding)
            if note:
                verdict["unmeasured"].append(note)
    return _reverdict(verdict, container_required=False)


def _reverdict(verdict: Dict[str, Any], container_required: bool) -> Dict[str, Any]:
    fresh = _verdict(verdict["facets"], verdict["findings"], verdict["warnings"], verdict["unmeasured"], {})
    if container_required and fresh["status"] == "ok":
        fresh["status"], fresh["exit"] = "could_not_measure", 3
    verdict.update(status=fresh["status"], exit=fresh["exit"])
    return verdict


# ── CLI ─────────────────────────────────────────────────────────────────────


def render(verdict: Mapping[str, Any]) -> List[str]:
    f = verdict["facets"]
    yn = {True: "yes", False: "no", None: "unmeasured"}
    lines = [
        f"key present ......... {yn[f.get('present')]}"
        + (f" (from {f['key_source']})" if f.get("key_source") else ""),
        f"role ................ {f.get('role') or 'unmeasured'}",
        f"exp in past ......... {yn[f.get('exp_in_past')]}",
        f"gateway admits ...... {yn[f.get('gateway_admits')]}",
        f"signature verifies .. {yn[f.get('signature_verifies')]}",
    ]
    if "expressions_match" in f:
        lines.append(f"compose wiring ...... {'cipher == kong' if f['expressions_match'] else 'DRIFT (cipher != kong)' if f['expressions_match'] is False else 'unmeasured'}")
    c = f.get("container")
    if c:
        lines.append(
            f"container ........... {c.get('name') or 'not found'}"
            + (f": exp in past {yn[c.get('exp_in_past')]}, role {c.get('role') or '?'}"
               f", matches env {yn[c.get('matches_env')]}" if c.get("name") and "present" in c else "")
            + (f", lookup HTTP {c['lookup_status']}" if c.get("lookup_status") is not None else "")
        )
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
    parser.add_argument("--env-file", action="append", type=Path, default=[], dest="env_files",
                        help="same list, same order, the Makefile passes docker compose")
    parser.add_argument("--container", action="store_true", help="also read the running cipher-api")
    parser.add_argument("--probe", action="store_true",
                        help="with --container: run cipher's own lookup (read-only GET, limit=0)")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        compose_files = args.compose_files or [_PMOVES_DIR / "docker-compose.yml"]
        docs = load_compose(compose_files)
        exprs = {
            "cipher": compose_env_expr(docs, *CIPHER),
            "gateway": compose_env_expr(docs, *GATEWAY),
            "pgrst_secret": compose_env_expr(docs, *PGRST_SECRET),
        }
        env, provenance, notes = resolve_env(args.env_files, dict(os.environ))
        verdict = assess(env, exprs, provenance)
        verdict["unmeasured"].extend(notes)
        if args.container:
            try:
                env_key = interpolate(exprs["cipher"] or "", env)
            except (Unresolvable, ValueError):
                env_key = None
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
