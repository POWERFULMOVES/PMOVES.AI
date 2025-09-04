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
FFW_URL = os.environ.get("FFW_URL","http://ffmpeg-whisper:8078")

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

def base_prefix(video_id: str):
    return f"yt/{video_id}"

def supa_insert(table: str, row: Dict[str,Any]):
    try:
        r = requests.post(f"{SUPA}/{table}", headers={'content-type':'application/json'}, data=json.dumps(row), timeout=20)
        r.raise_for_status(); return r.json()
    except Exception:
        return None

@app.post("/yt/info")
def yt_info(body: Dict[str,Any] = Body(...)):
    url = body.get('url')
    if not url: raise HTTPException(400, 'url required')
    ydl_opts = { 'quiet': True, 'noprogress': True, 'skip_download': True }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        wanted = {k: info.get(k) for k in ('id','title','uploader','duration','webpage_url')}
        return {'ok': True, 'info': wanted}

@app.post("/yt/download")
def yt_download(body: Dict[str,Any] = Body(...)):
    url = body.get('url'); ns = body.get('namespace') or DEFAULT_NAMESPACE
    bucket = body.get('bucket') or DEFAULT_BUCKET
    if not url: raise HTTPException(400, 'url required')
    tmpd = tempfile.mkdtemp(prefix='yt-')
    outtmpl = os.path.join(tmpd, '%(id)s.%(ext)s')
    ydl_opts = {
        'outtmpl': outtmpl,
        'format': body.get('format') or 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'writethumbnail': True,
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
            vid = info.get('id') or os.path.splitext(os.path.basename(outpath))[0]
            title = info.get('title') or vid
            base = base_prefix(vid)
            # Upload raw video
            raw_key = f"{base}/raw.mp4"
            s3_url = upload_to_s3(outpath, bucket, raw_key)
            # Upload thumbnail if present
            thumb = None
            for ext in ('.jpg','.png','.webp'):
                cand = os.path.join(tmpd, f"{vid}{ext}")
                if os.path.exists(cand):
                    thumb_key = f"{base}/thumb{ext}"
                    thumb = upload_to_s3(cand, bucket, thumb_key)
                    break
            # Publish Studio record
            supa_insert('studio_board', {
                'title': title,
                'namespace': ns,
                'content_url': s3_url,
                'status': 'submitted',
                'meta': {'source': 'youtube', 'original_url': url, 'thumb': thumb}
            })
            supa_insert('videos', {
                'video_id': vid,
                'namespace': ns,
                'title': title,
                'source_url': url,
                's3_base_prefix': f"s3://{bucket}/{base}",
                'meta': {'thumb': thumb}
            })
            # Emit ingest/file-added event (if contracts present)
            try:
                _publish_event('ingest.file.added.v1', {'bucket': bucket, 'key': raw_key, 'namespace': ns, 'title': title, 'source': 'youtube', 'video_id': vid})
            except Exception:
                pass
            return {'ok': True, 'title': title, 'video_id': vid, 's3_url': s3_url, 'thumb': thumb}
    except Exception as e:
        raise HTTPException(500, f"yt-dlp error: {e}")
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

@app.post("/yt/transcript")
def yt_transcript(body: Dict[str,Any] = Body(...)):
    vid = body.get('video_id'); bucket = body.get('bucket') or DEFAULT_BUCKET
    if not vid: raise HTTPException(400, 'video_id required')
    ns = body.get('namespace') or DEFAULT_NAMESPACE
    audio_key = f"{base_prefix(vid)}/audio.m4a"
    # If audio not present, try to extract from raw.mp4 using ffmpeg-whisper
    payload = {
        'bucket': bucket,
        'key': f"{base_prefix(vid)}/raw.mp4",
        'namespace': ns,
        'out_audio_key': audio_key,
        'language': body.get('language'),
        'whisper_model': body.get('whisper_model')
    }
    try:
        r = requests.post(f"{FFW_URL}/transcribe", headers={'content-type':'application/json'}, data=json.dumps(payload), timeout=600)
        j = r.json() if r.headers.get('content-type','').startswith('application/json') else {}
        if not r.ok:
            raise HTTPException(r.status_code, f"ffmpeg-whisper error: {j}")
        # Insert transcript row and emit event handled by worker
        supa_insert('transcripts', {
            'video_id': vid,
            'language': j.get('language') or body.get('language') or 'auto',
            'text': j.get('text') or '',
            's3_uri': j.get('s3_uri')
        })
        try:
            _publish_event('ingest.transcript.ready.v1', {'video_id': vid, 'namespace': ns, 'bucket': bucket, 'key': audio_key})
        except Exception:
            pass
        return {'ok': True, **j}
    except requests.RequestException as e:
        raise HTTPException(502, f"ffmpeg-whisper unreachable: {e}")

@app.post("/yt/ingest")
def yt_ingest(body: Dict[str,Any] = Body(...)):
    # Convenience orchestration: info + download + transcript
    url = body.get('url'); ns = body.get('namespace') or DEFAULT_NAMESPACE
    if not url: raise HTTPException(400, 'url required')
    dl = yt_download({'url': url, 'namespace': ns, 'bucket': body.get('bucket') or DEFAULT_BUCKET})
    tr = yt_transcript({'video_id': dl['video_id'], 'namespace': ns, 'bucket': body.get('bucket') or DEFAULT_BUCKET, 'language': body.get('language'), 'whisper_model': body.get('whisper_model')})
    return {'ok': True, 'video': dl, 'transcript': tr}
