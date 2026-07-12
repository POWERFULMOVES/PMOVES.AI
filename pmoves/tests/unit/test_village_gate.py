"""Tests for pmoves.tools.village_gate (evaluator gate before Village Rule signoff)."""

from __future__ import annotations

import json

import pytest

from pmoves.tools import village_gate as vg


class TestEvaluateThresholds:
    def test_min_violation(self):
        assert vg.evaluate_thresholds({"m": 0.5}, {"m": {"min": 0.8}})

    def test_max_violation(self):
        assert vg.evaluate_thresholds({"m": 10}, {"m": {"max": 5}})

    def test_pass_within_bounds(self):
        assert vg.evaluate_thresholds({"m": 5}, {"m": {"min": 1, "max": 10}}) == []

    def test_missing_metric_is_violation(self):
        assert vg.evaluate_thresholds({}, {"m": {"max": 1}})


class TestAdapters:
    def test_yaml_valid_counts_bad_files(self, tmp_path, monkeypatch):
        good = tmp_path / "good.yml"
        good.write_text("a: 1\n")
        bad = tmp_path / "bad.yml"
        bad.write_text("a: [unclosed\n")
        monkeypatch.setattr(vg, "REPO_ROOT", tmp_path)
        metrics = vg.check_yaml_valid({"globs": ["*.yml"]})
        assert metrics == {"invalid_count": 1.0, "files_checked": 2.0}

    def test_yaml_valid_tolerates_compose_local_tags(self, tmp_path, monkeypatch):
        compose = tmp_path / "docker-compose.hardened.yml"
        compose.write_text("services:\n  x:\n    ports: !override\n    - '1:1'\n")
        monkeypatch.setattr(vg, "REPO_ROOT", tmp_path)
        metrics = vg.check_yaml_valid({"globs": ["*.yml"]})
        assert metrics["invalid_count"] == 0.0

    def test_yaml_loader_still_rejects_python_object_tags(self, tmp_path, monkeypatch):
        evil = tmp_path / "evil.yml"
        evil.write_text("x: !!python/object/apply:os.system ['echo pwned']\n")
        monkeypatch.setattr(vg, "REPO_ROOT", tmp_path)
        metrics = vg.check_yaml_valid({"globs": ["*.yml"]})
        assert metrics["invalid_count"] == 1.0

    def test_dockerfile_user_coverage(self, tmp_path, monkeypatch):
        svc = tmp_path / "pmoves" / "services" / "x"
        svc.mkdir(parents=True)
        (svc / "Dockerfile").write_text("FROM x\nUSER app\n")
        (svc / "Dockerfile.gpu").write_text("FROM x\n")
        monkeypatch.setattr(vg, "REPO_ROOT", tmp_path)
        metrics = vg.check_dockerfile_user_coverage({"root": "pmoves/services"})
        assert metrics["user_fraction"] == 0.5
        assert metrics["dockerfiles"] == 2.0

    def test_command_exit(self):
        assert vg.check_command_exit({"command": ["true"]}) == {"exit_code": 0.0}
        assert vg.check_command_exit({"command": ["false"]}) == {"exit_code": 1.0}


def config_with(check: dict) -> dict:
    return {"version": 1, "checks": [check]}


class TestRunGate:
    def test_hard_pass(self):
        verdict = vg.run_gate(config_with({
            "id": "ok", "kind": "command_exit", "severity": "hard",
            "params": {"command": ["true"]},
            "threshold": {"exit_code": {"max": 0}},
        }))
        assert verdict["hard_pass"] is True
        assert verdict["checks"][0]["status"] == "pass"

    def test_hard_fail(self):
        verdict = vg.run_gate(config_with({
            "id": "bad", "kind": "command_exit", "severity": "hard",
            "params": {"command": ["false"]},
            "threshold": {"exit_code": {"max": 0}},
        }))
        assert verdict["hard_pass"] is False
        assert verdict["nats"]["payload"]["failed_checks"] == ["bad"]

    def test_advisory_failure_does_not_fail_gate(self):
        verdict = vg.run_gate(config_with({
            "id": "adv", "kind": "command_exit", "severity": "advisory",
            "params": {"command": ["false"]},
            "threshold": {"exit_code": {"max": 0}},
        }))
        assert verdict["hard_pass"] is True
        assert verdict["nats"]["payload"]["advisory_failures"] == ["adv"]

    def test_disabled_check_skipped(self):
        verdict = vg.run_gate(config_with({
            "id": "off", "kind": "command_exit", "enabled": False,
            "params": {"command": ["false"]}, "threshold": {"exit_code": {"max": 0}},
        }))
        assert verdict["hard_pass"] is True
        assert verdict["checks"][0]["status"] == "disabled"

    def test_missing_tool_skips_locally_fails_in_strict(self, monkeypatch):
        def raises(_params):
            raise vg.ToolMissing("nope")
        monkeypatch.setitem(vg.ADAPTERS, "command_exit", raises)
        check = {
            "id": "tool", "kind": "command_exit", "severity": "hard",
            "params": {}, "threshold": {"exit_code": {"max": 0}},
        }
        assert vg.run_gate(config_with(check))["hard_pass"] is True
        assert vg.run_gate(config_with(check), strict_tools=True)["hard_pass"] is False

    def test_adapter_crash_is_hard_failure(self, monkeypatch):
        def boom(_params):
            raise RuntimeError("boom")
        monkeypatch.setitem(vg.ADAPTERS, "command_exit", boom)
        verdict = vg.run_gate(config_with({
            "id": "crash", "kind": "command_exit", "severity": "hard",
            "params": {}, "threshold": {"exit_code": {"max": 0}},
        }))
        assert verdict["hard_pass"] is False

    def test_nats_envelope_subject(self):
        verdict = vg.run_gate({"version": 1, "checks": []})
        assert verdict["nats"]["subject"] == "village.gate.result.v1"


class TestOutputs:
    def test_main_writes_verdict_and_prom(self, tmp_path):
        config = tmp_path / "cfg.yaml"
        config.write_text(json.dumps(config_with({
            "id": "ok", "kind": "command_exit", "severity": "hard",
            "params": {"command": ["true"]}, "threshold": {"exit_code": {"max": 0}},
        })))
        verdict_path = tmp_path / "verdict.json"
        prom_path = tmp_path / "gate.prom"
        rc = vg.main([
            "--config", str(config),
            "--verdict", str(verdict_path),
            "--prom-textfile", str(prom_path),
        ])
        assert rc == 0
        verdict = json.loads(verdict_path.read_text())
        assert verdict["hard_pass"] is True
        prom = prom_path.read_text()
        assert "pmoves_village_gate_pass 1" in prom
        assert 'check="ok"' in prom

    def test_main_exit_1_on_hard_failure(self, tmp_path):
        config = tmp_path / "cfg.yaml"
        config.write_text(json.dumps(config_with({
            "id": "bad", "kind": "command_exit", "severity": "hard",
            "params": {"command": ["false"]}, "threshold": {"exit_code": {"max": 0}},
        })))
        assert vg.main(["--config", str(config), "--verdict", str(tmp_path / "v.json")]) == 1

    def test_main_config_error(self, tmp_path):
        assert vg.main(["--config", str(tmp_path / "missing.yaml")]) == 4
