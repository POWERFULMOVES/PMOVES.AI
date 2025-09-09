import os, json, asyncio
from typing import Dict, Any, Optional
import httpx
from fastapi import FastAPI, Body, HTTPException
from nats.aio.client import Client as NATS

app = FastAPI(title="Publisher-Discord", version="0.1.0")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_USERNAME = os.environ.get("DISCORD_USERNAME", "PMOVES")
DISCORD_AVATAR_URL = os.environ.get("DISCORD_AVATAR_URL", "")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
SUBJECTS = os.environ.get("DISCORD_SUBJECTS", "ingest.file.added.v1,ingest.transcript.ready.v1,ingest.summary.ready.v1,ingest.chapters.ready.v1").split(",")

_nc: Optional[NATS] = None

@app.get("/healthz")
async def healthz():
    return {"ok": True, "webhook": bool(DISCORD_WEBHOOK_URL)}

async def _post_discord(content: Optional[str], embeds: Optional[list]=None, retries: int = 3):
    if not DISCORD_WEBHOOK_URL:
        return False
    payload = {"username": DISCORD_USERNAME}
    if DISCORD_AVATAR_URL:
        payload["avatar_url"] = DISCORD_AVATAR_URL
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds
    backoff = 1.0
    async with httpx.AsyncClient(timeout=15) as client:
        for _ in range(max(1, retries)):
            r = await client.post(DISCORD_WEBHOOK_URL, json=payload)
            if r.status_code in (200, 204):
                return True
            if r.status_code == 429:
                try:
                    ra = float(r.headers.get("Retry-After", backoff))
                except Exception:
                    ra = backoff
                await asyncio.sleep(ra)
                backoff = min(backoff * 2.0, 8.0)
                continue
            if 500 <= r.status_code < 600:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)
                continue
            return False
    return False

def _format_event(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    name = name.strip()
    emb = {"title": name, "fields": []}
    thumb = None
    if name == "ingest.file.added.v1":
        title = payload.get("title") or payload.get("key")
        emb["title"] = f"Ingest: {title}"
        emb["fields"].append({"name":"Bucket", "value": str(payload.get("bucket")), "inline": True})
        emb["fields"].append({"name":"Namespace", "value": str(payload.get("namespace")), "inline": True})
        if payload.get("video_id"):
            emb["fields"].append({"name":"Video ID", "value": str(payload.get("video_id")), "inline": True})
        thumb = (payload.get("thumb") if isinstance(payload.get("thumb"), str) else None)
    elif name == "ingest.transcript.ready.v1":
        emb["title"] = f"Transcript ready: {payload.get('video_id')}"
        emb["fields"].append({"name":"Language", "value": str(payload.get("language") or "auto"), "inline": True})
        if payload.get("s3_uri"):
            emb["fields"].append({"name":"Audio", "value": payload.get("s3_uri"), "inline": False})
    elif name == "ingest.summary.ready.v1":
        summ = payload.get("summary") or ""
        emb["title"] = f"Summary: {payload.get('video_id')}"
        emb["description"] = (summ[:1800] + ("…" if len(summ) > 1800 else ""))
    elif name == "ingest.chapters.ready.v1":
        ch = payload.get("chapters") or []
        emb["title"] = f"Chapters: {payload.get('video_id')} ({len(ch)} items)"
        if ch:
            sample = "\n".join(f"• {c.get('title')}" for c in ch[:6])
            emb["description"] = sample
    else:
        desc = json.dumps(payload)[:1800]
        emb["description"] = f"```json\n{desc}\n```"
    if thumb:
        emb["thumbnail"] = {"url": thumb}
    return {"content": None, "embeds": [emb]}

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
