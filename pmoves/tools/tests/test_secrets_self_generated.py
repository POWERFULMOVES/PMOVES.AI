"""Tests for the funnel-side self-generated secrets guard.

The Supabase JWT derivation must match scripts/supabase/generate-keys.sh
byte-for-byte; the guard must be additive (never overwrite operator values) and
must not fabricate POSTGRES_PASSWORD. An EXPIRED self-generated JWT is the one
exception to additivity: these labels are re-derivable from JWT_SECRET by
construction, so a dead key is stale, not operator intent.
"""
import base64
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
