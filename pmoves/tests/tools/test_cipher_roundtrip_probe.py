"""Offline tests for the authenticated cipher write->read round-trip probe.

The network seam (`_urlopen`) is replaced by an in-process fake cipher that
enforces the same rules as memory-routes.ts + auth.ts: no bearer -> 401 when the
server holds a token, wrong agentId for the bearer -> 403. Nothing here touches
a live cipher or the node's real env.shared.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "cipher_roundtrip_probe.py"
MAKEFILE = REPO_ROOT / "pmoves" / "Makefile"

spec = importlib.util.spec_from_file_location("cipher_roundtrip_probe", MODULE)
assert spec and spec.loader
rp = importlib.util.module_from_spec(spec)
sys.modules["cipher_roundtrip_probe"] = rp
spec.loader.exec_module(rp)

# Fake credentials only. Neither is, nor resembles, a real token.
BOOT_TOKEN = "test-bootstrap-token-not-real"
MINTED_TOKEN = "cipher_00000000-0000-4000-8000-00000000test"


@pytest.fixture(autouse=True)
def _isolated(tmp_path_factory, monkeypatch):
    """No real env.shared, no inherited identity/token, and no real network."""
    absent = tmp_path_factory.mktemp("no-env") / "env.shared.absent"
    monkeypatch.setenv("PMOVES_ENV_SHARED", str(absent))
    for name in ("CIPHER_API_TOKEN", "PMOVES_RESOLVED_IDENTITY", "PMOVES_NODE_IDENTITY", "CIPHER_PORT"):
        monkeypatch.delenv(name, raising=False)

    def _guard(*_a, **_k):
        raise AssertionError("test reached the real network seam")

    monkeypatch.setattr(rp, "_urlopen", _guard)


class _Resp:
    def __init__(self, status: int, body=None):
        self.status = status
        self._raw = b"" if body is None else json.dumps(body).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeCipher:
    """Just enough of memory-routes.ts to exercise the probe."""

    def __init__(self, token_agent: dict | None = None, embed: bool = True,
                 score: bool = True, corrupt_read: bool = False, search_hides: bool = False):
        # bearer -> agent it resolves to; None means the server enforces nothing
        self.token_agent = token_agent
        self.embed, self.score = embed, score
        self.corrupt_read, self.search_hides = corrupt_read, search_hides
        self.store: dict = {}
        self.calls: list = []
        self.auth_headers: list = []

    def _err(self, url, code, message):
        body = io.BytesIO(json.dumps({"error": message}).encode("utf-8"))
        return urllib.error.HTTPError(url, code, message, {}, body)

    def __call__(self, req, timeout):
        url = req.full_url
        parsed = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        method = req.get_method()
        self.calls.append((method, parsed.path))
        auth = req.get_header("Authorization")
        self.auth_headers.append(auth)

        auth_agent = None
        if self.token_agent is not None:
            bearer = auth[len("Bearer "):] if auth and auth.startswith("Bearer ") else None
            if bearer not in self.token_agent:
                raise self._err(url, 401, "Unauthorized")
            auth_agent = self.token_agent[bearer]

        def check(agent):
            if auth_agent and agent != auth_agent:
                raise self._err(url, 403, f"Forbidden: token belongs to agent '{auth_agent}', "
                                          f"but request specified '{agent}'")

        if method == "POST" and parsed.path == "/api/memory":
            body = json.loads(req.data.decode("utf-8"))
            check(body["agentId"])
            mid = f"m{len(self.store) + 1}"
            self.store[mid] = body
            return _Resp(201, {"agentId": body["agentId"], "id": mid,
                               "embedding_id": mid if self.embed else None})
        if method == "GET" and parsed.path == "/api/memory/search":
            check(query.get("agentId"))
            results = []
            for mid, rec in self.store.items():
                if self.search_hides or rec["agentId"] != query.get("agentId"):
                    continue
                hit = {"id": mid, "content": rec["content"], "agentId": rec["agentId"]}
                if self.score:
                    hit["score"] = 0.99
                results.append(hit)
            return _Resp(200, {"results": results})
        if method == "GET" and parsed.path.startswith("/api/memory/"):
            mid = parsed.path.rsplit("/", 1)[1]
            if mid not in self.store:
                raise self._err(url, 404, "Memory not found")
            content = "tampered" if self.corrupt_read else self.store[mid]["content"]
            return _Resp(200, {"id": mid, "content": content})
        if method == "DELETE" and parsed.path.startswith("/api/memory/"):
            check(query.get("agentId"))
            self.store.pop(parsed.path.rsplit("/", 1)[1], None)
            return _Resp(204)
        raise self._err(url, 404, "no route")


def _run(monkeypatch, fake, argv, capsys):
    monkeypatch.setattr(rp, "_urlopen", fake)
    rc = rp.main(argv)
    out = capsys.readouterr()
    return rc, out


def test_bootstrap_bearer_round_trip_is_authenticated_and_writes_as_bootstrap(monkeypatch, capsys):
    monkeypatch.setenv("CIPHER_API_TOKEN", BOOT_TOKEN)
    fake = FakeCipher(token_agent={BOOT_TOKEN: "bootstrap"})
    rc, out = _run(monkeypatch, fake, ["--json"], capsys)
    row = json.loads(out.out)
    assert rc == 0, out
    assert row["verdict"] == "ok"
    assert row["agent"] == "bootstrap"
    assert all(h == f"Bearer {BOOT_TOKEN}" for h in fake.auth_headers)
    assert [c[0] for c in fake.calls] == ["POST", "GET", "GET", "DELETE"]
    assert row["cleaned_up"] is True and fake.store == {}


def test_the_credential_never_reaches_output(monkeypatch, capsys):
    monkeypatch.setenv("CIPHER_API_TOKEN", BOOT_TOKEN)
    for argv in (["--json"], []):
        _, out = _run(monkeypatch, FakeCipher(token_agent={BOOT_TOKEN: "bootstrap"}), argv, capsys)
        assert BOOT_TOKEN not in out.out + out.err
    # and not on the failure path either
    _, out = _run(monkeypatch, FakeCipher(token_agent={"other": "bootstrap"}), ["--json"], capsys)
    assert BOOT_TOKEN not in out.out + out.err


def test_minted_bearer_writes_as_the_session_identity(monkeypatch, capsys):
    monkeypatch.setenv("CIPHER_API_TOKEN", MINTED_TOKEN)
    monkeypatch.setenv("PMOVES_RESOLVED_IDENTITY", "z890-claude")
    fake = FakeCipher(token_agent={MINTED_TOKEN: "z890-claude"})
    rc, out = _run(monkeypatch, fake, ["--json"], capsys)
    assert rc == 0, out
    assert json.loads(out.out)["agent"] == "z890-claude"


def test_minted_bearer_without_identity_is_unmeasured_not_a_guess(monkeypatch, capsys):
    monkeypatch.setenv("CIPHER_API_TOKEN", MINTED_TOKEN)
    fake = FakeCipher(token_agent={MINTED_TOKEN: "z890-claude"})
    rc, out = _run(monkeypatch, fake, ["--json"], capsys)
    assert rc == 3
    assert json.loads(out.out)["verdict"] == "no_identity"
    assert fake.calls == []


def test_wrong_identity_is_a_403_finding_with_the_servers_reason(monkeypatch, capsys):
    monkeypatch.setenv("CIPHER_API_TOKEN", BOOT_TOKEN)
    fake = FakeCipher(token_agent={BOOT_TOKEN: "bootstrap"})
    rc, out = _run(monkeypatch, fake, ["--json", "--agent", "cipher-memory-smoke"], capsys)
    row = json.loads(out.out)
    assert rc == 1
    assert row["verdict"] == "unauthorized" and row["failed_step"] == "write"
    assert "token belongs to agent 'bootstrap'" in row["error"]


def test_missing_bearer_against_an_enforcing_server_is_unauthorized(monkeypatch, capsys):
    fake = FakeCipher(token_agent={BOOT_TOKEN: "bootstrap"})
    rc, out = _run(monkeypatch, fake, ["--json"], capsys)
    assert rc == 1
    assert json.loads(out.out)["verdict"] == "unauthorized"


def test_nothing_listening_is_unmeasured(monkeypatch, capsys):
    def refused(req, timeout):
        raise urllib.error.URLError("connection refused")

    rc, out = _run(monkeypatch, refused, ["--json"], capsys)
    assert rc == 3
    assert json.loads(out.out)["verdict"] == "unreachable"


def test_read_back_must_carry_the_written_content(monkeypatch, capsys):
    rc, out = _run(monkeypatch, FakeCipher(corrupt_read=True), ["--json"], capsys)
    row = json.loads(out.out)
    assert rc == 1 and row["verdict"] == "readback_mismatch"
    assert row["cleaned_up"] is True


def test_a_write_search_cannot_find_is_a_finding(monkeypatch, capsys):
    rc, out = _run(monkeypatch, FakeCipher(search_hides=True), ["--json"], capsys)
    assert rc == 1
    assert json.loads(out.out)["verdict"] == "search_miss"


def test_require_vector_fails_on_the_lexical_fallback_only(monkeypatch, capsys):
    rc, out = _run(monkeypatch, FakeCipher(embed=False, score=False), ["--json"], capsys)
    assert rc == 0, "without --require-vector a lexical round trip still counts"
    rc, out = _run(monkeypatch, FakeCipher(embed=False, score=False),
                   ["--json", "--require-vector"], capsys)
    assert rc == 1
    assert json.loads(out.out)["verdict"] == "vector_path_dead"
    rc, _ = _run(monkeypatch, FakeCipher(), ["--json", "--require-vector"], capsys)
    assert rc == 0


def test_bearer_resolves_from_the_env_file_like_the_session(monkeypatch, tmp_path, capsys):
    env_file = tmp_path / "env.shared"
    env_file.write_text(f"CIPHER_API_TOKEN={BOOT_TOKEN}\n", encoding="utf-8")
    fake = FakeCipher(token_agent={BOOT_TOKEN: "bootstrap"})
    rc, out = _run(monkeypatch, fake, ["--json", "--env-file", str(env_file)], capsys)
    assert rc == 0, out
    assert fake.auth_headers[0] == f"Bearer {BOOT_TOKEN}"


def test_keep_skips_cleanup(monkeypatch, capsys):
    fake = FakeCipher()
    rc, _ = _run(monkeypatch, fake, ["--keep"], capsys)
    assert rc == 0
    assert "DELETE" not in [c[0] for c in fake.calls] and len(fake.store) == 1


def test_cipher_memory_smoke_runs_the_authenticated_probe():
    """The make target used to curl with no bearer and a fixed agentId no token
    resolves to, so under token enforcement it could never pass."""
    text = MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^cipher-memory-smoke:.*?(?=^\S)", text, re.S | re.M)
    assert m, "cipher-memory-smoke target not found"
    recipe = m.group(0)
    assert "tools/cipher_roundtrip_probe.py" in recipe
    assert "--require-vector" in recipe
    assert '"agentId":"cipher-memory-smoke"' not in recipe
