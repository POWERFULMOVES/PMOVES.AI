"""Containers must reach the host's loopback-bound Ollama, and only the consumers.

Measured on Knuckles/B850 2026-10-01 from inside pmoves-cipher-api-1: the
host-gateway name resolved (172.17.0.1) but :11434 was refused, because Ollama
binds 127.0.0.1 by default; a host-native 0.0.0.0 listener (:1234) timed out
from the same container, so UFW default-deny was a second wall behind the
bind. tensorzero.toml routes qwen3_embedding_4b_local to
host.docker.internal:11434, so Cipher had no embedding path at all.

The consumers' packets leave by their default route, the gateway of
pmoves_external (172.30.6.0/24 on br-49971c7b94fe), not by docker0, so the
rule admits that subnet on that bridge only (review of #3245, P2-1/P2-2).
--apply records what it installed and --rollback reads only that record
(P2-3); a changed network deletes the old rule (P2-4).

Separately, `make up-tensorzero` bundled pmoves-ollama (an NVIDIA device
reservation) into the gateway's own `up`, so on an AMD node the daemon error
aborted the whole call and left the gateway Created but never started.

These tests run deploy/provision/ollama-docker-bridge.sh against stub
systemctl / ufw / ip / docker / curl. The ufw stub keeps a rule store and
re-emits rules in ufw's normalized `show added` order (proto last, per
ufw/parser.py get_command), so order-sensitive comparisons would fail here.
Each behavioural check carries a control: the same check run against a mutated
script (or main's Makefile) must FAIL.
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
NET_ID = "49971c7b94fe50975c5676b1f2fab03109b0ae830ee9a3e34b1c76810512b3f8"
BR = "br-49971c7b94fe"
SUBNET = "172.30.6.0/24"
RULE = f"in on {BR} proto tcp from {SUBNET} to {GW} port 11434"
COMMENT = "pmoves: containers -> host ollama via pmoves-ollama-bridge"

STUBS = {
    "systemctl": """#!/usr/bin/env bash
echo "systemctl $*" >> "$STUB_LOG"
if [[ "$1" == "is-active" ]]; then exit "${STUB_ACTIVE_RC:-3}"; fi
exit 0
""",
    # A rule store in ufw's normalized form, so `show added` is realistic.
    "ufw": """#!/usr/bin/env bash
echo "ufw $*" >> "$STUB_LOG"
case "$1" in
  status) echo "Status: ${STUB_UFW:-active}"; exit 0 ;;
  show) echo "Added user rules (see 'ufw status' for running firewall):"
        [[ -f "$STUB_UFW_RULES" ]] && sed 's/^/ufw /' "$STUB_UFW_RULES"; exit 0 ;;
esac
exec python3 - "$STUB_UFW_RULES" "$@" <<'PY'
import shlex, sys
store, args = sys.argv[1], sys.argv[2:]
delete = args[0] == "delete"
if delete:
    args = args[1:]
d = {"action": args[0], "in": "", "from": "any", "to": "any", "port": "any", "proto": "any", "comment": ""}
i = 1
while i < len(args):
    w = args[i]
    if w == "in" and args[i + 1] == "on":
        d["in"] = args[i + 2]; i += 3
    else:
        d[w] = args[i + 1]; i += 2
def norm(d):  # ufw/parser.py get_command order
    s = d["action"]
    if d["in"]:
        s += " in on " + d["in"]
    s += " from %s to %s port %s proto %s" % (d["from"], d["to"], d["port"], d["proto"])
    return s
key = norm(d)
try:
    lines = open(store).read().splitlines()
except FileNotFoundError:
    lines = []
kept = [l for l in lines if l.split(" comment ")[0] != key]
if delete:
    if len(kept) == len(lines):
        print("Could not delete non-existent rule"); sys.exit(0)
    print("Rule deleted")
else:
    if len(kept) != len(lines):
        print("Skipping adding existing rule"); sys.exit(0)
    kept.append(key + (" comment " + shlex.quote(d["comment"]) if d["comment"] else ""))
    print("Rule added")
open(store, "w").write("".join(l + "\\n" for l in kept))
PY
""",
    "ip": """#!/usr/bin/env bash
dev="${@: -1}"
if [[ "$dev" == docker0 && -n "${STUB_DOCKER0:-}" ]]; then
  echo "5: docker0    inet ${STUB_DOCKER0}/16 brd 172.17.255.255 scope global docker0"
elif [[ -n "${STUB_BR_IFACE:-}" && "$dev" == "$STUB_BR_IFACE" && -n "${STUB_BR_ADDR:-}" ]]; then
  echo "9: $dev    inet ${STUB_BR_ADDR} brd 172.30.6.255 scope global $dev"
fi
""",
    "docker": """#!/usr/bin/env bash
echo "docker $*" >> "$STUB_LOG"
if [[ "$1 $2" == "network inspect" && "$3" == "${STUB_NET_NAME:-pmoves_external}" && -n "${STUB_NET:-}" ]]; then
  echo "$STUB_NET"; exit 0
fi
echo "Error: No such network: $3" >&2; exit 1
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
        "STUB_UFW_RULES": str(tmp_path / "ufw.rules"),
        "STUB_DOCKER0": GW,
        "STUB_NET": f"{NET_ID}|<no value>|{SUBNET},",
        "STUB_BR_IFACE": BR,
        "STUB_BR_ADDR": "172.30.6.1/24",
        "SYSTEMD_DIR": str(systemd_dir),
        "DOCKER_DAEMON_JSON": str(tmp_path / "daemon.json"),  # absent by default
        "SYSTEMD_SOCKET_PROXYD": str(proxyd),
        "OLLAMA_BRIDGE_STATE_FILE": str(tmp_path / "state" / "ollama-bridge.state"),
        "PMOVES_PROVISION_ALLOW_NONROOT": "1",
    }


def run(env, *args, script=SCRIPT):
    return subprocess.run(["bash", str(script), *args], env=env, capture_output=True, text=True)


def calls(env) -> list[str]:
    log = Path(env["STUB_LOG"])
    return log.read_text().splitlines() if log.exists() else []


def ufw_rules(env) -> list[str]:
    p = Path(env["STUB_UFW_RULES"])
    return p.read_text().splitlines() if p.exists() else []


def unit(env, suffix) -> str:
    return (Path(env["SYSTEMD_DIR"]) / f"pmoves-ollama-bridge.{suffix}").read_text()


def units_dir(env) -> list[str]:
    return sorted(p.name for p in Path(env["SYSTEMD_DIR"]).iterdir())


def check_scoped_to_consumers(env, script=SCRIPT) -> list[str]:
    """Return defects; empty means bind, upstream, source and ingress are all narrow."""
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
    added = [c for c in calls(env) if c.startswith("ufw allow")]
    if added != [f"ufw allow {RULE} comment {COMMENT}"]:
        defects.append(f"ufw rule not scoped to {SUBNET} on {BR} -> {GW}:11434: {added}")
    return defects


def test_apply_is_scoped_to_the_consumer_network(env):
    assert check_scoped_to_consumers(env) == []
    assert "systemctl enable --now pmoves-ollama-bridge.socket" in calls(env)
    assert "docker network inspect pmoves_external" in " ".join(calls(env))


@pytest.mark.parametrize(
    "mutation",
    [
        ("ListenStream=$BIND_IP:$PORT", "ListenStream=0.0.0.0:$PORT"),
        ("FreeBind=yes", ""),
        ('UFW_RULE="in on $IN_IFACE proto tcp from $SOURCE_CIDR to $BIND_IP port $PORT"',
         'UFW_RULE="proto tcp from 172.16.0.0/12 to $BIND_IP port $PORT"'),
        ('UFW_RULE="in on $IN_IFACE proto tcp', 'UFW_RULE="proto tcp'),
        ("ExecStart=$PROXYD $UPSTREAM", "ExecStart=$PROXYD 0.0.0.0:11434"),
    ],
    ids=["wildcard-bind", "no-freebind", "pool-source", "no-iface", "wrong-upstream"],
)
def test_control_scope_check_fails_on_mutated_script(env, tmp_path, mutation):
    old, new = mutation
    src = SCRIPT.read_text()
    assert old in src, f"mutation anchor vanished: {old}"
    mutated = tmp_path / "mutated.sh"
    mutated.write_text(src.replace(old, new))
    assert check_scoped_to_consumers(env, script=mutated) != []


def test_bridge_name_option_wins_over_derived_br_id(env):
    e = {**env, "STUB_NET": f"{NET_ID}|pmoves-ext0|{SUBNET},", "STUB_BR_IFACE": "pmoves-ext0"}
    r = run(e)
    assert r.returncode == 0, r.stderr
    assert "ufw allow in on pmoves-ext0 proto tcp from 172.30.6.0/24" in r.stdout


def test_ipv6_subnet_listed_first_is_skipped(env):
    r = run({**env, "STUB_NET": f"{NET_ID}|<no value>|fd00:30:6::/64,{SUBNET},"})
    assert r.returncode == 0, r.stderr
    assert f"from {SUBNET} to {GW}" in r.stdout


def test_explicit_source_override_is_used(env):
    r = run({**env, "OLLAMA_BRIDGE_SOURCE_CIDR": "172.30.6.0/25"})
    assert r.returncode == 0, r.stderr
    assert "from 172.30.6.0/25 to" in r.stdout


@pytest.mark.parametrize("cidr", ["172.16.0.0/12", "0.0.0.0/0", "8.8.8.0/24", "172.30.6.1/24", "fd00::/64"])
def test_broad_or_public_source_override_is_refused(env, cidr):
    r = run({**env, "OLLAMA_BRIDGE_SOURCE_CIDR": cidr}, "--apply")
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert units_dir(env) == []


def test_missing_consumer_network_is_could_not_measure(env):
    r = run({**env, "STUB_NET": ""}, "--apply")
    assert r.returncode == 3
    assert units_dir(env) == []
    assert not Path(env["OLLAMA_BRIDGE_STATE_FILE"]).exists()


def test_interface_not_on_link_for_subnet_is_refused(env):
    r = run({**env, "STUB_BR_ADDR": "172.30.9.1/24"}, "--apply")
    assert r.returncode == 2, r.stderr
    assert "disagree" in r.stderr
    assert units_dir(env) == []


def test_dry_run_writes_nothing_and_mutates_nothing(env):
    r = run(env)
    assert r.returncode == 0, r.stderr
    assert f"ListenStream={GW}:11434" in r.stdout
    assert units_dir(env) == []
    assert not Path(env["OLLAMA_BRIDGE_STATE_FILE"]).exists()
    assert [c for c in calls(env) if not c.startswith("docker network inspect")] == []


def test_apply_writes_a_0600_state_record(env):
    assert run(env, "--apply").returncode == 0
    st = Path(env["OLLAMA_BRIDGE_STATE_FILE"])
    assert oct(st.stat().st_mode & 0o777) == "0o600"
    text = st.read_text()
    assert f"UFW_RULE={RULE}" in text
    assert f"BIND_IP={GW}" in text


def test_apply_is_idempotent(env):
    assert run(env, "--apply").returncode == 0
    first = {p.name: p.stat().st_mtime_ns for p in Path(env["SYSTEMD_DIR"]).iterdir()}
    r = run(env, "--apply")
    assert r.returncode == 0
    assert "units changed: 0" in r.stdout
    assert {p.name: p.stat().st_mtime_ns for p in Path(env["SYSTEMD_DIR"]).iterdir()} == first
    assert len(ufw_rules(env)) == 1
    assert not [c for c in calls(env) if c.startswith("ufw delete")]


def test_drift_deletes_the_previous_rule_before_adding(env):
    assert run(env, "--apply").returncode == 0
    e2 = {**env, "STUB_DOCKER0": "172.18.0.1", "STUB_ACTIVE_RC": "0"}
    assert run(e2, "--apply").returncode == 0
    log = calls(e2)
    delete = f"ufw delete allow {RULE}"
    assert delete in log
    add_new = next(i for i, c in enumerate(log) if c.startswith("ufw allow") and "to 172.18.0.1" in c)
    assert log.index(delete) < add_new
    assert len(ufw_rules(e2)) == 1 and "to 172.18.0.1" in ufw_rules(e2)[0]
    assert "ListenStream=172.18.0.1:11434" in unit(e2, "socket")
    assert "systemctl restart pmoves-ollama-bridge.socket" in log


def test_subnet_drift_also_deletes_the_previous_rule(env):
    assert run(env, "--apply").returncode == 0
    e2 = {**env, "STUB_NET": f"{NET_ID}|<no value>|172.30.7.0/24,", "STUB_BR_ADDR": "172.30.7.1/24"}
    assert run(e2, "--apply").returncode == 0
    assert f"ufw delete allow {RULE}" in calls(e2)
    assert [r for r in ufw_rules(e2) if "172.30.6.0/24" in r] == []


def test_rollback_reads_state_with_docker_absent(env):
    assert run(env, "--apply").returncode == 0
    gone = {**env, "STUB_DOCKER0": "", "STUB_NET": "", "STUB_BR_ADDR": ""}
    r = run(gone, "--rollback")
    assert r.returncode == 0, r.stderr
    assert units_dir(env) == []
    assert f"ufw delete allow {RULE}" in calls(gone)
    assert ufw_rules(gone) == []
    assert not Path(env["OLLAMA_BRIDGE_STATE_FILE"]).exists()


def test_rollback_never_rederives(env):
    assert run(env, "--apply").returncode == 0
    Path(env["STUB_LOG"]).unlink()
    assert run(env, "--rollback").returncode == 0
    assert not [c for c in calls(env) if c.startswith("docker ")]


def test_rollback_with_nothing_installed_is_clean(env):
    r = run(env, "--rollback")
    assert r.returncode == 0
    assert "nothing to roll back" in r.stdout


def test_rollback_refuses_to_guess_without_state(env):
    (Path(env["SYSTEMD_DIR"]) / "pmoves-ollama-bridge.socket").write_text("hand-made\n")
    r = run(env, "--rollback")
    assert r.returncode == 3
    assert not [c for c in calls(env) if c.startswith("ufw delete")]


@pytest.mark.parametrize(
    "daemon_json",
    [
        '{"host-gateway-ip": "0.0.0.0"}',
        '{"host-gateway-ip": "0"}',
        '{"host-gateway-ip": "::"}',
        '{"host-gateway-ip": "::ffff:0.0.0.0"}',
        '{"host-gateway-ip": "127.0.0.1"}',
        '{"host-gateway-ips": ["[::]"]}',
        '{"host-gateway-ips": ["::"]}',
    ],
    ids=["unspecified", "bare-zero", "v6-unspecified", "v4-mapped-unspecified", "loopback",
         "bracketed-v6", "only-v6"],
)
def test_wildcard_or_unusable_bind_is_refused(env, daemon_json):
    Path(env["DOCKER_DAEMON_JSON"]).write_text(daemon_json)
    r = run(env, "--apply")
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert units_dir(env) == []
    assert not Path(env["OLLAMA_BRIDGE_STATE_FILE"]).exists()


def test_daemon_json_host_gateway_ip_wins_over_docker0(env):
    Path(env["DOCKER_DAEMON_JSON"]).write_text('{"host-gateway-ip": "10.99.0.1"}')
    r = run(env)
    assert "ListenStream=10.99.0.1:11434" in r.stdout


@pytest.mark.parametrize(
    "daemon_json",
    [
        '{"host-gateway-ips": ["10.99.0.1"]}',
        '{"host-gateway-ips": ["2001:db8::1111", "10.99.0.1"]}',
        '{"host-gateway-ips": ["10.99.0.1"], "host-gateway-ip": "10.88.0.1"}',
    ],
    ids=["plural", "plural-ipv6-first", "plural-wins-over-legacy"],
)
def test_daemon_json_host_gateway_ips_array_is_read(env, daemon_json):
    # dockerd(8) "Configure host gateway IP": the daemon.json key is the array
    # "host-gateway-ips"; "host-gateway-ip" is the legacy single-string form.
    Path(env["DOCKER_DAEMON_JSON"]).write_text(daemon_json)
    r = run(env)
    assert r.returncode == 0, r.stderr
    assert "ListenStream=10.99.0.1:11434" in r.stdout


def test_no_bridge_address_is_could_not_measure(env):
    r = run({**env, "STUB_DOCKER0": ""}, "--apply")
    assert r.returncode == 3
    assert units_dir(env) == []


def test_apply_without_root_mutates_nothing(env):
    e = {k: v for k, v in env.items() if k != "PMOVES_PROVISION_ALLOW_NONROOT"}
    if os.geteuid() == 0:
        pytest.skip("running as root")
    r = run(e, "--apply")
    assert r.returncode == 3
    assert units_dir(env) == []
    assert calls(e) == []


def test_inactive_ufw_gets_no_rule(env):
    e = {**env, "STUB_UFW": "inactive"}
    assert run(e, "--apply").returncode == 0
    assert not [c for c in calls(e) if c.startswith("ufw allow")]


def test_service_orders_after_ollama_but_never_starts_it(env):
    # systemd.unit(5): Wants= starts the listed unit with this one; After= only orders.
    assert run(env, "--apply").returncode == 0
    svc = unit(env, "service")
    assert re.search(r"^After=.*\bollama\.service\b", svc, re.M)
    assert not re.search(r"^(Wants|Requires|BindsTo)=.*\bollama\.service\b", svc, re.M)


def test_status_reports_findings_until_provisioned(env):
    assert run(env, "--status").returncode == 1
    assert run(env, "--apply").returncode == 0
    r = run({**env, "STUB_ACTIVE_RC": "0"}, "--status")
    assert r.returncode == 0, r.stdout
    assert "rule: ufw allow" in r.stdout


def test_status_flags_an_orphaned_rule(env):
    assert run(env, "--apply").returncode == 0
    with open(env["STUB_UFW_RULES"], "a") as f:
        f.write(f"allow in on {BR} from 172.30.9.0/24 to {GW} port 11434 proto tcp comment '{COMMENT}'\n")
    r = run({**env, "STUB_ACTIVE_RC": "0"}, "--status")
    assert r.returncode == 1
    assert "ORPHAN:" in r.stdout and "172.30.9.0/24" in r.stdout


def test_status_flags_a_missing_rule(env):
    assert run(env, "--apply").returncode == 0
    Path(env["STUB_UFW_RULES"]).write_text("")
    r = run({**env, "STUB_ACTIVE_RC": "0"}, "--status")
    assert r.returncode == 1
    assert "MISSING rule" in r.stdout


def test_status_flags_live_drift_from_recorded_state(env):
    assert run(env, "--apply").returncode == 0
    r = run({**env, "STUB_ACTIVE_RC": "0", "STUB_DOCKER0": "172.18.0.1"}, "--status")
    assert r.returncode == 1
    assert "DRIFT: live network/gateway" in r.stdout


def test_status_with_docker_down_still_checks_recorded_state(env):
    assert run(env, "--apply").returncode == 0
    r = run({**env, "STUB_ACTIVE_RC": "0", "STUB_DOCKER0": "", "STUB_NET": ""}, "--status")
    assert r.returncode == 0, r.stdout
    assert "not derivable" in r.stdout


def test_status_without_root_is_could_not_measure(env):
    if os.geteuid() == 0:
        pytest.skip("running as root")
    e = {k: v for k, v in env.items() if k != "PMOVES_PROVISION_ALLOW_NONROOT"}
    assert run(e, "--status").returncode == 3


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
