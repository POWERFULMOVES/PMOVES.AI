"""FastAPI application entrypoint for the PMOVES gateway service."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Ensure the repository root is importable for shared utilities.
_repo_root = Path(__file__).resolve().parents[4]
if str(_repo_root) not in sys.path:
    sys.path.append(str(_repo_root))

_contracts_dir = _repo_root / "pmoves" / "contracts"
if _contracts_dir.exists():
    os.environ.setdefault("PMOVES_CONTRACTS_DIR", str(_contracts_dir))

from .api import chit, events as events_api  # noqa: E402  (local import after sys.path tweak)
from .api.consciousness import router as consciousness_router  # noqa: E402
from .api.events import router as events_router  # noqa: E402
from .api.mindmap import router as mindmap_router  # noqa: E402
from .api.signaling import router as sig_router  # noqa: E402
from .api.viz import router as viz_router  # noqa: E402
from .api.workflow import router as workflow_router  # noqa: E402
from ..event_bus import EventBus  # noqa: E402

logger = logging.getLogger("pmoves.gateway")

# Shared NATS event bus (publishes contracts + captures workflow events).
event_bus = EventBus(
    nats_url=os.environ.get("NATS_URL", "nats://nats:4222"),
    subscribe_topics=[
        "ingest.file.added.v1",
        "ingest.transcript.ready.v1",
        "kb.upsert.request.v1",
        "kb.upsert.result.v1",
    ],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage PMOVES Gateway application lifespan."""
    # Startup
    if app.state.event_bus:
        await app.state.event_bus.start()
    yield
    # Shutdown
    if app.state.event_bus:
        await app.state.event_bus.stop()


app = FastAPI(title="PMOVES.AI Gateway", lifespan=lifespan)

# Initialise ShapeStore so CHIT endpoints have in-memory state available.
try:  # pragma: no cover - optional during documentation builds
    from pmoves.services.common.shape_store import ShapeStore

    _shape_store = ShapeStore(capacity=10_000)
    chit.set_shape_store(_shape_store)
    app.state.shape_store = _shape_store
except Exception as exc:  # pragma: no cover - optional dependency
    logger.warning("ShapeStore unavailable: %s", exc)
    _shape_store = None
    chit.set_shape_store(None)

events_api.set_event_bus(event_bus)
app.state.event_bus = event_bus

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chit.router)
app.include_router(consciousness_router)
app.include_router(sig_router)
app.include_router(viz_router)
app.include_router(workflow_router)
app.include_router(events_router)
app.include_router(mindmap_router)

_service_root = Path(__file__).resolve().parents[1]
app.mount("/web", StaticFiles(directory=str(_service_root / "web")), name="web")
app.mount(
    "/data",
    StaticFiles(directory=str(_service_root / "data"), check_dir=False),
    name="data",
)
app.mount(
    "/artifacts",
    StaticFiles(directory=str(_service_root / "artifacts"), check_dir=False),
    name="artifacts",
)


@app.get("/demo/shapes-webrtc")
def demo() -> FileResponse:
    return FileResponse(str(_service_root / "web" / "demo_shapes_webrtc.html"))


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    learned = os.getenv("CHIT_LEARNED_TEXT", "false").lower() == "true"
    supa = bool(os.getenv("SUPA_REST_URL"))
    hirag = bool(os.getenv("HIRAG_URL"))
    jelly = bool(os.getenv("JELLYFIN_URL"))

    learned_color = "var(--acc)" if learned else "#ef4444"
    learned_text = "ON" if learned else "OFF"
    supa_color = "#34d399" if supa else "#ef4444"
    supa_text = "CONFIGURED" if supa else "NOT SET"
    hirag_color = "#34d399" if hirag else "#ef4444"
    hirag_text = "ONLINE" if hirag else "OFFLINE"
    jelly_color = "#34d399" if jelly else "#ef4444"
    jelly_text = "ONLINE" if jelly else "OFFLINE"

    html = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>PMOVES.AI Gateway</title>
  <style>
    :root{ --bg1:#0f172a; --bg2:#0b1324; --acc:#22d3ee; --acc2:#a78bfa; --txt:#e5e7eb; --mut:#94a3b8; --card:#0b1222cc; --glow:#22d3ee40; }
    *{ box-sizing:border-box }
    html,body{ height:100%; margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica Neue, Arial, \"Apple Color Emoji\", \"Segoe UI Emoji\"; color:var(--txt); }
    body{
      background: radial-gradient(1200px 600px at 10% 10%, #07233a, transparent),
                  radial-gradient(1000px 800px at 90% 30%, #1a1031, transparent),
                  linear-gradient(160deg, var(--bg1), var(--bg2));
      overflow-x:hidden;
    }
    .grid{ min-height:100%; display:grid; place-items:center; position:relative; }
    .orb{ position:absolute; width:40vmax; height:40vmax; border-radius:50%; background: radial-gradient(circle at 30% 30%, var(--acc), transparent 60%); filter: blur(60px); opacity:.35; animation: float 16s ease-in-out infinite; }
    .orb.o2{ background: radial-gradient(circle at 70% 60%, var(--acc2), transparent 55%); width:46vmax; height:46vmax; left:auto; right:-10vmax; top:10vmax; animation-delay:-6s; opacity:.25 }
    @keyframes float{ 0%,100%{ transform: translateY(-2vmax) translateX(-2vmax) } 50%{ transform: translateY(2vmax) translateX(2vmax) } }
    .card{ position:relative; max-width:960px; width:92%; padding:32px; border-radius:16px; background: linear-gradient(180deg,#0b1222e6,#0b1222cc); border:1px solid #1f2a44; box-shadow: 0 10px 40px #0008, 0 0 60px var(--glow); backdrop-filter:saturate(140%) blur(10px); }
    .head{ display:flex; gap:16px; align-items:center; margin-bottom:10px }
    .logo{ width:48px; height:48px; display:grid; place-items:center; border-radius:12px; background: conic-gradient(from 220deg, var(--acc), var(--acc2)); box-shadow: inset 0 0 20px #fff2; }
    .logo svg{ width:28px; height:28px }
    h1{ margin:0; font-size: clamp(28px, 3.4vw, 44px); letter-spacing:.3px }
    .sub{ color:var(--mut); margin:6px 0 22px; font-size: clamp(14px, 1.6vw, 16px) }
    .actions{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); gap:14px }
    .btn{ text-decoration:none; color:var(--txt); border:1px solid #23304f; padding:16px 18px; border-radius:12px; background: linear-gradient(180deg, #0e1830, #0b1428); display:flex; align-items:center; gap:12px; transition: transform .15s ease, box-shadow .15s ease, border-color .15s; }
    .btn:hover{ transform: translateY(-2px); border-color:#2e3e67; box-shadow: 0 8px 26px #0006, inset 0 0 0 1px #ffffff10 }
    .btn .icon{ width:18px; height:18px; opacity:.9; color:#7dd3fc }
    .btn .meta{ color:var(--mut); font-size:13px }
    .footer{ margin-top:22px; display:flex; gap:12px; align-items:center; color:var(--mut); font-size:13px; flex-wrap:wrap }
    .badge{ padding:6px 10px; border:1px solid #223457; border-radius:999px; background:#0b162b; }
    .pill{ padding:6px 10px; border-radius:999px; border:1px solid #223457; background:#0b162b; }
    .inline-btn{ display:inline-block; padding:8px 12px; border-radius:8px; border:1px solid #223457; background:#0e1830; color:#e5e7eb; text-decoration:none; cursor:pointer; }
    label span{ font-size:13px; color:var(--mut); }
    input{ font-family:inherit; }
  </style>
</head>
<body>
  <div class=\"grid\">
    <div class=\"orb\" style=\"left:-8vmax; top:-6vmax\"></div>
    <div class=\"orb o2\" style=\"right:-10vmax; top:10vmax\"></div>
    <main class=\"card\">
      <div class=\"head\">
        <div class=\"logo\">
          <svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"#0ea5b7\" stroke-width=\"2\">
            <circle cx=\"12\" cy=\"12\" r=\"6\"/>
            <path d=\"M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1\"/>
          </svg>
        </div>
        <div>
          <h1>PMOVES.AI Gateway</h1>
          <div class=\"sub\">Trigger YouTube ingest → Hi-RAG → Neo4j → CHIT visualization</div>
        </div>
      </div>

      <section class=\"actions\">
        <a class=\"btn\" href=\"/docs\">
          <svg class=\"icon\" viewBox=\"0 0 24 24\" fill=\"currentColor\">
            <path d=\"M4 19h16V5H4v14zm2-2h12V7H6v10z\"/>
          </svg>
          <div>
            <div>API Docs (Swagger)</div>
            <div class=\"meta\">Explore and test endpoints</div>
          </div>
        </a>

        <a class=\"btn\" href=\"/web/playground.html\">
          <svg class=\"icon\" viewBox=\"0 0 24 24\" fill=\"currentColor\">
            <path d=\"M12 2l3 7 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z\"/>
          </svg>
          <div>
            <div>Mix & Match Playground</div>
            <div class=\"meta\">Blend constellations • preview decode</div>
          </div>
        </a>
      </section>

      <section style=\"margin-top:24px\">
        <h2 style=\"margin:0 0 12px;font-size:18px;color:var(--mut);letter-spacing:.4px\">Workflow Demo (end-to-end)</h2>
        <div style=\"border:1px solid #223457;border-radius:12px;padding:16px;background:#0b162b70\">
          <form id=\"demoForm\" style=\"display:grid;gap:12px\">
            <label style=\"display:grid;gap:6px\">
              <span>YouTube URL</span>
              <input id=\"demoUrl\" type=\"text\" placeholder=\"https://www.youtube.com/watch?v=...\" style=\"padding:10px 12px;border-radius:8px;border:1px solid #223457;background:#0b162b;color:#e5e7eb\" />
            </label>
            <div style=\"display:flex;gap:12px;align-items:center;flex-wrap:wrap\">
              <label style=\"display:flex;align-items:center;gap:6px\">
                <span>Per constellation</span>
                <input id=\"demoK\" type=\"number\" value=\"20\" min=\"5\" max=\"50\" style=\"width:80px;padding:6px 8px;border-radius:8px;border:1px solid #223457;background:#0b162b;color:#e5e7eb\" />
              </label>
              <button class=\"inline-btn\" id=\"runDemo\" type=\"submit\">Run Orchestration</button>
              <span class=\"pill\">Learned Decode: <b style=\"color: __LEARNED_COLOR__\">__LEARNED_TEXT__</b></span>
              <span class=\"pill\">Supabase REST: <b style=\"color: __SUPA_COLOR__\">__SUPA_TEXT__</b></span>
              <span class=\"pill\">Hi-RAG: <b style=\"color: __HIRAG_COLOR__\">__HIRAG_TEXT__</b></span>
              <span class=\"pill\">Jellyfin: <b style=\"color: __JELLY_COLOR__\">__JELLY_TEXT__</b></span>
            </div>
          </form>
          <div class=\"meta\" style=\"margin-top:8px\">
            The gateway publishes NATS events, pushes transcript chunks into Hi-RAG, mirrors constellations into Neo4j, and renders CHIT shapes from the live media.
          </div>
          <pre id=\"demoOut\" style=\"margin-top:10px;white-space:pre-wrap;background:#0b162b;color:#b7fbce;border:1px solid #223457;border-radius:8px;padding:10px;min-height:140px;max-height:320px;overflow:auto\"></pre>
          <div id=\"demoLinks\" class=\"meta\"></div>
          <div id=\"eventFeed\" class=\"meta\" style=\"margin-top:10px\"></div>
        </div>
      </section>

      <section style=\"margin-top:24px\">
        <h2 style=\"margin:0 0 12px;font-size:18px;color:var(--mut);letter-spacing:.4px\">Quick Instructions</h2>
        <div style=\"display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px\">
          <div style=\"border:1px solid #223457;border-radius:12px;padding:14px;background:#0b162b70\">
            <div style=\"font-weight:600;margin-bottom:8px\">WebRTC Shapes Demo</div>
            <ol style=\"margin:0 0 10px 18px;padding:0;line-height:1.6\">
              <li>Open this page in two tabs/windows.</li>
              <li>In both tabs, open <a href=\"/demo/shapes-webrtc\">Shapes WebRTC Demo</a>.</li>
              <li>Use the same <code>Room</code>, then click <strong>Join</strong> in both.</li>
              <li>In either tab, click <strong>Connect</strong> to create the peer link.</li>
              <li>When \"datachannel open\" appears, try <strong>Send Text</strong> and <strong>Send Demo Shape</strong>.</li>
            </ol>
            <div class=\"meta\">Tip: If it doesn't connect, re-Join both tabs first, then Connect.</div>
          </div>
          <div style=\"border:1px solid #223457;border-radius:12px;padding:14px;background:#0b162b70\">
            <div style=\"font-weight:600;margin-bottom:8px\">CHIT APIs (REST)</div>
            <ol style=\"margin:0 0 10px 18px;padding:0;line-height:1.6\">
              <li>Open <a href=\"/web/client.html\">Client Test Page</a>.</li>
              <li>Paste a CGP JSON (see <code>tests/data/cgp_fixture.json</code>).</li>
              <li>Click <strong>Publish</strong> to POST <code>/geometry/event</code>.</li>
              <li>Click <strong>Decode</strong> for <code>/geometry/decode/text</code> and <strong>Calibration</strong> for metrics.</li>
            </ol>
          </div>
        </div>
      </section>

      <div class=\"footer\">
        <span class=\"badge\">FastAPI</span>
        <span class=\"badge\">Uvicorn</span>
        <span class=\"badge\">WebSocket</span>
        <span class=\"note\">Env: <code>CHIT_REQUIRE_SIGNATURE</code>, <code>CHIT_DECRYPT_ANCHORS</code>, <code>CHIT_PASSPHRASE</code>, <code>CHIT_LEARNED_TEXT</code>, <code>SUPA_REST_URL</code>, <code>HIRAG_URL</code>, <code>JELLYFIN_URL</code></span>
      </div>
    </main>
  </div>
  <script>
  const show = (el, obj) => { try { el.textContent = JSON.stringify(obj, null, 2); } catch(e){ el.textContent = String(obj); } };
  const mklinks = (base, shapeId) => {
    if (!shapeId) return '';
    const svg = `${base}/viz/shape/${shapeId}.svg`;
    const raw = `${base}/data/${shapeId}.json`;
    const rep = `${base}/artifacts/reconstruction_report.md`;
    return `View: <a href=\"${svg}\" target=\"_blank\">Shape SVG</a> · <a href=\"${raw}\" target=\"_blank\">Raw JSON</a> · <a href=\"${rep}\" target=\"_blank\">Reconstruction Report</a>`;
  };
  const out = document.getElementById('demoOut');
  const links = document.getElementById('demoLinks');
  const events = document.getElementById('eventFeed');
  document.getElementById('demoForm').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const url = document.getElementById('demoUrl').value.trim();
    const perConst = parseInt(document.getElementById('demoK').value || '20', 10);
    out.textContent = 'Running demo…';
    links.innerHTML = '';
    events.innerHTML = '';
    try {
      const payload = { per_constellation: perConst };
      if (url) payload.youtube_url = url;
      const r = await fetch('/workflow/demo_run', { method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(payload) });
      const obj = await r.json();
      show(out, obj);
      const sid = (obj && obj.shape && obj.shape.shape_id) ? obj.shape.shape_id : obj.shape_id;
      links.innerHTML = mklinks('', sid);
      try {
        const evs = await fetch('/events/recent?limit=6');
        const evJson = await evs.json();
        if (evJson && evJson.events) {
          events.innerHTML = `<strong>Recent events</strong><br/>${evJson.events.map(e => `<code>${e.topic}</code>`).join(' · ')}`;
        }
      } catch (err) {
        console.error(err);
      }
    } catch (e) {
      out.textContent = String(e);
    }
  });
  </script>
</body>
</html>
"""
    html = html.replace("__LEARNED_COLOR__", learned_color).replace("__LEARNED_TEXT__", learned_text)
    html = html.replace("__SUPA_COLOR__", supa_color).replace("__SUPA_TEXT__", supa_text)
    html = html.replace("__HIRAG_COLOR__", hirag_color).replace("__HIRAG_TEXT__", hirag_text)
    html = html.replace("__JELLY_COLOR__", jelly_color).replace("__JELLY_TEXT__", jelly_text)
    return html
