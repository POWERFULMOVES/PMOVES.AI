"""secrets-provider-verify: exit-code matrix and output hygiene, HTTP mocked.

No test here reaches a provider. Every request goes through the ``http_get``
seam, and the directory conftest denies non-loopback connects as a backstop.
Every key is FABRICATED: a provider prefix + FAKE + zeros.
"""

from __future__ import annotations

import json

import pytest

from pmoves.tools import secrets_provider_verify as v
from pmoves.tools.secret_shape_rules import load_rules

KEYS = {
    "ANTHROPIC_API_KEY": "sk-ant-api03-FAKE-" + "0" * 60,
    "OPENAI_API_KEY": "sk-proj-FAKE-" + "0" * 40,
    "GEMINI_API_KEY": "AIzaFAKE" + "0" * 31,
    "HF_TOKEN": "hf_FAKE" + "0" * 30,
    "GITHUB_PAT": "github_pat_FAKE_" + "0" * 60,
    "GH_TOKEN": "gho_FAKE" + "0" * 32,
    "GHCR_TOKEN": "ghp_FAKE" + "0" * 32,
    "TAILSCALE_API_KEY": "tskey-api-FAKE-" + "0" * 30,
}
SCOPES_OK = {"X-OAuth-Scopes": "repo, read:packages"}


class FakeHttp:
    """Answers by URL+label; records what was sent. Never touches a socket."""

    def __init__(self, status=200, headers=None, by_label=None, raise_for=None):
        self.status = status
        self.headers = SCOPES_OK if headers is None else headers
        self.by_label = by_label or {}
        self.raise_for = raise_for or {}
        self.calls = []

    def __call__(self, url, headers, timeout):
        sent = next(
            (label for label, value in KEYS.items() if any(value in h for h in headers.values())),
            None,
        )
        self.calls.append((url, dict(headers), sent))
        if sent in self.raise_for:
            raise self.raise_for[sent]
        answer = self.by_label.get(sent, (self.status, self.headers))
        status, response_headers = answer[0], answer[1]
        reasons = answer[2] if len(answer) > 2 else ()
        return v.HttpResult(status=status, headers=response_headers, reasons=reasons)


def _run(env, http, *argv):
    return v.main(list(argv), env=env, http_get=http)


def test_all_ok_exits_0(capsys):
    assert _run(KEYS, FakeHttp()) == 0
    assert "VERDICT: PASS exit=0" in capsys.readouterr().out


def test_one_auth_failure_exits_1():
    assert _run(KEYS, FakeHttp(by_label={"OPENAI_API_KEY": (401, {})})) == 1


def test_a_missing_key_is_unmeasured_and_never_sent():
    env = {k: val for k, val in KEYS.items() if k != "HF_TOKEN"}
    http = FakeHttp()
    assert _run(env, http) == 3
    assert "huggingface.co" not in " ".join(url for url, _, _ in http.calls)


def test_a_blank_key_is_unmeasured_not_a_pass():
    assert _run({**KEYS, "HF_TOKEN": "   "}, FakeHttp()) == 3


@pytest.mark.parametrize("status", [302, 404, 429, 500, 503])
def test_an_inconclusive_status_is_unmeasured(status):
    assert _run(KEYS, FakeHttp(by_label={"ANTHROPIC_API_KEY": (status, {})})) == 3


def test_a_failure_outranks_an_unmeasured():
    http = FakeHttp(by_label={"OPENAI_API_KEY": (403, {}), "HF_TOKEN": (503, {})})
    assert _run(KEYS, http) == 1


def test_no_keys_at_all_exits_3_without_any_request():
    http = FakeHttp()
    assert _run({}, http) == 3
    assert http.calls == []


def test_a_transport_error_is_unmeasured_and_names_only_the_class(capsys):
    secret = KEYS["GEMINI_API_KEY"]
    http = FakeHttp(raise_for={"GEMINI_API_KEY": OSError(f"boom {secret}")})
    assert _run(KEYS, http) == 3
    out = capsys.readouterr().out
    assert "request failed (OSError)" in out
    assert secret not in out


def test_gemini_400_is_a_failure_only_with_the_api_key_invalid_reason(capsys):
    bad_key = FakeHttp(by_label={"GEMINI_API_KEY": (400, {}, ("INVALID_ARGUMENT", "API_KEY_INVALID"))})
    assert _run(KEYS, bad_key, "--only", "gemini") == 1
    assert "API_KEY_INVALID" in capsys.readouterr().out


@pytest.mark.parametrize("reasons", [("FAILED_PRECONDITION",), ("INVALID_ARGUMENT",), ()])
def test_gemini_400_for_anything_else_is_unmeasured(reasons):
    """An unsupported region answers 400 FAILED_PRECONDITION with a VALID key."""
    http = FakeHttp(by_label={"GEMINI_API_KEY": (400, {}, reasons)})
    assert _run(KEYS, http, "--only", "gemini") == 3


def test_error_reasons_keep_only_machine_identifiers():
    secret = KEYS["GEMINI_API_KEY"]
    body = json.dumps({"error": {
        "code": 400, "message": f"API key not valid: {secret}", "status": "INVALID_ARGUMENT",
        "details": [{"reason": "API_KEY_INVALID", "metadata": {"echo": secret}},
                    {"reason": secret}, "junk"],
    }}).encode()
    reasons = v._error_reasons(body)
    assert reasons == ("INVALID_ARGUMENT", "API_KEY_INVALID")
    assert v._error_reasons(b"not json") == () and v._error_reasons(b"[1]") == ()


def test_an_installation_token_in_gh_token_is_unmeasured_and_never_sent():
    """A CI GITHUB_TOKEN (ghs_) in GH_TOKEN would 403 on GET /user: a false fail."""
    http = FakeHttp(by_label={"GH_TOKEN": (403, {})})
    env = {**KEYS, "GH_TOKEN": "ghs_123456_FAKEhdr0.FAKEpayload0-0000.FAKEsig_0000"}
    assert _run(env, http, "--only", "github-gh-token") == 3
    assert http.calls == []


def test_an_installation_token_on_ghcr_is_unmeasured_and_never_sent():
    """ghs_ cannot call GET /user; reporting 403 as 'rejected' would be a lie."""
    http = FakeHttp()
    env = {**KEYS, "GHCR_TOKEN": "ghs_123456_FAKEhdr0.FAKEpayload0-0000.FAKEsig_0000"}
    assert _run(env, http, "--only", "ghcr") == 3
    assert http.calls == []


def test_ghcr_accepts_an_oauth_token_that_carries_read_packages():
    env = {**KEYS, "GHCR_TOKEN": "gho_FAKE" + "0" * 32}
    assert _run(env, FakeHttp(), "--only", "ghcr") == 0


def test_ghcr_needs_a_packages_scope_not_just_a_live_token():
    no_scope = FakeHttp(by_label={"GHCR_TOKEN": (200, {"X-OAuth-Scopes": "repo, user"})})
    assert _run(KEYS, no_scope, "--only", "ghcr") == 1
    fine_grained = FakeHttp(by_label={"GHCR_TOKEN": (200, {})})
    assert _run(KEYS, fine_grained, "--only", "ghcr") == 1
    assert _run(KEYS, FakeHttp(), "--only", "ghcr") == 0


def test_a_mis_shaped_key_is_reported_fail_and_never_sent(capsys):
    http = FakeHttp()
    truncated = KEYS["HF_TOKEN"][1:]
    assert _run({**KEYS, "HF_TOKEN": truncated}, http, "--only", "huggingface") == 1
    assert http.calls == []
    assert "shape" in capsys.readouterr().out


def test_auth_header_shapes_follow_the_probe_config():
    http = FakeHttp()
    _run(KEYS, http)
    sent = {label: headers for _, headers, label in http.calls}
    assert sent["ANTHROPIC_API_KEY"]["x-api-key"] == KEYS["ANTHROPIC_API_KEY"]
    assert sent["GEMINI_API_KEY"]["x-goog-api-key"] == KEYS["GEMINI_API_KEY"]
    assert sent["OPENAI_API_KEY"]["Authorization"] == "Bearer " + KEYS["OPENAI_API_KEY"]
    assert all(url.startswith("https://") for url, _, _ in http.calls)
    assert not any("key=" in url for url, _, _ in http.calls), "no credential in a URL"


@pytest.mark.parametrize("as_json", [False, True])
def test_no_key_appears_in_any_output(capsys, as_json):
    http = FakeHttp(by_label={"OPENAI_API_KEY": (401, {})})
    _run(KEYS, http, *(["--json"] if as_json else []))
    captured = capsys.readouterr()
    for value in KEYS.values():
        assert value not in captured.out and value not in captured.err


def test_json_output_is_one_parseable_document(capsys):
    _run(KEYS, FakeHttp(), "--json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "PASS"
    assert {c["verdict"] for c in payload["checks"]} == {"ok"}


def test_unknown_only_name_exits_3():
    assert _run(KEYS, FakeHttp(), "--only", "no-such-provider") == 3


# ── Config discipline: names an env var, never holds a key ──────────────────


@pytest.mark.parametrize(
    "body",
    [
        # a key pasted into the file: unknown field
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    api_key: sk-FAKE0000\n"
        "    url: https://example.invalid/\n",
        # the auth header set statically
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    url: https://example.invalid/\n"
        "    headers: {Authorization: Bearer sk-FAKE0000}\n",
        # ANY auth-bearing static header, not only the probe's own auth_header
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    url: https://example.invalid/\n"
        "    auth_header: x-api-key\n    auth_scheme: ''\n    headers: {Authorization: Bearer sk-FAKE0000}\n",
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    url: https://example.invalid/\n"
        "    headers: {X-Goog-Api-Key: AIzaFAKE0000}\n",
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    url: https://example.invalid/\n"
        "    headers: {X-Session-Token: FAKE0000}\n",
        # names a deny-list missed: the allowlist refuses anything unlisted
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    url: https://example.invalid/\n"
        "    headers: {X-Access: FAKE0000}\n",
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    url: https://example.invalid/\n"
        "    headers: {Bearer: FAKE0000}\n",
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    url: https://example.invalid/\n"
        "    headers: {X-Session: FAKE0000}\n",
        # a reason-gated status that is also unconditional
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    url: https://example.invalid/\n"
        "    auth_failure_reasons: {401: [API_KEY_INVALID]}\n",
        # plaintext transport
        "version: 1\nprobes:\n  - name: x\n    api_key_env: X\n    url: http://example.invalid/\n",
        # api_key_env that is not an identifier (a value, not a name)
        "version: 1\nprobes:\n  - name: x\n    api_key_env: sk-FAKE0000\n    url: https://example.invalid/\n",
        "version: 1\nprobes: [\n",
    ],
)
def test_a_malformed_probes_file_exits_3(tmp_path, body):
    path = tmp_path / "probes.yaml"
    path.write_text(body)
    http = FakeHttp()
    assert _run(KEYS, http, "--probes", str(path)) == 3
    assert http.calls == []


def test_every_probe_label_has_a_shape_rule():
    rules = load_rules()
    missing = [p.api_key_env for p in v.load_probes().probes if p.api_key_env not in rules]
    assert not missing


def test_no_static_header_value_looks_like_a_credential():
    prefixes = [p for rule in load_rules().values() for p in rule.prefixes]
    for probe in v.load_probes().probes:
        for value in probe.headers.values():
            assert not any(value.startswith(p) for p in prefixes), probe.name


def test_redirects_are_never_followed():
    """urllib would re-send the credential header to wherever a 3xx points."""
    assert v._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://elsewhere") is None


def test_urllib_get_returns_statuses_and_does_not_follow_a_redirect():
    """The real transport, against a loopback stub: 3xx and 401 are answers, not follows."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            hits.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/landed")
            elif self.path == "/denied":
                self.send_response(401)
            elif self.path == "/bad-key":
                body = json.dumps({"error": {
                    "status": "INVALID_ARGUMENT", "message": "echoes FAKE0000",
                    "details": [{"reason": "API_KEY_INVALID"}],
                }}).encode()
                self.send_response(400)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            else:
                self.send_response(200)
                self.send_header("X-OAuth-Scopes", "read:packages")
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert v.urllib_get(base + "/redirect", {}, 5).status == 302
        assert v.urllib_get(base + "/denied", {}, 5).status == 401
        bad = v.urllib_get(base + "/bad-key", {}, 5)
        assert bad.status == 400 and bad.reasons == ("INVALID_ARGUMENT", "API_KEY_INVALID")
        ok = v.urllib_get(base + "/ok", {}, 5)
        assert ok.status == 200 and v._header_value(ok.headers, "x-oauth-scopes") == "read:packages"
    finally:
        server.shutdown()
    assert "/landed" not in hits


def test_every_static_header_in_the_tracked_probes_is_allowlisted():
    """Positive control for the allowlist: the real file loads under it."""
    names = {h.lower() for p in v.load_probes().probes for h in p.headers}
    assert names and names <= v.STATIC_HEADER_ALLOWLIST
