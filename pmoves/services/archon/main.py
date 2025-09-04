from fastapi import FastAPI, Body
import os, asyncio, json
from nats.aio.client import Client as NATS
from services.common.events import envelope

app = FastAPI(title="Archon (PMOVES v5)")
PORT = int(os.environ.get("PORT", 8090))
NATS_URL = os.environ.get("NATS_URL","nats://nats:4222")

@app.get("/healthz")
def healthz():
    return {"status":"ok","service":"archon" }

@app.post("/events/publish")
async def events_publish(body: dict = Body(...)):
    topic = body.get("topic")
    payload = body.get("payload", {})
    msg = envelope(topic, payload, source="archon")
    await _nc.publish(topic.encode(), json.dumps(msg).encode())
    return {"published": topic}

async def nats_listener():
    global _nc
    _nc = NATS()
    await _nc.connect(servers=[NATS_URL])

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(nats_listener())

if __name__ == "__main__":
    import uvicorn, asyncio
    asyncio.run(startup_event())
    uvicorn.run(app, host="0.0.0.0", port=PORT)
