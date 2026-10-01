# pmoves/tools/tests/test_garage_render_config.py
"""Tests for the Garage node-config renderer and secret-file preflight.

The rendered config must carry every §6.1 gap-table fix, bind nothing outside
the tailnet, and pick db_engine by tier. The secret preflight must flag exactly
what Garage itself refuses at boot (mode & 0o077) without reading the files.
"""
import importlib.util
import os
from pathlib import Path

import pytest
import tomllib

TOOL = Path(__file__).resolve().parents[1] / "garage_render_config.py"
spec = importlib.util.spec_from_file_location("garage_render_config", TOOL)
grc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grc)

SELF = "100.64.0.10"
PEER_A = "a" * 64 + "@100.64.0.11:3901"
PEER_B = "b" * 64 + "@100.64.0.12:3901"


def rendered(tier="1", peers=()):
    text = grc.render(grc.TEMPLATE.read_text(), tier=tier, ip=SELF, peers=list(peers))
    return text, tomllib.loads(text)


def test_template_has_every_gap_table_fix():
    _, cfg = rendered()
    assert cfg["replication_factor"] == 3
    assert cfg["consistency_mode"] == "consistent"
    assert cfg["compression_level"] == "none"
    assert cfg["admin"]["metrics_require_token"] is True
    assert cfg["s3_api"]["s3_region"] == "us-east-1"
    assert "s3_web" not in cfg
    assert "allow_world_readable_secrets" not in cfg
    assert cfg["metadata_snapshots_dir"] != cfg["data_dir"]
    assert not cfg["metadata_snapshots_dir"].startswith(cfg["data_dir"] + "/")
    # secrets only by file, never inline
    for k in ("rpc_secret", "admin_token", "metrics_token"):
        assert k not in cfg and k not in cfg["admin"]
    assert cfg["rpc_secret_file"] == "/run/secrets/pmoves_garage_rpc_secret"
    assert cfg["admin"]["admin_token_file"] == "/run/secrets/pmoves_garage_admin_token"
    assert cfg["admin"]["metrics_token_file"] == "/run/secrets/pmoves_garage_metrics_token"


def test_every_listener_is_on_the_tailnet_address():
    _, cfg = rendered()
    for addr in (cfg["rpc_bind_addr"], cfg["rpc_public_addr"],
                 cfg["s3_api"]["api_bind_addr"], cfg["admin"]["api_bind_addr"]):
        assert addr.startswith(SELF + ":"), addr
    assert {a.rsplit(":", 1)[1] for a in (cfg["rpc_bind_addr"], cfg["s3_api"]["api_bind_addr"],
                                          cfg["admin"]["api_bind_addr"])} == {"3900", "3901", "3903"}


@pytest.mark.parametrize("tier,engine", [("1", "lmdb"), ("2", "sqlite")])
def test_db_engine_by_tier(tier, engine):
    _, cfg = rendered(tier=tier)
    assert cfg["db_engine"] == engine


def test_bootstrap_peers_render_and_exclude_self():
    peers = grc.parse_peers(f"# first cut\n{PEER_A}\n\n{'c' * 64}@{SELF}:3901\n{PEER_B}\n{PEER_A}\n", SELF)
    assert peers == [PEER_A, PEER_B]
    _, cfg = rendered(peers=peers)
    assert cfg["bootstrap_peers"] == [PEER_A, PEER_B]
    _, cfg = rendered(peers=[])
    assert cfg["bootstrap_peers"] == []


@pytest.mark.parametrize("line", [
    "a" * 63 + "@100.64.0.11:3901",          # short id
    "a" * 64 + "@100.64.0.11:3900",          # wrong port
    "a" * 64 + "@8.8.8.8:3901",              # off-tailnet
    "a" * 64 + "@kvm2:3901",                 # MagicDNS does not resolve in the bridge
])
def test_bad_peer_lines_are_rejected(line):
    with pytest.raises(ValueError):
        grc.parse_peers(line, SELF)


@pytest.mark.parametrize("ip", ["8.8.8.8", "10.0.0.5", "0.0.0.0", "fd7a:115c:a1e0::1", "kvm2"])
def test_non_tailnet_bind_address_is_refused(ip):
    with pytest.raises(ValueError):
        grc.tailnet_ip(ip)


def test_unfilled_placeholder_is_an_error():
    with pytest.raises(KeyError):
        grc.render("x = \"${NOT_A_KNOWN_VAR}\"", tier="1", ip=SELF, peers=[])


def _secrets(tmp_path, mode=0o600, skip=()):
    for name in grc.SECRET_FILES:
        if name in skip:
            continue
        p = tmp_path / name
        p.write_text("x")
        os.chmod(p, mode)
    return tmp_path


def test_secrets_clean(tmp_path):
    assert grc.check_secrets(_secrets(tmp_path), os.getuid()) == []
    assert grc.check_secrets(_secrets(tmp_path, mode=0o400), None) == []


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o660])
def test_secrets_group_or_other_bits_flagged(tmp_path, mode):
    problems = grc.check_secrets(_secrets(tmp_path, mode=mode), None)
    assert len(problems) == len(grc.SECRET_FILES)
    assert all("Garage refuses to start" in p for p in problems)


def test_secrets_missing_and_wrong_owner(tmp_path):
    d = _secrets(tmp_path, skip=("pmoves_garage_metrics_token",))
    problems = grc.check_secrets(d, os.getuid() + 1)
    assert sum(": missing" in p for p in problems) == 1
    assert sum(": owned by uid" in p for p in problems) == 2


def test_secrets_dir_absent_is_could_not_measure(tmp_path):
    with pytest.raises(grc.Unmeasured):
        grc.check_secrets(tmp_path / "nope", None)
    assert grc.main(["check-secrets", "--dir", str(tmp_path / "nope")]) == grc.EXIT_UNMEASURED


def test_cli_exit_codes(tmp_path):
    out = tmp_path / "garage.toml"
    assert grc.main(["render", "--tier", "2", "--tailnet-ip", SELF, "--out", str(out)]) == grc.EXIT_OK
    assert tomllib.loads(out.read_text())["db_engine"] == "sqlite"
    assert oct(out.stat().st_mode & 0o777) == oct(0o644)
    assert grc.main(["render", "--tier", "1", "--tailnet-ip", "8.8.8.8", "--out", str(out)]) == grc.EXIT_FINDINGS
    assert grc.main(["render", "--tier", "1", "--tailnet-ip", SELF, "--peers", str(tmp_path / "none"),
                     "--out", str(out)]) == grc.EXIT_UNMEASURED
    sdir = tmp_path / "s"
    sdir.mkdir()
    assert grc.main(["check-secrets", "--dir", str(_secrets(sdir))]) == grc.EXIT_OK
    os.chmod(sdir / grc.SECRET_FILES[0], 0o644)
    assert grc.main(["check-secrets", "--dir", str(sdir)]) == grc.EXIT_FINDINGS
