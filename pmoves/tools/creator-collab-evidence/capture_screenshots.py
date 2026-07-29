"""Creator Collab Lane — visual evidence capture (Playwright).

Boots a local HTTP server on the evidence directory, opens each section
of the rendered dashboard in chromium, takes a full-page screenshot of
each, and writes the PNGs to ./screenshots/.

Screenshots:
  01-overview.png      — full page (1440x900 viewport)
  02-rooms.png         — #rooms section
  03-creator-studio.png — #rooms .room-card:first-of-type
  04-helpdesk.png      — #rooms .room-card:nth-of-type(2)
  05-pinokio-apps.png  — #pinokio-apps section
  06-tac-trees.png     — #tac section
  07-topics.png        — #topics section

Why chromium with a headless render:
- the dashboard uses CSS that requires a real browser engine
- we want a consistent 1440x900 viewport (operator's preferred review size)
- we want full-page screenshots so each section is captured at its
  natural height, not clipped to the viewport

Why local HTTP server (not file://):
- the dashboard's <details> + CSS Grid layout behave slightly
  differently under file:// in some browsers
- a local server is the closest analogue to a real "served" deploy

Usage (from the worktree root):
    C:/Users/russe/AppData/Local/Programs/Python/Python312/python.exe \\
        pmoves/tools/creator-collab-evidence/capture_screenshots.py \\
        --html pmoves/docs/evidence/creator-collab-2026-07-28/index.html \\
        --out pmoves/docs/evidence/creator-collab-2026-07-28/screenshots \\
        --port 8848
"""
from __future__ import annotations

import argparse
import http.server
import os
import socket
import socketserver
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright


VIEWPORT = {"width": 1440, "height": 900}


def _free_port(preferred: int) -> int:
    """Try the preferred port; if it's busy, return any free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


@contextmanager
def _serve(directory: Path, port: int):
    """Serve `directory` over HTTP on a background thread. Yields the URL."""
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=str(directory), **kwargs
    )
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--html", required=True, help="path to the HTML dashboard (must be index.html at the serve root)")
    p.add_argument("--out", required=True, help="output directory for the PNGs")
    p.add_argument("--port", type=int, default=8848, help="preferred port (defaults to 8848; falls back to any free port)")
    args = p.parse_args(argv)

    html_path = Path(args.html).resolve()
    if not html_path.exists():
        print(f"ERROR: HTML not found: {html_path}", file=sys.stderr)
        return 1
    serve_dir = html_path.parent
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    port = _free_port(args.port)
    print(f"[capture] serving {serve_dir} on http://127.0.0.1:{port}")
    with _serve(serve_dir, port) as base_url:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
            page = ctx.new_page()
            page.goto(base_url + "/", wait_until="networkidle")
            time.sleep(0.5)  # let any CSS animations settle

            targets = [
                ("01-overview.png", None),  # full page
                ("02-rooms.png", "#rooms"),
                ("03-creator-studio.png", "#rooms"),
                ("04-helpdesk.png", "#rooms"),
                ("05-pinokio-apps.png", "#pinokio-apps"),
                ("06-tac-trees.png", "#tac"),
                ("07-topics.png", "#topics"),
            ]
            for fname, selector in targets:
                path = out_dir / fname
                if selector is None:
                    page.screenshot(path=str(path), full_page=True)
                elif fname == "03-creator-studio.png":
                    el = page.locator("#rooms .room-card").first
                    el.scroll_into_view_if_needed()
                    el.screenshot(path=str(path))
                elif fname == "04-helpdesk.png":
                    el = page.locator("#rooms .room-card").nth(1)
                    el.scroll_into_view_if_needed()
                    el.screenshot(path=str(path))
                else:
                    el = page.locator(selector)
                    el.scroll_into_view_if_needed()
                    el.screenshot(path=str(path))
                print(f"[capture] wrote {path}")
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
