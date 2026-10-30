"""drop-folder-ingest core: host drop folder -> MinIO -> ``ingest.file.added.v1``.

Pure stdlib on purpose. ``app.py`` owns FastAPI, the MinIO client and the NATS
connection and injects them here as two callables (``upload`` / ``publish``), so
every rule below is testable on a host without the service's runtime deps.

Lifecycle of one dropped file::

    <drop>/talk.mp3                         operator drops it (any depth)
      poll N:   (size, mtime) observed      not ready -- may still be writing
      poll N+1: (size, mtime) unchanged     ready
      sha256 already in the state file?     -> <drop>/.done/talk.mp3 (no re-publish)
      upload s3://<bucket>/drop/YYYY/MM/DD/<sha12>-talk.mp3
      publish ingest.file.added.v1 (standard envelope)
      record sha256 in <drop>/.drop-folder-state.json
      move -> <drop>/.done/talk.mp3
    on error: retry on later polls up to max_attempts, then
      move -> <drop>/.failed/talk.mp3  +  talk.mp3.error.txt

Nothing is ever deleted: files are only moved, and a move never overwrites (a
name clash gets a ``.N`` suffix before the extension).

Delivery is at-least-once: a crash between publish and the state write
re-publishes that one file on restart. The router treats a repeat as a repeat;
the alternative (record before publish) would silently lose files instead.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("drop-folder-ingest")

SUBJECT = "ingest.file.added.v1"
SOURCE = "drop-folder-ingest"  # envelope.source: the emitting service
META_SOURCE = "drop-folder"  # payload.meta.source: the ingestion route

DONE_DIR = ".done"
FAILED_DIR = ".failed"
STATE_FILE = ".drop-folder-state.json"

# Partial-download / editor-scratch suffixes. A file carrying one is by
# definition not finished, however stable its size looks.
IGNORED_SUFFIXES = (
    ".part", ".partial", ".crdownload", ".download", ".tmp", ".temp", ".swp", ".!qb", ".aria2",
)

# Checked BEFORE mimetypes: these are either missing from slim images'
# mime tables or come back as something the router would misroute.
EXT_MIME: Dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/opus",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".rtf": "application/rtf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".html": "text/html",
    ".htm": "text/html",
    ".srt": "text/plain",
    ".vtt": "text/vtt",
}

DOCUMENT_MIMES = {
    "application/pdf",
    "application/msword",
    "application/rtf",
    "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

Snapshot = Dict[Path, Tuple[int, int]]
Uploader = Callable[[str, str, Path, str, str], None]
Publisher = Callable[[str, bytes], Awaitable[None]]


# ── config ───────────────────────────────────────────────────────────────────
@dataclass
class Config:
    drop_dir: Path
    bucket: str = "assets"
    key_prefix: str = "drop"
    namespace: str = "pmoves"
    poll_interval: float = 5.0
    max_attempts: int = 3

    @classmethod
    def from_env(cls) -> "Config":
        env = os.environ
        return cls(
            drop_dir=Path(env.get("DROP_FOLDER_PATH", "/drop")),
            bucket=env.get("DROP_FOLDER_BUCKET", "assets"),
            key_prefix=env.get("DROP_FOLDER_KEY_PREFIX", "drop").strip("/") or "drop",
            namespace=env.get("DROP_FOLDER_NAMESPACE", "pmoves"),
            poll_interval=float(env.get("DROP_FOLDER_POLL_SEC", "5")),
            max_attempts=max(1, int(env.get("DROP_FOLDER_MAX_ATTEMPTS", "3"))),
        )


# ── discovery ────────────────────────────────────────────────────────────────
def is_ignored(rel: Path) -> bool:
    """Dotfiles/dot-dirs anywhere in the path, partial downloads, ``~`` backups."""
    if any(part.startswith(".") for part in rel.parts):
        return True
    name = rel.name.lower()
    return name.endswith("~") or name.endswith(IGNORED_SUFFIXES)


def scan(drop_dir: Path) -> Snapshot:
    """{relative path: (size, mtime_ns)} for every candidate regular file.

    Dot-directories (``.done``, ``.failed``, anything hidden) are pruned, which
    is what keeps processed files from being re-ingested.
    """
    out: Snapshot = {}
    for root, dirs, files in os.walk(drop_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            full = Path(root) / name
            rel = full.relative_to(drop_dir)
            if is_ignored(rel):
                continue
            try:
                st = full.stat()
            except FileNotFoundError:  # moved away mid-walk
                continue
            if not full.is_file() or full.is_symlink():
                continue
            out[rel] = (st.st_size, st.st_mtime_ns)
    return out


class StabilityTracker:
    """A file is ready once (size, mtime) is identical across two polls."""

    def __init__(self) -> None:
        self._last: Snapshot = {}

    def observe(self, snapshot: Snapshot) -> List[Path]:
        ready = sorted(p for p, sig in snapshot.items() if self._last.get(p) == sig)
        self._last = dict(snapshot)
        return ready

    def forget(self, rel: Path) -> None:
        self._last.pop(rel, None)


# ── classification / naming ──────────────────────────────────────────────────
def guess_mime(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    if ext in EXT_MIME:
        return EXT_MIME[ext]
    mime, _ = mimetypes.guess_type(name, strict=False)
    return mime or "application/octet-stream"


def kind_for(mime: str) -> str:
    """Map a MIME type onto the file-added.v1 ``kind`` enum."""
    mime = (mime or "").lower()
    for prefix, kind in (("audio/", "audio"), ("video/", "video"), ("image/", "image"), ("text/", "document")):
        if mime.startswith(prefix):
            return kind
    if mime in DOCUMENT_MIMES:
        return "document"
    return "other"


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(name: str) -> str:
    stem, ext = os.path.splitext(name)
    stem = _UNSAFE.sub("-", stem).strip("-.") or "file"
    ext = _UNSAFE.sub("", ext)
    return f"{stem[:120]}{ext}"


def object_key(prefix: str, sha256: str, name: str, now: datetime) -> str:
    """``<prefix>/YYYY/MM/DD/<sha12>-<safe name>`` -- date-sharded, collision-free."""
    return f"{prefix.strip('/')}/{now:%Y/%m/%d}/{sha256[:12]}-{safe_name(name)}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ── event ────────────────────────────────────────────────────────────────────
def build_event(
    *,
    bucket: str,
    key: str,
    sha256: str,
    size: int,
    mime_type: str,
    original_filename: str,
    relative_path: str,
    namespace: str,
    now: datetime,
) -> dict:
    """The standard PMOVES envelope around a file-added.v1 payload.

    The envelope matches ``services/common/events.envelope`` (and pdf-ingest's
    publisher); its schema forbids extra top-level keys. The payload satisfies
    ``file-added.v1`` (file_id / uri / kind + checksum / size_bytes / meta) and
    ALSO carries the de-facto fields the consumers read: ``bucket`` / ``key`` /
    ``mime_type`` (watch-folder-router), ``title`` / ``namespace``
    (publisher-discord, messaging-gateway). The schema allows additional
    properties, so both hold at once.
    """
    file_id = f"drop:{sha256[:16]}"
    payload = {
        "file_id": file_id,
        "uri": f"s3://{bucket}/{key}",
        "kind": kind_for(mime_type),
        "checksum": sha256,
        "size_bytes": int(size),
        "meta": {
            "source": META_SOURCE,
            "original_filename": original_filename,
            "relative_path": relative_path,
            "mime_type": mime_type,
            "checksum_alg": "sha256",
        },
        "bucket": bucket,
        "key": key,
        "mime_type": mime_type,
        "namespace": namespace,
        "title": original_filename,
        "uploader": META_SOURCE,
    }
    return {
        "id": str(uuid.uuid4()),
        "topic": SUBJECT,
        "ts": _iso(now),
        "version": "v1",
        "source": SOURCE,
        "correlation_id": file_id,
        "payload": payload,
    }


# ── state ────────────────────────────────────────────────────────────────────
class StateStore:
    """sha256 -> what was published, persisted in the drop dir (a dotfile, so
    the scanner never picks it up). Written atomically via tmp + rename."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.published: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            self.published = dict(data.get("published") or {})
        except (ValueError, OSError, AttributeError):
            # Never clobber an unreadable state file: set it aside for the operator.
            aside = _unique(self.path.with_name(self.path.name + ".corrupt"))
            logger.error("state file %s unreadable; preserved as %s", self.path, aside.name)
            try:
                os.replace(self.path, aside)
            except OSError:
                logger.exception("could not set aside corrupt state file")
            self.published = {}

    def seen(self, sha256: str) -> bool:
        return sha256 in self.published

    def record(self, sha256: str, info: dict) -> None:
        self.published[sha256] = info
        self.save()

    def save(self) -> None:
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps({"version": 1, "published": self.published}, indent=1, sort_keys=True))
        os.replace(tmp, self.path)


# ── moves ────────────────────────────────────────────────────────────────────
def _unique(target: Path) -> Path:
    """``target`` if free, else ``name.1.ext``, ``name.2.ext``, ... (never overwrite)."""
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    n = 1
    while True:
        cand = target.with_name(f"{stem}.{n}{suffix}")
        if not cand.exists():
            return cand
        n += 1


def move_aside(drop_dir: Path, rel: Path, dirname: str) -> Path:
    target = _unique(drop_dir / dirname / rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(drop_dir / rel), str(target))
    return target


def _write_error(target: Path, rel: Path, exc: BaseException, attempts: int, now: datetime) -> None:
    sidecar = _unique(target.with_name(target.name + ".error.txt"))
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).strip()
    sidecar.write_text(
        f"file: {rel}\nfailed_at: {_iso(now)}\nattempts: {attempts}\n"
        f"error: {type(exc).__name__}: {exc}\n\n{tb}\n"
        "\nTo retry: move the file back into the drop folder.\n"
    )


class EmptyFileError(ValueError):
    pass


# ── the ingestor ─────────────────────────────────────────────────────────────
class DropFolderIngestor:
    def __init__(
        self,
        config: Config,
        upload: Uploader,
        publish: Publisher,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.config = config
        self.upload = upload
        self.publish = publish
        self.clock = clock
        self.tracker = StabilityTracker()
        self.attempts: Dict[Path, int] = {}
        self._state: Optional[StateStore] = None
        self.totals = {"published": 0, "duplicate": 0, "failed": 0, "retry": 0, "bytes": 0}
        self.last_scan: Optional[str] = None
        self.last_error: Optional[str] = None

    @property
    def state(self) -> StateStore:
        if self._state is None:
            self._state = StateStore(self.config.drop_dir / STATE_FILE)
        return self._state

    def drop_folder_ok(self) -> bool:
        d = self.config.drop_dir
        return d.is_dir() and os.access(d, os.W_OK | os.X_OK)

    async def scan_once(self, can_publish: bool = True) -> dict:
        summary = {"drop_folder_ok": self.drop_folder_ok(), "pending": 0, "ready": 0,
                   "published": 0, "duplicate": 0, "failed": 0, "retry": 0}
        if not summary["drop_folder_ok"]:
            # Unplugged drive / missing mount: report, do not raise, do not create it
            # (creating it would write into the mount point on the root filesystem).
            self.last_error = f"drop folder {self.config.drop_dir} missing or not writable"
            return summary
        snapshot = await asyncio.to_thread(scan, self.config.drop_dir)
        ready = self.tracker.observe(snapshot)
        summary["pending"] = len(snapshot) - len(ready)
        summary["ready"] = len(ready)
        self.last_scan = _iso(self.clock())
        if not can_publish:
            # Bus down: leave everything in place; it is retried once NATS is back.
            summary["pending"] = len(snapshot)
            return summary
        for rel in ready:
            outcome = await self._process(rel)
            summary[outcome] += 1
            self.totals[outcome] += 1
        return summary

    async def _process(self, rel: Path) -> str:
        cfg = self.config
        path = cfg.drop_dir / rel
        now = self.clock()
        try:
            size = path.stat().st_size
            if size == 0:
                raise EmptyFileError("empty file (0 bytes): nothing to ingest")
            sha = await asyncio.to_thread(sha256_file, path)
            if self.state.seen(sha):
                prior = self.state.published[sha]
                logger.info("%s duplicates already-published %s; not re-publishing", rel, prior.get("key"))
                await asyncio.to_thread(move_aside, cfg.drop_dir, rel, DONE_DIR)
                self._forget(rel)
                return "duplicate"
            mime = guess_mime(rel.name)
            key = object_key(cfg.key_prefix, sha, rel.name, now)
            await asyncio.to_thread(self.upload, cfg.bucket, key, path, mime, sha)
            env = build_event(
                bucket=cfg.bucket, key=key, sha256=sha, size=size, mime_type=mime,
                original_filename=rel.name, relative_path=rel.as_posix(),
                namespace=cfg.namespace, now=now,
            )
            await self.publish(SUBJECT, json.dumps(env).encode())
            self.state.record(sha, {
                "file_id": env["payload"]["file_id"], "key": key, "uri": env["payload"]["uri"],
                "name": rel.as_posix(), "size_bytes": size, "published_at": env["ts"],
            })
            await asyncio.to_thread(move_aside, cfg.drop_dir, rel, DONE_DIR)
            self._forget(rel)
            self.totals["bytes"] += size
            logger.info("published %s -> s3://%s/%s (%s)", rel, cfg.bucket, key, mime)
            return "published"
        except Exception as exc:  # noqa: BLE001 - every failure is per-file
            attempts = self.attempts.get(rel, 0) + 1
            self.attempts[rel] = attempts
            self.last_error = f"{rel}: {type(exc).__name__}: {exc}"
            if attempts < cfg.max_attempts and not isinstance(exc, EmptyFileError):
                logger.warning("attempt %d/%d failed for %s: %s", attempts, cfg.max_attempts, rel, exc)
                return "retry"
            logger.error("giving up on %s after %d attempt(s): %s", rel, attempts, exc)
            try:
                target = await asyncio.to_thread(move_aside, cfg.drop_dir, rel, FAILED_DIR)
                _write_error(target, rel, exc, attempts, now)
            except Exception:  # noqa: BLE001
                logger.exception("could not move %s to %s", rel, FAILED_DIR)
            self._forget(rel)
            return "failed"

    def _forget(self, rel: Path) -> None:
        self.attempts.pop(rel, None)
        self.tracker.forget(rel)
