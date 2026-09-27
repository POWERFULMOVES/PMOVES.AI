"""The tailnet forwarder that fronts Neo4j (#3201, operator option A).

Neo4j stays internal-only: no egress, no host port. Fleet AGInTs reach bolt over
the tailnet through `neo4j-tailnet`, per DOCKER_NETWORK_HARDENING Rule 5
("gateway-front it"). These assertions pin the design so it cannot drift:
  * userspace Tailscale (TS_DEST_IP is refused in userspace; measured), forwarding
    via TS_SERVE_CONFIG, which tailscaled dials with the container's own stack;
  * ONLY tcp:7687 -> neo4j:7687 (the 7474 browser UI is not forwarded);
  * least privilege: pmoves_graph_front (internal; neo4j + this forwarder only) +
    pmoves_external (control plane) -- NOT pmoves_data; no shared netns, no
    published ports, no capabilities, an image pinned by digest;
  * the overlay is NOT in STACK_FILES, so nodes without a key are unaffected.
Structural only: no docker, no env files. (The auth-key line is deliberately not
asserted here -- see #3201; its `:?` guard makes compose itself refuse to start
without the key.)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PMOVES = Path(__file__).resolve().parents[1]
OVERLAY = PMOVES / "docker-compose.neo4j-tailnet.yml"
SERVE = PMOVES / "config" / "tailscale" / "neo4j-tailnet-serve.json"

SVC = yaml.safe_load(OVERLAY.read_text())["services"]["neo4j-tailnet"]
ENV = dict(e.split("=", 1) for e in SVC["environment"])


def test_image_is_pinned_by_digest():
    assert re.fullmatch(r"tailscale/tailscale:[\w.-]+@sha256:[0-9a-f]{64}", SVC["image"]), SVC["image"]


def test_userspace_and_serve_config_not_dest_ip():
    assert ENV["TS_USERSPACE"] == "true"
    assert "TS_DEST_IP" not in ENV, "TS_DEST_IP is refused with TS_USERSPACE (measured)"
    assert ENV["TS_SERVE_CONFIG"] == "/config/serve.json"
    mounts = [v for v in SVC["volumes"] if v.endswith(":/config/serve.json:ro")]
    assert mounts == ["./config/tailscale/neo4j-tailnet-serve.json:/config/serve.json:ro"]


def test_only_bolt_is_forwarded_to_neo4j():
    cfg = json.loads(SERVE.read_text())
    assert set(cfg) == {"TCP"}
    assert cfg["TCP"] == {"7687": {"TCPForward": "neo4j:7687"}}


def test_it_advertises_tag_neo4j():
    assert "--advertise-tags=tag:neo4j" in ENV["TS_EXTRA_ARGS"].split()


def test_least_privilege_networks_no_netns_share_no_ports_no_caps():
    assert set(SVC["networks"]) == {"pmoves_graph_front", "pmoves_external"}
    assert "pmoves_data" not in SVC["networks"], "the forwarder must not reach the whole data tier"
    assert "network_mode" not in SVC
    assert "ports" not in SVC, "the forwarder publishes nothing on the host"
    assert SVC.get("cap_drop") == ["ALL"]
    assert "cap_add" not in SVC
    assert "no-new-privileges:true" in SVC.get("security_opt", [])


def test_the_overlay_is_not_in_the_default_stack():
    mk = (PMOVES / "Makefile").read_text()
    m = re.search(r"^STACK_FILES \?= \\\n((?:\t-f \S+(?: \\)?\n)+)", mk, re.M)
    assert m and "docker-compose.neo4j-tailnet.yml" not in m.group(1)
    assert "include mk/neo4j-tailnet.mk" in mk


def test_the_make_targets_never_nest_make():
    text = (PMOVES / "mk" / "neo4j-tailnet.mk").read_text()
    recipes = [ln for ln in text.splitlines() if ln.startswith("\t")]
    assert recipes, "no recipe lines found -- parser is broken"
    assert not [ln for ln in recipes if "$(MAKE)" in ln], "a recipe nests make (it runs even under -n)"
    for target in ("up-neo4j-tailnet", "neo4j-tailnet-status", "down-neo4j-tailnet"):
        assert re.search(rf"^{target}:", text, re.M), target



# --- #3201 review P2: the forwarder must never recreate Neo4j implicitly -----

def _recipe(target: str) -> str:
    text = (PMOVES / "mk" / "neo4j-tailnet.mk").read_text()
    start = text.index(f"\n{target}:")
    end = text.find("\n\n", start + 1)
    return text[start:end if end != -1 else len(text)]


def test_up_uses_no_deps_and_a_graph_front_preflight():
    r = _recipe("up-neo4j-tailnet")
    assert "up -d --no-deps neo4j-tailnet" in r
    assert "pmoves_graph_front" in r and "REFUSING" in r
    assert r.index("pmoves_graph_front") < r.index("up -d --no-deps"), "preflight must precede the up"


def test_the_state_volume_cannot_be_wiped_by_volume_reset_neo4j():
    vols = yaml.safe_load(OVERLAY.read_text())["volumes"]
    for name in vols:
        full = f"pmoves_{name}"
        assert not re.search(r"(^pmoves_.*neo4j|neo4j$)", full), full


def _docker_guard():
    name = "pmoves_tests_destructive_docker_guard"
    if name in sys.modules:
        return sys.modules[name]
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("_destructive_docker_guard.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


INSPECT_BEHAVIOUR = r"""
if [ "$1" = "inspect" ]; then
  [ -n "$FAKE_NEO4J_INSPECT" ] && echo "$FAKE_NEO4J_INSPECT"
  exit "${FAKE_INSPECT_RC:-0}"
fi
"""


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
@pytest.mark.parametrize("inspect,rc,refusal", [
    ("true pmoves_app pmoves_bus pmoves_data ", 0, "not attached to pmoves_graph_front"),  # before the gated recreate
    ("true pmoves_app pmoves_bus pmoves_data pmoves_graph_front ", 0, None),               # after it
    ("false pmoves_app pmoves_bus pmoves_data pmoves_graph_front ", 0, "not running"),      # recreated, but stopped
    ("", 1, "could not inspect"),                                                          # missing / daemon / permission
])
def test_up_refuses_until_neo4j_is_running_on_the_graph_front(tmp_path, inspect, rc, refusal):
    stub = _docker_guard().build_stub_env(tmp_path / "bin", stub_make=False,
                                          behaviours={"docker": INSPECT_BEHAVIOUR})
    env = dict(stub)
    env["FAKE_NEO4J_INSPECT"] = inspect
    env["FAKE_INSPECT_RC"] = str(rc)
    proc = subprocess.run(["make", "-s", "-C", str(PMOVES), "up-neo4j-tailnet"],
                          capture_output=True, text=True, timeout=120, env=env)
    calls = [row for row in stub.calls() if row and row[0] == "docker"]
    ups = [row for row in calls if "up" in row]
    if refusal:
        out = proc.stdout + proc.stderr
        assert proc.returncode != 0 and "REFUSING" in out and refusal in out, out
        assert ups == [], ups
    else:
        assert ups, calls
        assert all("--no-deps" in row for row in ups), ups
