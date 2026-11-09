"""Capture screenshots of the LIVE pmoves-ui on :4482 (real runtime)."""
from __future__ import annotations
import sys
import time
from playwright.sync_api import sync_playwright

URL = "http://localhost:4482"
OUT = r"C:\Users\russe\Documents\GitHub\PMOVES.AI\.worktrees\feat-creator-collab-lane\pmoves\docs\evidence\creator-collab-2026-07-28\screenshots-live"

def main():
    import os; os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width":1440,"height":900})
        page = ctx.new_page()
        targets = [
            ("01-home.png", "/"),
            ("02-dashboard-services.png", "/dashboard/services"),
            ("03-dashboard-rooms.png", "/dashboard/rooms"),
            ("04-room-fordham.png", "/dashboard/fordham"),
            ("05-api-rooms.png", "/api/rooms"),
        ]
        for fname, path in targets:
            try:
                page.goto(URL + path, wait_until="domcontentloaded", timeout=15000)
                time.sleep(1.5)
                full = "home" in fname
                page.screenshot(path=f"{OUT}/{fname}", full_page=full)
                print(f"OK {fname} <- {path} (full_page={full})")
            except Exception as e:
                print(f"ERR {fname} <- {path}: {e}")
        b.close()

if __name__ == "__main__":
    sys.exit(main() or 0)
