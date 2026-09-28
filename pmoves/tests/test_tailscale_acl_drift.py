"""Tests for pmoves/tools/tailscale_acl_drift.py (read-only tailnet policy drift).

No test touches the network: the live side is either a fixture file
(--live-file) or a monkeypatched urlopen.
"""

from __future__ import annotations

import http.client
import io
import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))

import tailscale_acl_drift as tad  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "tailscale_acl"
REPO_FIXTURE = FIX / "repo_policy.hujson"
REAL_POLICY = REPO_ROOT / "pmoves" / "configs" / "tailscale-acl-policy.json"

CRED_VARS = (
    "TS_OAUTH_CLIENT_ID",
    "TS_OAUTH_SECRET",
    "TS_API_KEY",
    "TAILSCALE_API_KEY",
    "TAILSCALE_APIKEY",
    "TS_TAILNET",
    "TAILSCALE_TAILNET",
    "GITHUB_STEP_SUMMARY",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in CRED_VARS:
        monkeypatch.delenv(var, raising=False)


# --------------------------------------------------------------- HuJSON parsing
def test_strip_preserves_slashes_and_commas_inside_strings():
    text = '{"u": "https://x//y", "v": "a,]", // c\n "w": [1,2,], /* z */}'
    assert json.loads(tad.strip_hujson(text)) == {"u": "https://x//y", "v": "a,]", "w": [1, 2]}


def test_strip_handles_escaped_quote():
    text = '{"q": "he said \\"//not a comment\\"", }'
    assert json.loads(tad.strip_hujson(text)) == {"q": 'he said "//not a comment"'}


def test_unterminated_block_comment_is_could_not_measure():
    with pytest.raises(tad.CouldNotMeasure):
        tad.parse_policy('{"a": 1 /* never closed', "x")


def test_real_repo_policy_parses_and_has_ssh_rule():
    policy = tad.parse_policy(REAL_POLICY.read_text(encoding="utf-8"), "repo")
    rule = policy["ssh"][0]
    assert rule["src"] == ["tag:pmoves"] and rule["dst"] == ["tag:pmoves"]
    assert rule["users"] == ["autogroup:nonroot"]


def test_real_repo_policy_round_trip_is_not_drift():
    """A live copy that is the same policy minus comments/whitespace is NOT drift."""
    policy = tad.parse_policy(REAL_POLICY.read_text(encoding="utf-8"), "repo")
    reserialised = json.loads(json.dumps(policy, separators=(",", ":")))
    drifted, _ = tad.compare(policy, reserialised, "repo", "live")
    assert drifted is False


# --------------------------------------------------------------- compare / CLI
def test_identical_fixture_exits_zero(capsys):
    rc = tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(FIX / "live_identical.json")])
    out = capsys.readouterr().out
    assert rc == tad.EXIT_CLEAN
    assert "OK: no drift" in out


def test_drifted_fixture_exits_one_and_names_ssh(capsys):
    rc = tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(FIX / "live_drifted.hujson")])
    out = capsys.readouterr().out
    assert rc == tad.EXIT_DRIFT
    assert "  - ssh: +0 / -0 / ~1" in out
    assert "  - sshTests: +0 / -1 / ~0" in out
    assert "  - ssh[0].users[0]: changed" in out
    assert "  - sshTests: removed on live" in out
    # Values are withheld by default ...
    assert "autogroup:nonroot" not in out and '"pmoves"' not in out
    # ... and unchanged sections are not listed.
    assert "  - acls:" not in out


def test_show_values_adds_redacted_diff(capsys):
    rc = tad.main(
        [
            "--policy-file",
            str(REPO_FIXTURE),
            "--live-file",
            str(FIX / "live_drifted.hujson"),
            "--show-values",
        ]
    )
    out = capsys.readouterr().out
    assert rc == tad.EXIT_DRIFT
    assert '-        "autogroup:nonroot"' in out
    assert '+        "pmoves"' in out
    assert "repo-side-placeholder" not in out


def test_report_only_prints_drift_but_exits_zero(capsys):
    rc = tad.main(
        [
            "--policy-file",
            str(REPO_FIXTURE),
            "--live-file",
            str(FIX / "live_drifted.hujson"),
            "--report-only",
        ]
    )
    assert rc == tad.EXIT_CLEAN
    assert "DRIFT:" in capsys.readouterr().out


def test_redacted_values_never_printed(capsys):
    tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(FIX / "live_drifted.hujson")])
    out = capsys.readouterr().out
    assert "repo-side-placeholder" not in out


def test_drift_only_in_redacted_field_is_still_drift_but_value_withheld(capsys):
    rc = tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(FIX / "live_secret_drift.json")])
    out = capsys.readouterr().out
    assert rc == tad.EXIT_DRIFT
    assert "derpMap.privateKey: changed" in out
    assert "LIVE-SIDE-DIFFERENT-VALUE" not in out
    assert "repo-side-placeholder" not in out


def test_missing_policy_file_is_could_not_measure(tmp_path, capsys):
    rc = tad.main(["--policy-file", str(tmp_path / "nope.json"), "--live-file", str(REPO_FIXTURE)])
    assert rc == tad.EXIT_UNMEASURED
    assert "COULD-NOT-MEASURE" in capsys.readouterr().err


def test_step_summary_written(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(FIX / "live_drifted.hujson")])
    assert "Tailscale policy drift" in summary.read_text()


def test_save_live_is_redacted(tmp_path):
    out = tmp_path / "live.json"
    tad.main(
        [
            "--policy-file",
            str(REPO_FIXTURE),
            "--live-file",
            str(FIX / "live_identical.json"),
            "--save-live",
            str(out),
        ]
    )
    saved = json.loads(out.read_text())
    assert saved["derpMap"]["privateKey"] == tad.REDACTED


# --------------------------------------------------------------- live fetch (mocked)
class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_no_credentials_is_could_not_measure(capsys):
    rc = tad.main(["--policy-file", str(REPO_FIXTURE)])
    assert rc == tad.EXIT_UNMEASURED
    assert "no credential" in capsys.readouterr().err


def test_api_key_fetch_is_a_single_get_and_never_prints_key(monkeypatch, capsys):
    secret = "tskey-api-FAKEFAKEFAKE-notreal"
    monkeypatch.setenv("TAILSCALE_API_KEY", secret)
    seen = []

    def fake_urlopen(req, timeout=30):
        seen.append((req.get_method(), req.full_url, req.headers.get("Accept")))
        return _Resp((FIX / "live_identical.json").read_bytes())

    monkeypatch.setattr(tad.urllib.request, "urlopen", fake_urlopen)
    rc = tad.main(["--policy-file", str(REPO_FIXTURE)])
    captured = capsys.readouterr()
    assert rc == tad.EXIT_CLEAN
    assert seen == [("GET", f"{tad.API_BASE}/tailnet/-/acl", "application/hujson")]
    assert secret not in captured.out + captured.err


def test_oauth_exchanges_then_gets_with_bearer(monkeypatch):
    monkeypatch.setenv("TS_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("TS_OAUTH_SECRET", "csecret")
    monkeypatch.setenv("TS_TAILNET", "example.com")
    calls = []

    def fake_urlopen(req, timeout=30):
        calls.append((req.get_method(), req.full_url, req.headers.get("Authorization")))
        if req.full_url.endswith("/oauth/token"):
            return _Resp(json.dumps({"access_token": "tok123"}).encode())
        return _Resp((FIX / "live_drifted.hujson").read_bytes())

    monkeypatch.setattr(tad.urllib.request, "urlopen", fake_urlopen)
    rc = tad.main(["--policy-file", str(REPO_FIXTURE)])
    assert rc == tad.EXIT_DRIFT
    assert calls[0][:2] == ("POST", f"{tad.API_BASE}/oauth/token")
    assert calls[1] == ("GET", f"{tad.API_BASE}/tailnet/example.com/acl", "Bearer tok123")
    # Read-only: exactly one token exchange and one GET, nothing else.
    assert len(calls) == 2


@pytest.mark.parametrize("code,needle", [(401, "policy scope"), (403, "policy scope"), (404, "not found")])
def test_http_errors_are_could_not_measure_with_hint(monkeypatch, capsys, code, needle):
    monkeypatch.setenv("TS_API_KEY", "tskey-api-x")

    def fake_urlopen(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, code, "err", {}, None)

    monkeypatch.setattr(tad.urllib.request, "urlopen", fake_urlopen)
    rc = tad.main(["--policy-file", str(REPO_FIXTURE)])
    err = capsys.readouterr().err
    assert rc == tad.EXIT_UNMEASURED
    assert f"HTTP {code}" in err and needle in err


# --------------------------------------------------------------- public-log safety
PLANTED = (
    "planted.person@example.invalid",
    "198.51.100.77",
    "planted-host",
    "tag:plantedvaluetag",
    "tag:plantedkeytag",
)


def test_default_output_contains_no_planted_live_values(tmp_path, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    rc = tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(FIX / "live_planted.hujson")])
    captured = capsys.readouterr()
    published = captured.out + captured.err + summary.read_text()
    assert rc == tad.EXIT_DRIFT
    fixture_text = (FIX / "live_planted.hujson").read_text()
    for value in PLANTED:
        assert value in fixture_text, value  # the test is not vacuous
        assert value not in published, value
    # Control: the opt-in local flag DOES surface them, so the default is what hides them.
    tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(FIX / "live_planted.hujson"), "--show-values"])
    shown = capsys.readouterr().out
    assert "198.51.100.77" in shown and "planted.person@example.invalid" in shown
    # Structure is still reported.
    assert "  - groups: added on live" in captured.out
    assert "  - hosts: added on live" in captured.out
    assert '  - tagOwners[<live-only key>]: added on live' in captured.out
    assert "  - ssh[0].src[1]: added on live" in captured.out


def test_comparison_is_type_strict(capsys):
    """false (repo) vs 0 (live) is drift; Python's False == 0 must not hide it."""
    rc = tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(FIX / "live_planted.hujson")])
    assert rc == tad.EXIT_DRIFT
    assert "derpMap.OmitDefaultRegions: type changed" in capsys.readouterr().out
    assert tad.same(True, 1) is False and tad.same(1, 1.0) is False


def test_summary_uses_no_fence_that_input_could_break(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    repo = tmp_path / "repo.json"
    live = tmp_path / "live.json"
    repo.write_text(json.dumps({"tagOwners": {"x```\n# injected": ["a"]}}))
    live.write_text(json.dumps({"tagOwners": {"x```\n# injected": ["b"]}}))
    tad.main(["--policy-file", str(repo), "--live-file", str(live)])
    text = summary.read_text()
    assert "```" not in text
    assert "\n# injected" not in text


# --------------------------------------------------------------- exit-code integrity
def test_missing_live_file_is_rc3(tmp_path, capsys):
    rc = tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(tmp_path / "gone.json")])
    assert rc == tad.EXIT_UNMEASURED
    assert "COULD-NOT-MEASURE" in capsys.readouterr().err


def test_non_utf8_live_file_is_rc3(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_bytes(b'{"a": "\xff\xfe"}')
    assert tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(bad)]) == tad.EXIT_UNMEASURED


def test_incomplete_read_is_rc3(monkeypatch, capsys):
    monkeypatch.setenv("TS_API_KEY", "tskey-api-x")

    class _Broken(_Resp):
        def read(self, *a):
            raise http.client.IncompleteRead(b"{", 100)

    monkeypatch.setattr(tad.urllib.request, "urlopen", lambda req, timeout=30: _Broken(b""))
    assert tad.main(["--policy-file", str(REPO_FIXTURE)]) == tad.EXIT_UNMEASURED
    assert "IncompleteRead" in capsys.readouterr().err


def test_unicode_decode_error_from_api_is_rc3(monkeypatch):
    monkeypatch.setenv("TS_API_KEY", "tskey-api-x")
    monkeypatch.setattr(tad.urllib.request, "urlopen", lambda req, timeout=30: _Resp(b"\xff\xfe\xfa"))
    assert tad.main(["--policy-file", str(REPO_FIXTURE)]) == tad.EXIT_UNMEASURED


@pytest.mark.parametrize("body", [b'["not", "an", "object"]', b'"str"', b"null", b"{}", b"not json"])
def test_bad_oauth_json_is_rc3(monkeypatch, capsys, body):
    monkeypatch.setenv("TS_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("TS_OAUTH_SECRET", "csecret")
    monkeypatch.setattr(tad.urllib.request, "urlopen", lambda req, timeout=30: _Resp(body))
    assert tad.main(["--policy-file", str(REPO_FIXTURE)]) == tad.EXIT_UNMEASURED
    assert "OAuth token exchange" in capsys.readouterr().err


def test_unexpected_exception_is_rc3_not_drift(monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(tad, "compare", boom)
    rc = tad.main(["--policy-file", str(REPO_FIXTURE), "--live-file", str(FIX / "live_drifted.hujson")])
    assert rc == tad.EXIT_UNMEASURED
    assert "unexpected RuntimeError" in capsys.readouterr().err


def test_bad_arguments_are_rc3():
    assert tad.main(["not-a-mode"]) == tad.EXIT_UNMEASURED


def test_runs_under_python_OO():
    """No runtime dependence on __doc__ (stripped under -OO)."""
    tool = REPO_ROOT / "pmoves" / "tools" / "tailscale_acl_drift.py"
    res = subprocess.run(
        [sys.executable, "-OO", str(tool), "--policy-file", str(REPO_FIXTURE),
         "--live-file", str(FIX / "live_identical.json")],
        capture_output=True, text=True, check=False,
    )
    assert res.returncode == 0, res.stderr
    assert "OK: no drift" in res.stdout


# --------------------------------------------------------------- validate mode
def _validate_env(monkeypatch):
    monkeypatch.setenv("TS_API_KEY", "tskey-api-FAKE-validate")
    monkeypatch.setenv("TS_TAILNET", "example.com")


def test_validate_success_posts_policy_every_time(monkeypatch, capsys):
    _validate_env(monkeypatch)
    calls = []

    def fake_urlopen(req, timeout=30):
        calls.append((req.get_method(), req.full_url, req.data))
        return _Resp(b"{}")

    monkeypatch.setattr(tad.urllib.request, "urlopen", fake_urlopen)
    for _ in range(2):  # no ETag short-circuit: every run POSTs
        assert tad.main(["validate", "--policy-file", str(REPO_FIXTURE)]) == tad.EXIT_CLEAN
    assert [c[:2] for c in calls] == [("POST", f"{tad.API_BASE}/tailnet/example.com/acl/validate")] * 2
    assert calls[0][2] == REPO_FIXTURE.read_bytes()
    out = capsys.readouterr().out
    assert "OK: Tailscale validated" in out
    assert "tskey-api-FAKE-validate" not in out


def test_validate_policy_error_is_finding(monkeypatch, capsys):
    _validate_env(monkeypatch)
    body = json.dumps({"message": 'line 3: unknown field "srcs"'}).encode()

    def fake_urlopen(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(body))

    monkeypatch.setattr(tad.urllib.request, "urlopen", fake_urlopen)
    rc = tad.main(["validate", "--policy-file", str(REPO_FIXTURE)])
    out = capsys.readouterr().out
    assert rc == tad.EXIT_FINDING
    assert "policy rejected (HTTP 400)" in out and "unknown field" in out


def test_validate_test_failure_is_finding(monkeypatch, capsys):
    _validate_env(monkeypatch)
    body = json.dumps(
        {
            "message": "test(s) failed",
            "data": [{"user": "tag:partner", "errors": ["tag:pmoves:22 should be denied"]}],
        }
    ).encode()
    monkeypatch.setattr(tad.urllib.request, "urlopen", lambda req, timeout=30: _Resp(body))
    rc = tad.main(["validate", "--policy-file", str(REPO_FIXTURE)])
    out = capsys.readouterr().out
    assert rc == tad.EXIT_FINDING
    assert "message: test(s) failed" in out
    assert "test error [tag:partner]: tag:pmoves:22 should be denied" in out


def test_validate_data_without_message_is_still_finding(monkeypatch):
    _validate_env(monkeypatch)
    body = json.dumps({"data": [{"user": "x", "warnings": ["w"]}]}).encode()
    monkeypatch.setattr(tad.urllib.request, "urlopen", lambda req, timeout=30: _Resp(body))
    assert tad.main(["validate", "--policy-file", str(REPO_FIXTURE)]) == tad.EXIT_FINDING


@pytest.mark.parametrize("code", [401, 403, 404, 429, 500])
def test_validate_credential_or_server_problem_is_rc3(monkeypatch, code):
    _validate_env(monkeypatch)

    def fake_urlopen(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, code, "err", {}, None)

    monkeypatch.setattr(tad.urllib.request, "urlopen", fake_urlopen)
    assert tad.main(["validate", "--policy-file", str(REPO_FIXTURE)]) == tad.EXIT_UNMEASURED


def test_validate_non_object_2xx_is_rc3(monkeypatch):
    _validate_env(monkeypatch)
    monkeypatch.setattr(tad.urllib.request, "urlopen", lambda req, timeout=30: _Resp(b"[1,2]"))
    assert tad.main(["validate", "--policy-file", str(REPO_FIXTURE)]) == tad.EXIT_UNMEASURED
