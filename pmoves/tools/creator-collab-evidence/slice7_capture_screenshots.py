"""slice7_capture_screenshots.py - Visual evidence for slice 7.

Captures Playwright screenshots of the live pmoves-ui + nats_event_bus
dashboards immediately after the Fordham E2E has run. The aim is to show:

  01-pmoves-ui-rooms.png         pmoves-ui /api/rooms - all 12 rooms listed
  02-nats-event-bus-topics.png   nats_event_bus /healthz - 8 topics wired
  03-room-presence-events.png    nats_event_bus /v1/events/room.presence.v1
  04-helpdesk-events.png         nats_event_bus /v1/events/helpdesk.* (joined)
  05-nats-dashboard.html         rendered nats_event_bus index (HTML)

This is the P2 (visual evidence) commit of the slice 7 stack.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


VIEWPORT = {"width": 1440, "height": 900}
PMOVES_UI_BASE = "http://127.0.0.1:4482"
NATS_EVENT_BUS_BASE = "http://127.0.0.1:8131"


HTML_DASHBOARD = """<!doctype html>
<html><head><meta charset="utf-8">
<title>Slice 7 — nats_event_bus live state</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #0b1220; color: #d4d4d4; margin: 0; padding: 24px; }}
  h1, h2 {{ color: #7dd3fc; font-weight: 600; }}
  h1 {{ font-size: 22px; margin: 0 0 8px; }}
  h2 {{ font-size: 16px; margin: 24px 0 8px; }}
  .kv {{ display: grid; grid-template-columns: 200px 1fr; gap: 4px 16px; font-size: 13px; }}
  .kv div:nth-child(odd) {{ color: #94a3b8; }}
  pre {{ background: #111827; border: 1px solid #1f2937; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; line-height: 1.4; color: #e5e7eb; }}
  .topic {{ display: inline-block; margin: 2px 4px 2px 0; padding: 2px 8px; background: #1e293b; border: 1px solid #334155; border-radius: 12px; font-size: 11px; }}
  .ok {{ color: #34d399; }}
  .pill {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
  .pill-ok {{ background: #064e3b; color: #6ee7b7; }}
  .pill-fail {{ background: #7f1d1d; color: #fecaca; }}
</style></head><body>
<h1>nats_event_bus — live state (slice 7 evidence)</h1>
<div class="kv">
  <div>URL</div><div><code>{bus_url}</code></div>
  <div>Status</div><div><span class="pill {status_class}">{status}</span> {ok_marker}</div>
  <div>NATS connected</div><div>{nats_connected}</div>
  <div>Writes enabled</div><div>{writes_enabled}</div>
  <div>Topics ({topic_count})</div><div>{topics_html}</div>
</div>
<h2>room.presence.v1 events (latest 3)</h2>
<pre>{presence_html}</pre>
<h2>helpdesk.intake.opened.v1 events (latest 3)</h2>
<pre>{intake_opened_html}</pre>
<h2>helpdesk.intake.routed.v1 events (latest 3)</h2>
<pre>{intake_routed_html}</pre>
<h2>helpdesk.room.suggested.v1 events (latest 3)</h2>
<pre>{room_suggested_html}</pre>
</body></html>
"""


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _format_event_html(events: list[dict]) -> str:
    if not events:
        return "(no events captured)"
    out = []
    for e in events[-3:]:
        env = e if isinstance(e, dict) else {"raw": str(e)}
        ts = env.get("ts") or env.get("observed_at") or env.get("opened_at") or env.get("routed_at") or env.get("suggested_at") or "?"
        out.append(f"--- {ts} ---\n{json.dumps(env, indent=2)}")
    return "\n\n".join(out)


def capture(evidence_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    import httpx

    # 0. Pull bus state for the dashboard
    bus_state = httpx.get(f"{NATS_EVENT_BUS_BASE}/healthz", timeout=5).json()
    topics = bus_state.get("topics", [])
    bus_state["topic_count"] = len(topics)
    bus_state["topics_html"] = " ".join(
        f'<span class="topic">{_esc(t)}</span>' for t in topics
    )
    bus_state["status"] = bus_state.get("status", "unknown")
    bus_state["status_class"] = "pill-ok" if bus_state["status"] == "ok" else "pill-fail"
    bus_state["ok_marker"] = "OK" if bus_state["status"] == "ok" else "FAIL"
    bus_state["nats_connected"] = "yes" if bus_state.get("nats_connected") else "no"
    bus_state["writes_enabled"] = "yes" if bus_state.get("writes_enabled") else "no"
    bus_state["bus_url"] = NATS_EVENT_BUS_BASE

    # 1. Pull latest events for each subject
    subject_to_key = {
        "room.presence.v1": "presence_html",
        "helpdesk.intake.opened.v1": "intake_opened_html",
        "helpdesk.intake.routed.v1": "intake_routed_html",
        "helpdesk.room.suggested.v1": "room_suggested_html",
    }
    for subject, key in subject_to_key.items():
        r = httpx.get(
            f"{NATS_EVENT_BUS_BASE}/v1/events/{subject}?limit=3", timeout=5
        )
        if r.status_code == 200:
            d = r.json()
            bus_state[key] = _format_event_html(d.get("events", []))
        else:
            bus_state[key] = f"(error {r.status_code}: {r.text[:200]})"

    # Render the dashboard HTML
    dashboard_html = HTML_DASHBOARD.format(**bus_state)
    (out_dir / "05-nats-dashboard.html").write_text(
        dashboard_html, encoding="utf-8"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT)
        page = ctx.new_page()

        # 01: pmoves-ui rooms
        page.goto(f"{PMOVES_UI_BASE}/api/rooms", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        page.screenshot(path=str(out_dir / "01-pmoves-ui-rooms.png"), full_page=True)

        # 02: nats_event_bus /healthz (raw JSON, rendered by browser)
        page.goto(f"{NATS_EVENT_BUS_BASE}/healthz", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        page.screenshot(path=str(out_dir / "02-nats-event-bus-topics.png"), full_page=True)

        # 03-05: rendered dashboard from the HTML we just wrote
        page.goto(f"file://{out_dir / '05-nats-dashboard.html'.replace(chr(92), '/')}", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        page.screenshot(path=str(out_dir / "03-nats-dashboard-full.png"), full_page=True)

        # 04: pmoves-ui home (if reachable) -- shows the central dashboard
        try:
            page.goto(f"{PMOVES_UI_BASE}/", wait_until="domcontentloaded", timeout=5000)
            page.wait_for_timeout(500)
            page.screenshot(path=str(out_dir / "04-pmoves-ui-home.png"), full_page=True)
        except Exception as e:  # noqa: BLE001
            print(f"  (pmoves-ui / not reachable: {e})")

        browser.close()

    print(f"  -> wrote {out_dir / '01-pmoves-ui-rooms.png'}")
    print(f"  -> wrote {out_dir / '02-nats-event-bus-topics.png'}")
    print(f"  -> wrote {out_dir / '03-nats-dashboard-full.png'}")
    print(f"  -> wrote {out_dir / '05-nats-dashboard.html'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "slice7",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Screenshot output dir (default: evidence-dir/screenshots)",
    )
    args = parser.parse_args()
    out = args.out_dir or args.evidence_dir / "screenshots"
    capture(args.evidence_dir, out)
    print(f"\nScreenshots saved to {out}")
