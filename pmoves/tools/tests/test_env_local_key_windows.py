# pmoves/tools/tests/test_env_local_key_windows.py
"""env_local_key must work where ``os.fchmod`` / ``os.fchown`` do not exist.

Windows Python has neither. The original call sites sat behind ``except OSError``,
but a missing function raises ``AttributeError``, so ``make env-local-set`` died on
Windows after ``cipher-mint-token`` had already consumed its piped bearer. These
tests strip both functions so Linux CI exercises the Windows path.
"""
import io
import os
import stat

import pytest

from pmoves.tools import env_local_key as elk

SECRET = "cipher_0123456789abcdef0123456789abcdef"


def _run(env_file, audit, *argv, value=None):
    stdin = io.StringIO(value if value is not None else "")
    return elk.main(
        ["--file", str(env_file), "--audit-log", str(audit), *argv], stdin=stdin
    )


@pytest.fixture
def windows_like(monkeypatch):
    """Remove the POSIX-only calls exactly as a Windows interpreter lacks them."""
    monkeypatch.delattr(os, "fchmod", raising=False)
    monkeypatch.delattr(os, "fchown", raising=False)
    assert not hasattr(os, "fchmod") and not hasattr(os, "fchown")


def test_set_new_file_without_fchmod_fchown(tmp_path, windows_like):
    env, audit = tmp_path / ".env.local", tmp_path / "audit.jsonl"
    assert _run(env, audit, "set", "CIPHER_TOKEN_Z890_CLAUDE", value=SECRET + "\n") == 0
    assert f"CIPHER_TOKEN_Z890_CLAUDE={SECRET}" in env.read_text()


def test_set_existing_file_takes_the_owner_branch(tmp_path, windows_like):
    # An existing file makes _commit pass an owner tuple to _atomic_write, which is
    # the path that reached os.fchown.
    env, audit = tmp_path / ".env.local", tmp_path / "audit.jsonl"
    env.write_text("KEEP=1\n")
    assert _run(env, audit, "set", "NEW_KEY", value="v\n") == 0
    text = env.read_text()
    assert "KEEP=1" in text and "NEW_KEY=v" in text


def test_unset_and_has_without_fchmod_fchown(tmp_path, windows_like):
    env, audit = tmp_path / ".env.local", tmp_path / "audit.jsonl"
    env.write_text("A=1\nB=2\n")
    assert _run(env, audit, "unset", "A") == 0
    assert "A=1" not in env.read_text() and "B=2" in env.read_text()
    assert _run(env, audit, "has", "B") == 0


def test_audit_log_never_carries_the_value(tmp_path, windows_like):
    env, audit = tmp_path / ".env.local", tmp_path / "audit.jsonl"
    assert _run(env, audit, "set", "CIPHER_TOKEN_Z890_CLAUDE", value=SECRET + "\n") == 0
    assert SECRET not in audit.read_text()


@pytest.mark.skipif(not hasattr(os, "fchmod"), reason="POSIX mode bits only")
def test_posix_preserves_the_existing_mode(tmp_path):
    env, audit = tmp_path / ".env.local", tmp_path / "audit.jsonl"
    env.write_text("A=1\n")
    env.chmod(0o644)
    assert _run(env, audit, "set", "NEW_KEY", value="v\n") == 0
    assert stat.S_IMODE(env.stat().st_mode) == 0o644
