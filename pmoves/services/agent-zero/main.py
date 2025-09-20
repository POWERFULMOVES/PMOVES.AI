import os

from fastapi import Body, FastAPI

from services.agent_zero import controller

app = FastAPI(title="Agent-Zero (PMOVES v5)")
PORT = int(os.environ.get("PORT", 8080))

@app.get("/healthz")
def healthz():
    return {"status":"ok","service":"agent-zero" }

@app.post("/events/publish")
async def events_publish(body: dict = Body(...)):
    topic = body.get("topic")
    payload = body.get("payload", {})
    env = await controller.publish(topic, payload, source="agent-zero-api")
    return {"published": topic, "envelope": env}

@app.on_event("startup")
async def startup_event():
    await controller.start()


@app.on_event("shutdown")
async def shutdown_event():
    await controller.stop()


@app.get("/metrics")
async def metrics():
    return controller.metrics

if __name__ == "__main__":
    import asyncio
    import uvicorn

    async def _main():
        await controller.start()

    asyncio.run(_main())
    uvicorn.run(app, host="0.0.0.0", port=PORT)
