"""
P7 Service Configuration
========================

Pydantic settings for the P7 room-aware stage manager.

All settings can be overridden via environment variables. The defaults assume
the service is running inside the PMOVES docker-compose stack (paths are
relative to /etc/pmoves/) or locally for development (relative to repo root).

Env-var contract:
  P7_NATS_URL                  NATS server URL (default: nats://nats:4222)
  P7_ROOM_CATALOG_PATH         catalog.json path
  P7_ROOMS_DIR                 directory containing per-room manifests
  P7_ROOM_MANIFEST_SCHEMA      path to room.manifest.v1.schema.json
  P7_SIGNING_CARDS_PATH        path to signing_identity_cards.yaml
  P7_AGENT_REGISTRY_PATH       path to agent_registry.yaml
  P7_HTTP_PORT                 HTTP port (default: 8120)
  P7_CHIT_REQUIRE_SIGNATURE    bool — fail-closed if true (default: true)
  P7_SERVICE_CARD_ID           P7's own CHIT signing card UUID (default: env-injected)
  P7_PMOVES_ROOT               repo root for resolving relative paths (default: pmoves)
  P7_LOG_LEVEL                 log level (default: INFO)
  P7_ALLOW_UNSIGNED_LOCAL      allow unsigned-local advisory on transition gate (default: true)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class P7Settings(BaseSettings):
    """P7 service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="P7_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    # ---- NATS ----
    nats_url: str = "nats://nats:4222"
    nats_connect_timeout_sec: int = 10
    nats_retry_max_attempts: int = 5
    nats_retry_backoff_sec: float = 1.5  # exponential: 1.5, 3, 6, 12, 24, cap 60

    # ---- Room catalog & manifests ----
    # When running in container, these are absolute paths inside /etc/pmoves/...
    # When running locally, these are relative to PMOVES repo root.
    room_catalog_path: str = "pmoves/config/rooms/catalog.json"
    rooms_dir: str = "pmoves/config/rooms"
    room_manifest_schema: str = "pmoves/contracts/schemas/room/room.manifest.v1.schema.json"
    signing_cards_path: str = "pmoves/config/signing_identity_cards.yaml"
    agent_registry_path: str = "pmoves/config/agent_registry.yaml"

    # ---- HTTP ----
    http_host: str = "0.0.0.0"
    http_port: int = 8120

    # ---- CHIT ----
    chit_require_signature: bool = True
    service_card_id: str = ""  # P7's own signing card UUID; if empty, transitions run unsigned-local

    # ---- Repo root (for resolving relative paths) ----
    pmoves_root: str = "."  # default cwd; override with P7_PMOVES_ROOT=/path/to/repo

    # ---- Logging ----
    log_level: str = "INFO"

    # ---- Operational ----
    allow_unsigned_local: bool = True  # operator-acknowledged unsigned advisory is acceptable

    # ---- Derived helpers ----
    def resolved(self, path: str) -> Path:
        """Resolve a relative path against pmoves_root."""
        p = Path(path)
        if p.is_absolute():
            return p
        return Path(self.pmoves_root) / p

    @property
    def catalog_path(self) -> Path:
        return self.resolved(self.room_catalog_path)

    @property
    def rooms_dir_path(self) -> Path:
        return self.resolved(self.rooms_dir)

    @property
    def manifest_schema_path(self) -> Path:
        return self.resolved(self.room_manifest_schema)

    @property
    def signing_cards_path_resolved(self) -> Path:
        return self.resolved(self.signing_cards_path)

    @property
    def agent_registry_path_resolved(self) -> Path:
        return self.resolved(self.agent_registry_path)
