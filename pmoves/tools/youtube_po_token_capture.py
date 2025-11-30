#!/usr/bin/env python3
"""
PMOVES • YouTube PO-token / request capture helper

This script automates the “userscript for Invidious” workflow described at
https://docs.invidious.io/applications/#userscripts-for-invidious by running a
headless Chromium session, loading your YouTube cookies, navigating to a target
video, and recording the critical request/response payloads that modern SABR
streams require (PO token, signature headers, visitor data, etc.).

Output is a JSON blob you can feed into pmoves-yt (or any yt-dlp wrapper) to
replay the same authenticated request without having to keep a browser open.

Usage
-----
    python pmoves/tools/youtube_po_token_capture.py \\
        --cookies path/to/www.youtube.com_cookies.txt \\
        --video-id 3V3_Y_FuMYk \\
        --output pmoves/config/cookies/youtube_po_token.json

Prerequisites
-------------
    pip install playwright
    playwright install chromium

Cookie file must be in the standard “Netscape” format (the export that yt-dlp
produces with `--cookies`), as documented at
https://github.com/yt-dlp/yt-dlp/wiki/Extractors#cookies. You can reuse the same
file you point pmoves-yt at via YT_COOKIES.

What it captures
----------------
* The outbound POST body for youtubei/v1/player
* The request headers (including Authorization, X-Goog-Visitor-Id, etc.)
* Any `poToken` values found in the response payload

The JSON schema looks like:
{
  "video_id": "...",
  "request": {
    "url": "...youtubei/v1/player...",
    "headers": { ... },
    "body": { ... }          # parsed JSON
  },
  "response": {
    "status": 200,
    "headers": { ... },
    "body": { ... }          # parsed JSON if decodable
  },
  "po_tokens": ["...","..."],
  "captured_at": "2025-10-24T00:52:03.123456Z"
}

You can feed the `request.headers` / `request.body` into a custom downloader, or
extract the first entry from `po_tokens` and drop it straight into
`YT_PO_TOKEN_VALUE` for pmoves-yt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, Request, Response


@dataclass
class CaptureResult:
    request_url: str
    request_headers: Dict[str, str]
    request_body: Optional[dict]
    response_status: int
    response_headers: Dict[str, str]
    response_body: Optional[dict]
    po_tokens: List[str]


def parse_netscape_cookies(path: Path) -> List[dict]:
    """Parse a Netscape cookie file (the format used by yt-dlp --cookies)."""
    cookies: List[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 7:
                continue
            domain, flag, path, secure, expiry, name, value = parts
            cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": domain.lstrip("."),
                    "path": path,
                    "httpOnly": False,
                    "secure": secure.lower() == "true",
                    "expires": int(expiry) if expiry.isdigit() else None,
                }
            )
    return cookies


async def capture(video_id: str, cookies: List[dict], headless: bool) -> CaptureResult:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()
        player_request_data = {}

        async def _handle_request(request: Request) -> None:
            if "youtubei/v1/player" in request.url:
                player_request_data["url"] = request.url
                player_request_data["headers"] = dict(request.headers)
                try:
                    player_request_data["body"] = request.post_data_json
                except Exception:
                    body = request.post_data
                    player_request_data["body"] = body if body else None

        async def _handle_response(response: Response) -> None:
            if "youtubei/v1/player" in response.url and "response" not in player_request_data:
                player_request_data["response"] = {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": None,
                }
                try:
                    player_request_data["response"]["body"] = await response.json()
                except Exception:
                    try:
                        text = await response.text()
                        player_request_data["response"]["body"] = text
                    except Exception:
                        pass

        page.on("request", _handle_request)
        page.on("response", _handle_response)

        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        await page.goto(watch_url)
        await page.wait_for_timeout(15_000)  # give the player time to initialise

        await browser.close()

    if not player_request_data:
        raise RuntimeError("Failed to capture youtubei/v1/player traffic. Check cookies/login.")

    request_body = player_request_data.get("body")
    response_body = player_request_data.get("response", {}).get("body")

    po_tokens: List[str] = []
    if isinstance(response_body, dict):
        streaming = response_body.get("streamingData") or {}
        for fmt in streaming.get("adaptiveFormats", []):
            if "poToken" in fmt:
                po_tokens.append(fmt["poToken"])
        if "poToken" in streaming:
            po_tokens.append(streaming["poToken"])

    if isinstance(request_body, dict):
        if "signatureTimestamp" in request_body:
            # not a poToken, but useful debug info – we keep capture intact
            pass

    return CaptureResult(
        request_url=player_request_data["url"],
        request_headers=player_request_data.get("headers", {}),
        request_body=request_body if isinstance(request_body, dict) else None,
        response_status=player_request_data["response"]["status"],
        response_headers=player_request_data["response"]["headers"],
        response_body=response_body if isinstance(response_body, dict) else None,
        po_tokens=po_tokens,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture YouTube PO token / player request")
    parser.add_argument("--cookies", type=Path, required=True, help="Path to Netscape-format cookies.txt")
    parser.add_argument("--video-id", required=True, help="YouTube video ID to load")
    parser.add_argument("--output", type=Path, required=True, help="Path to write capture JSON")
    parser.add_argument("--headful", action="store_true", help="Disable headless mode for debugging")
    args = parser.parse_args()

    if not args.cookies.exists():
        print(f"[error] Cookie file not found: {args.cookies}", file=sys.stderr)
        sys.exit(1)

    cookies = parse_netscape_cookies(args.cookies)
    if not cookies:
        print("[warn] No cookies parsed; YouTube may return consent / login prompts.", file=sys.stderr)

    try:
        result = asyncio.run(capture(args.video_id, cookies, headless=not args.headful))
    except Exception as exc:  # pragma: no cover
        print(f"[error] Capture failed: {exc}", file=sys.stderr)
        sys.exit(2)

    payload = {
        "video_id": args.video_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "request": {
            "url": result.request_url,
            "headers": result.request_headers,
            "body": result.request_body,
        },
        "response": {
            "status": result.response_status,
            "headers": result.response_headers,
            "body": result.response_body,
        },
        "po_tokens": result.po_tokens,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[ok] Capture stored at {args.output}")
    if result.po_tokens:
        print(f"[info] Discovered {len(result.po_tokens)} po_token(s); first={result.po_tokens[0]}")
    else:
        print("[warn] No po_token found in response. Check the captured payload manually.")


if __name__ == "__main__":
    main()

