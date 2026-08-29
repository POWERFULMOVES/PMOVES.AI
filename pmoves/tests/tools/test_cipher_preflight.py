"""Offline tests for the Cipher startup check.

The network is stubbed, so these run with no Cipher and on any node. What is
under test is the verdict logic — above all that "no measurement" exits 3 rather
than 0, because a session that believes it has memory and does not is the exact
failure this check exists to prevent.

Context: `.claude/mcp.json` carries two cipher entries — the fleet one via
`${TS_Z890}` and a local one. #2792 added the local entry after the roster had
carried only the fleet endpoint: "memory that silently wasn't there". So the
check has to report WHICH endpoint answered, not merely that one did.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "cipher_preflight.py"
LAUNCHER = REPO_ROOT / "pmoves" / "scripts" / "claude-pmoves.sh"

spec = importlib.util.spec_from_file_location("cipher_preflight", MODULE)
assert spec and spec.loader
cp = importlib.util.module_from_spec(spec)
sys.modules["cipher_preflight"] = cp
spec.loader.exec_module(cp)


def _roster(tmp_path: Path, servers: dict) -> Path:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
    return path


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_reachable_endpoint_passes(monkeypatch, tmp_path):
    monkeypatch.setattr(cp.urllib.request, "urlopen", lambda *a, **k: _Resp(200))
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 0


def test_the_answering_endpoint_is_named(monkeypatch, tmp_path, capsys):
    """"Memory is up" must not quietly mean "someone else's memory is up"."""
    monkeypatch.setattr(cp.urllib.request, "urlopen", lambda *a, **k: _Resp(200))
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    cp.main(["--roster", str(roster)])
    assert "pmoves-cipher-local" in capsys.readouterr().out


def test_an_unexpanded_variable_is_reported_not_probed(tmp_path, capsys):
    """`${TS_Z890}` left literal means the tailnet helper did not run.

    Claude Code would use that text as a hostname, so this is "not configured",
    not a transient outage — and it must not be dialled as though it were a real
    address.
    """
    roster = _roster(tmp_path, {"pmoves-cipher": {"url": "http://${TS_Z890}:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 1
    assert "unresolved variable" in capsys.readouterr().err


def test_one_endpoint_up_is_enough(monkeypatch, tmp_path):
    """Fleet down + local up is a working session, not a failure."""
    def fake(req, *a, **k):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "localhost" in url:
            return _Resp(200)
        raise urllib.error.URLError("unreachable")

    monkeypatch.setattr(cp.urllib.request, "urlopen", fake)
    roster = _roster(tmp_path, {
        "pmoves-cipher": {"url": "http://pmoves-z890:8105/mcp/sse"},
        "pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"},
    })
    assert cp.main(["--roster", str(roster)]) == 0


def test_every_endpoint_down_exits_1(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cp.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("refused")),
    )
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 1
    assert "NO persistent memory" in capsys.readouterr().err


def test_underscore_prefixed_entries_are_skipped(tmp_path):
    """`_pmoves-cipher-legacy-python-wrapper` is a broken duplicate.

    `_` is the repo's real off-switch (mcp_roster_normalize.py P2), so probing
    it would report a down endpoint nobody intends to use.
    """
    roster = _roster(tmp_path, {
        "_pmoves-cipher-legacy-python-wrapper": {"url": "http://localhost:9999/x"},
        "pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"},
    })
    names = [c["name"] for c in cp.cipher_urls_from_roster(roster)]
    assert names == ["pmoves-cipher-local"]


def test_no_cipher_entry_is_unmeasured_not_a_pass(tmp_path):
    """Exit 3. Memory is not configured at all — that is not "fine"."""
    roster = _roster(tmp_path, {"some-other-server": {"url": "http://x/y"}})
    assert cp.main(["--roster", str(roster)]) == 3


def test_a_missing_roster_is_unmeasured(tmp_path):
    assert cp.main(["--roster", str(tmp_path / "absent.json")]) == 3


def test_an_http_error_still_reports_a_status(monkeypatch, tmp_path, capsys):
    """A 404 proves something IS listening — a different problem from absence."""
    def fake(*a, **k):
        raise urllib.error.HTTPError("u", 404, "nf", None, None)

    monkeypatch.setattr(cp.urllib.request, "urlopen", fake)
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 1
    assert "HTTP 404" in capsys.readouterr().err


def test_the_launcher_actually_invokes_the_check():
    """Wiring assertion: a check nothing calls is decoration."""
    body = LAUNCHER.read_text(encoding="utf-8")
    assert "cipher_preflight" in body, "claude-pmoves.sh does not call the cipher check"
