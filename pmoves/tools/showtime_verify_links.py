#!/usr/bin/env python3
"""Generate clickable Showtime verification pages for UI/API endpoints."""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON = REPO_ROOT / "pmoves" / "docs" / "evidence" / "showtime_links.json"
DEFAULT_MD = REPO_ROOT / "pmoves" / "docs" / "SHOWTIME_VERIFY_LINKS.md"
DEFAULT_HTML = REPO_ROOT / "pmoves" / "docs" / "SHOWTIME_VERIFY_LINKS.html"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flight_check_retro import ENDPOINTS  # type: ignore


DEFAULT_REQUIRED = {
    "Supabase REST",
    "Archon API",
    "Agent Zero API",
    "Grafana",
    "Console UI",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--output-html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--timeout", type=float, default=2.5)
    parser.add_argument("--open", action="store_true", help="Open generated HTML in default browser.")
    return parser.parse_args()


def check(url: str, timeout: float) -> tuple[str, int, str]:
    try:
        with urlopen(url, timeout=timeout) as resp:
            code = int(getattr(resp, "status", 200))
        status = "ok" if 200 <= code < 400 else "warn"
        return status, code, ""
    except HTTPError as exc:
        status = "warn" if 400 <= exc.code < 500 else "error"
        return status, int(exc.code), str(exc)
    except (TimeoutError, URLError) as exc:
        return "error", 0, str(exc)
    except Exception as exc:
        return "error", 0, str(exc)


def compose_services_snapshot() -> list[dict[str, str]]:
    cmd = ["docker", "compose", "ps", "--format", "json"]
    try:
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT / "pmoves"), text=True, capture_output=True, check=False, timeout=20)
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    raw = proc.stdout.strip()
    rows: list[dict[str, str]] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = [parsed]
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    rows.append({str(k): str(v) for k, v in item.items()})
            return rows
    except Exception:
        pass

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append({str(k): str(v) for k, v in item.items()})
        except Exception:
            continue
    return rows


def select_worker_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    match_tokens = [
        token.strip().lower()
        for token in os.environ.get(
            "SHOWTIME_WORKER_MATCH",
            "worker,gateway,publisher,monitor,agent,archon,eval,hirag",
        ).split(",")
        if token.strip()
    ]
    selected: list[dict[str, str]] = []
    for row in rows:
        service = row.get("Service", "")
        key = service.lower()
        if any(token in key for token in match_tokens):
            selected.append(row)
    selected.sort(key=lambda item: item.get("Service", "").lower())
    return selected


def render_markdown(results: list[dict[str, str]], workers: list[dict[str, str]]) -> str:
    ok_count = sum(1 for row in results if row["status"] == "ok")
    lines = [
        "# Showtime Verify Links",
        "",
        "## Endpoint Status",
        f"- Ready: **{ok_count}/{len(results)}**",
        "",
        "| Name | URL | Status | Code |",
        "| --- | --- | --- | --- |",
    ]
    for row in results:
        lines.append(
            f"| {row['name']} | [{row['url']}]({row['url']}) | `{row['status']}` | `{row['code']}` |"
        )
    lines.extend(["", "## Worker Services", "| Service | State | Health |", "| --- | --- | --- |"])
    if workers:
        for row in workers:
            lines.append(
                f"| `{row.get('Service','')}` | `{row.get('State','unknown')}` | `{row.get('Health','n/a')}` |"
            )
    else:
        lines.append("| _none detected_ |  |  |")
    return "\n".join(lines) + "\n"


def render_html(results: list[dict[str, str]], workers: list[dict[str, str]]) -> str:
    def status_class(status: str) -> str:
        if status == "ok":
            return "ok"
        if status == "warn":
            return "warn"
        return "err"

    rows_html = "\n".join(
        [
            (
                "<tr>"
                f"<td>{html.escape(row['name'])}</td>"
                f"<td><a href=\"{html.escape(row['url'])}\" target=\"_blank\" rel=\"noopener\">{html.escape(row['url'])}</a></td>"
                f"<td class=\"{status_class(row['status'])}\">{html.escape(row['status'])}</td>"
                f"<td>{html.escape(str(row['code']))}</td>"
                "</tr>"
            )
            for row in results
        ]
    )
    worker_rows = "\n".join(
        [
            (
                "<tr>"
                f"<td>{html.escape(row.get('Service',''))}</td>"
                f"<td>{html.escape(row.get('State','unknown'))}</td>"
                f"<td>{html.escape(row.get('Health','n/a'))}</td>"
                "</tr>"
            )
            for row in workers
        ]
    )
    if not worker_rows:
        worker_rows = "<tr><td colspan=\"3\">none detected</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PMOVES Showtime Verify Links</title>
  <style>
    :root {{
      --bg: #0b1020;
      --bg2: #141d35;
      --text: #e7f0ff;
      --muted: #94a7c8;
      --ok: #22c55e;
      --warn: #f59e0b;
      --err: #ef4444;
      --accent: #38bdf8;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      color: var(--text);
      background: radial-gradient(circle at 10% 20%, var(--bg2), var(--bg));
      min-height: 100vh;
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 12px; color: var(--accent); }}
    p {{ color: var(--muted); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: rgba(9, 14, 28, 0.7);
      border: 1px solid rgba(148, 163, 184, 0.3);
      margin: 14px 0 24px;
    }}
    th, td {{
      text-align: left;
      border-bottom: 1px solid rgba(148, 163, 184, 0.2);
      padding: 10px 12px;
      font-size: 14px;
    }}
    th {{ color: #cde6ff; background: rgba(15, 23, 42, 0.9); }}
    a {{ color: #93c5fd; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .ok {{ color: var(--ok); font-weight: 600; }}
    .warn {{ color: var(--warn); font-weight: 600; }}
    .err {{ color: var(--err); font-weight: 600; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>PMOVES Showtime Verify Links</h1>
    <p>Click any URL to verify UI/pages/API endpoints while bring-up and smoke run.</p>
    <table>
      <thead><tr><th>Name</th><th>URL</th><th>Status</th><th>Code</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <h2>Helper/Worker Services</h2>
    <table>
      <thead><tr><th>Service</th><th>State</th><th>Health</th></tr></thead>
      <tbody>{worker_rows}</tbody>
    </table>
  </div>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    required_raw = os.environ.get("SHOWTIME_REQUIRED_NAMES", "")
    required_names = {name.strip() for name in required_raw.split(",") if name.strip()} or DEFAULT_REQUIRED

    results: list[dict[str, str]] = []
    for name, url in ENDPOINTS:
        status, code, error = check(url, timeout=args.timeout)
        results.append(
            {
                "name": name,
                "url": url,
                "status": status,
                "code": str(code),
                "error": error,
                "required": "true" if name in required_names else "false",
            }
        )
    results.sort(key=lambda row: row["name"].lower())

    workers = select_worker_rows(compose_services_snapshot())

    output_json = args.output_json.resolve()
    output_md = args.output_md.resolve()
    output_html = args.output_html.resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_html.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "required_names": sorted(required_names),
        "results": results,
        "workers": workers,
    }
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(results, workers), encoding="utf-8")
    output_html.write_text(render_html(results, workers), encoding="utf-8")

    rel_json = output_json.relative_to(REPO_ROOT).as_posix()
    rel_md = output_md.relative_to(REPO_ROOT).as_posix()
    rel_html = output_html.relative_to(REPO_ROOT).as_posix()
    click_url = output_html.resolve().as_uri()
    print(f"Wrote {rel_json}")
    print(f"Wrote {rel_md}")
    print(f"Wrote {rel_html}")
    print(f"Open report: {click_url}")

    if args.open:
        webbrowser.open(click_url)

    if args.strict:
        failing = [
            row
            for row in results
            if row["name"] in required_names and row["status"] not in {"ok", "warn"}
        ]
        if failing:
            print("Strict mode failures:")
            for row in failing:
                print(f"- {row['name']} -> {row['code']} {row['error']}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

