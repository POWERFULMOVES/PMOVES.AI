import asyncio

import contextlib


import datetime
import json
import logging
import os
import pathlib
import re
import unicodedata
from dataclasses import asdict
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from urllib.parse import urljoin

try:  # pragma: no cover - optional dependency for runtime environments
    import requests
except ImportError:  # pragma: no cover - exercised in tests when requests missing
    requests = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency for runtime environments
    from minio import Minio as _MinioClient
except ImportError:  # pragma: no cover - exercised in tests when minio missing
    _MinioClient = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency for runtime environments
    from nats.aio.client import Client as _NATSClient
except ImportError:  # pragma: no cover - exercised in tests when nats missing
    _NATSClient = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from minio import Minio as MinioClientType
    from nats.aio.client import Client as NATSClientType
else:  # pragma: no cover - typing fallback for runtime when deps absent
    MinioClientType = Any  # type: ignore[misc,assignment]
    NATSClientType = Any  # type: ignore[misc,assignment]

try:  # pragma: no cover - optional shared helper
    from services.common.events import envelope
except Exception:  # pragma: no cover - fallback used in tests without dependency
    import datetime
    import uuid

    def envelope(
        topic: str,
        payload: Dict[str, Any],
        parent_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source: str = "publisher",
    ) -> Dict[str, Any]:
        env: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "topic": topic,
            "version": "v1",
            "ts": datetime.datetime.now(timezone.utc).isoformat() + "Z",
            "source": source,
            "payload": payload,
        }
        if parent_id:
            env["parent_id"] = parent_id
        if correlation_id:
            env["correlation_id"] = correlation_id
        return env


try:  # pragma: no cover - optional Supabase client helper
    from services.common import supabase as supabase_common
except Exception:  # pragma: no cover - Supabase optional in most environments
    supabase_common = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency for runtime environments
    from services.common import supabase as supabase_client
except Exception:  # pragma: no cover - supabase is optional for local/dev testing
    supabase_client = None  # type: ignore[assignment]

from services.common.telemetry import (
    PublisherMetrics,
    PublishTelemetry,
    compute_publish_telemetry,
)

# Optional Prometheus metrics
PROM_ENABLED = False
try:  # pragma: no cover - optional in many environments
    from prometheus_client import (
        Counter as _PromCounter,
        Summary as _PromSummary,
        CollectorRegistry as _PromRegistry,
        generate_latest as _prom_generate,
        CONTENT_TYPE_LATEST as _PROM_CONTENT_TYPE,
    )
    _PROM_REG = _PromRegistry()
    _PROM = {
        "download_success": _PromCounter("publisher_download_success_total", "Successful artifact downloads", registry=_PROM_REG),
        "download_failure": _PromCounter("publisher_download_failure_total", "Failed artifact downloads", registry=_PROM_REG),
        "refresh_attempt": _PromCounter("publisher_refresh_attempts_total", "Jellyfin refresh attempts", registry=_PROM_REG),
        "refresh_success": _PromCounter("publisher_refresh_success_total", "Jellyfin refresh successes", registry=_PROM_REG),
        "refresh_failure": _PromCounter("publisher_refresh_failures_total", "Jellyfin refresh failures", registry=_PROM_REG),
        "turnaround": _PromSummary("publisher_turnaround_seconds", "Publish turnaround seconds", registry=_PROM_REG),
        "approval_latency": _PromSummary("publisher_approval_latency_seconds", "Approval-to-publish latency seconds", registry=_PROM_REG),
    }
    PROM_ENABLED = True
except Exception:
    _PROM = None  # type: ignore[assignment]
    _PROM_REG = None  # type: ignore[assignment]


NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_USE_SSL = os.environ.get("MINIO_USE_SSL", "false").lower() == "true"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "pmoves")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "password")
JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "http://jellyfin:8096")
JELLYFIN_API_KEY = os.environ.get("JELLYFIN_API_KEY")
JELLYFIN_USER_ID = os.environ.get("JELLYFIN_USER_ID")
JELLYFIN_PUBLIC_BASE_URL = os.environ.get("JELLYFIN_PUBLIC_BASE_URL", JELLYFIN_URL)
JELLYFIN_REFRESH_WEBHOOK_URL = os.environ.get("JELLYFIN_REFRESH_WEBHOOK_URL")
JELLYFIN_REFRESH_WEBHOOK_TOKEN = os.environ.get("JELLYFIN_REFRESH_WEBHOOK_TOKEN")
JELLYFIN_REFRESH_DELAY_SEC = float(os.environ.get("JELLYFIN_REFRESH_DELAY_SEC", "0"))
MEDIA_LIBRARY_PATH = os.environ.get("MEDIA_LIBRARY_PATH", "/library/images")
MEDIA_LIBRARY_PUBLIC_BASE_URL = os.environ.get("MEDIA_LIBRARY_PUBLIC_BASE_URL")
DOWNLOAD_RETRIES = int(os.environ.get("PUBLISHER_DOWNLOAD_RETRIES", "3"))
DOWNLOAD_RETRY_BACKOFF_SEC = float(os.environ.get("PUBLISHER_DOWNLOAD_RETRY_BACKOFF", "1.5"))
METRICS_HOST = os.environ.get("PUBLISHER_METRICS_HOST", "0.0.0.0")
METRICS_PORT = int(os.environ.get("PUBLISHER_METRICS_PORT", "9095"))
METRICS_ROLLUP_TABLE = os.environ.get("PUBLISHER_METRICS_TABLE", "publisher_metrics_rollup")
ROLLUP_CONFLICT_COLUMN = os.environ.get("PUBLISHER_METRICS_CONFLICT", "artifact_uri")


logger = logging.getLogger("pmoves.publisher")


def _configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )


METRICS = PublisherMetrics()
_METRICS_SERVER: Optional[asyncio.AbstractServer] = None


class DownloadError(Exception):
    """Raised when an artifact fails to download after retries."""


class JellyfinRefreshError(Exception):
    """Raised when Jellyfin fails to refresh or respond."""

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.details = details or {}

def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _coerce_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_reviewer(payload: Dict[str, Any]) -> Optional[str]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    candidates = [
        payload.get("reviewer"),
        payload.get("approved_by"),
        payload.get("reviewed_by"),
        meta.get("reviewer") if isinstance(meta, dict) else None,
        meta.get("approved_by") if isinstance(meta, dict) else None,
        meta.get("reviewed_by") if isinstance(meta, dict) else None,
    ]
    for candidate in candidates:
        text = _coerce_text(candidate)
        if text:
            return text
    return None


def _extract_reviewed_at(payload: Dict[str, Any], fallback: Optional[str]) -> Optional[str]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    if isinstance(meta, dict):
        for key in ("approved_at", "reviewed_at", "status_changed_at"):
            value = meta.get(key)
            if value:
                return _coerce_text(value)
    return _coerce_text(fallback)


def _combine_meta(base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    meta: Dict[str, Any] = {}
    if isinstance(base, dict):
        meta.update(base)
    if isinstance(extra, dict):
        for key, value in extra.items():
            if value is not None:
                meta[key] = value
    return meta or None


def _describe_exception(exc: BaseException) -> str:
    text = str(exc).strip()
    return text or exc.__class__.__name__


def _record_audit(
    *,
    publish_event_id: Optional[str],
    approval_event_ts: Optional[str],
    correlation_id: Optional[str],
    artifact_uri: Optional[str],
    artifact_path: Optional[str],
    namespace: Optional[str],
    reviewer: Optional[str],
    reviewed_at: Optional[str],
    status: str,
    failure_reason: Optional[str],
    published_event_id: Optional[str] = None,
    public_url: Optional[str] = None,
    published_at: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    if not publish_event_id or supabase_client is None:
        return

    now_iso = _utc_now_iso()
    normalized_failure = _coerce_text(failure_reason)
    if normalized_failure is not None:
        normalized_failure = normalized_failure.strip() or None
    if status == "failed" and not normalized_failure:
        normalized_failure = "unspecified failure"

    row = {
        "publish_event_id": publish_event_id,
        "approval_event_ts": approval_event_ts,
        "correlation_id": correlation_id,
        "artifact_uri": artifact_uri,
        "artifact_path": artifact_path,
        "namespace": namespace,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "status": status,
        "failure_reason": normalized_failure,
        "published_event_id": published_event_id,
        "public_url": public_url,
        "published_at": published_at,
        "processed_at": now_iso,
        "meta": meta or None,
        "updated_at": now_iso,
    }

    try:
        supabase_client.upsert_publisher_audit(row)
    except RuntimeError as exc:  # pragma: no cover - supabase config missing
        logger.debug(
            "Supabase not configured; skipping publisher audit",
            extra={"publish_event_id": publish_event_id},
            exc_info=exc,
        )
    except Exception as exc:  # pragma: no cover - network/driver errors
        logger.warning(
            "Failed to persist publisher audit entry",
            extra={"publish_event_id": publish_event_id, "status": status},
            exc_info=exc,
        )


def parse_s3(uri: str) -> Tuple[str, str]:
    m = re.match(r"^s3://([^/]+)/(.+)$", uri)
    if not m:
        raise ValueError("Bad artifact_uri; expected s3://bucket/key")
    return m.group(1), m.group(2)


def ensure_path(path: str) -> None:
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(value: Optional[str]) -> str:
    raw = value or ""
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_str.lower()
    replaced = _SLUG_PATTERN.sub("-", lowered).strip("-")
    return replaced or "item"


def _normalize_extension(ext: Optional[str]) -> str:
    if not ext:
        return ""
    return ext if ext.startswith(".") else f".{ext}"


def _build_namespace_filename(namespace_slug: str, slug: str, extension: str) -> str:
    slug_part = slug
    if slug_part == namespace_slug:
        return f"{namespace_slug}{extension}"
    if slug_part.startswith(f"{namespace_slug}-") or slug_part.startswith(f"{namespace_slug}--"):
        slug_part = slug_part[len(namespace_slug) + 1 :]
        if slug_part.startswith("-"):
            slug_part = slug_part[1:]
        slug_part = slug_part or namespace_slug
    filename_slug = f"{namespace_slug}--{slug_part}" if slug_part else namespace_slug
    return f"{filename_slug}{extension}"


def derive_output_path(base: str, namespace: Optional[str], slug: str, ext: str) -> str:
    namespace_slug = slugify(namespace or "default")
    slug_value = slugify(slug)
    directory = os.path.join(base, namespace_slug)
    ensure_path(directory)
    extension = _normalize_extension(ext)
    filename = _build_namespace_filename(namespace_slug, slug_value, extension)
    return os.path.join(directory, filename)


def merge_metadata(
    title: str,
    description: Optional[str],
    tags: Optional[Any],
    incoming_meta: Optional[Dict[str, Any]],
    *,
    slug: str,
    namespace_slug: str,
    filename: str,
    extension: str,
    additional_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = dict(incoming_meta or {})
    meta.setdefault("title", title)
    if description:
        meta["description"] = description
    if tags:
        meta["tags"] = list(tags)
    meta.setdefault("slug", slug)
    meta.setdefault("namespace_slug", namespace_slug)
    meta["filename"] = filename
    meta["extension"] = extension.lstrip(".") if extension else ""
    if isinstance(additional_meta, dict):
        for key, value in additional_meta.items():
            if value is not None:
                meta[key] = value
    return meta


def build_published_payload(
    *,
    artifact_uri: str,
    published_path: str,
    namespace: str,
    title: str,
    description: Optional[str],
    tags: Optional[Any],
    incoming_meta: Optional[Dict[str, Any]],
    public_url: Optional[str],
    jellyfin_item_id: Optional[str],
    jellyfin_public_url: Optional[str],
    thumbnail_url: Optional[str],
    duration: Optional[float],
    jellyfin_meta: Optional[Dict[str, Any]],
    slug: str,
    namespace_slug: str,
    filename: str,
    extension: str,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "artifact_uri": artifact_uri,
        "published_path": published_path,
        "namespace": namespace,
    }
    if title:
        payload["title"] = title
    if description:
        payload["description"] = description
    if tags:
        payload["tags"] = list(tags)
    if thumbnail_url:
        payload["thumbnail_url"] = thumbnail_url
    if duration is not None:
        payload["duration"] = duration
    payload: Dict[str, Any] = {
        **payload,
        "meta": merge_metadata(
            title,
            description,
            tags,
            incoming_meta,
            slug=slug,
            namespace_slug=namespace_slug,
            filename=filename,
            extension=extension,
            additional_meta=_combine_meta(
                jellyfin_meta,
                {
                    "thumbnail_url": thumbnail_url,
                    "duration": duration,
                    "jellyfin_public_url": jellyfin_public_url,
                    "jellyfin_item_id": jellyfin_item_id,
                },
            ),
        ),
    }
    if public_url:
        payload["public_url"] = public_url
    if jellyfin_item_id:
        payload["jellyfin_item_id"] = jellyfin_item_id
    if jellyfin_public_url:
        payload["jellyfin_public_url"] = jellyfin_public_url
    return payload


def build_failure_payload(
    *,
    stage: str,
    reason: str,
    retryable: bool,
    outcome: str,
    artifact_uri: Optional[str],
    namespace: Optional[str],
    publish_event_id: Optional[str],
    public_url: Optional[str],
    jellyfin_public_url: Optional[str],
    jellyfin_item_id: Optional[str],
    details: Optional[Dict[str, Any]],
    meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "stage": stage,
        "reason": reason,
        "retryable": bool(retryable),
        "outcome": outcome,
    }
    if artifact_uri:
        payload["artifact_uri"] = artifact_uri
    if namespace:
        payload["namespace"] = namespace
    if publish_event_id:
        payload["publish_event_id"] = publish_event_id
    if public_url:
        payload["public_url"] = public_url
    if jellyfin_public_url:
        payload["jellyfin_public_url"] = jellyfin_public_url
    if jellyfin_item_id:
        payload["jellyfin_item_id"] = jellyfin_item_id
    if details:
        payload["details"] = {k: v for k, v in details.items() if v is not None}
    if meta:
        payload["meta"] = meta
    return payload


async def emit_publish_failure(
    nc: NATSClientType,
    parent_env: Dict[str, Any],
    *,
    stage: str,
    reason: str,
    retryable: bool,
    outcome: str = "fatal",
    artifact_uri: Optional[str],
    namespace: Optional[str],
    public_url: Optional[str],
    jellyfin_public_url: Optional[str],
    jellyfin_item_id: Optional[str],
    details: Optional[Dict[str, Any]],
    meta: Optional[Dict[str, Any]],
) -> None:
    publish_event_id = _coerce_text(parent_env.get("id"))
    correlation_id = _coerce_text(parent_env.get("correlation_id"))
    payload = build_failure_payload(
        stage=stage,
        reason=reason,
        retryable=retryable,
        outcome=outcome,
        artifact_uri=artifact_uri,
        namespace=namespace,
        publish_event_id=publish_event_id,
        public_url=public_url,
        jellyfin_public_url=jellyfin_public_url,
        jellyfin_item_id=jellyfin_item_id,
        details=details,
        meta=meta,
    )

    try:
        evt = envelope(
            "content.publish.failed.v1",
            payload,
            parent_id=publish_event_id,
            correlation_id=correlation_id,
            source="publisher",
        )
        await nc.publish("content.publish.failed.v1", json.dumps(evt).encode())
    except Exception as exc:  # pragma: no cover - NATS failures
        logger.warning(
            "Failed to emit publish failure envelope",
            exc_info=exc,
            extra={
                "stage": stage,
                "reason": reason,
                "publish_event_id": publish_event_id,
            },
        )
async def download_with_retries(minio: MinioClientType, bucket: str, key: str, dest: str) -> None:
    last_error: Optional[Exception] = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            minio.fget_object(bucket, key, dest)
            METRICS.record_download_success()
            if PROM_ENABLED:
                _PROM["download_success"].inc()
            return
        except Exception as exc:  # pragma: no cover - error path
            METRICS.record_download_failure()
            if PROM_ENABLED:
                _PROM["download_failure"].inc()
            last_error = exc
            logger.warning(
                "Download attempt failed",
                extra={"bucket": bucket, "key": key, "attempt": attempt},
                exc_info=exc,
            )
            if attempt < DOWNLOAD_RETRIES:
                await asyncio.sleep(DOWNLOAD_RETRY_BACKOFF_SEC * attempt)
    raise DownloadError(f"Failed to download s3://{bucket}/{key}") from last_error


async def persist_publish_rollup(row: Dict[str, Any]) -> None:
    if supabase_common is None:
        logger.debug("Supabase client unavailable; skipping metrics rollup persistence")
        return
    try:
        await asyncio.to_thread(
            supabase_common.upsert_row,
            METRICS_ROLLUP_TABLE,
            row,
            ROLLUP_CONFLICT_COLUMN or None,
        )
    except Exception as exc:  # pragma: no cover - Supabase failures
        logger.warning(
            "Failed to persist metrics rollup", extra={"table": METRICS_ROLLUP_TABLE, "row": row}, exc_info=exc
        )


def _lookup_jellyfin_item(title: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    if requests is None:
        logger.debug("requests dependency missing; skipping Jellyfin lookup")
        return None, None, {}
    if not (JELLYFIN_URL and JELLYFIN_API_KEY and JELLYFIN_USER_ID):
        missing = [
            name
            for name, value in {
                "JELLYFIN_URL": JELLYFIN_URL,
                "JELLYFIN_API_KEY": JELLYFIN_API_KEY,
                "JELLYFIN_USER_ID": JELLYFIN_USER_ID,
            }.items()
            if not value
        ]
        logger.debug(
            "Skipping Jellyfin lookup; configuration incomplete",
            extra={"title": title, "missing": missing},
        )
        return None, None, {}
    try:
        response = requests.get(
            f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items",
            params={
                "searchTerm": title,
                "IncludeItemTypes": "Movie,Video,Episode,Photo",
            },
            headers={"X-Emby-Token": JELLYFIN_API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        items = (response.json() or {}).get("Items") or []
    except Exception as exc:  # pragma: no cover - external dependency
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        body = None
        if getattr(exc, "response", None) is not None:
            with contextlib.suppress(Exception):
                body = exc.response.text[:256]
        logger.warning(
            "Failed to query Jellyfin items",
            exc_info=exc,
            extra={
                "title": title,
                "status_code": status_code,
                "body": body,
                "url": f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items",
            },
        )
        return None, None, {}

    if not items:
        logger.info(
            "Jellyfin item lookup returned no results",
            extra={"title": title, "user": JELLYFIN_USER_ID},
        )
        return None, None, {}

    title_norm = (title or "").lower()
    best = None
    for item in items:
        name = (item.get("Name") or "").lower()
        if title_norm and (title_norm in name or name in title_norm):
            best = item
            break
    if not best:
        best = items[0]
    item_id = best.get("Id")
    if not item_id:
        return None, None, {}
    public_base = JELLYFIN_PUBLIC_BASE_URL or JELLYFIN_URL
    public_url = None
    if public_base:
        public_url = urljoin(public_base, f"/web/index.html#!/details?id={item_id}&serverId=local")

    jellyfin_meta: Dict[str, Any] = {}
    runtime = best.get("RunTimeTicks") or best.get("RuntimeTicks")
    duration_seconds = None
    with contextlib.suppress(TypeError, ValueError):
        if runtime is not None:
            duration_seconds = float(runtime) / 10_000_000
    if duration_seconds:
        jellyfin_meta["duration"] = duration_seconds
    if isinstance(best.get("ImageTags"), dict):
        image_tags = best["ImageTags"]
        primary_tag = image_tags.get("Primary")
        if primary_tag and public_base:
            image_url = urljoin(public_base, f"/Items/{item_id}/Images/Primary?tag={primary_tag}")
            jellyfin_meta["thumbnail_url"] = image_url
    if isinstance(best.get("UserData"), dict):
        user_data = best["UserData"]
        if user_data.get("Played"):
            jellyfin_meta["jellyfin_played"] = bool(user_data.get("Played"))
    jellyfin_meta["jellyfin_item_type"] = best.get("Type")
    jellyfin_meta["jellyfin_base_url"] = public_base
    return public_url, item_id, jellyfin_meta


def jellyfin_refresh(title: str, namespace: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    if not (JELLYFIN_URL and JELLYFIN_API_KEY):
        missing = [name for name, value in {"JELLYFIN_URL": JELLYFIN_URL, "JELLYFIN_API_KEY": JELLYFIN_API_KEY}.items() if not value]
        logger.warning(
            "Jellyfin refresh skipped due to missing configuration",
            extra={"namespace": namespace, "title": title, "missing": missing},
        )
        raise JellyfinRefreshError(
            "Jellyfin refresh skipped; credentials not configured",
            details={"missing": missing, "namespace": namespace, "title": title},
        )
    if requests is None:
        METRICS.record_refresh_failure()
        logger.warning(
            "Requests dependency missing; cannot refresh Jellyfin",
            extra={"namespace": namespace, "title": title},
        )
        raise JellyfinRefreshError(
            "requests dependency is not installed",
            details={"namespace": namespace, "title": title},
        )

    METRICS.record_refresh_attempt()
    if PROM_ENABLED:
        _PROM["refresh_attempt"].inc()
    headers = {"X-Emby-Token": JELLYFIN_API_KEY}
    url = urljoin(JELLYFIN_URL, "/Library/Refresh")
    try:
        response = requests.post(url, headers=headers, timeout=10)
        response.raise_for_status()
        METRICS.record_refresh_success()
        if PROM_ENABLED:
            _PROM["refresh_success"].inc()
    except Exception as exc:  # pragma: no cover - external dependency
        METRICS.record_refresh_failure()
        if PROM_ENABLED:
            _PROM["refresh_failure"].inc()
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        body = None
        if getattr(exc, "response", None) is not None:
            with contextlib.suppress(Exception):
                body = exc.response.text[:256]
        logger.error(
            "Jellyfin refresh HTTP error",
            exc_info=exc,
            extra={
                "namespace": namespace,
                "title": title,
                "status_code": status_code,
                "body": body,
                "url": url,
            },
        )
        raise JellyfinRefreshError(
            f"Refresh failed for namespace {namespace}",
            details={
                "status_code": status_code,
                "body": body,
                "url": url,
                "namespace": namespace,
                "title": title,
            },
        ) from exc

    public_url, item_id, meta = _lookup_jellyfin_item(title)
    return public_url, item_id, meta


async def request_jellyfin_refresh(title: str, namespace: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    if JELLYFIN_REFRESH_DELAY_SEC > 0:
        await asyncio.sleep(JELLYFIN_REFRESH_DELAY_SEC)

    if JELLYFIN_REFRESH_WEBHOOK_URL:
        if requests is None:
            METRICS.record_refresh_failure()
            logger.warning(
                "Requests dependency missing; cannot invoke Jellyfin refresh webhook",
                extra={"namespace": namespace, "title": title},
            )
            raise JellyfinRefreshError(
                "requests dependency is not installed",
                details={"namespace": namespace, "title": title, "webhook": JELLYFIN_REFRESH_WEBHOOK_URL},
            )

        METRICS.record_refresh_attempt()
        if PROM_ENABLED:
            _PROM["refresh_attempt"].inc()
        headers = {"Authorization": f"Bearer {JELLYFIN_REFRESH_WEBHOOK_TOKEN}"} if JELLYFIN_REFRESH_WEBHOOK_TOKEN else None
        try:
            response = requests.post(
                JELLYFIN_REFRESH_WEBHOOK_URL,
                json={"title": title, "namespace": namespace},
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            METRICS.record_refresh_success()
            if PROM_ENABLED:
                _PROM["refresh_success"].inc()
        except Exception as exc:  # pragma: no cover - network failures
            METRICS.record_refresh_failure()
            if PROM_ENABLED:
                _PROM["refresh_failure"].inc()
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            body = None
            if getattr(exc, "response", None) is not None:
                with contextlib.suppress(Exception):
                    body = exc.response.text[:256]
            logger.warning(
                "Jellyfin refresh webhook failed",
                exc_info=exc,
                extra={
                    "namespace": namespace,
                    "title": title,
                    "webhook": JELLYFIN_REFRESH_WEBHOOK_URL,
                    "status_code": status_code,
                    "body": body,
                },
            )
            raise JellyfinRefreshError(
                "Webhook refresh failed",
                details={
                    "namespace": namespace,
                    "title": title,
                    "webhook": JELLYFIN_REFRESH_WEBHOOK_URL,
                    "status_code": status_code,
                    "body": body,
                },
            ) from exc

        return _lookup_jellyfin_item(title)

    return await asyncio.to_thread(jellyfin_refresh, title, namespace)


async def main() -> None:
    _configure_logging()
    if _NATSClient is None:
        raise RuntimeError("nats-py client is required to run the publisher service")
    nc: NATSClientType = _NATSClient()
    await nc.connect(servers=[NATS_URL])
    if _MinioClient is None:
        raise RuntimeError("minio client is required to run the publisher service")
    s3: MinioClientType = _MinioClient(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL,
    )

    await start_metrics_server()

    async def handle(msg):
        env = json.loads(msg.data.decode())
        payload_raw = env.get("payload") or {}
        payload = payload_raw if isinstance(payload_raw, dict) else {}

        publish_event_id = _coerce_text(env.get("id"))
        approval_event_ts = _coerce_text(env.get("ts"))
        correlation_id = _coerce_text(env.get("correlation_id"))
        artifact_uri = _coerce_text(payload.get("artifact_uri"))
        title = _coerce_text(payload.get("title")) or "untitled"
        namespace = _coerce_text(payload.get("namespace")) or "pmoves-demo"
        reviewer = _extract_reviewer(payload)
        reviewed_at = _extract_reviewed_at(payload, approval_event_ts)

        base_meta: Dict[str, Any] = {}
        if isinstance(payload.get("meta"), dict):
            base_meta["source_meta"] = payload["meta"]

        async def record_failure(
            *,
            stage: str,
            reason: str,
            retryable: bool,
            outcome: str = "fatal",
            meta_base: Optional[Dict[str, Any]] = None,
            details: Optional[Dict[str, Any]] = None,
            artifact_path_value: Optional[str] = None,
            public_url_value: Optional[str] = None,
            jellyfin_public_url_value: Optional[str] = None,
            jellyfin_item_id_value: Optional[str] = None,
        ) -> None:
            failure_details = _combine_meta(details, {"stage": stage})
            combined_meta = _combine_meta(meta_base, failure_details)
            await emit_publish_failure(
                nc,
                env,
                stage=stage,
                reason=reason,
                retryable=retryable,
                outcome=outcome,
                artifact_uri=artifact_uri,
                namespace=namespace,
                public_url=public_url_value,
                jellyfin_public_url=jellyfin_public_url_value,
                jellyfin_item_id=jellyfin_item_id_value,
                details=failure_details,
                meta=combined_meta,
            )
            _record_audit(
                publish_event_id=publish_event_id,
                approval_event_ts=approval_event_ts,
                correlation_id=correlation_id,
                artifact_uri=artifact_uri,
                artifact_path=artifact_path_value,
                namespace=namespace,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
                status="failed",
                failure_reason=reason,
                meta=combined_meta,
            )

        if not artifact_uri:
            logger.error(
                "Missing artifact URI",
                extra={
                    "publish_event_id": publish_event_id,
                    "payload_keys": list(payload.keys()),
                },
            )
            await record_failure(
                stage="validate",
                reason="missing artifact_uri",
                retryable=False,
                meta_base=base_meta,
            )
            return

        try:
            bucket, key = parse_s3(artifact_uri)
        except Exception as exc:
            logger.error(
                "Invalid artifact URI",
                exc_info=exc,
                extra={"artifact_uri": artifact_uri, "publish_event_id": publish_event_id},
            )
            await record_failure(
                stage="parse_uri",
                reason=_describe_exception(exc),
                retryable=False,
                meta_base=base_meta,
                details={"exception": exc.__class__.__name__},
            )
            return

        meta_with_source = _combine_meta(base_meta, {"bucket": bucket, "key": key})
        name = (key or "").split("/")[-1]
        ext = "." + name.split(".")[-1] if "." in name else ".png"
        slug_source = _coerce_text(payload.get("slug")) or title
        slug = slugify(slug_source)
        namespace_slug = slugify(namespace or "default")
        meta_with_slug = _combine_meta(
            meta_with_source,
            {"slug": slug, "namespace_slug": namespace_slug},
        )
        out_path = derive_output_path(MEDIA_LIBRARY_PATH, namespace, slug, ext)
        filename = os.path.basename(out_path)
        extension = os.path.splitext(filename)[1]
        path_meta_base = _combine_meta(
            meta_with_slug,
            {"output_path": out_path, "filename": filename, "extension": extension},
        )

        try:
            await download_with_retries(s3, bucket, key, out_path)
        except DownloadError as exc:
            logger.error(
                "Failed to download artifact",
                exc_info=exc,
                extra={
                    "artifact_uri": artifact_uri,
                    "namespace": namespace,
                    "output": out_path,
                    "publish_event_id": publish_event_id,
                },
            )
            await record_failure(
                stage="download",
                reason=_describe_exception(exc),
                retryable=True,
                meta_base=path_meta_base,
                details={"attempts": DOWNLOAD_RETRIES, "bucket": bucket, "key": key},
                artifact_path_value=out_path,
            )
            return

        jellyfin_public_url: Optional[str] = None
        jellyfin_item_id: Optional[str] = None
        jellyfin_meta: Dict[str, Any] = {}
        try:
            jellyfin_public_url, jellyfin_item_id, jellyfin_meta = await request_jellyfin_refresh(title, namespace)
        except JellyfinRefreshError as exc:
            logger.warning(
                "Jellyfin refresh error",
                exc_info=exc,
                extra={"namespace": namespace, "title": title, "publish_event_id": publish_event_id},
            )
            error_details = getattr(exc, "details", {})
            jellyfin_meta = _combine_meta({"jellyfin_refresh_error": str(exc)}, error_details) or {"jellyfin_refresh_error": str(exc)}
            await record_failure(
                stage="jellyfin_refresh",
                reason=_describe_exception(exc),
                retryable=True,
                outcome="partial",
                meta_base=path_meta_base,
                details=_combine_meta(
                    jellyfin_meta,
                    {"webhook": JELLYFIN_REFRESH_WEBHOOK_URL, "delay": JELLYFIN_REFRESH_DELAY_SEC},
                ),
                artifact_path_value=out_path,
            )
            jellyfin_public_url = None


        published_at = datetime.datetime.now(datetime.timezone.utc)

        derived_public_url = jellyfin_public_url or _derive_public_url(out_path)
        path_meta_with_url = _combine_meta(
            path_meta_base,
            {
                "public_url": derived_public_url,
                "jellyfin_public_url": jellyfin_public_url,
            },
        )

        payload_meta_dict = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        thumbnail_url: Optional[str] = None
        for candidate in (
            _coerce_text(payload.get("thumbnail_url")),
            _coerce_text(payload_meta_dict.get("thumbnail_url")) if isinstance(payload_meta_dict, dict) else None,
            _coerce_text(jellyfin_meta.get("thumbnail_url")),
        ):
            if candidate:
                thumbnail_url = candidate
                break

        duration_value: Optional[float] = None
        for candidate in (
            _coerce_float(payload.get("duration")),
            _coerce_float(payload_meta_dict.get("duration")) if isinstance(payload_meta_dict, dict) else None,
            _coerce_float(jellyfin_meta.get("duration")),
        ):
            if candidate is not None:
                duration_value = candidate
                break

        published_payload: Dict[str, Any] = {}
        evt: Optional[Dict[str, Any]] = None
        failure_stage = "build_payload"

        try:
            published_payload = build_published_payload(
                artifact_uri=artifact_uri,
                published_path=out_path,
                namespace=namespace,
                title=title,
                description=payload.get("description"),
                tags=payload.get("tags"),
                incoming_meta=payload.get("meta"),
                public_url=derived_public_url,
                jellyfin_item_id=jellyfin_item_id,
                jellyfin_public_url=jellyfin_public_url,
                thumbnail_url=thumbnail_url,
                duration=duration_value,
                jellyfin_meta=jellyfin_meta,
                slug=slug,
                namespace_slug=namespace_slug,
                filename=filename,
                extension=extension,
            )

            failure_stage = "telemetry"
            telemetry = compute_publish_telemetry(payload.get("meta"), env.get("ts"), published_at)
            published_payload.setdefault("meta", {}).update(telemetry.to_meta())

            METRICS.record_turnaround(telemetry.turnaround_seconds)
            METRICS.record_approval_latency(telemetry.approval_latency_seconds)
            METRICS.record_engagement(telemetry.engagement)
            METRICS.record_cost(telemetry.cost)
            if PROM_ENABLED:
                if telemetry.turnaround_seconds is not None:
                    _PROM["turnaround"].observe(telemetry.turnaround_seconds)
                if telemetry.approval_latency_seconds is not None:
                    _PROM["approval_latency"].observe(telemetry.approval_latency_seconds)

            failure_stage = "persist_rollup"
            await persist_publish_rollup(
                telemetry.to_rollup_row(
                    artifact_uri=artifact_uri,
                    namespace=namespace,
                    slug=slug,
                )
            )

            failure_stage = "emit_event"
            evt = envelope(
                "content.published.v1",
                published_payload,
                parent_id=env.get("id"),
                correlation_id=env.get("correlation_id"),
                source="publisher",
            )
            await nc.publish("content.published.v1", json.dumps(evt).encode())
        except Exception as exc:
            logger.exception(
                "Failed to finalize publish pipeline",
                extra={
                    "publish_event_id": publish_event_id,
                    "artifact_uri": artifact_uri,
                    "artifact_path": out_path,
                    "stage": failure_stage,
                    "namespace": namespace,
                },
            )
            failure_retryable = failure_stage not in {"build_payload"}
            failure_details = _combine_meta(
                jellyfin_meta,
                {
                    "public_url": derived_public_url,
                    "jellyfin_item_id": jellyfin_item_id,
                    "exception": exc.__class__.__name__,
                },
            )
            await record_failure(
                stage=failure_stage,
                reason=_describe_exception(exc),
                retryable=failure_retryable,
                meta_base=path_meta_with_url,
                details=failure_details,
                artifact_path_value=out_path,
                public_url_value=derived_public_url,
                jellyfin_public_url_value=jellyfin_public_url,
                jellyfin_item_id_value=jellyfin_item_id,
            )
            return

        success_context: Dict[str, Any] = {"stage": "published"}
        if jellyfin_item_id:
            success_context["jellyfin_item_id"] = jellyfin_item_id
        success_context.update(jellyfin_meta)
        success_meta = _combine_meta(
            path_meta_with_url,
            _combine_meta(
                success_context,
                {"thumbnail_url": thumbnail_url, "duration": duration_value},
            ),
        )

        _record_audit(
            publish_event_id=publish_event_id,
            approval_event_ts=approval_event_ts,
            correlation_id=correlation_id,
            artifact_uri=artifact_uri,
            artifact_path=out_path,
            namespace=namespace,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
            status="published",
            failure_reason=None,
            published_event_id=_coerce_text(evt.get("id")),
            public_url=published_payload.get("public_url"),
            published_at=_coerce_text(evt.get("ts")),
            meta=success_meta,
        )

        logger.info(
            "Published content",
            extra={
                "artifact_uri": artifact_uri,
                "published_path": out_path,
                "published_filename": filename,
                "namespace": namespace,
                "namespace_slug": namespace_slug,
                "event_id": env.get("id"),
                "correlation_id": env.get("correlation_id"),
                "public_url": published_payload.get("public_url"),
                "jellyfin_public_url": published_payload.get("jellyfin_public_url"),
                "thumbnail_url": published_payload.get("thumbnail_url"),
                "duration": published_payload.get("duration"),
                "metrics_summary": METRICS.summary(),
                "publish_event_id": publish_event_id,
                "reviewer": reviewer,
                "metrics_state": asdict(METRICS),
            },
        )

    await nc.subscribe("content.publish.approved.v1", cb=handle)
    logger.info("Publisher ready", extra={"topic": "content.publish.approved.v1"})
    while True:
        await asyncio.sleep(3600)


async def _handle_metrics_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request = await reader.read(4096)
        request_line = request.split(b"\r\n", 1)[0].decode(errors="ignore")
        if request_line.startswith("GET /healthz ") or request_line.startswith("GET /healthz\r") or request_line.startswith("GET /healthz\n") or request_line.startswith("GET /healthz"):
            # PMOVES.AI: Health check endpoint for Kubernetes and monitoring
            payload = json.dumps({"status": "healthy", "service": "pmoves-publisher"}).encode()
            headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(payload)}\r\n"
                "Cache-Control: no-store\r\n"
                "Connection: close\r\n\r\n"
            ).encode()
            writer.write(headers + payload)
        elif request_line.startswith("GET /metrics ") or request_line.startswith("GET /metrics\r") or request_line.startswith("GET /metrics\n") or request_line.startswith("GET /metrics"):
            # Always serve JSON at /metrics to satisfy tests and simplify tooling
            payload = json.dumps(METRICS.summary()).encode()
            headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(payload)}\r\n"
                "Cache-Control: no-store\r\n"
                "Connection: close\r\n\r\n"
            ).encode()
            writer.write(headers + payload)
        elif request_line.startswith("GET /metrics.prom"):
            if PROM_ENABLED:
                prom = _prom_generate(_PROM_REG)
                headers = (
                    "HTTP/1.1 200 OK\r\n"
                    f"Content-Type: {_PROM_CONTENT_TYPE}\r\n"
                    f"Content-Length: {len(prom)}\r\n"
                    "Cache-Control: no-store\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
                writer.write(headers + prom)
            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        elif request_line.startswith("GET /metrics.json"):
            payload = json.dumps(METRICS.summary()).encode()
            headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(payload)}\r\n"
                "Cache-Control: no-store\r\n"
                "Connection: close\r\n\r\n"
            ).encode()
            writer.write(headers + payload)
        else:
            writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        await writer.drain()
    finally:
        writer.close()
        with contextlib.suppress(Exception):  # pragma: no cover - platform dependent
            await writer.wait_closed()


async def start_metrics_server() -> asyncio.AbstractServer:
    global _METRICS_SERVER
    server = await asyncio.start_server(_handle_metrics_request, METRICS_HOST, METRICS_PORT)
    _METRICS_SERVER = server
    sockets = server.sockets or []
    bound = [sock.getsockname() for sock in sockets]
    logger.info("Metrics endpoint ready", extra={"bind": bound})
    return server


def _derive_public_url(path: str) -> Optional[str]:
    if not MEDIA_LIBRARY_PUBLIC_BASE_URL:
        return None
    rel_path = os.path.relpath(path, MEDIA_LIBRARY_PATH)
    rel_path = rel_path.replace(os.sep, "/")
    return urljoin(MEDIA_LIBRARY_PUBLIC_BASE_URL.rstrip("/") + "/", rel_path)


if __name__ == "__main__":
    asyncio.run(main())
