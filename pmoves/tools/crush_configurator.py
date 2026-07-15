"""Generate PMOVES CLI configuration tailored for PMOVES deployment."""

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
    PROJECT_ROOT / "pmoves" / "env.shared",
    PROJECT_ROOT / "pmoves" / "env.tier-llm",
    PROJECT_ROOT / "pmoves" / "env.tier-llm.generated",
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


# TensorZero is the primary provider - it routes to all backends
# Models are discovered dynamically from TensorZero, not hardcoded here
TENSORZERO_SPEC = ProviderSpec(
    id="tensorzero",
    name="TensorZero Gateway",
    base_url="http://localhost:3030/v1",
    type="openai",
    env_var=None,  # TensorZero handles auth internally
)

# Z.AI Coding Plan direct provider — used when TensorZero is unavailable
# or when operators want direct GLM access without the gateway hop.
# Endpoint-locked: Coding Plan keys only work on /api/coding/paas/v4.
ZAI_SPEC = ProviderSpec(
    id="zai",
    name="Z.AI Coding Plan",
    base_url="https://api.z.ai/api/coding/paas/v4",
    type="openai",
    env_var="Z_AI_API_KEY",
    models=[
        ModelSpec(id="glm-5.2", name="GLM-5.2", role="large", can_reason=True),
        ModelSpec(id="glm-5-turbo", name="GLM-5-Turbo", role="small"),
    ],
    default_large="glm-5.2",
    default_small="glm-5-turbo",
)


def _fetch_tensorzero_models() -> List[ModelSpec]:
    """Fetch available models from TensorZero API dynamically.

    Queries the TensorZero Gateway /v1/models endpoint to discover all available
    models, eliminating the need for hardcoded model lists. Model roles (large/small)
    are inferred from naming patterns.

    Returns:
        List of ModelSpec objects representing available models. Each spec includes:
            - id: Model identifier (e.g., "claude-sonnet-4-5", "qwen3_8b")
            - name: Human-readable model name
            - role: Either "large" (complex reasoning) or "small" (fast tasks)

    Raises:
        urllib.error.URLError: If TensorZero API endpoint is unreachable.
        TimeoutError: If API request exceeds 5 second timeout.
        json.JSONDecodeError: If API response is not valid JSON.

    Example:
        >>> models = _fetch_tensorzero_models()
        >>> large_models = [m for m in models if m.role == "large"]
        >>> print(f"Found {len(large_models)} large models")

    Note:
        - Role inference pattern: Models with "32b", "70b", "claude", "gpt-4o" → "large"
        - All other models → "small"
        - Fallback defaults returned if TensorZero unavailable:
            * qwen3_8b (small)
            * claude-sonnet-4-5 (large, can_reason=True)
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
                if any(x in model_id.lower() for x in ["32b", "70b", "claude", "gpt-4o", "glm-5", "glm-4.7"]):
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
    required_envs: List[str] = field(default_factory=list)

    def missing_envs(self, env_cache: Dict[Path, Dict[str, str]]) -> List[str]:
        keys = list(self.required_envs)
        if self.required_env:
            keys.append(self.required_env)
        return [
            key
            for key in keys
            if not _lookup_env(key, env_cache)
        ]


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
        key="pmoves-cipher",
        config={
            "type": "sse",
            "url": "http://${TS_Z890}:8105/mcp/sse",
            "headers": {"Authorization": "Bearer ${CIPHER_API_TOKEN}"},
            "timeout": 30,
        },
        required_env="CIPHER_API_TOKEN",
    ),
    MCPSpec(
        key="pmoves-cipher-local",
        config={
            "type": "sse",
            "url": "http://localhost:8105/mcp/sse",
            "headers": {"Authorization": "Bearer ${CIPHER_API_TOKEN}"},
            "timeout": 30,
        },
        required_env="CIPHER_API_TOKEN",
    ),
    MCPSpec(
        key="agent-zero",
        config={
            "type": "http",
            "url": "http://${TS_Z890}:8080/mcp",
            "timeout": 30,
        },
    ),
    MCPSpec(
        key="pmoves-nats-fleet",
        config={
            "type": "stdio",
            "command": "uv",
            "args": [
                "--directory",
                "./pmoves-nats-mcp",
                "run",
                "python",
                "-m",
                "nats_mcp.server",
            ],
            "timeout": 60,
        },
        required_commands=["uv"],
        required_env="NATS_URL",
    ),
    MCPSpec(
        key="pmoves-supabase",
        config={
            "type": "stdio",
            "command": "npx",
            "args": [
                "-y",
                "@supabase/mcp-server-postgrest@0.1.1",
                "--apiUrl",
                "${SUPABASE_REST_URL:-http://localhost:8000/rest/v1}",
                "--apiKey",
                "${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_KEY}}",
                "--schema",
                "public",
            ],
            "timeout": 60,
        },
        required_commands=["npx"],
    ),
    MCPSpec(
        key="supabase-db",
        config={
            "type": "stdio",
            "command": "uvx",
            "args": [
                "postgres-mcp@0.3.0",
                "--access-mode=unrestricted",
            ],
            "timeout": 60,
        },
        required_commands=["uvx"],
        required_env="SUPABASE_DB_URI",
    ),
    MCPSpec(
        key="huggingface",
        config={
            "type": "stdio",
            "command": "npx",
            "args": [
                "-y",
                "@llmindset/hf-mcp-server@0.3.30",
            ],
            "timeout": 60,
        },
        required_commands=["npx"],
        required_env="HF_TOKEN",
    ),
    MCPSpec(
        key="tailscale",
        config={
            "type": "stdio",
            "command": "npx",
            "args": [
                "-y",
                "tailscale-mcp@2026.4.10-1",
            ],
            "timeout": 60,
        },
        required_commands=["npx"],
        required_envs=["TAILSCALE_API_KEY", "TAILSCALE_TAILNET"],
    ),
    MCPSpec(
        key="pmoves-docker-gateway",
        config={
            "type": "stdio",
            "command": "docker",
            "args": [
                "mcp",
                "gateway",
                "run",
                "--profile",
                "pmoves_5090_web",
            ],
            "timeout": 60,
        },
        required_commands=["docker"],
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
    MCPSpec(
        key="hostinger",
        config={
            "type": "stdio",
            "command": "docker",
            "args": ["exec", "-i", "pmz-hostinger", "hostinger-api-mcp"],
            "timeout": 60,
        },
        required_commands=["docker"],
        required_env="HOSTINGER_API_TOKEN",
    ),
]


def _select_models(available: Dict[str, ProviderSpec], provider_models: Dict[str, List[ModelSpec]]) -> Dict[str, Dict[str, str]]:
    """Select models — TensorZero primary, Z.AI direct fallback.

    TensorZero routes internally to all backends. When TensorZero is
    unavailable, Z.AI Coding Plan (GLM-5.2 / GLM-5-Turbo) serves as
    the direct fallback so `crush setup` produces a working config even
    on nodes without the gateway running.
    """
    # TensorZero is the preferred gateway
    if "tensorzero" in available:
        tz_spec = available["tensorzero"]
        return {
            "large": {"provider": "tensorzero", "model": tz_spec.default_large or "claude-sonnet-4-5"},
            "small": {"provider": "tensorzero", "model": tz_spec.default_small or "qwen3_8b_local"},
        }

    # Z.AI direct fallback when TensorZero is absent
    if "zai" in available:
        zai_spec = available["zai"]
        return {
            "large": {"provider": "zai", "model": zai_spec.default_large or "glm-5.2"},
            "small": {"provider": "zai", "model": zai_spec.default_small or "glm-5-turbo"},
        }

    # Last resort: scan remaining providers
    large: Optional[Tuple[str, str]] = None
    small: Optional[Tuple[str, str]] = None
    for provider_id, provider in available.items():
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

    This function dynamically discovers all available models from the TensorZero
    Gateway API, eliminating hardcoded model lists. TensorZero serves as the
    single source of truth for model routing and observability.

    The configuration includes:
    - TensorZero as the sole provider (all models route through it)
    - MCP servers (pmoves-mini, docker, n8n) with auto-detection
    - Context paths for PMOVES.AI documentation
    - LSP servers for Python, TypeScript, and Go
    - Tool permissions and attribution settings

    Returns:
        A tuple of:
            - Dict[str, object]: Complete Crush configuration ready for JSON serialization
            - Dict[str, ProviderSpec]: Mapping of provider IDs to ProviderSpec objects
                for runtime inspection. Keys: {"tensorzero"}

    Raises:
        urllib.error.URLError: If TensorZero API is unreachable during model discovery.
        TimeoutError: If TensorZero API request times out (5 second timeout).
        json.JSONDecodeError: If TensorZero API returns invalid JSON.

    Example:
        >>> config, providers = build_config()
        >>> print(f"Found {len(providers['tensorzero'].models)} models")
        >>> with open("~/.config/crush/crush.json", "w") as f:
        ...     json.dump(config, f, indent=2)

    Note:
        - MCP servers are automatically disabled if required commands or env vars are missing
        - Context paths are filtered to only include files that exist
        - Fallback models used if TensorZero unavailable: qwen3_8b, claude-sonnet-4-5
    """
    env_cache = {path: _load_env_file(path) for path in ENV_CANDIDATES}

    base_url_env = _lookup_env("TENSORZERO_BASE_URL", env_cache) or "http://localhost:3030"
    base_url = f"{base_url_env.rstrip('/')}/v1"

    providers_dict: Dict[str, object] = {}
    available_specs: Dict[str, ProviderSpec] = {}
    provider_models: Dict[str, List[ModelSpec]] = {}

    # Fetch models dynamically from TensorZero
    models = _fetch_tensorzero_models()
    tensorzero_reachable = bool(models) and any(
        m.id not in ("qwen3_8b", "claude-sonnet-4-5") for m in models
    )

    # Only add TensorZero provider if the gateway is actually reachable
    # (not returning fallback defaults). When TensorZero is down and
    # Z_AI_API_KEY is present, Z.AI becomes the primary provider.
    if tensorzero_reachable:
        # Find large and small models from dynamic list
        large_models = [m for m in models if m.role == "large"]
        small_models = [m for m in models if m.role == "small"]
        default_large = large_models[0].id if large_models else "claude-sonnet-4-5"
        default_small = small_models[0].id if small_models else "qwen3_8b"

        providers_dict["tensorzero"] = {
            "name": "TensorZero Gateway",
            "base_url": base_url,
            "type": "openai",
            "models": [model.to_dict() for model in models],
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
        available_specs["tensorzero"] = tensorzero_spec
        provider_models["tensorzero"] = models

    # Conditionally add Z.AI direct provider when API key is present
    zai_key = _lookup_env("Z_AI_API_KEY", env_cache)
    if zai_key:
        zai_spec = ProviderSpec(
            id="zai",
            name="Z.AI Coding Plan",
            base_url=ZAI_SPEC.base_url,
            type="openai",
            env_var="Z_AI_API_KEY",
            models=ZAI_SPEC.models,
            default_large=ZAI_SPEC.default_large,
            default_small=ZAI_SPEC.default_small,
        )
        providers_dict["zai"] = {
            "id": "zai",
            "name": "Z.AI Coding Plan",
            "base_url": zai_spec.base_url,
            "api_key": zai_key,
        }
        available_specs["zai"] = zai_spec
        provider_models["zai"] = zai_spec.models

    models_config = _select_models(available_specs, provider_models)

    mcp_config: Dict[str, Dict[str, object]] = {}
    for spec in MCP_SPECS:
        config = dict(spec.config)
        disabled = False
        if spec.required_commands and not all(shutil.which(cmd) for cmd in spec.required_commands):
            disabled = True
        if spec.missing_envs(env_cache):
            disabled = True
        if disabled:
            config["disabled"] = True
        mcp_config[spec.key] = config

    repo_root = PROJECT_ROOT.parent
    context_candidates = [
        Path("CRUSH.md"),
        Path("docs/AGENT_TRAIL.md"),
        Path("pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md"),
        Path("pmoves/config/agent_signatures.yaml"),
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
