import os, json, tempfile, shutil, asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, Body, HTTPException
import yt_dlp
import boto3
import requests
from nats.aio.client import Client as NATS
from services.common.events import envelope

app = FastAPI(title="PMOVES.YT", version="1.0.0")

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"
MINIO_SECURE = (os.environ.get("MINIO_SECURE","false").lower() == "true")
DEFAULT_BUCKET = os.environ.get("YT_BUCKET","assets")
DEFAULT_NAMESPACE = os.environ.get("INDEXER_NAMESPACE","pmoves")
SUPA = os.environ.get("SUPA_REST_URL","http://postgrest:3000")
NATS_URL = os.environ.get("NATS_URL","nats://nats:4222")

_nc: Optional[NATS] = None

def s3_client():
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client("s3", aws_access_key_id=MINIO_ACCESS_KEY, aws_secret_access_key=MINIO_SECRET_KEY, endpoint_url=endpoint_url)

@app.on_event("startup")
async def startup():
    global _nc
    _nc = NATS()
    try:
        await _nc.connect(servers=[NATS_URL])
    except Exception:
        _nc = None

@app.get("/healthz")
def healthz():
    return {"ok": True}

def _publish_event(topic: str, payload: Dict[str,Any]):
    if _nc is None:
        return
    msg = envelope(topic, payload, source="pmoves-yt")
    asyncio.create_task(_nc.publish(topic.encode(), json.dumps(msg).encode()))

def upload_to_s3(local_path: str, bucket: str, key: str):
    s3 = s3_client()
    s3.upload_file(local_path, bucket, key)
    scheme = 'https' if MINIO_SECURE else 'http'
    return f"{scheme}://{MINIO_ENDPOINT}/{bucket}/{key}"

@app.post("/yt/download")
def yt_download(body: Dict[str,Any] = Body(...)):
    url = body.get('url'); ns = body.get('namespace') or DEFAULT_NAMESPACE
    bucket = body.get('bucket') or DEFAULT_BUCKET
    if not url: raise HTTPException(400, 'url required')
    tmpd = tempfile.mkdtemp(prefix='yt-')
    outtmpl = os.path.join(tmpd, '%(title)s.%(ext)s')
    ydl_opts = {
        'outtmpl': outtmpl,
        'format': body.get('format') or 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': True,
        'noprogress': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Determine output file
            if 'requested_downloads' in info and info['requested_downloads']:
                outpath = info['requested_downloads'][0]['_filename']
            else:
                outpath = ydl.prepare_filename(info)
            title = info.get('title') or os.path.basename(outpath)
            key = f"yt/{title}"
            s3_url = upload_to_s3(outpath, bucket, key)
            # Publish Studio record
            try:
                row = {
                    'title': title,
                    'namespace': ns,
                    'content_url': s3_url,
                    'status': 'submitted',
                    'meta': {'source': 'youtube', 'original_url': url}
                }
                requests.post(f"{SUPA}/studio_board", headers={'content-type':'application/json'}, data=json.dumps(row), timeout=20)
            except Exception:
                pass
            # Emit ingest/file-added event (if contracts present)
            try:
                _publish_event('ingest.file-added.v1', {'bucket': bucket, 'key': key, 'namespace': ns, 'title': title, 'source': 'youtube'})
            except Exception:
                pass
            return {'ok': True, 'title': title, 's3_url': s3_url}
    except Exception as e:
        raise HTTPException(500, f"yt-dlp error: {e}")
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

