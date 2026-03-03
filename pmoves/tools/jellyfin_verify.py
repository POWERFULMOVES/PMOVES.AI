#!/usr/bin/env python3
"""
Verify Jellyfin bridge + overlay readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _request_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 5.0):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8") if resp.length != 0 else ""
        payload = json.loads(raw) if raw else {}
        return int(resp.status), payload


def _request_status(url: str, timeout: float = 5.0) -> int:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return int(resp.status)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Jellyfin bridge/overlay readiness.")
    parser.add_argument("--bridge-url", default="http://localhost:8093", help="Jellyfin bridge base URL")
    parser.add_argument(
        "--jellyfin-url",
        default=os.environ.get("JELLYFIN_VERIFY_URL", "http://localhost:8096"),
        help="Primary Jellyfin server URL",
    )
    parser.add_argument(
        "--jellyfin-fallback-url",
        default=os.environ.get("JELLYFIN_VERIFY_FALLBACK_URL", "http://localhost:9096"),
        help="Fallback Jellyfin server URL used when primary probe fails",
    )
    parser.add_argument("--api-url", default="http://localhost:8300/health", help="Jellyfin API gateway health URL")
    parser.add_argument("--dashboard-url", default="http://localhost:8400", help="Jellyfin dashboard URL")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout seconds")
    args = parser.parse_args()

    failures: list[str] = []

    checks = [
        ("bridge-health", f"{args.bridge_url}/healthz"),
        ("jellyfin-server", args.jellyfin_url),
        ("jellyfin-api", args.api_url),
        ("jellyfin-dashboard", args.dashboard_url),
    ]

    jellyfin_server_ok = False
    for name, url in checks:
        try:
            code = _request_status(url, timeout=args.timeout)
            if code == 200:
                print(f"[PASS] {name}: {url} -> {code}")
                if name == "jellyfin-server":
                    jellyfin_server_ok = True
            else:
                print(f"[FAIL] {name}: {url} -> HTTP {code}")
                failures.append(name)
        except urllib.error.HTTPError as exc:
            print(f"[FAIL] {name}: {url} -> HTTP {exc.code}")
            failures.append(name)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {name}: {url} unreachable ({exc})")
            failures.append(name)

    if not jellyfin_server_ok and args.jellyfin_fallback_url and args.jellyfin_fallback_url != args.jellyfin_url:
        try:
            code = _request_status(args.jellyfin_fallback_url, timeout=args.timeout)
            if code == 200:
                print(f"[PASS] jellyfin-server-fallback: {args.jellyfin_fallback_url} -> {code}")
            else:
                print(f"[FAIL] jellyfin-server-fallback: {args.jellyfin_fallback_url} -> HTTP {code}")
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] jellyfin-server-fallback: {args.jellyfin_fallback_url} unreachable ({exc})")

    refresh_url = f"{args.bridge_url}/jellyfin/refresh"
    try:
        code, payload = _request_json(refresh_url, method="POST", body={}, timeout=args.timeout)
        if code == 200 and payload.get("ok") is True:
            print(f"[PASS] bridge-refresh: {refresh_url} -> ok=true")
        else:
            print(f"[FAIL] bridge-refresh: {refresh_url} -> HTTP {code}, payload={payload}")
            failures.append("bridge-refresh")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            detail = str(exc)
        print(f"[FAIL] bridge-refresh: {refresh_url} -> HTTP {exc.code}, detail={detail}")
        failures.append("bridge-refresh")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] bridge-refresh: {refresh_url} unreachable ({exc})")
        failures.append("bridge-refresh")

    if failures:
        print(f"\nSummary: FAIL ({len(failures)} checks)")
        return 1

    print("\nSummary: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
