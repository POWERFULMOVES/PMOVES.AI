import asyncio
import json
import logging
import os
import pathlib
import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Tuple

import requests
from minio import Minio
from nats.aio.client import Client as NATS
from urllib.parse import urljoin

from services.common.events import envelope

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_USE_SSL = os.environ.get("MINIO_USE_SSL", "false").lower() == "true"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "pmoves")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "password")
JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "http://jellyfin:8096")
JELLYFIN_API_KEY = os.environ.get("JELLYFIN_API_KEY")
JELLYFIN_USER_ID = os.environ.get("JELLYFIN_USER_ID")
JELLYFIN_PUBLIC_BASE_URL = os.environ.get("JELLYFIN_PUBLIC_BASE_URL", JELLYFIN_URL)
MEDIA_LIBRARY_PATH = os.environ.get("MEDIA_LIBRARY_PATH", "/library/images")
MEDIA_LIBRARY_PUBLIC_BASE_URL = os.environ.get("MEDIA_LIBRARY_PUBLIC_BASE_URL")
DOWNLOAD_RETRIES = int(os.environ.get("PUBLISHER_DOWNLOAD_RETRIES", "3"))
DOWNLOAD_RETRY_BACKOFF_SEC = float(os.environ.get("PUBLISHER_DOWNLOAD_RETRY_BACKOFF", "1.5"))


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


METRICS = PublisherMetrics()


class DownloadError(Exception):
    """Raised when an artifact fails to download after retries."""


class JellyfinRefreshError(Exception):
    """Raised when Jellyfin fails to refresh or respond."""


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


def derive_output_path(base: str, namespace: Optional[str], slug: str, ext: str) -> str:
    namespace_slug = slugify(namespace or "default")
    directory = os.path.join(base, namespace_slug)
    ensure_path(directory)
    extension = ext if ext.startswith(".") else f".{ext}" if ext else ""
    return os.path.join(directory, f"{slug}{extension}")


def merge_metadata(
    title: str,
    description: Optional[str],
    tags: Optional[Any],
    incoming_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    meta: Dict[str, Any] = dict(incoming_meta or {})
    meta.setdefault("title", title)
    if description:
        meta["description"] = description
    if tags:
        meta["tags"] = list(tags)
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
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "artifact_uri": artifact_uri,
        "published_path": published_path,
        "namespace": namespace,
        "meta": merge_metadata(title, description, tags, incoming_meta),
    }
    if public_url:
        payload["public_url"] = public_url
    if jellyfin_item_id:
        payload["jellyfin_item_id"] = jellyfin_item_id
    return payload


async def download_with_retries(minio: Minio, bucket: str, key: str, dest: str) -> None:
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


def _lookup_jellyfin_item(title: str) -> Tuple[Optional[str], Optional[str]]:
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


async def main() -> None:
    _configure_logging()
    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    s3 = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL,
    )

    async def handle(msg):
        env = json.loads(msg.data.decode())
        payload = env.get("payload", {})
        artifact_uri = payload.get("artifact_uri")
        title = payload.get("title", "untitled")
        namespace = payload.get("namespace", "pmoves-demo")

        try:
            bucket, key = parse_s3(artifact_uri)
        except Exception as exc:
            logger.error("Invalid artifact URI", exc_info=exc, extra={"artifact_uri": artifact_uri})
            return

        name = (key or "").split("/")[-1]
        ext = "." + name.split(".")[-1] if "." in name else ".png"
        slug = slugify(payload.get("slug") or title)
        out_path = derive_output_path(MEDIA_LIBRARY_PATH, namespace, slug, ext)

        try:
            await download_with_retries(s3, bucket, key, out_path)
        except DownloadError as exc:
            logger.error(
                "Failed to download artifact",
                exc_info=exc,
                extra={"artifact_uri": artifact_uri, "namespace": namespace, "output": out_path},
            )
            return

        public_url: Optional[str] = None
        jellyfin_item_id: Optional[str] = None
        try:
            public_url, jellyfin_item_id = jellyfin_refresh(title, namespace)
        except JellyfinRefreshError as exc:
            logger.warning(
                "Jellyfin refresh error",
                exc_info=exc,
                extra={"namespace": namespace, "title": title},
            )

        published_payload = build_published_payload(
            artifact_uri=artifact_uri,
            published_path=out_path,
            namespace=namespace,
            title=title,
            description=payload.get("description"),
            tags=payload.get("tags"),
            incoming_meta=payload.get("meta"),
            public_url=public_url or _derive_public_url(out_path),
            jellyfin_item_id=jellyfin_item_id,
        )

        evt = envelope(
            "content.published.v1",
            published_payload,
            parent_id=env.get("id"),
            correlation_id=env.get("correlation_id"),
            source="publisher",
        )
        await nc.publish("content.published.v1".encode(), json.dumps(evt).encode())
        logger.info(
            "Published content",
            extra={
                "artifact_uri": artifact_uri,
                "published_path": out_path,
                "namespace": namespace,
                "metrics": asdict(METRICS),
            },
        )

    await nc.subscribe("content.publish.approved.v1", cb=handle)
    logger.info("Publisher ready", extra={"topic": "content.publish.approved.v1"})
    while True:
        await asyncio.sleep(3600)


def _derive_public_url(path: str) -> Optional[str]:
    if not MEDIA_LIBRARY_PUBLIC_BASE_URL:
        return None
    rel_path = os.path.relpath(path, MEDIA_LIBRARY_PATH)
    rel_path = rel_path.replace(os.sep, "/")
    return urljoin(MEDIA_LIBRARY_PUBLIC_BASE_URL.rstrip("/") + "/", rel_path)


if __name__ == "__main__":
    asyncio.run(main())
