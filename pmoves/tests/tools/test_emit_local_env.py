"""Tests for pmoves.tools.emit_local_env — the runnerless funnel gap fix.

Guards the fix for the 2026-08-14 Hostinger key gap: on a runnerless node the
CI CHIT bundle materialized the tier files but nothing regenerated local.env,
so ``secrets_local_hydrate`` kept overlaying a stale value into env.shared.
``emit_local_env`` reproduces (locally) what ``sync-secrets-local.yml`` does on
a runner: decode the bundle -> write local.env, so a subsequent hydrate lands
fresh values in env.shared.
"""

from __future__ import annotations

from pmoves.chit.codec import encode_secret_map, save_cgp
from pmoves.tools import emit_local_env
from pmoves.tools._secrets_common import parse_env_file

PEM = (
    "-----BEGIN OPENSSH PRIVATE KEY-----\n"
    "b3BlbnNzaC1rZXktdjEAAAAABG5vbmU\n"
    "-----END OPENSSH PRIVATE KEY-----"
)


def _make_bundle(tmp_path, secrets):
    cgp = encode_secret_map(secrets)
    path = tmp_path / "env.cgp.json"
    save_cgp(cgp, path)
    return path


def test_emit_roundtrips_real_secrets(tmp_path):
    bundle = _make_bundle(tmp_path, {"HOSTINGER_API_KEY": "abc123def456", "NATS_PASSWORD": "s3cret-value"})
    local_env = tmp_path / "secrets" / "local.env"

    emitted = emit_local_env.emit(bundle, local_env)

    assert emitted == {"HOSTINGER_API_KEY": "abc123def456", "NATS_PASSWORD": "s3cret-value"}
    parsed = parse_env_file(local_env)
    assert parsed["HOSTINGER_API_KEY"] == "abc123def456"
    assert parsed["NATS_PASSWORD"] == "s3cret-value"


def test_emit_skips_placeholder_values(tmp_path):
    bundle = _make_bundle(tmp_path, {"REAL_KEY": "realvalue123", "EMPTY_KEY": "", "PLACEHOLDER": "changeme"})
    local_env = tmp_path / "local.env"

    emitted = emit_local_env.emit(bundle, local_env)

    assert emitted == {"REAL_KEY": "realvalue123"}
    assert "EMPTY_KEY" not in parse_env_file(local_env)
    assert "PLACEHOLDER" not in parse_env_file(local_env)


def test_emit_skips_multiline_values(tmp_path):
    bundle = _make_bundle(tmp_path, {"GOOD": "flatvalue", "HOSTINGER_SSH_PRIVATE_KEY": PEM})
    local_env = tmp_path / "local.env"

    emitted = emit_local_env.emit(bundle, local_env)

    assert emitted == {"GOOD": "flatvalue"}
    assert "HOSTINGER_SSH_PRIVATE_KEY" not in parse_env_file(local_env)


def test_emit_merges_preserving_local_only_keys(tmp_path):
    local_env = tmp_path / "local.env"
    local_env.write_text("# header comment\nLOCAL_ONLY=keepme\nHOSTINGER_API_KEY=oldvalue\n")
    bundle = _make_bundle(tmp_path, {"HOSTINGER_API_KEY": "newvalue123"})

    emit_local_env.emit(bundle, local_env)

    parsed = parse_env_file(local_env)
    assert parsed["HOSTINGER_API_KEY"] == "newvalue123"  # updated in place
    assert parsed["LOCAL_ONLY"] == "keepme"  # preserved, not dropped
    assert "# header comment" in local_env.read_text()  # structure preserved


def test_emit_dry_run_writes_nothing(tmp_path):
    bundle = _make_bundle(tmp_path, {"HOSTINGER_API_KEY": "abc123def456"})
    local_env = tmp_path / "local.env"

    emitted = emit_local_env.emit(bundle, local_env, dry_run=True)

    assert emitted == {"HOSTINGER_API_KEY": "abc123def456"}
    assert not local_env.exists()


def test_select_emittable_rejects_lowercase_keys():
    emit, skipped = emit_local_env.select_emittable({"lower_key": "v", "GOOD_KEY": "v2"})
    assert emit == {"GOOD_KEY": "v2"}
    assert "lower_key" in skipped
