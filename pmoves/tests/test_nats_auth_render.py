"""nats_auth_render: fail-closed rendering of the NATS dual-credential conf.

Behavioural controls (fail before control where marked):
- an empty NATS_PASSWORD or NATS_PASSWORD_V2 refuses BEFORE writing (control)
- bcrypt hashes are single-quoted in the conf (documented $-token gotcha)
- --drop-old renders without the old user
- output file mode is 0600
"""
from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import nats_auth_render as nar

MONKEYPATCH = pytest.MonkeyPatch


def _set_env(monkeypatch: MONKEYPATCH, **drop: str) -> None:
    base = {
        "NATS_USER": "nats",
        "NATS_PASSWORD": "old-secret",
        "NATS_USER_V2": "nats-v2",
        "NATS_PASSWORD_V2": "new-secret",
    }
    base.update(drop)
    for key, value in base.items():
        monkeypatch.setenv(key, value)
    # the fallback reads NATS_URL; a session-exported one (the documented
    # compose shadowing trap) must not leak into the test
    monkeypatch.delenv("NATS_URL", raising=False)


def test_renders_both_users(tmp_path: Path, monkeypatch: MONKEYPATCH) -> None:
    _set_env(monkeypatch)
    out = tmp_path / "auth.conf"
    nar.render(out, drop_old=False)
    conf = out.read_text()
    assert 'user: "nats"' in conf
    assert 'user: "nats-v2"' in conf
    assert conf.count("password: \"$2b$") == 2
    # plaintext never lands on disk
    assert "old-secret" not in conf
    assert "new-secret" not in conf


def test_empty_password_fails_before_writing(
    tmp_path: Path, monkeypatch: MONKEYPATCH
) -> None:
    _set_env(monkeypatch, NATS_PASSWORD="")
    out = tmp_path / "auth.conf"
    with pytest.raises(SystemExit):
        nar.render(out, drop_old=False)
    assert not out.exists()  # control: the file must not exist


def test_empty_v2_password_fails_before_writing(
    tmp_path: Path, monkeypatch: MONKEYPATCH
) -> None:
    _set_env(monkeypatch, NATS_PASSWORD_V2="")
    out = tmp_path / "auth.conf"
    with pytest.raises(SystemExit):
        nar.render(out, drop_old=False)
    assert not out.exists()


def test_current_credential_falls_back_to_nats_url(
    monkeypatch: MONKEYPATCH,
) -> None:
    monkeypatch.delenv("NATS_PASSWORD", raising=False)
    monkeypatch.setenv("NATS_URL", "nats://bususer:secret@nats:4222")
    user, password = nar._current_credential()
    assert (user, password) == ("bususer", "secret")


def test_no_credential_anywhere_fails(monkeypatch: MONKEYPATCH) -> None:
    monkeypatch.delenv("NATS_PASSWORD", raising=False)
    monkeypatch.delenv("NATS_URL", raising=False)
    with pytest.raises(SystemExit):
        nar._current_credential()


def test_drop_old_evicts_leaked_user_keeps_target(
    tmp_path: Path, monkeypatch: MONKEYPATCH
) -> None:
    _set_env(monkeypatch)
    out = tmp_path / "auth.conf"
    nar.render(out, drop_old=True)
    conf = out.read_text()
    # the FINAL render must carry ONLY the rotation target: the leaked user is
    # the thing being retired (behavioural control for the inversion the review
    # caught: --drop-old once kept the leaked user and evicted the target)
    assert 'user: "nats-v2"' in conf
    assert 'user: "nats"' not in conf
    assert "old-secret" not in conf
    assert conf.count("password: \"$2b$") == 1


def test_final_render_requires_v2_even_with_old_present(
    tmp_path: Path, monkeypatch: MONKEYPATCH
) -> None:
    # a final render must never silently fall back to the leaked credential
    _set_env(monkeypatch, NATS_PASSWORD_V2="")
    out = tmp_path / "auth.conf"
    with pytest.raises(SystemExit):
        nar.render(out, drop_old=True)
    assert not out.exists()


def test_output_mode_is_0600(tmp_path: Path, monkeypatch: MONKEYPATCH) -> None:
    _set_env(monkeypatch)
    out = tmp_path / "auth.conf"
    nar.render(out, drop_old=False)
    mode = stat.S_IMODE(out.stat().st_mode)
    assert mode == 0o600
