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


PROVIDER_SPECS: List[ProviderSpec] = [
    ProviderSpec(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        type="openai",
        env_var="OPENAI_API_KEY",
        models=[
            ModelSpec(id="gpt-4o", name="GPT-4o", role="large", context_window=128000),
            ModelSpec(id="gpt-4o-mini", name="GPT-4o mini", role="small", context_window=128000),
        ],
        default_large="gpt-4o",
        default_small="gpt-4o-mini",
    ),
    ProviderSpec(
        id="anthropic",
        name="Anthropic",
        base_url="https://api.anthropic.com/v1",
        type="anthropic",
        env_var="ANTHROPIC_API_KEY",
        extra_headers={"anthropic-version": "2023-06-01"},
        models=[
            ModelSpec(id="claude-3.5-sonnet-20240620", name="Claude 3.5 Sonnet", role="large", context_window=200000, default_max_tokens=4000, can_reason=True),
            ModelSpec(id="claude-3-haiku-20240307", name="Claude 3 Haiku", role="small", context_window=200000, default_max_tokens=4000),
        ],
        default_large="claude-3.5-sonnet-20240620",
        default_small="claude-3-haiku-20240307",
    ),
    ProviderSpec(
        id="gemini",
        name="Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        type="gemini",
        env_var="GEMINI_API_KEY",
        models=[
            ModelSpec(id="gemini-2.0-pro-exp-02-05", name="Gemini 2.0 Pro Exp", role="large"),
            ModelSpec(id="gemini-2.0-flash-exp", name="Gemini 2.0 Flash", role="small"),
        ],
        default_large="gemini-2.0-pro-exp-02-05",
        default_small="gemini-2.0-flash-exp",
    ),
    ProviderSpec(
        id="tensorzero",
        name="TensorZero Gateway",
        base_url="http://localhost:3030/openai/v1",
        type="openai",
    ),
    ProviderSpec(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        type="openai",
        env_var="DEEPSEEK_API_KEY",
        models=[
            ModelSpec(id="deepseek-chat", name="DeepSeek Chat", role="large", context_window=64000),
            ModelSpec(id="deepseek-reasoner", name="DeepSeek Reasoner", role="small", context_window=64000, can_reason=True),
        ],
        default_large="deepseek-chat",
        default_small="deepseek-reasoner",
    ),
    ProviderSpec(
        id="ollama",
        name="Ollama",
        base_url="http://localhost:11434/v1",
        type="openai",
        env_var=None,  # no key required
        models=[
            ModelSpec(id="qwen2.5:7b", name="Qwen 2.5 7B", role="small"),
            ModelSpec(id="llama3.1:70b", name="LLaMA 3.1 70B", role="large"),
        ],
        default_large="llama3.1:70b",
        default_small="qwen2.5:7b",
    ),
]


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
    large: Optional[Tuple[str, str]] = None
    small: Optional[Tuple[str, str]] = None
    priority = ["tensorzero", "openai", "anthropic", "deepseek", "gemini", "ollama"]
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
    env_cache = {path: _load_env_file(path) for path in ENV_CANDIDATES}
    providers_dict: Dict[str, object] = {}
    available_specs: Dict[str, ProviderSpec] = {}
    provider_models: Dict[str, List[ModelSpec]] = {}

    for spec in PROVIDER_SPECS:
        if spec.id == "tensorzero":
            base_url_env = _lookup_env("TENSORZERO_BASE_URL", env_cache)
            if not base_url_env:
                continue
            base_url = f"{base_url_env.rstrip('/')}/openai/v1"
            large_model_id = _lookup_env("TENSORZERO_LARGE_MODEL", env_cache) or "openai::gpt-4o"
            small_model_id = _lookup_env("TENSORZERO_SMALL_MODEL", env_cache) or "openai::gpt-4o-mini"
            models = [
                ModelSpec(id=large_model_id, name=large_model_id, role="large"),
                ModelSpec(id=small_model_id, name=small_model_id, role="small"),
            ]
            entry = {
                "name": spec.name,
                "base_url": base_url,
                "type": spec.type,
                "models": [model.to_dict() for model in models],
            }
            api_key = _lookup_env("TENSORZERO_API_KEY", env_cache)
            extra_headers = dict(spec.extra_headers)
            if api_key:
                entry["api_key"] = "$TENSORZERO_API_KEY"
                extra_headers = dict(extra_headers)
                extra_headers.setdefault("Authorization", "Bearer $TENSORZERO_API_KEY")
            if extra_headers:
                entry["extra_headers"] = extra_headers
            providers_dict[spec.id] = entry
            available_specs[spec.id] = ProviderSpec(
                id=spec.id,
                name=spec.name,
                base_url=base_url,
                type=spec.type,
                env_var="TENSORZERO_API_KEY" if api_key else None,
                extra_headers=extra_headers,
                models=models,
                default_large=large_model_id,
                default_small=small_model_id,
            )
            provider_models[spec.id] = models
            continue
        if spec.env_var:
            value = _lookup_env(spec.env_var, env_cache)
            if not value:
                continue
        entry = {
            "name": spec.name,
            "base_url": spec.base_url,
            "type": spec.type,
            "models": [model.to_dict() for model in spec.models],
        }
        if spec.env_var:
            entry["api_key"] = f"${spec.env_var}"
        if spec.extra_headers:
            entry["extra_headers"] = spec.extra_headers
        providers_dict[spec.id] = entry
        available_specs[spec.id] = spec
        provider_models[spec.id] = spec.models

    if not providers_dict:
        providers_dict["ollama"] = {
            "name": "Ollama",
            "base_url": "http://localhost:11434/v1",
            "type": "openai",
            "models": [model.to_dict() for model in PROVIDER_SPECS[-1].models],
        }
        available_specs["ollama"] = PROVIDER_SPECS[-1]
        provider_models["ollama"] = PROVIDER_SPECS[-1].models

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
