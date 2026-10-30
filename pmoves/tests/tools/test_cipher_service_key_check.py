"""Offline tests for cipher's service-key preflight and key precedence.

The incident (knuckles, 2026-10-21/22): cipher-api presented CIPHER_DB_SERVICE_KEY,
a service_role JWT pasted into pmoves/.env.local. It expired. The funnel
refreshed SUPABASE_SERVICE_ROLE_KEY / SERVICE_ROLE_KEY (#3410) but the paste
shadowed them, and Kong's service_role consumer key is rendered from those
refreshed names, not from the paste. Every per-agent lookup then 401'd.

What is under test:
  * the precedence: which NAME supplies the key cipher presents, for the
    pre-fix expression (on disk until the compose grant lands) and the
    gateway-mirroring expression this lane proposes
  * the verdicts: expired / wrong role / missing / wrong pair (gateway or
    signature) / ok / could-not-measure, and their exit codes
  * that no key, digest or secret ever reaches stdout/stderr

Keys are minted with the funnel's own derivation (secrets_self_generated), so
"a funnel-refreshed key is admitted" is tested against the real minting code.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES = REPO_ROOT / "pmoves"
MODULE = PMOVES / "tools" / "cipher_service_key_check.py"

spec = importlib.util.spec_from_file_location("cipher_service_key_check", MODULE)
assert spec and spec.loader
ck = importlib.util.module_from_spec(spec)
sys.modules["cipher_service_key_check"] = ck
spec.loader.exec_module(ck)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from pmoves.tools.secrets_self_generated import derive_supabase_jwt  # noqa: E402

NOW = 1_800_000_000
PGRST_SECRET = "s" * 40            # the secret PostgREST runs with
OTHER_SECRET = "o" * 40            # a different stack's secret
LIVE = dict(iat=NOW - 10, exp=NOW + 10 * 365 * 86400)
DEAD = dict(iat=NOW - 400 * 86400, exp=NOW - 86400)

FRESH = derive_supabase_jwt(PGRST_SECRET, "service_role", **LIVE)
FRESH_LEGACY = derive_supabase_jwt(PGRST_SECRET, "service_role", iat=NOW - 5, exp=NOW + 3650 * 86400)
EXPIRED_PASTE = derive_supabase_jwt(PGRST_SECRET, "service_role", **DEAD)
FOREIGN = derive_supabase_jwt(OTHER_SECRET, "service_role", **LIVE)
ANON = derive_supabase_jwt(PGRST_SECRET, "anon", **LIVE)

# The pre-fix cipher expression (df0218537) and the gateway's own expression.
PRE_FIX = "${CIPHER_DB_SERVICE_KEY:-${SUPABASE_SERVICE_KEY:-}}"
GATEWAY = "${SUPABASE_SERVICE_ROLE_KEY:-${SERVICE_ROLE_KEY:-}}"
SECRET_EXPR = "${SUPABASE_JWT_SECRET:-${JWT_SECRET:-}}"


def exprs(cipher: str = GATEWAY) -> dict:
    return {"cipher": cipher, "gateway": GATEWAY, "pgrst_secret": SECRET_EXPR}


def codes(verdict: dict) -> list:
    return sorted(f["code"] for f in verdict["findings"])


# ── interpolation ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "env, value, source",
    [
        ({"A": "a", "B": "b"}, "a", "A"),
        ({"A": "", "B": "b"}, "b", "B"),
        ({"B": "b"}, "b", "B"),
        ({}, "", None),
    ],
)
def test_nested_default_reports_the_supplying_name(env, value, source):
    assert ck.interpolate_with_source("${A:-${B:-}}", env) == (value, source)


def test_dash_without_colon_honours_set_but_empty():
    assert ck.interpolate("${A-x}", {"A": ""}) == ""
    assert ck.interpolate("${A:-x}", {"A": ""}) == "x"


def test_required_guard_raises_with_name_only():
    with pytest.raises(ck.Unresolvable) as exc:
        ck.interpolate("${NEEDED:?set it}", {})
    assert str(exc.value) == "NEEDED"


# ── compose: the precedence that decides which key cipher presents ─────────


def _compose(path: Path) -> list:
    return ck.load_compose([path])


def test_compose_kong_consumer_expression_is_the_funnel_refreshed_pair():
    docs = _compose(PMOVES / "docker-compose.yml")
    assert ck.compose_env_expr(docs, *ck.GATEWAY) == GATEWAY
    assert ck.compose_env_expr(docs, *ck.PGRST_SECRET) == SECRET_EXPR


@pytest.mark.xfail(
    strict=True,
    reason="BLOCKED: compose is readOnly; the cipher-api edit needs an operator "
    "KNOWN_ROAD grant (diff in PR #3433). Strict: once it lands this XPASSes and "
    "the marker must go.",
)
@pytest.mark.parametrize("compose", ["docker-compose.yml", "docker-compose.agents.yml"])
def test_compose_cipher_presents_the_gateway_key(compose):
    gateway = ck.compose_env_expr(_compose(PMOVES / "docker-compose.yml"), *ck.GATEWAY)
    assert ck.compose_env_expr(_compose(PMOVES / compose), *ck.CIPHER) == gateway


# The knuckles incident env: the paste is set and expired, SUPABASE_SERVICE_KEY
# is a key from another stack, both refreshed names are live.
INCIDENT_ENV = {
    "CIPHER_DB_SERVICE_KEY": EXPIRED_PASTE,
    "SUPABASE_SERVICE_KEY": FOREIGN,
    "SUPABASE_SERVICE_ROLE_KEY": FRESH,
    "SERVICE_ROLE_KEY": FRESH,
    "SUPABASE_JWT_SECRET": PGRST_SECRET,
}


def test_pre_fix_expression_presents_the_expired_paste():
    """Characterises main: the paste wins, and is refused at both gates."""
    v = ck.assess(INCIDENT_ENV, exprs(PRE_FIX), now=NOW)
    assert v["facets"]["key_source"] == "CIPHER_DB_SERVICE_KEY"
    assert codes(v) == ["expired", "wrong_pair_gateway"]
    assert v["exit"] == 1


@pytest.mark.parametrize(
    "cipher_expr",
    [
        pytest.param(GATEWAY, id="proposed"),
        pytest.param(
            "on-disk",
            id="on-disk",
            marks=pytest.mark.xfail(strict=True, reason="compose edit BLOCKED (see above)"),
        ),
    ],
)
def test_incident_env_presents_a_key_the_gateway_admits(cipher_expr):
    """Failing-before control: on the on-disk (pre-fix) compose this fails on
    the VERDICT (expired + wrong_pair_gateway), not on a missing symbol."""
    if cipher_expr == "on-disk":
        cipher_expr = ck.compose_env_expr(_compose(PMOVES / "docker-compose.yml"), *ck.CIPHER)
    v = ck.assess(INCIDENT_ENV, exprs(cipher_expr), now=NOW)
    assert codes(v) == []
    assert v["status"] == "ok" and v["exit"] == 0
    assert v["facets"]["gateway_admits"] is True
    assert v["facets"]["key_source"] in {"SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY"}


@pytest.mark.parametrize(
    "node_env, source",
    [
        # funnel-generated node: both names present and refreshed
        ({"SUPABASE_SERVICE_ROLE_KEY": FRESH, "SERVICE_ROLE_KEY": FRESH}, "SUPABASE_SERVICE_ROLE_KEY"),
        # node carrying only the legacy name (the 2026-09-22 "legacy verifies" shape)
        ({"SERVICE_ROLE_KEY": FRESH_LEGACY}, "SERVICE_ROLE_KEY"),
        # 2026-09-23 shape: legacy name stale, canonical live -- canonical wins
        ({"SUPABASE_SERVICE_ROLE_KEY": FRESH, "SERVICE_ROLE_KEY": EXPIRED_PASTE}, "SUPABASE_SERVICE_ROLE_KEY"),
    ],
    ids=["funnel-both", "legacy-only", "legacy-stale"],
)
def test_every_node_shape_presents_what_kong_admits_without_a_paste(node_env, source):
    v = ck.assess({**node_env, "JWT_SECRET": PGRST_SECRET}, exprs(), now=NOW)
    assert v["facets"]["key_source"] == source
    assert v["facets"]["gateway_admits"] is True
    assert v["status"] == "ok", v


def test_legacy_verifies_newer_does_not_reproduces_the_compose_comment():
    """pmoves/docker-compose.yml:4154-4162 (B850, 2026-09-22): PGRST301 on the
    SUPABASE_* pair (SUPABASE_SERVICE_KEY), the LEGACY pair (SERVICE_ROLE_KEY)
    verifies. The proposed expression never reads SUPABASE_SERVICE_KEY, so a
    node in that state with a funnel-derived canonical key is clean."""
    env = {
        "SUPABASE_SERVICE_KEY": FOREIGN,          # the newer pair: PGRST301
        "SERVICE_ROLE_KEY": FRESH_LEGACY,         # the legacy pair: verifies
        "SUPABASE_SERVICE_ROLE_KEY": FRESH_LEGACY,  # funnel: same role group, same mint
        "SUPABASE_JWT_SECRET": PGRST_SECRET,
    }
    v = ck.assess(env, exprs(), now=NOW)
    assert v["status"] == "ok" and v["facets"]["signature_verifies"] is True
    # ...while the pre-fix fallback presents exactly the pair the comment says fails.
    pre = ck.assess(env, exprs(PRE_FIX), now=NOW)
    assert pre["facets"]["key_source"] == "SUPABASE_SERVICE_KEY"
    assert "wrong_pair_signature" in codes(pre)


def test_legacy_first_precedence_would_be_refused_by_kong():
    """Why cipher does NOT put SERVICE_ROLE_KEY first even though the legacy pair
    verified: when the two names differ, Kong admits only its own consumer key
    (SUPABASE_SERVICE_ROLE_KEY first), so legacy-first is refused at the gateway.
    The mirrored order instead surfaces the real fault, and names who verifies."""
    env = {
        "SUPABASE_SERVICE_ROLE_KEY": FOREIGN,     # canonical name holds a foreign-signed key
        "SERVICE_ROLE_KEY": FRESH_LEGACY,         # legacy verifies
        "SUPABASE_JWT_SECRET": PGRST_SECRET,
    }
    legacy_first = ck.assess(env, exprs("${SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-}}"), now=NOW)
    assert codes(legacy_first) == ["wrong_pair_gateway"]
    mirrored = ck.assess(env, exprs(), now=NOW)
    assert codes(mirrored) == ["wrong_pair_signature"]
    assert mirrored["facets"]["verifying_names"] == ["SERVICE_ROLE_KEY"]
    assert "SERVICE_ROLE_KEY" in mirrored["findings"][0]["detail"]


# ── verdicts ──────────────────────────────────────────────────────────────


def _env(key, **extra):
    env = {"SUPABASE_SERVICE_ROLE_KEY": key, "SUPABASE_JWT_SECRET": PGRST_SECRET}
    env.update(extra)
    return env


def test_expired_is_a_finding():
    v = ck.assess(_env(EXPIRED_PASTE), exprs(), now=NOW)
    assert v["facets"]["exp_in_past"] is True
    assert codes(v) == ["expired"] and v["exit"] == 1


def test_wrong_role_is_a_finding():
    v = ck.assess(_env(ANON), exprs(), now=NOW)
    assert v["facets"]["role"] == "anon"
    assert codes(v) == ["wrong_role"]


def test_missing_is_a_finding():
    v = ck.assess({"SUPABASE_JWT_SECRET": PGRST_SECRET}, exprs(), now=NOW)
    assert v["facets"]["present"] is False
    assert codes(v) == ["missing"] and v["exit"] == 1


def test_signature_under_another_secret_is_wrong_pair():
    # Kong would admit it (it IS Kong's consumer key) but PostgREST will not.
    v = ck.assess(_env(FOREIGN), exprs(), now=NOW)
    assert v["facets"]["gateway_admits"] is True
    assert v["facets"]["signature_verifies"] is False
    assert codes(v) == ["wrong_pair_signature"]


def test_gateway_mismatch_is_wrong_pair():
    env = {"CIPHER_KEY": FRESH, "SUPABASE_SERVICE_ROLE_KEY": FRESH_LEGACY, "JWT_SECRET": PGRST_SECRET}
    v = ck.assess(env, exprs("${CIPHER_KEY}"), now=NOW)
    assert codes(v) == ["wrong_pair_gateway"]
    assert v["facets"]["expressions_match"] is False
    assert any("wiring drift" in w for w in v["warnings"])


def test_live_admitted_key_is_ok():
    v = ck.assess(_env(FRESH), exprs(), now=NOW)
    assert (v["status"], v["exit"], v["findings"]) == ("ok", 0, [])
    assert v["facets"]["signature_verifies"] is True


def test_opaque_key_cannot_be_judged_for_expiry():
    v = ck.assess(_env("sb_secret_abcdef"), exprs(), now=NOW)
    assert v["facets"]["shape"] == "opaque"
    assert v["status"] == "could_not_measure" and v["exit"] == 3


def test_unresolvable_gateway_is_could_not_measure():
    v = ck.assess({"K": FRESH}, {"cipher": "${K}", "gateway": None, "pgrst_secret": None}, now=NOW)
    assert v["exit"] == 3


def test_retired_override_warns_with_provenance_and_does_not_decide_the_key():
    env = _env(FRESH, CIPHER_DB_SERVICE_KEY=EXPIRED_PASTE)
    v = ck.assess(env, exprs(), {"CIPHER_DB_SERVICE_KEY": [".env.local"]}, now=NOW)
    assert v["status"] == "ok"
    warn = [w for w in v["warnings"] if "CIPHER_DB_SERVICE_KEY" in w]
    assert warn and ".env.local" in warn[0] and "no longer reads it" in warn[0]


def test_retired_override_warning_says_when_compose_still_reads_it():
    v = ck.assess(INCIDENT_ENV, exprs(PRE_FIX), now=NOW)
    assert any("STILL READS IT" in w for w in v["warnings"])


# ── env layering (compose precedence) ─────────────────────────────────────


def _parse(path):
    out = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def test_later_env_file_wins_and_process_env_wins_even_empty(tmp_path):
    a, b = tmp_path / "env.shared", tmp_path / ".env.local"
    a.write_text("X=from-shared\nY=shared\nZ=shared\n")
    b.write_text("X=from-local\n")
    env, prov, notes = ck.resolve_env([a, b, tmp_path / "absent"], {"Z": ""}, parse=_parse)
    assert env["X"] == "from-local" and env["Y"] == "shared" and env["Z"] == ""
    assert prov["X"] == ["env.shared", ".env.local"]
    assert any("absent" in n for n in notes)


def test_env_file_alias_expands_against_earlier_files(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("SERVICE_ROLE_KEY=live\n")
    b.write_text("SUPABASE_SERVICE_KEY=${SERVICE_ROLE_KEY}\n")
    env, _, _ = ck.resolve_env([a, b], {}, parse=_parse)
    assert env["SUPABASE_SERVICE_KEY"] == "live"


# ── CLI: exit codes, structured verdict, no secret leaks ──────────────────


COMPOSE_FIXTURE = f"""
services:
  supabase-postgrest:
    environment:
    - PGRST_JWT_SECRET={SECRET_EXPR}
  supabase-kong:
    environment:
    - SUPABASE_SERVICE_KEY={GATEWAY}
  cipher-api:
    environment:
    - SUPABASE_SERVICE_KEY=__CIPHER__
"""


def _run_cli(tmp_path, monkeypatch, capsys, cipher_expr, env_lines, *extra):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(COMPOSE_FIXTURE.replace("__CIPHER__", cipher_expr))
    envf = tmp_path / "env.shared"
    envf.write_text("".join(f"{k}={v}\n" for k, v in env_lines.items()))
    for k in list(INCIDENT_ENV) + ["JWT_SECRET"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(ck, "time", type("T", (), {"time": staticmethod(lambda: NOW)}))
    rc = ck.main(["--compose", str(compose), "--env-file", str(envf), *extra])
    out = capsys.readouterr()
    return rc, out.out, out.err


SECRETS = [FRESH, EXPIRED_PASTE, FOREIGN, PGRST_SECRET]


def _assert_no_leak(text):
    import hashlib
    for s in SECRETS:
        assert s not in text
        assert hashlib.sha256(s.encode()).hexdigest() not in text
        assert s.split(".")[-1] not in text  # not even the signature part


def test_cli_incident_exits_1_with_structured_verdict_and_no_leak(tmp_path, monkeypatch, capsys):
    env = {**INCIDENT_ENV}
    rc, out, err = _run_cli(tmp_path, monkeypatch, capsys, PRE_FIX, env)
    assert rc == 1
    last = out.strip().splitlines()[-1]
    assert last.startswith("CIPHER_AUTH_VERDICT=")
    verdict = json.loads(last.split("=", 1)[1])
    assert verdict["status"] == "finding" and verdict["exit"] == 1
    assert set(verdict["findings"]) == {"expired", "wrong_pair_gateway"}
    assert "exp in past ......... yes" in out
    _assert_no_leak(out + err)


def test_cli_fixed_expression_exits_0_json_and_no_leak(tmp_path, monkeypatch, capsys):
    rc, out, err = _run_cli(tmp_path, monkeypatch, capsys, GATEWAY, INCIDENT_ENV, "--json")
    assert rc == 0
    payload = json.loads(out)
    assert payload["facets"]["key_source"] == "SUPABASE_SERVICE_ROLE_KEY"
    _assert_no_leak(out + err)


def test_cli_crash_is_could_not_measure(tmp_path, capsys):
    rc = ck.main(["--compose", str(tmp_path / "missing.yml")])
    out = capsys.readouterr().out
    assert rc == 3 and '"status": "could_not_measure"' in out


# ── running container (fake docker) ───────────────────────────────────────


def _runner(report, names="pmoves-cipher-api-1"):
    calls = []

    def run(cmd):
        calls.append(cmd)
        if cmd[:2] == ["docker", "ps"]:
            return 0, names + "\n" if names else ""
        return 0, json.dumps(report) + "\n"

    run.calls = calls
    return run


def _container_report(key, probe=None):
    import hashlib
    claims = ck.jwt_parts(key)[1]
    r = {"present": True, "sha256": hashlib.sha256(key.encode()).hexdigest(),
         "role": claims["role"], "exp": claims["exp"]}
    if probe is not None:
        r["probe"] = probe
    return r


def _base_ok():
    return ck.assess(_env(FRESH), exprs(), now=NOW)


def test_container_matching_env_and_lookup_200_is_ok():
    run = _runner(_container_report(FRESH, {"status": 200, "code": None, "kong": False}))
    v = ck.assess_container(_base_ok(), FRESH, run, probe=True, now=NOW)
    c = v["facets"]["container"]
    assert c["matches_env"] is True and c["lookup_status"] == 200
    assert v["status"] == "ok"
    assert run.calls[-1][:3] == ["docker", "exec", "pmoves-cipher-api-1"]
    assert "if (k && true)" in run.calls[-1][-1]


def test_stale_container_warns_and_expired_container_is_a_finding():
    run = _runner(_container_report(EXPIRED_PASTE))
    v = ck.assess_container(_base_ok(), FRESH, run, probe=False, now=NOW)
    assert v["facets"]["container"]["matches_env"] is False
    assert any("up-cipher" in w for w in v["warnings"])
    assert codes(v) == ["container_expired"] and v["exit"] == 1


@pytest.mark.parametrize(
    "probe, code",
    [
        ({"status": 401, "code": None, "kong": True}, "lookup_refused_gateway"),
        ({"status": 401, "code": "PGRST303", "kong": False, "expired": True}, "lookup_refused_expired"),
        ({"status": 401, "code": "PGRST301", "kong": False}, "lookup_refused_signature"),
        ({"status": 500, "code": None, "kong": False}, "lookup_http_error"),
    ],
)
def test_probe_classifies_the_refusing_gate(probe, code):
    run = _runner(_container_report(FRESH, probe))
    v = ck.assess_container(_base_ok(), FRESH, run, probe=True, now=NOW)
    assert codes(v) == [code] and v["exit"] == 1


def test_no_container_is_could_not_measure():
    v = ck.assess_container(_base_ok(), FRESH, _runner({}, names=""), probe=False, now=NOW)
    assert v["status"] == "could_not_measure" and v["exit"] == 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_in_container_script_emits_claims_and_digest_never_the_key():
    script = ck._NODE_SCRIPT.replace("__PROBE__", "false")
    proc = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=20,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "SUPABASE_SERVICE_KEY": FRESH},
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["role"] == "service_role" and report["exp"] == LIVE["exp"]
    assert FRESH not in proc.stdout and FRESH.split(".")[-1] not in proc.stdout
