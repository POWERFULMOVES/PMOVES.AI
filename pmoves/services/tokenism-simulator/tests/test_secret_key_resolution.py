"""Fail-closed SECRET_KEY resolution tests for Tokenism Simulator config.

Deliberately imports ONLY the config module (stdlib + optional dotenv), so
the suite runs on seats without flask/structlog — the heavy import surface
(app.py -> flask, structlog, api blueprints) is not touched here.
"""

import importlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("services", None)

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


def test_env_unset_mints_ephemeral_64hex(monkeypatch):
    """Dev mode: absent SECRET_KEY mints a 64-hex ephemeral, never a default."""
    monkeypatch.setenv("DOCKER_CONTAINER", "1")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    importlib.reload(config)
    first = config.ServiceConfig().secret_key
    second = config.ServiceConfig().secret_key
    assert re.fullmatch(r"[0-9a-f]{64}", first)
    assert re.fullmatch(r"[0-9a-f]{64}", second)
    # Two instantiations must not share a key: ephemeral means per-process,
    # never a repo-wide constant wearing a random coat.
    assert first != second


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
