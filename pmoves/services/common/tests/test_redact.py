"""redact_url fails closed, and every inline fallback copy is the same algorithm.

All credentials below are synthetic. Each password is built from ``hunter2``
and/or ``s3cr3t`` -- both on test_no_hardcoded_nats_credentials'
SYNTHETIC_TEST_PASSWORDS allowlist -- or is a base64-style token listed in
``secrets``. Each marker is checked as two overlapping fragments (``hunter`` /
``ter2``, ``s3cr`` / ``cr3t``) so a half-redacted password still fails.
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
# #3244 round-1 control review's corpus; r2_* rows are the round-2 corpus.
CORPUS = [
    ("plain", "nats://alice:hunter2@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("pw_at", "nats://alice:hunter2@s3cr3t@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("pw_colon", "nats://alice:hunter2:s3cr3t@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("pw_slash", "nats://alice:hunter2/s3cr3t@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("pw_pct", "nats://alice:hunter2%40s3cr3t@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("pw_hash", "nats://alice:hunter2#s3cr3t@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("pw_qmark", "nats://alice:hunter2?s3cr3t@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("pw_comma", "nats://alice:hunter2,s3cr3t@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("pw_space", "nats://alice:hunter2 s3cr3t@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("ipv6", "nats://alice:hunter2@[::1]:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("user_only", "nats://hunter2@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("pw_only", "nats://:hunter2@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("tls", "tls://alice:hunter2@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("postgres", "postgres://alice:hunter2@db:5432/x", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("postgresql", "postgresql+asyncpg://alice:hunter2@db:5432/x", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("redis", "redis://:hunter2@redis:6379/0", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("rediss", "rediss://default:hunter2@redis:6380", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("amqp", "amqp://alice:hunter2@rabbit:5672/vh", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("query", "postgres://db/x?user=a&password=hunter2", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("bad_port", "nats://alice:hunter2@nats:notaport", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("no_scheme", "alice:hunter2@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("list", "nats://a:hunter2@h1:4222,nats://b:hunter2@h2:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("list_space", "nats://a:hunter2@h1:4222, nats://b:hunter2@h2:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("uppercase", "NATS://alice:hunter2@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("embedded", "connect failed for nats://alice:hunter2@nats:4222 (timeout)", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("none", None, []),
    # Standard-base64 generated passwords: '/', '+', '=' unencoded.
    ("b64_slash", "nats://svc:U1lOVEg/c2VjcmV0+Zm9v==@nats:4222", ["U1lOVEg", "c2VjcmV0", "Zm9v"]),
    ("b64_pg", "postgresql://svc:QUJD/REVG+R0g=@db:5432/app", ["QUJD", "REVG", "R0g"]),
    ("b64_list", "nats://a:QUJD/REVG@h1:4222,nats://b:R0hJ/SktM@h2:4222", ["QUJD", "REVG", "R0hJ", "SktM"]),
    ("b64_mixed", "nats://svc:ab/cd#ef?gh,ij kl@nats:4222", ["ab/", "cd#", "ef?", "gh,", "ij kl"]),
    ("scheme_in_pw", "nats://alice:pw://hunter2@nats:4222", ["hunter", "ter2", "pw:"]),
    ("token_param", "https://api.example/x?token=hunter2&page=2", ["hunter", "ter2", "s3cr", "cr3t"]),
    # Round-3 review (pullrequestreview-5384822500): '@' then a later '://' inside
    # the password, and the bare Google/YouTube ?key= API-key parameter.
    ("r3_at_then_scheme", "nats://alice:hunter2@s3cr3t://x@nats:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("r3_at_then_scheme_list", "nats://a:hunter2@s3cr3t://x@h1:4222,nats://b:hunter2@h2:4222", ["hunter", "ter2", "s3cr", "cr3t"]),
    ("r3_key_param", "https://www.googleapis.com/youtube/v3/videos?key=hunter2&id=1", ["hunter", "ter2", "s3cr", "cr3t"]),
    # Round-2 control review corpus (pullrequestreview-5382143346), incl. the two
    # fail-open shapes it found: a scheme after ':' or '/' followed by a later
    # scheme, and a password containing a '!http://'-like run.
    ('r2_plain', 'nats://alice:hunter2@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_at', 'nats://alice:hunter2@s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_slash', 'nats://alice:hunter2/s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_hash', 'nats://alice:hunter2#s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_q', 'nats://alice:hunter2?s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_comma', 'nats://alice:hunter2,s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_colon', 'nats://alice:hunter2:s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_pct', 'nats://alice:hunter2%40s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_ipv6', 'nats://alice:hunter2@[::1]:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_nl', 'nats://alice:hunter2\ns3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_scheme_plain', 'nats://alice:hunter2http://s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_scheme_bang', 'nats://alice:hunter2!http://s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_scheme_us', 'nats://alice:hunter2_x://s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_pw_scheme_eq', 'nats://alice:hunter2=a://s3cr3t@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_midsentence', 'error: connect to nats://alice:hunter2@nats:4222 failed, retry', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_mid_email', 'connect nats://a:hunter2@h failed; mail ops@example.com', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_colon_prefix_then_scheme', 'primary:nats://a:hunter2@h1 backup=nats://b:pw@h2', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_slash_prefix_then_scheme', 'cfg/nats://a:hunter2@h1 nats://b:pw@h2', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_alnum_prefix_then_scheme', 'URLnats://a:hunter2@h1 nats://b:pw@h2', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_colon_prefix_only', 'url:nats://a:hunter2@h1', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_dict_repr', "{'url': 'nats://a:hunter2@h1', 'db': 'postgres://u:hunter2@db/x'}", ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_json', '{"url":"nats://a:hunter2@h1"}', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_list', 'nats://a:hunter2@h1:4222,nats://b:hunter2@h2:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_query_pw', 'postgres://db/x?user=a&password=hunter2', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_query_tok_hash', 'https://h/x#access_token=hunter2', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_query_sslpassword', 'postgres://db/x?sslpassword=hunter2', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_query_apikey_upper', 'https://h/x?API-KEY=hunter2', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_query_auth', 'https://h/x?auth=hunter2', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_no_scheme', 'alice:hunter2@nats:4222', ['hunter', 'ter2', 's3cr', 'cr3t']),
    ('r2_no_scheme_two', 'a:hunter2@h1 b:hunter2@h2', ['hunter', 'ter2', 's3cr', 'cr3t']),
]

CLEAN = [
    "https://hooks.example/api/webhooks/123/abc",  # path secrets are out of scope (docstring)
    "connect to nats://nats:4222 failed, retry",
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
