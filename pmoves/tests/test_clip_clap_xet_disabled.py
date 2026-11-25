"""clip-embed and clap-embed must download weights over plain HTTP, not hf-xet.

Measured on SPARK 2026-10-22 inside pmoves-clap-embed-1 (huggingface_hub
1.25.1, hf_xet 1.5.2): every xet-backed file (the weights; small files such as
config.json are not xet-stored) failed at once with
``RuntimeError: Reqwest error: builder error``, so /embed returned 500 while
/healthz stayed green. Unsetting the empty HTTP(S)_PROXY / NO_PROXY did NOT
fix it; HF_HUB_DISABLE_XET=1 did (776 MB pytorch_model.bin in 31 s).
"""

from pathlib import Path

import pytest
import yaml

PMOVES = Path(__file__).resolve().parents[1]
COMPOSE_FILES = ["docker-compose.yml", "docker-compose.core.yml"]
SERVICES = ["clip-embed", "clap-embed"]


def _env(service: dict) -> dict:
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return {k: str(v) for k, v in env.items()}
    out = {}
    for item in env:
        key, _, value = str(item).partition("=")
        out[key] = value
    return out


@pytest.mark.parametrize("compose", COMPOSE_FILES)
@pytest.mark.parametrize("name", SERVICES)
def test_xet_disabled_by_default(compose: str, name: str) -> None:
    doc = yaml.safe_load((PMOVES / compose).read_text())
    service = doc["services"][name]
    value = _env(service).get("HF_HUB_DISABLE_XET")
    assert value is not None, f"{compose}:{name} does not set HF_HUB_DISABLE_XET"
    # Overridable per node, but the default must disable xet.
    assert value in ("1", "${HF_HUB_DISABLE_XET:-1}"), value
