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


EXPECTED_LOCAL = {"nats", "pmoves-nats-1", "localhost", "127.0.0.1", "::1", "host.docker.internal"}


def test_local_host_forms_are_rewritten(tmp_path):
    # Literal set, not d.LOCAL_BROKER_HOSTS: dropping a form must fail here.
    assert EXPECTED_LOCAL <= d.LOCAL_BROKER_HOSTS
    for host in sorted(EXPECTED_LOCAL | {"127.0.0.2", "0:0:0:0:0:0:0:1"}):
        hp = f"[{host}]:4222" if ":" in host else f"{host}:4222"
        p = _env(tmp_path, f"NATS_PASSWORD=new\nNATS_URL={_url('nats', 'old', hp)}\n")
        assert d.derive(p) == "updated", host
        assert parse_env_file(p)["NATS_URL"] == _url("nats", "new", hp)


def test_private_and_tailnet_ips_count_as_remote(tmp_path):
    # The hub sits on a private/tailnet address; only loopback is assumed local.
    for hp in ("10.0.0.5:4222", "172.17.0.1:4222", "100.64.0.9:4222"):
        body = f"NATS_PASSWORD=localpw\nNATS_URL={_url('nats', 'hubpw', hp)}\n"
        p = _env(tmp_path, body)
        assert d.derive(p) == "remote", hp
        assert p.read_text() == body


def test_operator_can_declare_extra_local_hosts(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_LOCAL_BROKER_HOSTS", " other-nats-1 , ")
    p = _env(tmp_path, f"NATS_PASSWORD=new\nNATS_URL={_url('nats', 'old', 'other-nats-1:4222')}\n")
    assert d.derive(p) == "updated"
    assert parse_env_file(p)["NATS_URL"] == _url("nats", "new", "other-nats-1:4222")


def _tiers(tmp_path: Path, shared: str, tiers: dict[str, str]) -> Path:
    p = _env(tmp_path, shared)
    for name, body in tiers.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    return p


def test_check_reports_stale_tier_and_ignores_non_tier_files(tmp_path):
    fresh, stale = _url("nats", "newpw"), _url("nats", "oldpw")
    p = _tiers(
        tmp_path,
        f"NATS_PASSWORD=newpw\nNATS_URL={fresh}\n",
        {
            "env.tier-agent": f"NATS_URL={fresh}\nNATS_PASSWORD=newpw\n",
            "env.tier-ui": f"NATS_URL={stale}\n",
            "env.tier-data": "OTHER=1\n",  # declares no NATS key
            "env.tier-ui.example": f"NATS_URL={stale}\n",
            "env.tier-supabase.urlencoded": f"NATS_URL={stale}\n",
        },
    )
    rows = {(k, t.name): status for k, t, status in d.tier_status(p)}
    assert rows == {
        ("NATS_URL", "env.tier-agent"): "match",
        ("NATS_PASSWORD", "env.tier-agent"): "match",
        ("NATS_URL", "env.tier-ui"): "MISMATCH",
    }


def test_promote_fixes_declared_keys_only_and_never_prints_values(tmp_path, capsys):
    fresh, stale = _url("nats", "newpw"), _url("nats", "oldpw")
    p = _tiers(
        tmp_path,
        f"NATS_USER=nats\nNATS_PASSWORD=newpw\nNATS_URL={fresh}\n",
        {
            "env.tier-ui": f"# keep\nNATS_URL={stale}\nUI=1\n",
            "env.tier-data": "OTHER=1\n",
        },
    )
    assert d.main(["--env-file", str(p), "--promote"]) == 0
    ui = tmp_path / "env.tier-ui"
    assert ui.read_text() == f"# keep\nNATS_URL={fresh}\nUI=1\n"  # only the stale line moved
    assert (tmp_path / "env.tier-data").read_text() == "OTHER=1\n"  # never gains a key
    assert d.main(["--env-file", str(p), "--check"]) == 0
    out = capsys.readouterr().out
    assert "newpw" not in out and "oldpw" not in out
    assert "NATS_URL -> env.tier-ui" in out


def test_check_exits_nonzero_on_mismatch(tmp_path):
    p = _tiers(
        tmp_path,
        f"NATS_PASSWORD=newpw\nNATS_URL={_url('nats', 'newpw')}\n",
        {"env.tier-ui": "NATS_PASSWORD=oldpw\n"},
    )
    assert d.main(["--env-file", str(p), "--check"]) == 1


def test_tier_value_with_no_shared_source_fails_check(tmp_path, capsys):
    # env.shared has no NATS_URL, but a tier still sets one: that tier value wins
    # in compose and nothing can correct it, so --check must not pass quietly.
    p = _tiers(tmp_path, "NATS_PASSWORD=newpw\n", {"env.tier-ui": f"NATS_URL={_url('nats', 'oldpw')}\n"})
    assert d.main(["--env-file", str(p), "--check"]) == 1
    out = capsys.readouterr().out
    assert "NATS_URL env.tier-ui UNSOURCED" in out and "oldpw" not in out
    assert d.promote(p) == []  # nothing to copy from
