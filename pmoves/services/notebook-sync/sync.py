import asyncio
import logging
import os
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from dateutil import parser as date_parser
from fastapi import FastAPI, HTTPException, Request
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

LOGGER = logging.getLogger("pmoves.notebook_sync")
logging.basicConfig(
    level=getattr(logging, os.getenv("NOTEBOOK_SYNC_LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus Metrics
# ─────────────────────────────────────────────────────────────────────────────
NOTEBOOK_SYNC_CYCLES = Counter(
    "notebook_sync_cycles_total",
    "Total sync cycles executed",
    ["status"]
)
NOTEBOOK_SYNC_ITEMS = Counter(
    "notebook_sync_items_total",
    "Total items synced",
    ["resource"]
)
NOTEBOOK_SYNC_CHUNKS = Counter(
    "notebook_sync_chunks_indexed_total",
    "Total chunks indexed from notebooks"
)
NOTEBOOK_SYNC_LATENCY = Histogram(
    "notebook_sync_cycle_latency_seconds",
    "Sync cycle latency in seconds",
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)
NOTEBOOK_SYNC_ERRORS = Counter(
    "notebook_sync_errors_total",
    "Total sync errors",
    ["stage"]
)
NOTEBOOK_SYNC_ACTIVE = Gauge(
    "notebook_sync_active",
    "Whether a sync is currently active"
)

VALID_MODES = {"live", "offline"}


class CursorStore:
    """Simple SQLite-backed cursor store for resource sync positions."""

    def __init__(self, path: str) -> None:
        self.path = path
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_cursors (
                    resource TEXT PRIMARY KEY,
                    cursor TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            yield conn
        finally:
            conn.close()

    def get_cursor(self, resource: str) -> Optional[str]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT cursor FROM sync_cursors WHERE resource = ?", (resource,)
            )
            row = cur.fetchone()
            return row[0] if row else None

    def set_cursor(self, resource: str, cursor: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_cursors(resource, cursor, updated_at)
                VALUES(?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(resource)
                DO UPDATE SET cursor=excluded.cursor, updated_at=CURRENT_TIMESTAMP
                """,
                (resource, cursor),
            )
            conn.commit()


class NotebookSyncer:
    RESOURCES = ("notebooks", "notes", "sources")

    def __init__(
        self,
        base_url: str,
        cursor_store: CursorStore,
        interval_seconds: int = 300,
        namespace: str = "open-notebook",
        langextract_url: str = "http://langextract:8084",
        extract_worker_url: str = "http://extract-worker:8083",
        api_token: Optional[str] = None,
        mode: str = "live",
        enabled_resources: Optional[List[str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cursor_store = cursor_store
        self.interval_seconds = interval_seconds
        self.namespace = namespace
        self.langextract_url = langextract_url.rstrip("/")
        self.extract_worker_url = extract_worker_url.rstrip("/")
        self.api_token = api_token
        self.mode = mode if mode in VALID_MODES else "live"
        self.enabled_resources: List[str] = (
            [resource for resource in (enabled_resources or []) if resource in self.RESOURCES]
            or list(self.RESOURCES)
        )

        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        timeout = httpx.Timeout(30.0, connect=10.0)
        self.api_client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=timeout)
        self.lang_client = httpx.AsyncClient(base_url=self.langextract_url, timeout=timeout)
        self.extract_client = httpx.AsyncClient(base_url=self.extract_worker_url, timeout=timeout)

        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._lock = asyncio.Lock()
        self.last_sync_time: Optional[datetime] = None

    async def start(self) -> None:
        if self.mode != "live":
            LOGGER.info("Notebook sync worker disabled (mode=%s)", self.mode)
            return
        if self.interval_seconds <= 0:
            LOGGER.info("Notebook sync worker disabled (interval_seconds=%s)", self.interval_seconds)
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        LOGGER.info("Notebook sync worker started with interval=%ss", self.interval_seconds)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            await self._task
        await self.api_client.aclose()
        await self.lang_client.aclose()
        await self.extract_client.aclose()
        LOGGER.info("Notebook sync worker stopped")

    async def trigger_once(self) -> None:
        if self.mode != "live":
            LOGGER.info("Skipping manual trigger; mode=%s", self.mode)
            return
        await self._sync_cycle(manual=True)

    async def _run(self) -> None:
        try:
            while self._running:
                await self._sync_cycle()
                if self.interval_seconds <= 0:
                    LOGGER.info("Notebook sync interval set to %s; stopping loop", self.interval_seconds)
                    break
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            LOGGER.info("Notebook sync loop cancelled")
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Notebook sync loop crashed")
        finally:
            self._running = False

    async def _sync_cycle(self, manual: bool = False) -> None:
        async with self._lock:
            NOTEBOOK_SYNC_ACTIVE.set(1)
            start = datetime.now(timezone.utc)
            cycle_status = "success"
            try:
                if not self.enabled_resources:
                    LOGGER.info("No notebook resources enabled; skipping sync")
                    return
                LOGGER.info(
                    "Starting %s notebook sync (resources=%s)",
                    "manual" if manual else "scheduled",
                    ",".join(self.enabled_resources),
                )
                for resource in self.enabled_resources:
                    try:
                        await self._sync_resource(resource)
                    except Exception:  # pylint: disable=broad-except
                        LOGGER.exception("Failed to sync resource '%s'", resource)
                        NOTEBOOK_SYNC_ERRORS.labels(stage="resource").inc()
                        cycle_status = "partial"
                self.last_sync_time = datetime.now(timezone.utc)
                LOGGER.info(
                    "Completed notebook sync in %.2fs", (self.last_sync_time - start).total_seconds()
                )
            except Exception:
                cycle_status = "error"
                raise
            finally:
                NOTEBOOK_SYNC_ACTIVE.set(0)
                NOTEBOOK_SYNC_CYCLES.labels(status=cycle_status).inc()
                NOTEBOOK_SYNC_LATENCY.observe((datetime.now(timezone.utc) - start).total_seconds())

    async def _sync_resource(self, resource: str) -> None:
        cursor = self.cursor_store.get_cursor(resource)
        params: Dict[str, Any] = {}
        if cursor:
            params["updated_after"] = cursor
        next_cursor: Optional[str] = None
        latest_cursor: Optional[str] = cursor

        while True:
            request_params = params.copy()
            if next_cursor:
                request_params = {"cursor": next_cursor}
            response = await self._request(self.api_client, "GET", f"/api/{resource}", params=request_params)
            payload = response.json()
            items = self._extract_items(payload)
            if not items:
                break

            for item in items:
                await self._process_item(resource, item)
                latest_cursor = self._select_latest(latest_cursor, self._extract_cursor_value(item))

            next_cursor = self._extract_next_cursor(payload)
            if not next_cursor:
                break

        if latest_cursor and latest_cursor != cursor:
            self.cursor_store.set_cursor(resource, latest_cursor)
            LOGGER.info("Updated cursor for %s to %s", resource, latest_cursor)

    async def _process_item(self, resource: str, item: Dict[str, Any]) -> None:
        normalized = self._normalize_item(resource, item)
        if not normalized:
            LOGGER.debug("Skipping %s item without content: %s", resource, item.get("id"))
            return

        document_text = self._compose_document(normalized)
        if not document_text.strip():
            LOGGER.debug("%s %s had no text to extract", resource, normalized["id"])
            return

        doc_id = f"{resource}:{normalized['id']}"
        lang_body = {
            "text": document_text,
            "namespace": self.namespace,
            "doc_id": doc_id,
        }

        extract_result: Dict[str, Any]
        try:
            response = await self._request(
                self.lang_client,
                "POST",
                "/extract/text",
                json=lang_body,
            )
            extract_result = response.json()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("LangExtract failed for %s %s", resource, normalized["id"])
            NOTEBOOK_SYNC_ERRORS.labels(stage="langextract").inc()
            metadata = self._build_metadata(resource, normalized)
            error_payload = {
                "message": str(exc),
                "stage": "langextract",
                "metadata": metadata,
            }
            await self._emit_errors([error_payload])
            return

        metadata = self._build_metadata(resource, normalized)
        tags = normalized.get("tags", [])
        chunks = [self._enrich_chunk(chunk, metadata, tags) for chunk in extract_result.get("chunks", [])]
        errors = [self._enrich_error(err, metadata) for err in extract_result.get("errors", [])]

        NOTEBOOK_SYNC_ITEMS.labels(resource=resource).inc()
        NOTEBOOK_SYNC_CHUNKS.inc(len(chunks))

        ingest_body = {"chunks": chunks, "errors": errors}
        try:
            await self._request(self.extract_client, "POST", "/ingest", json=ingest_body)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("Failed to ingest chunks for %s %s", resource, normalized["id"])
            NOTEBOOK_SYNC_ERRORS.labels(stage="ingest").inc()
            failure = {
                "message": str(exc),
                "stage": "ingest",
                "metadata": metadata,
            }
            failure["metadata"]["chunks_count"] = len(chunks)
            failure["metadata"]["errors_count"] = len(errors)
            await self._emit_errors([failure])

    async def _emit_errors(self, errors: List[Dict[str, Any]]) -> None:
        if not errors:
            return
        try:
            await self._request(self.extract_client, "POST", "/ingest", json={"chunks": [], "errors": errors})
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Failed to forward errors to extract-worker")

    @staticmethod
    def _extract_items(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return payload  # type: ignore[return-value]
        if isinstance(payload, dict):
            for key in ("data", "items", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value  # type: ignore[return-value]
        return []

    @staticmethod
    def _extract_next_cursor(payload: Any) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        for key in ("next_cursor", "next", "cursor"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                nested = value.get("cursor") or value.get("id")
                if isinstance(nested, str):
                    return nested
        return None

    @staticmethod
    def _extract_cursor_value(item: Dict[str, Any]) -> Optional[str]:
        for key in ("updated_at", "modified_at", "last_modified", "timestamp", "synced_at"):
            value = item.get(key)
            iso = NotebookSyncer._normalize_datetime(value)
            if iso:
                return iso
        return None

    @staticmethod
    def _normalize_datetime(value: Any) -> Optional[str]:
        if not value:
            return None
        dt: Optional[datetime] = None
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        elif isinstance(value, str):
            try:
                parsed = date_parser.parse(value)
            except (ValueError, TypeError):
                parsed = None
            if parsed:
                if parsed.tzinfo is None:
                    dt = parsed.replace(tzinfo=timezone.utc)
                else:
                    dt = parsed.astimezone(timezone.utc)
        if not dt:
            return None
        return dt.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _select_latest(current: Optional[str], candidate: Optional[str]) -> Optional[str]:
        if not candidate:
            return current
        if not current:
            return candidate
        current_dt = date_parser.parse(current)
        candidate_dt = date_parser.parse(candidate)
        return candidate if candidate_dt > current_dt else current

    @staticmethod
    def _normalize_item(resource: str, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        item_id = item.get("id")
        if item_id is None:
            return None

        title = (
            item.get("title")
            or item.get("name")
            or item.get("heading")
            or f"{resource.rstrip('s').title()} {item_id}"
        )
        content = (
            item.get("content")
            or item.get("body")
            or item.get("text")
            or item.get("markdown")
            or ""
        )
        tags = NotebookSyncer._coerce_tags(item.get("tags") or item.get("labels"))
        notebook_id = (
            item.get("notebook_id")
            or (item.get("notebook") or {}).get("id")
            or (item.get("meta") or {}).get("notebook_id")
        )
        note_id = item.get("note_id") or (item.get("note") or {}).get("id")
        source_id = item.get("source_id") or (item.get("source") or {}).get("id")

        normalized = {
            "id": str(item_id),
            "title": str(title) if title else "",
            "content": str(content) if content else "",
            "tags": tags,
            "notebook_id": str(notebook_id) if notebook_id else (str(item_id) if resource == "notebooks" else None),
            "note_id": str(item_id) if resource == "notes" else (str(note_id) if note_id else None),
            "source_id": str(item_id) if resource == "sources" else (str(source_id) if source_id else None),
            "raw": item,
        }
        return normalized

    @staticmethod
    def _coerce_tags(tags: Any) -> List[str]:
        if not tags:
            return []
        if isinstance(tags, str):
            return [t.strip() for t in tags.split(",") if t.strip()]
        if isinstance(tags, (list, tuple, set)):
            return [str(t) for t in tags if str(t).strip()]
        return []

    @staticmethod
    def _compose_document(normalized: Dict[str, Any]) -> str:
        parts: List[str] = []
        if normalized.get("title"):
            parts.append(str(normalized["title"]))
        if normalized.get("content"):
            parts.append(str(normalized["content"]))
        tags = normalized.get("tags") or []
        if tags:
            parts.append("Tags: " + ", ".join(tags))
        return "\n\n".join(parts)

    @staticmethod
    def _build_metadata(resource: str, normalized: Dict[str, Any]) -> Dict[str, Any]:
        metadata = {
            "source": "open-notebook",
            "open_notebook_resource": resource,
            "open_notebook_id": normalized.get("id"),
        }
        if normalized.get("title"):
            metadata["title"] = normalized["title"]
        if normalized.get("notebook_id"):
            metadata["notebook_id"] = normalized["notebook_id"]
        if normalized.get("note_id"):
            metadata["note_id"] = normalized["note_id"]
        if normalized.get("source_id"):
            metadata["source_id"] = normalized["source_id"]
        updated_at = NotebookSyncer._extract_cursor_value(normalized.get("raw", {}))
        if updated_at:
            metadata["open_notebook_updated_at"] = updated_at
        return metadata

    @staticmethod
    def _enrich_chunk(chunk: Dict[str, Any], metadata: Dict[str, Any], tags: List[str]) -> Dict[str, Any]:
        enriched = dict(chunk)
        payload_meta = dict(enriched.get("metadata") or {})
        payload_meta.update(metadata)
        if tags:
            payload_meta.setdefault("tags", tags)
        enriched["metadata"] = payload_meta
        return enriched

    @staticmethod
    def _enrich_error(error: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(error)
        payload_meta = dict(enriched.get("metadata") or {})
        payload_meta.update(metadata)
        enriched["metadata"] = payload_meta
        return enriched

    async def _request(self, client: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> httpx.Response:
        retry_policy = AsyncRetrying(
            retry=retry_if_exception_type(httpx.HTTPError),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        async for attempt in retry_policy:  # type: ignore[var-annotated]
            with attempt:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
        raise RuntimeError("Request retry loop exited unexpectedly")


def _load_syncer() -> NotebookSyncer:
    base_url = os.getenv("OPEN_NOTEBOOK_API_URL")
    mode = os.getenv("NOTEBOOK_SYNC_MODE", "live").lower()

    # If OPEN_NOTEBOOK_API_URL is missing, check if graceful degradation is enabled
    if not base_url:
        if os.getenv("NOTEBOOK_SYNC_GRACEFUL_DEGRADATION", "").lower() == "true":
            LOGGER.warning(
                "OPEN_NOTEBOOK_API_URL not set; running in DEGRADED offline mode. "
                "Syncing is disabled. Set OPEN_NOTEBOOK_API_URL to enable."
            )
            mode = "offline"
            base_url = ""  # Empty - don't pretend we have a valid URL
        else:
            raise RuntimeError(
                "OPEN_NOTEBOOK_API_URL must be set for notebook-sync. "
                "Set NOTEBOOK_SYNC_GRACEFUL_DEGRADATION=true to start in offline mode."
            )

    cursor_path = os.getenv("NOTEBOOK_SYNC_DB_PATH", "data/notebook_sync.db")
    interval = int(os.getenv("NOTEBOOK_SYNC_INTERVAL_SECONDS", "300"))
    namespace = os.getenv("NOTEBOOK_SYNC_NAMESPACE", "open-notebook")
    langextract_url = os.getenv("LANGEXTRACT_URL", "http://langextract:8084")
    extract_worker_url = os.getenv("EXTRACT_WORKER_URL", "http://extract-worker:8083")
    token = os.getenv("OPEN_NOTEBOOK_API_TOKEN")
    # Validate mode only if not already forced to offline (e.g., missing URL)
    if mode not in VALID_MODES:
        LOGGER.warning("Invalid NOTEBOOK_SYNC_MODE=%s; defaulting to 'live'", mode)
        mode = "live"
    sources_env = os.getenv("NOTEBOOK_SYNC_SOURCES")
    enabled_resources: Optional[List[str]] = None
    if sources_env:
        enabled_resources = [src.strip() for src in sources_env.split(",") if src.strip()]

    cursor_store = CursorStore(cursor_path)
    return NotebookSyncer(
        base_url=base_url,
        cursor_store=cursor_store,
        interval_seconds=interval,
        namespace=namespace,
        langextract_url=langextract_url,
        extract_worker_url=extract_worker_url,
        api_token=token,
        mode=mode,
        enabled_resources=enabled_resources,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    syncer = _load_syncer()
    app.state.syncer = syncer
    await syncer.start()
    yield
    await syncer.stop()


app = FastAPI(title="PMOVES Notebook Sync", version="1.0.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz(request: Request) -> Dict[str, Any]:
    syncer = request.app.state.syncer
    return {
        "ok": True,
        "last_sync": syncer.last_sync_time.isoformat().replace("+00:00", "Z")
        if syncer.last_sync_time
        else None,
        "interval_seconds": syncer.interval_seconds,
    }

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/sync")
async def trigger_sync(request: Request) -> Dict[str, Any]:
    syncer = request.app.state.syncer
    if syncer._lock.locked():  # pylint: disable=protected-access
        raise HTTPException(status_code=409, detail="Sync already in progress")
    await syncer.trigger_once()
    return {"ok": True, "last_sync": syncer.last_sync_time.isoformat().replace("+00:00", "Z")}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("sync:app", host="0.0.0.0", port=int(os.getenv("PORT", "8095")), reload=False)
