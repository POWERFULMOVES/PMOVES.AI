"""redact_url fails closed, and every inline fallback copy is the same algorithm.

All credentials below are synthetic. Each password carries the marker ``SYNTH``
and/or ``secret`` (or is a base64-style token listed in ``secrets``), and the
assertion is that no such substring survives redaction on either path.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from services.common.redact import redact_url

PMOVES = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PMOVES / "tools"))
import sync_redact_url_copies as sync  # noqa: E402

# (name, input, secrets that must not survive). The first 26 rows are the
# #3244 control review's corpus.
CORPUS = [
    ("plain", "nats://alice:SYNTHsecret@nats:4222", ["SYNTH", "secret"]),
    ("pw_at", "nats://alice:SYNTH@secret@nats:4222", ["SYNTH", "secret"]),
    ("pw_colon", "nats://alice:SYNTH:secret@nats:4222", ["SYNTH", "secret"]),
    ("pw_slash", "nats://alice:SYNTH/secret@nats:4222", ["SYNTH", "secret"]),
    ("pw_pct", "nats://alice:SYNTH%40secret@nats:4222", ["SYNTH", "secret"]),
    ("pw_hash", "nats://alice:SYNTH#secret@nats:4222", ["SYNTH", "secret"]),
    ("pw_qmark", "nats://alice:SYNTH?secret@nats:4222", ["SYNTH", "secret"]),
    ("pw_comma", "nats://alice:SYNTH,secret@nats:4222", ["SYNTH", "secret"]),
    ("pw_space", "nats://alice:SYNTH secret@nats:4222", ["SYNTH", "secret"]),
    ("ipv6", "nats://alice:SYNTHsecret@[::1]:4222", ["SYNTH", "secret"]),
    ("user_only", "nats://SYNTHsecret@nats:4222", ["SYNTH", "secret"]),
    ("pw_only", "nats://:SYNTHsecret@nats:4222", ["SYNTH", "secret"]),
    ("tls", "tls://alice:SYNTHsecret@nats:4222", ["SYNTH", "secret"]),
    ("postgres", "postgres://alice:SYNTHsecret@db:5432/x", ["SYNTH", "secret"]),
    ("postgresql", "postgresql+asyncpg://alice:SYNTHsecret@db:5432/x", ["SYNTH", "secret"]),
    ("redis", "redis://:SYNTHsecret@redis:6379/0", ["SYNTH", "secret"]),
    ("rediss", "rediss://default:SYNTHsecret@redis:6380", ["SYNTH", "secret"]),
    ("amqp", "amqp://alice:SYNTHsecret@rabbit:5672/vh", ["SYNTH", "secret"]),
    ("query", "postgres://db/x?user=a&password=SYNTHsecret", ["SYNTH", "secret"]),
    ("bad_port", "nats://alice:SYNTHsecret@nats:notaport", ["SYNTH", "secret"]),
    ("no_scheme", "alice:SYNTHsecret@nats:4222", ["SYNTH", "secret"]),
    ("list", "nats://a:SYNTHsecret@h1:4222,nats://b:SYNTHsecret@h2:4222", ["SYNTH", "secret"]),
    ("list_space", "nats://a:SYNTHsecret@h1:4222, nats://b:SYNTHsecret@h2:4222", ["SYNTH", "secret"]),
    ("uppercase", "NATS://alice:SYNTHsecret@nats:4222", ["SYNTH", "secret"]),
    ("embedded", "connect failed for nats://alice:SYNTHsecret@nats:4222 (timeout)", ["SYNTH", "secret"]),
    ("none", None, []),
    # Standard-base64 generated passwords: '/', '+', '=' unencoded.
    ("b64_slash", "nats://svc:U1lOVEg/c2VjcmV0+Zm9v==@nats:4222", ["U1lOVEg", "c2VjcmV0", "Zm9v"]),
    ("b64_pg", "postgresql://svc:QUJD/REVG+R0g=@db:5432/app", ["QUJD", "REVG", "R0g"]),
    ("b64_list", "nats://a:QUJD/REVG@h1:4222,nats://b:R0hJ/SktM@h2:4222", ["QUJD", "REVG", "R0hJ", "SktM"]),
    ("b64_mixed", "nats://svc:ab/cd#ef?gh,ij kl@nats:4222", ["ab/", "cd#", "ef?", "gh,", "ij kl"]),
    ("scheme_in_pw", "nats://alice:pw://SYNTH@nats:4222", ["SYNTH", "pw:"]),
    ("token_param", "https://api.example/x?token=SYNTHsecret&page=2", ["SYNTH", "secret"]),
]

CLEAN = [
    "nats://nats:4222",
    "nats://a:4222,nats://b:4222",
    "http://[::1]:8080/x",
    "https://host.example/path?page=2#frag",
    "postgresql://db:5432/app?sslmode=require",
    "",
]


def _exec_copy(fn: ast.FunctionDef):
    namespace = {"_re": __import__("re")}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<copy>", "exec"), namespace)
    return namespace["redact_url"]


COPIES = [(str(path.relative_to(PMOVES)), fn) for path in sync.files_with_copies() for fn in sync.copy_functions(path)]


def test_copies_were_found():
    # A silent zero would make every copy test below vacuous.
    assert len(COPIES) >= 40, len(COPIES)


@pytest.mark.parametrize("name, url, secrets", CORPUS, ids=[c[0] for c in CORPUS])
def test_canonical_fails_closed(name, url, secrets):
    out = redact_url(url)
    for secret in secrets:
        assert secret not in out, name


@pytest.mark.parametrize("url", CLEAN)
def test_canonical_leaves_clean_urls_alone(url):
    assert redact_url(url) == url


@pytest.mark.parametrize("path, fn", COPIES, ids=[c[0] for c in COPIES])
def test_inline_copy_is_ast_identical(path, fn):
    canonical = ast.parse(sync.canonical_function()).body[0]
    assert ast.dump(fn) == ast.dump(canonical), f"{path} drifted; run tools/sync_redact_url_copies.py"


@pytest.mark.parametrize("path, fn", COPIES, ids=[c[0] for c in COPIES])
def test_inline_copy_matches_canonical_on_corpus(path, fn):
    copy = _exec_copy(fn)
    for name, url, secrets in CORPUS:
        out = copy(url)
        assert out == redact_url(url), (path, name)
        for secret in secrets:
            assert secret not in out, (path, name)
    for url in CLEAN:
        assert copy(url) == url, path


def test_sync_check_reports_clean():
    proc = subprocess.run(
        [sys.executable, str(PMOVES / "tools" / "sync_redact_url_copies.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout
