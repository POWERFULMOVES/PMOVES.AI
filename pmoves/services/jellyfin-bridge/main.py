import asyncio
import contextlib
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from difflib import SequenceMatcher
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
import httpx
from urllib.parse import urlencode
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle Management
# ─────────────────────────────────────────────────────────────────────────────
_autolink_task = None


def _on_autolink_done(task: asyncio.Task) -> None:
    """Log if the autolink background task dies unexpectedly."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        LOGGER.error("Autolink background task died: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan for Jellyfin Bridge."""
    global _autolink_task
    # Startup
    if AUTOLINK and JELLYFIN_URL and JELLYFIN_API_KEY and JELLYFIN_USER_ID:
        _autolink_task = asyncio.create_task(_autolink_loop())
        _autolink_task.add_done_callback(_on_autolink_done)

    yield

    # Shutdown
    if _autolink_task and not _autolink_task.done():
        _autolink_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _autolink_task


app = FastAPI(title="Jellyfin Bridge", version="0.1.0", lifespan=lifespan)

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus Metrics
# ─────────────────────────────────────────────────────────────────────────────
JELLYFIN_REQUESTS = Counter(
    "jellyfin_bridge_requests_total",
    "Total Jellyfin Bridge requests",
    ["endpoint", "status"]
)
JELLYFIN_SEARCH_LATENCY = Histogram(
    "jellyfin_bridge_search_latency_seconds",
    "Jellyfin search latency in seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)
JELLYFIN_LINKS = Counter(
    "jellyfin_bridge_links_total",
    "Total Jellyfin video link operations",
    ["result"]
)
JELLYFIN_NOTEBOOK_PUBLISHES = Counter(
    "jellyfin_bridge_notebook_publishes_total",
    "Total Open Notebook publish attempts",
    ["status"]
)

LOGGER = logging.getLogger("jellyfin_bridge")

# ---------------------------------------------------------------------------
# Open Notebook Publishing Configuration
# ---------------------------------------------------------------------------
OPEN_NOTEBOOK_API_URL = os.environ.get("OPEN_NOTEBOOK_API_URL", "")
OPEN_NOTEBOOK_API_TOKEN = os.environ.get("OPEN_NOTEBOOK_API_TOKEN", "")
OPEN_NOTEBOOK_NOTEBOOK_ID = os.environ.get("OPEN_NOTEBOOK_NOTEBOOK_ID", "") or os.environ.get("DEEPRESEARCH_NOTEBOOK_ID", "")
JELLYFIN_NOTEBOOK_PUBLISH = os.environ.get("JELLYFIN_NOTEBOOK_PUBLISH", "true").lower() in {"1", "true", "yes", "on"}

# Initialize notebook publisher if available
_notebook_publisher = None
try:
    from libs.notebook_publisher import NotebookPublisher
    if OPEN_NOTEBOOK_API_URL and OPEN_NOTEBOOK_API_TOKEN and JELLYFIN_NOTEBOOK_PUBLISH:
        _notebook_publisher = NotebookPublisher(
            base_url=OPEN_NOTEBOOK_API_URL,
            api_token=OPEN_NOTEBOOK_API_TOKEN,
            notebook_id=OPEN_NOTEBOOK_NOTEBOOK_ID,
        )
        LOGGER.info("Open Notebook publisher initialized for Jellyfin bridge")
except ImportError:
    LOGGER.info("notebook_publisher library not available")

def _parse_env_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        source: Iterable[str] = value.split(",")
    else:
        source = value  # pragma: no cover - defensive fallback
    return [str(part).strip() for part in source if str(part).strip()]


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ensure_list(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(value).strip()]


def _bool_param(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).lower() in {"1", "true", "yes", "on"}


_TITLE_SANITIZER = re.compile(r"[^a-z0-9]+")


def _normalize_title(value: Optional[str]) -> str:
    if not value:
        return ""
    return _TITLE_SANITIZER.sub(" ", value.lower()).strip()


JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "")
JELLYFIN_API_KEY = os.environ.get("JELLYFIN_API_KEY", "")
JELLYFIN_USER_ID = os.environ.get("JELLYFIN_USER_ID", "")
SUPA = os.environ.get("SUPA_REST_URL", "http://postgrest:3000")
AUTOLINK = os.environ.get("JELLYFIN_AUTOLINK", "false").lower() == "true"
AUTOLINK_SEC = float(os.environ.get("AUTOLINK_INTERVAL_SEC", "60"))
DEFAULT_MEDIA_TYPES = _parse_env_list(os.environ.get("JELLYFIN_DEFAULT_MEDIA_TYPES", "Movie,Video"))
DEFAULT_LIBRARY_IDS = _parse_env_list(os.environ.get("JELLYFIN_DEFAULT_LIBRARY_IDS"))
JELLYFIN_SERVER_ID = os.environ.get("JELLYFIN_SERVER_ID", "local")
JELLYFIN_DEVICE_ID = os.environ.get("JELLYFIN_DEVICE_ID", "")

_BRANDING_FIELD_METADATA: Dict[str, Dict[str, str]] = {
    "brand_name": {
        "env": "JELLYFIN_BRAND_NAME",
        "default": "PMOVES Jellyfin",
        "description": "Primary title shown at the top of the admin dashboard.",
    },
    "brand_tagline": {
        "env": "JELLYFIN_BRAND_TAGLINE",
        "default": "Curate, sync, and stream",
        "description": "Subtitle displayed beneath the admin title and on login panels.",
    },
    "primary_color": {
        "env": "JELLYFIN_BRAND_PRIMARY_COLOR",
        "default": "#1F2937",
        "description": "Background color for primary navigation and headers.",
    },
    "accent_color": {
        "env": "JELLYFIN_BRAND_ACCENT_COLOR",
        "default": "#38BDF8",
        "description": "Accent color applied to buttons, toggles, and focused form elements.",
    },
    "logo_url": {
        "env": "JELLYFIN_BRAND_LOGO_URL",
        "default": "",
        "description": "URL to the square logo rendered in the admin header.",
    },
    "background_url": {
        "env": "JELLYFIN_BRAND_BACKGROUND_URL",
        "default": "",
        "description": "Hero background image displayed on admin login and landing cards.",
    },
    "support_link": {
        "env": "JELLYFIN_BRAND_SUPPORT_LINK",
        "default": "",
        "description": "External link for help / support surfaced in the admin footer.",
    },
    "theme_pack": {
        "env": "JELLYFIN_BRAND_THEME_PACK",
        "default": "transformers-1986",
        "description": "Active TAC theme pack from agent-themes.yaml.",
    },
    "custom_css": {
        "env": "JELLYFIN_BRAND_CUSTOM_CSS",
        "default": "",
        "description": "Generated CSS from TAC tree (auto-populated on theme apply).",
    },
}

BRANDING_DEFAULTS: Dict[str, str] = {
    key: os.environ.get(meta["env"], meta["default"])
    for key, meta in _BRANDING_FIELD_METADATA.items()
}

BRANDING_TABLE = os.environ.get("JELLYFIN_BRANDING_TABLE", "")
BRANDING_KEY = os.environ.get("JELLYFIN_BRANDING_KEY", "default")
BRANDING_KEY_COLUMN = os.environ.get("JELLYFIN_BRANDING_KEY_COLUMN", "key")
BRANDING_VALUE_COLUMN = os.environ.get("JELLYFIN_BRANDING_VALUE_COLUMN", "value")

_BRANDING_LOCK = Lock()
_BRANDING_STATE: Dict[str, str] = dict(BRANDING_DEFAULTS)
_BRANDING_LOADED = False


def _ensure_jellyfin_credentials() -> None:
    if not (JELLYFIN_URL and JELLYFIN_API_KEY and JELLYFIN_USER_ID):
        raise HTTPException(412, "JELLYFIN_URL, JELLYFIN_API_KEY, and JELLYFIN_USER_ID required")

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

def _supa_patch(table: str, match: Dict[str, Any], patch: Dict[str, Any]):
    qs = []
    for k, v in match.items():
        if isinstance(v, str):
            qs.append(f"{k}=eq.{v}")
        else:
            qs.append(f"{k}=eq.{json.dumps(v)}")
    url = f"{SUPA}/{table}?" + "&".join(qs)
    r = httpx.patch(url, json=patch, timeout=10)
    r.raise_for_status()
    if not r.content:
        return {}
    try:
        return r.json()
    except json.JSONDecodeError:
        return {}

def _supa_get(table: str, match: Dict[str, Any]):
    qs = []
    for k, v in match.items():
        if isinstance(v, str):
            qs.append(f"{k}=eq.{v}")
        else:
            qs.append(f"{k}=eq.{json.dumps(v)}")
    url = f"{SUPA}/{table}?" + "&".join(qs)
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def _supa_upsert(table: str, rows: List[Dict[str, Any]]):
    url = f"{SUPA}/{table}"
    headers = {"Prefer": "return=representation,resolution=merge-duplicates"}
    r = httpx.post(url, json=rows, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


_BRANDING_LOAD_FAILED = object()


def _load_branding_from_supa() -> Dict[str, Any] | object:
    if not BRANDING_TABLE:
        return {}
    try:
        rows = _supa_get(BRANDING_TABLE, {BRANDING_KEY_COLUMN: BRANDING_KEY})
    except Exception as exc:
        LOGGER.error("Branding load from Supabase failed: %s", exc)
        return _BRANDING_LOAD_FAILED
    if not rows:
        return {}
    raw = rows[0].get(BRANDING_VALUE_COLUMN)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _persist_branding_state(state: Dict[str, str]) -> None:
    if not BRANDING_TABLE:
        return
    payload = {
        BRANDING_KEY_COLUMN: BRANDING_KEY,
        BRANDING_VALUE_COLUMN: state,
    }
    try:
        _supa_upsert(BRANDING_TABLE, [payload])
    except Exception as exc:
        LOGGER.error("Branding persistence failed: %s", exc)


def _ensure_branding_loaded() -> None:
    global _BRANDING_LOADED
    if _BRANDING_LOADED:
        return
    if not BRANDING_TABLE:
        _BRANDING_LOADED = True
        return
    data = _load_branding_from_supa()
    if data is _BRANDING_LOAD_FAILED:
        # Supabase failed — do NOT set flag, retry next call
        return
    if isinstance(data, dict) and data:
        with _BRANDING_LOCK:
            for key, value in data.items():
                if key in _BRANDING_STATE and value is not None:
                    _BRANDING_STATE[key] = str(value)
    _BRANDING_LOADED = True


def _get_branding_state() -> Dict[str, str]:
    _ensure_branding_loaded()
    with _BRANDING_LOCK:
        return dict(_BRANDING_STATE)


def _update_branding_state(updates: Dict[str, Any]) -> Dict[str, str]:
    if not updates:
        return _get_branding_state()
    _ensure_branding_loaded()
    normalized: Dict[str, str] = {}
    for key, value in updates.items():
        if key not in BRANDING_DEFAULTS:
            continue
        if value is None:
            normalized[key] = BRANDING_DEFAULTS.get(key, "")
        else:
            normalized[key] = str(value)
    if not normalized:
        return _get_branding_state()
    with _BRANDING_LOCK:
        _BRANDING_STATE.update(normalized)
        snapshot = dict(_BRANDING_STATE)
    _persist_branding_state(snapshot)
    return snapshot


def _branding_fields_schema() -> List[Dict[str, str]]:
    schema: List[Dict[str, str]] = []
    for key, meta in _BRANDING_FIELD_METADATA.items():
        schema.append(
            {
                "name": key,
                "label": key.replace("_", " ").title(),
                "env": meta.get("env", ""),
                "default": BRANDING_DEFAULTS.get(key, ""),
                "description": meta.get("description", ""),
            }
        )
    return schema


def _normalize_search_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = filters or {}
    normalized: Dict[str, Any] = {}
    library_value = (
        payload.get("library_ids")
        or payload.get("library_scope")
        or payload.get("library_scopes")
    )
    normalized["library_ids"] = _ensure_list(library_value)
    include_value = payload.get("include_item_types") or payload.get("media_types")
    normalized["include_item_types"] = _ensure_list(include_value)
    normalized["exclude_item_types"] = _ensure_list(payload.get("exclude_item_types"))
    normalized["fields"] = _ensure_list(payload.get("fields"))
    normalized["sort_by"] = _ensure_list(payload.get("sort_by"))
    normalized["sort_order"] = _ensure_list(payload.get("sort_order"))
    normalized["parent_id"] = payload.get("parent_id") or payload.get("collection_id")
    normalized["year"] = _safe_int(payload.get("year") or payload.get("production_year"))
    normalized["limit"] = _safe_int(payload.get("limit")) or 25
    normalized["recursive"] = _bool_param(payload.get("recursive"), True)
    normalized["enable_images"] = payload.get("enable_images")
    return normalized


def _build_search_params(query: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    normalized = _normalize_search_filters(filters)
    params: Dict[str, str] = {
        "searchTerm": query,
        "Limit": str(normalized.get("limit", 25)),
        "Recursive": "true" if normalized.get("recursive", True) else "false",
    }
    include_types = normalized.get("include_item_types")
    if not include_types:
        include_types = DEFAULT_MEDIA_TYPES
    if include_types:
        params["IncludeItemTypes"] = ",".join(include_types)
    library_ids = normalized.get("library_ids")
    if not library_ids:
        library_ids = DEFAULT_LIBRARY_IDS
    if library_ids:
        params["LibraryIds"] = ",".join(library_ids)
    exclude_types = normalized.get("exclude_item_types")
    if exclude_types:
        params["ExcludeItemTypes"] = ",".join(exclude_types)
    fields = normalized.get("fields")
    if fields:
        params["Fields"] = ",".join(fields)
    sort_by = normalized.get("sort_by")
    if sort_by:
        params["SortBy"] = ",".join(sort_by)
    sort_order = normalized.get("sort_order")
    if sort_order:
        params["SortOrder"] = ",".join(sort_order)
    if normalized.get("parent_id"):
        params["ParentId"] = str(normalized["parent_id"])
    if normalized.get("year"):
        params["Years"] = str(normalized["year"])
    enable_images = normalized.get("enable_images")
    if enable_images is not None:
        params["EnableImages"] = "true" if _bool_param(enable_images, True) else "false"
    return params


def _search_jellyfin(query: str, filters: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    if not (JELLYFIN_URL and JELLYFIN_API_KEY and JELLYFIN_USER_ID):
        raise HTTPException(412, "JELLYFIN_URL, JELLYFIN_API_KEY, and JELLYFIN_USER_ID required")
    params = _build_search_params(query, filters)
    params.setdefault("api_key", JELLYFIN_API_KEY)
    try:
        r = httpx.get(
            f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items",
            params=params,
            headers={
                "X-Emby-Authorization": (
                    'MediaBrowser Client="PMOVES Bridge", Device="PMOVES Bridge", '
                    'DeviceId="pmoves-jellyfin-bridge", Version="1.0", '
                    f'Token="{JELLYFIN_API_KEY}"'
                ),
                "Accept": "application/json",
            },
            timeout=8,
        )
        r.raise_for_status()
    except Exception as exc:  # pragma: no cover - network errors not deterministic
        raise HTTPException(502, f"jellyfin search error: {exc}")
    payload = r.json()
    items = payload.get("Items") or []
    return items, params


def _serialize_jellyfin_item(item: Dict[str, Any]) -> Dict[str, Any]:
    image_tags = item.get("ImageTags") if isinstance(item.get("ImageTags"), dict) else {}
    data = {
        "Id": item.get("Id"),
        "Name": item.get("Name"),
        "ProductionYear": item.get("ProductionYear"),
        "Type": item.get("Type"),
        "MediaType": item.get("MediaType"),
        "RunTimeTicks": item.get("RunTimeTicks"),
        "Path": item.get("Path"),
        "Overview": item.get("Overview"),
        "SeriesName": item.get("SeriesName"),
        "ParentId": item.get("ParentId"),
        "PrimaryImageTag": image_tags.get("Primary") if isinstance(image_tags, dict) else None,
    }
    return {k: v for k, v in data.items() if v not in (None, "")}


def _score_match(title_norm: str, candidate: Dict[str, Any], target_year: Optional[int] = None) -> float:
    name_norm = _normalize_title(candidate.get("Name"))
    score = SequenceMatcher(None, title_norm, name_norm).ratio() if (title_norm and name_norm) else 0.0
    if title_norm and name_norm and (title_norm in name_norm or name_norm in title_norm):
        score += 0.2
    alternate_sources: List[str] = []
    original_title = candidate.get("OriginalTitle")
    if isinstance(original_title, str):
        alternate_sources.append(_normalize_title(original_title))
    alt_list = candidate.get("AlternateTitles") or candidate.get("AlternateTitle")
    if isinstance(alt_list, list):
        alternate_sources.extend(_normalize_title(val) for val in alt_list if isinstance(val, str))
    for alt in alternate_sources:
        if alt:
            score = max(score, SequenceMatcher(None, title_norm, alt).ratio())
    production_year = _safe_int(candidate.get("ProductionYear"))
    if target_year:
        if production_year == target_year:
            score += 0.15
        elif production_year:
            score -= 0.05
    return score


def _pick_best_match(title: str, items: List[Dict[str, Any]], target_year: Optional[int] = None) -> Optional[Tuple[Dict[str, Any], float]]:
    if not items:
        return None
    title_norm = _normalize_title(title)
    if not title_norm:
        return None
    best_item: Optional[Dict[str, Any]] = None
    best_score = -1.0
    for candidate in items:
        score = _score_match(title_norm, candidate, target_year)
        if score > best_score:
            best_score = score
            best_item = candidate
    if not best_item:
        return None
    threshold = 0.25 if len(items) > 1 else 0.15
    if best_score < threshold:
        return None
    return best_item, best_score


def _publish_to_notebook_sync(
    title: str,
    media_type: str,
    overview: Optional[str] = None,
    year: Optional[int] = None,
    runtime_ticks: Optional[int] = None,
    jellyfin_item_id: Optional[str] = None,
) -> Optional[str]:
    """Sync wrapper to publish Jellyfin media to Open Notebook."""
    if not _notebook_publisher:
        return None
    try:
        # Convert runtime ticks to minutes (1 tick = 100 nanoseconds)
        duration_minutes = None
        if runtime_ticks:
            duration_minutes = int(runtime_ticks // 600_000_000)

        # Build poster URL if available
        poster_url = None
        if jellyfin_item_id and JELLYFIN_URL:
            poster_url = f"{JELLYFIN_URL}/Items/{jellyfin_item_id}/Images/Primary"

        async def _async_publish():
            return await _notebook_publisher.publish_media(
                title=title,
                media_type=media_type,
                description=overview,
                poster_url=poster_url,
                year=year,
                duration_minutes=duration_minutes,
            )

        # Run async publisher from sync context
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, schedule on the existing loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _async_publish())
                entry_id, error = future.result(timeout=15)
        except RuntimeError:
            # No running loop, we can use asyncio.run directly
            entry_id, error = asyncio.run(_async_publish())

        if error:
            JELLYFIN_NOTEBOOK_PUBLISHES.labels(status="error").inc()
            LOGGER.warning("Notebook publish failed for '%s': %s", title, error)
        elif entry_id:
            LOGGER.info("Published to Open Notebook: %s (id=%s)", title, entry_id)
        return entry_id
    except Exception as e:
        JELLYFIN_NOTEBOOK_PUBLISHES.labels(status="error").inc()
        LOGGER.warning("Notebook publish error for '%s': %s", title, e)
        return None

@app.post("/jellyfin/link")
def jellyfin_link(body: Dict[str,Any] = Body(...)):
    vid = body.get('video_id'); item = body.get('jellyfin_item_id')
    if not vid or not item:
        JELLYFIN_REQUESTS.labels(endpoint="link", status="error").inc()
        raise HTTPException(400, 'video_id and jellyfin_item_id required')
    patch = {"meta": {"jellyfin_item_id": item}}
    _supa_patch('videos', {'video_id': vid}, patch)
    JELLYFIN_LINKS.labels(result="success").inc()
    JELLYFIN_REQUESTS.labels(endpoint="link", status="success").inc()
    return {"ok": True}

@app.post("/jellyfin/refresh")
def jellyfin_refresh(body: Dict[str,Any] = Body({})):
    # Best-effort: call System/Info if creds provided; otherwise noop
    if not JELLYFIN_URL or not JELLYFIN_API_KEY:
        return {"ok": True, "skipped": True}
    try:
        r = httpx.get(f"{JELLYFIN_URL}/System/Info", headers={"X-Emby-Token": JELLYFIN_API_KEY}, timeout=6)
        r.raise_for_status()
        return {"ok": True, "system": r.json().get('Version')}
    except Exception as e:
        raise HTTPException(502, f"jellyfin error: {e}")

@app.post("/jellyfin/playback-url")
def jellyfin_playback_url(body: Dict[str, Any] = Body(...)):
    vid = body.get("video_id")
    if not vid:
        raise HTTPException(400, "video_id required")
    try:
        t = float(body.get("t") or 0.0)
    except (TypeError, ValueError):
        raise HTTPException(400, "t must be numeric")
    rows = _supa_get("videos", {"video_id": vid})
    if not rows:
        raise HTTPException(404, "video not found")
    record = rows[0]
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    item = body.get("jellyfin_item_id") or meta.get("jellyfin_item_id")
    if not item and not JELLYFIN_URL:
        return {"ok": True, "url": f"/web/player?video_id={vid}&t={t}"}
    if not (item and JELLYFIN_URL):
        raise HTTPException(412, "missing jellyfin mapping or JELLYFIN_URL")
    media_source_id = body.get("media_source_id") or meta.get("jellyfin_media_source_id")
    server_id = body.get("server_id") or meta.get("jellyfin_server_id") or JELLYFIN_SERVER_ID
    device_id = body.get("device_id") or meta.get("jellyfin_device_id") or JELLYFIN_DEVICE_ID
    playback_type = body.get("playback_type") or meta.get("jellyfin_playback_type")
    audio_stream_index = body.get("audio_stream_index") or meta.get("jellyfin_audio_stream_index")
    subtitle_stream_index = body.get("subtitle_stream_index") or meta.get("jellyfin_subtitle_stream_index")
    ticks = max(0, int(round(t * 10_000_000)))
    start_seconds = max(0, int(round(t)))
    params: Dict[str, str] = {
        "id": str(item),
        "serverId": str(server_id or ""),
        "startTimeTicks": str(ticks),
        "startTime": str(start_seconds),
    }
    if media_source_id:
        params["mediaSourceId"] = str(media_source_id)
    if device_id:
        params["deviceId"] = str(device_id)
    if playback_type:
        params["playbackType"] = str(playback_type)
    if audio_stream_index is not None:
        params["audioStreamIndex"] = str(audio_stream_index)
    if subtitle_stream_index is not None:
        params["subtitleStreamIndex"] = str(subtitle_stream_index)
    url = f"{JELLYFIN_URL}/web/index.html#!/details?{urlencode(params)}"
    return {"ok": True, "url": url, "params": params}

@app.get("/jellyfin/search")
def jellyfin_search(
    query: str,
    library_ids: Optional[List[str]] = Query(None, description="Limit results to specific library IDs."),
    library_scope: Optional[List[str]] = Query(None, description="Alias for library_ids when multiple scopes are provided."),
    media_types: Optional[List[str]] = Query(None, description="Shorthand for include_item_types."),
    include_item_types: Optional[List[str]] = Query(None, description="Explicit Jellyfin item types to include."),
    exclude_item_types: Optional[List[str]] = Query(None, description="Jellyfin item types to exclude."),
    fields: Optional[List[str]] = Query(None, description="Additional Jellyfin fields to request."),
    sort_by: Optional[List[str]] = Query(None, description="SortBy values (e.g., ProductionYear, SortName)."),
    sort_order: Optional[List[str]] = Query(None, description="SortOrder values (Ascending or Descending)."),
    parent_id: Optional[str] = Query(None, description="Restrict results to a specific parent collection."),
    year: Optional[int] = Query(None, description="Preferred production year."),
    recursive: bool = Query(True, description="Traverse child libraries recursively."),
    limit: int = Query(25, ge=1, le=200, description="Maximum number of results to return."),
):
    start = time.time()
    try:
        _ensure_jellyfin_credentials()
        filters: Dict[str, Any] = {
            "library_ids": library_ids,
            "library_scope": library_scope,
            "media_types": media_types,
            "include_item_types": include_item_types,
            "exclude_item_types": exclude_item_types,
            "fields": fields,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "parent_id": parent_id,
            "year": year,
            "recursive": recursive,
            "limit": limit,
        }
        items, params = _search_jellyfin(query, filters)
        serialized = [_serialize_jellyfin_item(item) for item in items]
        JELLYFIN_REQUESTS.labels(endpoint="search", status="success").inc()
        return {"ok": True, "items": serialized, "applied_filters": params}
    except HTTPException:
        JELLYFIN_REQUESTS.labels(endpoint="search", status="error").inc()
        raise
    finally:
        JELLYFIN_SEARCH_LATENCY.observe(time.time() - start)

@app.post("/jellyfin/map-by-title")
def jellyfin_map_by_title(body: Dict[str, Any] = Body(...)):
    start = time.time()
    vid = body.get("video_id")
    if not vid:
        JELLYFIN_REQUESTS.labels(endpoint="map-by-title", status="error").inc()
        raise HTTPException(400, "video_id required")
    rows = _supa_get("videos", {"video_id": vid})
    if not rows:
        raise HTTPException(404, "video not found")
    record = rows[0]
    title = body.get("title") or record.get("title")
    if not title:
        raise HTTPException(400, "title missing for video")
    _ensure_jellyfin_credentials()
    base_filters = dict(body.get("search_filters") or {})
    for alias in ("library_ids", "library_scope", "library_scopes"):
        if body.get(alias) is not None and alias not in base_filters:
            base_filters[alias] = body.get(alias)
    for alias in ("media_types", "include_item_types", "exclude_item_types", "fields", "sort_by", "sort_order"):
        if body.get(alias) is not None and alias not in base_filters:
            base_filters[alias] = body.get(alias)
    if body.get("year") is not None and base_filters.get("year") is None:
        base_filters["year"] = body.get("year")
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    release_year = _safe_int(meta.get("release_year") or meta.get("year"))
    if release_year and base_filters.get("year") is None:
        base_filters["year"] = release_year
    items, params = _search_jellyfin(title, base_filters)
    target_year = _safe_int(base_filters.get("year"))
    match = _pick_best_match(title, items, target_year)
    if not match:
        raise HTTPException(404, "no jellyfin items matched")
    best_item, score = match
    updated_meta = dict(meta)
    updated_meta.update({
        "jellyfin_item_id": best_item.get("Id"),
        "jellyfin_media_type": best_item.get("Type"),
        "jellyfin_production_year": best_item.get("ProductionYear"),
        "jellyfin_match_score": round(float(score), 4),
    })
    if best_item.get("Path"):
        updated_meta["jellyfin_path"] = best_item.get("Path")
    library_ids = _ensure_list(base_filters.get("library_ids") or base_filters.get("library_scope") or base_filters.get("library_scopes"))
    if library_ids:
        updated_meta["jellyfin_library_ids"] = library_ids
    _supa_patch("videos", {"video_id": vid}, {"meta": updated_meta})

    # Publish to Open Notebook (best-effort, non-blocking)
    notebook_entry_id = None
    if _notebook_publisher:
        notebook_entry_id = _publish_to_notebook_sync(
            title=best_item.get("Name") or title,
            media_type=best_item.get("Type") or "Video",
            overview=best_item.get("Overview"),
            year=_safe_int(best_item.get("ProductionYear")),
            runtime_ticks=_safe_int(best_item.get("RunTimeTicks")),
            jellyfin_item_id=best_item.get("Id"),
        )

    JELLYFIN_LINKS.labels(result="mapped").inc()
    JELLYFIN_REQUESTS.labels(endpoint="map-by-title", status="success").inc()
    JELLYFIN_SEARCH_LATENCY.observe(time.time() - start)

    result: Dict[str, Any] = {
        "ok": True,
        "mapped": {
            "video_id": vid,
            "jellyfin_item_id": best_item.get("Id"),
            "name": best_item.get("Name"),
            "score": round(float(score), 4),
        },
        "applied_filters": params,
    }
    if notebook_entry_id:
        result["notebook_entry_id"] = notebook_entry_id
        JELLYFIN_NOTEBOOK_PUBLISHES.labels(status="success").inc()
    return result


@app.get("/jellyfin/branding")
def jellyfin_branding():
    return {"ok": True, "branding": _get_branding_state(), "fields": _branding_fields_schema()}


@app.post("/jellyfin/branding")
def update_jellyfin_branding(body: Dict[str, Any] = Body(...)):
    if body.get("reset"):
        reset_state = {key: BRANDING_DEFAULTS.get(key, "") for key in BRANDING_DEFAULTS}
        branding = _update_branding_state(reset_state)
        return {"ok": True, "branding": branding, "reset": True}
    updates = {key: body[key] for key in body if key in BRANDING_DEFAULTS}
    if not updates:
        raise HTTPException(400, "no branding fields supplied")
    branding = _update_branding_state(updates)
    return {"ok": True, "branding": branding, "updated": list(updates.keys())}


# ─────────────────────────────────────────────────────────────────────────────
# TAC Tree — Theme-Agent-Character Theming
# ─────────────────────────────────────────────────────────────────────────────
try:
    from . import tac_tree as _tac
except ImportError:
    import tac_tree as _tac  # type: ignore[no-redef]

TAC_REQUESTS = Counter(
    "jellyfin_bridge_tac_requests_total",
    "Total TAC tree theme requests",
    ["endpoint", "status"],
)


@app.get("/jellyfin/theme/tac-tree")
def jellyfin_tac_tree():
    """Return the full TAC tree structure (theme packs + agent mappings)."""
    try:
        tree = _tac.get_tac_tree()
        TAC_REQUESTS.labels(endpoint="tac_tree", status="ok").inc()
        return {"ok": True, "tac_tree": tree}
    except Exception as exc:
        TAC_REQUESTS.labels(endpoint="tac_tree", status="error").inc()
        raise HTTPException(500, f"TAC tree load failed: {exc}")


@app.get("/jellyfin/theme/packs")
def jellyfin_theme_packs():
    """List available theme packs."""
    return {"ok": True, "packs": _tac.list_theme_packs()}


@app.get("/jellyfin/theme/preview/{agent_key}")
def jellyfin_theme_preview(
    agent_key: str,
    theme_pack: Optional[str] = None,
    target: str = Query(default="jellyfin", description="CSS target: jellyfin, grafana, dashboard, vars-only"),
):
    """Preview TAC tree CSS for an agent without applying it."""
    css = _tac.generate_tac_css(theme_pack=theme_pack, agent_key=agent_key, target=target)
    mapping = _tac.resolve_agent_mapping(agent_key)
    palette = _tac.resolve_palette(agent_key, theme_pack)
    return {"ok": True, "agent": agent_key, "target": target, "css": css, "palette": palette, "mapping": mapping}


@app.get("/jellyfin/theme/manifest/{agent_key}")
def jellyfin_theme_manifest(agent_key: str, theme_pack: Optional[str] = None):
    """Return JSON color manifest for programmatic consumption (non-CSS targets)."""
    manifest = _tac.generate_color_manifest(agent_key=agent_key, theme_pack=theme_pack)
    return {"ok": True, "manifest": manifest}


@app.get("/jellyfin/theme/card/{agent_key}")
def jellyfin_theme_card(agent_key: str):
    """Return agent card theming data for the agent-card-gen FlOO$ pairing."""
    card = _tac.generate_agent_card_theme(agent_key)
    return {"ok": True, "card": card}


@app.get("/jellyfin/theme/agents/{theme_pack}")
def jellyfin_theme_agents_for_pack(theme_pack: str):
    """List all agents using characters from a given theme pack."""
    agents = _tac.list_agents_for_pack(theme_pack)
    return {"ok": True, "theme_pack": theme_pack, "agents": agents, "count": len(agents)}


@app.post("/jellyfin/theme/apply")
def jellyfin_theme_apply(body: Dict[str, Any] = Body(...)):
    """Generate TAC CSS and push it to Jellyfin's branding configuration.

    Body: {"theme_pack": "transformers-1986", "agent": "jellyfin-ai", "target": "jellyfin"}
    """
    agent_key = body.get("agent", "jellyfin-ai")
    theme_pack = body.get("theme_pack")
    target = body.get("target", "jellyfin")

    css = _tac.generate_tac_css(theme_pack=theme_pack, agent_key=agent_key, target=target)
    if not css or css.startswith("/* TAC tree: no mapping"):
        TAC_REQUESTS.labels(endpoint="apply", status="not_found").inc()
        raise HTTPException(404, f"No TAC mapping for agent '{agent_key}'")

    # Push CSS to Jellyfin branding API
    applied_to_jellyfin = False
    if JELLYFIN_URL and JELLYFIN_API_KEY:
        try:
            branding_url = f"{JELLYFIN_URL}/System/Configuration/branding"
            headers = {"X-Emby-Token": JELLYFIN_API_KEY, "Content-Type": "application/json"}
            # Fetch current branding config
            current = httpx.get(branding_url, headers=headers, timeout=8)
            current.raise_for_status()
            branding_config = current.json()
            branding_config["CustomCss"] = css
            # Push updated config
            resp = httpx.post(branding_url, json=branding_config, headers=headers, timeout=8)
            resp.raise_for_status()
            applied_to_jellyfin = True
        except Exception as exc:
            LOGGER.warning("Failed to push TAC CSS to Jellyfin: %s", exc)

    # Update branding state
    _update_branding_state({
        "theme_pack": theme_pack or "default",
        "custom_css": css[:500],  # Truncate for state storage
    })

    TAC_REQUESTS.labels(endpoint="apply", status="ok").inc()
    return {
        "ok": True,
        "agent": agent_key,
        "theme_pack": theme_pack,
        "applied_to_jellyfin": applied_to_jellyfin,
        "css_length": len(css),
    }


@app.get("/jellyfin/config")
def jellyfin_config():
    return {
        "ok": True,
        "search_defaults": {
            "library_ids": list(DEFAULT_LIBRARY_IDS),
            "media_types": list(DEFAULT_MEDIA_TYPES),
            "server_id": JELLYFIN_SERVER_ID,
            "device_id": JELLYFIN_DEVICE_ID,
        },
        "branding": _get_branding_state(),
        "branding_fields": _branding_fields_schema(),
    }

# ─────────────────────────────────────────────────────────────────────────────
# YouTube Station Management
# ─────────────────────────────────────────────────────────────────────────────
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")

STATION_REQUESTS = Counter(
    "jellyfin_bridge_station_requests_total",
    "Total station management requests",
    ["endpoint", "status"],
)


STATION_SECRET = os.environ.get("STATION_MGMT_SECRET", "")
_CHANNEL_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _supa_headers():
    svc_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    return {
        "apikey": svc_key,
        "Authorization": f"Bearer {svc_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _check_station_auth(request: Request) -> None:
    """Validate bearer token for station management endpoints."""
    if not STATION_SECRET:
        raise HTTPException(status_code=503, detail="Station management not configured")
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != STATION_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _validate_channel_id(channel_id: str) -> str:
    if not _CHANNEL_ID_RE.match(channel_id):
        raise HTTPException(status_code=400, detail="Invalid channel_id format")
    return channel_id


@app.get("/yt/channels")
def yt_channels(request: Request):
    """List subscribed YouTube channels from Supabase."""
    if STATION_SECRET:
        _check_station_auth(request)
    try:
        url = f"{SUPA}/yt_stations?select=*&order=channel_title.asc"
        r = httpx.get(url, headers=_supa_headers(), timeout=10)
        r.raise_for_status()
        STATION_REQUESTS.labels(endpoint="list_channels", status="ok").inc()
        return {"ok": True, "channels": r.json()}
    except HTTPException:
        raise
    except Exception as exc:
        STATION_REQUESTS.labels(endpoint="list_channels", status="error").inc()
        raise HTTPException(status_code=502, detail="Failed to list channels")


@app.post("/yt/channels/{channel_id}/station")
async def yt_create_station(
    channel_id: str,
    request: Request,
    body: dict = Body(...),
):
    """Create an auto-ingest station for a YouTube channel."""
    _check_station_auth(request)
    _validate_channel_id(channel_id)
    try:
        row = {
            "channel_id": channel_id,
            "channel_title": body.get("channel_title", ""),
            "platform": body.get("platform", "youtube"),
            "extractor_key": body.get("extractor_key", ""),
            "active": True,
            "docked": body.get("docked", True),
            "node_id": body.get("node_id"),
        }
        url = f"{SUPA}/yt_stations"
        r = httpx.post(url, headers=_supa_headers(), json=row, timeout=10)
        r.raise_for_status()
        station = r.json()[0] if isinstance(r.json(), list) else r.json()

        await _publish_station_event(channel_id, "station_created", station)

        STATION_REQUESTS.labels(endpoint="create_station", status="ok").inc()
        return {"ok": True, "station": station}
    except HTTPException:
        raise
    except Exception as exc:
        STATION_REQUESTS.labels(endpoint="create_station", status="error").inc()
        raise HTTPException(status_code=502, detail="Station creation failed")


@app.delete("/yt/channels/{channel_id}/station")
async def yt_delete_station(channel_id: str, request: Request):
    """Remove an auto-ingest station."""
    _check_station_auth(request)
    _validate_channel_id(channel_id)
    try:
        from urllib.parse import quote
        url = f"{SUPA}/yt_stations?channel_id=eq.{quote(channel_id, safe='')}"
        r = httpx.delete(url, headers=_supa_headers(), timeout=10)
        r.raise_for_status()

        await _publish_station_event(channel_id, "station_removed", {})

        STATION_REQUESTS.labels(endpoint="delete_station", status="ok").inc()
        return {"ok": True, "channel_id": channel_id}
    except HTTPException:
        raise
    except Exception as exc:
        STATION_REQUESTS.labels(endpoint="delete_station", status="error").inc()
        raise HTTPException(status_code=502, detail="Station deletion failed")


@app.get("/yt/stations")
def yt_stations(request: Request):
    """List active stations with last-ingested timestamp."""
    if STATION_SECRET:
        _check_station_auth(request)
    try:
        url = f"{SUPA}/yt_stations?active=eq.true&select=*&order=last_ingested_at.desc.nullsfirst"
        r = httpx.get(url, headers=_supa_headers(), timeout=10)
        r.raise_for_status()
        STATION_REQUESTS.labels(endpoint="list_stations", status="ok").inc()
        return {"ok": True, "stations": r.json()}
    except HTTPException:
        raise
    except Exception as exc:
        STATION_REQUESTS.labels(endpoint="list_stations", status="error").inc()
        raise HTTPException(status_code=502, detail="Failed to list stations")


NATS_STATION_PUBLISH_FAILURES = Counter(
    "jellyfin_bridge_nats_station_publish_failures_total",
    "NATS publish failures for station events",
)


async def _publish_station_event(channel_id: str, action: str, data: dict) -> None:
    """Publish station change to CHIT geometry bus via NATS."""
    import json as _json
    from nats.aio.client import Client as NATS
    payload = {
        "namespace": "pmoves.media",
        "modality": "station_sync",
        "channel_id": channel_id,
        "action": action,
        "data": data,
    }
    nc = NATS()
    try:
        await nc.connect(servers=[NATS_URL])
        await nc.publish("tokenism.geometry.event.v1", _json.dumps(payload).encode())
        await nc.flush()
    except Exception as exc:
        NATS_STATION_PUBLISH_FAILURES.inc()
        LOGGER.error("NATS publish failed for station event: %s", exc)
    finally:
        await nc.close()


# ─────────────────────────────────────────────────────────────────────────────
# Auto-link Loop
# ─────────────────────────────────────────────────────────────────────────────
def _list_recent_unmapped(limit: int = 25):
    # Fetch recent videos and filter locally for those without jellyfin map
    r = httpx.get(f"{SUPA}/videos?order=id.desc&limit={limit}", timeout=10)
    r.raise_for_status()
    rows = r.json()
    out = []
    for row in rows:
        meta = row.get('meta') or {}
        if not meta.get('jellyfin_item_id'):
            out.append({"video_id": row.get('video_id'), "title": row.get('title')})
    return out

async def _autolink_loop():
    import asyncio
    while True:
        try:
            unmapped = await asyncio.to_thread(_list_recent_unmapped, 25)
            for it in unmapped:
                try:
                    await asyncio.to_thread(
                        jellyfin_map_by_title,
                        {"video_id": it.get('video_id'), "title": it.get('title')},
                    )
                except HTTPException:
                    # Expected: 404 when no match found, 412 when creds missing
                    LOGGER.debug("Autolink skip video_id=%s: %s", it.get('video_id'), "no match or creds missing")
                except Exception:
                    LOGGER.exception("Autolink failed for video_id=%s", it.get('video_id'))
        except Exception:
            LOGGER.exception("Autolink loop iteration failed")
        await asyncio.sleep(AUTOLINK_SEC)
