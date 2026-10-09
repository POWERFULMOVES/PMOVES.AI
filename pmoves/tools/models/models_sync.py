#!/usr/bin/env python3
"""PMOVES model profile sync utility.

Supports:
  - sync: write service override env files from static model manifests
  - sync-dynamic: write overrides from live Supabase registry mappings;
      for targets agent-zero/all, generate the _model_config presets.yaml
      from the same registry rows (registry = config authority; TensorZero
      is one optional lane, not a hard dependency)
  - swap: patch a single model env for a target service
  - seed-list: emit comma-separated local models to pre-pull
  - registry-snapshot: export active model registry JSON
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime dependency check
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc


ROOT = Path(__file__).resolve().parents[2]  # pmoves/
MODELS_DIR = ROOT / "models"
ENV_DIR = ROOT
DEFAULT_BASELINE_MODELS = ("qwen3:8b", "nomic-embed-text")
DEFAULT_CLOUD_FALLBACK_ORDER = ("ollama_cloud", "cloudflare_free", "coding_plan")
MODEL_SYNC_DB_CONTAINER = os.environ.get("MODEL_SYNC_DB_CONTAINER", "pmoves-supabase-db-1")
MODEL_SYNC_DB_CANDIDATES = (
    "supabase_db_pmoves",
    "pmoves-supabase-db-1",
    "pmoves_supabase_db_1",
)


def _read_yaml(path: Path) -> dict:
    """Load a YAML file and return its contents as a dict."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"invalid manifest format (expected mapping): {path}")
    return data


def _write_env(path: Path, env_map: dict[str, object]) -> None:
    """Write key=value pairs to an env override file, sorted alphabetically."""
    lines = [f"{k}={v}" for k, v in sorted(env_map.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def _manifest(profile: str) -> dict:
    """Load a named model profile manifest from the models directory."""
    path = MODELS_DIR / f"{profile}.yaml"
    if not path.exists():
        raise SystemExit(f"manifest not found: {path}")
    return _read_yaml(path)


def _target_for_host(targets: dict, host: str) -> dict:
    """Resolve a host-specific target config, falling back to the first available."""
    if host in targets and isinstance(targets[host], dict):
        return targets[host]
    for value in targets.values():
        if isinstance(value, dict):
            return value
    return {}


def _parse_bool(value: str | None) -> bool:
    """Return True if the string value is a common truthy representation."""
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv_env(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    """Parse a comma-separated env value into a tuple, using default if empty."""
    if not value:
        return default
    items = [item.strip() for item in value.split(",") if item.strip()]
    return tuple(items) if items else default


def _supabase_rest_base() -> str:
    """Resolve the Supabase REST base URL from env, appending /rest/v1 if needed."""
    url = (
        os.environ.get("SUPABASE_REST_URL")
        or os.environ.get("SUPA_REST_URL")
        or os.environ.get("SUPA_REST_INTERNAL_URL")
        or os.environ.get("SUPABASE_URL")
        or ""
    ).strip().rstrip("/")
    if not url:
        raise SystemExit("SUPABASE_REST_URL/SUPA_REST_URL/SUPABASE_URL is required")
    return url if url.endswith("/rest/v1") else f"{url}/rest/v1"


def _supabase_key() -> str:
    """Resolve the Supabase API key from env (service role preferred, anon fallback)."""
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("ANON_KEY")
        or ""
    ).strip()
    if not key:
        raise SystemExit("SUPABASE key missing (SUPABASE_SERVICE_ROLE_KEY/ANON_KEY)")
    return key


def _supabase_headers(key: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "pmoves_core",
        "Content-Profile": "pmoves_core",
    }


def _http_get_json(endpoint: str, headers: dict[str, str], timeout: int = 20) -> list[dict]:
    req = urllib.request.Request(endpoint, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _db_json_query(sql: str) -> list[dict]:
    container = _resolve_db_container()
    cmd = [
        "docker",
        "exec",
        container,
        "psql",
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-At",
        "-c",
        sql,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=25)
    if proc.returncode != 0:
        raise SystemExit(f"failed SQL fallback via {container}: {proc.stderr.strip()}")
    raw = (proc.stdout or "").strip()
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON payload from SQL fallback: {exc}") from exc
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _resolve_db_container() -> str:
    explicit = os.environ.get("MODEL_SYNC_DB_CONTAINER", "").strip()
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    candidates.extend(name for name in MODEL_SYNC_DB_CANDIDATES if name not in candidates)

    try:
        proc = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"unable to discover docker containers for SQL fallback: {exc}") from exc

    available = {line.strip() for line in (proc.stdout or "").splitlines() if line.strip()}
    for name in candidates:
        if name in available:
            return name
    if explicit:
        raise SystemExit(
            f"MODEL_SYNC_DB_CONTAINER '{explicit}' not running. Available containers: {', '.join(sorted(available)) or 'none'}"
        )
    raise SystemExit(
        "unable to find Supabase DB container for SQL fallback; "
        "set MODEL_SYNC_DB_CONTAINER explicitly"
    )


def _load_service_models() -> list[dict]:
    base = _supabase_rest_base()
    key = _supabase_key()
    endpoint = (
        f"{base}/v_service_models?"
        "select=service_name,function_name,variant_name,priority,weight,"
        "model_id,model_name,model_type,provider_name,provider_type,api_base"
    )
    try:
        rows = _http_get_json(endpoint, _supabase_headers(key))
        if rows:
            return rows
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        pass

    sql = (
        "select coalesce(json_agg(row_to_json(t) "
        "order by t.service_name, t.function_name, t.priority, t.weight desc), '[]'::json) "
        "from ("
        "  select service_name, function_name, variant_name, priority, weight, "
        "         model_id, model_name, model_type, provider_name, provider_type, api_base "
        "  from pmoves_core.v_service_models"
        ") t;"
    )
    return _db_json_query(sql)


def _load_active_models() -> list[dict]:
    base = _supabase_rest_base()
    key = _supabase_key()
    endpoint = (
        f"{base}/v_active_models?"
        "select=model_id,model_type,provider_name,provider_type,context_length,vram_mb,capabilities"
    )
    try:
        rows = _http_get_json(endpoint, _supabase_headers(key))
        if rows:
            return rows
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        pass

    sql = (
        "select coalesce(json_agg(row_to_json(t) "
        "order by t.model_type, t.context_length desc nulls last), '[]'::json) "
        "from ("
        "  select model_id, model_type, provider_name, provider_type, context_length, vram_mb, capabilities "
        "  from pmoves_core.v_active_models"
        ") t;"
    )
    return _db_json_query(sql)


def _normalize_model_id(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _provider_lane(provider_name: str, provider_type: str) -> str:
    """Classify a provider into a routing lane (local, ollama_cloud, cloudflare_free, etc.)."""
    name = provider_name.lower()
    ptype = provider_type.lower()

    if "ollama_cloud" in name:
        return "ollama_cloud"
    if "cloudflare" in name:
        return "cloudflare_free"
    if any(token in name for token in ("glm", "zai", "alibaba", "claude", "codex", "coding_plan", "kilocode")):
        return "coding_plan"
    if ptype in {"ollama", "vllm", "tts"}:
        return "local"
    if any(token in name for token in ("_local", "_edge", "local", "edge")):
        return "local"
    return "other_cloud"


def _lane_rank(provider_name: str, provider_type: str, cloud_order: tuple[str, ...]) -> int:
    lane = _provider_lane(provider_name, provider_type)
    if lane == "local":
        return 0
    for idx, entry in enumerate(cloud_order, start=1):
        if lane == entry:
            return idx
    return len(cloud_order) + 5


def _safe_int(value: object, default: int = 9999) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _filter_rows(
    rows: list[dict],
    services: tuple[str, ...],
    functions: tuple[str, ...],
    model_types: tuple[str, ...],
) -> list[dict]:
    service_set = {item.strip().lower() for item in services if item.strip()}
    func_order = [item.strip().lower() for item in functions if item.strip()]
    type_set = {item.strip().lower() for item in model_types if item.strip()}

    service_rows = [row for row in rows if str(row.get("service_name", "")).strip().lower() in service_set]
    if not service_rows:
        return []

    if type_set:
        service_rows = [row for row in service_rows if str(row.get("model_type", "")).strip().lower() in type_set]
        if not service_rows:
            return []

    if not func_order:
        return service_rows

    for function_name in func_order:
        current = [row for row in service_rows if str(row.get("function_name", "")).strip().lower() == function_name]
        if current:
            return current
    return service_rows


def _select_best(rows: list[dict], cloud_order: tuple[str, ...]) -> tuple[dict | None, tuple[str, ...]]:
    """Select the best model row and build a fallback chain ordered by lane priority."""
    if not rows:
        return None, ()

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            _lane_rank(str(row.get("provider_name", "")), str(row.get("provider_type", "")), cloud_order),
            _safe_int(row.get("priority"), 9999),
            -_safe_float(row.get("weight"), 0.0),
            -_safe_int(row.get("context_length"), 0),
        ),
    )
    chain: list[str] = []
    for row in sorted_rows:
        model_id = _normalize_model_id(row.get("model_id"))
        if model_id and model_id not in chain:
            chain.append(model_id)
    return sorted_rows[0], tuple(chain)


def _fallback_from_active_models(active_models: list[dict], model_types: tuple[str, ...], cloud_order: tuple[str, ...]) -> tuple[dict | None, tuple[str, ...]]:
    type_set = {item.strip().lower() for item in model_types if item.strip()}
    rows = [
        row for row in active_models
        if (not type_set) or str(row.get("model_type", "")).strip().lower() in type_set
    ]
    return _select_best(rows, cloud_order)


# --- Agent Zero presets generation (registry cutover) -----------------------
# The registry is the config authority: these helpers project the same
# Supabase rows the old env lane consumed into the A0 2.5 _model_config
# presets.yaml schema. TensorZero is one lane among several, not a hard dep.

A0_PRESETS_SUBPATH = Path("data/agent-zero/usr/plugins/_model_config/presets.yaml")
A0_PRESETS_TEMPLATE = "pmoves/config/agent-zero/model-presets-docked.yaml"
A0_OLLAMA_API_BASE = "http://pmoves-ollama-1:11434"

# Registry provider_name -> A0 model provider id (model_providers.yaml ids).
PROVIDER_ID_ALIASES = {
    "tensorzero": "tensorzero",
    "zai": "zai",
    "zai coding plan": "zai_coding",
    "ollama": "ollama",
    "nvidia nim": "nvidia_nim",
    "openai": "openai",
}

# Degraded-mode rows: the checked-in fallback template expressed as
# registry-shaped rows (TensorZero chat lane default + its embedding lane).
A0_FALLBACK_TEMPLATE_ROWS = (
    {
        "service_name": "agent_zero",
        "function_name": "chat",
        "model_type": "chat",
        "model_id": "chat_zai_glm53",
        "provider_name": "tensorzero",
        "provider_type": "tensorzero",
        "context_length": 128000,
    },
    {
        "service_name": "tensorzero",
        "function_name": "embeddings",
        "model_type": "embedding",
        "model_id": "qwen3_embedding_4b_local",
        "provider_name": "tensorzero",
        "provider_type": "tensorzero",
        "context_length": 0,
    },
)


def _provider_id_for(provider_name: str) -> str:
    """Map a registry provider_name to an A0 model provider id."""
    key = provider_name.strip().lower()
    if key in PROVIDER_ID_ALIASES:
        return PROVIDER_ID_ALIASES[key]
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return slug or "other"


def _a0_chat_model_name(provider_id: str, model_id: str) -> str:
    if provider_id == "tensorzero":
        return f"tensorzero::model_name::{model_id}"
    return f"{provider_id}/{model_id}"


def _a0_embed_model_name(provider_id: str, model_id: str) -> str:
    if provider_id == "tensorzero":
        # openai/ prefix REQUIRED: A0's embed path hands the name straight to
        # litellm without adding a provider prefix (see the presets template
        # header) -- bare tensorzero::... fails with "LLM Provider NOT provided".
        return f"openai/tensorzero::embedding_model_name::{model_id}"
    if provider_id == "openai":
        return model_id
    return f"{provider_id}/{model_id}"


def _a0_api_base(row: dict, provider_id: str, tensorzero_base: str) -> str | None:
    if provider_id == "tensorzero":
        return f"{tensorzero_base.rstrip('/')}/openai/v1"
    base = str(row.get("api_base") or "").strip()
    if base:
        return base
    if provider_id == "ollama":
        return A0_OLLAMA_API_BASE
    return None


def _a0_model_block(row: dict, tensorzero_base: str, kind: str) -> dict:
    """Build a chat/utility preset block matching the _model_config schema."""
    provider_id = _provider_id_for(str(row.get("provider_name", "")))
    model_id = _normalize_model_id(row.get("model_id"))
    api_base = _a0_api_base(row, provider_id, tensorzero_base)
    block: dict = {
        "provider": provider_id,
        "name": _a0_chat_model_name(provider_id, model_id),
    }
    if api_base:
        block["api_base"] = api_base
    if kind == "chat":
        block.update({
            "ctx_length": _safe_int(row.get("context_length"), 32768),
            "ctx_history": 0.7,
            "vision": False,
            "max_embeds": 10,
        })
    else:
        block.update({
            "ctx_length": _safe_int(row.get("context_length"), 32768),
            "ctx_input": 0.7,
        })
    block.update({"rl_requests": 0, "rl_input": 0, "rl_output": 0, "kwargs": {}})
    return block


def _a0_embedding_block(row: dict, tensorzero_base: str) -> dict:
    provider_id = _provider_id_for(str(row.get("provider_name", "")))
    model_id = _normalize_model_id(row.get("model_id"))
    api_base = _a0_api_base(row, provider_id, tensorzero_base)
    block: dict = {
        "provider": provider_id,
        "name": _a0_embed_model_name(provider_id, model_id),
    }
    if api_base:
        block["api_base"] = api_base
    block.update({"rl_requests": 0, "rl_input": 0, "kwargs": {}})
    return block


def _a0_chat_lane(
    rows: list[dict],
    active_models: list[dict],
    cloud_order: tuple[str, ...],
) -> tuple[list[dict], dict | None, tuple[str, ...]]:
    """agent_zero chat lane: same selection the old env lane performed."""
    functions = _parse_csv_env(
        os.environ.get("MODEL_DYNAMIC_AGENT_ZERO_FUNCTIONS"),
        ("chat", "coding", "reasoning", "orchestrator", "default"),
    )
    chat_rows = _filter_rows(rows, ("agent_zero", "agent-zero", "agentzero"), functions, ("chat",))
    selected, chain = _select_best(chat_rows, cloud_order)
    if selected is None:
        fb_rows = [
            row for row in active_models
            if str(row.get("model_type", "")).strip().lower() == "chat"
        ]
        selected, chain = _select_best(fb_rows, cloud_order)
        if selected is not None:
            chat_rows = fb_rows
    return chat_rows, selected, chain


def _a0_embedding_row(
    rows: list[dict],
    active_models: list[dict],
    cloud_order: tuple[str, ...],
) -> dict | None:
    """agent_zero embedding lane: archon-style embed selection."""
    embed_functions = _parse_csv_env(
        os.environ.get("MODEL_DYNAMIC_EMBED_FUNCTIONS"),
        ("embeddings", "embedding", "embed", "retrieval", "default"),
    )
    embed_row, _chain = _select_best(
        _filter_rows(rows, ("tensorzero", "archon", "hirag"), embed_functions, ("embedding",)),
        cloud_order,
    )
    if embed_row is None:
        embed_row, _chain = _fallback_from_active_models(active_models, ("embedding",), cloud_order)
    if embed_row is None:
        print("WARNING: no embedding row resolvable; using template embedding lane")
        embed_row = dict(A0_FALLBACK_TEMPLATE_ROWS[1])
    return embed_row


def _build_a0_presets(
    rows: list[dict],
    active_models: list[dict],
    tensorzero_base: str,
    cloud_order: tuple[str, ...],
) -> tuple[list[tuple[str, dict]], dict | None]:
    """Order presets: T0 lane first (resilient), then best direct, then fallbacks."""
    chat_rows, selected, chain = _a0_chat_lane(rows, active_models, cloud_order)

    def chat_name(row: dict) -> str:
        return _a0_chat_model_name(
            _provider_id_for(str(row.get("provider_name", ""))),
            _normalize_model_id(row.get("model_id")),
        )

    presets: list[tuple[str, dict]] = []
    emitted: set[str] = set()
    t0_row = next(
        (row for row in chat_rows if _provider_id_for(str(row.get("provider_name", ""))) == "tensorzero"),
        None,
    )
    if t0_row is not None:
        presets.append(("TensorZero", t0_row))
        emitted.add(chat_name(t0_row))
    if selected is not None and chat_name(selected) not in emitted:
        presets.append(("Registry", selected))
        emitted.add(chat_name(selected))

    by_model: dict[str, dict] = {}
    for row in chat_rows:
        model_id = _normalize_model_id(row.get("model_id"))
        if model_id and model_id not in by_model:
            by_model[model_id] = row
    fallback_idx = 0
    for model_id in chain[1:5]:
        row = by_model.get(model_id) or {
            "model_id": model_id,
            "provider_name": "tensorzero",
            "provider_type": "tensorzero",
        }
        name = chat_name(row)
        if name in emitted:
            continue
        fallback_idx += 1
        emitted.add(name)
        presets.append((f"Fallback-{fallback_idx}", row))

    return presets, _a0_embedding_row(rows, active_models, cloud_order)


def _write_a0_presets(
    rows: list[dict],
    active_models: list[dict],
    out_path: Path,
    instance: str = "docked",
    tensorzero_base: str = "http://tensorzero-gateway:3000",
    cloud_order: tuple[str, ...] = DEFAULT_CLOUD_FALLBACK_ORDER,
    apply: bool = True,
) -> None:
    """Generate the Agent Zero _model_config presets.yaml from registry rows.

    The T0 lane (when a tensorzero chat-lane row exists) is emitted first as
    the resilient preset, then the best direct lane, then the fallback chain
    as Fallback-1..N. When the live file exists and --apply-presets was not
    passed, the result is written as presets.yaml.new beside it with a one-line
    diff summary; the operator applies it by rename.
    """
    presets, embed_row = _build_a0_presets(rows, active_models, tensorzero_base, cloud_order)
    if not presets:
        print("WARNING: no chat-lane row resolvable; writing an empty presets file")
    doc: list[dict] = []
    for preset_name, row in presets:
        preset = {
            "name": preset_name,
            "chat": _a0_model_block(row, tensorzero_base, "chat"),
            "utility": _a0_model_block(row, tensorzero_base, "utility"),
        }
        if embed_row is not None:
            preset["embedding"] = _a0_embedding_block(embed_row, tensorzero_base)
        doc.append(preset)

    header = (
        "# GENERATED FILE - do not hand-edit.\n"
        f"# Source: pmoves/tools/models/models_sync.py sync-dynamic (instance: {instance}).\n"
        f"# Checked-in fallback template: {A0_PRESETS_TEMPLATE}\n"
    )
    payload = header + yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    applied = True
    if out_path.exists() and not apply:
        new_path = Path(str(out_path) + ".new")
        new_path.write_text(payload, encoding="utf-8")
        try:
            old_doc = yaml.safe_load(out_path.read_text(encoding="utf-8")) or []
        except yaml.YAMLError:
            old_doc = []
        old_names = ", ".join(str(p.get("name")) for p in old_doc if isinstance(p, dict)) or "(none)"
        new_names = ", ".join(name for name, _row in presets) or "(none)"
        print(
            f"diff summary: {out_path} [{old_names}] -> {new_path} [{new_names}] "
            "(rename the .new file over the live one to apply, or rerun with --apply-presets)"
        )
        applied = False
    else:
        out_path.write_text(payload, encoding="utf-8")
        print(f"wrote {out_path}")

    print(f"template: {A0_PRESETS_TEMPLATE}")
    manifest = {
        "instance": instance,
        "presets_file": str(out_path),
        "applied": applied,
        "presets": [name for name, _row in presets],
        "chat_lane": {
            name: _a0_chat_model_name(
                _provider_id_for(str(row.get("provider_name", ""))),
                _normalize_model_id(row.get("model_id")),
            )
            for name, row in presets
        },
    }
    if embed_row is not None:
        manifest["embedding"] = _normalize_model_id(embed_row.get("model_id"))
    print(json.dumps(manifest, indent=2))


def _sync_dynamic_agent_zero(rows: list[dict], active_models: list[dict], cloud_order: tuple[str, ...], tensorzero_base: str, apply_presets: bool = True) -> None:
    """Agent Zero output is now the generated presets file, not env overrides.

    The .env.agent-zero.override lane (AGENT_ZERO_MODEL_ID /
    AGENT_ZERO_FALLBACK_MODELS / OPENAI_COMPAT_BASE_URL) is dead: the A0 2.5
    _model_config preset plugin ignores those vars. The registry emits
    presets.yaml instead, with the T0 lane demoted to one lane among several.
    """
    _write_a0_presets(
        rows,
        active_models,
        ROOT / A0_PRESETS_SUBPATH,
        instance="docked",
        tensorzero_base=tensorzero_base,
        cloud_order=cloud_order,
        apply=apply_presets,
    )


def _sync_dynamic_archon(rows: list[dict], active_models: list[dict], cloud_order: tuple[str, ...]) -> None:
    embed_functions = _parse_csv_env(
        os.environ.get("MODEL_DYNAMIC_EMBED_FUNCTIONS"),
        ("embeddings", "embedding", "embed", "retrieval", "default"),
    )
    rerank_functions = _parse_csv_env(
        os.environ.get("MODEL_DYNAMIC_RERANK_FUNCTIONS"),
        ("rerank", "reranker", "default"),
    )

    embed_row, embed_chain = _select_best(
        _filter_rows(rows, ("tensorzero", "archon", "hirag"), embed_functions, ("embedding",)),
        cloud_order,
    )
    if embed_row is None:
        embed_row, embed_chain = _fallback_from_active_models(active_models, ("embedding",), cloud_order)

    rerank_row, rerank_chain = _select_best(
        _filter_rows(rows, ("hirag", "archon"), rerank_functions, ("reranker",)),
        cloud_order,
    )
    if rerank_row is None:
        rerank_row, rerank_chain = _fallback_from_active_models(active_models, ("reranker",), cloud_order)

    env_map = {
        "HIRAG_EMBED_MODEL": _normalize_model_id((embed_row or {}).get("model_id")) or "sentence-transformers/all-MiniLM-L6-v2",
        "HIRAG_RERANK_MODEL": _normalize_model_id((rerank_row or {}).get("model_id")) or "BAAI/bge-reranker-base",
        "HIRAG_RERANK_ENABLED": "true" if rerank_row is not None else "false",
        "GRAPH_BOOST": 0.15,
        "OLLAMA_URL": "http://pmoves-ollama:11434",
        "SENTENCE_MODEL": "all-MiniLM-L6-v2",
        "HIRAG_EMBED_FALLBACK_MODELS": ",".join(embed_chain[1:5]),
        "HIRAG_RERANK_FALLBACK_MODELS": ",".join(rerank_chain[1:5]),
        "HIRAG_MODEL_SELECTION_MODE": "dynamic_registry",
    }
    _write_env(ENV_DIR / ".env.hirag.override", env_map)


def _sync_dynamic_creator(rows: list[dict], active_models: list[dict], cloud_order: tuple[str, ...], host: str) -> None:
    del host  # reserved for future host-aware creator strategy
    vl_functions = _parse_csv_env(
        os.environ.get("MODEL_DYNAMIC_VL_FUNCTIONS"),
        ("vision", "vl", "caption", "chat", "default"),
    )
    selected, chain = _select_best(
        _filter_rows(rows, ("creator", "pmoves_media_processor", "vl_sentinel", "agent_zero"), vl_functions, ("vl",)),
        cloud_order,
    )
    if selected is None:
        selected, chain = _fallback_from_active_models(active_models, ("vl",), cloud_order)
    if selected is None:
        return

    env_map = {
        "VLM_MODEL": _normalize_model_id(selected.get("model_id")),
        "VLM_MODEL_SELECTION_MODE": "dynamic_registry",
        "VLM_FALLBACK_MODELS": ",".join(chain[1:5]),
    }
    _write_env(ENV_DIR / ".env.creator.override", env_map)



def _sync_agent_zero(manifest: dict, host: str, tensorzero_base: str, apply_presets: bool = True) -> None:
    """Static manifests flow through the same presets generator.

    The manifest's llm entry becomes a single synthetic registry row:
    provider-prefixed ids map to their direct lane, everything else rides the
    TensorZero model_name lane (the routing the old AGENT_ZERO_MODEL_ID +
    OPENAI_COMPAT_BASE_URL env pair encoded, minus the dead env write).
    """
    target = _target_for_host(manifest.get("targets", {}), host)
    model_id = str(target.get("llm") or manifest.get("llm", {}).get("default", "")).strip()
    if not model_id:
        raise SystemExit("agent-zero manifest is missing llm model for selected host")
    prefixed = re.match(r"^([a-z0-9_]+)/(.+)$", model_id)
    if prefixed:
        rows = [{
            "model_id": prefixed.group(2),
            "provider_name": prefixed.group(1),
            "provider_type": prefixed.group(1),
        }]
    else:
        rows = [{
            "model_id": model_id,
            "provider_name": "tensorzero",
            "provider_type": "tensorzero",
            "context_length": _safe_int(target.get("ctx"), 32768),
        }]
    _write_a0_presets(
        rows,
        [],
        ROOT / A0_PRESETS_SUBPATH,
        instance="docked",
        tensorzero_base=tensorzero_base,
        apply=apply_presets,
    )


def _sync_archon(manifest: dict) -> None:
    embedding = manifest.get("embedding", {})
    reranker = manifest.get("reranker", {})
    hirag = manifest.get("hirag", {})
    env_map = {
        "HIRAG_EMBED_MODEL": embedding.get("default", "sentence-transformers/all-MiniLM-L6-v2"),
        "HIRAG_RERANK_MODEL": reranker.get("default", "BAAI/bge-reranker-base"),
        "HIRAG_RERANK_ENABLED": "true" if hirag.get("enable_rerank", True) else "false",
        "GRAPH_BOOST": hirag.get("graph_boost", 0.15),
        "OLLAMA_URL": hirag.get("ollama_url", "http://pmoves-ollama:11434"),
        "SENTENCE_MODEL": hirag.get("sentence_model_fallback", "all-MiniLM-L6-v2"),
        "HIRAG_MODEL_SELECTION_MODE": "manifest_static",
    }
    _write_env(ENV_DIR / ".env.hirag.override", env_map)


def _sync_media(manifest: dict, host: str) -> None:
    env_map: dict[str, object] = {}
    if "asr" in manifest and isinstance(manifest["asr"], dict):
        asr = manifest["asr"].get(host)
        if asr is None:
            asr = manifest["asr"].get("desktop-9950xd") or next(iter(manifest["asr"].values()), "")
        if asr:
            model = str(asr).split()[0]
            env_map["WHISPER_MODEL"] = model
            env_map["WHISPER_PROVIDER"] = "faster-whisper" if "faster-whisper" in str(asr) else "openai-whisper"
    if host.startswith("jetson"):
        detector = manifest.get("vision", {}).get("jetson_orin_8gb", {}).get("detector")
        if detector:
            env_map["MEDIA_DETECTOR_MODEL"] = detector
    if not env_map:
        env_map["WHISPER_MODEL"] = "faster-whisper-small"
    _write_env(ENV_DIR / ".env.media.override", env_map)


def _sync_creator(manifest: dict, host: str) -> None:
    vlm = manifest.get("vlm", {})
    model = vlm.get(host) or vlm.get("desktop-9950xd") or next(iter(vlm.values()), "")
    flows = manifest.get("sd_workflows", {}).get("comfyui", [])
    env_map = {
        "VLM_MODEL": model,
        "VLM_MODEL_SELECTION_MODE": "manifest_static",
        "COMFY_WORKFLOWS": ",".join(str(x) for x in flows),
    }
    _write_env(ENV_DIR / ".env.creator.override", env_map)


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync a static model profile manifest into service override env files."""
    manifest = _manifest(args.profile)
    if args.profile == "agent-zero":
        _sync_agent_zero(manifest, args.host, args.tensorzero_base, args.apply_presets)
    elif args.profile == "archon":
        _sync_archon(manifest)
    elif args.profile == "media":
        _sync_media(manifest, args.host)
    elif args.profile == "vlm-and-creator":
        _sync_creator(manifest, args.host)
    else:
        raise SystemExit(f"unsupported profile: {args.profile}")
    return 0


def cmd_sync_dynamic(args: argparse.Namespace) -> int:
    """Sync Agent Zero presets from live Supabase model registry mappings."""
    cloud_order = _parse_csv_env(
        args.cloud_order or os.environ.get("MODEL_CLOUD_FALLBACK_ORDER"),
        DEFAULT_CLOUD_FALLBACK_ORDER,
    )
    target = args.target.strip().lower()
    try:
        rows = _load_service_models()
        active_models = _load_active_models()
    except (SystemExit, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as exc:
        if target != "agent-zero":
            raise
        # Degrade, don't die: emit presets from the checked-in template rows
        # so standalone nodes keep a stale-but-valid config surface.
        rows = [dict(row) for row in A0_FALLBACK_TEMPLATE_ROWS]
        active_models = []
        print(
            f"WARNING: model registry unreachable ({exc}); "
            "emitting Agent Zero presets from fallback template rows",
            file=sys.stderr,
        )

    if target in {"all", "agent-zero"}:
        _sync_dynamic_agent_zero(rows, active_models, cloud_order, args.tensorzero_base, args.apply_presets)
    if target in {"all", "archon"}:
        _sync_dynamic_archon(rows, active_models, cloud_order)
    if target in {"all", "creator"}:
        _sync_dynamic_creator(rows, active_models, cloud_order, args.host)
    return 0


def _append_model(models: set[str], value: object) -> None:
    model = _normalize_model_id(value)
    if not model:
        return
    if model.startswith("tensorzero::") or model.startswith("http://") or model.startswith("https://"):
        return
    models.add(model)


def _seed_list_from_profiles(host: str) -> set[str]:
    models: set[str] = set()
    for profile in ("agent-zero", "archon", "vlm-and-creator"):
        path = MODELS_DIR / f"{profile}.yaml"
        if not path.exists():
            continue
        manifest = _read_yaml(path)
        if profile == "agent-zero":
            target = _target_for_host(manifest.get("targets", {}), host)
            _append_model(models, target.get("llm"))
        elif profile == "archon":
            _append_model(models, manifest.get("embedding", {}).get("local_ollama"))
        elif profile == "vlm-and-creator":
            vlm = manifest.get("vlm", {})
            _append_model(models, vlm.get(host) or vlm.get("desktop-9950xd"))
    return models


def _seed_list_from_registry_snapshot() -> set[str]:
    snapshot = ROOT / "models" / "registry.snapshot.json"
    models: set[str] = set()
    if not snapshot.exists():
        return models
    try:
        data = json.loads(snapshot.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return models
    if not isinstance(data, list):
        return models
    for row in data:
        if not isinstance(row, dict):
            continue
        lane = _provider_lane(str(row.get("provider_name", "")), str(row.get("provider_type", "")))
        if lane != "local":
            continue
        _append_model(models, row.get("model_id"))
    return models


def _seed_list_from_dynamic_registry(cloud_order: tuple[str, ...]) -> set[str]:
    models: set[str] = set()
    rows = _load_service_models()
    selected: list[dict] = []
    for service, functions, model_types in (
        (("agent_zero", "agent-zero", "agentzero"), ("chat", "coding", "reasoning", "default"), ("chat",)),
        (("tensorzero", "archon", "hirag"), ("embeddings", "embedding", "embed", "default"), ("embedding",)),
        (("hirag", "archon"), ("rerank", "reranker", "default"), ("reranker",)),
        (("creator", "pmoves_media_processor", "vl_sentinel"), ("vision", "vl", "caption", "default"), ("vl",)),
    ):
        best, chain = _select_best(_filter_rows(rows, service, functions, model_types), cloud_order)
        if best is not None:
            selected.append(best)
        for model_id in chain[:3]:
            _append_model(models, model_id)
    for row in selected:
        lane = _provider_lane(str(row.get("provider_name", "")), str(row.get("provider_type", "")))
        if lane == "local":
            _append_model(models, row.get("model_id"))
    return models


def cmd_seed_list(args: argparse.Namespace) -> int:
    """Print comma-separated list of local models to pre-pull on startup."""
    source = args.source.lower()
    cloud_order = _parse_csv_env(
        os.environ.get("MODEL_CLOUD_FALLBACK_ORDER"),
        DEFAULT_CLOUD_FALLBACK_ORDER,
    )
    models: set[str] = set()
    if source in {"auto", "profile"}:
        models.update(_seed_list_from_profiles(args.host))
    if source in {"auto", "registry"}:
        models.update(_seed_list_from_registry_snapshot())
    if source in {"auto", "dynamic"}:
        models.update(_seed_list_from_dynamic_registry(cloud_order))
    if args.include_baseline:
        models.update(DEFAULT_BASELINE_MODELS)
    print(",".join(sorted(models)))
    return 0


def cmd_swap(args: argparse.Namespace) -> int:
    """Hot-swap a single model for a target service by writing its override env."""
    service = args.service.strip().lower()
    if not args.name:
        raise SystemExit("--name is required for swap")
    env_file = None
    key = None
    if service in {"agents", "agent-zero"}:
        env_file = ENV_DIR / ".env.agent-zero.override"
        key = "AGENT_ZERO_MODEL_ID"
    elif service in {"hirag", "hi-rag-gateway-v2"}:
        env_file = ENV_DIR / ".env.hirag.override"
        key = "HIRAG_RERANK_MODEL"
    elif service.startswith("media"):
        env_file = ENV_DIR / ".env.media.override"
        key = "WHISPER_MODEL" if "whisper" in args.name else "MEDIA_DETECTOR_MODEL"
    elif service in {"creator", "comfyui"}:
        env_file = ENV_DIR / ".env.creator.override"
        key = "VLM_MODEL"
    else:
        raise SystemExit(f"unsupported service: {args.service}")
    _write_env(env_file, {key: args.name})
    return 0


def cmd_registry_snapshot(args: argparse.Namespace) -> int:
    """Export the active Supabase model registry to a JSON snapshot file."""
    base = _supabase_rest_base()
    key = _supabase_key()
    endpoint = (
        f"{base}/v_active_models?"
        "select=model_id,model_type,provider_name,provider_type,context_length,vram_mb,capabilities"
    )
    try:
        payload = _http_get_json(endpoint, _supabase_headers(key))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        sql = (
            "select coalesce(json_agg(row_to_json(t) "
            "order by t.model_type, t.context_length desc nulls last), '[]'::json) "
            "from ("
            "  select model_id, model_type, provider_name, provider_type, context_length, vram_mb, capabilities "
            "  from pmoves_core.v_active_models"
            ") t;"
        )
        payload = _db_json_query(sql)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands."""
    parser = argparse.ArgumentParser(description="PMOVES model sync utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sync = sub.add_parser("sync", help="sync a model profile into env override file")
    sync.add_argument("--profile", required=True, choices=["agent-zero", "archon", "media", "vlm-and-creator"])
    sync.add_argument("--host", default="desktop-9950xd")
    sync.add_argument("--tensorzero-base", default="http://tensorzero-gateway:3000")
    sync.add_argument("--apply-presets", action="store_true", help="overwrite the live presets.yaml (default: write presets.yaml.new beside it when it exists)")
    sync.set_defaults(func=cmd_sync)

    sync_dynamic = sub.add_parser("sync-dynamic", help="sync overrides from live registry mappings")
    sync_dynamic.add_argument("--target", default="all", choices=["all", "agent-zero", "archon", "creator"])
    sync_dynamic.add_argument("--host", default="desktop-9950xd")
    sync_dynamic.add_argument("--tensorzero-base", default="http://tensorzero-gateway:3000")
    sync_dynamic.add_argument("--cloud-order", default="", help="comma list, default MODEL_CLOUD_FALLBACK_ORDER")
    sync_dynamic.add_argument("--apply-presets", action="store_true", help="overwrite the live presets.yaml (default: write presets.yaml.new beside it when it exists)")
    sync_dynamic.set_defaults(func=cmd_sync_dynamic)

    swap = sub.add_parser("swap", help="swap one service model override")
    swap.add_argument("--service", required=True)
    swap.add_argument("--name", required=True)
    swap.set_defaults(func=cmd_swap)

    seed = sub.add_parser("seed-list", help="print comma-separated local models to seed")
    seed.add_argument("--host", default="desktop-9950xd")
    seed.add_argument("--source", default="auto", choices=["auto", "profile", "registry", "dynamic"])
    seed.add_argument("--include-baseline", action="store_true", default=True)
    seed.set_defaults(func=cmd_seed_list)

    snap = sub.add_parser("registry-snapshot", help="export Supabase active model snapshot")
    snap.add_argument("--out", required=True)
    snap.set_defaults(func=cmd_registry_snapshot)
    return parser


def main() -> int:
    """Entry point: parse args and dispatch to the selected subcommand."""
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
