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


@pytest.fixture(autouse=True)
def _no_real_env_file(tmp_path_factory, monkeypatch):
    """Never let a test consult the node's real pmoves/env.shared.

    The probe now layers an env file over the process environment (see
    `layered_environ`), so without this a node that HAS env.shared would feed a
    real CIPHER_API_TOKEN into tests that `delenv` it and assert the variable
    reads as absent. Those tests would pass or fail according to which machine
    ran them -- "works here, reproducible nowhere", the defect class this whole
    lane is about, reintroduced into its own test suite.

    Points at a path that does not exist rather than disabling the overlay, so
    the overlay CODE still runs on every test.
    """
    absent = tmp_path_factory.mktemp("no-env") / "env.shared.absent"
    monkeypatch.setenv("PMOVES_ENV_SHARED", str(absent))


def _env_file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "env.shared"
    path.write_text(body, encoding="utf-8")
    return path


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


# ---------------------------------------------------------------------------
# A crash is could-not-measure, not "the service is UP"
# ---------------------------------------------------------------------------
#
# `main()` returned 1 on any uncaught exception -- python's own exit code for
# one -- and claude-pmoves.sh reads exit 1 as "Cipher ANSWERED, the service is
# UP, do NOT report it as down and do not restart it". So a crash asserted the
# health of a service it had never contacted. That is this file's own thesis
# inverted, and it fired on two paths the reviewer actually executed: a
# schemeless roster url, and a failed import of the roster expander.


def test_an_unexpected_crash_is_could_not_measure_not_a_finding(monkeypatch, tmp_path):
    """Exit 3. Exit 1 would tell the launcher a service we never reached is UP."""

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(cp, "check", explode)
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 3


def test_the_crash_backstop_never_prints_the_exception_message(
    monkeypatch, tmp_path, capsys
):
    """`str(exc)` is not safe here: http.client's ValueError IS the credential."""

    def explode(*a, **k):
        raise ValueError(f"Invalid header value {('Bearer ' + SENTINEL)!r}")

    monkeypatch.setattr(cp, "check", explode)
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 3
    cap = capsys.readouterr()
    assert SENTINEL not in cap.out and SENTINEL not in cap.err
    assert "ValueError" in cap.err  # the TYPE is useful and safe
    assert "NOT a pass" in cap.err


def test_the_crash_backstop_holds_in_json_mode(monkeypatch, tmp_path, capsys):
    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(cp, "check", explode)
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster), "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["measured"] is False


def test_a_schemeless_url_is_a_row_verdict_not_a_crash(monkeypatch, tmp_path, capsys):
    """`Request("example.com/x")` raises ValueError('unknown url type').

    That construction sat outside the try, so one malformed roster row took the
    whole run down -- and the crash exited 1, i.e. "the service is UP".
    """

    def explode(*a, **k):  # pragma: no cover - must never be reached
        raise AssertionError("a malformed url was dialled")

    monkeypatch.setattr(cp, "_urlopen", explode)
    row = cp.probe("example.com/mcp/sse")
    assert row["verdict"] == "invalid_url"
    assert row["ok"] is False

    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "example.com/mcp/sse"}})
    # Nothing was contacted, so there is no measurement: 3, not 1.
    assert cp.main(["--roster", str(roster)]) == 3
    assert "NO persistent memory" in capsys.readouterr().err


def test_a_schemeless_url_does_not_disturb_the_unresolved_verdict(tmp_path):
    """`${TS_Z890}` still reports `unresolved`, which is its own diagnosis."""
    row = cp.probe("http://${TS_Z890}:8105/mcp/sse")
    assert row["verdict"] == "unresolved"


def test_a_broken_roster_expander_is_could_not_measure(monkeypatch, tmp_path, capsys):
    """The import at line ~104 failing used to abort the module -> exit 1.

    Without the shared expander the credential would resolve differently here
    than on the path into Claude Code, so any answer would vouch for something
    else. Refuse rather than guess.
    """
    monkeypatch.setattr(cp, "_EXPANDER_ERROR", "cannot import mcp_roster_normalize (ImportError)")
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 3
    assert "mcp_roster_normalize" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# The launcher must not collapse every exit 1 into "bind the token"
# ---------------------------------------------------------------------------


def test_an_answered_but_unusable_endpoint_is_not_labelled_down(
    monkeypatch, tmp_path, capsys
):
    """A 404 answered. "DOWN" says start the service; nothing is stopped."""

    def fake(*a, **k):
        raise urllib.error.HTTPError("u", 404, "nf", None, None)

    monkeypatch.setattr(cp, "_urlopen", fake)
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    assert cp.main(["--roster", str(roster)]) == 1
    err = capsys.readouterr().err
    assert "cipher ANSWERED" in err
    assert "cipher DOWN" not in err


def test_the_ok_line_shape_the_launcher_awks_is_intact(monkeypatch, tmp_path, capsys):
    """`awk '/^cipher OK/ {print $3; exit}'` in claude-pmoves.sh reads $3 = name."""
    monkeypatch.setattr(cp, "_urlopen", lambda *a, **k: _Resp(200))
    roster = _roster(tmp_path, {"pmoves-cipher-local": {"url": "http://localhost:8105/mcp/sse"}})
    cp.main(["--roster", str(roster)])
    line = next(
        ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("cipher OK")
    )
    assert line.split()[2] == "pmoves-cipher-local"


def test_the_launcher_does_not_blame_the_token_for_every_exit_1():
    """exit 1 is also a 404 or a refused 302. "bind CIPHER_API_TOKEN" is wrong there."""
    body = LAUNCHER.read_text(encoding="utf-8")
    assert 'case "$CIPHER_OUT" in' in body, (
        "claude-pmoves.sh still hardcodes one remedy for every exit 1"
    )
    assert "ANSWERED-UNUSABLE" in body, (
        "claude-pmoves.sh has no branch for answered-but-not-401"
    )


# ---------------------------------------------------------------------------
# The seam is not merely built correctly -- probe() actually goes through it
# ---------------------------------------------------------------------------


def test_probe_routes_through_the_non_redirecting_seam(monkeypatch):
    """The companion to the build_opener test above, which only proved the seam
    CONSTRUCTS the right opener. A `probe` that called `urlopen` directly would
    pass that and still forward the bearer to a redirect target."""
    seen = {}

    def fake_build_opener(*handlers):
        seen["handlers"] = handlers

        class _O:
            def open(self, req, timeout=None):
                return _Resp(200)

        return _O()

    monkeypatch.setattr(cp.urllib.request, "build_opener", fake_build_opener)
    row = cp.probe("http://localhost:8105/mcp/sse")
    assert row["status"] == 200
    assert cp._NoRedirect in seen.get("handlers", ()), (
        "probe() did not go through _urlopen — the redirect refusal is bypassed"
    )


def test_the_directory_network_guard_is_armed():
    """Enforcement of the enforcer.

    The stubs in this file silently detached once already, when probe() moved to
    an opener: the suite kept passing while hitting the real network, visible
    only as runtime going 0.05s -> 6.35s. pmoves/tests/tools/conftest.py denies
    outbound connects so that failure is loud next time. If this assertion ever
    goes red, the guard is gone and every "offline" test here is unverified.
    """
    with pytest.raises(AssertionError):
        socket.create_connection(("127.0.0.1", 9), timeout=0.1)


# ---------------------------------------------------------------------------
# THE PREFLIGHT RUNS BEFORE THE CREDENTIAL IS LOADED (review thread 3939783860)
#
#   pmoves/scripts/claude-pmoves.sh:183   runs cipher_preflight.py
#   pmoves/scripts/claude-pmoves.sh:248   execs deploy/provision/claude-pmoves.sh
#   deploy/provision/claude-pmoves.sh:72  ... which is what loads env.shared
#
# So on `make -C pmoves claude-pmoves`, with the token in its DOCUMENTED home,
# the roster header expanded against an environment that did not contain it:
# the probe went out anonymous, got 401, and the session was told memory was
# unusable seconds before the delegate loaded the token and launched a working
# Cipher MCP. The original defect of this lane -- a check that cannot pass --
# resurrected by ordering.
#
# It passed on the node where the fix was written only because the operator
# happened to have CIPHER_API_TOKEN exported. These tests remove that luck: the
# token is present ONLY in the file in every one of them.
# ---------------------------------------------------------------------------


def test_a_token_that_lives_only_in_the_env_file_still_authenticates(
    monkeypatch, tmp_path
):
    """The P1 regression, stated as the launcher actually invokes it.

    Absent from the process environment, present in the env file -- which is
    the documented arrangement, and which is exactly what
    `make -C pmoves claude-pmoves` produces at the moment this check runs.
    """
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    envf = _env_file(tmp_path, f"CIPHER_API_TOKEN={SENTINEL}\n")
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    rc = cp.main([
        "--roster", str(_cipher_roster(tmp_path)),
        "--env-file", str(envf),
    ])
    assert rc == 0


def test_the_pre_fix_failure_reason_is_unauthorized_not_merely_nonzero(
    monkeypatch, tmp_path, capsys
):
    """Assert the REASON, so a looser matcher cannot make this green wrongly.

    `--no-env-file` reproduces the pre-fix environment exactly: process env
    only, token absent from it. The distinguishing evidence is not "nonzero" --
    it is that the tool reports `unauthorized`, names CIPHER_API_TOKEN as
    unresolved, and records `auth: unresolved` rather than a rejected token.
    A test asserting only `rc != 0` would also pass for an unreachable host, a
    404, or a crash, none of which are this bug.
    """
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    envf = _env_file(tmp_path, f"CIPHER_API_TOKEN={SENTINEL}\n")
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    roster = _cipher_roster(tmp_path)

    rc = cp.main(["--roster", str(roster), "--env-file", str(envf),
                  "--no-env-file", "--json"])
    payload = json.loads(capsys.readouterr().out)
    row = payload["endpoints"][0]

    assert rc == 1, "pre-fix ordering must land on findings, not could-not-measure"
    assert row["verdict"] == "unauthorized"
    assert row["status"] == 401
    assert row["auth"] == "unresolved", (
        "the header must be OMITTED, not sent as literal ${CIPHER_API_TOKEN}"
    )
    assert row["missing_env"] == ["CIPHER_API_TOKEN"]

    # ... and the same invocation WITH the overlay is clean. Both halves in one
    # test so the control cannot drift away from the case it controls.
    rc_fixed = cp.main(["--roster", str(roster), "--env-file", str(envf), "--json"])
    fixed = json.loads(capsys.readouterr().out)
    assert rc_fixed == 0
    assert fixed["endpoints"][0]["verdict"] == "ok"
    assert fixed["endpoints"][0]["auth"] == "presented"
    assert fixed["endpoints"][0]["missing_env"] == []


def test_the_env_file_overrides_an_exported_value_as_the_launcher_does(
    monkeypatch, tmp_path
):
    """Fidelity, not convenience.

    deploy/provision/claude-pmoves.sh sources its sanitized copy under `set -a`,
    so a value in env.shared OVERRIDES an already-exported one. If the overlay
    preferred the process env, a stale token exported in the operator's shell
    would be pronounced healthy while the session went on to use the file's
    value -- the preflight vouching for a credential nobody uses.
    """
    monkeypatch.setenv("CIPHER_API_TOKEN", "stale-value-the-session-will-not-use")
    envf = _env_file(tmp_path, f"CIPHER_API_TOKEN={SENTINEL}\n")
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main([
        "--roster", str(_cipher_roster(tmp_path)),
        "--env-file", str(envf),
    ]) == 0


def test_an_alias_line_in_the_env_file_resolves_in_file_order(monkeypatch, tmp_path):
    """env.shared carries `KEY=${OTHER}` alias lines; the launcher expands them.

    Exporting the literal text is Codex #1987 P2 -- an MCP that starts
    unauthorized while the canonical key is present. The overlay expands in file
    order, which is what sourcing the file sequentially does.
    """
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    monkeypatch.delenv("CANONICAL_CIPHER_KEY", raising=False)
    envf = _env_file(
        tmp_path,
        f"CANONICAL_CIPHER_KEY={SENTINEL}\nCIPHER_API_TOKEN=${{CANONICAL_CIPHER_KEY}}\n",
    )
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main([
        "--roster", str(_cipher_roster(tmp_path)),
        "--env-file", str(envf),
    ]) == 0


def test_an_unresolvable_alias_leaves_the_variable_named_not_blank(
    monkeypatch, tmp_path, capsys
):
    """An alias whose target is unset must not become an empty bearer.

    Under the launcher's `set +u` it would become ``KEY=``, and `Bearer ` on the
    wire returns a 401 indistinguishable from a wrong token. Leaving the key
    ABSENT keeps the diagnosis: the roster expansion names the variable.
    """
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    envf = _env_file(tmp_path, "CIPHER_API_TOKEN=${NOT_SET_ANYWHERE}\n")
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    rc = cp.main([
        "--roster", str(_cipher_roster(tmp_path)),
        "--env-file", str(envf), "--json",
    ])
    row = json.loads(capsys.readouterr().out)["endpoints"][0]
    assert rc == 1
    assert row["auth"] == "unresolved"
    assert row["missing_env"] == ["CIPHER_API_TOKEN"]


def test_the_env_file_blocklist_matches_the_launchers(monkeypatch, tmp_path):
    """The launcher refuses to source ANTHROPIC_API_KEY et al; so must this.

    Resolving a variable the session will NOT load would be the mirror of the
    P1 bug: vouching for a credential that is not going to be there.
    """
    blocked = "ANTHROPIC_API_KEY"
    monkeypatch.delenv(blocked, raising=False)
    envf = _env_file(tmp_path, f"{blocked}=must-not-be-loaded\n")
    env, note = cp.layered_environ(envf, base={})
    assert note is None
    assert blocked not in env, "the overlay loaded a key the launcher blocklists"


def test_the_env_file_value_never_reaches_an_output_stream(
    monkeypatch, tmp_path, capsys
):
    """The overlay reads secrets. None of them may be printed, in either mode."""
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    envf = _env_file(
        tmp_path,
        f"UNRELATED_SECRET=another-{SENTINEL}\nCIPHER_API_TOKEN={SENTINEL}\n",
    )
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    args = ["--roster", str(_cipher_roster(tmp_path)), "--env-file", str(envf)]
    cp.main(args)
    cp.main(args + ["--json"])
    cap = capsys.readouterr()
    assert SENTINEL not in cap.out
    assert SENTINEL not in cap.err


def test_a_missing_env_file_is_not_an_alarm(monkeypatch, tmp_path):
    """A node may legitimately carry creds in the process environment."""
    monkeypatch.setenv("CIPHER_API_TOKEN", SENTINEL)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    env, note = cp.layered_environ(tmp_path / "definitely-not-here")
    assert note is None
    assert cp.main([
        "--roster", str(_cipher_roster(tmp_path)),
        "--env-file", str(tmp_path / "definitely-not-here"),
    ]) == 0


def test_an_unreadable_env_file_degrades_and_never_blocks(monkeypatch, tmp_path, capsys):
    """A bad env file must not abort the launcher, and must SAY it was skipped.

    The note is what keeps a 401 readable: "the token is missing" and "we could
    not look where the token lives" are different findings.
    """
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    envf = _env_file(tmp_path, f"CIPHER_API_TOKEN={SENTINEL}\n")

    def boom(_path):
        raise OSError(f"cannot read, and this message contains {SENTINEL}")

    monkeypatch.setattr(cp, "_parse_env_file", boom)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    rc = cp.main([
        "--roster", str(_cipher_roster(tmp_path)),
        "--env-file", str(envf), "--json",
    ])
    out = capsys.readouterr()
    payload = json.loads(out.out)
    assert rc == 1, "a bad env file is a finding, never a hard failure"
    assert "OSError" in (payload["env_note"] or "")
    assert SENTINEL not in out.out and SENTINEL not in out.err


def test_the_url_mode_presents_the_bearer(monkeypatch, tmp_path):
    """Review thread 3939783864 (P2).

    The documented `--url http://localhost:8105/mcp/sse` built a candidate with
    no `headers`, so it probed anonymously against an endpoint that requires a
    bearer -- it could only ever print 401. Pre-fix this returns 1.
    """
    monkeypatch.setenv("CIPHER_API_TOKEN", SENTINEL)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main(["--url", "http://localhost:8105/mcp/sse"]) == 0


def test_the_url_mode_reads_the_env_file_too(monkeypatch, tmp_path):
    """Both threads at once: an explicit --url with the token only in the file."""
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    envf = _env_file(tmp_path, f"CIPHER_API_TOKEN={SENTINEL}\n")
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main([
        "--url", "http://localhost:8105/mcp/sse", "--env-file", str(envf),
    ]) == 0


def test_the_url_mode_names_the_variable_when_it_is_unset(monkeypatch, capsys):
    """Not a silent anonymous probe: say WHICH variable to set."""
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    rc = cp.main(["--url", "http://localhost:8105/mcp/sse", "--json"])
    row = json.loads(capsys.readouterr().out)["endpoints"][0]
    assert rc == 1
    assert row["auth"] == "unresolved"
    assert row["missing_env"] == ["CIPHER_API_TOKEN"]


def test_the_url_mode_can_name_a_different_variable(monkeypatch):
    monkeypatch.delenv("CIPHER_API_TOKEN", raising=False)
    monkeypatch.setenv("SOME_OTHER_TOKEN_VAR", SENTINEL)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main([
        "--url", "http://localhost:8105/mcp/sse",
        "--token-env", "SOME_OTHER_TOKEN_VAR",
    ]) == 0


def test_the_url_mode_can_probe_anonymously_on_purpose(monkeypatch):
    """`--token-env ''` is how you measure that an endpoint REQUIRES a bearer."""
    monkeypatch.setenv("CIPHER_API_TOKEN", SENTINEL)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main([
        "--url", "http://localhost:8105/mcp/sse", "--token-env", "",
    ]) == 1


def test_no_flag_accepts_a_raw_token_on_argv(capsys):
    """argv is world-readable in `ps` and /proc/<pid>/cmdline.

    `--token-env` names a VARIABLE. A `--token` flag would be a wider leak than
    the http.client ValueError this PR already closed, so its absence is a
    property worth pinning rather than a thing left undone.
    """
    rc = cp.main(["--url", "http://localhost:8105/mcp/sse", "--token", SENTINEL])
    cap = capsys.readouterr()
    assert rc == 2, "a usage error, not a verdict"
    # Not merely nonzero: the reason must be the refusal, and the value must not
    # be echoed back into a log by the code complaining about it being visible.
    assert "--token is refused" in cap.err
    assert SENTINEL not in cap.out and SENTINEL not in cap.err


def test_token_is_not_silently_reinterpreted_as_a_variable_name(monkeypatch, capsys):
    """`--token` is an unambiguous PREFIX of `--token-env`.

    Before `--token` was declared and refused, argparse bound it to `--token-env`,
    so `--token "$CIPHER_API_TOKEN"` meant "the variable named <the token>" --
    unset, anonymous probe, 401, and the credential blamed. Silently doing
    something reasonable-looking with a misused flag is the shape of bug this
    whole file exists to remove.
    """
    monkeypatch.setenv("CIPHER_API_TOKEN", SENTINEL)
    monkeypatch.setattr(cp, "_urlopen", _auth_gated())
    assert cp.main(["--url", "http://localhost:8105/mcp/sse", "--token", SENTINEL]) == 2
    assert "--token is refused" in capsys.readouterr().err


def test_the_launcher_still_precedes_the_env_loading_delegate():
    """Pins WHY the tool must resolve the env file itself.

    If someone later moves the preflight after the env load in the launcher,
    this fails and points at the overlay as now-redundant -- rather than the
    overlay quietly rotting while the ordering silently changes underneath it.
    """
    body = LAUNCHER.read_text(encoding="utf-8")
    probe_at = body.index("cipher_preflight.py")
    exec_at = body.rindex("exec bash \"$LAUNCHER\"")
    assert probe_at < exec_at, (
        "the preflight no longer runs before the delegate that loads env.shared"
    )
    # `set -a` is HOW an env file gets loaded (deploy/provision/claude-pmoves.sh
    # brackets its `. "$tmpf"` with it). Matching the mechanism rather than the
    # words "env.shared", which appear in this launcher's header comment
    # describing what the DELEGATE does.
    assert "set -a" not in body[:probe_at], (
        "the thin launcher now loads an env file itself — re-read the overlay's rationale"
    )
