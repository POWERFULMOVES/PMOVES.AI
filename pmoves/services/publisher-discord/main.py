import os, json, asyncio
from typing import Dict, Any, Optional
import httpx
from fastapi import FastAPI, Body, HTTPException
from nats.aio.client import Client as NATS

app = FastAPI(title="Publisher-Discord", version="0.1.0")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
SUBJECTS = os.environ.get("DISCORD_SUBJECTS", "ingest.file.added.v1,ingest.transcript.ready.v1,ingest.summary.ready.v1,ingest.chapters.ready.v1").split(",")

_nc: Optional[NATS] = None

@app.get("/healthz")
async def healthz():
    return {"ok": True, "webhook": bool(DISCORD_WEBHOOK_URL)}

async def _post_discord(content: str, embeds: Optional[list]=None):
    if not DISCORD_WEBHOOK_URL:
        return False
    payload = {"content": content}
    if embeds:
        payload["embeds"] = embeds
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(DISCORD_WEBHOOK_URL, json=payload)
        return r.status_code in (200, 204)

def _format_event(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    title = f"{name}"
    desc = json.dumps(payload)[:1800]
    return {
        "content": None,
        "embeds": [{"title": title, "description": f"```json\n{desc}\n```"}]
    }

@app.on_event("startup")
async def startup():
    global _nc
    _nc = NATS()
    try:
        await _nc.connect(servers=[NATS_URL])
    except Exception:
        _nc = None
        return
    async def handler(msg):
        try:
            data = json.loads(msg.data.decode("utf-8"))
            name = data.get("topic") or msg.subject
            payload = data.get("payload") or data
        except Exception:
            name = msg.subject
            payload = {"raw": msg.data.decode("utf-8",errors="ignore")}
        rendered = _format_event(name, payload)
        await _post_discord(rendered.get("content"), rendered.get("embeds"))
    for subj in SUBJECTS:
        s = subj.strip()
        if not s:
            continue
        try:
            await _nc.subscribe(s, cb=handler)
        except Exception:
            pass

@app.post("/publish")
async def publish_test(body: Dict[str, Any] = Body(...)):
    content = body.get("content") or "PMOVES test message"
    embeds = body.get("embeds")
    ok = await _post_discord(content, embeds)
    if not ok:
        raise HTTPException(502, "discord webhook failed")
    return {"ok": True}

