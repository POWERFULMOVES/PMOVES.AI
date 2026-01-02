import os, time, hmac, hashlib
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, Header, Query
from pydantic import BaseModel, Field
import boto3
from botocore.config import Config
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

def get_s3():
    endpoint = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT")
    access_key = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    region = os.environ.get("AWS_DEFAULT_REGION","us-east-1")
    secure = (os.environ.get("MINIO_SECURE","true").lower() == "true")
    if not (endpoint and access_key and secret_key):
        raise RuntimeError("Missing MINIO/S3 credentials or endpoint")
    # Build endpoint_url if not a full URL
    if "://" not in endpoint:
        endpoint_url = f"{'https' if secure else 'http'}://{endpoint}"
    else:
        endpoint_url = endpoint
    return boto3.client("s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        endpoint_url=endpoint_url,
        config=Config(s3={"addressing_style": "virtual"}))

ALLOWED_BUCKETS = set([b.strip() for b in os.environ.get("ALLOWED_BUCKETS","").split(",") if b.strip()])
SHARED_SECRET = os.environ.get("PRESIGN_SHARED_SECRET","")

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus Metrics
# ─────────────────────────────────────────────────────────────────────────────
PRESIGN_REQUESTS = Counter(
    "presign_requests_total",
    "Total presign requests",
    ["operation", "status"]
)
PRESIGN_LATENCY = Histogram(
    "presign_latency_seconds",
    "Presign operation latency in seconds",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)
PRESIGN_AUTH_FAILURES = Counter(
    "presign_auth_failures_total",
    "Total authentication failures"
)
PRESIGN_BUCKET_DENIALS = Counter(
    "presign_bucket_denials_total",
    "Total bucket access denials",
    ["bucket"]
)

def check_auth(authorization: Optional[str] = Header(None)):
    if not SHARED_SECRET:
        return True
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer")
    token = authorization.split(" ",1)[1].strip()
    if not hmac.compare_digest(token, SHARED_SECRET):
        raise HTTPException(status_code=403, detail="bad token")
    return True

def check_bucket(bucket: str):
    if ALLOWED_BUCKETS and bucket not in ALLOWED_BUCKETS:
        raise HTTPException(status_code=403, detail="bucket not allowed")

class PresignReq(BaseModel):
    bucket: str
    key: str
    expires: int = Field(default=900, ge=60, le=604800)  # 1 min to 7 days
    content_type: Optional[str] = None

class PresignPostReq(BaseModel):
    bucket: str
    key: str
    expires: int = Field(default=900, ge=60, le=604800)
    content_type: Optional[str] = None
    acl: Optional[str] = None

app = FastAPI(title="PMOVES Presign", version="1.0.0")

@app.get("/healthz")
def healthz():
    return {"ok": True, "time": int(time.time())}

@app.get("/metrics")
def metrics_endpoint():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/presign/put")
def presign_put(req: PresignReq, authorization: Optional[str] = Header(None)):
    start = time.time()
    try:
        check_auth(authorization); check_bucket(req.bucket)
        s3 = get_s3()
        params = {"Bucket": req.bucket, "Key": req.key}
        if req.content_type:
            params["ContentType"] = req.content_type
        url = s3.generate_presigned_url("put_object", Params=params, ExpiresIn=req.expires)
        PRESIGN_REQUESTS.labels(operation="put", status="success").inc()
        return {"url": url, "method": "PUT", "headers": {"Content-Type": req.content_type} if req.content_type else {}}
    except HTTPException as e:
        if e.status_code == 401:
            PRESIGN_AUTH_FAILURES.inc()
        elif e.status_code == 403:
            PRESIGN_BUCKET_DENIALS.labels(bucket=req.bucket).inc()
        PRESIGN_REQUESTS.labels(operation="put", status="error").inc()
        raise
    finally:
        PRESIGN_LATENCY.observe(time.time() - start)

@app.post("/presign/get")
def presign_get(req: PresignReq, authorization: Optional[str] = Header(None)):
    start = time.time()
    try:
        check_auth(authorization); check_bucket(req.bucket)
        s3 = get_s3()
        params = {"Bucket": req.bucket, "Key": req.key}
        url = s3.generate_presigned_url("get_object", Params=params, ExpiresIn=req.expires)
        PRESIGN_REQUESTS.labels(operation="get", status="success").inc()
        return {"url": url, "method": "GET"}
    except HTTPException as e:
        if e.status_code == 401:
            PRESIGN_AUTH_FAILURES.inc()
        elif e.status_code == 403:
            PRESIGN_BUCKET_DENIALS.labels(bucket=req.bucket).inc()
        PRESIGN_REQUESTS.labels(operation="get", status="error").inc()
        raise
    finally:
        PRESIGN_LATENCY.observe(time.time() - start)

@app.post("/presign/post")
def presign_post(req: PresignPostReq, authorization: Optional[str] = Header(None)):
    start = time.time()
    try:
        check_auth(authorization); check_bucket(req.bucket)
        s3 = get_s3()
        fields = {}
        conditions = []
        if req.content_type:
            fields["Content-Type"] = req.content_type
            conditions.append({"Content-Type": req.content_type})
        if req.acl:
            fields["acl"] = req.acl
            conditions.append({"acl": req.acl})
        post = s3.generate_presigned_post(req.bucket, req.key, Fields=fields, Conditions=conditions, ExpiresIn=req.expires)
        PRESIGN_REQUESTS.labels(operation="post", status="success").inc()
        return {"url": post["url"], "fields": post["fields"]}
    except HTTPException as e:
        if e.status_code == 401:
            PRESIGN_AUTH_FAILURES.inc()
        elif e.status_code == 403:
            PRESIGN_BUCKET_DENIALS.labels(bucket=req.bucket).inc()
        PRESIGN_REQUESTS.labels(operation="post", status="error").inc()
        raise
    finally:
        PRESIGN_LATENCY.observe(time.time() - start)

