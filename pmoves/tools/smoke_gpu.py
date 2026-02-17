#!/usr/bin/env python3
"""GPU smoke harness for Hi-RAG v2 rerank validation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Tuple


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on", "y"}:
        return True
    if value in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _http_status(url: str, timeout: float = 10.0) -> int:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return 0


def _http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> Tuple[int, dict[str, Any] | None]:
    headers = {"Content-Type": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict):
                return int(resp.status), data
            return int(resp.status), None
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8")
            data = json.loads(raw) if raw else None
            if isinstance(data, dict):
                return int(exc.code), data
        except Exception:
            pass
        return int(exc.code), None
    except Exception:
        return 0, None


def _docker_compose_file() -> str:
    return str(Path(__file__).resolve().parents[1] / "docker-compose.yml")


def _docker_http_json(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 20.0,
    service: str = "hi-rag-gateway-v2-gpu",
) -> Tuple[int, dict[str, Any] | None]:
    url = f"http://127.0.0.1:8086{path}"
    marker = "__HTTP_STATUS__:"
    cmd = [
        "docker",
        "compose",
        "-f",
        _docker_compose_file(),
        "exec",
        "-T",
        service,
        "curl",
        "-sS",
        "--max-time",
        str(int(timeout)),
        "-H",
        "content-type: application/json",
        "-X",
        method,
    ]
    if payload is not None:
        cmd.extend(["--data-binary", json.dumps(payload, separators=(",", ":"))])
    cmd.extend([url, "-w", f"\\n{marker}%{{http_code}}"])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception:
        return 0, None
    if proc.returncode != 0:
        return 0, None
    raw = proc.stdout or ""
    if marker not in raw:
        return 0, None
    body, _, status_text = raw.rpartition(f"\n{marker}")
    try:
        status = int(status_text.strip())
    except ValueError:
        status = 0
    body = body.strip()
    if not body:
        return status, None
    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return status, parsed
    except Exception:
        pass
    return status, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Hi-RAG v2 GPU smoke checks.")
    parser.add_argument("--require-qwen", action="store_true", help="Fail unless rerank model contains 'qwen'.")
    parser.add_argument("--stats-only", action="store_true", help="Only check /hirag/admin/stats (no rerank query).")
    args = parser.parse_args()

    gpu_port = os.getenv("HIRAG_V2_GPU_HOST_PORT") or os.getenv("HIRAG_GPU_PORT") or "8087"
    namespace = os.getenv("INDEXER_NAMESPACE", "pmoves")
    strict = _env_bool("GPU_SMOKE_STRICT", True)

    if args.require_qwen:
        print("[Qwen] Inspect v2 stats...")

    print(f"[GPU] Check v2-gpu (:{gpu_port}) up...")
    host_mode = True
    root_code = _http_status(f"http://localhost:{gpu_port}/")
    if root_code != 200:
        docker_root_code, _ = _docker_http_json("/", timeout=10.0)
        if docker_root_code == 200:
            host_mode = False
            print(f"[WARN] host port :{gpu_port} unavailable; using in-network docker exec path")
        else:
            print(f"[FAIL] v2-gpu unavailable (host HTTP {root_code}, in-network HTTP {docker_root_code})")
            return 1
    print("OK")

    print("[GPU] v2-gpu stats...")
    if host_mode:
        stats_code, stats = _http_json(f"http://localhost:{gpu_port}/hirag/admin/stats")
    else:
        stats_code, stats = _docker_http_json("/hirag/admin/stats")
    if stats_code == 200 and stats is not None:
        print("OK")
    else:
        message = f"↷ /hirag/admin/stats returned HTTP {stats_code}"
        if args.require_qwen:
            print(f"[FAIL] {message}. Ensure SMOKE_ALLOW_ADMIN_STATS=true for local smoke.")
            return 1
        print(f"[WARN] {message} (continuing; admin guard may be enabled)")
        stats = None

    if args.require_qwen:
        model = str((stats or {}).get("rerank_model") or "")
        if "qwen" not in model.lower():
            print(
                f"[FAIL] Model ({model}) is not Qwen; set RERANK_MODEL=Qwen/Qwen3-Reranker-4B on v2-gpu and retry."
            )
            return 1
        print("OK")
        if args.stats_only:
            return 0

    if args.stats_only:
        return 0

    print("[GPU] v2-gpu rerank query...")
    payload = {
        "query": "pmoves gpu rerank smoke",
        "namespace": namespace,
        "k": 3,
        "use_rerank": True,
    }
    if host_mode:
        query_code, query_data = _http_json(
            f"http://localhost:{gpu_port}/hirag/query",
            method="POST",
            payload=payload,
            timeout=30.0,
        )
    else:
        query_code, query_data = _docker_http_json(
            "/hirag/query",
            method="POST",
            payload=payload,
            timeout=30.0,
        )
    if query_code != 200 or query_data is None:
        print(f"[FAIL] v2-gpu rerank query failed (HTTP {query_code})")
        return 1

    used_rerank = bool(query_data.get("used_rerank"))
    if strict and not used_rerank:
        print("[FAIL] strict rerank assertion failed (used_rerank=false)")
        return 1
    if not strict and not used_rerank:
        print("[WARN] used_rerank=false (relaxed mode)")
    print("OK")

    print("[GPU] v1-gpu (:8090) (optional)...")
    v1_code = _http_status("http://localhost:8090/")
    if v1_code in {200, 404, 405}:
        print("OK")
    else:
        print(f"[WARN] v1-gpu optional endpoint returned HTTP {v1_code}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
