import os, io, json, tempfile, shutil, subprocess, asyncio
from typing import Dict, Any
from fastapi import FastAPI, Body, HTTPException
import boto3
from PIL import Image

from services.common.supabase import insert_detections
from services.common.events import publish

YOLO_MODEL = os.environ.get('YOLO_MODEL','yolov8n.pt')
FRAME_EVERY = int(os.environ.get('FRAME_EVERY','5'))  # seconds
SCORE_THRES = float(os.environ.get('SCORE_THRES','0.25'))

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"
MINIO_SECURE = (os.environ.get("MINIO_SECURE","false").lower() == "true")

FRAMES_BUCKET = os.environ.get("MEDIA_VIDEO_FRAMES_BUCKET")
FRAMES_PREFIX = os.environ.get("MEDIA_VIDEO_FRAMES_PREFIX", "media-video/frames")

FRAME_BUCKET = os.environ.get("FRAME_BUCKET") or os.environ.get("FRAME_S3_BUCKET")


app = FastAPI(title='Media-Video', version='1.0.0')

def s3_client():
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client("s3", aws_access_key_id=MINIO_ACCESS_KEY, aws_secret_access_key=MINIO_SECRET_KEY, endpoint_url=endpoint_url)

def s3_http_base() -> str:
    if MINIO_ENDPOINT.startswith("http://") or MINIO_ENDPOINT.startswith("https://"):
        base = MINIO_ENDPOINT
    else:
        base = f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return base.rstrip('/')

def frame_storage_path(source_bucket: str, video_id: str | None, source_key: str, frame_name: str) -> Dict[str, str]:
    base_name = video_id or os.path.splitext(os.path.basename(source_key))[0]
    prefix_parts = [FRAMES_PREFIX.strip("/") if FRAMES_PREFIX else None, base_name, frame_name]
    key = "/".join([p for p in prefix_parts if p])
    bucket = FRAMES_BUCKET or source_bucket
    return {"bucket": bucket, "key": key}

@app.get('/healthz')
def healthz():
    return {'ok': True}

def ffmpeg_frames(src: str, outdir: str, every_sec: int):
    # Extract frames every N seconds
    # ffmpeg -i src -vf fps=1/every_sec outdir/frame_%06d.jpg
    cmd = ['ffmpeg','-y','-i',src,'-vf',f'fps=1/{every_sec}', os.path.join(outdir, 'frame_%06d.jpg')]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def load_yolo():
    try:
        from ultralytics import YOLO
        return YOLO(YOLO_MODEL)
    except Exception as e:
        return None

@app.post('/detect')
def detect(body: Dict[str,Any] = Body(...)):
    bucket = body.get('bucket'); key = body.get('key'); ns = body.get('namespace') or 'pmoves'
    vid = body.get('video_id')
    if not bucket or not key:
        raise HTTPException(400, 'bucket and key required')
    tmpd = tempfile.mkdtemp(prefix='mv-')
    s3 = s3_client()
    frame_bucket = FRAME_BUCKET or bucket
    if not frame_bucket:
        raise HTTPException(500, 'frame bucket not configured')
    try:
        src = os.path.join(tmpd, 'raw.mp4')
        with open(src, 'wb') as w:
            s3.download_fileobj(bucket, key, w)
        frames_dir = os.path.join(tmpd, 'frames'); os.makedirs(frames_dir, exist_ok=True)
        ffmpeg_frames(src, frames_dir, FRAME_EVERY)
        yolo = load_yolo()
        if yolo is None:
            raise HTTPException(501, 'YOLO model not available')
        detections = []

        base_url = s3_http_base()

        base_key = os.path.splitext(os.path.basename(key))[0] or 'video'
        frame_prefix_parts = ['frames', ns]
        if vid:
            frame_prefix_parts.append(str(vid))
        else:
            frame_prefix_parts.append(base_key)
        frame_prefix = '/'.join(part.strip('/') for part in frame_prefix_parts if part)

        for fname in sorted(os.listdir(frames_dir)):
            if not fname.endswith('.jpg'):
                continue
            fpath = os.path.join(frames_dir, fname)

            storage = frame_storage_path(bucket, vid, key, fname)
            s3.upload_file(fpath, storage['bucket'], storage['key'])
            frame_uri = f"{base_url}/{storage['bucket']}/{storage['key']}"

            frame_key = f"{frame_prefix}/{fname}"
            try:
                s3.upload_file(fpath, frame_bucket, frame_key)
            except Exception as exc:
                raise HTTPException(500, f'frame upload error: {exc}')
            frame_uri = f"s3://{frame_bucket}/{frame_key}"

            res = yolo(fpath, verbose=False)
            for r in res:
                for b in r.boxes:
                    cls = int(b.cls.item())
                    score = float(b.conf.item())
                    if score < SCORE_THRES:
                        continue
                    label = r.names.get(cls) or str(cls)
                    ts = None  # could derive from frame index * every_sec
                    detections.append({
                        'video_id': vid,
                        'label': label,
                        'score': score,
                        'ts_seconds': ts,
                        'frame': fname,
                        'frame_uri': frame_uri
                    })
        # Persist
        rows = [
            {
                'video_id': d.get('video_id'),
                'ts_seconds': d.get('ts_seconds'),
                'label': d.get('label'),
                'score': d.get('score'),

                'frame_uri': d.get('frame_uri') or d.get('frame')

                'frame_uri': d.get('frame_uri')

            }
            for d in detections
        ]
        insert_detections(rows)
        payload = {'video_id': vid, 'namespace': ns, 'detections': detections}
        env = asyncio.run(publish('analysis.entities.v1', payload, source='media-video'))
        return {'ok': True, 'count': len(detections), 'detections': detections, 'event': env}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f'ffmpeg error: {e}')
    except Exception as e:
        raise HTTPException(500, f'detect error: {e}')
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

