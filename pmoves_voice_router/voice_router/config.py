"""Env-only configuration + redaction guard (house pattern: pmoves-titanmail-mcp).

Secrets are read from the environment at call time, never cached, never logged,
never embedded in errors. Redaction strips key-looking material before it can
surface in any payload or exception path.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

REDACTED = "<redacted>"
_SECRET_SUBSTRINGS = ("api_key", "authorization", "x-api-key", "token", "secret")


def redact(payload: Any) -> Any:
    """Defense-in-depth: strip key-looking material before it can surface."""
    if isinstance(payload, dict):
        return {
            k: (REDACTED if any(s in str(k).lower() for s in _SECRET_SUBSTRINGS) else redact(v))
            for k, v in payload.items()
        }
    if isinstance(payload, list):
        return [redact(v) for v in payload]
    if isinstance(payload, str) and re.match(r"^(hf_|sk-ant-|sk-proj-|gh[pousr]_|github_pat_|xox[bpars]-|AKIA|AIza|glpat-|tskey-auth-)", payload):
        return REDACTED
    return payload


@dataclass(frozen=True)
class VoiceRouterConfig:
    default_engine: str | None
    omnivoice_base_url: str | None
    omnivoice_api_key: str | None
    flute_base_url: str | None
    flute_api_key: str | None
    utts_base_url: str | None
    utts_api_key: str | None


def get_config(env: dict | None = None) -> VoiceRouterConfig:
    """Build config from env (or an injected mapping for tests)."""
    e = os.environ if env is None else env
    return VoiceRouterConfig(
        default_engine=e.get("VOICE_ROUTER_DEFAULT_ENGINE"),
        omnivoice_base_url=e.get("OMNIVOICE_BASE_URL"),
        omnivoice_api_key=e.get("OMNIVOICE_API_KEY"),
        flute_base_url=e.get("FLUTE_BASE_URL"),
        flute_api_key=e.get("FLUTE_API_KEY"),
        utts_base_url=e.get("UTTS_BASE_URL"),
        utts_api_key=e.get("UTTS_API_KEY"),
    )
