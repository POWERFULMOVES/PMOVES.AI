import os, io, json, tempfile, shutil, subprocess
from typing import Dict, Any
from fastapi import FastAPI, Body, HTTPException
import boto3
from PIL import Image

YOLO_MODEL = os.environ.get('YOLO_MODEL','yolov8n.pt')
FRAME_EVERY = int(os.environ.get('FRAME_EVERY','5'))  # seconds
SCORE_THRES = float(os.environ.get('SCORE_THRES','0.25'))

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"
MINIO_SECURE = (os.environ.get("MINIO_SECURE","false").lower() == "true")

app = FastAPI(title='Media-Video', version='1.0.0')

def s3_client():
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client("s3", aws_access_key_id=MINIO_ACCESS_KEY, aws_secret_access_key=MINIO_SECRET_KEY, endpoint_url=endpoint_url)

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
        for fname in sorted(os.listdir(frames_dir)):
            if not fname.endswith('.jpg'): continue
            fpath = os.path.join(frames_dir, fname)
            res = yolo(fpath, verbose=False)
            for r in res:
                for b in r.boxes:
                    cls = int(b.cls.item())
                    score = float(b.conf.item())
                    if score < SCORE_THRES: continue
                    label = r.names.get(cls) or str(cls)
                    ts = None  # could derive from frame index * every_sec
                    detections.append({'video_id': vid, 'label': label, 'score': score, 'ts_seconds': ts, 'frame': fname})
        return {'ok': True, 'count': len(detections), 'detections': detections}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f'ffmpeg error: {e}')
    except Exception as e:
        raise HTTPException(500, f'detect error: {e}')
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

