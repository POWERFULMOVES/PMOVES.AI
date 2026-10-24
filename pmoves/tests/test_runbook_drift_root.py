"""runbook_drift audits the checkout it lives in, and refuses an empty scan.

ROOT used to be hardcoded to the A0 sidecar's /a0/usr/projects/pmoves_ai. On CI
runners and fleet nodes that path does not exist, so the glob matched nothing and
the docs-drift check reported files=0, claims=0 and passed.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "runbook_drift.py"


def _load(monkeypatch, **env):
    for key in ("RUNBOOK_DRIFT_ROOT", "JEV_MODEL_PATH"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    spec = importlib.util.spec_from_file_location("runbook_drift_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_defaults_to_the_checkout_holding_the_script(monkeypatch):
    assert _load(monkeypatch).ROOT == REPO_ROOT


def test_root_and_jev_model_can_be_pointed_elsewhere(monkeypatch, tmp_path):
    model = tmp_path / "agentjev.onnx"
    m = _load(monkeypatch, RUNBOOK_DRIFT_ROOT=str(tmp_path), JEV_MODEL_PATH=str(model))
    assert m.ROOT == tmp_path.resolve()
    assert m.JEV_MODEL == model


def test_jev_model_defaults_under_the_root(monkeypatch, tmp_path):
    m = _load(monkeypatch, RUNBOOK_DRIFT_ROOT=str(tmp_path))
    assert m.JEV_MODEL == tmp_path.resolve() / "research/models/agentjev/agentjev_0.6b_int8.onnx"


def test_a_relative_root_override_is_resolved_once(monkeypatch, tmp_path):
    (tmp_path / "tree").mkdir()
    monkeypatch.chdir(tmp_path)
    m = _load(monkeypatch, RUNBOOK_DRIFT_ROOT="tree")
    assert m.ROOT.is_absolute()
    assert m.ROOT == (tmp_path / "tree").resolve()


def test_a_scan_that_matches_no_files_fails(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "--no-jev", "--globs", "no-such-dir/*.md",
                        "--out", str(tmp_path / "report.json")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "matched no auditable files" in r.stderr
    assert "skipped" not in r.stderr


def test_a_scan_of_only_the_register_fails_and_says_why(tmp_path):
    docs = tmp_path / "docs"; docs.mkdir()
    (docs / "AGNOTE4482PHI.t1.md").write_text("Run `scripts/nope.py`.\n")
    r = subprocess.run([sys.executable, str(SCRIPT), "--no-jev", "--globs", "docs/*.md",
                        "--out", str(tmp_path / "report.json")], capture_output=True, text=True,
                       timeout=60, env={"PATH": "/usr/bin:/bin", "RUNBOOK_DRIFT_ROOT": str(tmp_path)})
    assert r.returncode == 2, r.stdout + r.stderr
    assert "matched no auditable files" in r.stderr
    assert "1 AGNOTE4482PHI register file(s) matched and skipped" in r.stderr


def test_a_real_scan_reads_files(tmp_path):
    docs = tmp_path / "docs"; docs.mkdir()
    (docs / "note.md").write_text("Run `scripts/does_not_exist.py` first.\n")
    out = tmp_path / "report.json"
    r = subprocess.run([sys.executable, str(SCRIPT), "--no-jev", "--globs", "docs/*.md",
                        "--out", str(out)], capture_output=True, text=True, timeout=60,
                       env={"PATH": "/usr/bin:/bin", "RUNBOOK_DRIFT_ROOT": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    report = json.loads(out.read_text())
    assert report["files_scanned"] == 1 and len(report["records"]) == 1


def test_jev_abstention_keeps_the_heuristic_class(monkeypatch, tmp_path):
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "THING_DRAFT.md").write_text("Run `scripts/nope.py`.\n")
    m = _load(monkeypatch, RUNBOOK_DRIFT_ROOT=str(tmp_path))
    monkeypatch.setattr(m, "_load_jev", lambda: ("sess", "tok"))
    monkeypatch.setattr(m, "jev_classify_doc", lambda *a, **k: "UNDECIDED")
    out = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["runbook_drift", "--globs", "plans/*.md", "--out", str(out)])
    m.main()
    assert json.loads(out.read_text())["records"][0]["doc_class"] == "DRAFT"
