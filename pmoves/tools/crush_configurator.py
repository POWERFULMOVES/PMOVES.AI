"""Generate PMOVES CLI configuration tailored for PMOVES deployment."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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



# Ollama (local) provider — used on SPARK and other local-inference nodes when
# TensorZero is unavailable. Model list is discovered dynamically.
OLLAMA_SPEC = ProviderSpec(
    id="ollama",
    name="Ollama",
    base_url="http://localhost:11434/v1",
    type="openai",
    env_var=None,
    models=[],
    default_large=None,
    default_small=None,
)



def _fetch_ollama_models(base_url: str = "http://localhost:11434") -> List[ModelSpec]:
    """Fetch available chat models from the local Ollama API.

    Queries Ollama's /api/tags endpoint to discover locally pulled models. Only
    models that advertise the 'completion' capability are included, so embedding
    models are not surfaced as chat candidates. Roles are inferred from the model's
    reported parameter_size (>= 30B or 'T' units → large), falling back to naming
    patterns only when the size field is missing.
    """
    import re
    import urllib.request
    import urllib.error

    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = []
            for model in data.get("models", []):
                model_id = model.get("name", "")
                if not model_id:
                    continue
                capabilities = model.get("capabilities", [])
                # Ollama API doesn't always include a capabilities field.
                # If absent, assume the model supports completion (chat).
                # Only skip models explicitly declaring non-completion capabilities
                # (e.g. embedding-only models that list only "embed").
                if capabilities and "completion" not in capabilities:
                    continue
                role = "small"
                details = model.get("details") or {}
                param_size = details.get("parameter_size", "")
                match = re.match(r"([\d.]+)\s*([A-Za-z]+)", str(param_size))
                if match:
                    value = float(match.group(1))
                    unit = match.group(2).upper()
                    if unit == "T" or (unit == "B" and value >= 30.0):
                        role = "large"
                else:
                    # Fallback to naming heuristics when Ollama omits size metadata
                    name_lower = model_id.lower()
                    if any(
                        x in name_lower
                        for x in ["32b", "70b", "120b", "claude", "gpt-4o", "glm-5", "glm-4.7", "nemotron", "hermes3:70b"]
                    ):
                        role = "large"
                models.append(ModelSpec(id=model_id, name=model_id, role=role))
            return models
    except (urllib.error.URLError, TimeoutError):
        return []



def _detect_node(env_cache: Dict[Path, Dict[str, str]]) -> str:
    """Detect whether this node is the DGX Spark sidecar.

    Returns 'spark' when the environment (SPARK_CHAT_MODEL, SPARK_PORT) or the
    hostname (HOSTNAME, NODE_NAME, platform.node()) indicates 'pmoves-spark'.
    Otherwise returns 'fleet' for fleet/Tailscale defaults.
    """
    if any(
        (_lookup_env(var, env_cache) or os.getenv(var))
        for var in ("SPARK_CHAT_MODEL", "SPARK_PORT")
    ):
        return "spark"
    for var in ("HOSTNAME", "NODE_NAME"):
        val = os.getenv(var, "")
        if val and "pmoves-spark" in val.lower():
            return "spark"
    if "pmoves-spark" in platform.node().lower():
        return "spark"
    return "fleet"



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
    # Cipher URL + bearer are MIRRORED from pmoves/config/mcp_inventory.json,
    # which is canonical and was already correct. This generator does not read it,
    # which is exactly how it kept two defects the inventory had fixed: the path
    # (/api/mcp/sse answers 404; /mcp/sse answers 200 -- a property of the server,
    # not of one container) and the bearer (an unset ${VAR} is sent LITERALLY, and
    # the shim 401s any non-empty token, so cipher never connected). #2729 fixed
    # both for claude/kilo through the inventory; crush was missed because nothing
    # linked it. test_crush_cipher_matches_inventory.py now fails if they diverge.
    MCPSpec(
        key="pmoves-cipher",
        config={
            "type": "sse",
            "url": "http://${TS_Z890}:8105/mcp/sse",
            "headers": {"Authorization": "Bearer ${CIPHER_API_TOKEN}"},
            "timeout": 30,
        },
        # Still NO required_env -- but the 2026-08 reasoning for it is now dead
        # and must not be quoted again. That reasoning was: "the shim accepts an
        # EMPTY bearer, which is exactly what the `:-` default in the header
        # above exists to send." Both halves have expired. There is no `:-`
        # default any more (removed 2026-09-02), and once CIPHER_API_TOKEN is
        # set on the serving node an empty bearer is a MEASURED 401, not a 200.
        #
        # The decision stands on a different, still-true argument:
        # missing_envs() -> `disabled: True`, i.e. the entry DISAPPEARS from the
        # generated config on a tokenless node. That is the silently-tool-less
        # outcome this lane exists to end, and it is strictly worse than an entry
        # that is present and 401s where session_check can name it.
        #
        # The counter-argument is real and deliberately not taken here: unlike
        # `_pmoves_roster_verdicts`, `disabled: True` IS a durable, greppable,
        # diffable record, so for crush specifically the gate would be a better
        # observability channel than the 401. Reversing #2762's un-gating is a
        # behaviour change on every tokenless node and belongs in a lane that can
        # measure crush end-to-end; it is not free-riding on this one.
        # See pmoves/docs/operations/CIPHER_AUTH_RUNBOOK.md §6/§6a.
    ),
    MCPSpec(
        key="pmoves-cipher-local",
        config={
            "type": "sse",
            "url": "http://localhost:8105/mcp/sse",
            "headers": {"Authorization": "Bearer ${CIPHER_API_TOKEN}"},
            "timeout": 30,
        },
        # See pmoves-cipher above: still no required_env, and for the reason
        # stated there -- NOT for the retired "the empty bearer is supported by
        # the server", which is false once the token is set.
    ),
    MCPSpec(
        key="agent-zero",
        config={
            "type": "sse",
            "url": "http://localhost:8081/mcp/t-${AGENT_ZERO_MCP_TOKEN}/sse",
            "timeout": 30,
        },
        required_env="AGENT_ZERO_MCP_TOKEN",
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


def _select_models(available: Dict[str, ProviderSpec], provider_models: Dict[str, List[ModelSpec]], node: str) -> Dict[str, Dict[str, str]]:
    """Select models — TensorZero primary, local Ollama on Spark, Z.AI direct fallback."""
    # TensorZero is the preferred gateway
    if "tensorzero" in available:
        tz_spec = available["tensorzero"]
        return {
            "large": {"provider": "tensorzero", "model": tz_spec.default_large or "claude-sonnet-4-5"},
            "small": {"provider": "tensorzero", "model": tz_spec.default_small or "qwen3_8b_local"},
        }

    # On Spark, local Ollama is the preferred fallback over cloud providers
    if node == "spark" and "ollama" in available:
        ollama_spec = available["ollama"]
        fallback_model = ollama_spec.models[0].id if ollama_spec.models else ""
        return {
            "large": {"provider": "ollama", "model": ollama_spec.default_large or fallback_model},
            "small": {"provider": "ollama", "model": ollama_spec.default_small or fallback_model},
        }

    # Z.AI direct fallback when TensorZero is absent
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


# ---------------------------------------------------------------------------
# Pair-review finding (2026-08-26): the same unresolvable-${TS_*} bug that
# PR #2769 killed for Claude's roster was still live here. `pmoves-cipher`
# emits http://${TS_Z890}:8105/mcp/sse; on a node without the tailscale CLI,
# Crush receives the literal string as a hostname -- a silent 404 in the exact
# harness whose cipher fix (#2762) had just deliberately dropped required_env.
# #2762 removed the token gate; this restores a *narrower* one for the hostname.
# ---------------------------------------------------------------------------

# Only cross-node hostnames. Credential vars stay OUT of this gate: the shim
# accepts an empty bearer, and credentials were #2762's decision to un-gate.
_TS_VAR_RE = re.compile(r"\$\{(TS_[A-Za-z0-9_]+)[^}]*\}")

TS_HELPER = PROJECT_ROOT / "scripts" / "tailscale-node-ips.sh"


def _resolve_ts_vars(names, env):
    """Resolve TS_* names from env, falling back to the shared tailscale helper.

    The helper is the ONE definition (crush-env.sh and claude-pmoves.sh both
    source it); running it here rather than reimplementing keeps this from
    becoming a third copy of the resolution. Never fatal: a missing helper or
    a failed run just leaves the name unresolved.
    """
    resolved = {name: (env.get(name) or "").strip() for name in names}
    missing = [n for n, v in resolved.items() if not v]
    if not missing or not TS_HELPER.is_file():
        return resolved
    listing = " ".join(missing)
    # Built by concatenation, not one f-string: the shell's ${!n} indirection
    # is not parseable inside f-string braces.
    cmd = (
        f'source "{TS_HELPER}" >/dev/null 2>&1 || exit 0; '
        + "for n in "
        + listing
        + '; do printf "%s=%s\\n" "$n" "${!n}"; done'
    )
    try:
        proc = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True, timeout=30,
            env={k: v for k, v in env.items() if k != "PMOVES_PYTHON"},
        )
        for line in proc.stdout.splitlines():
            name, _, value = line.partition("=")
            if name in resolved and not resolved[name] and value.strip():
                resolved[name] = value.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return resolved


def guard_unresolvable_ts(mcp_config, env=None):
    """Disable any spec whose URL references an unresolvable ${TS_*} var.

    Deliberately does NOT bake the resolved IP into the config: the runtime env
    (crush-env.sh sources the same helper) carries live resolution on every
    launch, and persisting tailnet topology into ~/.config/crush.json would
    leak what the helper itself is careful never to hardcode. The guard only
    converts the would-be-silent case (var unresolvable at generation time)
    into a disabled entry with a named reason on stderr.
    """
    env = dict(os.environ) if env is None else dict(env)
    names = sorted({
        m.group(1)
        for cfg in mcp_config.values()
        if isinstance(cfg, dict)
        for m in _TS_VAR_RE.finditer(str(cfg.get("url", "")))
    })
    if not names:
        return []
    resolved = _resolve_ts_vars(names, env)
    notes = []
    for key, cfg in mcp_config.items():
        if not isinstance(cfg, dict) or cfg.get("disabled"):
            continue
        for m in _TS_VAR_RE.finditer(str(cfg.get("url", ""))):
            var = m.group(1)
            if not resolved.get(var):
                cfg["disabled"] = True
                notes.append(
                    f"{key}: disabled — {var} unresolvable (env + tailscale helper "
                    f"both empty); the url would be handed to Crush as the literal "
                    f"${{{var}}} and 404 silently"
                )
                break
    for note in notes:
        print(f"[crush-config] {note}", file=sys.stderr)
    return notes


def build_config() -> Tuple[Dict[str, object], Dict[str, ProviderSpec]]:
    """Build Crush config with TensorZero as the preferred provider.

    This function dynamically discovers all available models from the TensorZero
    Gateway API, eliminating hardcoded model lists. TensorZero serves as the
    single source of truth for model routing and observability.

    The configuration is node-aware: on the DGX Spark sidecar, local Ollama is
    used as the fallback provider and the generated MCP server URLs point to the
    local Cipher and Agent Zero sidecar endpoints instead of the fleet Tailscale
    hosts.

    The configuration includes:
    - TensorZero as the preferred gateway (all models route through it when reachable)
    - Ollama local fallback on SPARK when TensorZero is unavailable
    - MCP servers (pmoves-mini, docker, n8n) with auto-detection
    - Context paths for PMOVES.AI documentation
    - LSP servers for Python, TypeScript, and Go
    - Tool permissions and attribution settings

    Returns:
        A tuple of:
            - Dict[str, object]: Complete Crush configuration ready for JSON serialization
            - Dict[str, ProviderSpec]: Mapping of provider IDs to ProviderSpec objects
                for runtime inspection. Keys vary by node (e.g. {"tensorzero"} or
                {"ollama"}).

    Raises:
        urllib.error.URLError: If TensorZero API is unreachable during model discovery.
        TimeoutError: If TensorZero API request times out (5 second timeout).
        json.JSONDecodeError: If TensorZero API returns invalid JSON.

    Example:
        >>> config, providers = build_config()
        >>> print(f"Found {len(providers.get('tensorzero', providers['ollama']).models)} models")
        >>> with open("~/.config/crush/crush.json", "w") as f:
        ...     json.dump(config, f, indent=2)

    Note:
        - MCP servers are automatically disabled if required commands or env vars are missing
        - Context paths are filtered to only include files that exist
        - Fallback models used if TensorZero unavailable: qwen3_8b, claude-sonnet-4-5
        - On SPARK, Ollama models are discovered from the local /api/tags endpoint
    """
    env_cache = {path: _load_env_file(path) for path in ENV_CANDIDATES}
    node = _detect_node(env_cache)

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
        # NO `api_key` VALUE. Crush reads ZAI_API_KEY from the environment (its
        # own README documents that name), and crush-pmoves bridges the funnel's
        # Z_AI_API_KEY onto it. Writing the resolved secret here put it in
        # ~/.config/crush/crush.json in plaintext, at rest, where rotating the
        # funnel value changed nothing -- the config kept serving the stale one.
        #
        # The presence of Z_AI_API_KEY is still what GATES adding the provider;
        # only the value is no longer copied out of the environment onto disk.
        providers_dict["zai"] = {
            "id": "zai",
            "name": "Z.AI Coding Plan",
            "base_url": zai_spec.base_url,
        }
        available_specs["zai"] = zai_spec
        provider_models["zai"] = zai_spec.models

    # On the DGX Spark sidecar, prefer local Ollama over a remote TensorZero gateway.
    # Only add Ollama as a provider when we can actually discover its pulled models
    # from the local /api/tags endpoint — no hardcoded model tags.
    if node == "spark":
        raw_ollama_base = (
            _lookup_env("OLLAMA_SPARK_BASE_URL", env_cache)
            or _lookup_env("SPARK_CHAT_API_BASE", env_cache)
            or "http://localhost:11434"
        )
        ollama_base_url = f"{raw_ollama_base.rstrip('/')}/v1"
        ollama_models = _fetch_ollama_models(raw_ollama_base)

        if ollama_models:
            ollama_large = [m for m in ollama_models if m.role == "large"]
            ollama_small = [m for m in ollama_models if m.role == "small"]
            ollama_default_large = ollama_large[0].id if ollama_large else ollama_models[0].id
            ollama_default_small = ollama_small[0].id if ollama_small else ollama_default_large

            providers_dict["ollama"] = {
                "name": "Ollama",
                "base_url": ollama_base_url,
                "type": "openai",
                "models": [model.to_dict() for model in ollama_models],
            }
            ollama_spec = ProviderSpec(
                id="ollama",
                name="Ollama",
                base_url=ollama_base_url,
                type="openai",
                env_var=None,
                models=ollama_models,
                default_large=ollama_default_large,
                default_small=ollama_default_small,
            )
            available_specs["ollama"] = ollama_spec
            provider_models["ollama"] = ollama_models

    models_config = _select_models(available_specs, provider_models, node)

    mcp_config: Dict[str, Dict[str, object]] = {}
    for spec in MCP_SPECS:
        config = dict(spec.config)
        if node == "spark":
            if spec.key in ("pmoves-cipher", "pmoves-cipher-local"):
                config["url"] = "http://localhost:8105/mcp/sse"
            elif spec.key == "agent-zero":
                config["url"] = "http://localhost:8093/mcp"
        # Normalize agent-zero to SSE with token auth on every node (Spark uses :8093,
        # others use :8081). Only applies if the URL hasn't already been set to SSE.
        if spec.key == "agent-zero" and "/t-" not in str(config.get("url", "")):
            port = "8093" if node == "spark" else "8081"
            config["url"] = f"http://localhost:{port}/mcp/t-${{AGENT_ZERO_MCP_TOKEN}}/sse"
            config["type"] = "sse"
        disabled = config.pop("disabled", False)
        if spec.required_commands and not all(shutil.which(cmd) for cmd in spec.required_commands):
            disabled = True
        if spec.missing_envs(env_cache):
            disabled = True
        if disabled:
            config["disabled"] = True
        mcp_config[spec.key] = config

    # Pair-review finding: ${TS_*} in a url with no resolution is the silent-404
    # class this roster shares with Claude's; guard it the same way (drop with a
    # named reason, never silently). Credential vars are deliberately NOT gated
    # here — that is #2762's un-gating decision and it stands.
    guard_unresolvable_ts(mcp_config)

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
        # Written at launch by crush-pmoves (node_identity.py resolver). Crush
        # has no --append-system-prompt, so this generated context file is how
        # the session's node identity reaches the model. exists() keeps nodes
        # that never ran the launcher clean. Gitignored runtime state.
        # ABSOLUTE, unlike every other candidate: Crush joins relative
        # context_paths to its working directory, so launching from a repo
        # subdirectory would resolve a nested pmoves/data/... that never
        # exists and silently drop the identity (review P2). The committed
        # candidates are repo-relative because they predate this concern and
        # are read from the project root; runtime state gets the robust form.
        (repo_root / "pmoves/data/identity/node-identity.md").resolve(),
    ]

    context_paths = [
        candidate.as_posix()
        for candidate in context_candidates
        if (candidate.is_absolute() and candidate.exists())
        or (not candidate.is_absolute() and (repo_root / candidate).exists())
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
