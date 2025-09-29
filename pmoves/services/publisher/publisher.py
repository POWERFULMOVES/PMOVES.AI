import asyncio

import contextlib


import datetime
import json
import logging
import os
import pathlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
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
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
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


@dataclass
class PublisherMetrics:
    downloads: int = 0
    download_failures: int = 0
    refresh_attempts: int = 0
    refresh_success: int = 0
    refresh_failures: int = 0
    turnaround_samples: int = 0
    total_turnaround_seconds: float = 0.0
    max_turnaround_seconds: float = 0.0
    approval_latency_samples: int = 0
    total_approval_latency_seconds: float = 0.0
    max_approval_latency_seconds: float = 0.0
    engagement_events: int = 0
    engagement_totals: Dict[str, float] = field(default_factory=dict)
    cost_events: int = 0
    cost_totals: Dict[str, float] = field(default_factory=dict)

    def record_download_success(self) -> None:
        self.downloads += 1

    def record_download_failure(self) -> None:
        self.download_failures += 1

    def record_refresh_attempt(self) -> None:
        self.refresh_attempts += 1

    def record_refresh_success(self) -> None:
        self.refresh_success += 1

    def record_refresh_failure(self) -> None:
        self.refresh_failures += 1

    def record_turnaround(self, seconds: Optional[float]) -> None:
        if seconds is None or seconds < 0:
            return
        self.turnaround_samples += 1
        self.total_turnaround_seconds += seconds
        if seconds > self.max_turnaround_seconds:
            self.max_turnaround_seconds = seconds

    def record_approval_latency(self, seconds: Optional[float]) -> None:
        if seconds is None or seconds < 0:
            return
        self.approval_latency_samples += 1
        self.total_approval_latency_seconds += seconds
        if seconds > self.max_approval_latency_seconds:
            self.max_approval_latency_seconds = seconds

    def record_engagement(self, engagement: Dict[str, float]) -> None:
        if not engagement:
            return
        self.engagement_events += 1
        for key, value in engagement.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            self.engagement_totals[key] = self.engagement_totals.get(key, 0.0) + numeric

    def record_cost(self, cost: Dict[str, float]) -> None:
        if not cost:
            return
        self.cost_events += 1
        for key, value in cost.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            self.cost_totals[key] = self.cost_totals.get(key, 0.0) + numeric

    def summary(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.turnaround_samples:
            data["avg_turnaround_seconds"] = self.total_turnaround_seconds / self.turnaround_samples
        if self.approval_latency_samples:
            data["avg_approval_latency_seconds"] = (
                self.total_approval_latency_seconds / self.approval_latency_samples
            )
        return data


METRICS = PublisherMetrics()
_METRICS_SERVER: Optional[asyncio.AbstractServer] = None


class DownloadError(Exception):
    """Raised when an artifact fails to download after retries."""


class JellyfinRefreshError(Exception):
    """Raised when Jellyfin fails to refresh or respond."""



@dataclass
class PublishTelemetry:
    published_at: datetime.datetime
    turnaround_seconds: Optional[float]
    approval_latency_seconds: Optional[float]
    engagement: Dict[str, float]
    cost: Dict[str, float]

    def to_meta(self) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "published_at": self.published_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        if self.turnaround_seconds is not None:
            meta["turnaround_seconds"] = self.turnaround_seconds
        if self.approval_latency_seconds is not None:
            meta["approval_to_publish_seconds"] = self.approval_latency_seconds
        if self.engagement:
            meta["engagement"] = self.engagement
        if self.cost:
            meta["cost"] = self.cost
        return meta

    def to_rollup_row(self, *, artifact_uri: str, namespace: str, slug: str) -> Dict[str, Any]:
        return {
            "artifact_uri": artifact_uri,
            "namespace": namespace,
            "slug": slug,
            "published_at": self.published_at.isoformat(),
            "turnaround_seconds": self.turnaround_seconds,
            "approval_latency_seconds": self.approval_latency_seconds,
            "engagement": self.engagement or None,
            "cost": self.cost or None,
        }



def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _coerce_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


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
        "failure_reason": failure_reason,
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
    slug: str,
    namespace_slug: str,
    filename: str,
    extension: str,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "artifact_uri": artifact_uri,
        "published_path": published_path,
        "namespace": namespace,
        "meta": merge_metadata(
            title,
            description,
            tags,
            incoming_meta,
            slug=slug,
            namespace_slug=namespace_slug,
            filename=filename,
            extension=extension,
        ),
    }
    if public_url:
        payload["public_url"] = public_url
    if jellyfin_item_id:
        payload["jellyfin_item_id"] = jellyfin_item_id
    return payload


async def download_with_retries(minio: MinioClientType, bucket: str, key: str, dest: str) -> None:
    last_error: Optional[Exception] = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            minio.fget_object(bucket, key, dest)
            METRICS.record_download_success()
            return
        except Exception as exc:  # pragma: no cover - error path
            METRICS.record_download_failure()
            last_error = exc
            logger.warning(
                "Download attempt failed",
                extra={"bucket": bucket, "key": key, "attempt": attempt},
                exc_info=exc,
            )
            if attempt < DOWNLOAD_RETRIES:
                await asyncio.sleep(DOWNLOAD_RETRY_BACKOFF_SEC * attempt)
    raise DownloadError(f"Failed to download s3://{bucket}/{key}") from last_error


def _parse_iso8601(value: Optional[Any]) -> Optional[datetime.datetime]:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        return None


def _coerce_numeric(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        numeric = float(value)
        if numeric != numeric:  # NaN
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _extract_first(meta: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
    for key in keys:
        candidate = meta.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def compute_publish_telemetry(
    incoming_meta: Optional[Dict[str, Any]],
    event_ts: Optional[str],
    published_at: datetime.datetime,
) -> PublishTelemetry:
    meta = incoming_meta or {}
    start_keys = (
        "ingest_started_at",
        "submitted_at",
        "created_at",
        "capture_completed_at",
    )
    approval_keys = (
        "approval_granted_at",
        "approved_at",
        "approval_completed_at",
    )

    start_ts = _parse_iso8601(_extract_first(meta, start_keys))
    approval_ts = _parse_iso8601(_extract_first(meta, approval_keys))
    event_timestamp = _parse_iso8601(event_ts)

    turnaround_seconds: Optional[float] = None
    if start_ts is not None:
        turnaround_seconds = (published_at - start_ts).total_seconds()

    approval_latency_seconds: Optional[float] = None
    reference_ts = approval_ts or event_timestamp
    if reference_ts is not None:
        approval_latency_seconds = (published_at - reference_ts).total_seconds()

    engagement: Dict[str, float] = {}
    for key in ("engagement", "analytics", "metrics"):
        candidate = meta.get(key)
        if isinstance(candidate, dict):
            for metric_key, value in candidate.items():
                numeric = _coerce_numeric(value)
                if numeric is None:
                    continue
                engagement[metric_key] = engagement.get(metric_key, 0.0) + numeric

    cost: Dict[str, float] = {}
    for key in ("cost", "spend", "usage"):
        candidate = meta.get(key)
        if isinstance(candidate, dict):
            for cost_key, value in candidate.items():
                numeric = _coerce_numeric(value)
                if numeric is None:
                    continue
                cost[cost_key] = cost.get(cost_key, 0.0) + numeric

    return PublishTelemetry(
        published_at=published_at,
        turnaround_seconds=turnaround_seconds,
        approval_latency_seconds=approval_latency_seconds,
        engagement=engagement,
        cost=cost,
    )


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


def _lookup_jellyfin_item(title: str) -> Tuple[Optional[str], Optional[str]]:
    if requests is None:
        logger.debug("requests dependency missing; skipping Jellyfin lookup")
        return None, None
    if not (JELLYFIN_URL and JELLYFIN_API_KEY and JELLYFIN_USER_ID):
        return None, None
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
        logger.debug("Failed to query Jellyfin items", exc_info=exc)
        return None, None

    if not items:
        return None, None

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
        return None, None
    public_base = JELLYFIN_PUBLIC_BASE_URL or JELLYFIN_URL
    public_url = None
    if public_base:
        public_url = urljoin(public_base, f"/web/index.html#!/details?id={item_id}&serverId=local")
    return public_url, item_id


def jellyfin_refresh(title: str, namespace: str) -> Tuple[Optional[str], Optional[str]]:
    if not (JELLYFIN_URL and JELLYFIN_API_KEY):
        return None, None
    if requests is None:
        METRICS.record_refresh_failure()
        logger.warning(
            "Requests dependency missing; cannot refresh Jellyfin",
            extra={"namespace": namespace, "title": title},
        )
        raise JellyfinRefreshError("requests dependency is not installed")

    METRICS.record_refresh_attempt()
    headers = {"X-Emby-Token": JELLYFIN_API_KEY}
    url = urljoin(JELLYFIN_URL, "/Library/Refresh")
    try:
        response = requests.post(url, headers=headers, timeout=10)
        response.raise_for_status()
        METRICS.record_refresh_success()
    except Exception as exc:  # pragma: no cover - external dependency
        METRICS.record_refresh_failure()
        raise JellyfinRefreshError(f"Refresh failed for namespace {namespace}") from exc

    public_url, item_id = _lookup_jellyfin_item(title)
    return public_url, item_id


async def request_jellyfin_refresh(title: str, namespace: str) -> Tuple[Optional[str], Optional[str]]:
    if JELLYFIN_REFRESH_DELAY_SEC > 0:
        await asyncio.sleep(JELLYFIN_REFRESH_DELAY_SEC)

    if JELLYFIN_REFRESH_WEBHOOK_URL:
        if requests is None:
            METRICS.record_refresh_failure()
            logger.warning(
                "Requests dependency missing; cannot invoke Jellyfin refresh webhook",
                extra={"namespace": namespace, "title": title},
            )
            raise JellyfinRefreshError("requests dependency is not installed")

        METRICS.record_refresh_attempt()
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
        except Exception as exc:  # pragma: no cover - network failures
            METRICS.record_refresh_failure()
            logger.warning(
                "Jellyfin refresh webhook failed",
                exc_info=exc,
                extra={"namespace": namespace, "title": title, "webhook": JELLYFIN_REFRESH_WEBHOOK_URL},
            )
            raise JellyfinRefreshError("Webhook refresh failed") from exc

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

        if not artifact_uri:
            logger.error(
                "Missing artifact URI",
                extra={
                    "publish_event_id": publish_event_id,
                    "payload_keys": list(payload.keys()),
                },
            )
            _record_audit(
                publish_event_id=publish_event_id,
                approval_event_ts=approval_event_ts,
                correlation_id=correlation_id,
                artifact_uri=artifact_uri,
                artifact_path=None,
                namespace=namespace,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
                status="failed",
                failure_reason="missing artifact_uri",
                meta=_combine_meta(base_meta, {"stage": "validate"}),
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
            _record_audit(
                publish_event_id=publish_event_id,
                approval_event_ts=approval_event_ts,
                correlation_id=correlation_id,
                artifact_uri=artifact_uri,
                artifact_path=None,
                namespace=namespace,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
                status="failed",
                failure_reason=str(exc),
                meta=_combine_meta(base_meta, {"stage": "parse_uri"}),
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
            _record_audit(
                publish_event_id=publish_event_id,
                approval_event_ts=approval_event_ts,
                correlation_id=correlation_id,
                artifact_uri=artifact_uri,
                artifact_path=out_path,
                namespace=namespace,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
                status="failed",
                failure_reason=str(exc),
                meta=_combine_meta(
                    meta_with_slug,
                    {"stage": "download", "output_path": out_path, "attempts": DOWNLOAD_RETRIES},
                ),
            )
            return

        public_url: Optional[str] = None
        jellyfin_item_id: Optional[str] = None
        jellyfin_meta: Dict[str, Any] = {}
        try:
            public_url, jellyfin_item_id = await request_jellyfin_refresh(title, namespace)
        except JellyfinRefreshError as exc:
            logger.warning(
                "Jellyfin refresh error",
                exc_info=exc,
                extra={"namespace": namespace, "title": title, "publish_event_id": publish_event_id},
            )
            jellyfin_meta = {"jellyfin_refresh_error": str(exc)}


        published_at = datetime.datetime.now(datetime.timezone.utc)

        derived_public_url = public_url or _derive_public_url(out_path)

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
            slug=slug,
            namespace_slug=namespace_slug,
            filename=filename,
            extension=extension,
        )

        telemetry = compute_publish_telemetry(payload.get("meta"), env.get("ts"), published_at)
        published_payload.setdefault("meta", {}).update(telemetry.to_meta())

        METRICS.record_turnaround(telemetry.turnaround_seconds)
        METRICS.record_approval_latency(telemetry.approval_latency_seconds)
        METRICS.record_engagement(telemetry.engagement)
        METRICS.record_cost(telemetry.cost)

        await persist_publish_rollup(
            telemetry.to_rollup_row(
                artifact_uri=artifact_uri,
                namespace=namespace,
                slug=slug,
            )
        )

        evt = envelope(
            "content.published.v1",
            published_payload,
            parent_id=env.get("id"),
            correlation_id=env.get("correlation_id"),
            source="publisher",
        )
        await nc.publish("content.published.v1", json.dumps(evt).encode())

        extra_meta = {
            "stage": "published",
            "filename": filename,
            "extension": extension,
            "jellyfin_item_id": jellyfin_item_id,
        }
        extra_meta.update(jellyfin_meta)
        success_meta = _combine_meta(meta_with_slug, extra_meta)

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

                "metrics": METRICS.summary(),

                "publish_event_id": publish_event_id,
                "reviewer": reviewer,
                "metrics": asdict(METRICS),

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
        if request_line.startswith("GET /metrics"):
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
