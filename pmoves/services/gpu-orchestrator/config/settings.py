"""Configuration settings for GPU Orchestrator service."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """GPU Orchestrator configuration loaded from environment variables."""

    # Service settings
    service_name: str = "gpu-orchestrator"
    host: str = "0.0.0.0"
    port: int = 8200
    log_level: str = "INFO"

    # NATS configuration
    nats_url: str = "nats://nats:4222"
    nats_reconnect_delay: float = 2.0

    # Provider URLs
    ollama_url: str = "http://pmoves-ollama:11434"
    vllm_url: str = "http://pmoves-vllm:8000"
    tts_url: str = "http://ultimate-tts-studio:7861"

    # Model lifecycle settings
    idle_timeout_seconds: int = 300  # 5 minutes
    vram_warning_threshold: float = 0.8  # 80%
    vram_critical_threshold: float = 0.95  # 95%
    status_publish_interval: float = 5.0  # seconds

    # Model registry
    model_registry_path: str = "/app/config/gpu-models.yaml"

    # GPU settings
    gpu_index: int = 0
    system_vram_reserve_mb: int = 2048  # Reserve 2GB for system

    class Config:
        env_prefix = "GPU_ORCHESTRATOR_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
