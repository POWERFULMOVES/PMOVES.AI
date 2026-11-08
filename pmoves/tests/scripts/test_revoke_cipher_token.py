"""The revoke half of the cipher token lane.

The constraint these tests exist for: the stored ``token_uuid`` IS the bearer
(mint builds ``cipher_{token_uuid.hex}`` and stores that same uuid; the
migration has no hash column). So a revoke tool that lists or echoes uuids would
reprint every live credential. Every assertion below is about that.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "revoke_cipher_token.py"
_spec = importlib.util.spec_from_file_location("revoke_cipher_token", SCRIPT)
revoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(revoke)

FAKE_UUID = "064cb5d4-3474-4faa-81f8-8c24f50bb776"


class _Resp:
    def __init__(self, body: bytes):
        self._b = body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def run_revoke(monkeypatch, capsys):
    def _run(argv_extra=None, active_rows=1, patch_error=None, leak_rows=False):
        seen: dict = {}

        def fake_urlopen(req, *a, **kw):
            seen.setdefault("urls", []).append(req.full_url)
            seen[req.method] = req.full_url
            # leak_rows: the server hands the bearer back anyway -- under an
            # ALIAS and raw. A tool that only guards its select= would print it.
            row = {"agent_id": "z890-claude"}
            if leak_rows:
                row = {"agent_id": "z890-claude", "tok": FAKE_UUID, "token_uuid": FAKE_UUID}
            if req.method == "GET":
                return _Resp(json.dumps([row] * active_rows).encode())
            if patch_error is not None:
                raise urllib.error.HTTPError(
                    req.full_url, 409, "Conflict", {},
                    io.BytesIO(f'duplicate key "{FAKE_UUID}"'.encode()),
                )
            seen["patch_body"] = json.loads(req.data.decode())
            return _Resp(json.dumps([row] * active_rows).encode())

        monkeypatch.setattr(revoke.urllib.request, "urlopen", fake_urlopen)
        argv = ["revoke", "--agent", "z890-claude", "--service-key", "k"] + (argv_extra or [])
        monkeypatch.setattr(sys, "argv", argv)
        code = revoke.main()
        return code, capsys.readouterr(), seen

    return _run


def test_bearer_never_exits_however_it_arrives(run_revoke):
    """THE invariant, tested at the SINK.

    Two earlier versions of this test guarded the SOURCE and both were too
    narrow, one level apart:

        v1  assert "select=token_uuid" not in src
            defeated by  select=agent_id,token_uuid   (widened list)
        v2  parse select= with [A-Za-z0-9_,*]+ and check each column
            defeated by  select=agent_id,tok:token_uuid   (PostgREST ALIAS --
            ':' is not in the class, so the match stops at 'tok')

    Both were me re-deriving a parser for a grammar PostgREST already specifies:
    select= admits aliases (alias:col), casts (col::type), embedded resources
    (rel(cols)), JSON paths (col->>key) and '*'. Enumerating those is
    reimplementing their parser badly, and the third spelling would have gotten
    through too.

    So test the PROPERTY instead of the syntax: whatever the server returns, and
    by whatever spelling, the bearer must not leave this tool. That is invariant
    to the grammar -- and it is the thing that actually matters, because the
    stored token_uuid IS the credential (mint stores `cipher_{uuid.hex}`'s uuid;
    the migration has no hash column).
    """
    # The server hands back the bearer under an ALIAS -- the exact shape that
    # defeated v2 -- plus the raw column, to cover both spellings at once.
    code, cap, _seen = run_revoke(leak_rows=True)
    assert code == 0, cap.err
    blob = cap.out + cap.err
    assert FAKE_UUID not in blob, "bearer (dashed) exited the tool"
    assert FAKE_UUID.replace("-", "") not in blob, "bearer (hex) exited the tool"


def test_select_list_does_not_ask_for_the_bearer_directly(run_revoke):
    """Defense in depth at the SOURCE, held deliberately narrow.

    This cannot be complete -- see the sink test above for why -- so it asserts
    only the unambiguous cases: a wildcard, or the bare column named in a select
    list. It is a smoke alarm, not the fire door.
    """
    import re

    src = SCRIPT.read_text(encoding="utf-8")
    assert "select=agent_id" in src
    for clause in re.findall(r"select=([^&\"'\s]+)", src):
        assert "*" not in clause, f"wildcard select returns the bearer: select={clause}"


def test_uuid_never_reaches_stdout_even_when_passed_in(run_revoke):
    """--token-uuid is accepted (a known-compromised credential) and must not be
    echoed. It travels in the FILTER, never into the report."""
    code, cap, seen = run_revoke(["--token-uuid", FAKE_UUID])
    assert code == 0, cap.err
    assert FAKE_UUID not in cap.out, "token uuid reached stdout"
    assert FAKE_UUID.replace("-", "") not in cap.out, "hex spelling reached stdout"
    assert FAKE_UUID in seen["PATCH"], "the uuid must still narrow the filter"


def test_patch_error_body_is_not_echoed(run_revoke):
    """PostgREST quotes the offending value back, and here that value is a
    bearer. The mint learned this on a 23505; the revoker must not relearn it."""
    code, cap, _seen = run_revoke(patch_error=True)
    assert code == 1
    assert FAKE_UUID not in cap.out + cap.err, "error body leaked the uuid"


def test_only_targets_active_rows(run_revoke):
    """Re-revoking an already-revoked token would move revoked_at forward and
    destroy when it was actually retired -- the one fact a compromise audit
    needs."""
    code, cap, seen = run_revoke()
    assert code == 0, cap.err
    assert "revoked_at=is.null" in seen["GET"]
    assert "revoked_at=is.null" in seen["PATCH"]


def test_dry_run_changes_nothing(run_revoke):
    code, cap, seen = run_revoke(["--dry-run"], active_rows=3)
    assert code == 0
    assert "WOULD_REVOKE=3" in cap.out
    assert "PATCH" not in seen, "dry-run issued a PATCH"


def test_no_active_tokens_is_success_not_failure(run_revoke):
    """Revoking nothing is a valid outcome: the agent already has no live
    credential. Exiting non-zero would make a safe state look like a fault."""
    code, cap, _seen = run_revoke(active_rows=0)
    assert code == 0
    assert "REVOKED=0" in cap.out


def test_sets_revoked_at_to_a_timestamp(run_revoke):
    code, cap, seen = run_revoke()
    assert code == 0
    assert "revoked_at" in seen["patch_body"]
    assert seen["patch_body"]["revoked_at"].startswith("20"), "expected an ISO timestamp"
