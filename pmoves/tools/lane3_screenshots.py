#!/usr/bin/env python3
"""Playwright screenshot capture for lane 3 supabase-stack-default-up."""
import asyncio
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
evidence_dir = repo / "tools" / "lane3-evidence"
evidence_dir.mkdir(parents=True, exist_ok=True)

async def main():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("playwright not installed; skipping screenshots", file=sys.stderr)
        return 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await ctx.new_page()

            # 1. pmoves-ui health endpoint (JSON rendering in browser)
            print("Capturing pmoves-ui /api/health...")
            await page.goto("http://localhost:4482/api/health", wait_until="domcontentloaded", timeout=15000)
            await page.screenshot(path=str(evidence_dir / "01_pmoves_ui_health.png"), full_page=True)

            # 2. Kong admin services page
            print("Capturing kong admin services...")
            await page.goto("http://localhost:8001/services", wait_until="domcontentloaded", timeout=15000)
            await page.screenshot(path=str(evidence_dir / "02_kong_services.png"), full_page=True)

            # 3. Kong admin routes page
            print("Capturing kong admin routes...")
            await page.goto("http://localhost:8001/routes", wait_until="domcontentloaded", timeout=15000)
            await page.screenshot(path=str(evidence_dir / "03_kong_routes.png"), full_page=True)

            # 4. Supabase Studio (the dashboard)
            print("Capturing supabase studio...")
            await page.goto("http://localhost:3000", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path=str(evidence_dir / "04_supabase_studio.png"), full_page=True)

            # 5. pmoves-ui main page
            print("Capturing pmoves-ui main page...")
            await page.goto("http://localhost:4482", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            await page.screenshot(path=str(evidence_dir / "05_pmoves_ui_main.png"), full_page=True)

            await ctx.close()
        finally:
            await browser.close()

    print(f"Screenshots written to {evidence_dir}")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
