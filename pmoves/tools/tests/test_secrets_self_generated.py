"""Tests for the funnel-side self-generated secrets guard.

The Supabase JWT derivation must match scripts/supabase/generate-keys.sh
byte-for-byte; the guard must be additive (never overwrite operator values) and
must not fabricate POSTGRES_PASSWORD. An EXPIRED self-generated JWT is the one
exception to additivity: these labels are re-derivable from JWT_SECRET by
construction, so a dead key is stale, not operator intent.
"""
import base64

import pytest
import json
import time

from pmoves.tools.secrets_self_generated import (
    SELF_GENERATED,
    _jwt_exp_claim,
    derive_supabase_jwt,
    fill_self_generated,
)

# Vector produced by generate-keys.sh's generate_jwt_token for this secret+role
# (verified byte-for-byte against the shell openssl pipeline).
_SECRET = "test-jwt-secret-1234567890"
_ANON = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlLWxvY2FsIiwiaWF0IjoxNjQxNzY5MjAwLCJleHAiOjE3OTk1MzU2MDB9."
    "XBdxir4-NBsyWuaWBM3b6me3NKgqkUroUMeCCbAMM90"
)


def _decode_claims(token: str) -> dict:
    payload = token.split(".")[1]
    pad = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(pad))


def test_derive_matches_generate_keys_sh_vector():
    assert derive_supabase_jwt(_SECRET, "anon") == _ANON


def test_derive_role_changes_token():
    assert derive_supabase_jwt(_SECRET, "service_role") != derive_supabase_jwt(_SECRET, "anon")


def test_fill_derives_all_supabase_labels_from_jwt_secret():
    out = fill_self_generated({"JWT_SECRET": _SECRET})
    assert out["SUPABASE_ANON_KEY"] == _ANON
    assert out["ANON_KEY"] == _ANON
    assert out["NEXT_PUBLIC_SUPABASE_ANON_KEY"] == _ANON
    # service_role derived and consistent across its aliases
    assert out["SUPABASE_SERVICE_ROLE_KEY"] == out["SERVICE_ROLE_KEY"]
    assert out["SUPABASE_SERVICE_ROLE_KEY"] == derive_supabase_jwt(_SECRET, "service_role")


def test_fill_accepts_supabase_jwt_secret_alias():
    out = fill_self_generated({"SUPABASE_JWT_SECRET": _SECRET})
    assert out["SUPABASE_ANON_KEY"] == _ANON


def test_fill_never_overwrites_operator_value():
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SUPABASE_ANON_KEY": "operator-set"})
    assert out["SUPABASE_ANON_KEY"] == "operator-set"


def test_fill_no_jwt_secret_is_noop():
    src = {"SOME_OTHER_KEY": "x"}
    assert fill_self_generated(src) == src


def test_fill_does_not_fabricate_postgres_password():
    out = fill_self_generated({"JWT_SECRET": _SECRET})
    assert "POSTGRES_PASSWORD" not in out


def test_postgres_recognized_but_not_derivable():
    # Recognized as self-generated (skip operator-missing reports) but never minted here.
    assert "POSTGRES_PASSWORD" in SELF_GENERATED


def test_self_generated_covers_supabase_labels():
    for label in ("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "POSTGRES_PASSWORD"):
        assert label in SELF_GENERATED


# --- expired-JWT refresh (knuckles 2026-10-22 incident) ---


def _expired_jwt(secret: str, role: str, exp: int) -> str:
    return derive_supabase_jwt(secret, role, iat=exp - 365 * 86400, exp=exp)


def test_fill_refreshes_expired_service_role_jwt():
    dead = _expired_jwt(_SECRET, "service_role", exp=int(time.time()) - 3600)
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SERVICE_ROLE_KEY": dead})
    fresh = out["SERVICE_ROLE_KEY"]
    assert fresh != dead
    claims = _decode_claims(fresh)
    assert claims["role"] == "service_role"
    assert claims["exp"] > int(time.time()) + 9 * 365 * 86400


def test_fill_refreshes_all_aliases_of_same_role_consistently():
    dead = _expired_jwt(_SECRET, "anon", exp=int(time.time()) - 60)
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SUPABASE_ANON_KEY": dead})
    assert out["ANON_KEY"] == out["NEXT_PUBLIC_SUPABASE_ANON_KEY"] == out["SUPABASE_ANON_KEY"]


def test_fill_never_touches_live_operator_jwt():
    # The canonical fixed-exp vector is far-future; must survive byte-exact.
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SUPABASE_ANON_KEY": _ANON})
    assert out["SUPABASE_ANON_KEY"] == _ANON


def test_fill_leaves_non_jwt_values_alone():
    # New-style sb_secret_* / opaque tokens are not refreshable here.
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SERVICE_ROLE_KEY": "sb_secret_opaque"})
    assert out["SERVICE_ROLE_KEY"] == "sb_secret_opaque"


def test_jwt_exp_claim_shapes():
    assert _jwt_exp_claim(None) is None
    assert _jwt_exp_claim("") is None
    assert _jwt_exp_claim("not-a-jwt") is None
    assert _jwt_exp_claim("a.b.c") is None  # undecodable payload
    assert _jwt_exp_claim(_ANON) == 1799535600
    no_exp = derive_supabase_jwt(_SECRET, "anon", exp=0)
    # exp claim present but zero is still an int
    assert _jwt_exp_claim(no_exp) == 0


def test_refreshed_token_signature_verifies_with_same_secret():
    import hashlib
    import hmac as hmac_mod

    dead = _expired_jwt(_SECRET, "service_role", exp=int(time.time()) - 1)
    out = fill_self_generated({"JWT_SECRET": _SECRET, "SERVICE_ROLE_KEY": dead})
    token = out["SERVICE_ROLE_KEY"]
    header, payload, sig = token.split(".")
    expected = base64.urlsafe_b64encode(
        hmac_mod.new(_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    assert sig == expected


# ── verifier precedence (#3433 review P2) ────────────────────────────────────
# Every compose verifier (PostgREST, GoTrue, Realtime, Studio) reads
# ${SUPABASE_JWT_SECRET:-${JWT_SECRET:-}}. Minting JWT_SECRET-first produced keys
# Kong admits but PostgREST refuses (PGRST301) wherever the two secrets differ.

_VERIFIER = "verifier-secret-abcdefghijklmnopqrstuvwxyz"
_OTHER = "legacy-jwt-secret-abcdefghijklmnopqrstuvwxyz"


def _signed_by(token: str, secret: str) -> bool:
    import hashlib
    import hmac as hmac_mod

    header, payload, sig = token.split(".")
    expected = base64.urlsafe_b64encode(
        hmac_mod.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return sig == expected


def test_mints_with_the_verifiers_secret_when_the_two_secrets_differ():
    out = fill_self_generated({"JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER})
    for label in ("SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY", "ANON_KEY"):
        assert _signed_by(out[label], _VERIFIER), label
        assert not _signed_by(out[label], _OTHER), label


def test_remints_a_live_key_that_does_not_verify_under_the_verifiers_secret():
    # Live (unexpired) but minted under the other secret: the old funnel left it,
    # so PostgREST refused it forever. It is self-generated, so re-mint it.
    live_exp = int(time.time()) + 365 * 86400
    wrong = derive_supabase_jwt(_OTHER, "service_role", exp=live_exp)
    out = fill_self_generated({
        "JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER,
        "SUPABASE_SERVICE_ROLE_KEY": wrong, "SERVICE_ROLE_KEY": wrong,
        "SUPABASE_RUNTIME": "compose",
    })
    assert out["SUPABASE_SERVICE_ROLE_KEY"] != wrong
    assert _signed_by(out["SUPABASE_SERVICE_ROLE_KEY"], _VERIFIER)
    # one role, one key: every alias moves to the same mint
    assert out["SERVICE_ROLE_KEY"] == out["SUPABASE_SERVICE_ROLE_KEY"]


def test_live_key_that_verifies_is_still_never_touched():
    live = derive_supabase_jwt(_VERIFIER, "service_role", exp=int(time.time()) + 86400)
    out = fill_self_generated({"SUPABASE_JWT_SECRET": _VERIFIER, "SERVICE_ROLE_KEY": live})
    assert out["SERVICE_ROLE_KEY"] == live


def test_non_hs256_values_are_never_judged_by_signature():
    out = fill_self_generated({"SUPABASE_JWT_SECRET": _VERIFIER, "SERVICE_ROLE_KEY": "sb_secret_opaque"})
    assert out["SERVICE_ROLE_KEY"] == "sb_secret_opaque"



# ── ownership + runtime gates on the live re-mint (#3433 follow-up P1/P2/P3) ──
# A live key is rewritten only if it is provably funnel-minted (HS256, iss
# supabase-local, the label's role) AND this node's compose Supabase is the
# verifier. Before #3433 live keys were never touched; a CLI/cloud key that does
# not verify under OUR secret may be exactly right for ITS verifier.

from pmoves.tools.secrets_self_generated import compose_consumers, local_runtime_is_verifier  # noqa: E402

_LIVE = int(time.time()) + 365 * 86400
_COMPOSE = {"SUPABASE_RUNTIME": "compose"}


def _jwt(header: dict, claims: dict, secret: str = "x") -> str:
    import hashlib
    import hmac as hmac_mod

    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=").decode()  # noqa: E731
    si = f"{enc(header)}.{enc(claims)}"
    sig = base64.urlsafe_b64encode(hmac_mod.new(secret.encode(), si.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{si}.{sig}"


def _base(**extra):
    return {"JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER, **_COMPOSE, **extra}


def test_rs256_shaped_jwt_is_left_alone():
    rs = _jwt({"alg": "RS256", "typ": "JWT"}, {"role": "anon", "iss": "supabase-local", "exp": _LIVE})
    events = []
    out = fill_self_generated(_base(SUPABASE_ANON_KEY=rs), events=events)
    assert out["SUPABASE_ANON_KEY"] == rs
    assert not [e for e in events if e["label"] == "SUPABASE_ANON_KEY"]


def test_foreign_iss_hs256_cloud_key_is_left_alone_and_warned_by_name():
    cloud = _jwt({"alg": "HS256", "typ": "JWT"},
                 {"iss": "supabase", "ref": "abcd", "role": "anon", "exp": _LIVE}, secret="cloud-secret")
    events = []
    out = fill_self_generated(_base(SUPABASE_ANON_KEY=cloud, NEXT_PUBLIC_SUPABASE_ANON_KEY=cloud), events=events)
    assert out["SUPABASE_ANON_KEY"] == cloud and out["NEXT_PUBLIC_SUPABASE_ANON_KEY"] == cloud
    assert {(e["label"], e["action"], e["reason"]) for e in events if e["role"] == "anon" and e["action"] != "filled"} == {
        ("SUPABASE_ANON_KEY", "left_unchanged", "not_minted_here"),
        ("NEXT_PUBLIC_SUPABASE_ANON_KEY", "left_unchanged", "not_minted_here"),
    }
    assert all(cloud not in str(e) for e in events)


def test_our_key_signed_with_the_other_secret_is_reminted_and_announced(capsys):
    from pmoves.tools.secrets_sync import announce_jwt_events

    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)  # iss supabase-local
    events = []
    out = fill_self_generated(_base(SUPABASE_SERVICE_ROLE_KEY=ours, SERVICE_ROLE_KEY=ours), events=events)
    assert out["SUPABASE_SERVICE_ROLE_KEY"] != ours and _signed_by(out["SUPABASE_SERVICE_ROLE_KEY"], _VERIFIER)
    assert ("SUPABASE_SERVICE_ROLE_KEY", "reminted", "signed_with_other_secret") in {
        (e["label"], e["action"], e["reason"]) for e in events}
    consumers = announce_jwt_events(events)  # real compose files
    printed = capsys.readouterr().out
    assert "RE-MINTED SUPABASE_SERVICE_ROLE_KEY (service_role): signed_with_other_secret" in printed
    assert {"supabase-kong", "cipher-api"} <= set(consumers)
    assert "make -C pmoves up-supabase" in printed and "make -C pmoves up-cipher" in printed
    assert ours not in printed and out["SUPABASE_SERVICE_ROLE_KEY"] not in printed


@pytest.mark.parametrize(
    "ctx, reason",
    [
        ({"SUPABASE_RUNTIME": "compose", "SUPABASE_URL": "https://abcd.supabase.co"}, "remote_url"),
        ({"SUPABASE_RUNTIME": "compose", "SUPABASE_REST_URL": "http://node.tailnet.example:8000/rest/v1"}, "remote_url"),
        ({"SUPABASE_RUNTIME": "cli"}, "runtime_cli"),
        ({}, "runtime_unknown"),
    ],
    ids=["cloud-url", "remote-rest-url", "cli-runtime", "runtime-unstated"],
)
def test_no_live_remint_unless_the_local_compose_stack_is_the_verifier(ctx, reason):
    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)
    secrets = {"JWT_SECRET": _OTHER, "SUPABASE_JWT_SECRET": _VERIFIER,
               "SUPABASE_SERVICE_ROLE_KEY": ours, "SERVICE_ROLE_KEY": ours, **ctx}
    events = []
    out = fill_self_generated(secrets, events=events)
    assert out["SUPABASE_SERVICE_ROLE_KEY"] == ours and out["SERVICE_ROLE_KEY"] == ours
    assert {e["reason"] for e in events if e["role"] == "service_role"} == {reason}


def test_local_urls_count_as_local():
    for url in ("http://supabase-kong:8000", "http://localhost:3001", "http://127.0.0.1:8000/rest/v1",
                "http://host.docker.internal:8000"):
        assert local_runtime_is_verifier({"SUPABASE_RUNTIME": "compose", "SUPABASE_URL": url}) == (True, "local"), url


def test_context_overrides_the_secret_map():
    # secrets_sync passes {**secrets, **os.environ}: an exported runtime wins.
    ours = derive_supabase_jwt(_OTHER, "service_role", exp=_LIVE)
    out = fill_self_generated(_base(SERVICE_ROLE_KEY=ours), context={"SUPABASE_RUNTIME": "cli"})
    assert out["SERVICE_ROLE_KEY"] == ours


def test_expired_foreign_key_still_refreshed_as_in_3410():
    dead = _jwt({"alg": "HS256", "typ": "JWT"}, {"iss": "supabase-demo", "role": "service_role",
                                                 "exp": int(time.time()) - 60}, secret="cli")
    events = []
    out = fill_self_generated({"SUPABASE_JWT_SECRET": _VERIFIER, "SERVICE_ROLE_KEY": dead}, events=events)
    assert out["SERVICE_ROLE_KEY"] != dead and _signed_by(out["SERVICE_ROLE_KEY"], _VERIFIER)
    assert ("SERVICE_ROLE_KEY", "reminted", "expired") in {(e["label"], e["action"], e["reason"]) for e in events}


def test_compose_consumers_reads_environment_and_build_args():
    docs = [{"services": {
        "kong": {"environment": ["SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_ROLE_KEY:-${SERVICE_ROLE_KEY:-}}"]},
        "ui": {"build": {"args": {"NEXT_PUBLIC_SUPABASE_ANON_KEY": "${NEXT_PUBLIC_SUPABASE_ANON_KEY}"}}},
        "other": {"environment": {"X": "${SERVICE_ROLE_KEYS_LIST}"}},   # different name, no match
    }}]
    assert compose_consumers(["SERVICE_ROLE_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"], docs) == ["kong", "ui"]
