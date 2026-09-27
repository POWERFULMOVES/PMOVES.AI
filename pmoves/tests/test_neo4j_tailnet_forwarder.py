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
import re
from pathlib import Path

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
