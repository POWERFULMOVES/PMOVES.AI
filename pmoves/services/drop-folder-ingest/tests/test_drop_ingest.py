"""drop-folder-ingest: host drop folder -> MinIO -> ingest.file.added.v1.

These import ``drop_ingest`` directly (not ``app``) because app.py pulls in
fastapi / minio / nats at module scope and the behaviour under test -- stability
detection, event shape, move-aside, idempotency, ignore rules -- is pure
filesystem + dict work. MinIO and NATS are replaced by recording fakes.

The event-shape tests validate against the REAL registered contracts
(``pmoves/contracts``), not a local copy, so drift between this publisher and
the contract fails here rather than on the bus.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_DIR.parents[2]
CONTRACTS = REPO_ROOT / "pmoves" / "contracts"
FILE_ADDED_SCHEMA = CONTRACTS / "schemas" / "ingest" / "file-added.v1.schema.json"
ENVELOPE_SCHEMA = CONTRACTS / "schemas" / "common" / "envelope.schema.json"

FIXED_NOW = datetime(2026, 10, 21, 14, 30, 0, tzinfo=timezone.utc)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve annotations via sys.modules
    spec.loader.exec_module(module)
    return module


di = _load("drop_folder_ingest_core", SERVICE_DIR / "drop_ingest.py")


# ── fakes ────────────────────────────────────────────────────────────────────
class FakeUploader:
    def __init__(self, fail_with: Exception | None = None):
        self.calls: list[dict] = []
        self.fail_with = fail_with

    def __call__(self, bucket, key, path, content_type, sha256):
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append(
            {"bucket": bucket, "key": key, "path": Path(path), "content_type": content_type,
             "sha256": sha256, "data": Path(path).read_bytes()}
        )


class FakePublisher:
    def __init__(self, fail_with: Exception | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.fail_with = fail_with

    async def __call__(self, subject: str, data: bytes):
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append((subject, json.loads(data.decode())))


def _ingestor(drop: Path, uploader=None, publisher=None, **cfg):
    config = di.Config(drop_dir=drop, **cfg)
    return di.DropFolderIngestor(
        config,
        upload=uploader or FakeUploader(),
        publish=publisher or FakePublisher(),
        clock=lambda: FIXED_NOW,
    )


def _settle(ing, polls: int = 2, can_publish: bool = True):
    """Run enough polls for a freshly dropped, untouched file to be stable."""
    out = None
    for _ in range(polls):
        out = asyncio.run(ing.scan_once(can_publish=can_publish))
    return out


def _all_files(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


# ── stability detection ──────────────────────────────────────────────────────
def test_a_file_is_ready_only_after_two_identical_observations():
    t = di.StabilityTracker()
    snap = {Path("a.mp3"): (10, 111)}
    assert t.observe(snap) == []
    assert t.observe(snap) == [Path("a.mp3")]


def test_a_file_still_growing_is_not_ready():
    t = di.StabilityTracker()
    assert t.observe({Path("a.mp3"): (10, 111)}) == []
    assert t.observe({Path("a.mp3"): (20, 112)}) == []  # still being written
    assert t.observe({Path("a.mp3"): (30, 113)}) == []
    assert t.observe({Path("a.mp3"): (30, 113)}) == [Path("a.mp3")]


def test_an_mtime_change_alone_resets_stability():
    t = di.StabilityTracker()
    t.observe({Path("a.txt"): (5, 1)})
    assert t.observe({Path("a.txt"): (5, 2)}) == []


def test_a_vanished_file_is_forgotten():
    t = di.StabilityTracker()
    t.observe({Path("a.txt"): (5, 1)})
    t.observe({})
    # Reappearing starts the stability clock again.
    assert t.observe({Path("a.txt"): (5, 1)}) == []


def test_a_half_written_file_is_not_uploaded(tmp_path):
    up = FakeUploader()
    ing = _ingestor(tmp_path, uploader=up)
    f = tmp_path / "talk.mp3"
    f.write_bytes(b"ID3" + b"\0" * 10)
    asyncio.run(ing.scan_once())
    f.write_bytes(b"ID3" + b"\0" * 100)  # writer still appending
    asyncio.run(ing.scan_once())
    assert up.calls == []
    assert f.exists()


# ── ignore rules ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "name",
    [".hidden", "movie.mp4.part", "file.crdownload", "upload.tmp", "x.PART", "doc.pdf~"],
)
def test_ignored_names(name):
    assert di.is_ignored(Path(name))


@pytest.mark.parametrize("name", ["talk.mp3", "paper.pdf", "notes.txt", "sub/clip.mp4"])
def test_regular_names_are_not_ignored(name):
    assert not di.is_ignored(Path(name))


def test_scan_skips_dotfiles_partials_and_the_service_own_dirs(tmp_path):
    (tmp_path / ".done").mkdir()
    (tmp_path / ".done" / "old.pdf").write_bytes(b"%PDF")
    (tmp_path / ".failed").mkdir()
    (tmp_path / ".failed" / "bad.pdf").write_bytes(b"%PDF")
    (tmp_path / ".drop-folder-state.json").write_text("{}")
    (tmp_path / ".DS_Store").write_bytes(b"x")
    (tmp_path / "big.mkv.part").write_bytes(b"x")
    (tmp_path / "dl.crdownload").write_bytes(b"x")
    (tmp_path / "w.tmp").write_bytes(b"x")
    (tmp_path / "keep.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "album").mkdir()
    (tmp_path / "album" / "track.flac").write_bytes(b"fLaC")
    assert set(di.scan(tmp_path)) == {Path("keep.pdf"), Path("album/track.flac")}


# ── mime / kind / key ────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "name,mime,kind",
    [
        ("talk.mp3", "audio/mpeg", "audio"),
        ("memo.m4a", "audio/mp4", "audio"),
        ("song.flac", "audio/flac", "audio"),
        ("clip.mp4", "video/mp4", "video"),
        ("clip.mkv", "video/x-matroska", "video"),
        ("clip.webm", "video/webm", "video"),
        ("photo.png", "image/png", "image"),
        ("photo.JPG", "image/jpeg", "image"),
        ("paper.pdf", "application/pdf", "document"),
        ("deck.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "document"),
        ("report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document"),
        ("notes.txt", "text/plain", "document"),
        ("readme.md", "text/markdown", "document"),
        ("blob.zzz", "application/octet-stream", "other"),
    ],
)
def test_mime_and_kind(name, mime, kind):
    assert di.guess_mime(name) == mime
    assert di.kind_for(mime) == kind


def test_object_key_is_date_prefixed_and_keeps_the_extension():
    sha = "ab" * 32
    key = di.object_key("drop", sha, "My Talk (final).MP3", FIXED_NOW)
    assert key.startswith("drop/2026/10/21/")
    assert key.endswith(".MP3")
    assert " " not in key and "(" not in key
    assert sha[:12] in key


# ── event shape ──────────────────────────────────────────────────────────────
def _sample_event(**over):
    kw = dict(
        bucket="assets",
        key="drop/2026/10/21/abcdef012345-paper.pdf",
        sha256="ab" * 32,
        size=1234,
        mime_type="application/pdf",
        original_filename="paper.pdf",
        relative_path="paper.pdf",
        namespace="pmoves",
        now=FIXED_NOW,
    )
    kw.update(over)
    return di.build_event(**kw)


def test_event_envelope_validates_against_the_registered_envelope_schema():
    env = _sample_event()
    jsonschema.validate(env, json.loads(ENVELOPE_SCHEMA.read_text()))
    assert env["topic"] == "ingest.file.added.v1"
    assert env["version"] == "v1"
    assert env["source"] == "drop-folder-ingest"
    assert env["correlation_id"] == env["payload"]["file_id"]


def test_event_payload_validates_against_the_registered_file_added_schema():
    topics = json.loads((CONTRACTS / "topics.json").read_text())["topics"]
    assert topics["ingest.file.added.v1"]["schema"] == "schemas/ingest/file-added.v1.schema.json"
    payload = _sample_event()["payload"]
    jsonschema.validate(payload, json.loads(FILE_ADDED_SCHEMA.read_text()))


def test_event_payload_carries_what_the_router_and_notifiers_read():
    p = _sample_event()["payload"]
    # schema-required
    assert p["file_id"] == "drop:" + ("ab" * 32)[:16]
    assert p["uri"] == "s3://assets/drop/2026/10/21/abcdef012345-paper.pdf"
    assert p["kind"] == "document"
    assert p["checksum"] == "ab" * 32  # plain hex sha256, as pdf-ingest publishes
    assert p["size_bytes"] == 1234
    # watch-folder-router reads bucket/key/mime_type; publisher-discord reads title/bucket/namespace
    assert p["bucket"] == "assets"
    assert p["key"] == "drop/2026/10/21/abcdef012345-paper.pdf"
    assert p["mime_type"] == "application/pdf"
    assert p["namespace"] == "pmoves"
    assert p["title"] == "paper.pdf"
    assert p["meta"]["source"] == "drop-folder"
    assert p["meta"]["original_filename"] == "paper.pdf"
    assert p["meta"]["relative_path"] == "paper.pdf"


@pytest.mark.parametrize(
    "name,mime", [("a.mp3", "audio/mpeg"), ("a.mp4", "video/mp4"), ("a.png", "image/png"),
                  ("a.zzz", "application/octet-stream")],
)
def test_every_kind_validates(name, mime):
    payload = _sample_event(mime_type=mime, original_filename=name, relative_path=name)["payload"]
    jsonschema.validate(payload, json.loads(FILE_ADDED_SCHEMA.read_text()))


# ── end-to-end over the fakes ────────────────────────────────────────────────
def test_a_stable_file_is_uploaded_published_and_moved_to_done(tmp_path):
    up, pub = FakeUploader(), FakePublisher()
    ing = _ingestor(tmp_path, uploader=up, publisher=pub)
    body = b"%PDF-1.4 hello"
    (tmp_path / "paper.pdf").write_bytes(body)

    _settle(ing)

    assert len(up.calls) == 1
    call = up.calls[0]
    assert call["bucket"] == "assets"
    assert call["key"].startswith("drop/2026/10/21/")
    assert call["content_type"] == "application/pdf"
    assert call["data"] == body
    import hashlib

    sha = hashlib.sha256(body).hexdigest()
    assert call["sha256"] == sha

    assert len(pub.calls) == 1
    subject, env = pub.calls[0]
    assert subject == "ingest.file.added.v1"
    assert env["payload"]["checksum"] == sha
    assert env["payload"]["key"] == call["key"]
    jsonschema.validate(env["payload"], json.loads(FILE_ADDED_SCHEMA.read_text()))

    assert not (tmp_path / "paper.pdf").exists()
    assert (tmp_path / ".done" / "paper.pdf").read_bytes() == body
    state = json.loads((tmp_path / ".drop-folder-state.json").read_text())
    assert sha in state["published"]


def test_nested_paths_are_preserved_under_done(tmp_path):
    ing = _ingestor(tmp_path)
    (tmp_path / "album").mkdir()
    (tmp_path / "album" / "t1.flac").write_bytes(b"fLaC1")
    _settle(ing)
    assert (tmp_path / ".done" / "album" / "t1.flac").exists()


def test_nothing_is_processed_while_the_bus_is_down(tmp_path):
    up, pub = FakeUploader(), FakePublisher()
    ing = _ingestor(tmp_path, uploader=up, publisher=pub)
    (tmp_path / "a.txt").write_text("hello")
    _settle(ing, polls=3, can_publish=False)
    assert up.calls == [] and pub.calls == []
    assert (tmp_path / "a.txt").exists()
    _settle(ing, polls=1, can_publish=True)  # already stable: goes on the next poll
    assert len(pub.calls) == 1


# ── idempotency ──────────────────────────────────────────────────────────────
def test_same_content_dropped_again_is_not_republished(tmp_path):
    up, pub = FakeUploader(), FakePublisher()
    ing = _ingestor(tmp_path, uploader=up, publisher=pub)
    (tmp_path / "a.txt").write_text("same bytes")
    _settle(ing)
    (tmp_path / "copy-of-a.txt").write_text("same bytes")
    _settle(ing)
    assert len(up.calls) == 1 and len(pub.calls) == 1
    assert (tmp_path / ".done" / "copy-of-a.txt").exists()


def test_idempotency_survives_a_restart(tmp_path):
    up1, pub1 = FakeUploader(), FakePublisher()
    (tmp_path / "a.txt").write_text("persisted")
    _settle(_ingestor(tmp_path, uploader=up1, publisher=pub1))
    assert len(pub1.calls) == 1

    # New process, same drop dir: the state file is the memory.
    up2, pub2 = FakeUploader(), FakePublisher()
    ing2 = _ingestor(tmp_path, uploader=up2, publisher=pub2)
    (tmp_path / "again.txt").write_text("persisted")
    _settle(ing2)
    assert up2.calls == [] and pub2.calls == []
    assert (tmp_path / ".done" / "again.txt").exists()


def test_a_corrupt_state_file_is_preserved_not_clobbered(tmp_path):
    (tmp_path / ".drop-folder-state.json").write_text("{not json")
    ing = _ingestor(tmp_path)
    (tmp_path / "a.txt").write_text("x")
    _settle(ing)
    # The unreadable file was set aside (never deleted) and a fresh one written.
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".drop-folder-state.json.corrupt")]
    assert leftovers, "corrupt state file must be preserved for the operator"
    json.loads((tmp_path / ".drop-folder-state.json").read_text())


# ── failure handling ─────────────────────────────────────────────────────────
def test_upload_failure_retries_then_moves_to_failed_with_a_sidecar(tmp_path):
    up = FakeUploader(fail_with=RuntimeError("minio unreachable"))
    pub = FakePublisher()
    ing = _ingestor(tmp_path, uploader=up, publisher=pub, max_attempts=2)
    (tmp_path / "talk.mp3").write_bytes(b"ID3data")

    _settle(ing, polls=2)  # stable on poll 2 -> attempt 1 fails, file stays for retry
    assert (tmp_path / "talk.mp3").exists()
    _settle(ing, polls=1)  # attempt 2 fails -> give up
    assert not (tmp_path / "talk.mp3").exists()
    assert (tmp_path / ".failed" / "talk.mp3").read_bytes() == b"ID3data"
    err = (tmp_path / ".failed" / "talk.mp3.error.txt").read_text()
    assert "minio unreachable" in err
    assert pub.calls == []


def test_publish_failure_moves_to_failed_and_does_not_record_state(tmp_path):
    pub = FakePublisher(fail_with=RuntimeError("nats publish timeout"))
    ing = _ingestor(tmp_path, publisher=pub, max_attempts=1)
    (tmp_path / "a.txt").write_text("x")
    _settle(ing)
    assert (tmp_path / ".failed" / "a.txt").exists()
    assert "nats publish timeout" in (tmp_path / ".failed" / "a.txt.error.txt").read_text()
    state_path = tmp_path / ".drop-folder-state.json"
    if state_path.exists():
        assert json.loads(state_path.read_text())["published"] == {}


def test_an_empty_file_is_failed_not_published(tmp_path):
    up, pub = FakeUploader(), FakePublisher()
    ing = _ingestor(tmp_path, uploader=up, publisher=pub)
    (tmp_path / "empty.txt").write_bytes(b"")
    _settle(ing)
    assert up.calls == [] and pub.calls == []
    assert (tmp_path / ".failed" / "empty.txt").exists()
    assert "empty" in (tmp_path / ".failed" / "empty.txt.error.txt").read_text().lower()


def test_moves_never_overwrite_an_existing_file(tmp_path):
    (tmp_path / ".done").mkdir()
    (tmp_path / ".done" / "a.txt").write_text("earlier")
    ing = _ingestor(tmp_path)
    (tmp_path / "a.txt").write_text("later")
    _settle(ing)
    assert (tmp_path / ".done" / "a.txt").read_text() == "earlier"
    moved = [p for p in (tmp_path / ".done").iterdir() if p.name != "a.txt"]
    assert len(moved) == 1 and moved[0].read_text() == "later"
    assert moved[0].suffix == ".txt"  # extension kept so the file stays openable


def test_nothing_is_ever_deleted(tmp_path):
    ing = _ingestor(tmp_path, uploader=FakeUploader(fail_with=RuntimeError("x")), max_attempts=1)
    names = ["a.txt", "b.pdf", "c.mp3", "d.zzz"]
    for n in names:
        (tmp_path / n).write_bytes(n.encode())
    _settle(ing)
    data_files = {p for p in _all_files(tmp_path) if not p.endswith(".error.txt")
                  and not p.startswith(".drop-folder-state")}
    assert data_files == {f".failed/{n}" for n in names}


def test_scan_once_reports_counts(tmp_path):
    ing = _ingestor(tmp_path)
    (tmp_path / "a.txt").write_text("1")
    first = asyncio.run(ing.scan_once())
    assert first["pending"] == 1 and first["published"] == 0
    second = asyncio.run(ing.scan_once())
    assert second["published"] == 1


def test_missing_drop_folder_is_reported_not_raised(tmp_path):
    ing = _ingestor(tmp_path / "unplugged")
    out = asyncio.run(ing.scan_once())
    assert out["drop_folder_ok"] is False


# ── config ───────────────────────────────────────────────────────────────────
def test_config_from_env_defaults(monkeypatch):
    for var in ("DROP_FOLDER_PATH", "DROP_FOLDER_BUCKET", "DROP_FOLDER_KEY_PREFIX",
                "DROP_FOLDER_NAMESPACE", "DROP_FOLDER_POLL_SEC", "DROP_FOLDER_MAX_ATTEMPTS"):
        monkeypatch.delenv(var, raising=False)
    cfg = di.Config.from_env()
    assert cfg.drop_dir == Path("/drop")
    assert cfg.bucket == "assets"
    assert cfg.key_prefix == "drop"
    assert cfg.namespace == "pmoves"
    assert cfg.poll_interval == 5.0
    assert cfg.max_attempts == 3


def test_config_from_env_overrides(monkeypatch):
    monkeypatch.setenv("DROP_FOLDER_PATH", "/x")
    monkeypatch.setenv("DROP_FOLDER_BUCKET", "inbox")
    monkeypatch.setenv("DROP_FOLDER_POLL_SEC", "2.5")
    cfg = di.Config.from_env()
    assert (cfg.drop_dir, cfg.bucket, cfg.poll_interval) == (Path("/x"), "inbox", 2.5)
