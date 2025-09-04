import os, io, json, tempfile, shutil
from typing import Dict, Any
from fastapi import FastAPI, Body, HTTPException
import boto3
import soundfile as sf
import numpy as np

from transformers import pipeline

EMOTION_MODEL = os.environ.get('EMOTION_MODEL','superb/hubert-large-superb-er')

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"
MINIO_SECURE = (os.environ.get("MINIO_SECURE","false").lower() == "true")

app = FastAPI(title='Media-Audio', version='1.0.0')

def s3_client():
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client("s3", aws_access_key_id=MINIO_ACCESS_KEY, aws_secret_access_key=MINIO_SECRET_KEY, endpoint_url=endpoint_url)

@app.get('/healthz')
def healthz():
    return {'ok': True}

def load_emotion():
    try:
        return pipeline('audio-classification', model=EMOTION_MODEL)
    except Exception:
        return None

@app.post('/emotion')
def emotion(body: Dict[str,Any] = Body(...)):
    bucket = body.get('bucket'); key = body.get('key'); vid = body.get('video_id')
    if not bucket or not key:
        raise HTTPException(400, 'bucket and key required')
    tmpd = tempfile.mkdtemp(prefix='ma-')
    s3 = s3_client()
    try:
        src = os.path.join(tmpd, 'audio.m4a')
        with open(src, 'wb') as w:
            s3.download_fileobj(bucket, key, w)
        emo = load_emotion()
        if emo is None:
            raise HTTPException(501, 'Emotion model not available')
        # Read entire audio and sample a few windows
        data, sr = sf.read(src)
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        dur = len(data)/sr
        wins = max(1, int(dur // 5))
        out = []
        for i in range(wins):
            start = int(i*5*sr); end = int(min((i+1)*5*sr, len(data)))
            segment = data[start:end]
            # transformers pipelines accept file path or array with sampling_rate
            res = emo({'array': segment, 'sampling_rate': sr})
            if res:
                top = res[0]
                out.append({'video_id': vid, 'ts_seconds': i*5, 'label': top['label'], 'score': float(top['score'])})
        return {'ok': True, 'count': len(out), 'emotions': out}
    except Exception as e:
        raise HTTPException(500, f'emotion error: {e}')
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

