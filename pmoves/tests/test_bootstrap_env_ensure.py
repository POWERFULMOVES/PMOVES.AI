"""Tests for bootstrap_env.ensure_secret — the secrets-funnel minting primitive.

``ensure_secret`` mints a stack-generated secret into env.shared ONLY when the
slot is absent or empty. It exists because SECRET_KEY_BASE, VAULT_ENC_KEY and the
two LOGFLARE tokens are declared ``required: true`` in both the bootstrap registry
(with generators) and the CHIT manifest, yet no step of ``make secrets-funnel``
ever ran a generator for them. They never reached env.shared, never reached the
CGP bundle, secrets_sync classified them operator-missing, and -- because a
missing required entry lands in ``rejected_out`` -- the funnel actively DELETED
them from the generated tier file. Compose's ``${SECRET_KEY_BASE:?}`` then failed,
and since compose interpolates the whole project before acting, four unset
Supabase variables blocked ``up -d cipher-api`` and every unrelated service.

The load-bearing property under test is the NEGATIVE one: an existing value is
never overwritten. VAULT_ENC_KEY is read with ``bytes.fromhex()`` by the yt OAuth
vault, so a rotation is a data-loss event for stored OAuth cookies.
"""

from __future__ import annotations

import importlib.util
import json
import string
import sys
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_env.py"
_spec = importlib.util.spec_from_file_location("bootstrap_env_ensure_under_test", _MOD_PATH)
be = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass annotation resolution can find the module.
sys.modules[_spec.name] = be
_spec.loader.exec_module(be)

REGISTRY = Path(__file__).resolve().parents[1] / "bootstrap" / "registry.json"


def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


def test_mints_when_key_is_absent(tmp_path):
    env = _write(tmp_path / "env.shared", "FOO=keep\n")
    generated, reason = be.ensure_secret(
        "LOGFLARE_PUBLIC_ACCESS_TOKEN", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is True
    assert "generated" in reason
    assert len(be.read_env_value("LOGFLARE_PUBLIC_ACCESS_TOKEN", env)) == 32
    assert be.read_env_value("FOO", env) == "keep"


def test_mints_when_key_is_present_but_empty(tmp_path):
    env = _write(tmp_path / "env.shared", "SECRET_KEY_BASE=\n")
    generated, _ = be.ensure_secret(
        "SECRET_KEY_BASE", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is True
    # Supabase requires >= 64 chars (docker/CONFIG.md: "recommended length: 64").
    assert len(be.read_env_value("SECRET_KEY_BASE", env)) == 64


def test_never_overwrites_an_existing_value(tmp_path):
    """The safety property: a live secret is never rotated by the funnel."""
    live = "deadbeefdeadbeefdeadbeefdeadbeef"
    env = _write(tmp_path / "env.shared", f"VAULT_ENC_KEY={live}\n")
    generated, reason = be.ensure_secret(
        "VAULT_ENC_KEY", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is False
    assert reason == "already set"
    assert be.read_env_value("VAULT_ENC_KEY", env) == live


def test_does_not_reshape_a_value_that_fails_the_format_check(tmp_path):
    """A malformed value is left ALONE here.

    ``bootstrap()`` regenerates a slot failing ``value_matches_spec``; that
    self-heal must stay operator-invoked (``make env-setup``) rather than fire on
    every funnel run, because reshaping VAULT_ENC_KEY destroys stored yt OAuth
    cookies. ensure_secret only ever fills a hole.
    """
    malformed = "not-hex-at-all-zzzz"  # would FAIL random_hex value_matches_spec
    assert not be.value_matches_spec(malformed, {"type": "random_hex", "length": 32})
    env = _write(tmp_path / "env.shared", f"VAULT_ENC_KEY={malformed}\n")
    generated, _ = be.ensure_secret(
        "VAULT_ENC_KEY", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is False
    assert be.read_env_value("VAULT_ENC_KEY", env) == malformed


def test_is_idempotent(tmp_path):
    env = _write(tmp_path / "env.shared", "# header\nFOO=keep\n")
    be.ensure_secret("SECRET_KEY_BASE", env_path=env, registry_path=str(REGISTRY))
    after_first = env.read_text(encoding="utf-8")
    generated, reason = be.ensure_secret(
        "SECRET_KEY_BASE", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is False and reason == "already set"
    assert env.read_text(encoding="utf-8") == after_first
    assert after_first.startswith("# header")


def test_honours_the_registry_declared_generator_type(tmp_path):
    """VAULT_ENC_KEY must come out hex, not urlsafe.

    The yt OAuth vault does bytes.fromhex() on it. A urlsafe value parses as a
    secret, satisfies compose's ${VAR:?}, and then raises ValueError at use.
    """
    env = _write(tmp_path / "env.shared", "")
    be.ensure_secret("VAULT_ENC_KEY", env_path=env, registry_path=str(REGISTRY))
    value = be.read_env_value("VAULT_ENC_KEY", env)
    assert len(value) == 32
    assert all(c in string.hexdigits for c in value)
    bytes.fromhex(value)  # the actual downstream consumer's call


def test_refuses_a_key_with_no_declared_generator(tmp_path):
    """No generator means no invented value -- an operator secret stays missing."""
    env = _write(tmp_path / "env.shared", "")
    generated, reason = be.ensure_secret(
        "ANTHROPIC_API_KEY", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is False
    assert "no generator" in reason
    assert be.read_env_value("ANTHROPIC_API_KEY", env) is None


def test_read_env_value_is_last_wins_and_skips_comments(tmp_path):
    """Matches chit_encode_secrets' parser: the last duplicate is what is read."""
    env = _write(
        tmp_path / "env.shared",
        "# SECRET_KEY_BASE=commented\nSECRET_KEY_BASE=first\nSECRET_KEY_BASE=second\n",
    )
    assert be.read_env_value("SECRET_KEY_BASE", env) == "second"
    assert be.read_env_value("ABSENT_KEY", env) is None


def test_the_four_blocking_keys_are_generatable_from_the_registry():
    """Guard the registry contract the funnel now depends on.

    If someone drops a generator from one of these, the funnel silently returns
    to warning-while-compose-fails. Fail here instead.
    """
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    specs = {
        v["key"]: v.get("generate")
        for s in data.get("services", [])
        for v in s.get("variables", [])
    }
    assert specs["SECRET_KEY_BASE"] == {"type": "random_urlsafe", "length": 64}
    assert specs["VAULT_ENC_KEY"] == {"type": "random_hex", "length": 32}
    assert specs["LOGFLARE_PUBLIC_ACCESS_TOKEN"] == {"type": "random_urlsafe", "length": 32}
    assert specs["LOGFLARE_PRIVATE_ACCESS_TOKEN"] == {"type": "random_urlsafe", "length": 32}


def test_the_four_are_sourced_from_the_funnel_source_file():
    """They must target env.shared, not a generated tier file.

    Targeting a tier file is what made this unfixable by running env-setup: the
    funnel OWNS the tier files and rewrites them from the CGP bundle, so a value
    written straight into a tier file is deleted on the next funnel run.
    """
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    files = {
        v["key"]: v.get("file")
        for s in data.get("services", [])
        for v in s.get("variables", [])
    }
    shared = "pmoves/env." + "shared"
    for key in (
        "SECRET_KEY_BASE",
        "VAULT_ENC_KEY",
        "LOGFLARE_PUBLIC_ACCESS_TOKEN",
        "LOGFLARE_PRIVATE_ACCESS_TOKEN",
    ):
        assert files[key] == shared, f"{key} must be sourced from the funnel source file"


def test_dry_run_reports_unprovisioned_without_writing(tmp_path, monkeypatch):
    """--ensure-dry-run is the gate: it must never write, and must exit non-zero.

    This is the check that stops the funnel from exiting 0 while a compose
    ``${VAR:?}`` variable is unprovisioned -- the state that blocked every
    service on the node.
    """
    env = _write(tmp_path / "env.shared", "FOO=keep\n")
    monkeypatch.setattr(be, "ENV_SHARED_PATH", env)
    rc = be.main(["--ensure", "SECRET_KEY_BASE", "--ensure-dry-run",
                  "--registry", str(REGISTRY)])
    assert rc == 1
    assert be.read_env_value("SECRET_KEY_BASE", env) is None  # wrote nothing
    assert env.read_text(encoding="utf-8") == "FOO=keep\n"


def test_dry_run_passes_once_provisioned(tmp_path, monkeypatch):
    env = _write(tmp_path / "env.shared", "")
    monkeypatch.setattr(be, "ENV_SHARED_PATH", env)
    be.ensure_secret("SECRET_KEY_BASE", env_path=env, registry_path=str(REGISTRY))
    rc = be.main(["--ensure", "SECRET_KEY_BASE", "--ensure-dry-run",
                  "--registry", str(REGISTRY)])
    assert rc == 0


def test_ensure_is_mutually_exclusive_with_rotate(tmp_path, monkeypatch):
    """Guard against a caller both minting-if-missing and force-rotating."""
    env = _write(tmp_path / "env.shared", "SECRET_KEY_BASE=live\n")
    monkeypatch.setattr(be, "ENV_SHARED_PATH", env)
    rc = be.main(["--ensure", "SECRET_KEY_BASE", "--rotate", "SECRET_KEY_BASE",
                  "--registry", str(REGISTRY)])
    assert rc == 2
    assert be.read_env_value("SECRET_KEY_BASE", env) == "live"
