"""The allowlist that decides which env.shared keys reach a launched session.

Pins pmoves/tools/launcher_env_allowlist.py. The launcher half (claude-pmoves
.sh/.ps1 calling it instead of bulk-exporting) is protected and lands under a
`launcher` Known Road; these tests are the contract it will be held to.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "pmoves" / "tools" / "launcher_env_allowlist.py"

_spec = importlib.util.spec_from_file_location("launcher_env_allowlist", TOOL)
lea = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lea)


def _root(tmp_path: Path, roster: dict, gateway: dict | None = None) -> Path:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "mcp.json").write_text(json.dumps(roster), encoding="utf-8")
    if gateway is not None:
        (tmp_path / ".mcp.json").write_text(json.dumps(gateway), encoding="utf-8")
    return tmp_path


def test_roster_refs_include_nested_defaults():
    data = {"mcpServers": {"s": {"args": ["--key", "${PRIMARY_KEY:-${LEGACY_KEY}}"]}}}
    assert lea.roster_refs(data) == {"PRIMARY_KEY", "LEGACY_KEY"}


def test_disabled_server_cannot_pull_its_secret_in():
    # `_`-prefixed servers are skipped by the normalizer (P2); a disabled entry
    # that still names a token must not put that token in the session.
    data = {
        "mcpServers": {
            "live": {"env": {"A": "${LIVE_TOKEN}"}},
            "_retired": {"env": {"B": "${RETIRED_TOKEN}"}},
        }
    }
    assert lea.roster_refs(data) == {"LIVE_TOKEN"}


def test_note_fields_are_not_references():
    data = {"mcpServers": {"s": {"_note": "was ${OLD_SECRET}", "url": "${URL_VAR}"}}}
    assert lea.roster_refs(data) == {"URL_VAR"}


def test_unrelated_secret_stays_behind(tmp_path):
    root = _root(tmp_path, {"mcpServers": {"s": {"env": {"T": "${ROSTER_TOKEN}"}}}})
    names = lea.allowlist(root)
    assert "ROSTER_TOKEN" in names
    # The class of key the demo-JWT incident rode in on: a compose-side secret
    # no roster server reads.
    assert "SUPABASE_JWT_SECRET" not in names
    assert "POSTGRES_PASSWORD" not in names


def test_gateway_entry_contributes(tmp_path):
    root = _root(
        tmp_path,
        {"mcpServers": {}},
        gateway={"mcpServers": {"gw": {"headers": {"Authorization": "Bearer ${GW_TOKEN}"}}}},
    )
    assert "GW_TOKEN" in lea.allowlist(root)


def test_implicit_reads_always_present(tmp_path):
    root = _root(tmp_path, {"mcpServers": {}})
    names = set(lea.allowlist(root))
    assert set(lea.IMPLICIT_READS) <= names


def test_implicit_reads_each_name_a_reader():
    for name, reader in lea.IMPLICIT_READS.items():
        assert reader.strip(), name


def test_blocklist_wins_over_a_roster_reference(tmp_path):
    root = _root(
        tmp_path,
        {"mcpServers": {"s": {"env": {
            "A": "${ANTHROPIC_API_KEY}",
            "B": "${CLAUDE_CODE_USE_BEDROCK}",
            "C": "${OK_VAR}",
        }}}},
    )
    names = lea.allowlist(root)
    assert "ANTHROPIC_API_KEY" not in names
    assert "CLAUDE_CODE_USE_BEDROCK" not in names
    assert "OK_VAR" in names


def test_malformed_roster_degrades_to_implicit_only(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "mcp.json").write_text("{not json", encoding="utf-8")
    assert lea.allowlist(tmp_path) == sorted(lea.IMPLICIT_READS)


def test_real_roster_covers_every_server_env_var():
    # Against the tracked roster: every var an active server names is on the
    # list, so the allowlist cannot start a roster server without its creds.
    roster = json.loads((REPO_ROOT / ".claude" / "mcp.json").read_text(encoding="utf-8"))
    names = set(lea.allowlist(REPO_ROOT))
    assert lea.roster_refs(roster) - names == set()


def test_cli_prints_names_only(tmp_path):
    root = _root(tmp_path, {"mcpServers": {"s": {"env": {"T": "${ROSTER_TOKEN}"}}}})
    r = subprocess.run(
        [sys.executable, str(TOOL), "--root", str(root)],
        capture_output=True, text=True, check=True,
    )
    lines = r.stdout.split()
    assert lines == sorted(lines)
    assert "ROSTER_TOKEN" in lines
    assert all("=" not in ln for ln in lines)
