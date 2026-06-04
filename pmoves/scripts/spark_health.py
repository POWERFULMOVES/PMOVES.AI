#!/usr/bin/env python3
"""SPARK node health probe for DGX Spark (pmoves-dgx-spark).

Checks critical SPARK node services:
- Ollama inference (11434)
- NATS leaf (local health)
- Cipher Memory (8105) - optional, fails gracefully
- Agent Zero SPARK (8093) - optional, fails gracefully
- TensorZero gateway (3030)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Iterable


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on", "y"}:
        return True
    if value in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _probe(url: str, timeout: float = 3.0) -> tuple[bool, int]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, int(response.status)
    except urllib.error.HTTPError as exc:
        return False, int(exc.code)
    except Exception:
        return False, 0


def _pick_first_ok(urls: Iterable[str]) -> tuple[str | None, bool, int]:
    for url in urls:
        ok, code = _probe(url)
        if ok:
            return url, True, code
    first = next(iter(urls), None)
    if first is None:
        return None, False, 0
    ok, code = _probe(first)
    return first, ok, code


def _check_ollama() -> dict:
    """Check Ollama model inventory."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as resp:
            data = json.load(resp)
            models = data.get("models", [])
            return {
                "ok": True,
                "model_count": len(models),
                "models": [m.get("name", "unknown") for m in models],
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> int:
    targets = {
        "ollama-tags": [
            os.getenv("SPARK_OLLAMA_URL", "http://localhost:11434/api/tags"),
        ],
        "tensorzero": [
            os.getenv("SPARK_TENSORZERO_URL", "http://localhost:3030/health"),
            "http://localhost:3030/healthz",
        ],
        "nats-local": [
            os.getenv("SPARK_NATS_URL", "http://localhost:8222/healthz"),
            "http://localhost:8222/health",
        ],
    }

    # Optional services (fail gracefully)
    optional = {
        "cipher-memory": [
            os.getenv("SPARK_CIPHER_URL", "http://localhost:8105/health"),
        ],
        "agent-zero-spark": [
            os.getenv("SPARK_AGENT_ZERO_URL", "http://localhost:8093/healthz"),
            "http://localhost:8093/health",
        ],
    }

    results: dict[str, dict] = {}
    down = 0

    # Check required services
    for name, urls in targets.items():
        picked, ok, code = _pick_first_ok(urls)
        if not ok:
            down += 1
        results[name] = {
            "ok": ok,
            "status": code,
            "url": picked,
        }

    # Check optional services
    for name, urls in optional.items():
        picked, ok, code = _pick_first_ok(urls)
        results[name] = {
            "ok": ok,
            "status": code,
            "url": picked,
            "optional": True,
        }

    # Check Ollama models
    ollama_result = _check_ollama()
    results["ollama-models"] = ollama_result

    # Print summary
    print("=== SPARK Node Health Check ===")
    for name in ["ollama-tags", "tensorzero", "nats-local", "cipher-memory", "agent-zero-spark"]:
        if name not in results:
            continue
        item = results[name]
        mark = "ok" if item["ok"] else "--"
        opt = " (optional)" if item.get("optional") else ""
        print(f"{mark:>2}  {name:<20} {item['status']:>3}  {item['url']}{opt}")

    # Print Ollama model summary
    if ollama_result.get("ok"):
        models = ollama_result.get("models", [])
        print(f"\n📦 Ollama: {len(models)} models deployed")
        for model in models:
            print(f"   - {model}")

    print("\n" + json.dumps({"strict": _env_bool("SPARK_HEALTH_STRICT", False), "results": results}, indent=2))

    if _env_bool("SPARK_HEALTH_STRICT", False) and down > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
