#!/usr/bin/env python3
"""Topology-aware smoke checks for PMOVES branded UI surfaces."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Probe:
    name: str
    url: str
    expected: tuple[int, ...]


def _base_url(env_name: str, default: str) -> str:
    value = os.getenv(env_name, default).strip()
    return value.rstrip("/")


def _join(base: str, path: str) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def _status(url: str, timeout: float) -> tuple[int, str | None]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.getcode()), None
    except urllib.error.HTTPError as exc:
        return int(exc.code), None
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)
    except TimeoutError:
        return 0, "timeout"


def _core_probes() -> list[Probe]:
    pmoves_ui = _base_url("PMOVES_UI_BASE_URL", "http://localhost:4482")
    agent_zero_ui = _base_url("AGENT_ZERO_UI_URL", "http://localhost:8081")
    archon_ui = _base_url("ARCHON_UI_URL", "http://localhost:3737")
    open_notebook_ui = _base_url("OPEN_NOTEBOOK_UI_URL", "http://localhost:8503")

    return [
        Probe("pmoves-ui-health", _join(pmoves_ui, "/api/health"), (200,)),
        Probe("pmoves-ui-home", pmoves_ui, (200, 301, 302, 307, 308)),
        Probe("agent-zero-ui", agent_zero_ui, (200, 301, 302, 307, 308)),
        Probe("archon-ui", archon_ui, (200, 301, 302, 307, 308)),
        Probe("open-notebook-ui", open_notebook_ui, (200, 301, 302, 307, 308)),
        Probe(
            "pmoves-ui-service-open-notebook",
            _join(pmoves_ui, "/dashboard/services/open-notebook"),
            (200, 301, 302, 307, 308),
        ),
        Probe(
            "pmoves-ui-service-jellyfin",
            _join(pmoves_ui, "/dashboard/services/jellyfin"),
            (200, 301, 302, 307, 308),
        ),
        Probe(
            "pmoves-ui-service-firefly",
            _join(pmoves_ui, "/dashboard/services/firefly"),
            (200, 301, 302, 307, 308),
        ),
        Probe(
            "pmoves-ui-service-wger",
            _join(pmoves_ui, "/dashboard/services/wger"),
            (200, 301, 302, 307, 308),
        ),
    ]


def _external_probes() -> list[Probe]:
    firefly_ui = _base_url("FIREFLY_UI_URL", f"http://localhost:{os.getenv('FIREFLY_PORT', '8082')}")
    wger_ui = _base_url("WGER_UI_URL", f"http://localhost:{os.getenv('WGER_HOST_PORT', '8000')}")
    jellyfin_ui = _base_url("JELLYFIN_UI_URL", "http://localhost:8096")
    jellyfin_ai_dashboard = _base_url("JELLYFIN_AI_DASHBOARD_URL", f"http://localhost:{os.getenv('JELLYFIN_DASHBOARD_PORT', '8400')}")
    jellyfin_ai_api = _base_url("JELLYFIN_AI_API_URL", f"http://localhost:{os.getenv('JELLYFIN_API_PORT', '8300')}")
    open_notebook_api = _base_url("OPEN_NOTEBOOK_API_URL", f"http://localhost:{os.getenv('OPEN_NOTEBOOK_API_PORT', '5055')}")

    return [
        Probe("firefly-ui", firefly_ui, (200, 301, 302, 303, 307, 308)),
        Probe("wger-ui", wger_ui, (200, 301, 302, 303, 307, 308)),
        Probe("jellyfin-ui", _join(jellyfin_ui, "/web/index.html"), (200, 301, 302, 307, 308)),
        Probe("jellyfin-ai-dashboard", jellyfin_ai_dashboard, (200, 301, 302, 307, 308)),
        Probe("jellyfin-ai-api", jellyfin_ai_api, (200, 301, 302, 307, 308, 404)),
        Probe("open-notebook-api", open_notebook_api, (200, 401, 403, 404)),
    ]


def _select_probes(profile: str) -> list[Probe]:
    if profile == "core":
        return _core_probes()
    if profile == "external":
        return _external_probes()
    probes = _core_probes() + _external_probes()
    # Preserve order while deduplicating by probe name.
    deduped: list[Probe] = []
    seen: set[str] = set()
    for probe in probes:
        if probe.name in seen:
            continue
        deduped.append(probe)
        seen.add(probe.name)
    return deduped


def _format_codes(codes: Iterable[int]) -> str:
    return ",".join(str(code) for code in codes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("core", "external", "all"), default=os.getenv("UI_TOPOLOGY_PROFILE", "core"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("UI_TOPOLOGY_TIMEOUT", "8")))
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        default=os.getenv("UI_TOPOLOGY_ALLOW_MISSING", "").lower() in {"1", "true", "yes"},
        help="Do not fail when an endpoint is unreachable (connection/timeout).",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    args = parser.parse_args()

    failures: list[dict[str, object]] = []
    results: list[dict[str, object]] = []

    for probe in _select_probes(args.profile):
        code, error = _status(probe.url, args.timeout)
        ok = code in probe.expected
        if code == 0 and args.allow_missing:
            ok = True
        entry = {
            "name": probe.name,
            "url": probe.url,
            "status": code,
            "expected": list(probe.expected),
            "ok": ok,
            "error": error,
        }
        results.append(entry)
        if not ok:
            failures.append(entry)

    if args.json:
        payload = {
            "profile": args.profile,
            "allow_missing": args.allow_missing,
            "total": len(results),
            "failed": len(failures),
            "results": results,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"UI topology smoke profile={args.profile} allow_missing={args.allow_missing}")
        for entry in results:
            status_label = "OK" if entry["ok"] else "FAIL"
            line = f"{status_label:4} {entry['name']}: {entry['status']} -> {entry['url']} (expected { _format_codes(entry['expected']) })"
            if entry["error"]:
                line += f" [{entry['error']}]"
            print(line)
        print(f"Summary: {len(results) - len(failures)}/{len(results)} checks passed")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
