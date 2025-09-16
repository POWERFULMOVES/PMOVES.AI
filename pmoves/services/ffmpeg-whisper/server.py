import os, json, tempfile, shutil, subprocess
from typing import Dict, Any
from fastapi import FastAPI, Body, HTTPException
import boto3
from faster_whisper import WhisperModel
import shutil as _shutil

from services.common.supabase import insert_segments

app = FastAPI(title="FFmpeg+Whisper (faster-whisper)", version="2.0.0")

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

def _select_device() -> str:
    # Prefer CUDA if available; allow override via WHISPER_DEVICE / USE_CUDA
    dev = os.environ.get("WHISPER_DEVICE")
    if dev:
        return dev
    if os.environ.get("USE_CUDA","false").lower() == "true":
        return "cuda"
    if _shutil.which("nvidia-smi"):
        return "cuda"
    return "cpu"

@app.post('/transcribe')
def transcribe(body: Dict[str,Any] = Body(...)):
    bucket = body.get('bucket'); key = body.get('key'); vid = body.get('video_id')
    if not bucket or not key:
        raise HTTPException(400, 'bucket and key required')
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
        # faster-whisper (ctranslate2). Uses CUDA if available.
        device = _select_device()
        compute_type = 'float16' if device == 'cuda' else 'int8'
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        segments_iter, info = model.transcribe(audio_path, language=lang)
        segs = []
        text_parts = []
        for seg in segments_iter:
            try:
                segs.append({
                    'start': float(getattr(seg, 'start', 0.0) or 0.0),
                    'end': float(getattr(seg, 'end', 0.0) or 0.0),
                    'text': (getattr(seg, 'text', '') or '').strip()
                })
                text_parts.append((getattr(seg, 'text', '') or ''))
            except Exception:
                continue
        text = ''.join(text_parts)
        rows = [
            {
                'video_id': vid,
                'ts_start': s['start'],
                'ts_end': s['end'],
                'uri': s3_uri,
                'meta': {'text': s['text']}
            }
            for s in segs
        ]
        insert_segments(rows)
        return {'ok': True, 'text': text, 'segments': segs, 'language': getattr(info, 'language', None) or lang, 's3_uri': s3_uri, 'device': device}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"ffmpeg error: {e}")
    except Exception as e:
        raise HTTPException(500, f"transcribe error: {e}")
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
