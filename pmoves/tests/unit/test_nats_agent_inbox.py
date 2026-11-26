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
        nats_agent_inbox.resolve_host_nats_url("nats://nats:s3cr3t@nats:4222")
        == "nats://nats:s3cr3t@127.0.0.1:4222"
    )


# --- agent identity resolution -------------------------------------------
# On node 5090 (2026-11-23) the inbox connected as pmoves-agent-inbox-5090-CODEX
# and wrote 5090-CODEX.jsonl because "5090-CODEX" was the hardcoded default.
# Order now: PMOVES_AGENT_ID, PMOVES_REGISTER_IDENTITY, the canonical node
# resolver (agent_terminal_theme._resolve_whoami, what node-sitrep prints),
# then "<hostname>-agent". Never a fixed agent string.

import socket

import pytest

_IDENTITY_ENV = ("PMOVES_AGENT_ID", "PMOVES_REGISTER_IDENTITY")


@pytest.fixture
def clean_identity_env(monkeypatch):
    for name in _IDENTITY_ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_agent_id_env_wins_over_everything(clean_identity_env):
    clean_identity_env.setenv("PMOVES_AGENT_ID", "spark-claude")
    clean_identity_env.setenv("PMOVES_REGISTER_IDENTITY", "B850-CLAUDE-FUNNEL")
    clean_identity_env.setattr(nats_agent_inbox, "_canonical_identity", lambda: "5090-claude")
    assert nats_agent_inbox.resolve_agent_id() == ("spark-claude", "PMOVES_AGENT_ID")


def test_register_identity_is_second(clean_identity_env):
    clean_identity_env.setenv("PMOVES_REGISTER_IDENTITY", "B850-CLAUDE-FUNNEL")
    clean_identity_env.setattr(nats_agent_inbox, "_canonical_identity", lambda: "5090-claude")
    assert nats_agent_inbox.resolve_agent_id() == ("B850-CLAUDE-FUNNEL", "PMOVES_REGISTER_IDENTITY")


def test_canonical_resolver_is_third(clean_identity_env):
    clean_identity_env.setattr(nats_agent_inbox, "_canonical_identity", lambda: "5090-claude")
    assert nats_agent_inbox.resolve_agent_id() == ("5090-claude", "whoami")


def test_hostname_fallback_is_last_and_never_codex(clean_identity_env):
    clean_identity_env.setattr(nats_agent_inbox, "_canonical_identity", lambda: None)
    clean_identity_env.setattr(socket, "gethostname", lambda: "test-box")
    assert nats_agent_inbox.resolve_agent_id() == ("test-box-agent", "hostname")


def test_blank_env_values_fall_through(clean_identity_env):
    clean_identity_env.setenv("PMOVES_AGENT_ID", "  ")
    clean_identity_env.setenv("PMOVES_REGISTER_IDENTITY", "")
    clean_identity_env.setattr(nats_agent_inbox, "_canonical_identity", lambda: "5090-claude")
    assert nats_agent_inbox.resolve_agent_id() == ("5090-claude", "whoami")


def test_canonical_identity_treats_unknown_as_unresolved(clean_identity_env):
    clean_identity_env.setattr(nats_agent_inbox, "_load_whoami", lambda: (lambda: "unknown"))
    assert nats_agent_inbox._canonical_identity() is None


def test_canonical_identity_survives_a_broken_resolver(clean_identity_env):
    def boom():
        raise RuntimeError("resolver exploded")

    clean_identity_env.setattr(nats_agent_inbox, "_load_whoami", lambda: boom)
    assert nats_agent_inbox._canonical_identity() is None


def test_canonical_identity_reuses_the_sitrep_resolver(clean_identity_env):
    """The real agent_terminal_theme resolver, via its hostname map (no gateway call)."""
    clean_identity_env.setattr(socket, "gethostname", lambda: "PMOVES-4090")
    assert nats_agent_inbox._load_whoami() is not None
    assert nats_agent_inbox._canonical_identity() == "4090-claude"


def test_parser_default_is_lazy_and_not_codex():
    args = nats_agent_inbox.build_parser().parse_args([])
    assert args.agent_id is None
    assert "CODEX" not in (nats_agent_inbox.build_parser().format_help())
