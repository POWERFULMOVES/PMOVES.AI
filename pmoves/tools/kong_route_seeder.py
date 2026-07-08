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
import re
import socket
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

    Avoids mutating the underlying LogRecord (which would affect all
    handlers globally).  Instead, redaction happens in ``process()`` so
    the redacted string is what ultimately reaches the formatter.
    """

    _SENSITIVE_RE = re.compile(
        r"((?:api[_-]?key|apikey|secret|token|password|auth)[^=]*)=\S+",
        re.IGNORECASE,
    )

    def process(self, msg, kwargs):
        msg = self._SENSITIVE_RE.sub(r"\1=***REDACTED***", str(msg))
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


def _setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(fmt)
    log.setLevel(level)
    log.addHandler(handler)


def get_redacting_logger() -> _RedactingLoggerAdapter:
    """Return a LoggerAdapter that redacts secrets at format time."""
    return _RedactingLoggerAdapter(log, {})


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
            log.info("[DRY-RUN] %s %s  body=%s", method, url, _redact_payload(payload))
            return None
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                log.debug("Exists (409): %s %s", method, url)
                return None
            if exc.code == 404 and method == "DELETE":
                log.debug("Not found for delete (404): %s", url)
                return None
            error_body = exc.read().decode("utf-8") if exc.fp else ""
            log.error("Kong API error: %s %s -> %s: %s", method, url, exc.code, error_body)
            raise

    def list_all(self, resource: str) -> list[dict[str, Any]]:
        """Paginated GET /{resource}."""
        from urllib.parse import urljoin

        results: list[dict[str, Any]] = []
        next_url = f"/{resource}"
        while next_url:
            url = urljoin(self.base, next_url)
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    results.extend(data.get("data", []))
                    next_url = data.get("next")
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8") if exc.fp else ""
                log.error(
                    "Failed to list %s: HTTP %s - %s", resource, exc.code, error_body
                )
                if exc.code >= 500:
                    raise  # Server errors are critical
                break  # Client errors (404, etc.) are expected
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
        """Idempotently create or update a plugin using PUT.

        Uses a deterministic plugin ID so repeated calls are true upserts.
        """
        plugin_id = f"{plugin_name}-{service_name or route_name or 'global'}"
        payload: dict[str, Any] = {"name": plugin_name}
        if service_name:
            payload["service"] = {"name": service_name}
        if route_name:
            payload["route"] = {"name": route_name}
        if config:
            payload["config"] = config
        return self._request("PUT", f"/plugins/{plugin_id}", payload)

    def delete_service_cascade(self, name: str) -> None:
        """Delete a service and all associated routes and plugins.

        Pre-filters routes and plugins by service name to avoid redundant
        iteration.  Complexity is O(R + P) per call where R is total routes
        and P is total plugins; call in batch when deleting many services.
        """
        all_routes = self.list_all("routes")
        matching_routes = [
            r for r in all_routes if r.get("service", {}).get("name") == name
        ]
        for route in matching_routes:
            self._request("DELETE", f"/routes/{route['name']}")

        all_plugins = self.list_all("plugins")
        matching_plugins = [
            p for p in all_plugins if p.get("service", {}).get("name") == name
        ]
        for plugin in matching_plugins:
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
        except (urllib.error.URLError, socket.timeout) as exc:
            log.debug("Kong health check failed: %s", exc)
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
        log.error("Model suits directory not found: %s", directory)
        return suits

    for path in sorted(directory.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Skipping %s: %s", path.name, exc)
            continue

        if not isinstance(doc, dict):
            continue

        # Schema 1: model_suit top-level (GLM family)
        if "model_suit" in doc and isinstance(doc["model_suit"], dict):
            ms = doc["model_suit"]
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
        if "suit" in doc and isinstance(doc["suit"], dict):
            suit = doc["suit"]
            mc = doc.get("model_config") or {}
            base_url = mc.get("api_base", "")
            if not base_url:
                tzc = doc.get("tensorzero_config") or {}
                base_url = tzc.get("api_base", "")
            api_key_env = mc.get("api_key_env", "")
            if not api_key_env:
                tp = doc.get("token_plan") or {}
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

        log.debug("Unrecognised schema in %s -- skipping", path.name)

    log.info("Parsed %d model suits from %s", len(suits), directory)
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
    """Convert a name to a URL-safe slug, handling a broad range of special characters."""
    slug = name.lower()
    for char in (
        " ", ".", "_", ":", "/", "\\", "@", "#", "%", "&", "?",
        "*", "+", "=", "<", ">", "{", "}", "[", "]", "|", "^",
        "~", "$", "`", '"', "'",
    ):
        slug = slug.replace(char, "-")
    # Collapse multiple consecutive hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    return slug


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
        log.info("Service: %s -> %s", svc_name, upstream_url)

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
            log.info("  Route: %s -> %s", route_name, route_path)

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
        log.info("  Plugin: key-auth on service %s", svc_name)

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
                    log.info("[DRY-RUN] Would prune stale route: %s", route_name)
                else:
                    log.info("Pruning stale route: %s", route_name)
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
        log.error("Kong Admin API at %s is not reachable. Is Kong running?", args.kong_url)
        return 1
    log.info("Kong Admin API: %s (healthy)", args.kong_url)

    suits = _parse_model_suits(args.model_suits_dir)
    if not suits:
        log.error("No model suits found in %s", args.model_suits_dir)
        return 1

    suits_with_missing_url = [s for s in suits if not s.get("base_url")]
    suits_with_missing_key_env = [s for s in suits if not s.get("api_key_env")]
    if suits_with_missing_url:
        log.warning(
            "%d model suit(s) missing base_url (will use fallback hosts): %s",
            len(suits_with_missing_url),
            ", ".join(s["source_file"] for s in suits_with_missing_url),
        )
    if suits_with_missing_key_env:
        log.warning(
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

    log.info(
        "Seeding complete: %d services, %d routes, %d plugins",
        summary["services_created"],
        summary["routes_created"],
        summary["plugins_created"],
    )
    if summary["routes_pruned"]:
        log.info("Pruned %d stale routes", summary["routes_pruned"])

    if args.json_summary:
        safe_summary = {k: v for k, v in summary.items() if k != "service_route_map"}
        safe_summary["service_route_map"] = summary.get("service_route_map", {})
        print(json.dumps(safe_summary, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
