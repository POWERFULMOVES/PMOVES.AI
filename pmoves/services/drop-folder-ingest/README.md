# drop-folder-ingest

**The front door of the watch-folder constellation.** Drop any file into a host
folder; it lands in MinIO and is announced on `ingest.file.added.v1`, where
[`watch-folder-router`](../watch-folder-router/README.md) routes it by MIME:

```
<host drop folder>/talk.mp3
  -> drop-folder-ingest  (poll, stable check, sha256, upload)
  -> s3://assets/drop/YYYY/MM/DD/<sha12>-talk.mp3
  -> ingest.file.added.v1
  -> watch-folder-router
       audio/video -> media-audio /analyze -> ingest.transcript.ready.v1
       pdf/office  -> ingest.document.ready.v1
       other       -> ingest.text.ready.v1
```

## Role

- **Port:** `8126` inside the container: `/healthz`, `/metrics`. **Not published
  to the host** (see Networks).
- **Publishes:** `ingest.file.added.v1` (standard PMOVES envelope).
- **Subscribes:** nothing. The work is a poll loop.
- No models, no GPU, no egress.

## Behaviour

| Rule | Detail |
|---|---|
| Polling, not inotify | inotify is unreliable on bind mounts; default every 5 s |
| Ready = stable | a file is processed only when `(size, mtime)` is identical across two polls, so a half-copied file is never uploaded |
| Ignored | dotfiles and dot-directories anywhere in the path, `*.part`, `*.partial`, `*.crdownload`, `*.download`, `*.tmp`, `*.temp`, `*.swp`, `*~`, symlinks |
| Subfolders | scanned recursively; the relative path is kept under `.done/` / `.failed/` |
| Content type | extension table first, then `mimetypes`, else `application/octet-stream` |
| Object key | `<DROP_FOLDER_KEY_PREFIX>/YYYY/MM/DD/<sha256[:12]>-<sanitised name>` (UTC date, extension kept) |
| Success | file moves to `<drop>/.done/<rel>` |
| Failure | retried on later polls up to `DROP_FOLDER_MAX_ATTEMPTS`, then moved to `<drop>/.failed/<rel>` with `<name>.error.txt` |
| Empty file | straight to `.failed/` (nothing to ingest) |
| Never deletes | files are only moved; a name clash becomes `name.1.ext` |
| Idempotent | sha256 of every published file is kept in `<drop>/.drop-folder-state.json`; the same bytes dropped again (any name, across restarts) go to `.done/` without a re-publish. A corrupt state file is set aside as `.corrupt`, never overwritten |
| NATS down | nothing is processed; files wait in place |
| Folder missing | e.g. the archive drive is unplugged: `/healthz` returns 503 and nothing is created at the mount point |

Delivery is at-least-once: a crash between publish and the state write
re-publishes that one file on restart.

## Event

Standard envelope (`services/common/events.envelope` shape; the envelope schema
forbids extra top-level keys). The payload satisfies
`contracts/schemas/ingest/file-added.v1.schema.json` **and** carries the fields
consumers actually read (`bucket`/`key`/`mime_type` for the router,
`title`/`namespace` for publisher-discord and messaging-gateway):

```json
{
  "id": "6f1c...-uuid4",
  "topic": "ingest.file.added.v1",
  "ts": "2026-10-21T14:30:00.000000Z",
  "version": "v1",
  "source": "drop-folder-ingest",
  "correlation_id": "drop:9f86d081884c7d65",
  "payload": {
    "file_id": "drop:9f86d081884c7d65",
    "uri": "s3://assets/drop/2026/10/21/9f86d081884c-paper.pdf",
    "kind": "document",
    "checksum": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "size_bytes": 48213,
    "meta": {
      "source": "drop-folder",
      "original_filename": "paper.pdf",
      "relative_path": "paper.pdf",
      "mime_type": "application/pdf",
      "checksum_alg": "sha256"
    },
    "bucket": "assets",
    "key": "drop/2026/10/21/9f86d081884c-paper.pdf",
    "mime_type": "application/pdf",
    "namespace": "pmoves",
    "title": "paper.pdf",
    "uploader": "drop-folder"
  }
}
```

When the contracts are present in the image the payload is validated against the
registered schema before it is published.

## Env

| Var | Default | Purpose |
|-----|---------|---------|
| `PMOVES_DROP_FOLDER` | `./data/drop` | **host** directory mounted at `/drop` (compose) |
| `DROP_FOLDER_PATH` | `/drop` | container path watched |
| `DROP_FOLDER_BUCKET` | `assets` | target bucket (created if missing) |
| `DROP_FOLDER_KEY_PREFIX` | `drop` | object key prefix |
| `DROP_FOLDER_NAMESPACE` | `pmoves` | `payload.namespace` |
| `DROP_FOLDER_POLL_SEC` | `5` | poll interval |
| `DROP_FOLDER_MAX_ATTEMPTS` | `3` | attempts before a file goes to `.failed/` |
| `NATS_URL` | `nats://nats:4222` | bus |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_SECURE` | as media-audio | object store (same names and `S3_ENDPOINT` switch as the other MinIO consumers) |

## Run

```bash
make -C pmoves up-drop-folder-ingest DROP_FOLDER=/media/powerfulmoves/pmoves-archive/drop
```

The target creates the folder (and `.done/`, `.failed/`) as the invoking user
first, then builds and recreates the service.

> **Status at authoring:** the `Dockerfile`, the compose service block and
> `requirements.lock` are damage-control protected paths and were left for
> operator-apply; their exact content is in the PR that introduced this
> service. Until they land, `up-drop-folder-ingest` stops at
> "no compose service named 'drop-folder-ingest'".

## Networks

`pmoves_bus` (NATS, MinIO) and `pmoves_data` (MinIO / juicefs-gateway). Both are
internal, so a host port publish would be inert (DOCKER_NETWORK_HARDENING Rule 5)
and the service has no reason to be on an egress-capable network (Rule 1). Health
is read through the container healthcheck instead.

## Tests

```bash
python3 -m pytest -q pmoves/services/drop-folder-ingest/tests
```

`test_router_compat.py` feeds real drop-folder events to watch-folder-router's
handler.
