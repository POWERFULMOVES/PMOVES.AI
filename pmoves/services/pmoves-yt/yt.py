import os, json, tempfile, shutil, asyncio, time, re, math, uuid
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Body, HTTPException
import yt_dlp
import boto3
import requests
from nats.aio.client import Client as NATS
# Prefer shared envelope util if present; otherwise, fall back to a local stub
try:
    from services.common.events import envelope  # type: ignore
except Exception:
    import uuid, datetime
    def envelope(topic: str, payload: dict, correlation_id: str|None=None, parent_id: str|None=None, source: str="pmoves-yt"):
        # Minimal schema-free envelope for environments where shared modules aren’t available
        env = {
            "id": str(uuid.uuid4()),
            "topic": topic,
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "version": "v1",
            "source": source,
            "payload": payload,
        }
        if correlation_id: env["correlation_id"] = correlation_id
        if parent_id: env["parent_id"] = parent_id
        return env

try:
    from services.common.geometry_params import get_builder_pack, clear_cache  # type: ignore
except Exception:  # pragma: no cover - fallback when module unavailable
    def get_builder_pack(namespace: str, modality: str):
        return None

    def clear_cache() -> None:
        return None

app = FastAPI(title="PMOVES.YT", version="1.0.0")

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"
MINIO_SECURE = (os.environ.get("MINIO_SECURE","false").lower() == "true")
DEFAULT_BUCKET = os.environ.get("YT_BUCKET","assets")
DEFAULT_NAMESPACE = os.environ.get("INDEXER_NAMESPACE","pmoves")
SUPA = os.environ.get("SUPA_REST_URL","http://postgrest:3000")
SUPA_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
)
NATS_URL = (os.environ.get("NATS_URL") or "").strip()
YT_NATS_ENABLE = os.environ.get("YT_NATS_ENABLE", "false").lower() == "true"
FFW_URL = os.environ.get("FFW_URL","http://ffmpeg-whisper:8078")
HIRAG_URL = os.environ.get("HIRAG_URL","http://hi-rag-gateway-v2:8086")

# Summarization (Gemma) configuration
YT_SUMMARY_PROVIDER = os.environ.get("YT_SUMMARY_PROVIDER", "ollama")  # ollama|hf
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
YT_GEMMA_MODEL = os.environ.get("YT_GEMMA_MODEL", "gemma2:9b-instruct")
HF_GEMMA_MODEL = os.environ.get("HF_GEMMA_MODEL", "google/gemma-2-9b-it")
HF_USE_GPU = os.environ.get("HF_USE_GPU", "false").lower() == "true"
HF_TOKEN = os.environ.get("HF_TOKEN")

# Playlist/Channel defaults
YT_PLAYLIST_MAX = int(os.environ.get("YT_PLAYLIST_MAX", "50"))
YT_CONCURRENCY = int(os.environ.get("YT_CONCURRENCY", "2"))
YT_RATE_LIMIT = float(os.environ.get("YT_RATE_LIMIT", "0.0"))  # seconds between downloads

# Segmentation thresholds (smart boundaries)
YT_SEG_TARGET_DUR = float(os.environ.get("YT_SEG_TARGET_DUR", "30.0"))
YT_SEG_GAP_THRESH = float(os.environ.get("YT_SEG_GAP_THRESH", "1.2"))
YT_SEG_MIN_CHARS = int(os.environ.get("YT_SEG_MIN_CHARS", "600"))
YT_SEG_MAX_CHARS = int(os.environ.get("YT_SEG_MAX_CHARS", "1500"))
YT_SEG_MAX_DUR = float(os.environ.get("YT_SEG_MAX_DUR", "60.0"))

# Always include lexical indexing on upsert (can be disabled)
YT_INDEX_LEXICAL = os.environ.get("YT_INDEX_LEXICAL", "true").lower() == "true"

# Auto-tune segmentation thresholds based on content profile
YT_SEG_AUTOTUNE = os.environ.get("YT_SEG_AUTOTUNE", "true").lower() == "true"

DEFAULT_ANDROID_UA = "Mozilla/5.0 (Linux; Android 12; Pixel 5 Build/SP2A.220405.004; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.41 Mobile Safari/537.36"
YT_PLAYER_CLIENT = (os.environ.get("YT_PLAYER_CLIENT") or "android").strip()
YT_USER_AGENT = os.environ.get("YT_USER_AGENT") or DEFAULT_ANDROID_UA
YT_FORCE_IPV4 = os.environ.get("YT_FORCE_IPV4", "true").lower() == "true"
try:
    YT_EXTRACTOR_RETRIES = int(os.environ.get("YT_EXTRACTOR_RETRIES", "2"))
except ValueError:
    YT_EXTRACTOR_RETRIES = 2
YT_COOKIES = os.environ.get("YT_COOKIES")

_nc: Optional[NATS] = None

def _with_ytdlp_defaults(opts: Dict[str, Any]) -> Dict[str, Any]:
    """Add hardened defaults so youtube-dl works without manual cookies."""
    merged = dict(opts)
    extractor_args = dict(merged.get('extractor_args') or {})
    youtube_args = dict(extractor_args.get('youtube') or {})
    if YT_PLAYER_CLIENT:
        clients = list(youtube_args.get('player_client') or [])
        if YT_PLAYER_CLIENT not in clients:
            youtube_args['player_client'] = [YT_PLAYER_CLIENT] + clients
    if youtube_args:
        extractor_args['youtube'] = youtube_args
    if extractor_args:
        merged['extractor_args'] = extractor_args

    headers = dict(merged.get('http_headers') or {})
    if YT_USER_AGENT and not headers.get('User-Agent'):
        headers['User-Agent'] = YT_USER_AGENT
    if headers:
        merged['http_headers'] = headers

    if YT_COOKIES and not merged.get('cookiefile'):
        merged['cookiefile'] = YT_COOKIES
    if YT_FORCE_IPV4:
        merged['force_ipv4'] = True
    if YT_EXTRACTOR_RETRIES >= 0 and 'extractor_retries' not in merged:
        merged['extractor_retries'] = YT_EXTRACTOR_RETRIES
    return merged

def s3_client():
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client("s3", aws_access_key_id=MINIO_ACCESS_KEY, aws_secret_access_key=MINIO_SECRET_KEY, endpoint_url=endpoint_url)

@app.on_event("startup")
async def startup():
    # Non-blocking, quiet NATS init. Skip entirely unless explicitly enabled.
    global _nc
    if not YT_NATS_ENABLE or not NATS_URL:
        _nc = None
        return

    async def _try_connect():
        global _nc
        nc = NATS()
        try:
            # Short timeout, no reconnect storm
            await asyncio.wait_for(nc.connect(servers=[NATS_URL], allow_reconnect=False), timeout=1.0)
            _nc = nc
        except Exception:
            _nc = None

    # Fire and forget; errors are suppressed and won't block startup
    asyncio.create_task(_try_connect())

@app.get("/healthz")
def healthz():
    return {"ok": True}

def _publish_event(topic: str, payload: Dict[str,Any]):
    if _nc is None:
        return
    msg = envelope(topic, payload, source="pmoves-yt")
    asyncio.create_task(_nc.publish(topic, json.dumps(msg).encode()))

def upload_to_s3(local_path: str, bucket: str, key: str):
    s3 = s3_client()
    s3.upload_file(local_path, bucket, key)
    scheme = 'https' if MINIO_SECURE else 'http'
    return f"{scheme}://{MINIO_ENDPOINT}/{bucket}/{key}"

def base_prefix(video_id: str):
    return f"yt/{video_id}"

def supa_insert(table: str, row: Dict[str,Any]):
    try:
        headers = {'content-type': 'application/json'}
        if SUPA_SERVICE_KEY:
            headers.update({'apikey': SUPA_SERVICE_KEY, 'Authorization': f"Bearer {SUPA_SERVICE_KEY}"})
        r = requests.post(f"{SUPA}/{table}", headers=headers, data=json.dumps(row), timeout=20)
        r.raise_for_status(); return r.json()
    except Exception:
        return None

def supa_upsert(table: str, row: Dict[str,Any], on_conflict: Optional[str]=None):
    try:
        url = f"{SUPA}/{table}"
        if on_conflict:
            url += f"?on_conflict={on_conflict}"
        headers = {'content-type': 'application/json', 'prefer': 'resolution=merge-duplicates'}
        if SUPA_SERVICE_KEY:
            headers.update({'apikey': SUPA_SERVICE_KEY, 'Authorization': f"Bearer {SUPA_SERVICE_KEY}"})
        r = requests.post(url, headers=headers, data=json.dumps(row), timeout=20)
        r.raise_for_status(); return r.json()
    except Exception:
        return None

def supa_update(table: str, match: Dict[str,Any], patch: Dict[str,Any]):
    try:
        # Build a simple eq filter query string
        qs = []
        for k, v in match.items():
            if isinstance(v, str):
                qs.append(f"{k}=eq.{v}")
            else:
                qs.append(f"{k}=eq.{json.dumps(v)}")
        url = f"{SUPA}/{table}?" + "&".join(qs)
        headers = {'content-type': 'application/json'}
        if SUPA_SERVICE_KEY:
            headers.update({'apikey': SUPA_SERVICE_KEY, 'Authorization': f"Bearer {SUPA_SERVICE_KEY}"})
        r = requests.patch(url, headers=headers, data=json.dumps(patch), timeout=20)
        r.raise_for_status(); return r.json()
    except Exception:
        return None

def supa_get(table: str, match: Dict[str,Any]) -> Optional[List[Dict[str,Any]]]:
    try:
        qs = []
        for k, v in match.items():
            if isinstance(v, str):
                qs.append(f"{k}=eq.{v}")
            else:
                qs.append(f"{k}=eq.{json.dumps(v)}")
        url = f"{SUPA}/{table}?" + "&".join(qs)
        headers: Dict[str, str] = {}
        if SUPA_SERVICE_KEY:
            headers.update({'apikey': SUPA_SERVICE_KEY, 'Authorization': f"Bearer {SUPA_SERVICE_KEY}"})
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status(); return r.json()
    except Exception:
        return None

@app.post("/yt/info")
def yt_info(body: Dict[str,Any] = Body(...)):
    url = body.get('url')
    if not url: raise HTTPException(400, 'url required')
    ydl_opts = _with_ytdlp_defaults({'quiet': True, 'noprogress': True, 'skip_download': True})
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
    ydl_opts = _with_ytdlp_defaults({
        'outtmpl': outtmpl,
        'format': body.get('format') or 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'writethumbnail': True,
        'quiet': True,
        'noprogress': True,
    })
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
    if body.get('provider'):
        payload['provider'] = body['provider']
    try:
        r = requests.post(f"{FFW_URL}/transcribe", headers={'content-type':'application/json'}, data=json.dumps(payload), timeout=1200)
        j = r.json() if r.headers.get('content-type','').startswith('application/json') else {}
        if not r.ok:
            raise HTTPException(r.status_code, f"ffmpeg-whisper error: {j}")
        # Insert transcript row and emit event handled by worker
        supa_insert('transcripts', {
            'video_id': vid,
            'language': j.get('language') or body.get('language') or 'auto',
            'text': j.get('text') or '',
            's3_uri': j.get('s3_uri'),
            'meta': {'segments': j.get('segments')}
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
    tr_payload = {
        'video_id': dl['video_id'],
        'namespace': ns,
        'bucket': body.get('bucket') or DEFAULT_BUCKET,
        'language': body.get('language'),
        'whisper_model': body.get('whisper_model'),
    }
    if body.get('provider'):
        tr_payload['provider'] = body['provider']
    tr = yt_transcript(tr_payload)
    return {'ok': True, 'video': dl, 'transcript': tr}

# -------------------- Playlist / Channel ingestion --------------------

def _extract_entries(url: str) -> List[Dict[str,Any]]:
    ydl_opts = _with_ytdlp_defaults({'quiet': True, 'noprogress': True, 'skip_download': True, 'extract_flat': True})
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        entries = info.get('entries') or []
        out = []
        for e in entries:
            vid = e.get('id') or e.get('url')
            if not vid: continue
            out.append({'id': vid, 'title': e.get('title')})
        return out

def _job_create(job_type: str, args: Dict[str,Any]) -> Optional[str]:
    row = {'type': job_type, 'args': args, 'state': 'queued', 'started_at': None, 'finished_at': None, 'error': None}
    res = supa_insert('yt_jobs', row)
    if isinstance(res, list) and res:
        return res[0].get('id')
    if isinstance(res, dict):
        return res.get('id')
    return None

def _job_update(job_id: str, state: str, error: Optional[str]=None):
    patch = {'state': state, 'error': error}
    if state == 'running':
        patch['started_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    if state in ('completed','failed'):
        patch['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    supa_update('yt_jobs', {'id': job_id}, patch)

def _item_upsert(job_id: str, video_id: str, status: str, error: Optional[str]=None, meta: Optional[Dict[str,Any]]=None):
    row = {'job_id': job_id, 'video_id': video_id, 'status': status, 'error': error, 'retries': 0, 'meta': meta or {}}
    supa_upsert('yt_items', row, on_conflict='job_id,video_id')

def _ingest_one(video_url: str, ns: str, bucket: str) -> Dict[str,Any]:
    try:
        d = yt_download({'url': video_url, 'namespace': ns, 'bucket': bucket})
        vid = d.get('video_id')
        t = yt_transcript({'video_id': vid, 'namespace': ns, 'bucket': bucket})
        return {'ok': True, 'video_id': vid, 'download': d, 'transcript': t}
    except HTTPException as e:
        return {'ok': False, 'error': str(e.detail)}

@app.post('/yt/playlist')
async def yt_playlist(body: Dict[str,Any] = Body(...)):
    url = body.get('url'); ns = body.get('namespace') or DEFAULT_NAMESPACE; bucket = body.get('bucket') or DEFAULT_BUCKET
    if not url: raise HTTPException(400, 'url required')
    limit = int(body.get('max_videos') or YT_PLAYLIST_MAX)
    entries = _extract_entries(url)[:limit]
    if not entries:
        raise HTTPException(400, 'no entries found')
    job_id = _job_create('playlist', {'url': url, 'namespace': ns, 'bucket': bucket, 'count': len(entries)})
    if job_id:
        _job_update(job_id, 'running')
    # Resolve limits per-call to respect runtime env overrides in tests
    try:
        rate_limit = float(os.environ.get('YT_RATE_LIMIT', str(YT_RATE_LIMIT)))
    except Exception:
        rate_limit = YT_RATE_LIMIT
    try:
        concurrency = int(os.environ.get('YT_CONCURRENCY', str(YT_CONCURRENCY)))
    except Exception:
        concurrency = YT_CONCURRENCY
    concurrency = max(1, concurrency)

    async def _ingest_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        vid = entry['id']
        vid_url = f"https://www.youtube.com/watch?v={vid}" if len(vid) == 11 else vid
        if job_id:
            _item_upsert(job_id, vid, 'running', None, {'title': entry.get('title')})
        result: Dict[str, Any]
        status = 'failed'
        error_msg: Optional[str] = None
        try:
            result = await asyncio.to_thread(_ingest_one, vid_url, ns, bucket)
            status = 'completed' if result.get('ok') else 'failed'
            error_msg = result.get('error')
        except Exception as exc:
            error_msg = str(exc)
            result = {'ok': False, 'error': error_msg}
        if job_id:
            _item_upsert(job_id, vid, status, error_msg)
        return {'id': vid, **result}

    results: List[Dict[str, Any]] = []

    if concurrency <= 1:
        for entry in entries:
            res = await _ingest_entry(entry)
            results.append(res)
            if rate_limit > 0:
                await asyncio.sleep(rate_limit)
    else:
        semaphore = asyncio.Semaphore(concurrency)
        rate_lock = asyncio.Lock()
        next_available = 0.0
        results_buffer: List[Optional[Dict[str, Any]]] = [None] * len(entries)

        async def _wait_rate_limit() -> None:
            nonlocal next_available
            if rate_limit <= 0:
                return
            async with rate_lock:
                now = time.monotonic()
                if now < next_available:
                    await asyncio.sleep(next_available - now)
                    now = next_available
                next_available = now + rate_limit

        async def _worker(idx: int, entry: Dict[str, Any]) -> None:
            async with semaphore:
                await _wait_rate_limit()
                res = await _ingest_entry(entry)
                results_buffer[idx] = res

        tasks = [asyncio.create_task(_worker(idx, entry)) for idx, entry in enumerate(entries)]
        await asyncio.gather(*tasks)
        results = [res for res in results_buffer if res is not None]

    if job_id:
        _job_update(job_id, 'completed')
    return {'ok': True, 'job_id': job_id, 'count': len(results), 'results': results}

@app.post('/yt/channel')
async def yt_channel(body: Dict[str,Any] = Body(...)):
    # Accept channel URL or channel_id
    base = body.get('url') or body.get('channel_id')
    if not base:
        raise HTTPException(400, 'url or channel_id required')
    # yt-dlp accepts channel URLs; if only id provided, build URL
    if not base.startswith('http'):
        base = f"https://www.youtube.com/channel/{base}/videos"
    return await yt_playlist({'url': base, 'namespace': body.get('namespace'), 'bucket': body.get('bucket'), 'max_videos': body.get('max_videos')})

# -------------------- Gemma Summarization --------------------

def _summarize_ollama(text: str, style: str) -> str:
    prompt = f"You are a skilled video summarizer. Style={style}. Summarize the transcript below succinctly.\n\nTranscript:\n{text[:12000]}"
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json={"model": YT_GEMMA_MODEL, "prompt": prompt, "stream": False}, timeout=180)
        r.raise_for_status()
        j = r.json()
        return j.get('response') or j.get('data') or ''
    except Exception as e:
        raise HTTPException(502, f"Ollama summarization failed: {e}")

def _summarize_hf(text: str, style: str) -> str:
    # Optional local transformers path; requires GPU for Gemma-2 9B
    try:
        import torch  # noqa: F401
        from transformers import AutoTokenizer, AutoModelForCausalLM
    except Exception:
        raise HTTPException(500, "HF Transformers not installed; use provider=ollama or install transformers+torch")
    try:
        tok = AutoTokenizer.from_pretrained(HF_GEMMA_MODEL, token=HF_TOKEN)
        model = AutoModelForCausalLM.from_pretrained(HF_GEMMA_MODEL, device_map="auto" if HF_USE_GPU else None, torch_dtype="auto")
        sys_prompt = f"Summarize the following transcript in style={style}. Keep it concise and faithful."
        prompt = f"<start_of_turn>user\n{sys_prompt}\n\nTranscript:\n{text[:8000]}<end_of_turn>\n<start_of_turn>model\n"
        inputs = tok(prompt, return_tensors='pt').to(model.device)
        out = model.generate(**inputs, max_new_tokens=512, temperature=0.3)
        s = tok.decode(out[0], skip_special_tokens=True)
        return s.split("<start_of_turn>model",1)[-1].strip()
    except Exception as e:
        raise HTTPException(500, f"HF Gemma generation failed: {e}")

def _get_transcript(video_id: str) -> Dict[str,Any]:
    rows = supa_get('transcripts', {'video_id': video_id}) or []
    if not rows:
        return {'text': '', 'segments': []}
    # Prefer the longest transcript
    rows.sort(key=lambda r: len(r.get('text') or ''), reverse=True)
    row = rows[0]
    meta = row.get('meta') or {}
    return {'text': row.get('text') or '', 'segments': meta.get('segments') or []}

def _merge_video_meta(video_id: str, gemma_patch: Dict[str, Any]) -> None:
    rows = supa_get('videos', {'video_id': video_id}) or []
    meta: Dict[str, Any] = {}
    if rows:
        existing_meta = rows[0].get('meta')
        if isinstance(existing_meta, dict):
            meta = dict(existing_meta)
    gemma_meta = meta.get('gemma')
    if isinstance(gemma_meta, dict):
        merged_gemma = dict(gemma_meta)
    else:
        merged_gemma = {}
    merged_gemma.update(gemma_patch)
    meta['gemma'] = merged_gemma
    supa_update('videos', {'video_id': video_id}, {'meta': meta})

@app.post('/yt/summarize')
def yt_summarize(body: Dict[str,Any] = Body(...)):
    vid = body.get('video_id'); provider = (body.get('provider') or YT_SUMMARY_PROVIDER).lower()
    style = (body.get('style') or 'short')
    if not vid: raise HTTPException(400, 'video_id required')
    tr = _get_transcript(vid)
    text = body.get('text') or tr.get('text')
    if not text: raise HTTPException(404, 'transcript not found; run /yt/transcript first')
    if provider == 'hf':
        summary = _summarize_hf(text, style)
    else:
        summary = _summarize_ollama(text, style)
    # persist into videos + studio_board meta
    _merge_video_meta(vid, {'style': style, 'provider': provider, 'summary': summary})
    # emit event for downstream (Discord/NATS)
    try:
        _publish_event('ingest.summary.ready.v1', {'video_id': vid, 'style': style, 'provider': provider, 'summary': summary[:500]})
    except Exception:
        pass
    return {'ok': True, 'video_id': vid, 'provider': provider, 'style': style, 'summary': summary}

@app.post('/yt/chapters')
def yt_chapters(body: Dict[str,Any] = Body(...)):
    vid = body.get('video_id'); provider = (body.get('provider') or YT_SUMMARY_PROVIDER).lower()
    if not vid: raise HTTPException(400, 'video_id required')
    tr = _get_transcript(vid)
    text = body.get('text') or tr.get('text')
    if not text: raise HTTPException(404, 'transcript not found; run /yt/transcript first')
    guide = "Produce 5-12 chapters. JSON array of objects: {title, blurb}. No extra prose."
    if provider == 'hf':
        raw = _summarize_hf(text, f"chapters; {guide}")
    else:
        raw = _summarize_ollama(text, f"chapters; {guide}")
    # try parse JSON array
    chapters: List[Dict[str,Any]] = []
    try:
        # find first [ ... ] block
        s = raw[raw.find('['): raw.rfind(']')+1]
        chapters = json.loads(s)
    except Exception:
        # fallback: split lines
        chapters = [{ 'title': line.strip('- ').strip(), 'blurb': '' } for line in raw.splitlines() if line.strip()][:10]
    _merge_video_meta(vid, {'chapters': chapters})
    try:
        _publish_event('ingest.chapters.ready.v1', {'video_id': vid, 'n': len(chapters), 'chapters': chapters[:6]})
    except Exception:
        pass
    return {'ok': True, 'video_id': vid, 'chapters': chapters}

# -------------------- Segmentation → JSONL + CGP emit --------------------

def _segment_transcript(text: str, doc_id: str, namespace: str) -> List[Dict[str,Any]]:
    # Naive sentence/paragraph segmentation by punctuation + length budget
    # Target ~900-1200 chars per chunk
    chunks: List[Dict[str,Any]] = []
    buf = []
    budget = 1000
    def flush():
        if not buf:
            return
        content = ' '.join(buf).strip()
        if content:
            chunk_id = f"{doc_id}:{len(chunks)}"
            chunks.append({
                'doc_id': doc_id,
                'section_id': None,
                'chunk_id': chunk_id,
                'text': content,
                'namespace': namespace,
                'payload': {'source': 'youtube'}
            })
        buf.clear()
    for part in re.split(r"(?<=[\.!?])\s+|\n+", text):
        if not part:
            continue
        buf.append(part)
        if sum(len(x) for x in buf) >= budget:
            flush()
    flush()
    # ensure at least one chunk
    if not chunks and text:
        chunks.append({'doc_id': doc_id, 'section_id': None, 'chunk_id': f"{doc_id}:0", 'text': text[:1200], 'namespace': namespace, 'payload': {'source': 'youtube'}})
    return chunks

def _segment_from_whisper_segments(
    segments: List[Dict[str,Any]],
    doc_id: str,
    namespace: str,
    target_dur: float = None,
    gap_thresh: float = None,
    min_chars: int = None,
    max_chars: int = None,
    max_dur: float = None,
) -> List[Dict[str,Any]]:
    # Smart boundary grouping with tunable thresholds
    tgt = float(target_dur) if target_dur is not None else YT_SEG_TARGET_DUR
    gap_thresh = gap_thresh if gap_thresh is not None else YT_SEG_GAP_THRESH
    min_chars = min_chars if min_chars is not None else YT_SEG_MIN_CHARS
    max_chars = max_chars if max_chars is not None else YT_SEG_MAX_CHARS
    max_dur = max_dur if max_dur is not None else YT_SEG_MAX_DUR
    chunks: List[Dict[str,Any]] = []
    cur: List[Dict[str,Any]] = []
    cur_dur = 0.0
    cur_chars = 0
    last_end = None
    def flush():
        nonlocal cur, cur_dur, cur_chars
        if not cur:
            return
        start = float(cur[0].get('start') or 0.0)
        end = float(cur[-1].get('end') or start)
        text = ' '.join((s.get('text') or '').strip() for s in cur).strip()
        chunk_id = f"{doc_id}:{len(chunks)}"
        chunks.append({
            'doc_id': doc_id,
            'section_id': None,
            'chunk_id': chunk_id,
            'text': text,
            'namespace': namespace,
            'payload': {'source': 'youtube', 't_start': start, 't_end': end}
        })
        cur = []
        cur_dur = 0.0
        cur_chars = 0
    for s in segments:
        st = float(s.get('start') or 0.0); en = float(s.get('end') or st)
        d = max(0.0, en - st)
        seg_text = s.get('text') or ''
        cur.append({'start': st, 'end': en, 'text': seg_text})
        cur_dur += d
        cur_chars += len(seg_text)
        gap = (st - last_end) if last_end is not None else 0.0
        last_end = en
        strong_punct = seg_text.strip().endswith(('.', '!', '?', '…'))
        # Adjust target for very short utterances (likely high-turn dialog)
        adj_tgt = tgt * 0.75 if len(seg_text.split()) < 6 else tgt
        if (cur_dur >= adj_tgt) or (gap > gap_thresh) or (strong_punct and cur_chars >= min_chars) or (cur_dur >= max_dur) or (cur_chars >= max_chars):
            flush()
    flush()
    if not chunks and segments:
        s0 = segments[0]
        chunks.append({'doc_id': doc_id, 'section_id': None, 'chunk_id': f"{doc_id}:0", 'text': s0.get('text') or '', 'namespace': namespace, 'payload': {'source':'youtube','t_start': float(s0.get('start') or 0.0),'t_end': float(s0.get('end') or 0.0)}})
    return chunks

def _auto_tune_segment_params(segments: List[Dict[str,Any]], text: str) -> Dict[str,Any]:
    """Infer content profile (dialogue, talk, music/lyrics) and adjust thresholds.

    Heuristics:
    - words/sec (wps), avg seg duration, avg words/seg, avg gap
    - lyrics/music cues: tags like [Music], repeated short lines, low punctuation
    """
    if not segments:
        return {}
    total_dur = 0.0
    total_words = 0
    gaps = []
    prev_end = None
    word_counts = []
    durations = []
    for s in segments:
        st = float(s.get('start') or 0.0); en = float(s.get('end') or st)
        d = max(0.0, en - st)
        durations.append(d)
        total_dur += d
        wc = len((s.get('text') or '').split())
        word_counts.append(wc)
        total_words += wc
        if prev_end is not None:
            gaps.append(max(0.0, st - prev_end))
        prev_end = en
    avg_gap = (sum(gaps)/len(gaps)) if gaps else 0.0
    avg_dur = (sum(durations)/len(durations)) if durations else 0.0
    avg_words = (sum(word_counts)/len(word_counts)) if word_counts else 0.0
    wps = (total_words/total_dur) if total_dur > 0 else 0.0
    # simple repetition/lyrics signal: many short lines and duplicates
    lines = [ (s.get('text') or '').strip().lower() for s in segments ]
    short_lines = sum(1 for l in lines if 0 < len(l) <= 40)
    unique_ratio = len(set(l for l in lines if l)) / max(1, len([l for l in lines if l]))
    has_music_tag = ('[music]' in text.lower()) or ('♪' in text)

    # Defaults (talk)
    params = dict(
        target_dur=YT_SEG_TARGET_DUR,
        gap_thresh=YT_SEG_GAP_THRESH,
        min_chars=YT_SEG_MIN_CHARS,
        max_chars=YT_SEG_MAX_CHARS,
        max_dur=YT_SEG_MAX_DUR,
        profile='talk'
    )
    # Dialogue: rapid turns, short segments, small gaps
    if avg_dur < 3.0 and avg_words < 12 and avg_gap < 0.8 and wps >= 2.0:
        params.update(dict(target_dur=max(15.0, YT_SEG_TARGET_DUR*0.67), gap_thresh=0.8, min_chars=max(400, YT_SEG_MIN_CHARS-200), max_chars=min(1200, YT_SEG_MAX_CHARS), max_dur=min(45.0, YT_SEG_MAX_DUR), profile='dialogue'))
        return params
    # Music/Lyrics: many short lines, repeated phrases, music cues
    if has_music_tag or (short_lines/ max(1,len(lines)) > 0.6 and unique_ratio < 0.9 and avg_words < 8):
        params.update(dict(target_dur=15.0, gap_thresh=0.6, min_chars=350, max_chars=900, max_dur=30.0, profile='lyrics'))
        return params
    # Long-form talk / lecture: long segments, slower wps
    if avg_dur >= 3.5 and avg_words >= 12 and wps <= 2.0:
        params.update(dict(target_dur=min(50.0, YT_SEG_TARGET_DUR*1.33), gap_thresh=max(1.5, YT_SEG_GAP_THRESH), min_chars=max(700, YT_SEG_MIN_CHARS), max_chars=min(1800, YT_SEG_MAX_CHARS+300), max_dur=min(75.0, YT_SEG_MAX_DUR+15), profile='talk-long'))
        return params
    return params

def _normalise(values: List[float]) -> List[float]:
    total = sum(values)
    if total <= 0:
        length = len(values) or 1
        uniform = 1.0 / length
        return [uniform] * length
    return [v / total for v in values]


def _build_cgp(video_id: str, chunks: List[Dict[str,Any]], title: Optional[str], namespace: str) -> Dict[str,Any]:
    pack = get_builder_pack(namespace, 'video')
    if not pack:
        # Fallback to direct Supabase lookup when the shared helper is unavailable in-container.
        packs = supa_get(
            'geometry_parameter_packs',
            {
                'namespace': namespace,
                'modality': 'video',
                'pack_type': 'cg_builder',
                'status': 'active',
            },
        ) or []
        if isinstance(packs, list) and packs:
            packs.sort(key=lambda row: row.get('created_at') or '', reverse=True)
            pack = packs[0]
    params = (pack or {}).get('params') or {}

    nbins = int(params.get('bins') or 32)
    nbins = max(4, min(128, nbins))
    kernel = int(params.get('K') or 1)
    kernel = max(1, min(nbins, kernel))
    tau = float(params.get('tau') or 1.0)
    tau = max(0.1, tau)
    beta = float(params.get('beta') or 1.0)
    beta = max(0.1, beta)

    spectrum_mode = (params.get('spectrum_mode') or 'histogram').lower()
    mf_rank = params.get('mf_rank') if isinstance(params.get('mf_rank'), list) else None

    n = max(1, len(chunks))
    spectrum = [0.0] * nbins

    if mf_rank and spectrum_mode == 'mf':
        mf_vals = [float(v) for v in mf_rank[:nbins]]
        if len(mf_vals) < nbins:
            mf_vals.extend([0.0] * (nbins - len(mf_vals)))
        spectrum = _normalise(mf_vals)
    else:
        decay_cache: Dict[int, float] = {}
        for idx in range(n):
            frac = (idx + 0.5) / n
            center = min(nbins - 1, int(frac * nbins))
            spectrum[center] += 1.0
            if kernel == 1:
                continue
            for offset in range(1, kernel):
                if offset not in decay_cache:
                    decay_cache[offset] = math.exp(-((offset / tau) ** beta))
                weight = decay_cache[offset]
                if center - offset >= 0:
                    spectrum[center - offset] += weight
                if center + offset < nbins:
                    spectrum[center + offset] += weight
        spectrum = _normalise(spectrum)

    points = []
    for i, ch in enumerate(chunks):
        points.append({
            'id': f"p:yt:{video_id}:{i}",
            'modality': 'video',
            'ref_id': video_id,
            't_start': (ch.get('payload') or {}).get('t_start'),
            't_end': (ch.get('payload') or {}).get('t_end'),
            'proj': float((i+1)/n),
            'conf': 1.0,
            'text': ch['text'][:400]
        })
    c = {
        'id': f"c:yt:{video_id}",
        'summary': title or f"YouTube {video_id}",
        'spectrum': [float(round(val, 6)) for val in spectrum],
        'points': points
    }
    meta: Dict[str, Any] = {'source': 'pmoves-yt', 'video_id': video_id, 'namespace': namespace, 'bins': nbins}
    if pack:
        meta['pack_id'] = pack.get('id')
        meta['builder_pack'] = {
            'id': pack.get('id'),
            'status': pack.get('status'),
            'generation': pack.get('generation'),
            'population_id': pack.get('population_id'),
            'fitness': pack.get('fitness'),
            'params': {
                'K': kernel,
                'bins': nbins,
                'tau': tau,
                'beta': beta,
                'spectrum_mode': spectrum_mode,
            },
            'raw': params,
        }
    return {'spec': 'chit.cgp.v0.1', 'meta': meta, 'super_nodes': [{'constellations': [c]}]}


@app.post('/yt/smoke/seed-pack')
def yt_smoke_seed_pack(body: Dict[str, Any] = Body({})):
    namespace = body.get('namespace') or DEFAULT_NAMESPACE
    modality = body.get('modality') or 'video'
    pack_id = body.get('pack_id') or str(uuid.uuid4())
    params = body.get('params') or {
        'bins': 24,
        'K': 2,
        'tau': 0.9,
        'beta': 1.15,
        'spectrum_mode': 'histogram'
    }
    payload = {
        'id': pack_id,
        'namespace': namespace,
        'modality': modality,
        'pack_type': 'cg_builder',
        'status': 'active',
        'params': params,
        'generation': body.get('generation') or 1,
        'population_id': body.get('population_id') or 'smoke',
        'fitness': body.get('fitness') or 0.9,
    }
    try:
        headers = {'content-type': 'application/json', 'prefer': 'return=representation'}
        if SUPA_SERVICE_KEY:
            headers.update({'apikey': SUPA_SERVICE_KEY, 'Authorization': f"Bearer {SUPA_SERVICE_KEY}"})
        resp = requests.post(
            f"{SUPA}/geometry_parameter_packs",
            headers=headers,
            data=json.dumps(payload),
            timeout=20,
        )
        resp.raise_for_status()
        rows = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else []
    except Exception as exc:
        raise HTTPException(502, f"geometry_parameter_packs insert failed: {exc}")
    clear_cache()
    if isinstance(rows, list) and rows:
        pack = rows[0]
    else:
        pack = payload
    return {'ok': True, 'pack': pack}


@app.post('/yt/cgp-build')
def yt_cgp_build(body: Dict[str, Any] = Body(...)):
    video_id = body.get('video_id')
    if not video_id:
        raise HTTPException(400, 'video_id required')
    namespace = body.get('namespace') or DEFAULT_NAMESPACE
    chunks = body.get('chunks') or []
    if not isinstance(chunks, list) or not chunks:
        raise HTTPException(400, 'chunks required')
    title = body.get('title')
    cgp = _build_cgp(video_id, chunks, title, namespace)
    return {'ok': True, 'cgp': cgp}

@app.post('/yt/emit')
def yt_emit(body: Dict[str,Any] = Body(...)):
    vid = body.get('video_id'); ns = body.get('namespace') or DEFAULT_NAMESPACE
    if not vid: raise HTTPException(400, 'video_id required')
    # fetch metadata for optional title
    vids = supa_get('videos', {'video_id': vid}) or []
    title = vids[0].get('title') if vids else None
    tr = _get_transcript(vid)
    text = body.get('text') or tr.get('text')
    segs = tr.get('segments') or []
    if not (text or segs): raise HTTPException(404, 'transcript not found; run /yt/transcript first')
    doc_id = f"yt:{vid}"
    tuned = None
    if segs and YT_SEG_AUTOTUNE:
        tuned = _auto_tune_segment_params(segs, text)
        chunks = _segment_from_whisper_segments(
            segs,
            doc_id,
            ns,
            target_dur=tuned.get('target_dur'),
            gap_thresh=tuned.get('gap_thresh'),
            min_chars=tuned.get('min_chars'),
            max_chars=tuned.get('max_chars'),
            max_dur=tuned.get('max_dur'),
        )
    elif segs:
        chunks = _segment_from_whisper_segments(segs, doc_id, ns)
    else:
        chunks = _segment_transcript(text, doc_id, ns)
    # upsert JSONL to hi-rag v2
    try:
        payload = {'items': chunks, 'ensure_collection': True, 'index_lexical': YT_INDEX_LEXICAL}
        r = requests.post(f"{HIRAG_URL}/hirag/upsert-batch", headers={'content-type':'application/json'}, data=json.dumps(payload), timeout=180)
        r.raise_for_status()
        up = r.json() if r.headers.get('content-type','').startswith('application/json') else {}
    except Exception as e:
        raise HTTPException(502, f"upsert-batch failed: {e}")
    # emit CGP
    try:
        cgp = _build_cgp(vid, chunks, title, ns)
        r2 = requests.post(f"{HIRAG_URL}/geometry/event", headers={'content-type':'application/json'}, data=json.dumps({'type':'geometry.cgp.v1','data':cgp}), timeout=60)
        r2.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"CGP emit failed: {e}")
    return {
        'ok': True,
        'video_id': vid,
        'chunks': len(chunks),
        'upserted': (up or {}).get('upserted'),
        'lexical_indexed': (up or {}).get('lexical_indexed'),
        'profile': (tuned or {}).get('profile') if tuned else None
    }

@app.post('/yt/search')
def yt_search(body: Dict[str,Any] = Body(...)):
    """Semantic search across YouTube transcript corpus via Hi-RAG v2.
    
    Args:
        query: Search query string
        limit: Maximum number of videos to return (default 10)
        threshold: Minimum similarity score 0-1 (default 0.70)
        namespace: Indexer namespace (default from env)
    
    Returns:
        {ok, query, results: [{video_id, title, url, similarity, excerpt, timestamp}], total}
    """
    query = body.get('query')
    if not query:
        raise HTTPException(400, 'query required')
    
    limit = int(body.get('limit', 10))
    threshold = float(body.get('threshold', 0.70))
    namespace = body.get('namespace', DEFAULT_NAMESPACE)
    
    # Query hi-rag for YouTube chunks (ask for more to account for filtering)
    try:
        payload = {'query': query, 'k': limit * 3, 'namespace': namespace}
        r = requests.post(f"{HIRAG_URL}/hirag/query", json=payload, timeout=30)
        r.raise_for_status()
        chunks = r.json().get('results', [])
    except Exception as e:
        raise HTTPException(502, f"hi-rag query failed: {e}")
    
    # Filter for YouTube content and deduplicate by video_id
    yt_results = []
    seen_videos = set()
    
    for chunk in chunks:
        doc_id = chunk.get('doc_id', '')
        if not doc_id.startswith('yt:'):
            continue
        
        video_id = doc_id.split(':')[1] if ':' in doc_id else doc_id
        if video_id in seen_videos:
            continue
        
        score = chunk.get('score', 0.0)
        if score < threshold:
            continue
        
        seen_videos.add(video_id)
        
        # Fetch video metadata from Supabase
        try:
            vid_rows = supa_get('videos', {'video_id': video_id}) or []
            title = vid_rows[0].get('title') if vid_rows else video_id
        except Exception:
            title = video_id
        
        yt_results.append({
            'video_id': video_id,
            'title': title,
            'url': f"https://youtube.com/watch?v={video_id}",
            'similarity': round(score, 4),
            'excerpt': chunk.get('text', '')[:300],
            'timestamp': chunk.get('payload', {}).get('t_start')
        })
        
        if len(yt_results) >= limit:
            break
    
    return {
        'ok': True,
        'query': query,
        'results': yt_results,
        'total': len(yt_results)
    }
