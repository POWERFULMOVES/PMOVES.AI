"""GPU status and process data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from config.settings import Settings


class ModelState(str, Enum):
    """State of a model in the GPU orchestrator."""

    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    UNLOADING = "unloading"
    ERROR = "error"


@dataclass
class ProcessInfo:
    """Information about a GPU process."""

    pid: int
    name: str
    vram_mb: int
    container_id: Optional[str] = None
    container_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "vram_mb": self.vram_mb,
            "container_id": self.container_id,
            "container_name": self.container_name,
        }


@dataclass
class LoadedModel:
    """Represents a loaded model with tracking metadata."""

    model_id: str
    provider: str  # ollama, vllm, tts
    vram_mb: int
    state: ModelState
    loaded_at: datetime
    last_used: datetime
    idle_timeout_seconds: int = 300  # Configurable idle threshold
    session_id: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def is_idle(self) -> bool:
        """Check if model has been idle beyond threshold."""
        return (datetime.now() - self.last_used).total_seconds() > self.idle_timeout_seconds

    @property
    def idle_seconds(self) -> float:
        """Get number of seconds model has been idle."""
        return (datetime.now() - self.last_used).total_seconds()

    def touch(self) -> None:
        """Update last_used timestamp."""
        self.last_used = datetime.now()

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "vram_mb": self.vram_mb,
            "state": self.state.value,
            "loaded_at": self.loaded_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "idle_timeout_seconds": self.idle_timeout_seconds,
            "session_id": self.session_id,
            "idle_seconds": self.idle_seconds,
            "error_message": self.error_message,
        }


@dataclass
class GpuMetrics:
    """Real-time GPU metrics."""

    gpu_index: int
    name: str
    total_vram_mb: int
    used_vram_mb: int
    free_vram_mb: int
    temperature_c: int
    utilization_percent: int
    is_mock: bool = False  # True if data is from mock/fallback mode
    power_draw_w: Optional[float] = None
    power_limit_w: Optional[float] = None

    @property
    def vram_usage_percent(self) -> float:
        """Calculate VRAM usage percentage."""
        if self.total_vram_mb == 0:
            return 0.0
        return (self.used_vram_mb / self.total_vram_mb) * 100

    def to_dict(self) -> dict:
        return {
            "gpu_index": self.gpu_index,
            "name": self.name,
            "total_vram_mb": self.total_vram_mb,
            "used_vram_mb": self.used_vram_mb,
            "free_vram_mb": self.free_vram_mb,
            "vram_usage_percent": round(self.vram_usage_percent, 2),
            "temperature_c": self.temperature_c,
            "utilization_percent": self.utilization_percent,
            "is_mock": self.is_mock,
            "power_draw_w": self.power_draw_w,
            "power_limit_w": self.power_limit_w,
        }


@dataclass
class GpuStatus:
    """Complete GPU status including metrics, processes, and loaded models."""

    metrics: GpuMetrics
    processes: List[ProcessInfo] = field(default_factory=list)
    loaded_models: Dict[str, LoadedModel] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def idle_models(self) -> List[LoadedModel]:
        """Get list of idle models."""
        return [m for m in self.loaded_models.values() if m.is_idle]

    @property
    def active_models(self) -> List[LoadedModel]:
        """Get list of active (non-idle) models."""
        return [m for m in self.loaded_models.values() if not m.is_idle]

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics.to_dict(),
            "processes": [p.to_dict() for p in self.processes],
            "loaded_models": {k: v.to_dict() for k, v in self.loaded_models.items()},
            "idle_model_count": len(self.idle_models),
            "active_model_count": len(self.active_models),
            "timestamp": self.timestamp.isoformat(),
        }
