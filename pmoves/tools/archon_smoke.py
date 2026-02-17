#!/usr/bin/env python3
"""Cross-platform Archon smoke checks without shell/jq dependencies."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import requests


def _read_env_value(env_file: Path, key: str) -> str | None:
    if not env_file.exists():
        return None
    prefix = f"{key}="
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        return line[len(prefix) :].strip().strip('"').strip("'")
    return None


def _json_get(url: str, timeout: float = 8.0) -> tuple[int, dict[str, Any] | None]:
    try:
        resp = requests.get(url, timeout=timeout)
        data: dict[str, Any] | None = None
        try:
            parsed = resp.json()
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            data = None
        return resp.status_code, data
    except requests.RequestException:
        return 0, None


def _put_json(base: str, key: str, value: str, description: str) -> None:
    payload = {"value": value, "category": "rag_strategy", "description": description}
    url = f"{base}/api/credentials/{key}"
    requests.put(url, json=payload, timeout=8.0).raise_for_status()


def _probe_supabase_rest() -> tuple[str, int]:
    rest = "http://127.0.0.1:65421/rest/v1"
    env_local = Path(__file__).resolve().parents[1] / ".env.local"
    env_value = _read_env_value(env_local, "SUPA_REST_URL")
    if env_value:
        rest = env_value
    probe = f"{rest}/it_errors?select=id&limit=1"
    try:
        code = requests.get(probe, timeout=8.0).status_code
    except requests.RequestException:
        code = 0
    return probe, code


def _run_upload(base: str) -> None:
    print(f"-> Archon upload smoke ({base}/api/documents/upload)")
    openai_code, openai = _json_get(f"{base}/api/providers/openai/status")
    openai_ok = bool(openai and openai.get("ok"))
    if openai_code == 0:
        print("WARN: OpenAI provider status endpoint unreachable; continuing with local defaults.")
    if not openai_ok:
        ollama_base = os.getenv("ARCHON_OLLAMA_BASE_URL", "http://pmoves-ollama:11434/v1")
        embed_model = os.getenv("ARCHON_EMBEDDING_MODEL", "qwen3-embedding:4b")
        print(f"-> OpenAI not configured; setting local defaults ({ollama_base}, {embed_model})")
        _put_json(base, "LLM_PROVIDER", "ollama", "PMOVES smoke: default to local Ollama")
        _put_json(base, "EMBEDDING_PROVIDER", "ollama", "PMOVES smoke: embeddings via local Ollama")
        _put_json(base, "LLM_BASE_URL", ollama_base, "PMOVES smoke: in-network Ollama base URL")
        _put_json(base, "EMBEDDING_MODEL", embed_model, "PMOVES smoke: local embedding model")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        tmp_path = Path(handle.name)
        handle.write(f"PMOVES archon upload smoke {dt.datetime.now(dt.timezone.utc).isoformat()}\n")

    try:
        with tmp_path.open("rb") as payload:
            resp = requests.post(
                f"{base}/api/documents/upload",
                files={"file": ("smoke.txt", payload, "text/plain")},
                timeout=20.0,
            )
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        if not isinstance(data, dict):
            raise RuntimeError("upload response not JSON object")
        ok = bool(data.get("success"))
        progress = data.get("progressId") or data.get("progress_id")
        if not ok or not progress:
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            raise RuntimeError(f"unexpected upload response:\n{pretty}")
        print(f"OK archon upload accepted (progressId={progress})")
    finally:
        tmp_path.unlink(missing_ok=True)


def _run_headless(base: str) -> None:
    ready_code, _ = _json_get(f"{base}/ready")
    if ready_code != 200:
        health_code, health = _json_get(f"{base}/healthz")
        supa = (health or {}).get("detail", {}).get("supabase", {}) if isinstance(health, dict) else {}
        supa_http = str(supa.get("http", ""))
        supa_url = str(supa.get("url", ""))
        if not (ready_code == 503 and supa_http == "404" and "host.docker.internal:65421" in supa_url):
            raise RuntimeError(f"archon /ready => {ready_code} (health={health_code}, supabase.http={supa_http}, url={supa_url})")
        print("WARN archon /ready 503 with CLI root 404; treating as soft-ok")

    print("-> Probing MCP bridge via /mcp/describe")
    desc_code, desc = _json_get(f"{base}/mcp/describe")
    if desc_code != 200 or not isinstance(desc, dict) or not bool(desc.get("reachable")):
        raise RuntimeError(f"MCP bridge not reachable (status={desc_code})")

    print("-> Listing MCP commands via /mcp/commands")
    cmds_code, cmds = _json_get(f"{base}/mcp/commands")
    if cmds_code != 200 or not isinstance(cmds, dict):
        print("WARN /mcp/commands unavailable; bridge reachable so treating as soft-ok")
        print("OK archon headless health")
        return

    commands = cmds.get("commands")
    if not isinstance(commands, list) or not commands:
        print("WARN no MCP commands advertised; treating as soft-ok")
        print("OK archon headless health")
        return

    chosen = None
    for item in commands:
        if isinstance(item, dict) and item.get("name") == "form.get":
            chosen = item.get("name")
            break
    if chosen is None:
        first = commands[0]
        if isinstance(first, dict):
            chosen = first.get("name")
    if not chosen:
        print("WARN command list parse issue; treating as soft-ok")
        print("OK archon headless health")
        return

    execute_payload = {"tool": chosen, "arguments": {}}
    try:
        exec_resp = requests.post(f"{base}/mcp/execute", json=execute_payload, timeout=12.0)
        if exec_resp.status_code == 200:
            print(f"OK archon MCP command executed: {chosen}")
        else:
            print(f"WARN MCP execute {chosen} => {exec_resp.status_code} (soft-ok)")
    except requests.RequestException as exc:
        print(f"WARN MCP execute {chosen} failed ({exc}); bridge reachable so soft-ok")
    print("OK archon headless health")


def run_full(base: str) -> None:
    api_code, _ = _json_get(f"{base}/healthz")
    if api_code != 200:
        raise RuntimeError(f"archon /healthz => {api_code}")
    probe, pg = _probe_supabase_rest()
    if pg in (0,) or pg >= 500:
        raise RuntimeError(f"Supabase REST probe failed (HTTP {pg}) URL: {probe}")
    print(f"OK archon /healthz 200 and Supabase REST probe {probe} (HTTP {pg})")
    _run_upload(base)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["full", "upload", "headless"])
    parser.add_argument("--base-url", default=os.getenv("ARCHON_BASE_URL", "http://localhost:8091"))
    args = parser.parse_args()

    try:
        if args.mode == "full":
            run_full(args.base_url.rstrip("/"))
        elif args.mode == "upload":
            _run_upload(args.base_url.rstrip("/"))
        else:
            _run_headless(args.base_url.rstrip("/"))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
