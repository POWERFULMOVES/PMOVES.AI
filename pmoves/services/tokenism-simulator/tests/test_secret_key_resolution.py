"""Fail-closed SECRET_KEY resolution tests for Tokenism Simulator config.

Deliberately imports ONLY the config module (stdlib + optional dotenv), so
the suite runs on seats without flask/structlog — the heavy import surface
(app.py -> flask, structlog, api blueprints) is not touched here.
"""

import importlib
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("services", None)

# The config module instantiates ServiceConfig() at import time and — by
# design after the codex P1 fix — fail-closes (raises) when it finds
# neither SECRET_KEY nor a dev signal. Pytest collection imports this
# module before any monkeypatch can run, so the INITIAL import carries
# the minimal dev signal; every test then reloads the module under its
# own scenario (the production-raises test deletes this shim explicitly).
os.environ.setdefault("TOKENISM_DEV", "1")

import config  # noqa: E402


def test_env_set_uses_value_verbatim(monkeypatch):
    """Fleet mode: a funnel-provided SECRET_KEY is used exactly as given."""
    # Hermetic: skips the module's dev-only env.shared dotenv loader, so the
    # test cannot ingest whatever a future funnel hydration writes there.
    monkeypatch.setenv("DOCKER_CONTAINER", "1")
    monkeypatch.setenv("SECRET_KEY", "fleet-value-from-funnel-0123456789abcdef")
    importlib.reload(config)
    cfg = config.ServiceConfig()
    assert cfg.secret_key == "fleet-value-from-funnel-0123456789abcdef"


def test_env_set_preserves_whitespace_padding_verbatim(monkeypatch):
    """P2 (codex): no silent .strip() — every byte of the value is the trust root.

    Stripping would silently change the signing key relative to what the
    funnel / operator configured, invalidating live cookies on upgrade.
    """
    monkeypatch.setenv("DOCKER_CONTAINER", "1")
    padded = "  padded-fleet-value-0123456789abcdef  "
    monkeypatch.setenv("SECRET_KEY", padded)
    importlib.reload(config)
    cfg = config.ServiceConfig()
    assert cfg.secret_key == padded


def test_env_unset_mints_ephemeral_64hex_in_dev(monkeypatch):
    """Dev mode (explicit signal): absent SECRET_KEY mints a 64-hex ephemeral."""
    monkeypatch.setenv("DOCKER_CONTAINER", "1")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    importlib.reload(config)
    first = config.ServiceConfig().secret_key
    second = config.ServiceConfig().secret_key
    assert re.fullmatch(r"[0-9a-f]{64}", first)
    assert re.fullmatch(r"[0-9a-f]{64}", second)
    # Two instantiations must not share a key: ephemeral means per-process,
    # never a repo-wide constant wearing a random coat.
    assert first != second


def test_tokenism_dev_flag_also_enables_mint(monkeypatch):
    """The explicit non-FLASK dev signal (TOKENISM_DEV=1) unlocks the mint."""
    monkeypatch.setenv("DOCKER_CONTAINER", "1")
    monkeypatch.setenv("TOKENISM_DEV", "1")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    importlib.reload(config)
    key = config.ServiceConfig().secret_key
    assert re.fullmatch(r"[0-9a-f]{64}", key)


def test_production_without_key_raises(monkeypatch):
    """P1 (codex): production / bare `docker run` with no key must fail loudly.

    Minting here would give each Gunicorn worker a DIFFERENT key (signed
    cookies fail depending on which worker serves the request) and a restart
    would invalidate every cookie. Dev minting requires an explicit signal.
    """
    monkeypatch.setenv("DOCKER_CONTAINER", "1")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("TOKENISM_DEV", raising=False)
    # The module-level singleton (config = ServiceConfig()) executes during
    # reload — THAT is the raiser, so the reload itself sits in the block.
    with pytest.raises(RuntimeError):
        importlib.reload(config)
    # Secondary: after the failed reload the module namespace carries the new
    # (raising) resolver, so a direct instantiation must raise too.
    with pytest.raises(RuntimeError):
        config.ServiceConfig()


def test_public_default_gone_from_service_tree():
    """The public literal must not exist anywhere in the service tree."""
    root = Path(__file__).resolve().parents[1]
    hits = [
        str(p)
        for p in root.rglob("*.py")
        if "tests" not in p.parts
        and "pmoves-tokenism-secret"
        in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert hits == []
