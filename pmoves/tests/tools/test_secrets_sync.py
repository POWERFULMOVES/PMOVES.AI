"""Regression tests for pmoves.tools.secrets_sync env-file serialization.

Guards the fix for the multi-line-value corruption that broke ``env.tier-agent``:
an OpenSSH private key (``HOSTINGER_SSH_PRIVATE_KEY``) was written into a line-based
env file, so its continuation lines re-parsed as bogus variables and docker compose's
strict env-file parser failed with ``unexpected character ... in variable name``.

Docker env-files are strictly one ``VAR=VAL`` per line — multi-line values are
unsupported even when quoted. Such secrets must use the ``*_FILE`` convention or
Docker ``secrets:`` instead.
Refs: https://docs.docker.com/reference/compose-file/services/#env_file
"""

from __future__ import annotations

from pmoves.tools import secrets_sync

PEM = (
    "-----BEGIN OPENSSH PRIVATE KEY-----\n"
    "b3BlbnNzaC1rZXktdjEAAAAABG5vbmU\n"
    "t2+5bsdL/CVKMNeC8nyvAAAAEXBtb3Zlcy1mbGVldEB6ODkw==\n"
    "-----END OPENSSH PRIVATE KEY-----"
)


def _parse_strict(text: str) -> dict[str, str]:
    """Parse like a strict line-based env-file; fail on any malformed line.

    Mirrors docker compose's parser closely enough to catch leaked continuation
    lines: a non-comment, non-blank line must be ``KEY=VAL`` with KEY a valid
    identifier.
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        assert "=" in s, f"malformed env line (no '='): {s!r}"
        k, v = s.split("=", 1)
        assert k.isidentifier(), f"invalid env key (leaked continuation?): {k!r}"
        out[k] = v
    return out


def test_drop_multiline_filters_newline_values():
    safe = secrets_sync._drop_multiline(
        "env.tier-agent",
        {"GOOD": "value", "HOSTINGER_SSH_PRIVATE_KEY": PEM, "CRLF": "a\r\nb"},
    )
    assert safe == {"GOOD": "value"}


def test_full_regen_skips_multiline_and_stays_parseable(tmp_path, monkeypatch):
    monkeypatch.setattr(secrets_sync, "PROJECT_ROOT", tmp_path)
    secrets_sync.write_env_files(
        {"env.tier-agent": {"GOOD": "v", "HOSTINGER_SSH_PRIVATE_KEY": PEM}}
    )
    parsed = _parse_strict((tmp_path / "env.tier-agent").read_text())
    assert parsed["GOOD"] == "v"
    assert "HOSTINGER_SSH_PRIVATE_KEY" not in parsed


def test_merge_ignores_corrupt_existing_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(secrets_sync, "PROJECT_ROOT", tmp_path)
    # Simulate an already-corrupt file: a prior multi-line value left bogus lines
    # (one base64 chunk with no '=', one with '+'/'/' that splits to a non-identifier).
    target = tmp_path / "env.tier-agent"
    target.write_text(
        "GOOD=keep\n"
        "MIIEvQIBADANBgkqhkiG9w0\n"
        "t2+5bsdL/CVKMNeC8nyv==\n"
    )
    secrets_sync.write_env_files({"env.tier-agent": {"NEW": "x"}}, merge=True)
    parsed = _parse_strict(target.read_text())
    assert parsed["GOOD"] == "keep"
    assert parsed["NEW"] == "x"
    assert "t2" not in parsed  # bogus continuation key must not survive
