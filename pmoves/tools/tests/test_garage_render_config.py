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

# Mode and owner semantics are POSIX; Garage itself runs only in a Linux container.
pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX file modes and uids")

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
    with pytest.raises(ValueError, match="NOT_A_KNOWN_VAR"):
        grc.render("x = \"${NOT_A_KNOWN_VAR}\"", tier="1", ip=SELF, peers=[])


def test_unfilled_placeholder_through_the_cli_is_a_finding(tmp_path):
    tmpl = tmp_path / "t.tmpl"
    tmpl.write_text("x = \"${NOT_A_KNOWN_VAR}\"\n")
    rc = grc.main(["render", "--tier", "1", "--tailnet-ip", SELF, "--template", str(tmpl),
                   "--out", str(tmp_path / "o.toml")])
    assert rc == grc.EXIT_FINDINGS
    assert not (tmp_path / "o.toml").exists()


def test_out_of_range_peer_octet_names_the_line():
    with pytest.raises(ValueError, match="peers line 2"):
        grc.parse_peers(f"{PEER_A}\n{'d' * 64}@999.64.0.1:3901\n", SELF)


def _secrets(tmp_path, mode=0o600, skip=()):
    for name in grc.MOUNT_FILES:
        if name in skip:
            continue
        p = tmp_path / name
        p.write_text("x")
        os.chmod(p, mode)
    return tmp_path


def test_secrets_clean(tmp_path):
    assert grc.check_mounts(_secrets(tmp_path), os.getuid()) == []
    assert grc.check_mounts(_secrets(tmp_path, mode=0o400), None) == []


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o660])
def test_secrets_group_or_other_bits_flagged(tmp_path, mode):
    problems = grc.check_mounts(_secrets(tmp_path, mode=mode), None)
    assert len(problems) == len(grc.MOUNT_FILES)
    assert all("Garage refuses to start" in p for p in problems)


def test_secrets_missing_and_wrong_owner(tmp_path):
    d = _secrets(tmp_path, skip=("pmoves_garage_metrics_token",))
    problems = grc.check_mounts(d, os.getuid() + 1)
    assert sum(": missing" in p for p in problems) == 1
    assert sum(": owned by uid" in p for p in problems) == 2


def test_secrets_dir_absent_is_could_not_measure(tmp_path):
    with pytest.raises(grc.Unmeasured):
        grc.check_mounts(tmp_path / "nope", None)
    assert grc.main(["check-secrets", "--dir", str(tmp_path / "nope")]) == grc.EXIT_UNMEASURED


def test_cli_exit_codes(tmp_path):
    out = tmp_path / "garage.toml"
    assert grc.main(["render", "--tier", "2", "--tailnet-ip", SELF, "--out", str(out)]) == grc.EXIT_OK
    assert tomllib.loads(out.read_text())["db_engine"] == "sqlite"
    assert oct(out.stat().st_mode & 0o777) == oct(0o644)
    assert grc.main(["render", "--tier", "1", "--tailnet-ip", "8.8.8.8", "--out", str(out)]) == grc.EXIT_FINDINGS
    # A missing --peers file is bad input (1), not could-not-measure (3).
    assert grc.main(["render", "--tier", "1", "--tailnet-ip", SELF, "--peers", str(tmp_path / "none"),
                     "--out", str(out)]) == grc.EXIT_FINDINGS
    sdir = tmp_path / "s"
    sdir.mkdir()
    assert grc.main(["check-secrets", "--dir", str(_secrets(sdir))]) == grc.EXIT_OK
    os.chmod(sdir / next(iter(grc.MOUNT_FILES)), 0o644)
    assert grc.main(["check-secrets", "--dir", str(sdir)]) == grc.EXIT_FINDINGS


# Synthetic values of the documented shapes (openssl rand -hex 32 / -base64 32).
GOOD = {
    "GARAGE_RPC_SECRET": "0123456789abcdef" * 4,
    "GARAGE_ADMIN_TOKEN": "A" * 43 + "=",
    "GARAGE_METRICS_TOKEN": "B" * 43 + "=",
}


def _env(tmp_path, values, name="env.tier-data"):
    p = tmp_path / name
    p.write_text("# tier env\nOTHER_KEY=unrelated\n"
                 + "".join(f"{k}={v}\n" for k, v in values.items()))
    return p


def test_materialize_writes_0600_files_that_pass_the_preflight(tmp_path):
    out = tmp_path / "garage"
    assert grc.materialize(_env(tmp_path, GOOD), out) == []
    for name, label in grc.MOUNT_FILES.items():
        f = out / name
        assert f.read_text() == GOOD[label]
        assert f.stat().st_mode & 0o777 == 0o600
    assert out.stat().st_mode & 0o777 == 0o700
    assert grc.check_mounts(out, os.getuid()) == []
    assert not list(out.glob(".*.tmp"))


def test_materialize_parses_export_and_quotes(tmp_path):
    p = tmp_path / "env"
    p.write_text(f"export GARAGE_RPC_SECRET='{GOOD['GARAGE_RPC_SECRET']}'\n"
                 f'GARAGE_ADMIN_TOKEN="{GOOD["GARAGE_ADMIN_TOKEN"]}"\n'
                 f"GARAGE_METRICS_TOKEN={GOOD['GARAGE_METRICS_TOKEN']}\n")
    out = tmp_path / "g"
    assert grc.materialize(p, out) == []
    assert (out / "pmoves_garage_rpc_secret").read_text() == GOOD["GARAGE_RPC_SECRET"]


@pytest.mark.parametrize("label,bad", [
    ("GARAGE_RPC_SECRET", "0123456789abcdef" * 4 + "00"),   # too long
    ("GARAGE_RPC_SECRET", "zz" + "0" * 62),                  # not hex
    ("GARAGE_RPC_SECRET", "2" * 62),                         # truncated (the E2B shape)
    ("GARAGE_ADMIN_TOKEN", "A" * 42),                        # truncated
    ("GARAGE_METRICS_TOKEN", ""),                            # empty
])
def test_materialize_refuses_bad_shapes_and_writes_nothing(tmp_path, label, bad):
    vals = dict(GOOD, **{label: bad})
    out = tmp_path / "garage"
    problems = grc.materialize(_env(tmp_path, vals), out)
    assert len(problems) == 1 and problems[0].startswith(label)
    assert not out.exists()
    # the message carries a length at most, never the value
    if bad:
        assert bad not in problems[0]


def test_materialize_cli_never_prints_a_value(tmp_path, capsys):
    env = _env(tmp_path, dict(GOOD, GARAGE_ADMIN_TOKEN="Q" * 30))
    assert grc.main(["materialize", "--env-file", str(env), "--dir", str(tmp_path / "g")]) == grc.EXIT_FINDINGS
    out = capsys.readouterr()
    for v in list(GOOD.values()) + ["Q" * 30]:
        assert v not in out.out and v not in out.err
    assert grc.main(["materialize", "--env-file", str(_env(tmp_path, GOOD, "e2")),
                     "--dir", str(tmp_path / "g")]) == grc.EXIT_OK
    out = capsys.readouterr()
    for v in GOOD.values():
        assert v not in out.out and v not in out.err


def test_materialize_missing_env_file_is_could_not_measure(tmp_path):
    assert grc.main(["materialize", "--env-file", str(tmp_path / "nope"),
                     "--dir", str(tmp_path / "g")]) == grc.EXIT_UNMEASURED


def test_mount_file_names_are_build_entry_docker_secret_names():
    """The funnel's docker_secret target and the compose secret name must agree."""
    import sys
    sys.path.insert(0, str(TOOL.parent))
    try:
        from chit_manifest_register import REGISTRY, build_entry
    finally:
        sys.path.pop(0)
    for name, label in grc.MOUNT_FILES.items():
        assert label in REGISTRY, label
        targets = build_entry(label, REGISTRY[label])["targets"]
        assert {"docker_secret": name} in targets
