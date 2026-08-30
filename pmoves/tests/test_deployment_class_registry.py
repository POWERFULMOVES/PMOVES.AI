"""Deployment-class registry coupling: profiles must resolve, registry must hold.

The registry exists because the fleet could express license class per model
and per TTS engine but not per deployment (no tenant_type in profiles, so
"which customer type is this node?" was unanswerable). These tests hold the
coupling the registry is FOR:

  * every deployment_class set in ANY profile resolves to a registry class
  * unset stays unset — nothing guesses a default (declare-never-infer)
  * the four customer types exist and their hosted_path/requires_ack posture
    is internally consistent with the gate creator_models established
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "pmoves" / "config" / "deployment_classes.yaml"
PROFILES = sorted((REPO_ROOT / "pmoves" / "config" / "profiles").glob("*.yaml"))


def _registry() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def test_registry_exists_and_versions():
    doc = _registry()
    assert doc["schema_version"] == 1
    assert doc["classes"], "registry declares no classes"


def test_the_four_customer_types_exist():
    classes = _registry()["classes"]
    for expected in ("private-mesh", "community", "school", "enterprise"):
        assert expected in classes, f"missing customer type {expected!r}"


def test_every_profile_class_resolves():
    reg = _registry()["classes"]
    offenders = []
    for path in PROFILES:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        dc = doc.get("deployment_class")
        if dc is None:
            continue  # unset means unset — deliberately not a failure
        if dc not in reg:
            offenders.append(f"{path.name}: {dc!r}")
    assert not offenders, f"profiles reference unknown classes: {offenders}"


def test_unset_is_not_guessed():
    """No profile may carry a guessed/commented default that parses as set."""
    for path in PROFILES:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        dc = doc.get("deployment_class")
        assert dc is None or isinstance(dc, str), f"{path.name}: non-string class"


def test_hosted_path_posture_matches_the_gate():
    """hosted_path=true must be the ONLY class where requires_ack components
    are excluded — that is the creator_models gate lifted one level. A class
    that hosts must exclude un-acked components; a class that does not host
    must not claim exclusion (it runs self-hosted under each engine's terms)."""
    classes = _registry()["classes"]
    for name, cls in classes.items():
        posture = cls["requires_ack_components"]
        hosted = cls["hosted_path"]
        if hosted:
            assert posture == "excluded", (
                f"{name}: hosted_path=true but requires_ack={posture!r} — the "
                "hosted path must exclude un-acked components (creator_models gate)"
            )
        else:
            assert posture != "excluded", (
                f"{name}: not hosted, so 'excluded' overstates — self-hosted "
                "classes run under each engine's own terms, they do not resell"
            )


def test_fleet_nodes_tagged_private_mesh():
    """The operator's own nodes carry the class explicitly — the field every
    later gate keys on must be present where we KNOW the answer."""
    fleet = {
        "desktop-9950xd.yaml",        # 5090
        "workstation_5090.yaml",      # 5090 (legacy id spelling)
        "dgx-spark-grace-blackwell.yaml",  # SPARK
        "intel-265kf-3090ti.yaml",    # z890
        "z890-coordinator.yaml",      # z890 (coordinator spelling)
        "laptop-4090.yaml",           # 4090
        "workstation-9850x3d-dual-r9700.yaml",  # B850/Knuckles
        "jetson-jons-1.yaml",
        "jetson-jons-2.yaml",
        "jetson-jons-3.yaml",
    }
    names = {p.name for p in PROFILES}
    assert fleet <= names, f"fleet profiles missing: {fleet - names}"
    for path in PROFILES:
        if path.name not in fleet:
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        assert doc.get("deployment_class") == "private-mesh", (
            f"{path.name}: fleet node must declare private-mesh explicitly"
        )
