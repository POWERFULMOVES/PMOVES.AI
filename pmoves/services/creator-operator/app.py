"""creator-operator FastAPI service (L3 dispatcher). Port 8120."""
from fastapi import FastAPI
from config import Config


def create_app() -> FastAPI:
    app = FastAPI(title="creator-operator", version="1.0.0")

    @app.get("/healthz")
    def healthz():
        return {"service": Config.SERVICE_SLUG, "ok": True, "nats": bool(Config.NATS_URL)}

    @app.get("/metrics")
    def metrics():
        return {"service": Config.SERVICE_SLUG, "up": 1}

    @app.on_event("startup")
    async def _startup():
        # Subscribe the dispatcher only when NATS is configured (mirrors clap-embed).
        if Config.NATS_URL:
            from dispatcher import run_responder
            app.state.nc = await run_responder()

    @app.on_event("shutdown")
    async def _shutdown():
        nc = getattr(app.state, "nc", None)
        if nc is not None:
            await nc.close()

    return app


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=Config.PORT)
