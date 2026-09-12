"""The minted cipher token must reach stdout exactly ONCE, and labelled.

Why this test exists, precisely:

`mint_cipher_token.py` builds the bearer as `token = f"cipher_{token_uuid.hex}"`
and stores that same `token_uuid` in `pmoves_core.cipher_agent_tokens`. There is
no hash column (migration 20260728100000: `token_uuid UUID PRIMARY KEY`), so the
STORED ROW IS THE CREDENTIAL -- anyone holding the row can reconstruct the
bearer.

The insert is sent with `Prefer: return=representation`, so Supabase echoes that
row back, and the script used to `print()` the raw response verbatim. That put a
SECOND copy of the credential on stdout in a form nobody recognises as a secret:
an operator or log scrubber redacting `CIPHER_TOKEN=` removes the labelled copy
and leaves the unlabelled one behind. Two emissions, one of them invisible to
redaction, is worse than one.

These tests pin the invariant, not the wording: whatever the script prints, the
token's uuid may appear at most once, and only on the labelled line.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "scripts" / "mint_cipher_token.py"

spec = importlib.util.spec_from_file_location("mint_cipher_token", MODULE)
assert spec and spec.loader
mint = importlib.util.module_from_spec(spec)
sys.modules["mint_cipher_token"] = mint
spec.loader.exec_module(mint)


class _FakeResponse:
    """Stand-in for the urlopen context manager."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def run_mint(monkeypatch):
    """Run main() with the network stubbed; return (exit_code, stdout, sent_payload)."""

    def _run(argv_extra=None, representation=True, http_error_body=None):
        captured: dict = {}

        def fake_urlopen(req, *a, **kw):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
            if http_error_body is not None:
                # Supabase quotes the offending value back on a constraint error.
                detail = http_error_body.replace(
                    "{TOKEN_UUID}", captured["body"]["token_uuid"]
                ).encode("utf-8")
                raise urllib.error.HTTPError(
                    req.full_url, 409, "Conflict", {}, io.BytesIO(detail)
                )
            row = dict(captured["body"])
            # Supabase echoes the stored row back under return=representation,
            # including columns the client never sent.
            row.update({"created_at": "2026-09-07T20:00:00Z", "revoked_at": None})
            body = json.dumps([row]).encode("utf-8") if representation else b""
            return _FakeResponse(body)

        monkeypatch.setattr(mint.urllib.request, "urlopen", fake_urlopen)
        argv = [
            "mint_cipher_token.py",
            "--agent", "test-agent",
            "--service-key", "svc-key",
            "--rest-url", "http://stub/rest/v1",
        ]
        monkeypatch.setattr(sys, "argv", argv + list(argv_extra or []))

        buf = io.StringIO()
        errbuf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        monkeypatch.setattr(sys, "stderr", errbuf)
        code = mint.main()
        monkeypatch.undo()
        captured["stderr"] = errbuf.getvalue()
        return code, buf.getvalue(), captured

    return _run


def _token_line(stdout: str) -> str:
    lines = [ln for ln in stdout.splitlines() if ln.startswith("CIPHER_TOKEN=")]
    assert len(lines) == 1, f"expected exactly one CIPHER_TOKEN= line, got {lines!r}"
    return lines[0]


def test_token_uuid_appears_exactly_once_in_stdout(run_mint):
    """The credential is emitted once. This is the regression under test."""
    code, out, captured = run_mint()
    assert code == 0, out

    stored_uuid = captured["body"]["token_uuid"]
    hex_form = stored_uuid.replace("-", "")

    # BOTH spellings must be counted, and that is the whole trap. The bearer is
    # cipher_<hex>, but Supabase echoes the row with the uuid DASHED. Counting
    # only the hex form PASSES against the unfixed script -- verified as a
    # negative control -- because the dashed copy is a complete reconstruction
    # of the credential that was sailing straight past the assertion.
    assert out.count(hex_form) == 1, (
        f"token hex appears {out.count(hex_form)}x in stdout; the stored row is "
        f"the bearer, so every occurrence is a copy of the credential:\n{out}"
    )
    assert out.count(stored_uuid) == 0, (
        f"dashed token_uuid leaked into stdout {out.count(stored_uuid)}x -- strip the dashes and it is the bearer:\n{out}"
    )


def test_the_only_occurrence_is_the_labelled_line(run_mint):
    """Redaction keys on the label; an unlabelled copy defeats it."""
    _, out, captured = run_mint()
    hex_form = captured["body"]["token_uuid"].replace("-", "")

    line = _token_line(out)
    assert hex_form in line, "the labelled line must be the one carrying the token"

    # Compare by VALUE, not identity. `ln is not line` reads as equivalent and
    # is not: splitlines() rebuilds each string, so the labelled line failed an
    # identity check against itself and the assertion fired on CORRECT output.
    dashed = captured["body"]["token_uuid"]
    others = [
        ln for ln in out.splitlines()
        if ln != line and (hex_form in ln or dashed in ln)
    ]
    assert others == [], f"token also present on unlabelled line(s): {others!r}"


def test_raw_server_response_is_not_dumped(run_mint):
    """Columns the client never sent are proof the raw row was printed."""
    _, out, _ = run_mint()
    assert "created_at" not in out, f"raw Supabase row echoed to stdout:\n{out}"
    assert "revoked_at" not in out, f"raw Supabase row echoed to stdout:\n{out}"


def test_confirmation_still_reports_agent_and_scopes(run_mint):
    """Silencing the raw row must not cost the operator their confirmation."""
    _, out, _ = run_mint(["--scopes", "memory:read,memory:write"])
    assert "AGENT=test-agent" in out
    assert "SCOPES=memory:read,memory:write" in out


def test_empty_representation_still_succeeds(run_mint):
    """A server that returns no body is not a mint failure."""
    code, out, captured = run_mint(representation=False)
    assert code == 0, out
    assert _token_line(out)


def test_error_body_cannot_leak_the_uuid_to_stderr(run_mint):
    """A 409 quotes the offending VALUE back, and that value is the credential.

    Server-controlled text is not a safe place to assume the token is absent, so
    both spellings are blanked before the detail is surfaced.
    """
    code, out, captured = run_mint(
        http_error_body='{"code":"23505","message":"duplicate key value violates '
                        'unique constraint","detail":"Key (token_uuid)=({TOKEN_UUID}) '
                        'already exists."}'
    )
    assert code == 1
    dashed = captured["body"]["token_uuid"]
    err = captured["stderr"]

    assert dashed not in err, "token_uuid reached stderr verbatim:\n" + err
    assert dashed.replace("-", "") not in err, "hex form reached stderr:\n" + err
    # The operator still needs to know what went wrong.
    assert "23505" in err and "409" in err, err
    assert "<redacted:token_uuid>" in err, err
    # And nothing at all on stdout: the mint failed.
    assert out == "", "failed mint still emitted stdout:\n" + out
