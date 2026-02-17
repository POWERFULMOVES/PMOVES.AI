#!/usr/bin/env python3
"""Quick Codex-oriented health probe for core PMOVES agent services."""

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


def main() -> int:
    targets = {
        "agent-zero": [
            os.getenv("CODEX_HEALTH_AGENT_ZERO_URL", "http://localhost:8081/healthz"),
            "http://localhost:8098/healthz",
        ],
        "archon": [
            os.getenv("CODEX_HEALTH_ARCHON_URL", "http://localhost:8091/healthz"),
            "http://localhost:8051/healthz",
        ],
        "hirag-v2": [
            os.getenv("CODEX_HEALTH_HIRAG_URL", "http://localhost:8086/hirag/admin/stats"),
        ],
        "flute-gateway": [
            os.getenv("CODEX_HEALTH_FLUTE_URL", "http://localhost:8092/healthz"),
        ],
        "evo-controller": [
            os.getenv("CODEX_HEALTH_EVO_URL", "http://localhost:8090/healthz"),
        ],
        "botz-gateway": [
            os.getenv("CODEX_HEALTH_BOTZ_URL", "http://localhost:8097/healthz"),
        ],
    }

    results: dict[str, dict[str, object]] = {}
    down = 0
    for name, urls in targets.items():
        picked, ok, code = _pick_first_ok(urls)
        if not ok:
            down += 1
        results[name] = {
            "ok": ok,
            "status": code,
            "url": picked,
        }

    for name in targets:
        item = results[name]
        mark = "ok" if item["ok"] else "--"
        print(f"{mark:>2}  {name:<14} {item['status']:>3}  {item['url']}")

    print(json.dumps({"strict": _env_bool("CODEX_HEALTH_STRICT", False), "results": results}, indent=2))
    if _env_bool("CODEX_HEALTH_STRICT", False) and down > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
