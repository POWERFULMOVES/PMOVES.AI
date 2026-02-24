#!/usr/bin/env python3
"""
Lightweight PMOVES.YT -> Jellyfin smoke.

Default mode:
- checks pmoves-yt healthz
- checks jellyfin-bridge healthz
- calls /yt/info for a sample URL to validate extractor path

Optional full mode:
- also triggers /jellyfin/refresh
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _request_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 8.0):
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PMOVES.YT + Jellyfin smoke.")
    parser.add_argument("--yt-url", default="http://localhost:8077", help="PMOVES.YT base URL")
    parser.add_argument("--bridge-url", default="http://localhost:8093", help="Jellyfin bridge base URL")
    parser.add_argument(
        "--video-url",
        default="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        help="Sample video URL used for /yt/info",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds")
    parser.add_argument("--full", action="store_true", help="Also trigger bridge refresh call.")
    args = parser.parse_args()

    failures: list[str] = []

    for name, url in [
        ("pmoves-yt-health", f"{args.yt_url}/healthz"),
        ("jellyfin-bridge-health", f"{args.bridge_url}/healthz"),
    ]:
        try:
            code, payload = _request_json(url, timeout=args.timeout)
            if code == 200 and (payload.get("ok", True) is True):
                print(f"[PASS] {name}: {url} -> {code}")
            else:
                print(f"[FAIL] {name}: {url} -> HTTP {code}, payload={payload}")
                failures.append(name)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {name}: {url} unreachable ({exc})")
            failures.append(name)

    info_url = f"{args.yt_url}/yt/info"
    try:
        code, payload = _request_json(
            info_url,
            method="POST",
            body={"url": args.video_url},
            timeout=args.timeout,
        )
        info = payload.get("info") if isinstance(payload.get("info"), dict) else payload
        title = info.get("title") if isinstance(info, dict) else None
        video_id = info.get("id") if isinstance(info, dict) else None
        if code == 200 and payload.get("ok", True) is True and title and video_id:
            print(f"[PASS] yt-info: id={video_id} title={title}")
        else:
            print(f"[FAIL] yt-info: HTTP {code}, payload={payload}")
            failures.append("yt-info")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"[FAIL] yt-info: HTTP {exc.code}, detail={detail}")
        failures.append("yt-info")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] yt-info: request failed ({exc})")
        failures.append("yt-info")

    if args.full:
        refresh_url = f"{args.bridge_url}/jellyfin/refresh"
        try:
            code, payload = _request_json(refresh_url, method="POST", body={}, timeout=args.timeout)
            if code == 200 and payload.get("ok") is True:
                print(f"[PASS] bridge-refresh: {refresh_url}")
            else:
                print(f"[FAIL] bridge-refresh: HTTP {code}, payload={payload}")
                failures.append("bridge-refresh")
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] bridge-refresh: request failed ({exc})")
            failures.append("bridge-refresh")

    if failures:
        print(f"\nSummary: FAIL ({len(failures)} checks)")
        return 1

    print("\nSummary: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

