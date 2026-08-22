"""Tests for pmoves/tools/docker_host_policy_check.py

This probe shipped with no tests at all, which is how three defects reached
review at once: a hard-coded ceiling that failed a correctly-provisioned node,
a `|| true` in the caller that suppressed real failures, and an outage path in
the companion script.

The one that these tests exist to prevent recurring is the ceiling.
deploy/provision/daemon.json is the BASELINE, not a universal maximum;
DOCKER_DAEMON_HARDENING.md sizes per node class and documents the KVM4 data
tier at 100m. A gate that rejects a node for honouring its own documented
policy trains operators to ignore it.

No live docker calls — `log_config` is patched, since that is the only thing
`audit_logging` reaches the host through.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import docker_host_policy_check as dhpc  # noqa: E402


def _with_configs(configs: dict):
    """Patch log_config so audit_logging never touches a real host."""
    return mock.patch.object(dhpc, "log_config", lambda name: configs[name])


def _json_file(max_size: str, max_file: str) -> dict:
    return {"Type": "json-file", "Config": {"max-size": max_size, "max-file": max_file}}


def test_baseline_size_is_compliant():
    with _with_configs({"c": _json_file("50m", "3")}):
        offenders, compliant = dhpc.audit_logging(["c"])
    assert offenders == []
    assert len(compliant) == 1


def test_kvm4_data_tier_100m_is_rejected_at_the_baseline_ceiling():
    """Documents the defect: the documented 100m fails against the 50m default."""
    with _with_configs({"c": _json_file("100m", "5")}):
        offenders, _ = dhpc.audit_logging(["c"])
    assert len(offenders) == 1
    assert "exceeds the 50m policy ceiling" in offenders[0]["reason"]


def test_kvm4_data_tier_100m_passes_at_its_own_documented_ceiling():
    """...and that raising the ceiling is what makes the gate usable there."""
    with _with_configs({"c": _json_file("100m", "5")}):
        offenders, compliant = dhpc.audit_logging(["c"], ceiling_mb=100)
    assert offenders == []
    assert len(compliant) == 1


def test_ceiling_still_rejects_above_itself():
    """Raising the ceiling must not disable the check."""
    with _with_configs({"c": _json_file("200m", "3")}):
        offenders, _ = dhpc.audit_logging(["c"], ceiling_mb=100)
    assert len(offenders) == 1
    assert "exceeds the 100m policy ceiling" in offenders[0]["reason"]


def test_missing_max_size_is_an_offender_at_any_ceiling():
    """The 59-of-62 case on B850 — unbounded growth, not a sizing question."""
    with _with_configs({"c": _json_file("", "3")}):
        offenders, _ = dhpc.audit_logging(["c"], ceiling_mb=10_000)
    assert len(offenders) == 1
    assert "without bound" in offenders[0]["reason"]


def test_max_file_below_one_is_an_offender():
    with _with_configs({"c": _json_file("50m", "0")}):
        offenders, _ = dhpc.audit_logging(["c"])
    assert len(offenders) == 1
    assert "max-file" in offenders[0]["reason"]


def test_external_driver_is_out_of_scope():
    """A driver that ships its own retention is not ours to police."""
    with _with_configs({"c": {"Type": "journald", "Config": {}}}):
        offenders, compliant = dhpc.audit_logging(["c"])
    assert offenders == []
    assert compliant[0]["reason"] == "external driver"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", dhpc.DEFAULT_MAX_SIZE_CEILING_MB),
        ("100", 100),
        ("not-a-number", dhpc.DEFAULT_MAX_SIZE_CEILING_MB),
        ("0", dhpc.DEFAULT_MAX_SIZE_CEILING_MB),
        ("-5", dhpc.DEFAULT_MAX_SIZE_CEILING_MB),
    ],
)
def test_env_ceiling_never_raises(monkeypatch, raw, expected):
    """A malformed env var must not be what decides whether a host certifies."""
    monkeypatch.setenv("PMOVES_LOG_MAX_SIZE_CEILING_MB", raw)
    assert dhpc._env_ceiling() == expected


def test_unmeasured_exits_3_not_0():
    """Exit 3 is 'no verdict', and the caller must not read it as a pass."""
    with mock.patch.object(
        dhpc, "running_containers", side_effect=dhpc.Unmeasured("no docker")
    ):
        assert dhpc.main([]) == 3
