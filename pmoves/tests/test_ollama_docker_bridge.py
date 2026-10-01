"""Containers must reach the host's loopback-bound Ollama, and only containers.

Measured on Knuckles/B850 2026-10-01 from inside pmoves-cipher-api-1: the
host-gateway name resolved (172.17.0.1) but :11434 was refused, because Ollama
binds 127.0.0.1 by default; a host-native 0.0.0.0 listener (:1234) timed out
from the same container, so UFW default-deny was a second wall behind the
bind. tensorzero.toml routes qwen3_embedding_4b_local to
host.docker.internal:11434, so Cipher had no embedding path at all.

Separately, `make up-tensorzero` bundled pmoves-ollama (an NVIDIA device
reservation) into the gateway's own `up`, so on an AMD node the daemon error
aborted the whole call and left the gateway Created but never started.

These tests run deploy/provision/ollama-docker-bridge.sh against stub
systemctl / ufw / ip / curl that only record argv, and each behavioural check
carries a control: the same check run against a mutated script (or main's
Makefile) must FAIL, so a check that cannot fail is caught here.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "deploy/provision/ollama-docker-bridge.sh"
MAKEFILE = REPO / "pmoves/Makefile"
TZ_TOML = REPO / "pmoves/tensorzero/config/tensorzero.toml"
GW = "172.17.0.1"

STUBS = {
    "systemctl": """#!/usr/bin/env bash
echo "systemctl $*" >> "$STUB_LOG"
if [[ "$1" == "is-active" ]]; then exit "${STUB_ACTIVE_RC:-3}"; fi
exit 0
""",
    "ufw": """#!/usr/bin/env bash
echo "ufw $*" >> "$STUB_LOG"
if [[ "$1" == "status" ]]; then echo "Status: ${STUB_UFW:-active}"; fi
exit 0
""",
    "ip": """#!/usr/bin/env bash
if [[ -n "${STUB_DOCKER0:-}" ]]; then
  echo "5: docker0    inet ${STUB_DOCKER0}/16 brd 172.17.255.255 scope global docker0"
fi
""",
    "curl": """#!/usr/bin/env bash
echo '{"version":"stub"}'
""",
}


@pytest.fixture()
def env(tmp_path):
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    for name, body in STUBS.items():
        p = stub_dir / name
        p.write_text(body)
        p.chmod(0o755)
    proxyd = tmp_path / "systemd-socket-proxyd"
    proxyd.write_text("#!/bin/sh\n")
    proxyd.chmod(0o755)
    systemd_dir = tmp_path / "systemd"
    systemd_dir.mkdir()
    return {
        **{k: v for k, v in os.environ.items() if not k.startswith("OLLAMA_BRIDGE_")},
        "PATH": f"{stub_dir}:{os.environ['PATH']}",
        "STUB_LOG": str(tmp_path / "calls.log"),
        "STUB_DOCKER0": GW,
        "SYSTEMD_DIR": str(systemd_dir),
        "DOCKER_DAEMON_JSON": str(tmp_path / "daemon.json"),  # absent by default
        "SYSTEMD_SOCKET_PROXYD": str(proxyd),
        "PMOVES_PROVISION_ALLOW_NONROOT": "1",
    }


def run(env, *args, script=SCRIPT):
    return subprocess.run(["bash", str(script), *args], env=env, capture_output=True, text=True)


def calls(env) -> list[str]:
    log = Path(env["STUB_LOG"])
    return log.read_text().splitlines() if log.exists() else []


def unit(env, suffix) -> str:
    return (Path(env["SYSTEMD_DIR"]) / f"pmoves-ollama-bridge.{suffix}").read_text()


def check_listens_only_on_gateway(env, script=SCRIPT) -> list[str]:
    """Return defects; empty means the applied socket is gateway-scoped."""
    r = run(env, "--apply", script=script)
    if r.returncode != 0:
        return [f"apply failed rc={r.returncode}: {r.stderr}"]
    sock = unit(env, "socket")
    defects = []
    listens = re.findall(r"^ListenStream=(.+)$", sock, re.M)
    if listens != [f"{GW}:11434"]:
        defects.append(f"ListenStream={listens}")
    if "FreeBind=yes" not in sock:
        defects.append("no FreeBind (socket fails if docker0 is not up yet at boot)")
    if not re.search(r"^ExecStart=\S+ 127\.0\.0\.1:11434$", unit(env, "service"), re.M):
        defects.append("proxy upstream is not Ollama's loopback socket")
    ufw = [c for c in calls(env) if c.startswith("ufw allow")]
    if ufw != [f"ufw allow proto tcp from 172.16.0.0/12 to {GW} port 11434 comment pmoves: containers -> host ollama via pmoves-ollama-bridge"]:
        defects.append(f"ufw rule not scoped to bridge range -> gateway:11434: {ufw}")
    return defects


def test_apply_listens_only_on_the_docker_gateway(env):
    assert check_listens_only_on_gateway(env) == []
    assert "systemctl enable --now pmoves-ollama-bridge.socket" in calls(env)


@pytest.mark.parametrize(
    "mutation",
    [
        ("ListenStream=$BIND_IP:$PORT", "ListenStream=0.0.0.0:$PORT"),
        ("FreeBind=yes", ""),
        ('from "$SOURCE_CIDR" to "$BIND_IP"', 'from any to any'),
        ("ExecStart=$PROXYD $UPSTREAM", "ExecStart=$PROXYD 0.0.0.0:11434"),
    ],
    ids=["wildcard-bind", "no-freebind", "ufw-any", "wrong-upstream"],
)
def test_control_gateway_check_fails_on_mutated_script(env, tmp_path, mutation):
    old, new = mutation
    src = SCRIPT.read_text()
    assert old in src, f"mutation anchor vanished: {old}"
    mutated = tmp_path / "mutated.sh"
    mutated.write_text(src.replace(old, new))
    assert check_listens_only_on_gateway(env, script=mutated) != []


def test_dry_run_writes_nothing_and_calls_nothing(env):
    r = run(env)
    assert r.returncode == 0, r.stderr
    assert f"ListenStream={GW}:11434" in r.stdout
    assert list(Path(env["SYSTEMD_DIR"]).iterdir()) == []
    assert calls(env) == []


def test_apply_is_idempotent(env):
    assert run(env, "--apply").returncode == 0
    first = {p.name: p.stat().st_mtime_ns for p in Path(env["SYSTEMD_DIR"]).iterdir()}
    r = run(env, "--apply")
    assert r.returncode == 0
    assert "units changed: 0" in r.stdout
    assert {p.name: p.stat().st_mtime_ns for p in Path(env["SYSTEMD_DIR"]).iterdir()} == first


def test_changed_listen_address_restarts_an_active_socket(env):
    assert run(env, "--apply").returncode == 0
    env2 = {**env, "STUB_DOCKER0": "172.18.0.1", "STUB_ACTIVE_RC": "0"}
    assert run(env2, "--apply").returncode == 0
    assert "ListenStream=172.18.0.1:11434" in unit(env2, "socket")
    assert "systemctl restart pmoves-ollama-bridge.socket" in calls(env2)


def test_daemon_json_host_gateway_ip_wins_over_docker0(env):
    Path(env["DOCKER_DAEMON_JSON"]).write_text('{"host-gateway-ip": "10.99.0.1"}')
    r = run(env)
    assert "ListenStream=10.99.0.1:11434" in r.stdout


def test_no_bridge_address_is_could_not_measure(env):
    r = run({**env, "STUB_DOCKER0": ""}, "--apply")
    assert r.returncode == 3
    assert list(Path(env["SYSTEMD_DIR"]).iterdir()) == []


@pytest.mark.parametrize("bad", ["0.0.0.0", "127.0.0.1", "::"])
def test_refuses_wildcard_or_loopback_bind(env, bad):
    r = run({**env, "OLLAMA_BRIDGE_BIND_IP": bad}, "--apply")
    assert r.returncode == 2
    assert list(Path(env["SYSTEMD_DIR"]).iterdir()) == []


def test_apply_without_root_mutates_nothing(env):
    e = {k: v for k, v in env.items() if k != "PMOVES_PROVISION_ALLOW_NONROOT"}
    if os.geteuid() == 0:
        pytest.skip("running as root")
    r = run(e, "--apply")
    assert r.returncode == 3
    assert list(Path(env["SYSTEMD_DIR"]).iterdir()) == []
    assert calls(e) == []


def test_inactive_ufw_gets_no_rule(env):
    e = {**env, "STUB_UFW": "inactive"}
    assert run(e, "--apply").returncode == 0
    assert not [c for c in calls(e) if c.startswith("ufw allow")]


def test_rollback_removes_units_and_rule(env):
    assert run(env, "--apply").returncode == 0
    r = run(env, "--rollback")
    assert r.returncode == 0, r.stderr
    assert list(Path(env["SYSTEMD_DIR"]).iterdir()) == []
    assert f"ufw delete allow proto tcp from 172.16.0.0/12 to {GW} port 11434" in calls(env)


def test_status_reports_findings_until_provisioned(env):
    assert run(env, "--status").returncode == 1
    assert run(env, "--apply").returncode == 0
    assert run({**env, "STUB_ACTIVE_RC": "0"}, "--status").returncode == 0


def test_bridge_serves_the_address_tensorzero_routes_embeddings_to():
    toml = TZ_TOML.read_text()
    block = toml.split("[embedding_models.qwen3_embedding_4b_local.providers.ollama_local_embedding]", 1)[1]
    api_base = re.search(r'^api_base = "([^"]+)"', block, re.M).group(1)
    assert api_base == "http://host.docker.internal:11434/v1"


def gateway_up_bundles_nvidia_ollama(makefile_text: str) -> bool:
    """True if up-tensorzero starts the gateway in the SAME `up` as pmoves-ollama."""
    recipe = makefile_text.split("\nup-tensorzero:", 1)[1].split("\n\n", 1)[0]
    return any(
        "tensorzero-gateway" in line and "pmoves-ollama" in line
        for line in recipe.splitlines()
        if not line.lstrip().startswith("@#")
    )


def test_up_tensorzero_does_not_let_pmoves_ollama_abort_the_gateway():
    assert not gateway_up_bundles_nvidia_ollama(MAKEFILE.read_text())


def test_control_main_makefile_bundled_them():
    old = subprocess.run(
        ["git", "-C", str(REPO), "show", "1c39a5f92:pmoves/Makefile"],
        capture_output=True, text=True,
    )
    if old.returncode != 0:
        pytest.skip("baseline commit not available in this clone")
    assert gateway_up_bundles_nvidia_ollama(old.stdout)
