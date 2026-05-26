import json

from pmoves.tools import nats_agent_inbox


def test_parse_subjects_defaults_when_empty():
    assert nats_agent_inbox.parse_subjects(None) == list(nats_agent_inbox.DEFAULT_SUBJECTS)
    assert nats_agent_inbox.parse_subjects(" , ") == list(nats_agent_inbox.DEFAULT_SUBJECTS)


def test_parse_subjects_splits_and_strips():
    assert nats_agent_inbox.parse_subjects("claw.task.assign.v1, branch.>") == [
        "claw.task.assign.v1",
        "branch.>",
    ]


def test_append_record_writes_jsonl(tmp_path):
    path = tmp_path / "inbox" / "5090-CODEX.jsonl"
    record = {"subject": "claw.task.assign.v1", "payload": {"task": "smoke"}}

    nats_agent_inbox.append_record(path, record)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == record


def test_inbox_path_sanitizes_agent_id(tmp_path):
    path = nats_agent_inbox.inbox_path("5090/CODEX test", str(tmp_path))
    assert path.name == "5090_CODEX_test.jsonl"


def test_resolve_host_nats_url_rewrites_docker_dns(monkeypatch):
    monkeypatch.delenv("PMOVES_NATS_NO_HOST_REWRITE", raising=False)
    assert (
        nats_agent_inbox.resolve_host_nats_url("nats://nats:pmoves@nats:4222")
        == "nats://nats:pmoves@127.0.0.1:4222"
    )
