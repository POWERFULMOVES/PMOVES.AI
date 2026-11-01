"""Fail-closed SECRET_KEY resolution tests for Tokenism Simulator config.

Deliberately imports ONLY the config module (stdlib + optional dotenv), so
the suite runs on seats without flask/structlog — the heavy import surface
(app.py -> flask, structlog, api blueprints) is not touched here.

These are PURE-FUNCTION tests: they call config._resolve_secret_key() and
config.ServiceConfig() directly under monkeypatch. An earlier revision used
importlib.reload(config) per scenario — the CI ratchet's grouped execution
(three test files sharing one pytest process) made that a cross-file hazard:
a reload that raised mid-module left the shared config module partially
re-exec'd, and every later reload in the group failed with
"module config not in sys.modules". Resolution is a pure function of
os.environ, so no reload is needed to exercise any scenario.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402  (tests/conftest.py floors TOKENISM_DEV for import)


def test_env_set_uses_value_verbatim(monkeypatch):
    """Fleet mode: a funnel-provided SECRET_KEY is used exactly as given."""
    monkeypatch.setenv("DOCKER_CONTAINER", "1")
    monkeypatch.setenv("SECRET_KEY", "fleet-value-from-funnel-0123456789abcdef")
    assert config._resolve_secret_key() == "fleet-value-from-funnel-0123456789abcdef"
    # The dataclass path resolves through the same function at instantiation.
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
    assert config._resolve_secret_key() == padded
    assert config.ServiceConfig().secret_key == padded


def test_env_unset_mints_ephemeral_64hex_in_dev(monkeypatch):
    """Dev mode (explicit signal): absent SECRET_KEY mints a 64-hex ephemeral."""
    monkeypatch.setenv("DOCKER_CONTAINER", "1")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    first = config._resolve_secret_key()
    second = config._resolve_secret_key()
    assert re.fullmatch(r"[0-9a-f]{64}", first)
    assert re.fullmatch(r"[0-9a-f]{64}", second)
    # Two resolutions must not share a key: ephemeral means per-mint,
    # never a repo-wide constant wearing a random coat.
    assert first != second


def test_tokenism_dev_flag_also_enables_mint(monkeypatch):
    """The explicit non-FLASK dev signal (TOKENISM_DEV=1) unlocks the mint."""
    monkeypatch.setenv("DOCKER_CONTAINER", "1")
    monkeypatch.setenv("TOKENISM_DEV", "1")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    assert re.fullmatch(r"[0-9a-f]{64}", config._resolve_secret_key())


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
    with pytest.raises(RuntimeError):
        config._resolve_secret_key()
    # The dataclass path (module-level singleton at import) raises through
    # the same resolver via default_factory — assert that path too.
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
