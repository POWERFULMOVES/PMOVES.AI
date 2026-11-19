"""NATS clients that dial the local broker take NATS_URL through compose interpolation.

The broker's password reaches it as an interpolated ${NATS_PASSWORD} (the
--env-file chain). A client that relied on env_file alone for NATS_URL was
measured failing authentication against a freshly recreated broker while
clients that set `NATS_URL=${NATS_URL}` in `environment:` (pdf-ingest and
others) authenticated -- so these services resolve NATS_URL from the same
interpolation as the broker.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PMOVES = Path(__file__).resolve().parents[2]
FILES = ("docker-compose.yml", "docker-compose.agents.yml")
SERVICES = ("hi-rag-gateway-v2", "hi-rag-gateway-v2-gpu", "mesh-agent")


def _env(name: str, service: str) -> list[str]:
    svc = yaml.safe_load((PMOVES / name).read_text(encoding="utf-8"))["services"][service]
    env = svc.get("environment") or []
    assert isinstance(env, list), f"{name}:{service} environment is expected in list form"
    return env


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("service", SERVICES)
def test_nats_url_comes_from_interpolation(name, service):
    assert "NATS_URL=${NATS_URL}" in _env(name, service)
