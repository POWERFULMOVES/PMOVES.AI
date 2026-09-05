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
import urllib.request
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
    monkeypatch.setattr(cp, "_urlopen", lambda *a, **k: _Resp(200))
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 0


def test_the_answering_endpoint_is_named(monkeypatch, tmp_path, capsys):
    """"Memory is up" must not quietly mean "someone else's memory is up"."""
    monkeypatch.setattr(cp, "_urlopen", lambda *a, **k: _Resp(200))
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
    # Exit 3, not 1. The module docstring has always named "nothing resolvable"
    # as a could-not-measure case; the code returned 1 anyway and this test
    # asserted the code rather than the doctrine. Nothing was ever dialled, so
    # there is no measurement to report as a finding.
    assert cp.main(["--roster", str(roster)]) == 3
    assert "unresolved variable" in capsys.readouterr().err


def test_one_endpoint_up_is_enough(monkeypatch, tmp_path):
    """Fleet down + local up is a working session, not a failure."""
    def fake(req, *a, **k):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "localhost" in url:
            return _Resp(200)
        raise urllib.error.URLError("unreachable")

    monkeypatch.setattr(cp, "_urlopen", fake)
    roster = _roster(tmp_path, {
        "pmoves-cipher": {"url": "http://pmoves-z890:8105/mcp/sse"},
        "pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"},
    })
    assert cp.main(["--roster", str(roster)]) == 0


def test_nothing_reachable_is_unmeasured_and_says_no_memory(monkeypatch, tmp_path, capsys):
    """Nothing answered at all — the one case where "no memory" is TRUE.

    Renamed from `test_every_endpoint_down_exits_1`: connection-refused reaches
    nothing, so it is could-not-measure (3), not a finding (1). A finding
    requires that something answered, which is the 401 case below.
    """
    monkeypatch.setattr(
        cp, "_urlopen",
        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("refused")),
    )
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 3
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

    monkeypatch.setattr(cp, "_urlopen", fake)
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 1
    assert "HTTP 404" in capsys.readouterr().err


def test_the_launcher_actually_invokes_the_check():
    """Wiring assertion: a check nothing calls is decoration."""
    body = LAUNCHER.read_text(encoding="utf-8")
    assert "cipher_preflight" in body, "claude-pmoves.sh does not call the cipher check"


# ---------------------------------------------------------------------------
# The credential the endpoint requires
# ---------------------------------------------------------------------------
#
# Measured on B850 2026-09-05, against the live container:
#
#     GET /health                          -> 200
#     GET /mcp/sse   (no Authorization)    -> 401
#     GET /mcp/sse   (Bearer $TOKEN)       -> 200
#
# `.claude/mcp.json` carries `headers.Authorization: "Bearer ${CIPHER_API_TOKEN}"`
# on BOTH cipher entries, and `cipher_urls_from_roster` used to discard it. The
# probe therefore sent no credential, the only reachable outcome was 401, and
# 401 was folded into DOWN — a check that could not pass. Three sessions were
# told they had no memory while Cipher was healthy the whole time.
#
# A sentinel token, never a real one: these tests also assert the value never
# reaches an output stream.
SENTINEL = "sentinel-token-not-a-real-credential"


def _auth_gated(expected: str = f"Bearer {SENTINEL}"):
    """urlopen stub: 200 only when the right bearer is presented, else 401."""

    def fake(req, *a, **k):
        got = req.get_header("Authorization") if hasattr(req, "get_header") else None
        if got == expected:
            return _Resp(200)
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", None, None)

    return fake


def _cipher_roster(tmp_path: Path) -> Path:
    return _roster(tmp_path, {
        "pmoves-cipher-local": {
            "url": "http://localhost:8105/mcp/sse",
            "headers": {"Authorization": f"Bearer ${{{'CIPHER_API_TOKEN'}}}"},
        }
    })


def test_the_roster_bearer_is_actually_presented(monkeypatch, tmp_path):
    """GREEN when the token is available — the whole point of the fix.

    Pre-fix this exits 1: the header never left the roster.
    """
    monkeypatch.setenv("CIPHER_API_TOKEN", SENTINEL)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main(["--roster", str(_cipher_roster(tmp_path))]) == 0


def test_headers_survive_the_roster_read(tmp_path):
    """`cipher_urls_from_roster` must carry `headers`, not drop them."""
    cands = cp.cipher_urls_from_roster(_cipher_roster(tmp_path))
    assert cands[0].get("headers"), "headers were discarded on the way out of the roster"


def test_a_401_is_unauthorized_not_down(monkeypatch, tmp_path, capsys):
    """REACHABLE-BUT-UNAUTHORIZED is proof of life, and a different remedy.

    "Cipher is dead" says start the service. "Cipher refused my credential"
    says bind the token. Collapsing them sent operators after the wrong fix.
    """
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main(["--roster", str(_cipher_roster(tmp_path))]) == 1
    err = capsys.readouterr().err
    assert "UNAUTHORIZED" in err
    assert "DOWN" not in err, "401 must not be reported as DOWN"


def test_the_summary_never_says_nothing_answered_when_something_answered(
    monkeypatch, tmp_path, capsys
):
    """The endpoint DID answer. It answered 401. That is not silence."""
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    cp.main(["--roster", str(_cipher_roster(tmp_path))])
    err = capsys.readouterr().err
    assert "No cipher endpoint answered" not in err


def test_a_false_no_memory_verdict_is_not_issued_on_401(monkeypatch, tmp_path, capsys):
    """The instruction that cost three sessions their memory layer.

    Cipher answering 401 is up. Telling the session it has NO persistent memory
    is false, and it acts on that by abandoning recall.
    """
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    cp.main(["--roster", str(_cipher_roster(tmp_path))])
    err = capsys.readouterr().err
    assert "NO persistent memory" not in err


def test_the_missing_variable_is_named_never_valued(monkeypatch, tmp_path, capsys):
    """An unresolvable header var is announced by NAME — P5 doctrine, WARN not drop."""
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    cp.main(["--roster", str(_cipher_roster(tmp_path))])
    assert "CIPHER_API_TOKEN" in capsys.readouterr().err


def test_the_token_value_never_reaches_an_output_stream(monkeypatch, tmp_path, capsys):
    """Names and lengths only. A preflight that leaks the credential it checks
    is a worse bug than the one it fixes."""
    monkeypatch.setenv("CIPHER_API_TOKEN", SENTINEL)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    roster = _cipher_roster(tmp_path)
    cp.main(["--roster", str(roster)])
    cp.main(["--roster", str(roster), "--json"])
    cap = capsys.readouterr()
    assert SENTINEL not in cap.out
    assert SENTINEL not in cap.err


def test_json_carries_the_verdict_and_no_secret(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    cp.main(["--roster", str(_cipher_roster(tmp_path)), "--json"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["endpoints"][0]["verdict"] == "unauthorized"
    assert SENTINEL not in json.dumps(doc)


def test_unreachable_is_could_not_measure_not_a_finding(monkeypatch, tmp_path):
    """Exit-code doctrine, shared with mcp_toolkit_preflight.py and
    docker_host_policy_check.py: 0 clean / 1 findings / 3 could-not-measure.

    Connection refused means the probe never reached anything, so there is no
    measurement to report — exit 3. Contrast a 401, which IS a measurement.
    """
    monkeypatch.setattr(
        cp, "_urlopen",
        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("refused")),
    )
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 3


def test_the_launcher_distinguishes_unauthorized_from_absent():
    """Wiring: the launcher must not tell the session "no memory" on a 401."""
    body = LAUNCHER.read_text(encoding="utf-8")
    assert "UNAUTHORIZED" in body or "unauthorized" in body, (
        "claude-pmoves.sh still collapses 401 into the no-memory message"
    )


def test_a_redirect_is_refused_so_the_bearer_cannot_be_forwarded():
    """urllib forwards Authorization to a redirect target, cross-host included.

    `HTTPRedirectHandler.redirect_request` copies every header except
    content-length/content-type onto a Request for the new URL — there is no
    cross-host strip the way `requests` has one. Once this probe started
    sending a credential, a 302 became a credential-exfiltration vector, so the
    opener declines redirects outright.
    """
    handler = cp._NoRedirect()
    req = urllib.request.Request(
        "http://localhost:8105/mcp/sse",
        headers={"Authorization": f"Bearer {SENTINEL}"},
    )
    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(req, None, 302, "Found", {}, "http://elsewhere.invalid/x")


def test_the_network_seam_installs_the_non_redirecting_handler(monkeypatch):
    """Wiring: the handler above is worthless if the seam builds a plain opener."""
    seen = {}

    def fake_build_opener(*handlers):
        seen["handlers"] = handlers

        class _O:
            def open(self, req, timeout=None):
                return _Resp(200)

        return _O()

    monkeypatch.setattr(cp.urllib.request, "build_opener", fake_build_opener)
    cp._urlopen(urllib.request.Request("http://localhost:8105/mcp/sse"), 1.0)
    assert cp._NoRedirect in seen["handlers"]


def test_a_trailing_newline_on_the_token_does_not_break_the_probe(monkeypatch, tmp_path):
    """The common real case: a token read from an env file keeps its newline.

    RFC 7230 3.2.4 excludes leading/trailing OWS from a field value, so
    stripping is correct. Left in, http.client raises
    `ValueError('Invalid header value %r' % value)` -- which prints the token.
    """
    monkeypatch.setenv("CIPHER_API_TOKEN", f"{SENTINEL}\n")
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main(["--roster", str(_cipher_roster(tmp_path))]) == 0


def test_an_embedded_crlf_credential_is_refused_without_printing_it(
    monkeypatch, tmp_path, capsys
):
    """A token with an interior CR/LF is corrupt or an injection attempt.

    It must never reach http.client, whose ValueError message quotes the value
    verbatim. Nothing is contacted, so this is could-not-measure (3).
    """
    poisoned = f"{SENTINEL}\r\nX-Injected: 1"
    monkeypatch.setenv("CIPHER_API_TOKEN", poisoned)

    def explode(*a, **k):  # pragma: no cover - must never be reached
        raise AssertionError("a malformed header was handed to the transport")

    monkeypatch.setattr(cp, "_urlopen", explode)
    assert cp.main(["--roster", str(_cipher_roster(tmp_path))]) == 3
    cap = capsys.readouterr()
    assert SENTINEL not in cap.out and SENTINEL not in cap.err
    assert "value withheld" in cap.err


def test_a_transport_valueerror_never_surfaces_its_message(monkeypatch, tmp_path, capsys):
    """Backstop. `str(exc)` on http.client's ValueError IS the credential."""
    monkeypatch.setenv("CIPHER_API_TOKEN", SENTINEL)

    def raise_valueerror(*a, **k):
        raise ValueError(f"Invalid header value {('Bearer ' + SENTINEL)!r}")

    monkeypatch.setattr(cp, "_urlopen", raise_valueerror)
    cp.main(["--roster", str(_cipher_roster(tmp_path))])
    cap = capsys.readouterr()
    assert SENTINEL not in cap.out and SENTINEL not in cap.err
