"""Model registry for known models and their VRAM requirements."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

logger = logging.getLogger(__name__)

# Valid providers for validation
VALID_PROVIDERS: Set[str] = {"ollama", "vllm", "tts"}


@dataclass
class ModelDefinition:
    """Definition of a known model with its characteristics."""

    id: str
    provider: str  # ollama, vllm, tts
    vram_mb: int
    description: Optional[str] = None
    priority_default: int = 5
    quantization: Optional[str] = None
    context_length: Optional[int] = None

    def __post_init__(self):
        """Validate model definition fields."""
        if self.provider not in VALID_PROVIDERS:
            raise ValueError(
                f"Invalid provider '{self.provider}'. "
                f"Must be one of: {sorted(VALID_PROVIDERS)}"
            )
        if self.vram_mb < 0:
            raise ValueError(f"vram_mb must be non-negative, got {self.vram_mb}")
        if not 0 <= self.priority_default <= 10:
            raise ValueError(
                f"priority_default must be 0-10, got {self.priority_default}"
            )
        if not self.id:
            raise ValueError("id cannot be empty")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "vram_mb": self.vram_mb,
            "description": self.description,
            "priority_default": self.priority_default,
            "quantization": self.quantization,
            "context_length": self.context_length,
        }


class ModelRegistry:
    """Registry of known models and their VRAM requirements."""

    def __init__(self, config_path: Optional[str] = None):
        self._models: Dict[str, ModelDefinition] = {}
        self._thresholds = {
            "vram_warning_percent": 80,
            "idle_timeout_seconds": 300,
        }
        self._hardware = {
            "total_vram_mb": 32768,  # RTX 5090 default
            "system_reserve_mb": 2048,
        }

        if config_path:
            self.load_from_file(config_path)
        else:
            self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default model definitions."""
        defaults = [
            # Ollama models
            ModelDefinition("qwen3:8b", "ollama", 6144, "Qwen3 8B quantized"),
            ModelDefinition("qwen3:32b", "ollama", 20480, "Qwen3 32B quantized"),
            ModelDefinition("nomic-embed-text", "ollama", 512, "Embedding model"),
            ModelDefinition("llama3.2:3b", "ollama", 2048, "Llama 3.2 3B"),
            ModelDefinition("codellama:7b", "ollama", 4096, "Code Llama 7B"),
            # TTS models
            ModelDefinition("kokoro", "tts", 2048, "Kokoro TTS engine"),
            ModelDefinition("f5-tts", "tts", 3072, "F5-TTS engine"),
            ModelDefinition("voxcpm", "tts", 2560, "VoxCPM engine"),
            # vLLM models
            ModelDefinition("default", "vllm", 16384, "Default vLLM model"),
        ]
        for model in defaults:
            self._models[f"{model.provider}/{model.id}"] = model

    def load_from_file(self, path: str) -> None:
        """Load model definitions from YAML file."""
        config_path = Path(path)
        if not config_path.exists():
            logger.warning(f"Config file not found: {path}, using defaults")
            self._load_defaults()
            return

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)
        except (OSError, IOError) as e:
            logger.error(f"Error reading config file {path}: {e}")
            self._load_defaults()
            return
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML from {path}: {e}")
            self._load_defaults()
            return

        if not data or not isinstance(data, dict):
            logger.warning(f"Invalid config data in {path}, using defaults")
            self._load_defaults()
            return

        try:
            if "models" in data:
                for model_data in data["models"]:
                    model = ModelDefinition(
                        id=model_data["id"],
                        provider=model_data["provider"],
                        vram_mb=model_data["vram_mb"],
                        description=model_data.get("description"),
                        priority_default=model_data.get("priority_default", 5),
                        quantization=model_data.get("quantization"),
                        context_length=model_data.get("context_length"),
                    )
                    self._models[f"{model.provider}/{model.id}"] = model

            if "thresholds" in data:
                self._thresholds.update(data["thresholds"])

            if "rtx5090" in data:
                self._hardware.update(data["rtx5090"])

        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Error processing model definitions from {path}: {e}")
            self._load_defaults()

    def get_model(self, provider: str, model_id: str) -> Optional[ModelDefinition]:
        """Get model definition by provider and ID."""
        key = f"{provider}/{model_id}"
        return self._models.get(key)

    def get_vram_estimate(self, provider: str, model_id: str) -> int:
        """Get estimated VRAM usage for a model."""
        model = self.get_model(provider, model_id)
        if model:
            return model.vram_mb
        # Default estimates for unknown models
        defaults = {"ollama": 4096, "vllm": 8192, "tts": 2048}
        return defaults.get(provider, 4096)

    def list_models(self, provider: Optional[str] = None) -> List[ModelDefinition]:
        """List all known models, optionally filtered by provider."""
        models = list(self._models.values())
        if provider:
            models = [m for m in models if m.provider == provider]
        return models

    def get_available_vram(self) -> int:
        """Get available VRAM after system reserve."""
        return self._hardware["total_vram_mb"] - self._hardware["system_reserve_mb"]

    @property
    def models(self) -> Dict[str, ModelDefinition]:
        """Get models dictionary (read-only access)."""
        return dict(self._models)

    @property
    def thresholds(self) -> Dict:
        """Get thresholds dictionary (read-only access)."""
        return dict(self._thresholds)

    @property
    def hardware(self) -> Dict:
        """Get hardware dictionary (read-only access)."""
        return dict(self._hardware)

    def to_dict(self) -> dict:
        return {
            "models": [m.to_dict() for m in self._models.values()],
            "thresholds": self._thresholds,
            "hardware": self._hardware,
        }
