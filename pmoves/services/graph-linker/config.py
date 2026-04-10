"""Graph Linker configuration via Pydantic BaseSettings.

All configuration is sourced from environment variables with sensible defaults.
Secrets should be injected via Docker/Kubernetes secrets or .env files.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """""""""Application settings loaded from environment variables."""""""""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Server ---------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8090
    log_level: str = "info"

    # -- Neo4j ----------------------------------------------------------
    neo4j_url: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"
    neo4j_database: str = "neo4j"
    neo4j_max_connection_pool_size: int = 50
    neo4j_connection_timeout: float = 30.0
    neo4j_max_transaction_retry_time: float = 30.0

    # -- NATS -----------------------------------------------------------
    nats_url: str = "nats://nats:pmoves@nats:4222"
    nats_name: str = "graph-linker"
    nats_reconnect_wait: float = 2.0
    nats_max_reconnect_attempts: int = 60
    nats_pending_msg_limit: int = 65536

    # -- Dead-letter ----------------------------------------------------
    dead_letter_subject: str = "graph-linker.dead-letter.v1"
    dead_letter_max_retries: int = 3

    # -- Migrations -----------------------------------------------------
    migrations_dir: str = "migrations"

    # -- NATS subjects to subscribe to ----------------------------------
    subjects: list[str] = [
        "gen.image.result.v1",
        "analysis.extract_topics.result.v1",
        "kb.upsert.request.v1",
    ]


def get_settings() -> Settings:
    """""""""Return a cached Settings instance."""""""""
    return Settings()
