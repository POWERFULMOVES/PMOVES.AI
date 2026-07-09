#!/usr/bin/env python3
"""Idempotent Kong route seeder for PMOVES.AI model suits.

Parses ``pmoves/configs/model-suits/*.yaml`` and generates Kong Admin API
calls to create services, routes, upstreams, and plugins.  Safe to run
multiple times -- uses PUT (update-or-create) for idempotency.

Execution chain::

    Agent (91 agents) --> Kong (:8000) --> TensorZero (:3030) --> Provider

CLI::

    python pmoves/tools/kong_route_seeder.py [--dry-run] [--prune] [--kong-url http://localhost:8001]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PMOVES = Path(__file__).resolve().parents[1]
MODEL_SUITS_DIR = PMOVES / "configs" / "model-suits"

# ---------------------------------------------------------------------------
# Logging (never emits API key values)
# ---------------------------------------------------------------------------
log = logging.getLogger("kong_route_seeder")


class _RedactingLoggerAdapter(logging.LoggerAdapter):
    """Redacts secrets from log messages at format time.

    Uses a LoggerAdapter instead of a Filter to avoid mutating LogRecord
    objects in-place (which would poison all handlers globally).
    """

    _SENSITIVE_RE = (
        r"((?:api[_-]?key|apikey|secret|token|password|auth)[^=]*)=\S+"
    )

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        import re as _re

        msg = _re.sub(self._SENSITIVE_RE, r"\1=***REDACTED***", str(msg))
        if "extra" in kwargs and isinstance(kwargs["extra"], dict):
            kwargs["extra"] = self._redact_dict(kwargs["extra"])
        return msg, kwargs

    def _redact_dict(self, d: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = {}
        for k, v in d.items():
            if isinstance(v, dict):
                redacted[k] = self._redact_dict(v)
            elif any(s in k.lower() for s in ("key", "secret", "token", "password")):
                redacted[k] = "***REDACTED***"
            else:
                redacted[k] = v
        return redacted


def _setup_logging(verbose: bool = False) -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("[%(name)s] %(levelname)s %(message)s")
    handler.setFormatter(fmt)
    root = logging.getLogger("kong_route_seeder")
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    return _RedactingLoggerAdapter(root, {})


# ---------------------------------------------------------------------------
# Kong Admin API client
# ---------------------------------------------------------------------------

class KongAdminClient:
    """Minimal typed client for Kong Admin API (DB mode)."""

    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        url = f"{self.base}{path}"
        data = json.dumps(payload).encode() if payload else None
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode() if exc.fp else ""
            log.error("HTTP %s %s -> %s: %s", method, path, exc.code, body[:200])
            if exc.code >= 500:
                raise
            return None
        except urllib.error.URLError as exc:
            log.error("URL error %s %s: %s", method, path, exc.reason)
            raise

    def upsert_service(self, name: str, url: str) -> dict[str, Any] | None:
        service_id = _slugify(name)
        return self._request(
            "PUT",
            f"/services/{service_id}",
            {"name": service_id, "url": url},
        )

    def upsert_route(
        self,
        service_name: str,
        route_name: str,
        paths: list[str],
    ) -> dict[str, Any] | None:
        route_id = _slugify(route_name)
        return self._request(
            "PUT",
            f"/routes/{route_id}",
            {
                "name": route_id,
                "service": {"name": _slugify(service_name)},
                "paths": paths,
                "protocols": ["http", "https"],
                "strip_path": False,
                "tags": ["auto-seeded", "model-suit"],
            },
        )

    def upsert_plugin(
        self,
        plugin_name: str,
        service_name: str | None = None,
        route_name: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        scope = service_name or route_name or "global"
        plugin_id = f"{_slugify(plugin_name)}-{_slugify(scope)}"
        payload: dict[str, Any] = {
            "name": plugin_name,
            "config": config or {},
        }
        if service_name:
            payload["service"] = {"name": _slugify(service_name)}
        if route_name:
            payload["route"] = {"name": _slugify(route_name)}

        return self._request("PUT", f"/plugins/{plugin_id}", payload)

    def list_all(self, resource: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_url = f"/{resource}"
        while next_url:
            try:
                result = self._request("GET", next_url)
                if result and isinstance(result, dict):
                    items.extend(result.get("data", []))
                    next_url = result.get("next") or None
                    if next_url and not next_url.startswith("http"):
                        from urllib.parse import urljoin

                        next_url = urljoin(f"{self.base}/", next_url)
                else:
                    break
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode() if exc.fp else ""
                log.error(
                    "Failed to list %s: HTTP %s - %s",
                    resource,
                    exc.code,
                    error_body[:200],
                )
                if exc.code >= 500:
                    raise
                break
        return items

    def delete_resource(self, resource: str, name: str) -> bool:
        try:
            self._request("DELETE", f"/{resource}/{name}")
            return True
        except Exception:
            return False

    def health(self) -> bool:
        try:
            self._request("GET", "/status")
            return True
        except (urllib.error.URLError, urllib.error.HTTPError):
            return False


# ---------------------------------------------------------------------------
# Model suit parser
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "-")
        .replace(".", "-")
        .replace("_", "-")
        .replace("/", "-")
        .replace(":", "-")
        .strip("-")
    )


def _parse_model_suits(model_suits_dir: Path) -> list[dict[str, Any]]:
    suits: list[dict[str, Any]] = []
    if not model_suits_dir.exists():
        log.error("Model suits directory not found: %s", model_suits_dir)
        return suits

    for yaml_file in sorted(model_suits_dir.glob("*.yaml")):
        log.debug("Parsing model suit: %s", yaml_file.name)
        try:
            doc = yaml.safe_load(yaml_file.read_text())
            if not isinstance(doc, dict):
                log.warning("Skipping non-dict YAML: %s", yaml_file.name)
                continue

            model_id = doc.get("model_id") or doc.get("model", {}).get("id")
            provider = doc.get("provider") or doc.get("model", {}).get("provider")
            api_base = doc.get("api_base") or doc.get("model", {}).get("api_base")
            api_key_env = doc.get("api_key_env_var") or doc.get("model", {}).get("api_key_env_var")

            if model_id and provider:
                suits.append(
                    {
                        "file": yaml_file.name,
                        "model_id": model_id,
                        "provider": provider,
                        "api_base": api_base or _infer_api_base(provider),
                        "api_key_env": api_key_env or _infer_key_env(provider),
                    }
                )
        except yaml.YAMLError as exc:
            log.warning("Failed to parse %s: %s", yaml_file.name, exc)
        except Exception as exc:
            log.warning("Unexpected error parsing %s: %s", yaml_file.name, exc)
    return suits


def _infer_api_base(provider: str) -> str:
    provider = provider.lower()
    mapping = {
        "zai": "https://api.z.ai/v1",
        "zhipu": "https://api.zhipu.ai/v1",
        "zhipu_ai": "https://api.zhipu.ai/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "minimax": "https://api.minimax.chat/v1",
        "alibaba": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "ollama": "http://localhost:11434/v1",
        "groq": "https://api.groq.com/openai/v1",
        "nvidia": "https://integrate.api.nvidia.com/v1",
        "nemotron": "https://integrate.api.nvidia.com/v1",
        "hf": "https://api-inference.huggingface.co/v1",
        "huggingface": "https://api-inference.huggingface.co/v1",
    }
    return mapping.get(provider, "https://api.openai.com/v1")


def _infer_key_env(provider: str) -> str:
    provider = provider.lower()
    mapping = {
        "zai": "Z_AI_API_KEY",
        "zhipu": "Z_AI_API_KEY",
        "zhipu_ai": "ZAI_API_KEY",
        "moonshot": "MOONSHOT_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "alibaba": "ALIBABA_PRO_CODING_PLAN",
        "qwen": "ALIBABA_PRO_CODING_PLAN",
        "ollama": "OLLAMA_API_KEY",
        "groq": "GROQ_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
        "nemotron": "NVIDIA_API_KEY",
        "hf": "HF_TOKEN",
        "huggingface": "HF_TOKEN",
    }
    return mapping.get(provider, f"{provider.upper()}_API_KEY")


# ---------------------------------------------------------------------------
# Route generation
# ---------------------------------------------------------------------------

def _group_by_provider(
    suits: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for suit in suits:
        provider = suit["provider"]
        groups.setdefault(provider, []).append(suit)
    return groups


def _generate_plan(
    groups: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    services: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []

    for provider, models in groups.items():
        service_name = f"pmoves-{provider}"
        api_base = models[0].get("api_base", _infer_api_base(provider))
        services.append(
            {
                "name": service_name,
                "url": api_base,
                "provider": provider,
                "models": [m["model_id"] for m in models],
            }
        )

        for model in models:
            model_id = model["model_id"]
            route_name = f"pmoves-{provider}-{model_id}"
            routes.append(
                {
                    "name": route_name,
                    "service": service_name,
                    "paths": [f"/v1/chat/completions/{model_id}"],
                    "model_id": model_id,
                }
            )

    return {"services": services, "routes": routes}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _execute_plan(
    client: KongAdminClient,
    plan: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    results = {"services_created": 0, "routes_created": 0, "errors": 0}

    for svc in plan["services"]:
        if dry_run:
            log.info("[DRY-RUN] Would create service: %s -> %s", svc["name"], svc["url"])
        else:
            result = client.upsert_service(svc["name"], svc["url"])
            if result:
                log.info("Service upserted: %s", svc["name"])
                results["services_created"] += 1
            else:
                log.error("Failed to upsert service: %s", svc["name"])
                results["errors"] += 1

    for route in plan["routes"]:
        if dry_run:
            log.info("[DRY-RUN] Would create route: %s -> %s", route["name"], route["paths"])
        else:
            result = client.upsert_route(
                route["service"], route["name"], route["paths"]
            )
            if result:
                log.info("Route upserted: %s", route["name"])
                results["routes_created"] += 1
            else:
                log.error("Failed to upsert route: %s", route["name"])
                results["errors"] += 1

    return results


def _prune_stale_routes(
    client: KongAdminClient,
    plan: dict[str, Any],
    dry_run: bool = False,
) -> int:
    current_routes = {r["name"] for r in plan["routes"]}
    existing = client.list_all("routes")
    stale = [
        r
        for r in existing
        if "auto-seeded" in (r.get("tags") or [])
        and r.get("name") not in current_routes
    ]

    pruned = 0
    for route in stale:
        name = route.get("name", "unknown")
        if dry_run:
            log.info("[DRY-RUN] Would prune stale route: %s", name)
        else:
            if client.delete_resource("routes", name):
                log.info("Pruned stale route: %s", name)
                pruned += 1
            else:
                log.warning("Failed to prune route: %s", name)
    return pruned


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Idempotent Kong route seeder for PMOVES.AI"
    )
    parser.add_argument(
        "--kong-url",
        default=os.environ.get("KONG_ADMIN_URL", "http://localhost:8001"),
        help="Kong Admin API base URL (default: KONG_ADMIN_URL env or http://localhost:8001)",
    )
    parser.add_argument(
        "--model-suits-dir",
        type=Path,
        default=MODEL_SUITS_DIR,
        help=f"Directory containing model-suit YAML files (default: {MODEL_SUITS_DIR})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--prune", action="store_true", help="Remove stale routes after seeding")
    parser.add_argument("--json-summary", action="store_true", help="Output JSON summary to stdout")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    client = KongAdminClient(args.kong_url)

    if not client.health():
        log.error("Kong Admin API not reachable at %s", args.kong_url)
        return 1
    log.info("Kong Admin API: OK (%s)", args.kong_url)

    suits = _parse_model_suits(args.model_suits_dir)
    if not suits:
        log.error("No model suits found in %s", args.model_suits_dir)
        return 1
    log.info("Parsed %d model suits from %s", len(suits), args.model_suits_dir)

    groups = _group_by_provider(suits)
    plan = _generate_plan(groups)
    log.info(
        "Plan: %d services, %d routes",
        len(plan["services"]),
        len(plan["routes"]),
    )

    results = _execute_plan(client, plan, dry_run=args.dry_run)

    if args.prune:
        pruned = _prune_stale_routes(client, plan, dry_run=args.dry_run)
        results["routes_pruned"] = pruned

    log.info(
        "Summary: services=%d routes=%d errors=%d",
        results["services_created"],
        results["routes_created"],
        results["errors"],
    )

    if args.json_summary:
        print(json.dumps({"plan": plan, "results": results}, indent=2))

    return 0 if results["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
