"""The host-rewrite branch must preserve operator-supplied credentials.

_resolve_nats_url() is NOT a fallback: when NATS_URL is set to the docker-alias
form it MATCHES and rewrites it to the host-published address. If that rewrite
drops the userinfo, an operator-supplied credential is silently discarded and
the host-run follower gets Authorization Violation against the authenticated
broker (docker-compose.yml: --user/--pass).
"""

import importlib

import pytest

MODULES = [
    ("pmoves.tools.voice_follow_agent", "NATS_URL"),
    ("pmoves.tools.voice_follow_cast_agent", "NATS_URL"),
]


@pytest.mark.parametrize("module_name,env_var", MODULES)
def test_host_rewrite_preserves_supplied_credentials(module_name, env_var, monkeypatch):
    """Production change that would make this fail: rewriting the docker alias
    to a bare host URL instead of preserving userinfo."""
    monkeypatch.setenv(env_var, "nats://nats:s3cr3t@nats:4222")
    # Clear the explicit overrides so the NATS_URL branch is the one exercised.
    monkeypatch.delenv("VOICE_FOLLOW_NATS_URL", raising=False)
    monkeypatch.delenv("CAST_FOLLOW_NATS_URL", raising=False)

    mod = importlib.import_module(module_name)
    resolved = mod._resolve_nats_url()

    assert "s3cr3t@" in resolved, (
        f"{module_name} discarded the supplied credential: {resolved!r}"
    )
    assert "127.0.0.1" in resolved, "the docker alias should still be rewritten to the host address"


@pytest.mark.parametrize("module_name,env_var", MODULES)
def test_credentialless_url_is_left_credentialless(module_name, env_var, monkeypatch):
    """Control: the rewrite must not invent a credential that was never supplied."""
    monkeypatch.setenv(env_var, "nats://nats:4222")
    monkeypatch.delenv("VOICE_FOLLOW_NATS_URL", raising=False)
    monkeypatch.delenv("CAST_FOLLOW_NATS_URL", raising=False)

    mod = importlib.import_module(module_name)
    resolved = mod._resolve_nats_url()

    assert "@" not in resolved, f"invented a credential: {resolved!r}"
    assert "127.0.0.1" in resolved
