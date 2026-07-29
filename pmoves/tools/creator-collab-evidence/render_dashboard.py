"""Creator Collab Lane — visual evidence dashboard generator.

Renders the slice 1+2+3+4+6 deliverables as a single static HTML page
that visualizes:
- the 12-room directory (pmoves/config/rooms/catalog.json)
- the 2 new room manifests in detail (creator-studio + helpdesk) with
  their skill_bindings + pinokio_app_refs + hardware_requirements
- the 12 pinokio-apps registry (curated YAML entries, with hardware +
  network_exposure)
- the 4 layer-TAC trees (L1 venv / L2 container / L3 mesh / L4 public)
- the 99 NATS topics with the 3 new helpdesk.* highlighted

Inputs: pmoves/config/rooms/catalog.json, the 2 new room manifests,
the 12 curated YAML files, the topics.json. Output: index.html in the
same directory.

Why a generator instead of a hand-written HTML:
- the data is the source of truth (no copy-paste drift)
- re-rendering after a slice commit is one command
- the rendered page is committed alongside the source so a viewer
  can see both the data and the visualization

Usage (from the worktree root):
    C:/Users/russe/AppData/Local/Programs/Python/Python312/python.exe \\
        pmoves/tools/creator-collab-evidence/render_dashboard.py \\
        --out pmoves/docs/evidence/creator-collab-2026-07-28/index.html

Then serve the directory on a local port and screenshot:
    python -m http.server 8848 --directory pmoves/docs/evidence/creator-collab-2026-07-28

Playwright script (pmoves/tools/creator-collab-evidence/capture_screenshots.py)
opens http://127.0.0.1:8848/ and writes PNGs to ./screenshots/.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CATALOG_PATH = REPO_ROOT / "pmoves" / "config" / "rooms" / "catalog.json"
CREATOR_STUDIO_PATH = REPO_ROOT / "pmoves" / "config" / "rooms" / "creator-studio.room.collab.json"
HELPDESK_PATH = REPO_ROOT / "pmoves" / "config" / "rooms" / "pmoves.room.helpdesk.json"
PINOKIO_CURATED_DIR = REPO_ROOT / "pmoves" / "configs" / "pinokio-apps" / "curated"
PINOKIO_SCHEMA_PATH = REPO_ROOT / "pmoves" / "configs" / "pinokio-apps" / "schema" / "pinokio-app.v1.schema.json"
TAC_TREES_DIR = REPO_ROOT / "pmoves" / "configs" / "tac_trees"
TOPICS_PATH = REPO_ROOT / "pmoves" / "contracts" / "topics.json"


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path):
    return json.loads(_read_text(path))


def _hardware_summary(room: dict) -> str:
    """Compact one-line hardware summary for the room card."""
    hr = room.get("hardware_requirements", {})
    if not hr:
        return "no hardware_requirements"
    gpu = "GPU" if hr.get("gpu") else "CPU"
    vram = hr.get("min_vram_mb", 0)
    roles = ",".join(hr.get("node_roles", []))
    return f"{gpu} {vram}MB · {roles}"


def _app_refs_summary(room: dict) -> str:
    refs = room.get("pinokio_app_refs", [])
    if not refs:
        return "no pinokio_app_refs"
    return ", ".join(
        f"{r.get('slug')}({r.get('role','?')}, {r.get('gpu_reservation_mb',0)}MB"
        + (f", {r.get('gpu_reservation_mode','concurrent')}" if r.get('gpu_reservation_mode') else "")
        + (f", autostart={r.get('autostart')}" if r.get('autostart') is False else "")
        + ")"
        for r in refs
    )


def _render_room_card(room: dict) -> str:
    rid = html.escape(room.get("room_id", "?"))
    name = html.escape(room.get("display_name", "?"))
    purpose = html.escape(room.get("room_purpose", "—"))
    surface = html.escape(room.get("creator_surface", "—"))
    stage = html.escape(room.get("stage", "—"))
    agent = html.escape(room.get("agent_id", "?"))
    hardware = _hardware_summary(room)
    app_refs = _app_refs_summary(room)
    apps = room.get("apps", [])
    skills = room.get("skill_bindings", [])
    publisher = room.get("policies", {}).get("publish", {}).get("allow_nats_emit", False)
    external = room.get("policies", {}).get("publish", {}).get("allow_external_publish", False)
    skill_rows = "".join(
        f"<li><code>{html.escape(s.get('skill_id','?'))}</code> — "
        f"<em>{html.escape(s.get('display_name', s.get('binding_id','?')))}</em> "
        f"<small>({html.escape(s.get('activation',{}).get('invocation_mode','?'))})</small></li>"
        for s in skills
    )
    app_rows = "".join(
        f"<li><code>{html.escape(a.get('app_id','?'))}</code> — "
        f"{html.escape(a.get('kind','?'))} · route <code>{html.escape(a.get('route','?'))}</code> · "
        f"status <strong>{html.escape(a.get('status','?'))}</strong></li>"
        for a in apps
    )
    invite = room.get("access", {}).get("invite_list", [])
    return f"""
    <div class="room-card">
      <h3>{name}</h3>
      <div class="rid"><code>{rid}</code></div>
      <table>
        <tr><th>purpose</th><td>{purpose}</td></tr>
        <tr><th>creator_surface</th><td>{surface}</td></tr>
        <tr><th>stage</th><td>{stage}</td></tr>
        <tr><th>agent_id</th><td><code>{agent}</code></td></tr>
        <tr><th>hardware</th><td>{hardware}</td></tr>
        <tr><th>pinokio_app_refs</th><td><code>{app_refs}</code></td></tr>
        <tr><th>policies.publish</th><td>allow_nats_emit={publisher}, allow_external_publish={external}</td></tr>
        <tr><th>access.invite_list</th><td>{', '.join(html.escape(x) for x in invite) if invite else '—'}</td></tr>
      </table>
      <h4>apps ({len(apps)})</h4>
      <ul>{app_rows}</ul>
      <h4>skill_bindings ({len(skills)})</h4>
      <ul>{skill_rows}</ul>
    </div>
    """


def _render_rooms_section(catalog: dict, creator_studio: dict, helpdesk: dict) -> str:
    rooms = catalog.get("rooms", [])
    cs_card = _render_room_card(creator_studio)
    hd_card = _render_room_card(helpdesk)
    other_rows = "".join(
        f"<tr><td><code>{html.escape(r.get('room_id','?'))}</code></td>"
        f"<td>{html.escape(r.get('display_name','?'))}</td>"
        f"<td><code>{html.escape(r.get('manifest','?'))}</code></td>"
        f"<td>{html.escape(r.get('current_stage','?'))}</td></tr>"
        for r in rooms if r.get("room_id") not in ("creator-studio.room.collab", "pmoves.room.helpdesk")
    )
    return f"""
    <section id="rooms">
      <h2>1. Room directory — {len(rooms)} rooms (slice 1 + slice 6 added 2)</h2>
      <table class="catalog">
        <thead>
          <tr><th>room_id</th><th>display_name</th><th>manifest</th><th>current_stage</th></tr>
        </thead>
        <tbody>
          {other_rows}
        </tbody>
      </table>
      <h3>Slice 1 — creator-studio.room.collab (first consumer of slice 1's 4 new fields)</h3>
      {cs_card}
      <h3>Slice 6 — pmoves.room.helpdesk (first consumer of <code>room_purpose: intake</code> + <code>creator_surface: ambient</code>)</h3>
      {hd_card}
    </section>
    """


def _render_pinokio_apps_section(curated_dir: Path) -> str:
    entries = []
    for f in sorted(curated_dir.glob("*.yaml")):
        try:
            data = _load_yaml(f)
        except Exception as e:
            entries.append({"slug": f.stem, "_error": str(e), "title": "PARSE ERROR"})
            continue
        entries.append(data)
    cards = []
    for e in entries:
        slug = html.escape(e.get("slug", "?"))
        title = html.escape(e.get("title", "?"))
        desc = html.escape((e.get("description") or "")[:200])
        runtime = e.get("runtime", {}) or {}
        gpu = "GPU" if runtime.get("gpu_required") else "CPU"
        vram = runtime.get("min_vram_mb", 0)
        arch = ",".join(runtime.get("gpu_arch") or [])
        autostart = runtime.get("autostart", "—")
        net = e.get("network_exposure", {}) or {}
        l1 = "✓" if (net.get("l1_venv") or {}).get("reachable") else "—"
        l2 = "✓" if (net.get("l2_container_same_host") or {}).get("reachable") else "—"
        l2_addr = (net.get("l2_container_same_host") or {}).get("address", "")
        l3 = "✓" if (net.get("l3_mesh") or {}).get("reachable") else "—"
        l3_addr = (net.get("l3_mesh") or {}).get("address", "")
        l4 = "✓" if (net.get("l4_public") or {}).get("reachable") else "—"
        l4_url = (net.get("l4_public") or {}).get("public_url", "")
        l4_url_html = f'<div class="addr">{html.escape(l4_url)}</div>' if l4_url else ""
        l2_addr_html = f'<div class="addr">{html.escape(l2_addr)}</div>' if l2_addr else ""
        l3_addr_html = f'<div class="addr">{html.escape(l3_addr)}</div>' if l3_addr else ""
        cards.append(f"""
        <div class="app-card">
          <h4>{title}</h4>
          <div class="slug"><code>{slug}</code></div>
          <p class="desc">{desc}…</p>
          <table>
            <tr><th>hardware</th><td>{gpu} {vram}MB</td></tr>
            <tr><th>gpu_arch</th><td>{html.escape(arch) or '—'}</td></tr>
            <tr><th>autostart</th><td>{html.escape(str(autostart))}</td></tr>
            <tr><th>L1 venv</th><td>{l1}</td></tr>
            <tr><th>L2 container</th><td>{l2} {l2_addr_html}</td></tr>
            <tr><th>L3 mesh</th><td>{l3} {l3_addr_html}</td></tr>
            <tr><th>L4 public</th><td>{l4} {l4_url_html}</td></tr>
          </table>
        </div>
        """)
    return f"""
    <section id="pinokio-apps">
      <h2>2. Pinokio Apps Registry — {len(entries)} curated entries (slice 4)</h2>
      <p>4-layer reachability model: L1 venv → L2 same-host container → L3 tailnet mesh → L4 public via kvm2 Cloudflare-Tunnel + Hostinger DNS.</p>
      <div class="cards-grid">
        {''.join(cards)}
      </div>
    </section>
    """


def _render_tac_trees_section(tac_dir: Path) -> str:
    if not tac_dir.exists():
        return "<section id='tac'><h2>3. Layer-TAC trees</h2><p>directory missing</p></section>"
    trees = sorted(tac_dir.glob("*.tac.yaml"))
    rows = "".join(
        f"<tr><td><code>{html.escape(t.name)}</code></td>"
        f"<td>{t.stat().st_size} bytes</td></tr>"
        for t in trees
    )
    return f"""
    <section id="tac">
      <h2>3. Layer-TAC trees — {len(trees)} trees (one per reachability layer, slice 4)</h2>
      <table class="catalog">
        <thead><tr><th>tree</th><th>size</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <p>Cascading gates: a failure in L1 propagates to L2/L3/L4 for the same app — surfacing which layer failed first rather than a single "is it reachable" bool.</p>
    </section>
    """


def _render_topics_section(topics_path: Path) -> str:
    data = _read_json(topics_path)
    topics = data.get("topics", {})
    helpdesk_topics = sorted([k for k in topics if k.startswith("helpdesk.")])
    comfy_topics = sorted([k for k in topics if k.startswith("comfy.collab.")])
    room_topics = sorted([k for k in topics if k.startswith("room.")])
    other = sorted(k for k in topics if not any(k.startswith(p) for p in ("helpdesk.", "comfy.collab.", "room.")))
    return f"""
    <section id="topics">
      <h2>4. NATS topics — {len(topics)} total (slice 3 +5, slice 6 +3)</h2>
      <h3>Slice 6 — 3 new helpdesk.* topics (highlighted)</h3>
      <ul class="topics">
        {''.join(f'<li class="hl"><code>{html.escape(t)}</code></li>' for t in helpdesk_topics)}
      </ul>
      <h3>Slice 3 — 5 new comfy.collab.* + room.* topics</h3>
      <ul class="topics">
        {''.join(f'<li><code>{html.escape(t)}</code></li>' for t in comfy_topics)}
        {''.join(f'<li><code>{html.escape(t)}</code></li>' for t in room_topics)}
      </ul>
      <h3>Pre-existing — {len(other)} topics</h3>
      <details><summary>show {len(other)} pre-existing topics</summary>
        <ul class="topics">
          {''.join(f'<li class="dim"><code>{html.escape(t)}</code></li>' for t in other)}
        </ul>
      </details>
    </section>
    """


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Creator Collab Lane — visual evidence (2026-07-28)</title>
  <style>
    :root {{
      --bg: #0f1115;
      --fg: #e6edf3;
      --dim: #8b949e;
      --accent: #7C3AED;
      --accent2: #0EA5E9;
      --hl: #f59e0b;
      --card-bg: #161b22;
      --border: #30363d;
      --code-bg: #1c2128;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      background: var(--bg); color: var(--fg);
      margin: 0; padding: 24px 32px; line-height: 1.5;
    }}
    h1 {{ font-size: 32px; margin: 0 0 8px; color: var(--accent); }}
    h2 {{ font-size: 24px; margin: 32px 0 12px; color: var(--accent2); border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
    h3 {{ font-size: 18px; margin: 24px 0 8px; }}
    h4 {{ font-size: 15px; margin: 12px 0 6px; color: var(--hl); }}
    .meta {{ color: var(--dim); font-size: 14px; margin-bottom: 24px; }}
    .meta code {{ background: var(--code-bg); padding: 2px 6px; border-radius: 3px; }}
    code {{ background: var(--code-bg); padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 13px; }}
    th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    th {{ background: #1c2128; color: var(--dim); font-weight: 600; }}
    .room-card, .app-card {{
      background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px;
      padding: 16px 20px; margin: 12px 0;
    }}
    .room-card h3, .app-card h4 {{ margin-top: 0; color: var(--accent); }}
    .rid {{ margin: 4px 0 12px; color: var(--dim); font-size: 13px; }}
    .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }}
    .catalog code {{ font-size: 12px; }}
    ul.topics {{ list-style: none; padding-left: 0; column-count: 3; column-gap: 16px; }}
    ul.topics li {{ break-inside: avoid; padding: 2px 0; font-size: 12px; }}
    ul.topics li.hl {{ color: var(--hl); font-weight: 600; }}
    ul.topics li.dim {{ color: var(--dim); }}
    details summary {{ cursor: pointer; color: var(--accent2); margin: 8px 0; }}
    .slices-summary {{
      display: flex; gap: 8px; margin: 16px 0; flex-wrap: wrap;
    }}
    .slice-badge {{
      background: var(--card-bg); border: 1px solid var(--border); border-radius: 4px;
      padding: 6px 10px; font-size: 13px; color: var(--dim);
    }}
    .slice-badge.done {{ border-color: var(--accent2); color: var(--accent2); }}
    .slice-badge.next {{ border-color: var(--hl); color: var(--hl); }}
    .desc {{ color: var(--dim); font-size: 13px; margin: 4px 0 8px; }}
    .addr {{ color: var(--dim); font-size: 11px; word-break: break-all; margin-top: 2px; }}
  </style>
</head>
<body>
  <h1>Creator Collab Lane — visual evidence (2026-07-28)</h1>
  <div class="meta">
    Generated by <code>pmoves/tools/creator-collab-evidence/render_dashboard.py</code> from the actual slice 1+2+3+4+6 artifacts in the lane.
    Lane: <code>feat/creator-collab-lane @ 970fb50792</code> · ship_count: 5/7 (slices 1+2+3+4+6 SHIPPED; slices 5+7 pending).
  </div>

  <div class="slices-summary">
    <span class="slice-badge done">slice 1 SHIPPED_MERGED (room manifest schema extensions)</span>
    <span class="slice-badge done">slice 2 SHIPPED (pinokio_bridge service + skill)</span>
    <span class="slice-badge done">slice 3 SHIPPED (NATS pipeline + 5 schemas)</span>
    <span class="slice-badge done">slice 4 SHIPPED (pinokio-apps registry + mesh_exposure + gepeto-wrapper)</span>
    <span class="slice-badge done">slice 6 SHIPPED (helpdesk room + 2 skills + 3 schemas)</span>
    <span class="slice-badge next">slice 5 (this page — visual evidence)</span>
    <span class="slice-badge">slice 7 (Fordham E2E — last)</span>
  </div>

  {rooms_section}
  {pinokio_section}
  {tac_section}
  {topics_section}

  <footer class="meta">
    Rendered: {rendered_at} · Re-run: <code>python pmoves/tools/creator-collab-evidence/render_dashboard.py</code>
  </footer>
</body>
</html>
"""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, help="output HTML path")
    args = p.parse_args(argv)

    catalog = _read_json(CATALOG_PATH)
    creator_studio = _read_json(CREATOR_STUDIO_PATH)
    helpdesk = _read_json(HELPDESK_PATH)

    rooms_section = _render_rooms_section(catalog, creator_studio, helpdesk)
    pinokio_section = _render_pinokio_apps_section(PINOKIO_CURATED_DIR)
    tac_section = _render_tac_trees_section(TAC_TREES_DIR)
    topics_section = _render_topics_section(TOPICS_PATH)

    html_text = HTML_TEMPLATE.format(
        rooms_section=rooms_section,
        pinokio_section=pinokio_section,
        tac_section=tac_section,
        topics_section=topics_section,
        rendered_at=html.escape(__import__("datetime").datetime.now().strftime("%Y-%m-%dT%H:%M:%S")),
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    print(f"wrote {out} ({len(html_text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
