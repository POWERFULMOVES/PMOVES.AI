"""Generate Crush CLI configuration tailored for PMOVES."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_CANDIDATES = [
    PROJECT_ROOT / ".env.generated",
    PROJECT_ROOT / "env.shared.generated",
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / "env.shared",
]
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "crush" / "crush.json"


def _load_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _lookup_env(name: str, caches: Dict[Path, Dict[str, str]]) -> Optional[str]:
    value = os.getenv(name)
    if value:
        return value
    for path, content in caches.items():
        if name in content and content[name]:
            return content[name]
    return None


@dataclass
class ModelSpec:
    id: str
    name: str
    role: str  # "large" or "small" or "general"
    context_window: Optional[int] = None
    default_max_tokens: Optional[int] = None
    can_reason: bool = False

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {"id": self.id, "name": self.name}
        if self.context_window:
            payload["context_window"] = self.context_window
        if self.default_max_tokens:
            payload["default_max_tokens"] = self.default_max_tokens
        if self.can_reason:
            payload["can_reason"] = True
        return payload


@dataclass
class ProviderSpec:
    id: str
    name: str
    base_url: str
    type: str = "openai"
    env_var: Optional[str] = None
    extra_headers: Dict[str, str] = field(default_factory=dict)
    models: List[ModelSpec] = field(default_factory=list)
    default_large: Optional[str] = None
    default_small: Optional[str] = None


# TensorZero is the ONLY provider - it routes to all backends
# Models are discovered dynamically from TensorZero, not hardcoded here
TENSORZERO_SPEC = ProviderSpec(
    id="tensorzero",
    name="TensorZero Gateway",
    base_url="http://localhost:3030/v1",
    type="openai",
    env_var=None,  # TensorZero handles auth internally
)


def _fetch_tensorzero_models() -> List[ModelSpec]:
    """Fetch available models from TensorZero API.

    Returns dynamically discovered models instead of hardcoded list.
    """
    import urllib.request
    import urllib.error

    base_url = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3030")
    try:
        with urllib.request.urlopen(f"{base_url}/v1/models", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                # Infer role from model name patterns
                role = "small"
                if any(x in model_id.lower() for x in ["32b", "70b", "claude", "gpt-4o"]):
                    role = "large"
                models.append(ModelSpec(id=model_id, name=model_id, role=role))
            return models
    except (urllib.error.URLError, TimeoutError):
        # Fallback defaults if TensorZero not reachable
        return [
            ModelSpec(id="qwen3_8b", name="Qwen3 8B (Local)", role="small"),
            ModelSpec(id="claude-sonnet-4-5", name="Claude Sonnet 4.5", role="large", can_reason=True),
        ]


# Legacy provider specs - only used if TensorZero unavailable
PROVIDER_SPECS: List[ProviderSpec] = [TENSORZERO_SPEC]


@dataclass
class MCPSpec:
    key: str
    config: Dict[str, object]
    required_commands: List[str] = field(default_factory=list)
    required_env: Optional[str] = None


MCP_SPECS: List[MCPSpec] = [
    MCPSpec(
        key="pmoves-mini",
        config={
            "type": "stdio",
            "command": "pmoves-mini",
            "args": ["mcp", "serve"],
            "timeout": 120,
        },
        required_commands=["pmoves-mini"],
    ),
    MCPSpec(
        key="docker",
        config={
            "type": "stdio",
            "command": "mcp-docker",
            "timeout": 60,
        },
        required_commands=["mcp-docker", "docker"],
    ),
    MCPSpec(
        key="n8n",
        config={
            "type": "http",
            "url": "http://localhost:5678/mcp",
            "headers": {"x-api-key": "$N8N_API_KEY"},
            "timeout": 30,
        },
        required_env="N8N_API_KEY",
    ),
]


def _select_models(available: Dict[str, ProviderSpec], provider_models: Dict[str, List[ModelSpec]]) -> Dict[str, Dict[str, str]]:
    """Select models - TensorZero is the ONLY gateway for all providers.

    TensorZero routes internally to: Ollama (local) → Anthropic → Gemini Flash
    All model calls go through TensorZero for unified observability.
    """
    # TensorZero is the single gateway - all models route through it
    if "tensorzero" in available:
        tz_spec = available["tensorzero"]
        return {
            "large": {"provider": "tensorzero", "model": tz_spec.default_large or "claude-sonnet-4-5"},
            "small": {"provider": "tensorzero", "model": tz_spec.default_small or "qwen3_8b_local"},
        }

    # Fallback only if TensorZero not available
    large: Optional[Tuple[str, str]] = None
    small: Optional[Tuple[str, str]] = None
    priority = ["ollama", "anthropic", "gemini"]
    for provider_id in priority:
        if provider_id not in available:
            continue
        provider = available[provider_id]
        if not large and provider.default_large:
            large = (provider_id, provider.default_large)
        if not small and provider.default_small:
            small = (provider_id, provider.default_small)
    if not large and available:
        pid, models = next(iter(provider_models.items()))
        if models:
            large = (pid, models[0].id)
    if not small:
        small = large
    models_config: Dict[str, Dict[str, str]] = {}
    if large:
        models_config["large"] = {"provider": large[0], "model": large[1]}
    if small:
        models_config["small"] = {"provider": small[0], "model": small[1]}
    return models_config


def build_config() -> Tuple[Dict[str, object], Dict[str, ProviderSpec]]:
    """Build Crush config with TensorZero as the ONLY provider.

    All models are discovered dynamically from TensorZero API.
    No hardcoded model lists - TensorZero is the single source of truth.
    """
    env_cache = {path: _load_env_file(path) for path in ENV_CANDIDATES}

    # TensorZero is the ONLY provider
    base_url_env = _lookup_env("TENSORZERO_BASE_URL", env_cache) or "http://localhost:3030"
    base_url = f"{base_url_env.rstrip('/')}/v1"

    # Fetch models dynamically from TensorZero
    models = _fetch_tensorzero_models()

    # Find large and small models from dynamic list
    large_models = [m for m in models if m.role == "large"]
    small_models = [m for m in models if m.role == "small"]
    default_large = large_models[0].id if large_models else "claude-sonnet-4-5"
    default_small = small_models[0].id if small_models else "qwen3_8b"

    providers_dict: Dict[str, object] = {
        "tensorzero": {
            "name": "TensorZero Gateway",
            "base_url": base_url,
            "type": "openai",
            "models": [model.to_dict() for model in models],
        }
    }

    tensorzero_spec = ProviderSpec(
        id="tensorzero",
        name="TensorZero Gateway",
        base_url=base_url,
        type="openai",
        models=models,
        default_large=default_large,
        default_small=default_small,
    )

    available_specs = {"tensorzero": tensorzero_spec}
    provider_models = {"tensorzero": models}

    models_config = _select_models(available_specs, provider_models)

    mcp_config: Dict[str, Dict[str, object]] = {}
    for spec in MCP_SPECS:
        config = dict(spec.config)
        disabled = False
        if spec.required_commands and not all(shutil.which(cmd) for cmd in spec.required_commands):
            disabled = True
        if spec.required_env and not _lookup_env(spec.required_env, env_cache):
            disabled = True
        if disabled:
            config["disabled"] = True
        mcp_config[spec.key] = config

    repo_root = PROJECT_ROOT.parent
    context_candidates = [
        Path("CRUSH.md"),
        Path("docs/LOCAL_DEV.md"),
        Path("docs/LOCAL_TOOLING_REFERENCE.md"),
        Path("pmoves/docs/ROADMAP.md"),
        Path("pmoves/docs/NEXT_STEPS.md"),
        Path("pmoves/docs/SMOKETESTS.md"),
        Path("pmoves/chit/secrets_manifest.yaml"),
        Path("docs/PMOVES_MINI_CLI_SPEC.md"),
    ]

    context_paths = [
        candidate.as_posix()
        for candidate in context_candidates
        if (repo_root / candidate).exists()
    ]

    config = {
        "$schema": "https://charm.land/crush.json",
        "providers": providers_dict,
        "models": models_config,
        "mcp": mcp_config,
        "options": {
            "context_paths": context_paths,
            "tui": {"compact_mode": True},
            "attribution": {"generated_with": True, "co_authored_by": False},
        },
        "permissions": {
            "allowed_tools": ["bash", "ls", "view"],
        },
        "tools": {"ls": {"max_depth": 4, "max_items": 400}},
        "lsp": {
            "gopls": {"command": "gopls"},
            "pyright": {"command": "pyright-langserver", "args": ["--stdio"]},
            "typescript": {"command": "typescript-language-server", "args": ["--stdio"]},
        },
    }
    return config, available_specs


def write_config(path: Path = DEFAULT_CONFIG_PATH) -> Tuple[Path, Dict[str, ProviderSpec]]:
    config, providers = build_config()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path, providers


def config_status(path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, object]:
    exists = path.exists()
    providers = {}
    if exists:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            providers = data.get("providers", {})
        except Exception:
            providers = {}
    return {
        "path": str(path),
        "exists": exists,
        "providers": list(providers.keys()),
    }
