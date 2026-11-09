"""Offline tests for the Docker host log-rotation probe.

Docker is stubbed so these run on a runner with no daemon; what is under test is
the verdict logic and — most importantly — that an unmeasurable host exits 3
rather than 0.

Context: Z890 reported logs eating disk. B850 measured 4.6 GB in
/var/lib/docker/containers with NO /etc/docker/daemon.json, and this probe found
59 of 62 running containers logging without any max-size. The fix
(pmoves/scripts/pmoves-daemon-log-rotation.sh) was already written and simply
never applied, and nothing checked.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "docker_host_policy_check.py"

spec = importlib.util.spec_from_file_location("docker_host_policy_check", MODULE)
assert spec and spec.loader
dhp = importlib.util.module_from_spec(spec)
sys.modules["docker_host_policy_check"] = dhp
spec.loader.exec_module(dhp)


def cfg(driver="json-file", **options):
    return {"Type": driver, "Config": options}


def stub(monkeypatch, configs: dict, orphans=None):
    monkeypatch.setattr(dhp, "running_containers", lambda: list(configs))
    monkeypatch.setattr(dhp, "log_config", lambda name: configs[name])
    monkeypatch.setattr(dhp, "orphaned_build_cache", lambda: orphans or [])


# ── size parsing ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("10m", 10.0), ("50M", 50.0), ("1g", 1024.0), ("512k", 0.5),
])
def test_parse_size_units(text, expected):
    assert dhp._parse_size_mb(text) == pytest.approx(expected)


def test_parse_size_rejects_garbage():
    assert dhp._parse_size_mb("") is None
    assert dhp._parse_size_mb("banana") is None


# ── verdicts ────────────────────────────────────────────────────────────────

def test_missing_max_size_is_an_offender(monkeypatch):
    """The exact condition on B850: json-file with no cap at all."""
    stub(monkeypatch, {"c1": cfg()})
    offenders, compliant = dhp.audit_logging(["c1"])
    assert len(offenders) == 1 and not compliant
    assert "grows without bound" in offenders[0]["reason"]


def test_compliant_container_passes(monkeypatch):
    stub(monkeypatch, {"c1": cfg(**{"max-size": "10m", "max-file": "3"})})
    offenders, compliant = dhp.audit_logging(["c1"])
    assert not offenders and len(compliant) == 1


def test_max_size_above_ceiling_fails(monkeypatch):
    """A cap looser than deploy/provision/daemon.json is not compliance."""
    stub(monkeypatch, {"c1": cfg(**{"max-size": "500m", "max-file": "3"})})
    offenders, _ = dhp.audit_logging(["c1"])
    assert len(offenders) == 1 and "ceiling" in offenders[0]["reason"]


def test_max_file_missing_fails(monkeypatch):
    stub(monkeypatch, {"c1": cfg(**{"max-size": "10m"})})
    offenders, _ = dhp.audit_logging(["c1"])
    assert len(offenders) == 1 and "max-file" in offenders[0]["reason"]


def test_external_driver_is_out_of_scope(monkeypatch):
    """A driver with its own retention (loki, journald) is not our business."""
    stub(monkeypatch, {"c1": cfg(driver="loki")})
    offenders, compliant = dhp.audit_logging(["c1"])
    assert not offenders and compliant[0]["reason"] == "external driver"


def test_mixed_fleet_reports_only_the_bad(monkeypatch):
    stub(monkeypatch, {
        "good": cfg(**{"max-size": "10m", "max-file": "3"}),
        "bad": cfg(),
    })
    offenders, compliant = dhp.audit_logging(["good", "bad"])
    assert [o["container"] for o in offenders] == ["bad"]
    assert len(compliant) == 1


# ── refusing to guess ───────────────────────────────────────────────────────

def test_unmeasurable_host_exits_3_not_0(monkeypatch):
    """No docker / no containers means the policy was not measured. Reporting
    success there is the failure mode this probe exists to remove."""
    def boom():
        raise dhp.Unmeasured("no running containers to sample")
    monkeypatch.setattr(dhp, "running_containers", boom)
    assert dhp.main([]) == 3


def test_offenders_exit_1(monkeypatch):
    stub(monkeypatch, {"bad": cfg()})
    assert dhp.main([]) == 1


def test_clean_host_exits_0(monkeypatch):
    stub(monkeypatch, {"good": cfg(**{"max-size": "10m", "max-file": "3"})})
    assert dhp.main([]) == 0


# ── orphaned build cache ────────────────────────────────────────────────────

def test_orphan_warning_does_not_fail_the_gate(monkeypatch):
    """183 GB of orphaned buildx cache is worth saying out loud, but removing a
    volume is the operator's call — the probe reports, it does not prune."""
    stub(monkeypatch,
         {"good": cfg(**{"max-size": "10m", "max-file": "3"})},
         orphans=[{"volume": "buildx_buildkit_gone_state", "builder": "gone"}])
    assert dhp.main([]) == 0


def test_probe_never_removes_anything():
    """Guard against a future edit turning the report into a prune."""
    source = MODULE.read_text(encoding="utf-8")
    for destructive in ("volume rm", "volume prune", "system prune", '"rm"'):
        assert f'_docker("{destructive}' not in source
    assert "subprocess.run([\"docker\", \"volume\", \"rm\"" not in source
