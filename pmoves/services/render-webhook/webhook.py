import os, time, hmac, hashlib, json
from typing import Optional, Dict, Any
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
import requests

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

@app.post("/comfy/webhook")
def comfy_webhook(body: RenderPayload, authorization: Optional[str] = Header(None)):
    if not ok_sig(authorization):
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
    return {"ok": True, "studio_board": created}
