import os, json, tempfile, shutil, asyncio, time, re, math, uuid, copy, logging, threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Body, HTTPException, BackgroundTasks, Response
import yt_dlp
try:
    from yt_dlp.utils import DownloadError, PostProcessingError
except Exception:  # pragma: no cover - fallback when utils module missing
    class DownloadError(Exception):
        pass

    class PostProcessingError(Exception):
        pass
import boto3
import requests
from urllib.parse import urlparse, parse_qs, urlunparse
from nats.aio.client import Client as NATS
from tenacity import AsyncRetrying, retry_if_exception, wait_exponential, stop_after_attempt, RetryError
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

# Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

http_requests_total = Counter('pmoves_yt_http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
http_request_duration = Histogram('pmoves_yt_http_request_duration_seconds', 'HTTP request duration')
videos_downloaded_total = Counter('pmoves_yt_videos_downloaded_total', 'Videos downloaded')
transcripts_processed_total = Counter('pmoves_yt_transcripts_processed_total', 'Transcripts processed')
nats_messages_total = Counter('pmoves_yt_nats_messages_total', 'NATS messages published', ['subject'])

app = FastAPI(title="PMOVES.YT", version="1.0.0")
logger = logging.getLogger("pmoves-yt")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(handler)
logger.propagate = True

# Optional import for docs sync helpers (underscore package path is import-safe)
try:
    from pmoves.services.pmoves_yt.docs_sync import collect_yt_dlp_docs, sync_to_supabase  # type: ignore
except Exception:  # pragma: no cover
    collect_yt_dlp_docs = None  # type: ignore
    sync_to_supabase = None  # type: ignore
try:
    from .docs_catalog import options_catalog, extractor_count, version_info  # type: ignore
except Exception:  # pragma: no cover
    def options_catalog():  # type: ignore
        return {"options": [], "counts": {"options": 0}}
    def extractor_count():  # type: ignore
        return 0
    def version_info():  # type: ignore
        return {"yt_dlp_version": "unknown"}

def _parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or os.environ.get("S3_ENDPOINT") or "minio:9000"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"
MINIO_SECURE = (os.environ.get("MINIO_SECURE","false").lower() == "true")
DEFAULT_BUCKET = os.environ.get("YT_BUCKET","assets")
DEFAULT_NAMESPACE = os.environ.get("INDEXER_NAMESPACE","pmoves")
# Prefer unified Supabase REST; fall back to legacy compose PostgREST only if neither is present
SUPA = (
    os.environ.get("SUPABASE_REST_URL")
    or os.environ.get("SUPA_REST_URL")
    or "http://postgrest:3000"
)
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
INVIDIOUS_BASE_URL = os.environ.get("INVIDIOUS_BASE_URL")

CHANNEL_MONITOR_STATUS_URL = os.environ.get("CHANNEL_MONITOR_STATUS_URL")
CHANNEL_MONITOR_STATUS_SECRET = os.environ.get("CHANNEL_MONITOR_STATUS_SECRET")

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
YT_RETRY_MAX = int(os.environ.get("YT_RETRY_MAX", "3"))
YT_TEMP_ROOT = Path(os.environ.get("YT_TEMP_ROOT", "/tmp/pmoves-yt"))
YT_ARCHIVE_DIR = Path(os.environ.get("YT_ARCHIVE_DIR", "/data/yt-dlp"))
YT_ENABLE_DOWNLOAD_ARCHIVE = os.environ.get("YT_ENABLE_DOWNLOAD_ARCHIVE", "true").lower() == "true"
YT_DOWNLOAD_ARCHIVE = os.environ.get("YT_DOWNLOAD_ARCHIVE")
if not YT_DOWNLOAD_ARCHIVE:
    YT_DOWNLOAD_ARCHIVE = str(YT_ARCHIVE_DIR / "download-archive.txt")

_subtitle_env = os.environ.get("YT_SUBTITLE_LANGS", "")
YT_SUBTITLE_LANGS = [lang.strip() for lang in _subtitle_env.split(",") if lang.strip()]
YT_SUBTITLE_AUTO = os.environ.get("YT_SUBTITLE_AUTO", "false").lower() == "true"
YT_WRITE_INFO_JSON = os.environ.get("YT_WRITE_INFO_JSON", "true").lower() == "true"

_postprocessors_env = os.environ.get("YT_POSTPROCESSORS_JSON")
_postprocessors_default: List[Dict[str, Any]]
if _postprocessors_env:
    try:
        parsed = json.loads(_postprocessors_env)
        if isinstance(parsed, list):
            _postprocessors_default = parsed
        else:
            logger.warning("YT_POSTPROCESSORS_JSON must be a list; falling back to defaults")
            _postprocessors_default = [
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ]
    except json.JSONDecodeError:
        logger.warning("Failed to parse YT_POSTPROCESSORS_JSON; using defaults")
        _postprocessors_default = [
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ]
else:
    _postprocessors_default = [
        {"key": "FFmpegMetadata"},
        {"key": "EmbedThumbnail"},
    ]

# Segmentation thresholds (smart boundaries)
YT_SEG_TARGET_DUR = float(os.environ.get("YT_SEG_TARGET_DUR", "30.0"))
YT_SEG_GAP_THRESH = float(os.environ.get("YT_SEG_GAP_THRESH", "1.2"))
YT_SEG_MIN_CHARS = int(os.environ.get("YT_SEG_MIN_CHARS", "600"))
YT_SEG_MAX_CHARS = int(os.environ.get("YT_SEG_MAX_CHARS", "1500"))
YT_SEG_MAX_DUR = float(os.environ.get("YT_SEG_MAX_DUR", "60.0"))
# PO Token provider defaults
BGUTIL_HTTP_BASE_URL = os.environ.get("BGUTIL_HTTP_BASE_URL")
BGUTIL_DISABLE_INNERTUBE = os.environ.get("BGUTIL_DISABLE_INNERTUBE")
# Always include lexical indexing on upsert (can be disabled)
YT_INDEX_LEXICAL = os.environ.get("YT_INDEX_LEXICAL", "true").lower() == "true"
try:
    YT_INDEX_LEXICAL_DISABLE_THRESHOLD = max(0, int(os.environ.get("YT_INDEX_LEXICAL_DISABLE_THRESHOLD", "0")))
except ValueError:
    YT_INDEX_LEXICAL_DISABLE_THRESHOLD = 0

YT_ASYNC_UPSERT_ENABLED = os.environ.get("YT_ASYNC_UPSERT_ENABLED", "true").lower() == "true"
try:
    YT_ASYNC_UPSERT_MIN_CHUNKS = max(1, int(os.environ.get("YT_ASYNC_UPSERT_MIN_CHUNKS", "200")))
except ValueError:
    YT_ASYNC_UPSERT_MIN_CHUNKS = 600

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
INVIDIOUS_COMPANION_URL = os.environ.get("INVIDIOUS_COMPANION_URL")
INVIDIOUS_COMPANION_KEY = os.environ.get("INVIDIOUS_COMPANION_KEY")
INVIDIOUS_FALLBACK_FORMAT = os.environ.get("INVIDIOUS_FALLBACK_FORMAT", "video/mp4")
YT_ENABLE_PO_TOKEN = os.environ.get("YT_ENABLE_PO_TOKEN", "false").lower() == "true"
YT_COMPANION_ENABLED = os.environ.get("YT_COMPANION_ENABLED", "true").lower() in {"true", "1", "yes", "y"}
YT_PO_TOKEN_VALUE = os.environ.get("YT_PO_TOKEN_VALUE")
YT_PO_TOKEN_ITAG = os.environ.get("YT_PO_TOKEN_ITAG", "18")
try:
    YT_UPSERT_BATCH_SIZE = max(1, int(os.environ.get("YT_UPSERT_BATCH_SIZE", "200")))
except ValueError:
    YT_UPSERT_BATCH_SIZE = 200
SOUNDCLOUD_USERNAME = os.environ.get("SOUNDCLOUD_USERNAME")
SOUNDCLOUD_PASSWORD = os.environ.get("SOUNDCLOUD_PASSWORD") or os.environ.get("SOUNDCLOUD_PASS")
SOUNDCLOUD_COOKIEFILE = os.environ.get("SOUNDCLOUD_COOKIEFILE") or os.environ.get("SOUNDCLOUD_COOKIES")
SOUNDCLOUD_COOKIES_FROM_BROWSER = os.environ.get("SOUNDCLOUD_COOKIES_FROM_BROWSER")
YT_TRANSCRIPT_PROVIDER = os.environ.get("YT_TRANSCRIPT_PROVIDER") or "faster-whisper"
YT_WHISPER_MODEL = os.environ.get("YT_WHISPER_MODEL") or "small"
_raw_transcript_diarize = os.environ.get("YT_TRANSCRIPT_DIARIZE")
if _raw_transcript_diarize is None:
    YT_TRANSCRIPT_DIARIZE = False
else:
    parsed = _parse_bool(_raw_transcript_diarize)
    YT_TRANSCRIPT_DIARIZE = False if parsed is None else parsed

_nc: Optional[NATS] = None
_nc_connect_task: Optional[asyncio.Task] = None

_emit_jobs: Dict[str, Dict[str, Any]] = {}
_emit_job_lock = threading.Lock()


def _record_emit_job(job_id: str, state: Dict[str, Any]) -> None:
    with _emit_job_lock:
        _emit_jobs[job_id] = state


def _update_emit_job(job_id: str, **updates: Any) -> None:
    with _emit_job_lock:
        current = copy.deepcopy(_emit_jobs.get(job_id) or {})
        current.update(updates)
        _emit_jobs[job_id] = current


def _get_emit_job(job_id: str) -> Dict[str, Any]:
    with _emit_job_lock:
        return copy.deepcopy(_emit_jobs.get(job_id) or {})


def _clear_emit_jobs() -> None:  # pragma: no cover - primarily used in tests
    with _emit_job_lock:
        _emit_jobs.clear()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _channel_monitor_notify(
    video_id: Optional[str],
    status: str,
    *,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if not video_id or not CHANNEL_MONITOR_STATUS_URL:
        return
    payload: Dict[str, Any] = {"video_id": video_id, "status": status}
    if error:
        payload["error"] = error
    if metadata:
        payload["metadata"] = metadata
    headers = {"content-type": "application/json"}
    if CHANNEL_MONITOR_STATUS_SECRET:
        headers["X-Channel-Monitor-Token"] = CHANNEL_MONITOR_STATUS_SECRET
    try:
        requests.post(
            CHANNEL_MONITOR_STATUS_URL,
            json=payload,
            headers=headers,
            timeout=5,
        )
    except requests.RequestException as exc:  # pragma: no cover - best effort
        logger.warning("Channel monitor notify failed for %s: %s", video_id, exc)

def _with_ytdlp_defaults(opts: Dict[str, Any], *, po_token: Optional[str] = None) -> Dict[str, Any]:
    """Add hardened defaults so youtube-dl works without manual cookies."""
    merged = dict(opts)
    extractor_args = dict(merged.get('extractor_args') or {})
    youtube_args = dict(extractor_args.get('youtube') or {})
    effective_po_token = po_token or (YT_PO_TOKEN_VALUE if YT_ENABLE_PO_TOKEN else None)
    if effective_po_token:
        po_token_values = list(youtube_args.get('po_token') or [])
        if effective_po_token not in po_token_values:
            youtube_args['po_token'] = [effective_po_token] + po_token_values
    if YT_PLAYER_CLIENT:
        clients = list(youtube_args.get('player_client') or [])
        if YT_PLAYER_CLIENT not in clients:
            youtube_args['player_client'] = [YT_PLAYER_CLIENT] + clients
    if youtube_args:
        extractor_args['youtube'] = youtube_args
    bgutil_args = dict(extractor_args.get('youtubepot-bgutilhttp') or {})
    if BGUTIL_HTTP_BASE_URL and not bgutil_args.get('base_url'):
        bgutil_args['base_url'] = [BGUTIL_HTTP_BASE_URL]
    if BGUTIL_DISABLE_INNERTUBE is not None and not bgutil_args.get('disable_innertube'):
        value = BGUTIL_DISABLE_INNERTUBE.lower()
        bgutil_args['disable_innertube'] = ['1' if value in {'1', 'true', 'yes'} else '0']
    if bgutil_args:
        extractor_args['youtubepot-bgutilhttp'] = bgutil_args
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
    merged.setdefault('continuedl', True)
    merged.setdefault('nooverwrites', True)
    merged.setdefault('format', 'best')
    merged.setdefault('merge_output_format', 'mp4')
    merged.setdefault('noplaylist', True)
    merged.setdefault('hls_prefer_native', True)
    return merged

def s3_client():
    endpoint_url = MINIO_ENDPOINT if "://" in MINIO_ENDPOINT else f"{'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}"
    return boto3.client("s3", aws_access_key_id=MINIO_ACCESS_KEY, aws_secret_access_key=MINIO_SECRET_KEY, endpoint_url=endpoint_url)

async def _nats_connect_loop() -> None:
    """Background task to keep the NATS connection alive."""
    global _nc
    backoff = 1.0
    while True:
        try:
            nc = NATS()
            closed_event: asyncio.Event = asyncio.Event()

            async def _handle_disconnected() -> None:
                logger.warning("Lost connection to NATS; waiting for reconnect")

            async def _handle_closed() -> None:
                global _nc
                logger.warning("NATS connection closed; scheduling reconnect")
                _nc = None
                closed_event.set()

            await nc.connect(
                servers=[NATS_URL],
                disconnected_cb=_handle_disconnected,
                closed_cb=_handle_closed,
            )
            _nc = nc
            logger.info("Connected to NATS at %s", NATS_URL)
            backoff = 1.0
            await closed_event.wait()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            logger.warning("Failed to connect to NATS at %s: %s", NATS_URL, err)
            _nc = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


@app.on_event("startup")
async def startup():
    # Non-blocking, quiet NATS init. Skip entirely unless explicitly enabled.
    global _nc, _nc_connect_task
    if not YT_NATS_ENABLE or not NATS_URL:
        _nc = None
    else:
        if _nc_connect_task is None or _nc_connect_task.done():
            _nc_connect_task = asyncio.create_task(_nats_connect_loop(), name="pmoves-yt-nats-connect")

    # Docs sync at startup + optional periodic schedule
    try:
        if collect_yt_dlp_docs and sync_to_supabase:
            if os.environ.get("YT_DOCS_SYNC_ON_START", "true").lower() in {"1","true","yes","y"}:
                try:
                    docs = collect_yt_dlp_docs()
                    sync_to_supabase(docs)
                    logger.info("yt-dlp docs synced on start")
                except Exception as exc:
                    logger.warning("docs sync on start failed: %s", exc)
            interval_env = os.environ.get("YT_DOCS_SYNC_INTERVAL_SECONDS") or os.environ.get("YT_DOCS_SYNC_INTERVAL")
            if interval_env:
                try:
                    interval = int(interval_env)
                except Exception:
                    interval = 86400
                async def _periodic_docs_sync():
                    while True:
                        await asyncio.sleep(interval)
                        try:
                            docs = collect_yt_dlp_docs()
                            sync_to_supabase(docs)
                            logger.info("yt-dlp docs synced (periodic)")
                        except Exception as exc:
                            logger.warning("periodic docs sync failed: %s", exc)
                asyncio.create_task(_periodic_docs_sync(), name="pmoves-yt-docs-sync")
    except Exception:
        pass


@app.on_event("shutdown")
async def shutdown():
    global _nc, _nc_connect_task
    if _nc_connect_task is not None:
        _nc_connect_task.cancel()
        try:
            await _nc_connect_task
        except asyncio.CancelledError:
            pass
        _nc_connect_task = None

    if _nc is not None and not getattr(_nc, "is_closed", True):
        try:
            await _nc.close()
        except Exception as err:
            logger.debug("Error closing NATS client during shutdown: %s", err)
    _nc = None

@app.get("/healthz")
def healthz():
    http_requests_total.labels(method='GET', endpoint='/healthz', status='200').inc()
    meta = version_info()
    prov = {
        "channel": os.environ.get("YT_CHANNEL") or os.environ.get("CHANNEL"),
        "origin": os.environ.get("YT_ORIGIN") or os.environ.get("ORIGIN"),
        "ytdlp_arg_version": os.environ.get("YTDLP_VERSION"),
        "ytdlp_pip_url": os.environ.get("YTDLP_PIP_URL"),
    }
    # Compact None values
    prov = {k: v for k, v in prov.items() if v}
    return {"ok": True, "yt_dlp": meta, "provenance": prov}

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

def _publish_event(topic: str, payload: Dict[str, Any]):
    nc = _nc
    if nc is None:
        logger.warning("NATS client unavailable; dropping event for topic %s", topic)
        return

    if getattr(nc, "is_closed", True) or getattr(nc, "is_draining", False) or not getattr(nc, "is_connected", False):
        logger.warning("NATS client not ready (closed=%s, draining=%s, connected=%s); dropping topic %s",
                       getattr(nc, "is_closed", True), getattr(nc, "is_draining", False), getattr(nc, "is_connected", False), topic)
        return

    msg = envelope(topic, payload, source="pmoves-yt")
    try:
        asyncio.create_task(nc.publish(topic, json.dumps(msg).encode()))
        nats_messages_total.labels(subject=topic.replace('.', '_')).inc()
    except Exception as exc:
        logger.exception("Failed to schedule publish for topic %s: %s", topic, exc)

def upload_to_s3(local_path: str, bucket: str, key: str):
    s3 = s3_client()
    s3.upload_file(local_path, bucket, key)
    scheme = 'https' if MINIO_SECURE else 'http'
    return f"{scheme}://{MINIO_ENDPOINT}/{bucket}/{key}"

def base_prefix(video_id: str, platform: Optional[str] = None):
    prefix = "yt"
    if platform:
        normalized = str(platform).strip().lower()
        if "youtube" in normalized:
            prefix = "yt"
        elif "soundcloud" in normalized:
            prefix = "sc"
        elif normalized:
            prefix = normalized.split(":")[0].replace("/", "-")
            if not prefix:
                prefix = "yt"
    return f"{prefix}/{video_id}"

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


def _parse_upload_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        if len(value) == 8 and value.isdigit():
            dt = datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def _fetch_channel_monitor_context(video_id: str) -> Optional[Dict[str, Any]]:
    rows = supa_get("pmoves_channel_monitoring", {"video_id": video_id}) or []
    if not rows:
        return None
    row = rows[0]
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    context = {
        "channel_id": row.get("channel_id"),
        "channel_name": row.get("channel_name"),
        "channel_url": metadata.get("channel_url") or metadata.get("source_url"),
        "channel_thumbnail": metadata.get("channel_thumbnail"),
        "namespace": row.get("namespace"),
        "tags": row.get("tags"),
        "priority": row.get("priority"),
        "last_status": metadata.get("last_status"),
        "last_status_at": metadata.get("last_status_at"),
        "subscriber_count": metadata.get("subscriber_count"),
        "channel_description": metadata.get("channel_description"),
    }
    return _compact(context) or None


def _collect_video_metadata(video_id: str) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "title": f"YouTube {video_id}",
        "description": None,
        "channel": None,
        "url": f"https://youtube.com/watch?v={video_id}",
        "published_at": None,
        "duration": None,
        "meta": {},
    }
    rows = supa_get("videos", {"video_id": video_id}) or []
    if not rows:
        return metadata

    row = rows[0]
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    provenance = meta.get("provenance") if isinstance(meta.get("provenance"), dict) else {}
    channel_meta = meta.get("channel") if isinstance(meta.get("channel"), dict) else {}
    channel_context = _fetch_channel_monitor_context(video_id)

    metadata["title"] = row.get("title") or metadata["title"]
    metadata["description"] = meta.get("description")
    metadata["duration"] = meta.get("duration") or meta.get("duration_seconds")
    metadata["namespace"] = row.get("namespace") or (channel_context or {}).get("namespace")
    metadata["tags"] = (channel_context or {}).get("tags")

    source_url = row.get("source_url") or provenance.get("original_url")
    if isinstance(source_url, str) and source_url.strip():
        metadata["url"] = source_url.strip()

    upload_date = provenance.get("upload_date") or meta.get("upload_date")
    published_at = _parse_upload_date(upload_date) or meta.get("published_at")
    if isinstance(published_at, str):
        parsed = _parse_upload_date(published_at) or published_at
        metadata["published_at"] = parsed

    channel_details = {
        "id": (channel_context or {}).get("channel_id") or channel_meta.get("id"),
        "name": (channel_context or {}).get("channel_name")
        or channel_meta.get("title")
        or channel_meta.get("name"),
        "url": (channel_context or {}).get("channel_url") or channel_meta.get("url"),
        "thumbnail": (channel_context or {}).get("channel_thumbnail")
        or channel_meta.get("thumbnail"),
        "description": (channel_context or {}).get("channel_description")
        or channel_meta.get("description"),
        "namespace": (channel_context or {}).get("namespace"),
        "tags": (channel_context or {}).get("tags"),
        "priority": (channel_context or {}).get("priority"),
        "subscriber_count": (channel_context or {}).get("subscriber_count")
        or channel_meta.get("subscriber_count"),
    }
    metadata["channel"] = _compact(channel_details)
    if channel_context:
        metadata["channel_monitor"] = channel_context

    metadata["meta"] = meta
    return metadata

def _should_use_invidious(exc: Exception) -> bool:
    if not (INVIDIOUS_BASE_URL or (INVIDIOUS_COMPANION_URL and INVIDIOUS_COMPANION_KEY)):
        return False
    # Allow operator to force fallback unconditionally (e.g., during SABR waves)
    if (os.environ.get("YT_FORCE_FALLBACK", "false").lower() in {"1","true","yes","y"}):
        return True
    msg = (str(exc) or "").lower()
    indicators = (
        # yt-dlp / SABR / nsig symptoms
        "signature extraction failed",
        "nsig",
        "sabr streaming",
        "missing a url",
        # client gating
        "player_ias",
        "innertube",
        # auth/throttling/region blocks
        "sign in to confirm",
        "sign in to view",
        "only available on certain devices",
        # http blocks and generic failures
        "http error 410",
        "http error 403",
        "http error 429",
        "unable to rename file",
        "downloaded file is empty",
        "did not get any data blocks",
        "all connection attempts failed",
        "yt_dlp returned no info",
    )
    return any(indicator in msg for indicator in indicators)

_YT_ID_RE = re.compile(r"(?:v=|/)([0-9A-Za-z_-]{11})(?:[&?/]|$)")

def _extract_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    match = _YT_ID_RE.search(url)
    if match:
        return match.group(1)
    if len(url) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", url):
        return url
    return None

def _infer_platform(url: Optional[str], entry_meta: Optional[Dict[str, Any]] = None) -> str:
    if entry_meta:
        for key in ("platform", "provider", "source"):
            value = entry_meta.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
    if url:
        lowered = url.lower()
        if "soundcloud.com" in lowered or lowered.startswith("soundcloud:"):
            return "soundcloud"
    return "youtube"

def _apply_provider_defaults(
    platform: str,
    ydl_opts: Dict[str, Any],
) -> None:
    if platform == "soundcloud":
        if SOUNDCLOUD_COOKIEFILE and "cookiefile" not in ydl_opts:
            ydl_opts["cookiefile"] = SOUNDCLOUD_COOKIEFILE
        if SOUNDCLOUD_COOKIES_FROM_BROWSER and "cookiesfrombrowser" not in ydl_opts:
            ydl_opts["cookiesfrombrowser"] = SOUNDCLOUD_COOKIES_FROM_BROWSER
        if SOUNDCLOUD_USERNAME and "username" not in ydl_opts:
            ydl_opts["username"] = SOUNDCLOUD_USERNAME
        if SOUNDCLOUD_PASSWORD and "password" not in ydl_opts:
            ydl_opts["password"] = SOUNDCLOUD_PASSWORD


def _fetch_po_token_from_companion(video_id: str) -> Optional[str]:
    if not YT_COMPANION_ENABLED:
        return None
    if not (INVIDIOUS_COMPANION_URL and INVIDIOUS_COMPANION_KEY):
        return None
    base = INVIDIOUS_COMPANION_URL.rstrip("/")
    if not base.endswith("/companion"):
        base = f"{base}/companion"
    try:
        resp = requests.get(
            f"{base}/latest_version",
            params={"id": video_id, "itag": YT_PO_TOKEN_ITAG, "local": "true"},
            headers={"Authorization": f"Bearer {INVIDIOUS_COMPANION_KEY}"},
            timeout=10,
            allow_redirects=False,
        )
        if resp.status_code in (301, 302):
            location = resp.headers.get("location")
            if location:
                query = parse_qs(urlparse(location).query)
                token = (query.get("pot") or [None])[0]
                if token:
                    logger.info(
                        "po_token_fetched",
                        extra={"event": "po_token_fetched", "video_id": video_id},
                    )
                    return f"WEB+{token}"
        else:
            logger.warning(
                "po_token_unexpected_status",
                extra={"event": "po_token_unexpected_status", "video_id": video_id, "status": resp.status_code},
            )
    except requests.RequestException as exc:
        logger.warning(
            "po_token_fetch_failed",
            extra={"event": "po_token_fetch_failed", "video_id": video_id, "error": str(exc)},
        )
    return None

def _download_with_yt_dlp(
    url: str,
    ns: str,
    bucket: str,
    ydl_opts: Dict[str, Any],
    postprocessors: Optional[List[Dict[str, Any]]],
    write_info_json: bool,
    job_id: Optional[str],
    entry_meta: Dict[str, Any],
    platform: str,
) -> Dict[str, Any]:
    success = False
    vid_dir: Optional[Path] = None
    platform_key = platform or "youtube"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise DownloadError(f"yt_dlp returned no info for {url}")
            if 'requested_downloads' in info and info['requested_downloads']:
                outpath = info['requested_downloads'][0]['_filename']
            else:
                outpath = ydl.prepare_filename(info)
            vid = info.get('id') or os.path.splitext(os.path.basename(outpath))[0]
            title = info.get('title') or vid
            base = base_prefix(vid, platform_key)
            vid_dir = YT_TEMP_ROOT / vid
            downloaded_at = datetime.now(timezone.utc).isoformat()
            channel_meta = {
                'title': info.get('uploader') or info.get('channel'),
                'id': info.get('channel_id') or info.get('uploader_id'),
                'url': info.get('uploader_url') or info.get('channel_url'),
            }
            video_meta_patch: Dict[str, Any] = {
                'thumb': None,
                'duration': info.get('duration'),
                'duration_ms': info.get('duration') * 1000 if info.get('duration') else None,
                'tags': info.get('tags'),
                'categories': info.get('categories'),
                'channel': channel_meta,
                'upload_date': info.get('upload_date'),
                'description': info.get('description'),
                'thumbnails': info.get('thumbnails'),
                'provenance': {
                    'source': platform_key,
                    'original_url': url,
                    'job_id': job_id,
                    'entry': entry_meta,
                    'downloaded_at': downloaded_at,
                },
                'ingest': {
                    'version': 1,
                    'downloader': 'yt-dlp',
                    'yt_dlp_version': getattr(yt_dlp, '__version__', None),
                    'options': {
                        'download_archive': ydl_opts.get('download_archive'),
                        'subtitleslangs': ydl_opts.get('subtitleslangs'),
                        'write_info_json': bool(write_info_json),
                        'postprocessors': [pp.get('key') for pp in postprocessors] if postprocessors else [],
                    },
                },
                'statistics': {
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                },
            }
            video_meta_patch = _compact(video_meta_patch) or {}
            raw_key = f"{base}/raw.mp4"
            s3_url = upload_to_s3(outpath, bucket, raw_key)
            thumb = None
            for ext in ('.jpg', '.png', '.webp'):
                cand = os.path.join(str(vid_dir), f"{vid}{ext}")
                if os.path.exists(cand):
                    thumb_key = f"{base}/thumb{ext}"
                    thumb = upload_to_s3(cand, bucket, thumb_key)
                    break
            if thumb:
                video_meta_patch = _deep_merge(video_meta_patch or {}, {'thumb': thumb})
            supa_insert('studio_board', {
                'title': title,
                'namespace': ns,
                'content_url': s3_url,
                'status': 'submitted',
                'meta': {
                    'source': platform_key,
                    'original_url': url,
                    'thumb': thumb,
                    'duration': info.get('duration'),
                    'channel': _compact(channel_meta) or None,
                    'job_id': job_id,
                }
            })
            supa_upsert('videos', {
                'video_id': vid,
                'namespace': ns,
                'title': title,
                'source_url': url,
                's3_base_prefix': f"s3://{bucket}/{base}",
                'meta': {'thumb': thumb}
            }, on_conflict='video_id')
            if video_meta_patch:
                _merge_meta(vid, video_meta_patch)
            try:
                event_payload = {
                    'bucket': bucket,
                    'key': raw_key,
                    'namespace': ns,
                    'title': title,
                    'source': platform_key,
                    'video_id': vid,
                }
                if info.get('duration'):
                    event_payload['duration'] = info.get('duration')
                _publish_event('ingest.file.added.v1', event_payload)
            except Exception:
                pass
            success = True
            logger.info(
                "download_complete",
                extra={
                    "event": "download_complete",
                    "video_id": vid,
                    "platform": platform_key,
                    "downloader": "yt-dlp",
                    "fallback_used": False,
                },
            )
            return {'ok': True, 'title': title, 'video_id': vid, 's3_url': s3_url, 'thumb': thumb}
    finally:
        if success and vid_dir is not None:
            shutil.rmtree(vid_dir, ignore_errors=True)

def _choose_invidious_stream(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    def score(stream: Dict[str, Any]) -> int:
        label = stream.get('qualityLabel') or stream.get('quality')
        if label and isinstance(label, str) and label.endswith('p'):
            try:
                return int(label.rstrip('p'))
            except ValueError:
                return 0
        return 0

    streams = data.get('formatStreams') or []
    preferred = [s for s in streams if 'video' in (s.get('type') or '') and 'mp4' in (s.get('type') or '') and s.get('url')]
    preferred.sort(key=score, reverse=True)
    if preferred:
        return preferred[0]
    fallback = [s for s in streams if s.get('url')]
    fallback.sort(key=score, reverse=True)
    return fallback[0] if fallback else None

def _choose_companion_stream(player_resp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    streaming = player_resp.get("streamingData") or {}
    candidates: List[Dict[str, Any]] = streaming.get("formats") or []
    if not candidates:
        candidates = streaming.get("adaptiveFormats") or []
    if not candidates:
        return None
    def score(item: Dict[str, Any]) -> int:
        height = item.get("height")
        if isinstance(height, int):
            return height
        quality = item.get("qualityLabel") or item.get("quality")
        if isinstance(quality, str) and quality.endswith("p"):
            try:
                return int(quality.rstrip("p"))
            except ValueError:
                return 0
        return 0
    filtered = []
    for fmt in candidates:
        mime = fmt.get("mimeType") or ""
        url = fmt.get("url")
        if not url:
            continue
        if INVIDIOUS_FALLBACK_FORMAT and INVIDIOUS_FALLBACK_FORMAT not in mime:
            continue
        filtered.append(fmt)
    if not filtered:
        filtered = [fmt for fmt in candidates if fmt.get("url")]
    filtered.sort(key=score, reverse=True)
    return filtered[0] if filtered else None

def _download_with_companion(
    url: str,
    ns: str,
    bucket: str,
    job_id: Optional[str],
    entry_meta: Dict[str, Any],
    platform: str,
) -> Dict[str, Any]:
    if not YT_COMPANION_ENABLED:
        raise HTTPException(503, "Invidious companion disabled")
    if not (INVIDIOUS_COMPANION_URL and INVIDIOUS_COMPANION_KEY):
        raise HTTPException(503, "Invidious companion not configured")
    video_id = _extract_video_id(url)
    if not video_id:
        raise HTTPException(400, "Unable to determine video id for Invidious companion fallback")
    player_endpoint = f"{INVIDIOUS_COMPANION_URL.rstrip('/')}/companion/youtubei/v1/player"
    headers = {
        "Authorization": f"Bearer {INVIDIOUS_COMPANION_KEY}",
        "content-type": "application/json",
    }
    payload = {"videoId": video_id}
    try:
        resp = requests.post(
            player_endpoint,
            json=payload,
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        player_resp = resp.json()
    except Exception as exc:
        raise HTTPException(502, f"Invidious companion error: {exc}") from exc
    stream = _choose_companion_stream(player_resp)
    if not stream:
        raise HTTPException(502, "Invidious companion did not return a playable stream")
    download_url = stream.get("url")
    if not download_url:
        raise HTTPException(502, "Invidious companion stream missing URL")
    mime = stream.get("mimeType") or "video/mp4"
    ext = "mp4"
    if "webm" in mime:
        ext = "webm"
    base = base_prefix(video_id, platform)
    vid_dir = YT_TEMP_ROOT / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = vid_dir / f"{video_id}.{ext}"
    try:
        with requests.get(download_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp_path, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    if chunk:
                        fh.write(chunk)
    except Exception as exc:
        shutil.rmtree(vid_dir, ignore_errors=True)
        raise HTTPException(502, f"Failed to download via Invidious companion: {exc}") from exc
    s3_url = upload_to_s3(str(tmp_path), bucket, f"{base}/raw.{ext}")
    title = entry_meta.get("title") or player_resp.get("videoDetails", {}).get("title") or video_id
    thumb = None
    thumbnails = (player_resp.get("videoDetails") or {}).get("thumbnail", {}).get("thumbnails") or []
    if thumbnails:
        thumb_sorted = sorted(thumbnails, key=lambda t: t.get("width") or 0, reverse=True)
        for thumb_entry in thumb_sorted:
            thumb_url = thumb_entry.get("url")
            if not thumb_url:
                continue
            try:
                r_thumb = requests.get(thumb_url, timeout=20)
                r_thumb.raise_for_status()
                thumb_path = vid_dir / f"{video_id}_thumb.jpg"
                with open(thumb_path, "wb") as tfh:
                    tfh.write(r_thumb.content)
                thumb = upload_to_s3(str(thumb_path), bucket, f"{base}/thumb.jpg")
                break
            except Exception:
                continue
    metadata_patch = _compact({
        "duration": stream.get("approxDurationMs"),
        "channel": {
            "title": (player_resp.get("videoDetails") or {}).get("author"),
            "id": (player_resp.get("videoDetails") or {}).get("channelId"),
        },
        "provenance": {
            "source": platform,
            "original_url": url,
            "job_id": job_id,
            "entry": entry_meta,
            "fallback": "companion",
        },
        "thumbnails": thumbnails,
        "statistics": {
            "view_count": (player_resp.get("videoDetails") or {}).get("viewCount"),
        },
    }) or {}
    supa_upsert(
        "videos",
        {
            "video_id": video_id,
            "namespace": ns,
            "title": title,
            "source_url": url,
            "s3_base_prefix": f"s3://{bucket}/{base}",
            "meta": {"thumb": thumb, "fallback": "companion"},
        },
        on_conflict="video_id",
    )
    if metadata_patch:
        _merge_meta(video_id, metadata_patch)
    supa_upsert(
        "studio_board",
        {
            "title": title,
            "namespace": ns,
            "content_url": s3_url,
            "status": "submitted",
            "meta": {
                "source": platform,
                "original_url": url,
                "thumb": thumb,
                "job_id": job_id,
                "fallback": "companion",
            },
        },
        on_conflict="content_url",
    )
    try:
        _publish_event(
            "ingest.file.added.v1",
            {
                "bucket": bucket,
                "key": f"{base}/raw.{ext}",
                "namespace": ns,
                "title": title,
                "source": platform,
                "video_id": video_id,
            },
        )
    except Exception:
        pass
    shutil.rmtree(vid_dir, ignore_errors=True)
    logger.info(
        "download_complete",
        extra={
            "event": "download_complete",
            "video_id": video_id,
            "platform": platform,
            "downloader": "invidious_companion",
            "fallback_used": True,
        },
    )
    return {"ok": True, "title": title, "video_id": video_id, "s3_url": s3_url, "thumb": thumb}

def _download_with_invidious(
    url: str,
    ns: str,
    bucket: str,
    job_id: Optional[str],
    entry_meta: Dict[str, Any],
    platform: str,
) -> Dict[str, Any]:
    if not INVIDIOUS_BASE_URL:
        raise HTTPException(503, 'Invidious fallback not configured (INVIDIOUS_BASE_URL missing)')
    video_id = _extract_video_id(url)
    if not video_id:
        raise HTTPException(400, 'Unable to determine YouTube video id for fallback')
    platform_key = platform or "youtube"
    api_url = f"{INVIDIOUS_BASE_URL.rstrip('/')}/api/v1/videos/{video_id}"
    try:
        response = requests.get(api_url, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise HTTPException(502, f"Invidious API error: {exc}") from exc
    stream = _choose_invidious_stream(data)
    if not stream:
        raise HTTPException(502, 'Invidious fallback did not return a playable stream')
    download_url = stream.get('url')
    if not download_url:
        raise HTTPException(502, 'Invidious fallback stream missing URL')
    content_type = stream.get('type') or 'video/mp4'
    ext = 'mp4'
    if 'webm' in content_type:
        ext = 'webm'
    base = base_prefix(video_id, platform_key)
    vid_dir = YT_TEMP_ROOT / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = vid_dir / f"{video_id}.{ext}"
    try:
        with requests.get(download_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp_path, 'wb') as fh:
                for chunk in r.iter_content(1 << 20):
                    if chunk:
                        fh.write(chunk)
    except Exception as exc:
        shutil.rmtree(vid_dir, ignore_errors=True)
        raise HTTPException(502, f"Failed to download via Invidious: {exc}") from exc
    s3_url = upload_to_s3(str(tmp_path), bucket, f"{base}/raw.{ext}")
    thumb_s3 = None
    thumbs = data.get('videoThumbnails') or []
    for thumb in sorted(thumbs, key=lambda t: t.get('width') or 0, reverse=True):
        thumb_url = thumb.get('url')
        if not thumb_url:
            continue
        try:
            resp = requests.get(thumb_url, timeout=20)
            resp.raise_for_status()
            thumb_ext = 'jpg'
            thumb_path = vid_dir / f"{video_id}_thumb.{thumb_ext}"
            with open(thumb_path, 'wb') as tfh:
                tfh.write(resp.content)
            thumb_key = f"{base}/thumb.{thumb_ext}"
            thumb_s3 = upload_to_s3(str(thumb_path), bucket, thumb_key)
            break
        except Exception:
            continue
    duration = data.get('lengthSeconds')
    title = data.get('title') or video_id
    channel_meta = {
        'title': data.get('author'),
        'id': data.get('authorId'),
        'url': data.get('authorUrl'),
    }
    video_meta_patch = _compact({
        'duration': duration,
        'duration_ms': int(duration) * 1000 if duration else None,
        'channel': channel_meta,
        'thumbnails': thumbs,
        'provenance': {
            'source': platform_key,
            'original_url': url,
            'job_id': job_id,
            'entry': entry_meta,
            'fallback': 'invidious',
        },
        'statistics': {
            'view_count': data.get('viewCount'),
        },
    }) or {}
    supa_upsert('videos', {
        'video_id': video_id,
        'namespace': ns,
        'title': title,
        'source_url': url,
        's3_base_prefix': f"s3://{bucket}/{base}",
        'meta': {'thumb': thumb_s3, 'fallback': 'invidious'}
    }, on_conflict='video_id')
    if video_meta_patch:
        _merge_meta(video_id, video_meta_patch)
    supa_upsert('studio_board', {
        'title': title,
        'namespace': ns,
        'content_url': s3_url,
        'status': 'submitted',
        'meta': {
            'source': platform_key,
            'original_url': url,
            'thumb': thumb_s3,
            'duration': duration,
            'channel': _compact(channel_meta) or None,
            'job_id': job_id,
            'fallback': 'invidious',
        }
    }, on_conflict='content_url')
    try:
        _publish_event('ingest.file.added.v1', {
            'bucket': bucket,
            'key': f"{base}/raw.{ext}",
            'namespace': ns,
            'title': title,
            'source': platform_key,
            'video_id': video_id,
        })
    except Exception:
        pass
    shutil.rmtree(vid_dir, ignore_errors=True)
    return {'ok': True, 'title': title, 'video_id': video_id, 's3_url': s3_url, 'thumb': thumb_s3}

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
    job_id = body.get('job_id')
    raw_meta = body.get('entry_meta') or body.get('metadata') or {}
    entry_meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
    platform = _infer_platform(url, entry_meta)
    entry_meta.setdefault('platform', platform)
    if not url: raise HTTPException(400, 'url required')
    YT_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    outtmpl = os.path.join(str(YT_TEMP_ROOT), '%(id)s', '%(id)s.%(ext)s')
    yt_options = body.get('yt_options') or {}
    video_id_hint = _extract_video_id(url)
    session_po_token = None
    if YT_ENABLE_PO_TOKEN and video_id_hint:
        session_po_token = _fetch_po_token_from_companion(video_id_hint)
        if not session_po_token and YT_PO_TOKEN_VALUE:
            session_po_token = YT_PO_TOKEN_VALUE
    elif YT_PO_TOKEN_VALUE and video_id_hint:
        session_po_token = YT_PO_TOKEN_VALUE
    ydl_opts = _with_ytdlp_defaults({
        'outtmpl': outtmpl,
        'format': body.get('format') or 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'writethumbnail': True,
        'quiet': True,
        'noprogress': True,
    }, po_token=session_po_token)
    if session_po_token and video_id_hint:
        logger.info(
            "po_token_applied",
            extra={"event": "po_token_applied", "video_id": video_id_hint},
        )
    archive_enabled = bool(yt_options.get('use_download_archive', YT_ENABLE_DOWNLOAD_ARCHIVE))
    archive_path_value = yt_options.get('download_archive', YT_DOWNLOAD_ARCHIVE)
    if archive_enabled and archive_path_value:
        archive_path = Path(archive_path_value)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        ydl_opts['download_archive'] = str(archive_path)

    subtitle_langs = yt_options.get('subtitle_langs', None)
    if isinstance(subtitle_langs, str):
        subtitle_langs = [lang.strip() for lang in subtitle_langs.split(',') if lang.strip()]
    if subtitle_langs is None:
        subtitle_langs = YT_SUBTITLE_LANGS
    auto_sub = bool(yt_options.get('subtitle_auto', YT_SUBTITLE_AUTO))
    if subtitle_langs:
        ydl_opts['writesubtitles'] = True
        ydl_opts['subtitleslangs'] = subtitle_langs
        if auto_sub:
            ydl_opts['writeautomaticsub'] = True

    write_info_json = yt_options.get('write_info_json', YT_WRITE_INFO_JSON)
    if write_info_json:
        ydl_opts['writeinfojson'] = True

    postprocessors = yt_options.get('postprocessors', None)
    if not isinstance(postprocessors, list):
        postprocessors = copy.deepcopy(_postprocessors_default)
    else:
        postprocessors = copy.deepcopy(postprocessors)
    if postprocessors:
        ydl_opts['postprocessors'] = postprocessors
    handled_keys = {
        'use_download_archive',
        'download_archive',
        'subtitle_langs',
        'subtitle_auto',
        'write_info_json',
        'postprocessors',
    }
    passthrough = {k: v for k, v in yt_options.items() if k not in handled_keys}
    for key, value in passthrough.items():
        if value is not None:
            ydl_opts[key] = value
    _apply_provider_defaults(platform, ydl_opts)
    try:
        return _download_with_yt_dlp(url, ns, bucket, ydl_opts, postprocessors, write_info_json, job_id, entry_meta, platform)
    except (DownloadError, PostProcessingError) as err:
        if platform == "youtube" and _should_use_invidious(err):
            logger.warning("yt-dlp failed, attempting fallback", extra={"video_id": _extract_video_id(url), "error": str(err)})
            if YT_COMPANION_ENABLED and INVIDIOUS_COMPANION_URL and INVIDIOUS_COMPANION_KEY:
                try:
                    return _download_with_companion(url, ns, bucket, job_id, entry_meta, platform)
                except HTTPException as companion_exc:
                    logger.exception("companion fallback failed", extra={"video_id": _extract_video_id(url), "error": str(companion_exc)})
                    raise companion_exc
            if INVIDIOUS_BASE_URL:
                fallback = _download_with_invidious(url, ns, bucket, job_id, entry_meta, platform)
                return fallback
            logger.warning("No Invidious fallback configured; propagating yt-dlp error", extra={"video_id": _extract_video_id(url)})
            raise HTTPException(500, f"yt-dlp error: {err}") from err
        raise HTTPException(500, f"yt-dlp error: {err}") from err
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"yt-dlp error: {exc}") from exc

@app.post("/yt/transcript")
def yt_transcript(body: Dict[str,Any] = Body(...)):
    vid = body.get('video_id'); bucket = body.get('bucket') or DEFAULT_BUCKET
    if not vid: raise HTTPException(400, 'video_id required')
    ns = body.get('namespace') or DEFAULT_NAMESPACE
    audio_key = f"{base_prefix(vid)}/audio.m4a"
    # Ensure raw.mp4 exists before attempting transcription. This triggers
    # yt-dlp with SABR-aware fallbacks (companion/invidious) when needed.
    try:
        yt_url = f"https://www.youtube.com/watch?v={vid}"
        _ = yt_download({'url': yt_url, 'namespace': ns, 'bucket': bucket})
    except HTTPException as dl_exc:
        # If download still fails, continue to ffmpeg-whisper which may be
        # able to transcribe from an existing raw.mp4 if it was uploaded by
        # another path; otherwise we’ll return its error below.
        logger.warning(
            "yt_transcript_prefetch_failed",
            extra={"event": "yt_transcript_prefetch_failed", "video_id": vid, "error": str(dl_exc.detail) if hasattr(dl_exc, 'detail') else str(dl_exc)},
        )
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
        transcript_text = j.get('text') or ''
        transcript_meta = _compact({
            'segments': j.get('segments'),
            'namespace': ns,
            'provider': j.get('provider') or body.get('provider'),
            'language': j.get('language') or body.get('language') or 'auto',
            's3_uri': j.get('s3_uri'),
        }) or {}
        supa_insert('transcripts', {
            'video_id': vid,
            'language': j.get('language') or body.get('language') or 'auto',
            'text': transcript_text,
            's3_uri': j.get('s3_uri'),
            'meta': transcript_meta,
        })
        if SUPA_SERVICE_KEY:
            try:
                video_meta = _collect_video_metadata(vid)
                channel_block = video_meta.get("channel") if isinstance(video_meta.get("channel"), dict) else {}
                channel_name = channel_block.get("name") if channel_block else video_meta.get("channel")
                yt_record: Dict[str, Any] = {
                    'video_id': vid,
                    'title': video_meta.get('title') or f"YouTube {vid}",
                    'description': video_meta.get('description'),
                    'channel': channel_name,
                    'channel_id': channel_block.get('id') if channel_block else None,
                    'channel_url': channel_block.get('url') if channel_block else None,
                    'channel_thumbnail': channel_block.get('thumbnail') if channel_block else None,
                    'channel_tags': channel_block.get('tags') if channel_block else None,
                    'namespace': video_meta.get('namespace'),
                    'url': video_meta.get('url'),
                    'published_at': video_meta.get('published_at'),
                    'duration': video_meta.get('duration'),
                    'transcript': transcript_text,
                    'meta': _compact({
                        'namespace': ns,
                        'language': j.get('language') or body.get('language') or 'auto',
                        's3_uri': j.get('s3_uri'),
                        'segments': j.get('segments'),
                        'channel_monitor': video_meta.get('channel_monitor'),
                    }) or None,
                    'channel_metadata': _compact({
                        'priority': channel_block.get('priority') if channel_block else None,
                        'subscriber_count': channel_block.get('subscriber_count') if channel_block else None,
                    }) or None,
                }
                supa_upsert('youtube_transcripts', yt_record, on_conflict='video_id')
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "youtube_transcripts_upsert_failed",
                    extra={"event": "youtube_transcripts_upsert_failed", "video_id": vid, "error": str(exc)},
                )
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
    if not url:
        raise HTTPException(400, 'url required')
    bucket = body.get('bucket') or DEFAULT_BUCKET
    dl: Optional[Dict[str, Any]] = None
    try:
        logger.info("ingest_started", extra={"event": "ingest_started", "url": url, "namespace": ns})
        dl = yt_download({'url': url, 'namespace': ns, 'bucket': bucket})
        logger.info(
            "ingest_download_complete",
            extra={
                "event": "ingest_download_complete",
                "url": url,
                "namespace": ns,
                "video_id": dl.get('video_id') if dl else None,
            },
        )
        tr_payload = {
            'video_id': dl['video_id'],
            'namespace': ns,
            'bucket': bucket,
            'language': body.get('language'),
            'whisper_model': body.get('whisper_model'),
        }
        if body.get('provider'):
            tr_payload['provider'] = body['provider']
        if YT_TRANSCRIPT_PROVIDER:
            tr_payload.setdefault('provider', YT_TRANSCRIPT_PROVIDER)
        if YT_WHISPER_MODEL:
            tr_payload.setdefault('whisper_model', YT_WHISPER_MODEL)
        if YT_TRANSCRIPT_DIARIZE is not None:
            tr_payload.setdefault('diarize', YT_TRANSCRIPT_DIARIZE)
        tr = yt_transcript(tr_payload)
        logger.info(
            "ingest_transcript_complete",
            extra={
                "event": "ingest_transcript_complete",
                "url": url,
                "namespace": ns,
                "video_id": dl.get('video_id') if dl else None,
                "transcript_ok": tr.get('ok'),
            },
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
        http_requests_total.labels(method='POST', endpoint='/yt/ingest', status=str(exc.status_code)).inc()
        _channel_monitor_notify(dl.get('video_id') if dl else None, 'failed', error=detail)
        logger.exception(
            "ingest_failed_http",
            extra={
                "event": "ingest_failed_http",
                "url": url,
                "namespace": ns,
                "video_id": dl.get('video_id') if dl else None,
                "error": detail,
            },
        )
        raise
    except Exception as exc:
        http_requests_total.labels(method='POST', endpoint='/yt/ingest', status='500').inc()
        _channel_monitor_notify(dl.get('video_id') if dl else None, 'failed', error=str(exc))
        logger.exception(
            "ingest_failed",
            extra={
                "event": "ingest_failed",
                "url": url,
                "namespace": ns,
                "video_id": dl.get('video_id') if dl else None,
                "error": str(exc),
            },
        )
        raise

    _channel_monitor_notify(
        dl.get('video_id'),
        'completed',
        metadata={
            'ingest': {
                'source': 'pmoves-yt',
                'namespace': ns,
                'bucket': bucket,
            }
        },
    )
    logger.info(
        "ingest_completed",
        extra={
            "event": "ingest_completed",
            "url": url,
            "namespace": ns,
            "video_id": dl.get('video_id'),
        },
    )
    # Track metrics
    videos_downloaded_total.inc()
    transcripts_processed_total.inc()
    http_requests_total.labels(method='POST', endpoint='/yt/ingest', status='200').inc()
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

def _item_upsert(
    job_id: str,
    video_id: str,
    status: str,
    error: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    retries: Optional[int] = None,
):
    row: Dict[str, Any] = {'job_id': job_id, 'video_id': video_id, 'status': status}
    if error is not None:
        row['error'] = error
    if meta is not None:
        row['meta'] = meta
    if retries is not None:
        row['retries'] = retries
    supa_upsert('yt_items', row, on_conflict='job_id,video_id')


def _item_update(job_id: str, video_id: str, patch: Dict[str, Any]) -> None:
    supa_update('yt_items', {'job_id': job_id, 'video_id': video_id}, patch)


class IngestException(Exception):
    def __init__(self, message: str, transient: bool = True) -> None:
        super().__init__(message)
        self.transient = transient


def _is_retryable_error(message: Optional[str]) -> bool:
    if not message:
        return True
    lowered = message.lower()
    for token in ("404", "not found", "private video", "copyright"):
        if token in lowered:
            return False
    return True


def _should_retry_exception(exc: BaseException) -> bool:
    if isinstance(exc, IngestException):
        return exc.transient
    if isinstance(exc, HTTPException):
        return 500 <= exc.status_code < 600
    return isinstance(exc, (requests.RequestException, DownloadError))


def _deep_merge(target: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(target)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _merge_meta(video_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    rows = supa_get('videos', {'video_id': video_id}) or []
    current: Dict[str, Any] = {}
    if rows:
        existing_meta = rows[0].get('meta')
        if isinstance(existing_meta, dict):
            current = copy.deepcopy(existing_meta)
    merged = _deep_merge(current, patch)
    supa_update('videos', {'video_id': video_id}, {'meta': merged})
    return merged


def _compact(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            compacted = _compact(v)
            if compacted is not None:
                cleaned[k] = compacted
        return cleaned or None
    if isinstance(value, list):
        cleaned_list = [v for v in (_compact(item) for item in value) if v is not None]
        return cleaned_list or None
    if value in (None, ""):
        return None
    return value

def _ingest_one(video_url: str, ns: str, bucket: str, job_id: Optional[str] = None, entry_meta: Optional[Dict[str, Any]] = None) -> Dict[str,Any]:
    try:
        payload = {'url': video_url, 'namespace': ns, 'bucket': bucket}
        if job_id:
            payload['job_id'] = job_id
        if entry_meta:
            payload['entry_meta'] = entry_meta
        d = yt_download(payload)
        vid = d.get('video_id')
        t = yt_transcript({'video_id': vid, 'namespace': ns, 'bucket': bucket})
        return {'ok': True, 'video_id': vid, 'download': d, 'transcript': t}
    except HTTPException as e:
        return {'ok': False, 'error': str(e.detail)}


async def _ingest_one_async(video_url: str, ns: str, bucket: str, job_id: Optional[str] = None, entry_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result = await asyncio.to_thread(_ingest_one, video_url, ns, bucket, job_id, entry_meta)
    if not result.get('ok'):
        msg = result.get('error') or 'ingest failed'
        raise IngestException(msg, transient=_is_retryable_error(msg))
    return result

@app.post('/yt/playlist')
async def yt_playlist(body: Dict[str,Any] = Body(...)):
    url = body.get('url'); ns = body.get('namespace') or DEFAULT_NAMESPACE; bucket = body.get('bucket') or DEFAULT_BUCKET
    if not url:
        raise HTTPException(400, 'url required')
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

    semaphore = asyncio.Semaphore(max(1, YT_CONCURRENCY))
    rate_lock = asyncio.Lock()
    last_request = {'ts': time.monotonic() - rate_limit if rate_limit > 0 else 0.0}

    async def respect_rate_limit():
        if rate_limit <= 0:
            return
        async with rate_lock:
            now = time.monotonic()
            wait_for = rate_limit - (now - last_request['ts'])
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            last_request['ts'] = time.monotonic()

    async def worker(position: int, entry: Dict[str, Any]):
        vid_id = entry['id']
        meta = {'title': entry.get('title'), 'position': position}
        if job_id:
            _item_upsert(job_id, vid_id, 'queued', None, meta, retries=0)
        video_url = f"https://www.youtube.com/watch?v={vid_id}" if len(vid_id) == 11 else vid_id

        async def attempt_ingest() -> Dict[str, Any]:
            async with semaphore:
                await respect_rate_limit()
                return await _ingest_one_async(video_url, ns, bucket, job_id=job_id, entry_meta=meta)

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(_should_retry_exception),
                stop=stop_after_attempt(max(1, YT_RETRY_MAX)),
                wait=wait_exponential(multiplier=1, min=1, max=30),
                reraise=True,
            ):
                attempt_num = attempt.retry_state.attempt_number
                if job_id:
                    status = 'running' if attempt_num == 1 else 'retrying'
                    _item_upsert(job_id, vid_id, status, None, meta, retries=max(0, attempt_num - 1))
                try:
                    result = await attempt_ingest()
                except BaseException as exc:
                    if job_id:
                        _item_update(job_id, vid_id, {
                            'status': 'retrying',
                            'error': str(exc),
                            'retries': attempt.retry_state.attempt_number,
                        })
                    raise
                else:
                    if job_id:
                        _item_update(job_id, vid_id, {'status': 'completed', 'error': None})
                    return {'id': vid_id, **result}
        except IngestException as exc:
            if job_id:
                _item_update(job_id, vid_id, {'status': 'failed', 'error': str(exc)})
            return {'id': vid_id, 'ok': False, 'error': str(exc)}
        except RetryError as exc:
            last_exc = exc.last_attempt.exception()
            msg = str(last_exc) if last_exc else 'max retries exceeded'
            if job_id:
                _item_update(job_id, vid_id, {'status': 'failed', 'error': msg, 'retries': YT_RETRY_MAX})
            return {'id': vid_id, 'ok': False, 'error': msg}
        except Exception as exc:
            if job_id:
                _item_update(job_id, vid_id, {'status': 'failed', 'error': str(exc)})
            return {'id': vid_id, 'ok': False, 'error': str(exc)}

    tasks = [asyncio.create_task(worker(idx, entry)) for idx, entry in enumerate(entries)]
    results = await asyncio.gather(*tasks)
    any_failures = any(not r.get('ok') for r in results)
    if job_id:
        _job_update(job_id, 'failed' if any_failures else 'completed', None if not any_failures else 'one or more items failed')
    return {'ok': not any_failures, 'job_id': job_id, 'count': len(results), 'results': results}
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
    _merge_meta(video_id, {'gemma': gemma_patch})

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

@app.post('/yt/docs/sync')
def yt_docs_sync():
    """Upsert yt-dlp CLI docs into Supabase (pmoves_core.tool_docs)."""
    if not (collect_yt_dlp_docs and sync_to_supabase):
        raise HTTPException(500, 'docs sync helpers unavailable')
    try:
        docs = collect_yt_dlp_docs()
        result = sync_to_supabase(docs)
        return {"ok": True, **result}
    except Exception as exc:  # pragma: no cover
        raise HTTPException(500, f"docs sync failed: {exc}")

@app.get('/yt/docs/catalog')
def yt_docs_catalog():
    """Return a structured options catalog and extractor count for UIs/agents."""
    try:
        cat = options_catalog()
        meta = version_info()
        meta["extractor_count"] = extractor_count()
        return {"ok": True, "meta": meta, **cat}
    except Exception as exc:  # pragma: no cover
        raise HTTPException(500, f"catalog error: {exc}")

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


def _upsert_chunks_to_hirag(
    chunks: List[Dict[str, Any]],
    *,
    lexical: bool,
    batch_size: int,
) -> Dict[str, Any]:
    payload_template = {'index_lexical': lexical}
    total_upserted = 0
    lexical_indexed = False
    batch_size = max(1, batch_size) if batch_size else len(chunks)
    for idx in range(0, len(chunks), batch_size):
        batch = chunks[idx:idx + batch_size]
        payload = dict(payload_template)
        payload['items'] = batch
        payload['ensure_collection'] = idx == 0
        r = requests.post(
            f"{HIRAG_URL}/hirag/upsert-batch",
            headers={'content-type': 'application/json'},
            data=json.dumps(payload),
            timeout=(10, 600),
        )
        r.raise_for_status()
        if r.headers.get('content-type', '').startswith('application/json'):
            up_resp = r.json()
            total_upserted += up_resp.get('upserted', 0) or 0
            lexical_indexed = up_resp.get('lexical_indexed', lexical_indexed) or lexical_indexed
    return {
        'upserted': total_upserted,
        'lexical_indexed': lexical_indexed if lexical else False,
    }


def _geometry_url_candidates() -> List[str]:
    candidates: List[str] = []

    def _push(url: Optional[str]) -> None:
        if not url:
            return
        cleaned = url.rstrip('/')
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    base = os.environ.get("HIRAG_URL")
    _push(base)
    _push(os.environ.get("HIRAG_GPU_URL"))
    _push(os.environ.get("HIRAG_CPU_URL"))

    # Derive common fallbacks from the primary base URL (CPU ↔ GPU, port swap, host bridge).
    derived_hosts: List[str] = []
    if base:
        parsed = urlparse(base)
        host = parsed.hostname or ""
        port = parsed.port
        scheme = parsed.scheme or "http"

        if host:
            if "hi-rag-gateway-v2" in host and "-gpu" not in host:
                derived_hosts.append(host.replace("hi-rag-gateway-v2", "hi-rag-gateway-v2-gpu"))
            if "hi-rag-gateway-v2-gpu" in host:
                derived_hosts.append(host.replace("hi-rag-gateway-v2-gpu", "hi-rag-gateway-v2"))
        if port == 8086:
            derived_hosts.append(f"{host}:8087" if host else "localhost:8087")
        elif port == 8087:
            derived_hosts.append(f"{host}:8086" if host else "localhost:8086")

        for derived in derived_hosts:
            if not derived:
                continue
            if ":" in derived:
                d_host, d_port = derived.split(":", 1)
            else:
                d_host, d_port = derived, ""
            new_netloc = derived
            if not d_port:
                new_netloc = f"{derived}:8086"
            derived_url = urlunparse((scheme, new_netloc, '', '', '', ''))
            _push(derived_url)

    # Default fallbacks for typical local setups.
    _push("http://hi-rag-gateway-v2-gpu:8086")
    _push("http://hi-rag-gateway-v2:8086")
    _push("http://host.docker.internal:8087")
    _push("http://host.docker.internal:8086")
    _push("http://localhost:8087")
    _push("http://localhost:8086")

    return candidates


def _emit_geometry_event(
    video_id: str,
    chunks: List[Dict[str, Any]],
    title: Optional[str],
    namespace: str,
) -> None:
    cgp = _build_cgp(video_id, chunks, title, namespace)
    payload = {'type': 'geometry.cgp.v1', 'data': cgp}
    last_error: Optional[Exception] = None
    for base in _geometry_url_candidates():
        try:
            r2 = requests.post(
                f"{base}/geometry/event",
                headers={'content-type': 'application/json'},
                data=json.dumps(payload),
                timeout=60,
            )
            r2.raise_for_status()
            if base != (HIRAG_URL.rstrip('/') if HIRAG_URL else None):
                logger.info(
                    "geometry_event_routed",
                    extra={
                        "event": "geometry_event_routed",
                        "video_id": video_id,
                        "target": base,
                    },
                )
            return
        except Exception as exc:  # pylint: disable=broad-except
            last_error = exc
            logger.warning(
                "geometry_event_post_failed",
                extra={
                    "event": "geometry_event_post_failed",
                    "video_id": video_id,
                    "target": base,
                    "error": str(exc),
                },
            )
            continue
    raise HTTPException(502, f"Failed to publish geometry event: {last_error}")


def _emit_async_job(
    job_id: str,
    video_id: str,
    namespace: str,
    title: Optional[str],
    tuned: Optional[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    lexical: bool,
    batch_size: int,
) -> None:
    logger.info(
        "yt_emit_async_started",
        extra={
            "event": "yt_emit_async_started",
            "job_id": job_id,
            "video_id": video_id,
            "namespace": namespace,
            "chunks": len(chunks),
            "lexical": lexical,
        },
    )
    try:
        up = _upsert_chunks_to_hirag(chunks, lexical=lexical, batch_size=batch_size)
        _emit_geometry_event(video_id, chunks, title, namespace)
        _update_emit_job(
            job_id,
            status="completed",
            finished_at=_utc_now(),
            upserted=up.get('upserted'),
            lexical_indexed=up.get('lexical_indexed'),
            profile=(tuned or {}).get('profile') if tuned else None,
        )
        logger.info(
            "yt_emit_async_completed",
            extra={
                "event": "yt_emit_async_completed",
                "job_id": job_id,
                "video_id": video_id,
                "namespace": namespace,
                "upserted": up.get('upserted'),
                "lexical_indexed": up.get('lexical_indexed'),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception(
            "yt_emit_async_failed",
            extra={
                "event": "yt_emit_async_failed",
                "job_id": job_id,
                "video_id": video_id,
                "namespace": namespace,
                "error": str(exc),
            },
        )
        _update_emit_job(
            job_id,
            status="failed",
            finished_at=_utc_now(),
            error=str(exc),
        )

@app.post('/yt/emit')
def yt_emit(background_tasks: BackgroundTasks, body: Dict[str, Any] = Body(...)):
    vid = body.get('video_id')
    ns = body.get('namespace') or DEFAULT_NAMESPACE
    if not vid:
        raise HTTPException(400, 'video_id required')
    # fetch metadata for optional title
    vids = supa_get('videos', {'video_id': vid}) or []
    title = vids[0].get('title') if vids else None
    tr = _get_transcript(vid)
    text = body.get('text') or tr.get('text')
    segs = tr.get('segments') or []
    if not (text or segs):
        # Auto-fallback: attempt an on-demand transcript via ffmpeg-whisper, then re-check
        try:
            payload = {
                'video_id': vid,
                'namespace': ns,
                'bucket': body.get('bucket') or DEFAULT_BUCKET,
            }
            # Respect configured defaults
            if YT_TRANSCRIPT_PROVIDER:
                payload['provider'] = YT_TRANSCRIPT_PROVIDER
            if YT_WHISPER_MODEL:
                payload['whisper_model'] = YT_WHISPER_MODEL
            res = yt_transcript(payload)  # may raise HTTPException
            # Prefer immediate result if DB is slow to reflect
            text = body.get('text') or (res.get('text') if isinstance(res, dict) else None)
            segs = (res.get('segments') if isinstance(res, dict) else None) or []
            if not (text or segs):
                tr = _get_transcript(vid)
                text = body.get('text') or tr.get('text')
                segs = tr.get('segments') or []
        except HTTPException:
            # fall through to 404 below if still missing
            pass
    if not (text or segs):
        raise HTTPException(404, 'transcript not found; run /yt/transcript first')
    doc_id = f"yt:{vid}"
    tuned: Optional[Dict[str, Any]] = None
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

    lexical_enabled = YT_INDEX_LEXICAL
    lexical_override = body.get('index_lexical')
    if isinstance(lexical_override, bool):
        lexical_enabled = lexical_override
    elif isinstance(lexical_override, str):
        parsed = _parse_bool(lexical_override)
        if parsed is not None:
            lexical_enabled = parsed

    lexical_auto_disabled = False
    if (
        lexical_enabled
        and YT_INDEX_LEXICAL_DISABLE_THRESHOLD
        and len(chunks) >= YT_INDEX_LEXICAL_DISABLE_THRESHOLD
    ):
        lexical_enabled = False
        lexical_auto_disabled = True

    try:
        batch_size = int(body.get('upsert_batch_size') or YT_UPSERT_BATCH_SIZE)
        if batch_size <= 0:
            batch_size = len(chunks) or 1
    except Exception:
        batch_size = len(chunks) or 1

    async_override = body.get('async') if 'async' in body else body.get('async_upsert')
    should_async = False
    if YT_ASYNC_UPSERT_ENABLED:
        if async_override is not None:
            if isinstance(async_override, bool):
                should_async = async_override
            elif isinstance(async_override, str):
                parsed = _parse_bool(async_override)
                if parsed is not None:
                    should_async = parsed
        if not should_async and len(chunks) >= YT_ASYNC_UPSERT_MIN_CHUNKS:
            should_async = True

    if should_async and background_tasks is None:
        background_tasks = BackgroundTasks()

    if should_async:
        job_id = str(uuid.uuid4())
        _record_emit_job(
            job_id,
            {
                'job_id': job_id,
                'status': 'pending',
                'video_id': vid,
                'namespace': ns,
                'chunks': len(chunks),
                'lexical_enabled': lexical_enabled,
                'lexical_auto_disabled': lexical_auto_disabled,
                'created_at': _utc_now(),
            },
        )
        background_tasks.add_task(
            _emit_async_job,
            job_id,
            vid,
            ns,
            title,
            tuned,
            copy.deepcopy(chunks),
            lexical_enabled,
            batch_size,
        )
        return {
            'ok': True,
            'video_id': vid,
            'chunks': len(chunks),
            'async': True,
            'job_id': job_id,
            'lexical_enabled': lexical_enabled,
            'lexical_auto_disabled': lexical_auto_disabled,
            'profile': (tuned or {}).get('profile') if tuned else None,
        }

    try:
        up = _upsert_chunks_to_hirag(chunks, lexical=lexical_enabled, batch_size=batch_size)
    except Exception as exc:
        raise HTTPException(502, f"upsert-batch failed: {exc}")

    try:
        _emit_geometry_event(vid, chunks, title, ns)
    except Exception as exc:
        raise HTTPException(502, f"CGP emit failed: {exc}")

    return {
        'ok': True,
        'video_id': vid,
        'chunks': len(chunks),
        'upserted': up.get('upserted'),
        'lexical_indexed': up.get('lexical_indexed'),
        'profile': (tuned or {}).get('profile') if tuned else None,
        'lexical_auto_disabled': lexical_auto_disabled,
    }


@app.get('/yt/emit/status/{job_id}')
def yt_emit_status(job_id: str):
    job = _get_emit_job(job_id)
    if not job:
        raise HTTPException(404, 'job not found')
    return {'ok': True, 'job': job}

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
