#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["nats-py==2.10.0"]
# ///
"""Durable per-identity NATS agent inbox (JetStream) plus optional broadcast tap.

Subcommands
-----------
subscribe    Pull this agent's durable JetStream consumer and append every
             message to the per-agent JSONL inbox. ``--broadcast`` additionally
             taps the legacy core-NATS subjects (task/branch/CHIT/P7/presence).
send         Publish one directed envelope to ``pmoves.agent.inbox.<to>.v1``
             and wait for the JetStream publish ack.
read         Print inbox records newer than the per-agent cursor, then advance it.
ensure       Idempotently create the AGENT_INBOX stream and an agent's consumer.
render-unit  Print the systemd --user unit template with paths filled in.

Durability: messages land in the ``AGENT_INBOX`` stream (file storage, limits
retention, 14d max age, size-capped). Each agent has a durable pull consumer
``inbox-<agent_id>`` filtered to its own subject, so a message sent while the
recipient's inbox is down is delivered when it comes back.

Stream and consumer management is CREATE-ONLY: an existing stream or consumer
is never updated, deleted or purged. If one exists with a config that cannot
serve the inbox (wrong subjects / filter), the tool refuses (exit 1) and says
so rather than "fixing" it.

Exit codes: 0 ok, 1 refused, 3 could not measure (missing identity, NATS
unreachable, no JetStream, no inbox file yet).

Never prints NATS_URL or credentials; connection failures report the URL shape.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import signal
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_COULD_NOT_MEASURE = 3

DEFAULT_SUBJECTS = (
    "claw.task.assign.v1",
    "branch.>",
    "chit.>",
    "p7.>",
    "owner.presence.>",
)

# Directed inbox. <agent_id> sits before the version token, matching the
# documented `mesh.agent.<node>.capabilities.v1` / `branch.<branch>.trail.v1`
# convention (.claude/context/nats-subjects.md).
INBOX_SUBJECT_PREFIX = "pmoves.agent.inbox"
INBOX_SUBJECT_VERSION = "v1"
INBOX_STREAM_SUBJECT = f"{INBOX_SUBJECT_PREFIX}.*.{INBOX_SUBJECT_VERSION}"

STREAM_NAME = "AGENT_INBOX"
STREAM_MAX_AGE_SECONDS = 14 * 24 * 3600
STREAM_MAX_BYTES = 512 * 1024 * 1024
STREAM_MAX_MSG_SIZE = 1024 * 1024
STREAM_DUPLICATE_WINDOW_SECONDS = 120
MAX_BODY_BYTES = 512 * 1024

AGENT_ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
ENVELOPE_KEYS = ("from", "to", "ts", "id", "reply_to", "body")


class InboxError(Exception):
    """Raised with an exit code attached."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


async def _ignore_nats_error(exc: Exception) -> None:
    return None


# --------------------------------------------------------------------------
# Pure helpers (unit-tested without NATS)
# --------------------------------------------------------------------------


def resolve_host_nats_url(url: str) -> str:
    if os.environ.get("PMOVES_NATS_NO_HOST_REWRITE", "").lower() in ("1", "true", "yes"):
        return url
    parts = urlsplit(url)
    userinfo = ""
    hostport = parts.netloc
    if "@" in hostport:
        userinfo, hostport = hostport.rsplit("@", 1)
        userinfo += "@"
    if hostport == "nats":
        hostport = "127.0.0.1"
    elif hostport.startswith("nats:"):
        hostport = "127.0.0.1:" + hostport.split(":", 1)[1]
    return urlunsplit((parts.scheme, userinfo + hostport, parts.path, parts.query, parts.fragment))


def url_shape(url: str) -> str:
    """Describe a NATS URL without credentials: scheme, auth presence, host, port."""
    if not url:
        return "unset"
    parts = urlsplit(url)
    auth = "with-userinfo" if "@" in parts.netloc else "no-userinfo"
    try:
        port = parts.port
    except ValueError:
        port = "?"
    return f"{parts.scheme or '?'}://<{auth}>{parts.hostname or '?'}:{port}"


def parse_subjects(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_SUBJECTS)
    subjects = [part.strip() for part in value.split(",") if part.strip()]
    return subjects or list(DEFAULT_SUBJECTS)


def normalize_agent_id(value: str | None) -> str:
    """Return the canonical agent id or raise InboxError.

    Missing -> exit 3 (fail closed: no identity, nothing can be measured).
    Present but not a single subject token -> exit 1 (refused).
    Lower-cased so `B850-CLAUDE` and `b850-claude` cannot split one inbox in two.
    """
    if value is None or not str(value).strip():
        raise InboxError("agent id is required (pass --agent-id / TO / FROM / AGENT)", EXIT_COULD_NOT_MEASURE)
    agent = str(value).strip().lower()
    if not AGENT_ID_RE.match(agent):
        raise InboxError(
            f"agent id {agent!r} is not a single subject token (allowed: a-z 0-9 _ -, max 64)",
            EXIT_REFUSED,
        )
    return agent


def inbox_subject(agent_id: str) -> str:
    return f"{INBOX_SUBJECT_PREFIX}.{normalize_agent_id(agent_id)}.{INBOX_SUBJECT_VERSION}"


def durable_name(agent_id: str) -> str:
    return f"inbox-{normalize_agent_id(agent_id)}"


def build_envelope(
    *,
    sender: str,
    recipient: str,
    body: Any,
    reply_to: str | None = None,
    msg_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    sender = normalize_agent_id(sender)
    recipient = normalize_agent_id(recipient)
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "from": sender,
        "to": recipient,
        "ts": ts,
        "id": msg_id or str(uuid.uuid4()),
        "reply_to": reply_to if reply_to is not None else inbox_subject(sender),
        "body": body,
    }


def encode_envelope(envelope: dict[str, Any]) -> bytes:
    missing = [k for k in ENVELOPE_KEYS if k not in envelope]
    if missing:
        raise InboxError(f"envelope missing keys: {missing}", EXIT_REFUSED)
    data = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_BODY_BYTES:
        raise InboxError(f"envelope is {len(data)} bytes; limit is {MAX_BODY_BYTES}", EXIT_REFUSED)
    return data


def default_inbox_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "PMOVES" / "agent-inbox"
    root = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(root) / "pmoves" / "agent-inbox"


def inbox_path(agent_id: str, inbox_dir: str | None = None) -> Path:
    safe_agent = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in agent_id)
    root = Path(inbox_dir) if inbox_dir else default_inbox_dir()
    return root / f"{safe_agent}.jsonl"


def cursor_path(agent_id: str, inbox_dir: str | None = None) -> Path:
    path = inbox_path(agent_id, inbox_dir)
    return path.with_name(path.stem + ".cursor.json")


def decode_payload(data: bytes) -> object:
    text = data.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def append_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load_cursor(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _write_cursor(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


SEEN_ID_LIMIT = 500


def read_new(agent_id: str, inbox_dir: str | None = None, *, advance: bool = True) -> list[dict[str, Any]]:
    """Return inbox records appended since the cursor; advance the cursor.

    Only complete lines (ending in newline) are consumed, so a record the
    subscriber is mid-write on is picked up next time. Delivery is
    at-least-once (ack follows the durable write), so records whose message id
    was already returned are skipped. If the inbox file shrank (rotated), the
    cursor restarts at 0.

    Raises InboxError(exit 3) when the inbox file does not exist: the
    subscriber has never run for this agent, so "no messages" cannot be told
    apart from "nothing is listening".
    """
    agent = normalize_agent_id(agent_id)
    path = inbox_path(agent, inbox_dir)
    cpath = cursor_path(agent, inbox_dir)
    if not path.exists():
        raise InboxError(
            f"no inbox file at {path}; the subscriber has never run for {agent!r} "
            f"(install it: make -C pmoves agent-inbox-install AGENT={agent})",
            EXIT_COULD_NOT_MEASURE,
        )
    cursor = _load_cursor(cpath)
    offset = int(cursor.get("offset", 0) or 0)
    seen: list[str] = list(cursor.get("seen_ids", []) or [])
    size = path.stat().st_size
    if offset > size:
        offset = 0
    with path.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read()
    end = chunk.rfind(b"\n")
    if end < 0:
        return []
    consumed = chunk[: end + 1]
    records: list[dict[str, Any]] = []
    seen_set = set(seen)
    for raw in consumed.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            record = {"kind": "unparseable", "raw": raw.decode("utf-8", errors="replace")}
        msg_id = record.get("msg_id") if isinstance(record, dict) else None
        if msg_id and msg_id in seen_set:
            continue
        if msg_id:
            seen.append(msg_id)
            seen_set.add(msg_id)
        records.append(record)
    if advance:
        _write_cursor(
            cpath,
            {
                "offset": offset + len(consumed),
                "seen_ids": seen[-SEEN_ID_LIMIT:],
                "updated": datetime.now(timezone.utc).isoformat(),
            },
        )
    return records


def format_record(record: dict[str, Any]) -> str:
    payload = record.get("payload")
    if record.get("kind") == "direct" and isinstance(payload, dict):
        head = (
            f"--- {payload.get('ts', record.get('ts'))} from={payload.get('from')} "
            f"to={payload.get('to')} id={payload.get('id')} reply_to={payload.get('reply_to')}"
        )
        body = payload.get("body")
        text = body if isinstance(body, str) else json.dumps(body, indent=2, sort_keys=True)
        return f"{head}\n{text}"
    return f"--- {record.get('ts')} [{record.get('kind', 'record')}] {record.get('subject')}\n" + json.dumps(
        payload, sort_keys=True
    )


# --------------------------------------------------------------------------
# JetStream management (create-only)
# --------------------------------------------------------------------------


@dataclass
class EnsureResult:
    name: str
    status: str  # "created" | "exists" | "drift"
    detail: str = ""


def _not_found_class() -> type[BaseException]:
    from nats.js.errors import NotFoundError  # type: ignore

    return NotFoundError


def stream_config_kwargs() -> dict[str, Any]:
    return {
        "name": STREAM_NAME,
        "subjects": [INBOX_STREAM_SUBJECT],
        "storage": "file",
        "retention": "limits",
        "discard": "old",
        "max_age": float(STREAM_MAX_AGE_SECONDS),
        "max_bytes": STREAM_MAX_BYTES,
        "max_msg_size": STREAM_MAX_MSG_SIZE,
        "duplicate_window": float(STREAM_DUPLICATE_WINDOW_SECONDS),
        "num_replicas": 1,
        "description": "PMOVES durable per-identity agent inbox (pmoves.agent.inbox.<agent_id>.v1)",
    }


def _stream_add_kwargs() -> dict[str, Any]:
    """Translate the plain config into nats-py enum values when nats is importable."""
    kwargs = stream_config_kwargs()
    try:
        from nats.js.api import DiscardPolicy, RetentionPolicy, StorageType  # type: ignore
    except ImportError:  # unit tests with fakes
        return kwargs
    kwargs["storage"] = StorageType.FILE
    kwargs["retention"] = RetentionPolicy.LIMITS
    kwargs["discard"] = DiscardPolicy.OLD
    return kwargs


def _cfg_get(info: Any, key: str) -> Any:
    config = getattr(info, "config", info)
    if isinstance(config, dict):
        return config.get(key)
    return getattr(config, key, None)


async def ensure_stream(js: Any, *, not_found: type[BaseException] | None = None) -> EnsureResult:
    """Create AGENT_INBOX if absent. Never updates, deletes or purges."""
    not_found = not_found or _not_found_class()
    try:
        info = await js.stream_info(STREAM_NAME)
    except not_found:
        await js.add_stream(**_stream_add_kwargs())
        return EnsureResult(STREAM_NAME, "created")
    subjects = list(_cfg_get(info, "subjects") or [])
    if INBOX_STREAM_SUBJECT not in subjects:
        return EnsureResult(
            STREAM_NAME,
            "drift",
            f"existing stream subjects {subjects} do not include {INBOX_STREAM_SUBJECT}; refusing to update it",
        )
    return EnsureResult(STREAM_NAME, "exists")


def consumer_config_kwargs(agent_id: str) -> dict[str, Any]:
    return {
        "durable_name": durable_name(agent_id),
        "filter_subject": inbox_subject(agent_id),
        "ack_policy": "explicit",
        "deliver_policy": "all",
        "ack_wait": 60.0,
        "max_ack_pending": 256,
        "description": f"PMOVES agent inbox for {normalize_agent_id(agent_id)}",
    }


def _consumer_add_kwargs(agent_id: str) -> dict[str, Any]:
    kwargs = consumer_config_kwargs(agent_id)
    try:
        from nats.js.api import AckPolicy, DeliverPolicy  # type: ignore
    except ImportError:
        return kwargs
    kwargs["ack_policy"] = AckPolicy.EXPLICIT
    kwargs["deliver_policy"] = DeliverPolicy.ALL
    return kwargs


async def ensure_consumer(
    js: Any, agent_id: str, *, not_found: type[BaseException] | None = None
) -> EnsureResult:
    """Create the agent's durable consumer if absent. Never updates or deletes."""
    not_found = not_found or _not_found_class()
    name = durable_name(agent_id)
    want_filter = inbox_subject(agent_id)
    try:
        info = await js.consumer_info(STREAM_NAME, name)
    except not_found:
        await js.add_consumer(STREAM_NAME, **_consumer_add_kwargs(agent_id))
        return EnsureResult(name, "created")
    have_filter = _cfg_get(info, "filter_subject")
    if have_filter != want_filter:
        return EnsureResult(
            name, "drift", f"existing consumer filter {have_filter!r} != {want_filter!r}; refusing to update it"
        )
    return EnsureResult(name, "exists")


# --------------------------------------------------------------------------
# NATS I/O
# --------------------------------------------------------------------------

CIPHER_FALLBACK_HINT = "fallback: store a Cipher memory tagged to:<agent_id> (see PATTERNS.md § Agent inbox)"


def _nats_url(explicit: str | None) -> str:
    url = explicit or os.environ.get("NATS_URL", "")
    if not url:
        raise InboxError(
            f"NATS_URL is not set (load it via pmoves/scripts/with-env.sh); {CIPHER_FALLBACK_HINT}",
            EXIT_COULD_NOT_MEASURE,
        )
    return resolve_host_nats_url(url)


async def _connect(url: str, name: str):
    try:
        import nats  # type: ignore
    except ImportError as exc:
        raise InboxError("nats-py is required (run via `uv run --script`)", EXIT_COULD_NOT_MEASURE) from exc
    try:
        return await asyncio.wait_for(
            nats.connect(
                url,
                name=name,
                connect_timeout=5,
                allow_reconnect=False,
                error_cb=_ignore_nats_error,
            ),
            timeout=8,
        )
    except Exception as exc:  # noqa: BLE001 - reported with shape, mapped to exit 3
        raise InboxError(
            f"cannot connect to NATS at {url_shape(url)}: {type(exc).__name__}; {CIPHER_FALLBACK_HINT}",
            EXIT_COULD_NOT_MEASURE,
        ) from exc


_UNAVAILABLE = ("NoRespondersError", "ServiceUnavailableError", "TimeoutError", "ConnectionClosedError")


async def _ensure_or_raise(js: Any, agent_id: str | None) -> list[EnsureResult]:
    try:
        results = [await ensure_stream(js)]
        if agent_id is not None and results[0].status != "drift":
            results.append(await ensure_consumer(js, agent_id))
    except InboxError:
        raise
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if name in _UNAVAILABLE:
            raise InboxError(f"JetStream unavailable: {name}", EXIT_COULD_NOT_MEASURE) from exc
        raise InboxError(f"JetStream refused stream/consumer create: {name}: {exc}", EXIT_REFUSED) from exc
    for result in results:
        print(json.dumps({"ensure": result.name, "status": result.status, "detail": result.detail}), file=sys.stderr)
        if result.status == "drift":
            raise InboxError(result.detail, EXIT_REFUSED)
    return results


async def run_ensure(*, nats_url: str, agent_id: str | None) -> int:
    nc = await _connect(nats_url, "pmoves-agent-inbox-ensure")
    try:
        await _ensure_or_raise(nc.jetstream(), agent_id)
        return EXIT_OK
    finally:
        await nc.drain()


async def run_send(*, nats_url: str, envelope: dict[str, Any]) -> int:
    data = encode_envelope(envelope)
    subject = inbox_subject(envelope["to"])
    nc = await _connect(nats_url, f"pmoves-agent-inbox-send-{envelope['from']}")
    try:
        js = nc.jetstream()
        await _ensure_or_raise(js, None)
        try:
            ack = await js.publish(
                subject, data, timeout=5, stream=STREAM_NAME, headers={"Nats-Msg-Id": envelope["id"]}
            )
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if name in _UNAVAILABLE:
                raise InboxError(f"no publish ack: {name}; {CIPHER_FALLBACK_HINT}", EXIT_COULD_NOT_MEASURE) from exc
            raise InboxError(f"publish refused: {name}: {exc}", EXIT_REFUSED) from exc
        print(
            json.dumps(
                {
                    "status": "acked",
                    "stream": ack.stream,
                    "seq": ack.seq,
                    "duplicate": bool(getattr(ack, "duplicate", False)),
                    "subject": subject,
                    "id": envelope["id"],
                    "from": envelope["from"],
                    "to": envelope["to"],
                }
            )
        )
        return EXIT_OK
    finally:
        await nc.drain()


def direct_record(agent_id: str, msg: Any) -> dict[str, Any]:
    meta = getattr(msg, "metadata", None)
    payload = decode_payload(msg.data)
    headers = getattr(msg, "headers", None) or {}
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "kind": "direct",
        "subject": msg.subject,
        "msg_id": headers.get("Nats-Msg-Id") or (payload.get("id") if isinstance(payload, dict) else None),
        "stream_seq": getattr(getattr(meta, "sequence", None), "stream", None),
        "delivered": getattr(meta, "num_delivered", None),
        "payload": payload,
    }


async def run_inbox(
    *,
    nats_url: str,
    agent_id: str,
    subjects: Iterable[str],
    output_path: Path,
    max_messages: int | None,
    broadcast: bool = False,
    fetch_timeout: float = 5.0,
) -> int:
    agent_id = normalize_agent_id(agent_id)
    stop_event = asyncio.Event()

    def _stop() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    received = 0

    def _count() -> None:
        nonlocal received
        received += 1
        if max_messages is not None and received >= max_messages:
            stop_event.set()

    async def broadcast_handler(msg) -> None:
        append_record(
            output_path,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "agent_id": agent_id,
                "kind": "broadcast",
                "subject": msg.subject,
                "reply": msg.reply or None,
                "payload": decode_payload(msg.data),
            },
        )
        print(json.dumps({"received": "broadcast", "subject": msg.subject}), flush=True)
        _count()

    nc = await _connect(nats_url, f"pmoves-agent-inbox-{agent_id}")
    try:
        js = nc.jetstream()
        await _ensure_or_raise(js, agent_id)
        # Touch the inbox file so `read` can tell "no messages" from "never ran".
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch(exist_ok=True)
        psub = await js.pull_subscribe_bind(durable_name(agent_id), STREAM_NAME)
        tapped: list[str] = []
        if broadcast:
            for subject in subjects:
                await nc.subscribe(subject, cb=broadcast_handler)
                tapped.append(subject)
        await nc.flush(timeout=2)
        print(
            json.dumps(
                {
                    "status": "listening",
                    "agent_id": agent_id,
                    "inbox_subject": inbox_subject(agent_id),
                    "stream": STREAM_NAME,
                    "durable": durable_name(agent_id),
                    "broadcast_subjects": tapped,
                    "path": str(output_path),
                }
            ),
            flush=True,
        )
        from nats.errors import TimeoutError as NatsTimeout  # type: ignore

        while not stop_event.is_set():
            try:
                msgs = await psub.fetch(batch=16, timeout=fetch_timeout)
            except (NatsTimeout, asyncio.TimeoutError):
                continue
            for msg in msgs:
                record = direct_record(agent_id, msg)
                append_record(output_path, record)  # durable write BEFORE ack: at-least-once
                await msg.ack()
                print(json.dumps({"received": "direct", "subject": msg.subject, "msg_id": record["msg_id"]}), flush=True)
                _count()
                if stop_event.is_set():
                    break
        return EXIT_OK
    except InboxError:
        raise
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if name in _UNAVAILABLE:
            raise InboxError(f"lost NATS/JetStream: {name}", EXIT_COULD_NOT_MEASURE) from exc
        raise
    finally:
        try:
            await nc.drain()
        except Exception:  # noqa: BLE001 - connection already gone; exit code already decided
            pass


# --------------------------------------------------------------------------
# systemd unit rendering
# --------------------------------------------------------------------------

UNIT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "fleet" / "pmoves-agent-inbox@.service"


def render_unit(template: str, *, code_dir: str, env_dir: str, uv_bin: str) -> str:
    for label, value in (("code_dir", code_dir), ("env_dir", env_dir), ("uv_bin", uv_bin)):
        if not value or not os.path.isabs(value) or any(c in value for c in "'\"\n%$`\\ "):
            raise InboxError(
                f"{label} must be an absolute path without spaces/quotes/%/$: {value!r}", EXIT_REFUSED
            )
    return (
        template.replace("@PMOVES_CODE_DIR@", code_dir)
        .replace("@PMOVES_ENV_DIR@", env_dir)
        .replace("@UV_BIN@", uv_bin)
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

COMMANDS = ("subscribe", "send", "read", "ensure", "render-unit")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Durable per-identity PMOVES agent inbox over NATS JetStream.")
    sub = parser.add_subparsers(dest="command")

    p_sub = sub.add_parser("subscribe", help="Run the inbox subscriber for one agent id.")
    p_sub.add_argument("--agent-id", default=os.environ.get("PMOVES_AGENT_ID"))
    p_sub.add_argument("--nats-url", default=None)
    p_sub.add_argument("--broadcast", action="store_true", help="Also tap the legacy core-NATS broadcast subjects.")
    p_sub.add_argument(
        "--subjects",
        default=os.environ.get("PMOVES_AGENT_INBOX_SUBJECTS"),
        help="Comma-separated broadcast subjects (with --broadcast). Defaults to task/branch/CHIT/P7/owner-presence.",
    )
    p_sub.add_argument("--inbox-dir", default=os.environ.get("PMOVES_AGENT_INBOX_DIR"))
    p_sub.add_argument("--max-messages", type=int, default=None, help="Exit after this many messages (smoke tests).")

    p_send = sub.add_parser("send", help="Publish one directed message and wait for the JetStream ack.")
    p_send.add_argument("--to", dest="to")
    p_send.add_argument("--from", dest="sender")
    body = p_send.add_mutually_exclusive_group()
    body.add_argument("--body-file")
    body.add_argument("--body")
    p_send.add_argument("--reply-to", default=None)
    p_send.add_argument("--id", dest="msg_id", default=None)
    p_send.add_argument("--nats-url", default=None)

    p_read = sub.add_parser("read", help="Print inbox records newer than the cursor, then advance it.")
    p_read.add_argument("--agent-id", default=os.environ.get("PMOVES_AGENT_ID"))
    p_read.add_argument("--inbox-dir", default=os.environ.get("PMOVES_AGENT_INBOX_DIR"))
    p_read.add_argument("--json", action="store_true", help="One JSON record per line.")
    p_read.add_argument("--peek", action="store_true", help="Do not advance the cursor.")

    p_ens = sub.add_parser("ensure", help="Create the AGENT_INBOX stream (+ an agent's consumer) if absent.")
    p_ens.add_argument("--agent-id", default=None)
    p_ens.add_argument("--nats-url", default=None)

    p_unit = sub.add_parser("render-unit", help="Print the systemd --user unit with paths filled in.")
    p_unit.add_argument("--code-dir", required=True)
    p_unit.add_argument("--env-dir", required=True)
    p_unit.add_argument("--uv-bin", required=True)
    return parser


def _read_body(args: argparse.Namespace) -> str:
    if args.body is not None:
        return args.body
    if not args.body_file:
        raise InboxError("a body is required (--body-file / BODY_FILE)", EXIT_COULD_NOT_MEASURE)
    path = Path(args.body_file)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise InboxError(f"cannot read body file {path}: {exc.strerror}", EXIT_COULD_NOT_MEASURE) from exc
    if len(data) > MAX_BODY_BYTES:
        raise InboxError(f"body file is {len(data)} bytes; limit is {MAX_BODY_BYTES}", EXIT_REFUSED)
    return data.decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Back-compat: the pre-JetStream tool had no subcommand and only subscribed.
    if not argv or (argv[0] not in COMMANDS and argv[0] not in ("-h", "--help")):
        argv = ["subscribe", *argv]
    args = build_parser().parse_args(argv)
    try:
        if args.command == "subscribe":
            agent = normalize_agent_id(args.agent_id)
            return asyncio.run(
                run_inbox(
                    nats_url=_nats_url(args.nats_url),
                    agent_id=agent,
                    subjects=parse_subjects(args.subjects),
                    output_path=inbox_path(agent, args.inbox_dir),
                    max_messages=args.max_messages,
                    broadcast=args.broadcast,
                )
            )
        if args.command == "send":
            sender = normalize_agent_id(args.sender)
            recipient = normalize_agent_id(args.to)
            envelope = build_envelope(
                sender=sender,
                recipient=recipient,
                body=_read_body(args),
                reply_to=args.reply_to,
                msg_id=args.msg_id,
            )
            return asyncio.run(run_send(nats_url=_nats_url(args.nats_url), envelope=envelope))
        if args.command == "read":
            agent = normalize_agent_id(args.agent_id)
            records = read_new(agent, args.inbox_dir, advance=not args.peek)
            for record in records:
                print(json.dumps(record, sort_keys=True) if args.json else format_record(record))
            print(f"agent-inbox: {len(records)} new record(s) for {agent}", file=sys.stderr)
            return EXIT_OK
        if args.command == "ensure":
            agent = normalize_agent_id(args.agent_id) if args.agent_id else None
            return asyncio.run(run_ensure(nats_url=_nats_url(args.nats_url), agent_id=agent))
        if args.command == "render-unit":
            template = UNIT_TEMPLATE_PATH.read_text(encoding="utf-8")
            sys.stdout.write(render_unit(template, code_dir=args.code_dir, env_dir=args.env_dir, uv_bin=args.uv_bin))
            return EXIT_OK
    except InboxError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.code
    except Exception as exc:  # noqa: BLE001 - unexpected: could not measure, and say what
        print(f"ERROR: agent inbox failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_COULD_NOT_MEASURE
    return EXIT_COULD_NOT_MEASURE


if __name__ == "__main__":
    raise SystemExit(main())
