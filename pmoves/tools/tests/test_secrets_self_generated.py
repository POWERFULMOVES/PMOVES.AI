"""Tests for the funnel-side self-generated secrets guard.

The Supabase JWT derivation must match scripts/supabase/generate-keys.sh
byte-for-byte; the guard must be additive (never overwrite operator values) and
must not fabricate POSTGRES_PASSWORD.
"""
from pmoves.tools.secrets_self_generated import (
    SELF_GENERATED,
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
