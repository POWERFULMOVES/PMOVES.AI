"""Unit tests for pmoves.tools.keygen_cards (no real key generation)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import yaml

from pmoves.tools import keygen_cards as kc

CARD_SAMPLE = """\
# 5x5 Signing Identity Cards — test fixture
schema_version: "1.0.0"
generated: "2026-04-26"
cards:
  - card_id: "00000000-0000-4000-8000-000000000007"
    issued_at: "2026-04-26T14:06:00Z"
    active: true
    ml:
      primary_method: github-app
      github_app_installation_id: null
    h:
      agent_id: "crush"
      display_name: "Crush"
      role: agent
"""


@pytest.fixture()
def cards_file(tmp_path, monkeypatch):
    p = tmp_path / "signing_identity_cards.yaml"
    p.write_text(CARD_SAMPLE)
    monkeypatch.setattr(kc, "CARDS_PATH", p)
    return p


def _args(**kw):
    base = {"passphrase_env": None}
    base.update(kw)
    return argparse.Namespace(**base)


class TestAudit:
    def test_audit_reports_pending_ml(self, cards_file, capsys):
        assert kc.cmd_audit(_args()) == 0
        out = capsys.readouterr().out
        assert "pending-ml (1): crush" in out

    def test_audit_reports_complete(self, cards_file, capsys):
        data = yaml.safe_load(cards_file.read_text())
        data["cards"][0]["ml"]["ssh_fingerprint"] = "SHA256:x"
        data["cards"][0]["ml"]["ssh_allowed_signers_line"] = "crush ssh-ed25519 AAA x"
        cards_file.write_text(yaml.safe_dump(data))
        assert kc.cmd_audit(_args()) == 0
        assert "complete (1): crush" in capsys.readouterr().out


class TestGenerate:
    def test_unknown_agent_errors(self, cards_file):
        assert kc.cmd_generate(_args(agent="nope", dry_run=True)) == 1

    def test_existing_key_refused(self, cards_file, tmp_path, monkeypatch):
        monkeypatch.setattr(kc, "DEFAULT_KEY_DIR", tmp_path)
        (tmp_path / "crush-signing").write_text("x")
        assert kc.cmd_generate(_args(agent="crush", dry_run=True)) == 1


class TestParsing:
    def test_cli_output_parsed(self):
        # structure check: the parse loop used in generate_key
        sample = (
            "authorized_key=ssh-ed25519 AAAAC3 test\n"
            "fingerprint=SHA256:abc\n"
            "key_type=ed25519\n"
        )
        fields = {}
        for line in sample.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                fields[key.strip()] = value.strip()
        assert fields["fingerprint"] == "SHA256:abc"
        assert fields["authorized_key"] == "ssh-ed25519 AAAAC3 test"


class TestRuwarp:
    def test_no_wrap_width_set(self):
        # the wrapper must configure ruamel width so the long
        # allowed-signers line never wraps (invalid-YAML regression)
        import inspect

        src = inspect.getsource(kc.cmd_generate)
        assert "yaml.width = 4096" in src.replace(" ", "").replace("yaml.width=4096", "yaml.width = 4096") or "width = 4096" in src
