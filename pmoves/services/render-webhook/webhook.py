import os, time, hmac, hashlib, json
from typing import Optional, Dict, Any
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from starlette.responses import Response
import requests
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus Metrics
# ─────────────────────────────────────────────────────────────────────────────
WEBHOOK_REQUESTS = Counter(
    "render_webhook_requests_total",
    "Total webhook requests received",
    ["status"]
)
WEBHOOK_LATENCY = Histogram(
    "render_webhook_duration_seconds",
    "Time spent processing webhook requests",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)
SUPA_OPS = Counter(
    "render_webhook_supa_operations_total",
    "Total Supabase operations",
    ["operation", "table"]
)

SUPA = os.environ.get("SUPA_REST_URL","http://postgrest:3000")
DEFAULT_NAMESPACE = os.environ.get("DEFAULT_NAMESPACE","pmoves")
SHARED = os.environ.get("RENDER_WEBHOOK_SHARED_SECRET","")
AUTO_APPROVE = os.environ.get("RENDER_AUTO_APPROVE","false").lower()=="true"
SUPA_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
SUPA_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

def inject_auth_headers(headers: Dict[str,str]):
    token = None
    if SUPA_SERVICE_KEY and "." in SUPA_SERVICE_KEY:
        token = SUPA_SERVICE_KEY
    elif SUPA_ANON_KEY and "." in SUPA_ANON_KEY:
        token = SUPA_ANON_KEY
    if token:
        headers["apikey"] = token
        headers["authorization"] = f"Bearer {token}"

def ok_sig(auth: Optional[str]) -> bool:
    if not SHARED:
        return True
    if not auth or not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ",1)[1].strip()
    return hmac.compare_digest(token, SHARED)

def supa_insert(table, row: Dict[str,Any]):
    headers = {
        "content-type": "application/json",
        "accept": "application/json",
        # Ask PostgREST to return the inserted row so JSON is present
        "prefer": "return=representation"
    }
    inject_auth_headers(headers)
    SUPA_OPS.labels(operation="insert", table=table).inc()
    r = requests.post(f"{SUPA}/{table}", headers=headers, data=json.dumps(row), timeout=30)
    r.raise_for_status()
    # Some deployments may still return empty body; guard to avoid 500s
    return (r.json() if r.text and r.text.strip() else {"status": r.status_code})

def supa_update(table, id, patch: Dict[str,Any]):
    headers = {
        "content-type": "application/json",
        "accept": "application/json",
        "prefer": "return=representation"
    }
    inject_auth_headers(headers)
    SUPA_OPS.labels(operation="update", table=table).inc()
    r = requests.patch(f"{SUPA}/{table}?id=eq.{id}", headers=headers, data=json.dumps(patch), timeout=30)
    r.raise_for_status()
    return (r.json() if r.text and r.text.strip() else {"status": r.status_code})

class RenderPayload(BaseModel):
    bucket: str
    key: str
    s3_uri: str
    presigned_get: Optional[str] = None
    title: Optional[str] = None
    namespace: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[list[str]] = None
    graph_hash: Optional[str] = None
    meta: Optional[Dict[str,Any]] = None
    auto_approve: Optional[bool] = None

app = FastAPI(title="PMOVES Render Webhook", version="1.0.0")

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/comfy/webhook")
def comfy_webhook(body: RenderPayload, authorization: Optional[str] = Header(None)):
    start = time.time()
    try:
        if not ok_sig(authorization):
            WEBHOOK_REQUESTS.labels(status="unauthorized").inc()
            raise HTTPException(status_code=401, detail="unauthorized")
        ns = body.namespace or DEFAULT_NAMESPACE
        status = "approved" if (body.auto_approve or AUTO_APPROVE) else "submitted"
        row = {
            "title": body.title or body.key.split("/")[-1],
            "namespace": ns,
            "content_url": body.s3_uri,
            "status": status,
            "meta": {
                "author": body.author,
                "tags": body.tags or [],
                "graph_hash": body.graph_hash,
                "presigned_get": body.presigned_get,
                "webhook": True,
                "source": "comfyui"
            }
        }
        created = supa_insert("studio_board", row)
        WEBHOOK_REQUESTS.labels(status="success").inc()
        return {"ok": True, "studio_board": created}
    except HTTPException:
        raise
    except Exception:
        WEBHOOK_REQUESTS.labels(status="error").inc()
        raise
    finally:
        WEBHOOK_LATENCY.observe(time.time() - start)
