
import os, time, hmac, hashlib
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, Header, Query
from pydantic import BaseModel, Field
import boto3
from botocore.config import Config

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

@app.post("/presign/put")
def presign_put(req: PresignReq, authorization: Optional[str] = Header(None)):
    check_auth(authorization); check_bucket(req.bucket)
    s3 = get_s3()
    params = {"Bucket": req.bucket, "Key": req.key}
    if req.content_type:
        params["ContentType"] = req.content_type
    url = s3.generate_presigned_url("put_object", Params=params, ExpiresIn=req.expires)
    return {"url": url, "method": "PUT", "headers": {"Content-Type": req.content_type} if req.content_type else {}}

@app.post("/presign/get")
def presign_get(req: PresignReq, authorization: Optional[str] = Header(None)):
    check_auth(authorization); check_bucket(req.bucket)
    s3 = get_s3()
    params = {"Bucket": req.bucket, "Key": req.key}
    url = s3.generate_presigned_url("get_object", Params=params, ExpiresIn=req.expires)
    return {"url": url, "method": "GET"}

@app.post("/presign/post")
def presign_post(req: PresignPostReq, authorization: Optional[str] = Header(None)):
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
    return {"url": post["url"], "fields": post["fields"]}

