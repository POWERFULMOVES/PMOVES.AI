#!/usr/bin/env python3
"""PMOVES model profile sync utility.

Supports:
  - sync: write service override env files from model manifests
  - swap: patch a single model env for a target service
  - seed-list: emit comma-separated Ollama models to pre-pull
  - registry-snapshot: export Supabase model registry JSON
"""

from __future__ import annotations

import argparse
import json
import os
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
MODEL_SYNC_DB_CONTAINER = os.environ.get("MODEL_SYNC_DB_CONTAINER", "pmoves-supabase-db-1")


def _read_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"invalid manifest format (expected mapping): {path}")
    return data


def _write_env(path: Path, env_map: dict[str, object]) -> None:
    lines = [f"{k}={v}" for k, v in sorted(env_map.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def _manifest(profile: str) -> dict:
    path = MODELS_DIR / f"{profile}.yaml"
    if not path.exists():
        raise SystemExit(f"manifest not found: {path}")
    return _read_yaml(path)


def _target_for_host(targets: dict, host: str) -> dict:
    if host in targets and isinstance(targets[host], dict):
        return targets[host]
    for value in targets.values():
        if isinstance(value, dict):
            return value
    return {}


def _sync_agent_zero(manifest: dict, host: str, tensorzero_base: str) -> None:
    target = _target_for_host(manifest.get("targets", {}), host)
    model_id = str(target.get("llm") or manifest.get("llm", {}).get("default", "")).strip()
    if not model_id:
        raise SystemExit("agent-zero manifest is missing llm model for selected host")
    env_map = {
        "AGENT_ZERO_MODEL_ID": model_id,
        "AGENT_ZERO_DECODING": json.dumps(target.get("decoding", {"temperature": 0.3, "top_p": 0.8})),
        "AGENT_ZERO_CONTEXT_WINDOW": target.get("ctx", 32768),
        "OPENAI_COMPAT_BASE_URL": tensorzero_base,
    }
    _write_env(ENV_DIR / ".env.agent-zero.override", env_map)


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
    }
    _write_env(ENV_DIR / ".env.hirag.override", env_map)


def _sync_media(manifest: dict, host: str) -> None:
    env_map: dict[str, object] = {}
    if "asr" in manifest and isinstance(manifest["asr"], dict):
        asr = manifest["asr"].get(host)
        if asr is None:
            asr = manifest["asr"].get("workstation_5090") or next(iter(manifest["asr"].values()), "")
        if asr:
            model = str(asr).split()[0]
            env_map["WHISPER_MODEL"] = model
            env_map["WHISPER_PROVIDER"] = "faster-whisper" if "faster-whisper" in str(asr) else "openai-whisper"
    if host.startswith("jetson"):
        detector = (
            manifest.get("vision", {})
            .get("jetson_orin_8gb", {})
            .get("detector")
        )
        if detector:
            env_map["MEDIA_DETECTOR_MODEL"] = detector
    if not env_map:
        env_map["WHISPER_MODEL"] = "faster-whisper-small"
    _write_env(ENV_DIR / ".env.media.override", env_map)


def _sync_creator(manifest: dict, host: str) -> None:
    vlm = manifest.get("vlm", {})
    model = vlm.get(host) or vlm.get("workstation_5090") or next(iter(vlm.values()), "")
    flows = manifest.get("sd_workflows", {}).get("comfyui", [])
    env_map = {
        "VLM_MODEL": model,
        "COMFY_WORKFLOWS": ",".join(str(x) for x in flows),
    }
    _write_env(ENV_DIR / ".env.creator.override", env_map)


def cmd_sync(args: argparse.Namespace) -> int:
    manifest = _manifest(args.profile)
    if args.profile == "agent-zero":
        _sync_agent_zero(manifest, args.host, args.tensorzero_base)
    elif args.profile == "archon":
        _sync_archon(manifest)
    elif args.profile == "media":
        _sync_media(manifest, args.host)
    elif args.profile == "vlm-and-creator":
        _sync_creator(manifest, args.host)
    else:
        raise SystemExit(f"unsupported profile: {args.profile}")
    return 0


def _append_model(models: set[str], value: object) -> None:
    if not isinstance(value, str):
        return
    model = value.strip()
    if not model:
        return
    # skip non-local model ids / providers
    if model.startswith("tensorzero::") or model.startswith("http://") or model.startswith("https://"):
        return
    if "/" in model and ":" not in model:
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
            _append_model(models, vlm.get(host) or vlm.get("workstation_5090"))
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
        provider = str(row.get("provider_name") or row.get("provider") or "").lower()
        if "ollama" not in provider:
            continue
        _append_model(models, row.get("name"))
    return models


def cmd_seed_list(args: argparse.Namespace) -> int:
    source = args.source.lower()
    models: set[str] = set()
    if source in {"auto", "profile"}:
        models.update(_seed_list_from_profiles(args.host))
    if source in {"auto", "registry"}:
        models.update(_seed_list_from_registry_snapshot())
    if args.include_baseline:
        models.update(DEFAULT_BASELINE_MODELS)
    print(",".join(sorted(models)))
    return 0


def cmd_swap(args: argparse.Namespace) -> int:
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
    url = (
        os.environ.get("SUPABASE_REST_URL")
        or os.environ.get("SUPA_REST_URL")
        or os.environ.get("SUPA_REST_INTERNAL_URL")
        or os.environ.get("SUPABASE_URL")
        or ""
    ).rstrip("/")
    if not url:
        raise SystemExit("SUPABASE_REST_URL/SUPA_REST_URL/SUPABASE_URL is required")
    if url.endswith("/rest/v1"):
        base = url
    else:
        base = f"{url}/rest/v1"

    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("ANON_KEY")
        or ""
    )
    if not key:
        raise SystemExit("SUPABASE key missing (SUPABASE_SERVICE_ROLE_KEY/ANON_KEY)")

    endpoint = f"{base}/models?select=name,provider_id,active"
    headers = {
        "Accept": "application/json",
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "pmoves_core",
        "Content-Profile": "pmoves_core",
    }
    req = urllib.request.Request(endpoint, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        sql = (
            "select coalesce(json_agg("
            "json_build_object('name', name, 'provider_id', provider_id, 'active', active)"
            " order by name"
            "), '[]'::json) "
            "from pmoves_core.models;"
        )
        cmd = [
            "docker",
            "exec",
            MODEL_SYNC_DB_CONTAINER,
            "psql",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-At",
            "-c",
            sql,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
            if proc.returncode != 0:
                raise SystemExit(f"failed to fetch model registry snapshot: {proc.stderr.strip()}")
            raw = (proc.stdout or "").strip()
            payload = json.loads(raw or "[]")
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            raise SystemExit(f"failed to fetch model registry snapshot: {exc}") from exc

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PMOVES model sync utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sync = sub.add_parser("sync", help="sync a model profile into env override file")
    sync.add_argument("--profile", required=True, choices=["agent-zero", "archon", "media", "vlm-and-creator"])
    sync.add_argument("--host", default="workstation_5090")
    sync.add_argument("--tensorzero-base", default="http://tensorzero-gateway:3000")
    sync.set_defaults(func=cmd_sync)

    swap = sub.add_parser("swap", help="swap one service model override")
    swap.add_argument("--service", required=True)
    swap.add_argument("--name", required=True)
    swap.set_defaults(func=cmd_swap)

    seed = sub.add_parser("seed-list", help="print comma-separated Ollama seed models")
    seed.add_argument("--host", default="workstation_5090")
    seed.add_argument("--source", default="auto", choices=["auto", "profile", "registry"])
    seed.add_argument("--include-baseline", action="store_true", default=True)
    seed.set_defaults(func=cmd_seed_list)

    snap = sub.add_parser("registry-snapshot", help="export Supabase model registry snapshot")
    snap.add_argument("--out", required=True)
    snap.set_defaults(func=cmd_registry_snapshot)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
