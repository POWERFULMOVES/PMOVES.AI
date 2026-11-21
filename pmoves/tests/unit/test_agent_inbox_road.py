"""Agent inbox Known Road: identity gate, envelope, cursor, create-only JetStream.

No live NATS: JetStream is a fake that records every call, so the tests can
assert that an existing stream/consumer is never updated, deleted or purged.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from pmoves.tools import nats_agent_inbox as inbox


class FakeNotFound(Exception):
    pass


class FakeJetStream:
    def __init__(self, streams=None, consumers=None):
        self.streams = dict(streams or {})
        self.consumers = dict(consumers or {})
        self.calls: list[str] = []

    async def stream_info(self, name):
        self.calls.append(f"stream_info:{name}")
        if name not in self.streams:
            raise FakeNotFound(name)
        return SimpleNamespace(config=SimpleNamespace(**self.streams[name]))

    async def add_stream(self, **kwargs):
        self.calls.append(f"add_stream:{kwargs['name']}")
        self.streams[kwargs["name"]] = kwargs

    async def consumer_info(self, stream, durable):
        self.calls.append(f"consumer_info:{stream}:{durable}")
        if (stream, durable) not in self.consumers:
            raise FakeNotFound(durable)
        return SimpleNamespace(config=SimpleNamespace(**self.consumers[(stream, durable)]))

    async def add_consumer(self, stream, **kwargs):
        self.calls.append(f"add_consumer:{stream}:{kwargs['durable_name']}")
        self.consumers[(stream, kwargs["durable_name"])] = kwargs

    # Any of these being called would be a create-only violation.
    def __getattr__(self, name):
        if name in ("update_stream", "delete_stream", "purge_stream", "delete_consumer", "update_consumer"):
            raise AssertionError(f"create-only violated: {name} called")
        raise AttributeError(name)


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- identity gate


@pytest.mark.parametrize("argv", [["subscribe"], ["subscribe", "--agent-id", ""], ["read"], []])
def test_missing_agent_id_exits_3(argv, monkeypatch, capsys):
    monkeypatch.delenv("PMOVES_AGENT_ID", raising=False)
    # Ensure no NATS is needed to fail closed: NATS_URL unset too.
    monkeypatch.delenv("NATS_URL", raising=False)
    assert inbox.main(argv) == 3
    assert "agent id is required" in capsys.readouterr().err


def test_no_hardcoded_default_identity(monkeypatch):
    monkeypatch.delenv("PMOVES_AGENT_ID", raising=False)
    args = inbox.build_parser().parse_args(["subscribe"])
    assert args.agent_id is None
    assert "5090-CODEX" not in Path(inbox.__file__).read_text(encoding="utf-8")


def test_send_missing_to_or_from_exits_3(monkeypatch):
    monkeypatch.delenv("NATS_URL", raising=False)
    assert inbox.main(["send", "--from", "b850-claude", "--body", "x"]) == 3
    assert inbox.main(["send", "--to", "crush", "--body", "x"]) == 3


@pytest.mark.parametrize("bad", ["a.b", "crush.>", "*", "has space", "x" * 65])
def test_non_token_agent_id_is_refused_exit_1(bad):
    with pytest.raises(inbox.InboxError) as err:
        inbox.normalize_agent_id(bad)
    assert err.value.code == 1


def test_agent_id_is_lowercased_so_one_inbox_cannot_split():
    assert inbox.normalize_agent_id(" B850-CLAUDE ") == "b850-claude"
    assert inbox.inbox_subject("B850-CLAUDE") == "pmoves.agent.inbox.b850-claude.v1"
    assert inbox.durable_name("crush") == "inbox-crush"


def test_send_without_nats_url_is_could_not_measure_and_names_fallback(monkeypatch, capsys):
    monkeypatch.delenv("NATS_URL", raising=False)
    assert inbox.main(["send", "--to", "crush", "--from", "b850-claude", "--body", "hi"]) == 3
    assert "to:<agent_id>" in capsys.readouterr().err


# ---------------------------------------------------------------- envelope


def test_envelope_shape():
    now = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    env = inbox.build_envelope(sender="b850-claude", recipient="crush", body="ping", now=now, msg_id="m-1")
    assert set(env) == {"from", "to", "ts", "id", "reply_to", "body"}
    assert env == {
        "from": "b850-claude",
        "to": "crush",
        "ts": "2026-11-21T12:00:00+00:00",
        "id": "m-1",
        "reply_to": "pmoves.agent.inbox.b850-claude.v1",
        "body": "ping",
    }
    decoded = json.loads(inbox.encode_envelope(env))
    assert decoded == env


def test_envelope_generates_unique_ids_and_honours_reply_to():
    a = inbox.build_envelope(sender="crush", recipient="b850-claude", body="x")
    b = inbox.build_envelope(sender="crush", recipient="b850-claude", body="x", reply_to="custom.subject.v1")
    assert a["id"] != b["id"]
    assert b["reply_to"] == "custom.subject.v1"


def test_oversize_envelope_is_refused():
    env = inbox.build_envelope(sender="crush", recipient="b850-claude", body="x" * (inbox.MAX_BODY_BYTES + 1))
    with pytest.raises(inbox.InboxError) as err:
        inbox.encode_envelope(env)
    assert err.value.code == 1


def test_inbox_subject_matches_stream_wildcard():
    subj = inbox.inbox_subject("crush").split(".")
    pattern = inbox.INBOX_STREAM_SUBJECT.split(".")
    assert len(subj) == len(pattern)
    assert all(p == "*" or p == s for p, s in zip(pattern, subj))


def test_url_shape_never_leaks_credentials():
    shape = inbox.url_shape("nats://zorgname:s3cr3t@127.0.0.1:4222")
    assert "s3cr3t" not in shape and "zorgname" not in shape
    assert shape == "nats://<with-userinfo>127.0.0.1:4222"


# ---------------------------------------------------------------- cursor


def _direct(msg_id: str, body: str) -> dict:
    return {
        "kind": "direct",
        "msg_id": msg_id,
        "subject": "pmoves.agent.inbox.crush.v1",
        "payload": {"from": "b850-claude", "to": "crush", "id": msg_id, "body": body},
    }


def test_read_without_inbox_file_is_could_not_measure(tmp_path):
    with pytest.raises(inbox.InboxError) as err:
        inbox.read_new("crush", str(tmp_path))
    assert err.value.code == 3


def test_cursor_advances_and_second_read_is_empty(tmp_path):
    path = inbox.inbox_path("crush", str(tmp_path))
    inbox.append_record(path, _direct("m1", "one"))
    inbox.append_record(path, _direct("m2", "two"))

    first = inbox.read_new("crush", str(tmp_path))
    assert [r["msg_id"] for r in first] == ["m1", "m2"]
    assert inbox.read_new("crush", str(tmp_path)) == []

    inbox.append_record(path, _direct("m3", "three"))
    assert [r["msg_id"] for r in inbox.read_new("crush", str(tmp_path))] == ["m3"]


def test_peek_does_not_advance(tmp_path):
    path = inbox.inbox_path("crush", str(tmp_path))
    inbox.append_record(path, _direct("m1", "one"))
    assert len(inbox.read_new("crush", str(tmp_path), advance=False)) == 1
    assert len(inbox.read_new("crush", str(tmp_path))) == 1


def test_partial_trailing_line_is_left_for_next_read(tmp_path):
    path = inbox.inbox_path("crush", str(tmp_path))
    inbox.append_record(path, _direct("m1", "one"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"kind":"direct","msg_id":"m2"')  # subscriber mid-write
    assert [r["msg_id"] for r in inbox.read_new("crush", str(tmp_path))] == ["m1"]
    with path.open("a", encoding="utf-8") as fh:
        fh.write(',"payload":{}}\n')
    assert [r["msg_id"] for r in inbox.read_new("crush", str(tmp_path))] == ["m2"]


def test_redelivered_message_id_is_shown_once(tmp_path):
    path = inbox.inbox_path("crush", str(tmp_path))
    inbox.append_record(path, _direct("m1", "one"))
    assert len(inbox.read_new("crush", str(tmp_path))) == 1
    inbox.append_record(path, _direct("m1", "one"))  # at-least-once redelivery
    assert inbox.read_new("crush", str(tmp_path)) == []


def test_truncated_inbox_resets_cursor(tmp_path):
    path = inbox.inbox_path("crush", str(tmp_path))
    inbox.append_record(path, _direct("m1", "one"))
    inbox.append_record(path, _direct("m2", "two"))
    inbox.read_new("crush", str(tmp_path))
    path.write_text("")  # rotated
    inbox.append_record(path, _direct("m9", "nine"))
    assert [r["msg_id"] for r in inbox.read_new("crush", str(tmp_path))] == ["m9"]


def test_read_cli_prints_once(tmp_path, capsys):
    path = inbox.inbox_path("crush", str(tmp_path))
    inbox.append_record(path, _direct("m1", "hello crush"))
    assert inbox.main(["read", "--agent-id", "crush", "--inbox-dir", str(tmp_path)]) == 0
    out = capsys.readouterr()
    assert "hello crush" in out.out and "1 new record(s)" in out.err
    assert inbox.main(["read", "--agent-id", "crush", "--inbox-dir", str(tmp_path)]) == 0
    out = capsys.readouterr()
    assert out.out == "" and "0 new record(s)" in out.err


# ---------------------------------------------------------------- create-only JetStream


def test_stream_created_when_absent_then_idempotent():
    js = FakeJetStream()
    first = run(inbox.ensure_stream(js, not_found=FakeNotFound))
    second = run(inbox.ensure_stream(js, not_found=FakeNotFound))
    assert (first.status, second.status) == ("created", "exists")
    assert js.calls.count("add_stream:AGENT_INBOX") == 1
    cfg = js.streams["AGENT_INBOX"]
    assert cfg["subjects"] == ["pmoves.agent.inbox.*.v1"]
    assert cfg["max_age"] == 14 * 24 * 3600
    assert cfg["max_bytes"] > 0
    assert str(cfg["storage"]).lower().endswith("file")
    assert str(cfg["retention"]).lower().endswith("limits")  # interest/workqueue would drop offline mail


def test_existing_stream_with_wrong_subjects_is_drift_not_update():
    js = FakeJetStream(streams={"AGENT_INBOX": {"subjects": ["something.else"]}})
    result = run(inbox.ensure_stream(js, not_found=FakeNotFound))
    assert result.status == "drift"
    assert js.calls == ["stream_info:AGENT_INBOX"]


def test_consumer_created_when_absent_then_idempotent():
    js = FakeJetStream()
    first = run(inbox.ensure_consumer(js, "crush", not_found=FakeNotFound))
    second = run(inbox.ensure_consumer(js, "crush", not_found=FakeNotFound))
    assert (first.status, second.status) == ("created", "exists")
    assert js.calls.count("add_consumer:AGENT_INBOX:inbox-crush") == 1
    cfg = js.consumers[("AGENT_INBOX", "inbox-crush")]
    assert cfg["filter_subject"] == "pmoves.agent.inbox.crush.v1"
    assert str(cfg["ack_policy"]).lower().endswith("explicit")
    assert str(cfg["deliver_policy"]).lower().endswith("all")


def test_existing_consumer_with_other_filter_is_drift_not_update():
    js = FakeJetStream(consumers={("AGENT_INBOX", "inbox-crush"): {"filter_subject": "pmoves.agent.inbox.x.v1"}})
    result = run(inbox.ensure_consumer(js, "crush", not_found=FakeNotFound))
    assert result.status == "drift"
    assert not any(c.startswith("add_consumer") for c in js.calls)


def test_ensure_or_raise_maps_drift_to_refused(monkeypatch):
    js = FakeJetStream(streams={"AGENT_INBOX": {"subjects": ["nope"]}})
    monkeypatch.setattr(inbox, "_not_found_class", lambda: FakeNotFound)
    with pytest.raises(inbox.InboxError) as err:
        run(inbox._ensure_or_raise(js, "crush"))
    assert err.value.code == 1


def test_ensure_or_raise_maps_unavailable_to_could_not_measure(monkeypatch):
    class NoRespondersError(Exception):
        pass

    class DeadJS(FakeJetStream):
        async def stream_info(self, name):
            raise NoRespondersError()

    monkeypatch.setattr(inbox, "_not_found_class", lambda: FakeNotFound)
    with pytest.raises(inbox.InboxError) as err:
        run(inbox._ensure_or_raise(DeadJS(), "crush"))
    assert err.value.code == 3


def test_no_destructive_jetstream_calls_in_source():
    src = Path(inbox.__file__).read_text(encoding="utf-8")
    for forbidden in ("delete_stream", "purge_stream", "update_stream", "delete_consumer", "update_consumer"):
        assert forbidden not in src


# ---------------------------------------------------------------- subscriber record + unit


def test_direct_record_carries_msg_id_and_payload():
    msg = SimpleNamespace(
        subject="pmoves.agent.inbox.crush.v1",
        data=json.dumps({"id": "m1", "from": "b850-claude", "to": "crush", "body": "hi"}).encode(),
        headers={"Nats-Msg-Id": "m1"},
        metadata=SimpleNamespace(sequence=SimpleNamespace(stream=7), num_delivered=1),
    )
    rec = inbox.direct_record("crush", msg)
    assert rec["kind"] == "direct" and rec["msg_id"] == "m1" and rec["stream_seq"] == 7
    assert rec["payload"]["body"] == "hi"


def test_unit_template_renders_with_instance_as_agent_id():
    template = inbox.UNIT_TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = inbox.render_unit(template, code_dir="/opt/p/pmoves", env_dir="/opt/main/pmoves", uv_bin="/usr/bin/uv")
    assert "@" not in rendered.split("[Unit]", 1)[1].replace("%i", "").replace("pmoves-agent-inbox@", "")
    assert '--agent-id "%i"' in rendered
    assert "/opt/main/pmoves/scripts/with-env.sh" in rendered
    assert "Restart=always" in rendered


@pytest.mark.parametrize("bad", ["relative/path", "/has space", "/x';rm -rf /;'", "/x$HOME"])
def test_unit_render_refuses_unsafe_paths(bad):
    with pytest.raises(inbox.InboxError):
        inbox.render_unit("x", code_dir=bad, env_dir="/a", uv_bin="/b")
