"""Tests for ``pmoves/scripts/audit_naming_drift.py``.

Smoke tests against the live repo (the audit is read-only; running it
is safe in tests). Plus targeted unit tests for the canonical-aliases
parser and the NATS subject regex.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "pmoves" / "scripts" / "audit_naming_drift.py"
DRIFT_REPORT = REPO_ROOT / "pmoves" / "docs" / "logs" / "naming_drift_latest.json"
NODE_DIFF_REPORT = REPO_ROOT / "pmoves" / "docs" / "logs" / "node_descriptions_diff_latest.md"


def _run_audit(*args: str) -> subprocess.CompletedProcess[str]:
    """
    Run the audit script with the given CLI arguments and capture its output.
    
    Parameters:
        *args (str): Command-line arguments forwarded to the audit script.
    
    Returns:
        subprocess.CompletedProcess[str]: Completed process containing `stdout`, `stderr`, and `returncode`.
    """
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


@pytest.mark.skipif(not SCRIPT.exists(), reason="audit script not present")
def test_audit_writes_drift_report() -> None:
    result = _run_audit()
    assert result.returncode == 0, f"non-strict run should succeed; stderr: {result.stderr}"
    assert DRIFT_REPORT.exists()
    data = json.loads(DRIFT_REPORT.read_text(encoding="utf-8"))
    assert "by_severity" in data
    assert "findings" in data
    assert "surfaces_scanned" in data
    assert "cards_summary" in data


@pytest.mark.skipif(not SCRIPT.exists(), reason="audit script not present")
def test_audit_writes_node_diff() -> None:
    _run_audit()
    assert NODE_DIFF_REPORT.exists()
    text = NODE_DIFF_REPORT.read_text(encoding="utf-8")
    assert text.startswith("# Node-Description Diff")
    assert "| Node |" in text


@pytest.mark.skipif(not SCRIPT.exists(), reason="audit script not present")
def test_audit_strict_fails_on_p0() -> None:
    """
    Ensure the audit script fails when run in strict mode targeting P0 severity.
    
    Asserts the subprocess exit code is 1, indicating strict mode fails when P0 findings are present.
    """
    result = _run_audit("--strict", "--severity", "P0")
    assert result.returncode == 1, "strict mode must fail when P0 findings exist"


@pytest.mark.skipif(not SCRIPT.exists(), reason="audit script not present")
def test_audit_json_mode_emits_summary() -> None:
    result = _run_audit("--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "by_severity" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)


@pytest.mark.skipif(not SCRIPT.exists(), reason="audit script not present")
def test_cards_summary_active_count_matches_seed() -> None:
    """signing_identity_cards.yaml seeded 16 active cards (Phase 2)."""
    _run_audit()
    data = json.loads(DRIFT_REPORT.read_text(encoding="utf-8"))
    assert data["cards_summary"]["active"] == 16
    by_role = data["cards_summary"]["by_role"]
    assert by_role.get("operator") == 1
    assert by_role.get("agent") == 9  # 7 base + z890/5090/4090 personas (z890 + 5090 + 4090 + 7 base agents - operator counted separately = 9 here actually = 6 base agents (claude/codex/kilocode/gemini/cline/crush) + 3 nodes = 9)
    assert by_role.get("service-account") == 1
    assert by_role.get("runner") == 5


@pytest.mark.skipif(not SCRIPT.exists(), reason="audit script not present")
def test_pem_misuse_count_matches_sitrep() -> None:
    """SITREP §2 enumerates 5 workflows w/ 7 GH_APP_SEC misuse sites."""
    _run_audit()
    data = json.loads(DRIFT_REPORT.read_text(encoding="utf-8"))
    pem_findings = [f for f in data["findings"] if f["check"] == "workflow.pem_misuse"]
    assert len(pem_findings) == 7


# Unit tests for helpers — import directly


def test_canonical_aliases_parser_reads_uppercase_canonicals() -> None:
    sys.path.insert(0, str(REPO_ROOT / "pmoves" / "scripts"))
    try:
        import audit_naming_drift as aud
    finally:
        sys.path.pop(0)
    aliases = aud.parse_canonical_aliases(aud.CANONICAL_NAMES_DOC)
    # At minimum the four uppercase canonicals from CANONICAL_NAMES.md sections 1,2,3,7
    assert "JWT_SECRET" in aliases
    assert "SERVICE_ROLE_KEY" in aliases
    assert "GH_APP_PRIVATE_KEY" in aliases
    assert "NATS_URL" in aliases


def test_nats_subject_regex_accepts_canonical_subjects() -> None:
    sys.path.insert(0, str(REPO_ROOT / "pmoves" / "scripts"))
    try:
        import audit_naming_drift as aud
    finally:
        sys.path.pop(0)
    valid = [
        "agent.graphiti.signed.v1",
        "geometry.cgp.v1",
        "tokenism.simulation.result.v1",
        "archon.work_order.github.v1",
        "ops.pr.monitor.completed.v1",
    ]
    for subj in valid:
        assert aud.NATS_SUBJECT_RE.match(subj), f"should accept canonical subject {subj!r}"


def test_nats_subject_regex_rejects_malformed() -> None:
    sys.path.insert(0, str(REPO_ROOT / "pmoves" / "scripts"))
    try:
        import audit_naming_drift as aud
    finally:
        sys.path.pop(0)
    bad = [
        "Agent.Graphiti.Signed.v1",  # uppercase
        "agent.graphiti.signed",     # no version
        "agent..signed.v1",          # empty segment
        "agent.signed.vV1",          # bad version
    ]
    for subj in bad:
        assert not aud.NATS_SUBJECT_RE.match(subj), f"should reject malformed {subj!r}"


def test_compose_var_regex_extracts_empty_defaults() -> None:
    sys.path.insert(0, str(REPO_ROOT / "pmoves" / "scripts"))
    try:
        import audit_naming_drift as aud
    finally:
        sys.path.pop(0)
    line = '    - A0_SET_mcp_server_token=${MCP_SERVER_TOKEN:-}'
    matches = list(aud.COMPOSE_VAR_RE.finditer(line))
    assert len(matches) == 1
    m = matches[0]
    assert m.group(1) == "MCP_SERVER_TOKEN"
    assert m.group(2) == ":-"
    assert m.group(3) == ""
