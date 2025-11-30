import os
import tempfile
import shutil
import subprocess
import asyncio
import logging
from typing import Dict, Any, List, Optional

import boto3
from fastapi import FastAPI, Body, HTTPException
from PIL import Image
import torch

from services.common.supabase import insert_detections, insert_segments, insert_emotions
from services.common.events import publish

YOLO_MODEL = os.environ.get('YOLO_MODEL', 'yolov8n.pt')
FRAME_EVERY = int(os.environ.get('FRAME_EVERY', '5'))  # seconds
SCORE_THRES = float(os.environ.get('SCORE_THRES', '0.25'))

SCENE_MODEL = os.environ.get('SCENE_MODEL', 'dima806/scene_classification_vit')
CAPTION_MODEL = os.environ.get('CAPTION_MODEL', 'Salesforce/blip-image-captioning-base')
MOOD_MODEL = os.environ.get('MOOD_MODEL', 'distilbert-base-uncased-finetuned-sst-2-english')
VIDEO_REASONER_MODEL = os.environ.get('VIDEO_REASONER_MODEL', 'Salesforce/blip2-flan-t5-base')
REASONER_MAX_FRAMES = int(os.environ.get('VIDEO_REASONER_MAX_FRAMES', '4'))

MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT') or os.environ.get('S3_ENDPOINT') or 'minio:9000'
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY') or os.environ.get('AWS_ACCESS_KEY_ID') or 'minioadmin'
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY') or 'minioadmin'
MINIO_SECURE = os.environ.get('MINIO_SECURE', 'false').lower() == 'true'

FRAMES_BUCKET = os.environ.get('MEDIA_VIDEO_FRAMES_BUCKET')
FRAMES_PREFIX = os.environ.get('MEDIA_VIDEO_FRAMES_PREFIX', 'media-video/frames')

FRAME_BUCKET = os.environ.get('FRAME_BUCKET') or os.environ.get('FRAME_S3_BUCKET')


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title='Media-Video', version='1.1.0')


def torch_device_index() -> int:
    return 0 if torch.cuda.is_available() else -1


def torch_device() -> torch.device:
    return torch.device('cuda' if torch.cuda.is_available() else 'cpu')


_yolo_model = None
_scene_classifier = None
_scene_loaded = False
_caption_generator = None
_caption_loaded = False
_mood_classifier = None
_mood_loaded = False
_video_reasoner = None
_reasoner_loaded = False


def s3_client():
    endpoint_url = MINIO_ENDPOINT if '://' in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client(
        's3',
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        endpoint_url=endpoint_url,
    )


def s3_http_base() -> str:
    if MINIO_ENDPOINT.startswith('http://') or MINIO_ENDPOINT.startswith('https://'):
        base = MINIO_ENDPOINT
    else:
        base = f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return base.rstrip('/')


def frame_storage_path(source_bucket: str, video_id: Optional[str], source_key: str, frame_name: str) -> Dict[str, str]:
    base_name = video_id or os.path.splitext(os.path.basename(source_key))[0]
    prefix_parts = [FRAMES_PREFIX.strip('/') if FRAMES_PREFIX else None, base_name, frame_name]
    key = '/'.join([p for p in prefix_parts if p])
    bucket = FRAMES_BUCKET or source_bucket
    return {'bucket': bucket, 'key': key}


@app.get('/healthz')
def healthz():
    return {'ok': True}


def ffmpeg_frames(src: str, outdir: str, every_sec: int) -> None:
    cmd = ['ffmpeg', '-y', '-i', src, '-vf', f'fps=1/{every_sec}', os.path.join(outdir, 'frame_%06d.jpg')]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def load_yolo():
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model
    try:
        from ultralytics import YOLO

        logger.info('Loading YOLO model %s', YOLO_MODEL)
        _yolo_model = YOLO(YOLO_MODEL)
    except Exception as exc:
        logger.error('Failed to load YOLO model: %s', exc)
        _yolo_model = None
    return _yolo_model


def load_scene_classifier():
    global _scene_classifier, _scene_loaded
    if _scene_loaded:
        return _scene_classifier
    _scene_loaded = True
    try:
        from transformers import pipeline

        logger.info('Loading scene classifier %s', SCENE_MODEL)
        _scene_classifier = pipeline(
            'image-classification',
            model=SCENE_MODEL,
            device=torch_device_index(),
        )
    except Exception as exc:
        logger.error('Failed to load scene classifier: %s', exc)
        _scene_classifier = None
    return _scene_classifier


def load_caption_generator():
    global _caption_generator, _caption_loaded
    if _caption_loaded:
        return _caption_generator
    _caption_loaded = True
    try:
        from transformers import pipeline

        logger.info('Loading caption generator %s', CAPTION_MODEL)
        _caption_generator = pipeline(
            'image-to-text',
            model=CAPTION_MODEL,
            device=torch_device_index(),
        )
    except Exception as exc:
        logger.error('Failed to load caption generator: %s', exc)
        _caption_generator = None
    return _caption_generator


def load_mood_classifier():
    global _mood_classifier, _mood_loaded
    if _mood_loaded:
        return _mood_classifier
    _mood_loaded = True
    try:
        from transformers import pipeline

        logger.info('Loading mood classifier %s', MOOD_MODEL)
        _mood_classifier = pipeline(
            'text-classification',
            model=MOOD_MODEL,
            device=torch_device_index(),
        )
    except Exception as exc:
        logger.error('Failed to load mood classifier: %s', exc)
        _mood_classifier = None
    return _mood_classifier


class VideoLanguageReasoner:
    def __init__(self, model_id: str):
        from transformers import AutoProcessor, Blip2ForConditionalGeneration

        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.device = torch_device()
        logger.info('Loading video-language reasoner %s', model_id)
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = Blip2ForConditionalGeneration.from_pretrained(
            model_id,
            torch_dtype=dtype,
        )
        self.model.to(self.device)

    def summarize(self, images: List[Image.Image], context: Optional[str] = None) -> Dict[str, Any]:
        if not images:
            return {}
        prompt = context or (
            'Provide a concise description of the events happening in these video frames, '
            'highlighting key objects, actions, and the emotional atmosphere.'
        )
        inputs = self.processor(
            images=images,
            text=prompt,
            return_tensors='pt',
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        generated_ids = self.model.generate(**inputs, max_new_tokens=120)
        text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return {'prompt': prompt, 'response': text}


def load_video_reasoner():
    global _video_reasoner, _reasoner_loaded
    if _reasoner_loaded:
        return _video_reasoner
    _reasoner_loaded = True
    try:
        _video_reasoner = VideoLanguageReasoner(VIDEO_REASONER_MODEL)
    except Exception as exc:
        logger.error('Failed to load video reasoner: %s', exc)
        _video_reasoner = None
    return _video_reasoner


def normalize_predictions(items: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    if not items:
        return normalized
    for item in items:
        label = item.get('label') if isinstance(item, dict) else getattr(item, 'label', None)
        score = item.get('score') if isinstance(item, dict) else getattr(item, 'score', None)
        if label is None:
            continue
        try:
            score_val = float(score) if score is not None else None
        except Exception:
            score_val = None
        normalized.append({'label': label, 'score': score_val})
    return normalized


def normalize_caption(items: Any) -> List[str]:
    captions: List[str] = []
    if not items:
        return captions
    for item in items:
        text = item.get('generated_text') if isinstance(item, dict) else getattr(item, 'generated_text', None)
        if text:
            captions.append(text.strip())
    return captions


def normalize_mood(items: Any) -> Optional[Dict[str, Any]]:
    if not items:
        return None
    item = items[0]
    if isinstance(item, dict):
        label = item.get('label')
        score = item.get('score')
    else:
        label = getattr(item, 'label', None)
        score = getattr(item, 'score', None)
    if not label:
        return None
    try:
        score_val = float(score) if score is not None else None
    except Exception:
        score_val = None
    return {'label': label, 'score': score_val}


@app.post('/detect')
def detect(body: Dict[str, Any] = Body(...)):
    bucket = body.get('bucket')
    key = body.get('key')
    ns = body.get('namespace') or 'pmoves'
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
        frames_dir = os.path.join(tmpd, 'frames')
        os.makedirs(frames_dir, exist_ok=True)
        ffmpeg_frames(src, frames_dir, FRAME_EVERY)
        yolo = load_yolo()
        if yolo is None:
            raise HTTPException(501, 'YOLO model not available')

        scene_classifier = load_scene_classifier()
        caption_generator = load_caption_generator()
        mood_classifier = load_mood_classifier()
        video_reasoner_model = load_video_reasoner()

        detections: List[Dict[str, Any]] = []
        captions: List[Dict[str, Any]] = []
        scenes: List[Dict[str, Any]] = []
        moods: List[Dict[str, Any]] = []
        reasoner_frames: List[Dict[str, Any]] = []

        base_url = s3_http_base()

        base_key = os.path.splitext(os.path.basename(key))[0] or 'video'
        frame_prefix_parts = ['frames', ns]
        if vid:
            frame_prefix_parts.append(str(vid))
        else:
            frame_prefix_parts.append(base_key)
        frame_prefix = '/'.join(part.strip('/') for part in frame_prefix_parts if part)

        for idx, fname in enumerate(sorted(os.listdir(frames_dir))):
            if not fname.endswith('.jpg'):
                continue
            fpath = os.path.join(frames_dir, fname)

            storage = frame_storage_path(bucket, vid, key, fname)
            s3.upload_file(fpath, storage['bucket'], storage['key'])
            frame_http_uri = f"{base_url}/{storage['bucket']}/{storage['key']}"

            frame_key = f"{frame_prefix}/{fname}"
            try:
                s3.upload_file(fpath, frame_bucket, frame_key)
            except Exception as exc:
                raise HTTPException(500, f'frame upload error: {exc}')
            frame_uri = f"s3://{frame_bucket}/{frame_key}"

            res = yolo(fpath, verbose=False)
            ts_seconds = idx * FRAME_EVERY

            with Image.open(fpath) as raw_img:
                image = raw_img.convert('RGB')

            scene_predictions = normalize_predictions(scene_classifier(image) if scene_classifier else [])
            caption_texts = normalize_caption(caption_generator(image) if caption_generator else [])
            caption_text = caption_texts[0] if caption_texts else None
            mood_info = normalize_mood(
                mood_classifier(caption_text) if (caption_text and mood_classifier) else None
            )

            if scene_predictions:
                top_scene = scene_predictions[0]
                scenes.append(
                    {
                        'video_id': vid,
                        'label': top_scene.get('label'),
                        'score': top_scene.get('score'),
                        'ts_start': max(ts_seconds - FRAME_EVERY / 2, 0.0),
                        'ts_end': ts_seconds + FRAME_EVERY / 2,
                        'frame_uri': frame_uri,
                        'alternatives': scene_predictions,
                    }
                )
            if caption_text:
                captions.append(
                    {
                        'video_id': vid,
                        'ts_seconds': ts_seconds,
                        'frame_uri': frame_uri,
                        'text': caption_text,
                        'alternatives': caption_texts,
                    }
                )
            if mood_info:
                moods.append(
                    {
                        'video_id': vid,
                        'ts_seconds': ts_seconds,
                        'frame_uri': frame_uri,
                        'label': mood_info.get('label'),
                        'score': mood_info.get('score'),
                        'caption': caption_text,
                    }
                )

            reasoner_frames.append(
                {
                    'image': image,
                    'ts_seconds': ts_seconds,
                    'frame_uri': frame_uri,
                    'http_uri': frame_http_uri,
                }
            )

            for r in res:
                for b in r.boxes:
                    cls = int(b.cls.item())
                    score = float(b.conf.item())
                    if score < SCORE_THRES:
                        continue
                    label = r.names.get(cls) or str(cls)
                    detections.append(
                        {
                            'video_id': vid,
                            'label': label,
                            'score': score,
                            'ts_seconds': ts_seconds,
                            'frame': fname,
                            'frame_uri': frame_uri,
                            'scene': scene_predictions[0] if scene_predictions else None,
                            'caption': caption_text,
                            'mood': mood_info,
                        }
                    )

        reasoning: Optional[Dict[str, Any]] = None
        if video_reasoner_model and reasoner_frames:
            if len(reasoner_frames) > REASONER_MAX_FRAMES:
                step = max(len(reasoner_frames) // REASONER_MAX_FRAMES, 1)
                sample = reasoner_frames[::step][:REASONER_MAX_FRAMES]
            else:
                sample = reasoner_frames
            reasoning = video_reasoner_model.summarize(
                [item['image'] for item in sample],
                context=body.get('question') or body.get('prompt'),
            )
            if reasoning:
                reasoning['samples'] = [
                    {
                        'ts_seconds': item['ts_seconds'],
                        'frame_uri': item['frame_uri'],
                        'http_uri': item.get('http_uri'),
                    }
                    for item in sample
                ]

        for item in reasoner_frames:
            item.pop('image', None)

        rows = [
            {
                'namespace': ns,
                'video_id': d.get('video_id'),
                'ts_seconds': d.get('ts_seconds'),
                'label': d.get('label'),
                'score': d.get('score'),
                'frame_uri': d.get('frame_uri'),
                'meta': {
                    'frame': d.get('frame'),
                    'scene': d.get('scene'),
                    'caption': d.get('caption'),
                    'mood': d.get('mood'),
                },
            }
            for d in detections
        ]
        if rows:
            insert_detections(rows)

        scene_rows = [
            {
                'namespace': ns,
                'video_id': s.get('video_id'),
                'label': s.get('label'),
                'score': s.get('score'),
                'ts_start': s.get('ts_start'),
                'ts_end': s.get('ts_end'),
                'uri': s.get('frame_uri'),
                'meta': {'alternatives': s.get('alternatives')},
            }
            for s in scenes
            if s.get('label')
        ]
        if scene_rows:
            insert_segments(scene_rows)

        emotion_rows = [
            {
                'namespace': ns,
                'video_id': m.get('video_id'),
                'ts_seconds': m.get('ts_seconds'),
                'label': m.get('label'),
                'score': m.get('score'),
                'frame_uri': m.get('frame_uri'),
                'meta': {'caption': m.get('caption')},
            }
            for m in moods
            if m.get('label')
        ]
        if emotion_rows:
            insert_emotions(emotion_rows)

        payload = {
            'video_id': vid,
            'namespace': ns,
            'detections': detections,
            'scenes': scenes,
            'captions': captions,
            'moods': moods,
            'reasoning': reasoning,
        }
        env = asyncio.run(publish('analysis.entities.v1', payload, source='media-video'))
        return {
            'ok': True,
            'count': len(detections),
            'detections': detections,
            'scenes': scenes,
            'captions': captions,
            'moods': moods,
            'reasoning': reasoning,
            'event': env,
        }
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, f'ffmpeg error: {exc}')
    except Exception as exc:
        raise HTTPException(500, f'detect error: {exc}')
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
