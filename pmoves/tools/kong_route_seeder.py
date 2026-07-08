#!/usr/bin/env python3
"""Idempotent Kong route seeder for PMOVES.AI model suits.

Parses ``pmoves/configs/model-suits/*.yaml`` and generates Kong Admin API
calls to create services, routes, upstreams, and plugins.  Safe to run
multiple times -- uses PUT (update-or-create) for idempotency.

Execution chain::

    Agent (91 agents) --> Kong (:8000) --> TensorZero (:3030) --> Provider

CLI:
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
LOG = logging.getLogger("kong_route_seeder")


class _SecretsFilter(logging.Filter):
    """Drops log records that contain probable API key values."""

    _SENSITIVE = ("api_key", "apikey", "api-key", "_key", "secret", "token", "password")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        lowered = msg.lower()
        for trigger in self._SENSITIVE:
            if trigger in lowered and "=" in lowered:
                import re as _re

                record.msg = _re.sub(
                    rf"({trigger}[^=]*)=\S+", r"\1=***REDACTED***", record.msg
                )
                if record.args:
                    record.args = tuple(
                        _re.sub(rf"({trigger}[^=]*)=\S+", r"\1=***REDACTED***", str(a))
                        for a in record.args
                    )
        return True


def _setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(_SecretsFilter())
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(fmt)
    LOG.setLevel(level)
    LOG.addHandler(handler)


# ---------------------------------------------------------------------------
# Kong Admin API client
# ---------------------------------------------------------------------------
class KongAdminClient:
    """Thin Kong Admin API client with idempotent PUT semantics."""

    def __init__(self, base_url: str, dry_run: bool = False) -> None:
        self.base = base_url.rstrip("/")
        self.dry_run = dry_run

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        url = f"{self.base}{path}"
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.dry_run and method in ("POST", "PUT", "PATCH", "DELETE"):
            LOG.info("[DRY-RUN] %s %s  body=%s", method, url, _redact_payload(payload))
            return None
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                LOG.debug("Exists (409): %s %s", method, url)
                return None
            if exc.code == 404 and method == "DELETE":
                LOG.debug("Not found for delete (404): %s", url)
                return None
            error_body = exc.read().decode("utf-8") if exc.fp else ""
            LOG.error("Kong API error: %s %s -> %s: %s", method, url, exc.code, error_body)
            raise

    def list_all(self, resource: str) -> list[dict[str, Any]]:
        """Paginated GET /{resource}."""
        results: list[dict[str, Any]] = []
        next_url = f"/{resource}"
        while next_url:
            url = f"{self.base}{next_url}"
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    results.extend(data.get("data", []))
                    next_url = data.get("next")
            except urllib.error.HTTPError as exc:
                LOG.error("Failed to list %s: %s", resource, exc)
                break
        return results

    def upsert_service(self, name: str, url: str, **extra: Any) -> dict[str, Any] | None:
        payload = {"name": name, "url": url, **extra}
        return self._request("PUT", f"/services/{name}", payload)

    def upsert_route(
        self, service_name: str, name: str, paths: list[str], **extra: Any
    ) -> dict[str, Any] | None:
        payload = {
            "name": name,
            "service": {"name": service_name},
            "paths": paths,
            "strip_path": False,
            **extra,
        }
        return self._request("PUT", f"/routes/{name}", payload)

    def upsert_upstream(self, name: str, **extra: Any) -> dict[str, Any] | None:
        payload = {"name": name, **extra}
        return self._request("PUT", f"/upstreams/{name}", payload)

    def upsert_target(self, upstream_name: str, target: str, **extra: Any) -> dict[str, Any] | None:
        payload = {"target": target, **extra}
        return self._request("POST", f"/upstreams/{upstream_name}/targets", payload)

    def upsert_plugin(
        self,
        plugin_name: str,
        service_name: str | None = None,
        route_name: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"name": plugin_name}
        if service_name:
            payload["service"] = {"name": service_name}
        if route_name:
            payload["route"] = {"name": route_name}
        if config:
            payload["config"] = config
        return self._request("POST", "/plugins", payload)

    def delete_service_cascade(self, name: str) -> None:
        routes = self.list_all("routes")
        for route in routes:
            svc = route.get("service")
            if svc and svc.get("name") == name:
                self._request("DELETE", f"/routes/{route['name']}")
        plugins = self.list_all("plugins")
        for plugin in plugins:
            svc = plugin.get("service")
            if svc and svc.get("name") == name:
                self._request("DELETE", f"/plugins/{plugin['id']}")
        self._request("DELETE", f"/services/{name}")

    def delete_route(self, name: str) -> None:
        self._request("DELETE", f"/routes/{name}")

    def delete_plugin(self, plugin_id: str) -> None:
        self._request("DELETE", f"/plugins/{plugin_id}")

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base}/status", timeout=5) as resp:
                return resp.status == 200
        except Exception as exc:
            LOG.debug("Kong health check failed: %s", exc)
            return False


def _redact_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    redacted = dict(payload)
    for key in list(redacted):
        lowered = key.lower()
        if any(s in lowered for s in ("key", "secret", "token", "password", "auth")):
            redacted[key] = "***REDACTED***"
    return redacted


def _parse_model_suits(directory: Path) -> list[dict[str, Any]]:
    """Parse all YAML files in *directory* and return a list of model suit dicts.

    Supports two schemas:
    1. GLM-style: ``model_suit:`` top-level with ``name``, ``provider``, ``base_url``, ``api_key_env``
    2. KIMI/MiniMax-style: ``suit:`` top-level with ``id``, ``name``, ``provider`` plus nested ``model_config``
    """
    suits: list[dict[str, Any]] = []
    if not directory.exists():
        LOG.error("Model suits directory not found: %s", directory)
        return suits

    for path in sorted(directory.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            LOG.warning("Skipping %s: %s", path.name, exc)
            continue

        if not isinstance(raw, dict):
            continue

        # Schema 1: model_suit top-level (GLM family)
        if "model_suit" in raw and isinstance(raw["model_suit"], dict):
            ms = raw["model_suit"]
            suits.append(
                {
                    "name": ms.get("name", path.stem),
                    "provider": ms.get("provider", "unknown"),
                    "base_url": ms.get("base_url", ""),
                    "api_key_env": ms.get("api_key_env", ""),
                    "source_file": path.name,
                }
            )
            continue

        # Schema 2: suit top-level with nested model_config (KIMI, MiniMax)
        if "suit" in raw and isinstance(raw["suit"], dict):
            suit = raw["suit"]
            mc = raw.get("model_config") or {}
            base_url = mc.get("api_base", "")
            if not base_url:
                tzc = raw.get("tensorzero_config") or {}
                base_url = tzc.get("api_base", "")
            api_key_env = mc.get("api_key_env", "")
            if not api_key_env:
                tp = raw.get("token_plan") or {}
                api_key_env = tp.get("api_key_env", "")
            suits.append(
                {
                    "name": suit.get("name", path.stem),
                    "id": suit.get("id", path.stem),
                    "provider": suit.get("provider", "unknown"),
                    "base_url": base_url,
                    "api_key_env": api_key_env,
                    "source_file": path.name,
                }
            )
            continue

        LOG.debug("Unrecognised schema in %s -- skipping", path.name)

    LOG.info("Parsed %d model suits from %s", len(suits), directory)
    return suits


def _provider_to_service_name(provider: str) -> str:
    mapping = {
        "zai": "zai-glm",
        "moonshot_ai": "moonshot-kimi",
        "minimax": "minimax",
        "anthropic": "anthropic",
        "openrouter": "openrouter",
        "openai": "openai",
        "groq": "groq",
        "together": "together-ai",
        "huggingface": "huggingface",
        "ollama": "ollama-local",
    }
    return mapping.get(provider, f"provider-{provider}")


def _provider_to_host(provider: str, base_url: str) -> str:
    if base_url:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        if parsed.netloc:
            return parsed.netloc
    fallbacks = {
        "zai": "api.z.ai",
        "moonshot_ai": "api.moonshot.cn",
        "minimax": "api.minimax.chat",
        "anthropic": "api.anthropic.com",
        "openrouter": "openrouter.ai",
        "openai": "api.openai.com",
        "groq": "api.groq.com",
        "together": "api.together.xyz",
    }
    return fallbacks.get(provider, f"{provider}.localhost")


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace(".", "-").replace("_", "-")


def seed_routes(kong: KongAdminClient, suits: list[dict[str, Any]]) -> dict[str, Any]:
    services: dict[str, dict[str, Any]] = {}
    for suit in suits:
        provider = suit["provider"]
        svc_name = _provider_to_service_name(provider)
        if svc_name not in services:
            services[svc_name] = {
                "provider": provider,
                "host": _provider_to_host(provider, suit.get("base_url", "")),
                "base_url": suit.get("base_url", ""),
                "models": [],
            }
        services[svc_name]["models"].append(suit)

    created_services = 0
    created_routes = 0
    created_plugins = 0
    service_route_map: dict[str, list[str]] = {}

    for svc_name, info in services.items():
        upstream_url = f"http://{info['host']}"
        kong.upsert_service(
            name=svc_name,
            url=upstream_url,
            tags=["auto-seeded", f"provider:{info['provider']}"],
        )
        created_services += 1
        LOG.info("Service: %s -> %s", svc_name, upstream_url)

        upstream_name = f"{svc_name}-upstream"
        kong.upsert_upstream(
            name=upstream_name,
            healthchecks={
                "active": {
                    "type": "http",
                    "http_path": "/health",
                    "timeout": 5,
                    "interval": 15,
                    "healthy": {"http_statuses": [200, 401], "interval": 10},
                }
            },
        )
        kong.upsert_target(upstream_name, info["host"], weight=100)

        service_route_map[svc_name] = []
        for model in info["models"]:
            model_slug = _slugify(model.get("name") or model.get("id", "unknown"))
            route_name = f"route-{model_slug}"
            route_path = f"/v1/chat/completions/{model_slug}"

            kong.upsert_route(
                service_name=svc_name,
                name=route_name,
                paths=[route_path],
                tags=["auto-seeded", f"model:{model_slug}"],
            )
            created_routes += 1
            service_route_map[svc_name].append(route_name)
            LOG.info("  Route: %s -> %s", route_name, route_path)

        kong.upsert_plugin(
            plugin_name="key-auth",
            service_name=svc_name,
            config={
                "key_names": ["x-api-key"],
                "hide_credentials": True,
                "anonymous": None,
            },
        )
        created_plugins += 1
        LOG.info("  Plugin: key-auth on service %s", svc_name)

    return {
        "services_created": created_services,
        "routes_created": created_routes,
        "plugins_created": created_plugins,
        "service_route_map": service_route_map,
    }


def prune_stale_routes(
    kong: KongAdminClient, suits: list[dict[str, Any]], summary: dict[str, Any]
) -> int:
    current_models = {_slugify(s.get("name") or s.get("id", "")) for s in suits}
    all_routes = kong.list_all("routes")
    deleted = 0
    for route in all_routes:
        route_name = route.get("name", "")
        tags = route.get("tags") or []
        if "auto-seeded" not in tags:
            continue
        if route_name.startswith("route-"):
            model_slug = route_name[len("route-"):]
            if model_slug not in current_models:
                if kong.dry_run:
                    LOG.info("[DRY-RUN] Would prune stale route: %s", route_name)
                else:
                    LOG.info("Pruning stale route: %s", route_name)
                    kong.delete_route(route_name)
                deleted += 1
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kong-url", default=os.environ.get("KONG_ADMIN_URL", "http://localhost:8001"))
    ap.add_argument("--model-suits-dir", type=Path, default=MODEL_SUITS_DIR)
    ap.add_argument("--dry-run", action="store_true", help="Print what would be done without making changes")
    ap.add_argument("--prune", action="store_true", help="Remove routes for deleted model suits")
    ap.add_argument("--json-summary", action="store_true", help="Emit JSON summary to stdout")
    ap.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = ap.parse_args()

    _setup_logging(logging.DEBUG if args.debug else logging.INFO)

    kong = KongAdminClient(args.kong_url, dry_run=args.dry_run)
    if not kong.health():
        LOG.error("Kong Admin API at %s is not reachable. Is Kong running?", args.kong_url)
        return 1
    LOG.info("Kong Admin API: %s (healthy)", args.kong_url)

    suits = _parse_model_suits(args.model_suits_dir)
    if not suits:
        LOG.error("No model suits found in %s", args.model_suits_dir)
        return 1

    suits_with_missing_url = [s for s in suits if not s.get("base_url")]
    suits_with_missing_key_env = [s for s in suits if not s.get("api_key_env")]
    if suits_with_missing_url:
        LOG.warning(
            "%d model suit(s) missing base_url (will use fallback hosts): %s",
            len(suits_with_missing_url),
            ", ".join(s["source_file"] for s in suits_with_missing_url),
        )
    if suits_with_missing_key_env:
        LOG.warning(
            "%d model suit(s) missing api_key_env (provider credentials may not be set): %s",
            len(suits_with_missing_key_env),
            ", ".join(s["source_file"] for s in suits_with_missing_key_env),
        )

    summary = seed_routes(kong, suits)

    if args.prune:
        pruned = prune_stale_routes(kong, suits, summary)
        summary["routes_pruned"] = pruned
    else:
        summary["routes_pruned"] = 0

    providers = {}
    for s in suits:
        p = s["provider"]
        providers[p] = providers.get(p, 0) + 1
    summary["providers"] = providers
    summary["model_suits_parsed"] = len(suits)

    LOG.info(
        "Seeding complete: %d services, %d routes, %d plugins",
        summary["services_created"],
        summary["routes_created"],
        summary["plugins_created"],
    )
    if summary["routes_pruned"]:
        LOG.info("Pruned %d stale routes", summary["routes_pruned"])

    if args.json_summary:
        safe_summary = {k: v for k, v in summary.items() if k != "service_route_map"}
        safe_summary["service_route_map"] = summary.get("service_route_map", {})
        print(json.dumps(safe_summary, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
