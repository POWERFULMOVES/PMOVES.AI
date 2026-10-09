"""Tests for pmoves.tools.node_gateway_profile — per-node Docker MCP gateway profile.

Guards the defect measured on the 4090 on 2026-09-13: ``pmoves_5090_web`` was the
literal in mcp-toolkit-connect.sh, .claude/mcp.json and mcp_inventory.json, so
every node launched a gateway for the 5090's profile. It was silent because both
profiles are imported on that node -- the wrong one launches fine.

These tests drive the REAL scorer in profile_loader through fixture YAMLs and
stub only the two hardware probes. Re-implementing the scoring here would make
the tests agree with a copy of the logic rather than with the logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pmoves.tools import node_gateway_profile as mod
from pmoves.tools import profile_loader


def _write_profile(
    directory: Path,
    profile_id: str,
    *,
    cpu_model: str = "",
    cpu_vendor: str = "",
    gpu_models: list[str] | None = None,
    gateway_profile: str | None = None,
) -> None:
    """A node profile YAML in the shape load_profiles() expects."""
    gpus = ", ".join('"%s"' % g for g in (gpu_models or []))
    lines = [
        "id: %s" % profile_id,
        'name: "%s"' % profile_id,
        "hardware:",
        "  cpu:",
        '    vendor: "%s"' % cpu_vendor,
        '    model: "%s"' % cpu_model,
        "  gpu:",
        "    models: [%s]" % gpus,
    ]
    if gateway_profile is not None:
        lines += ["docker_mcp:", "  gateway_profile: %s" % gateway_profile]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ("%s.yaml" % profile_id)).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


@pytest.fixture
def hardware(monkeypatch):
    """Control what the real detector sees. Returns a setter."""

    def _set(cpu: str = "", gpus: list[str] | None = None, jetson: bool = False):
        monkeypatch.setattr(profile_loader, "_get_cpu_string", lambda: cpu.lower())
        monkeypatch.setattr(
            profile_loader, "_get_gpu_names", lambda: [g.lower() for g in (gpus or [])]
        )
        monkeypatch.setattr(profile_loader, "_is_jetson", lambda: jetson)

    return _set


@pytest.fixture(autouse=True)
def no_pin(monkeypatch):
    """Default to an unpinned node so detection is what is under test."""
    monkeypatch.setattr(mod, "load_active_profile_id", lambda: None)


# --- the override outranks everything --------------------------------------


def test_env_override_wins_without_reading_profiles(tmp_path):
    """An operator who names the profile is not second-guessed."""
    value, reason = mod.resolve(tmp_path, environ={mod.ENV_OVERRIDE: "explicit_profile"})
    assert value == "explicit_profile"
    assert mod.ENV_OVERRIDE in reason


# --- detection --------------------------------------------------------------


def test_detects_this_nodes_profile_not_another_nodes(tmp_path, hardware):
    """The regression itself: a 4090 must not resolve the 5090's profile."""
    _write_profile(
        tmp_path, "laptop-4090", cpu_vendor="Intel",
        gpu_models=["RTX 4090 Laptop"], gateway_profile="pmoves_4090_web",
    )
    _write_profile(
        tmp_path, "desktop-9950xd", cpu_vendor="AMD",
        gpu_models=["RTX 5090"], gateway_profile="pmoves_5090_web",
    )
    hardware(cpu="intel core i9", gpus=["NVIDIA GeForce RTX 4090 Laptop GPU"])

    value, reason = mod.resolve(tmp_path, environ={})
    assert value == "pmoves_4090_web", reason


def test_alias_profiles_declaring_the_same_value_do_not_tie_fatally(tmp_path, hardware):
    """workstation_5090 is `alias_of: desktop-9950xd` -- same hardware, same answer."""
    _write_profile(
        tmp_path, "desktop-9950xd", cpu_vendor="AMD",
        gpu_models=["RTX 5090"], gateway_profile="pmoves_5090_web",
    )
    _write_profile(
        tmp_path, "workstation_5090", cpu_vendor="AMD",
        gpu_models=["RTX 5090"], gateway_profile="pmoves_5090_web",
    )
    hardware(cpu="amd ryzen 9 9950xd", gpus=["NVIDIA GeForce RTX 5090"])

    value, reason = mod.resolve(tmp_path, environ={})
    assert value == "pmoves_5090_web", reason


def test_tie_on_conflicting_values_refuses_rather_than_picking(tmp_path, hardware):
    """Two equally-matched profiles disagreeing is unresolvable -- say so, don't coin-flip."""
    _write_profile(
        tmp_path, "node-a", cpu_vendor="AMD",
        gpu_models=["RTX 5090"], gateway_profile="profile_a",
    )
    _write_profile(
        tmp_path, "node-b", cpu_vendor="AMD",
        gpu_models=["RTX 5090"], gateway_profile="profile_b",
    )
    hardware(cpu="amd ryzen 9", gpus=["NVIDIA GeForce RTX 5090"])

    value, reason = mod.resolve(tmp_path, environ={})
    assert value is None
    assert "tied" in reason
    assert "node-a" in reason and "node-b" in reason


# --- the refusals -----------------------------------------------------------


def test_no_hardware_match_returns_none_not_a_default(tmp_path, hardware):
    """The whole point: no answer beats a node-named guess."""
    _write_profile(
        tmp_path, "desktop-9950xd", cpu_vendor="AMD",
        gpu_models=["RTX 5090"], gateway_profile="pmoves_5090_web",
    )
    hardware(cpu="some unrecognised cpu", gpus=[])

    value, reason = mod.resolve(tmp_path, environ={})
    assert value is None
    assert "pmoves_5090_web" not in reason


def test_matched_profile_without_a_declaration_names_the_file_to_edit(tmp_path, hardware):
    _write_profile(tmp_path, "kvm4-1", cpu_vendor="AMD", gpu_models=[])
    hardware(cpu="amd epyc", gpus=[])

    value, reason = mod.resolve(tmp_path, environ={})
    assert value is None
    assert "kvm4-1" in reason
    assert "gateway_profile" in reason


def test_empty_profile_dir_is_reported_as_such(tmp_path):
    value, reason = mod.resolve(tmp_path, environ={})
    assert value is None
    assert "no node profiles" in reason


# --- the pin ----------------------------------------------------------------


def test_pinned_profile_outranks_hardware_detection(tmp_path, hardware, monkeypatch):
    _write_profile(
        tmp_path, "laptop-4090", cpu_vendor="Intel",
        gpu_models=["RTX 4090 Laptop"], gateway_profile="pmoves_4090_web",
    )
    _write_profile(
        tmp_path, "kvm4-1", cpu_vendor="AMD", gpu_models=[],
        gateway_profile="pmoves_kvm_web",
    )
    hardware(cpu="intel core i9", gpus=["NVIDIA GeForce RTX 4090 Laptop GPU"])
    monkeypatch.setattr(mod, "load_active_profile_id", lambda: "kvm4-1")

    value, reason = mod.resolve(tmp_path, environ={})
    assert value == "pmoves_kvm_web"
    assert "pinned" in reason


def test_pin_naming_a_missing_profile_is_an_error_not_a_fallthrough(
    tmp_path, hardware, monkeypatch
):
    """A stale pin must not silently degrade into detecting a different node."""
    _write_profile(
        tmp_path, "laptop-4090", cpu_vendor="Intel",
        gpu_models=["RTX 4090 Laptop"], gateway_profile="pmoves_4090_web",
    )
    hardware(cpu="intel core i9", gpus=["NVIDIA GeForce RTX 4090 Laptop GPU"])
    monkeypatch.setattr(mod, "load_active_profile_id", lambda: "deleted-node")

    value, reason = mod.resolve(tmp_path, environ={})
    assert value is None
    assert "deleted-node" in reason


# --- the declaration reader -------------------------------------------------


def test_declared_profile_ignores_blank_or_wrong_shaped_declarations(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "blank.yaml").write_text(
        "id: blank\nname: blank\nhardware: {}\ndocker_mcp:\n  gateway_profile: '   '\n",
        encoding="utf-8",
    )
    (tmp_path / "wrong.yaml").write_text(
        "id: wrong\nname: wrong\nhardware: {}\ndocker_mcp: not-a-mapping\n",
        encoding="utf-8",
    )
    profiles = profile_loader.load_profiles(tmp_path)
    assert mod.declared_profile(profiles["blank"]) is None
    assert mod.declared_profile(profiles["wrong"]) is None


# --- the shipped profiles ---------------------------------------------------


def test_shipped_4090_and_5090_profiles_declare_distinct_gateways():
    """Against the REAL pmoves/config/profiles, not a fixture."""
    profiles = profile_loader.load_profiles()
    assert mod.declared_profile(profiles["laptop-4090"]) == "pmoves_4090_web"
    assert mod.declared_profile(profiles["desktop-9950xd"]) == "pmoves_5090_web"
    # The deprecated alias must agree with its canonical profile, or detection
    # on the 5090 ties fatally.
    assert mod.declared_profile(profiles["workstation_5090"]) == "pmoves_5090_web"
