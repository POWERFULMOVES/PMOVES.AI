import os, json, tempfile, shutil, subprocess
from typing import Dict, Any
from fastapi import FastAPI, Body, HTTPException
import boto3
import whisper

app = FastAPI(title="FFmpeg+Whisper", version="1.0.0")

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"
MINIO_SECURE = (os.environ.get("MINIO_SECURE","false").lower() == "true")

def s3_client():
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client("s3", aws_access_key_id=MINIO_ACCESS_KEY, aws_secret_access_key=MINIO_SECRET_KEY, endpoint_url=endpoint_url)

@app.get('/healthz')
def healthz():
    return {'ok': True}

def ffmpeg_extract_audio(src: str, dst: str):
    # Example: convert to m4a AAC
    cmd = ['ffmpeg','-y','-i', src,'-vn','-acodec','aac','-b:a','128k', dst]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@app.post('/transcribe')
def transcribe(body: Dict[str,Any] = Body(...)):
    bucket = body.get('bucket'); key = body.get('key')
    if not bucket or not key: raise HTTPException(400, 'bucket and key required')
    lang = body.get('language'); model_name = body.get('whisper_model') or 'base'
    out_audio_key = body.get('out_audio_key')
    tmpd = tempfile.mkdtemp(prefix='ffw-')
    s3 = s3_client()
    try:
        # fetch source
        src_path = os.path.join(tmpd, 'raw.mp4')
        with open(src_path, 'wb') as w:
            s3.download_fileobj(bucket, key, w)
        # extract audio
        audio_path = os.path.join(tmpd, 'audio.m4a')
        ffmpeg_extract_audio(src_path, audio_path)
        # upload audio if requested
        s3_uri = None
        if out_audio_key:
            s3.upload_file(audio_path, bucket, out_audio_key)
            scheme = 'https' if MINIO_SECURE else 'http'
            s3_uri = f"{scheme}://{MINIO_ENDPOINT}/{bucket}/{out_audio_key}"
        # whisper
        model = whisper.load_model(model_name)
        res = model.transcribe(audio_path, language=lang)
        text = res.get('text') or ''
        return {'ok': True, 'text': text, 'language': res.get('language') or lang, 's3_uri': s3_uri}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"ffmpeg error: {e}")
    except Exception as e:
        raise HTTPException(500, f"transcribe error: {e}")
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

