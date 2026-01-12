"""Model registry for known models and their VRAM requirements."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml


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
        self.models: Dict[str, ModelDefinition] = {}
        self.thresholds = {
            "vram_warning_percent": 80,
            "idle_timeout_seconds": 300,
        }
        self.hardware = {
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
            self.models[f"{model.provider}/{model.id}"] = model

    def load_from_file(self, path: str) -> None:
        """Load model definitions from YAML file."""
        config_path = Path(path)
        if not config_path.exists():
            self._load_defaults()
            return

        with open(config_path) as f:
            data = yaml.safe_load(f)

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
                self.models[f"{model.provider}/{model.id}"] = model

        if "thresholds" in data:
            self.thresholds.update(data["thresholds"])

        if "rtx5090" in data:
            self.hardware.update(data["rtx5090"])

    def get_model(self, provider: str, model_id: str) -> Optional[ModelDefinition]:
        """Get model definition by provider and ID."""
        key = f"{provider}/{model_id}"
        return self.models.get(key)

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
        models = list(self.models.values())
        if provider:
            models = [m for m in models if m.provider == provider]
        return models

    def get_available_vram(self) -> int:
        """Get available VRAM after system reserve."""
        return self.hardware["total_vram_mb"] - self.hardware["system_reserve_mb"]

    def to_dict(self) -> dict:
        return {
            "models": [m.to_dict() for m in self.models.values()],
            "thresholds": self.thresholds,
            "hardware": self.hardware,
        }
