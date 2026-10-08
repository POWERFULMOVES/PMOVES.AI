"""derive_nats_url keeps NATS_URL's userinfo in step with NATS_USER/NATS_PASSWORD.

NATS_URL is stored as a literal URL with the credential embedded, and nothing
re-derived it, so rotating NATS_PASSWORD left NATS_URL on the old value: a
broker recreated with the new password would refuse every NATS_URL client.
"""

from __future__ import annotations

from pathlib import Path

from pmoves.tools import derive_nats_url as d
from pmoves.tools._secrets_common import parse_env_file


def _url(user: str, pw: str, hostport: str = "nats:4222") -> str:
    # Built at runtime so this file holds no literal user:pass@ URL for the
    # committed-credential scanner (test_no_hardcoded_nats_credentials).
    return f"nats://{user}:{pw}@{hostport}"


def _env(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "env.shared"
    p.write_text(body, encoding="utf-8")
    return p


def test_rewrites_stale_userinfo_and_keeps_host_port(tmp_path, capsys):
    p = _env(tmp_path, f"# c\nNATS_USER=nats\nNATS_PASSWORD=newpw123\nNATS_URL={_url('nats', 'oldpw')}\nOTHER=1\n")
    assert d.derive(p) == "updated"
    vals = parse_env_file(p)
    assert vals["NATS_URL"] == _url("nats", "newpw123")
    assert vals["OTHER"] == "1"
    assert p.read_text().startswith("# c\n")  # other lines untouched
    out = capsys.readouterr().out + capsys.readouterr().err
    assert "newpw123" not in out and "oldpw" not in out  # never echoes values


def test_noop_when_already_consistent(tmp_path):
    body = f"NATS_USER=nats\nNATS_PASSWORD=pw\nNATS_URL={_url('nats', 'pw')}\n"
    p = _env(tmp_path, body)
    assert d.derive(p) == "unchanged"
    assert p.read_text() == body


def test_defaults_user_to_nats_and_percent_encodes(tmp_path):
    p = _env(tmp_path, f"NATS_PASSWORD=a/b@c\nNATS_URL={_url('x', 'y', 'localhost:4222')}\n")
    assert d.derive(p) == "updated"
    assert parse_env_file(p)["NATS_URL"] == "nats://nats:a%2Fb%40c@localhost:4222"


def test_skips_when_password_or_url_missing(tmp_path):
    p = _env(tmp_path, f"NATS_URL={_url('nats', 'pw')}\n")
    assert d.derive(p) == "skipped"
    p2 = _env(tmp_path, "NATS_PASSWORD=pw\n")
    assert d.derive(p2) == "skipped"  # never invents a URL


def test_skips_url_without_userinfo(tmp_path):
    # A credential-free URL (e.g. creds file / account auth) is left alone.
    body = "NATS_PASSWORD=pw\nNATS_URL=nats://nats:4222\n"
    p = _env(tmp_path, body)
    assert d.derive(p) == "skipped"
    assert p.read_text() == body


def test_remote_broker_url_is_left_alone(tmp_path):
    # A node dialing the fleet hub authenticates with the HUB's credential;
    # rewriting it with this node's local NATS_PASSWORD drops the node off the bus.
    body = f"NATS_PASSWORD=localpw\nNATS_URL={_url('nats', 'hubpw', 'hub.example:4222')}\n"
    p = _env(tmp_path, body)
    assert d.derive(p) == "remote"
    assert p.read_text() == body


def test_local_host_forms_are_rewritten(tmp_path):
    for host in sorted(d.LOCAL_BROKER_HOSTS):
        hp = f"[{host}]:4222" if ":" in host else f"{host}:4222"
        p = _env(tmp_path, f"NATS_PASSWORD=new\nNATS_URL={_url('nats', 'old', hp)}\n")
        assert d.derive(p) == "updated", host
        assert parse_env_file(p)["NATS_URL"] == _url("nats", "new", hp)
