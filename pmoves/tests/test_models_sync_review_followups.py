"""models_sync review follow-ups from #3373 (landed in #3396).

Covers the --check exit contract (0 clean / 1 drift / 2 undecided), the
degradation ladder re-guard, per-instance usr-dir resolution, collision-proof
review copies and pruned CB-4 archives, the template-row memo, the ollama
default host, and the Makefile's command-line-only INSTANCE/OUT knobs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import urllib.error
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES = REPO_ROOT / "pmoves"
SPEC = importlib.util.spec_from_file_location(
    "models_sync_review_followups", PMOVES / "tools" / "models" / "models_sync.py")
assert SPEC is not None and SPEC.loader is not None
ms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ms)

ROWS = [{"service_name": "agent_zero", "function_name": "chat", "model_type": "chat",
         "model_id": "qwen2.5:14b", "provider_name": "ollama", "provider_type": "ollama",
         "context_length": 32768}]
EMBED_ONLY = [{"service_name": "tensorzero", "function_name": "embeddings", "model_type": "embedding",
               "model_id": "nomic-embed-text", "provider_name": "ollama", "provider_type": "ollama"}]


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "ROOT", tmp_path)  # review/backup copies stay in tmp
    monkeypatch.delenv("A0_PRESETS_BACKUP_KEEP", raising=False)
    return tmp_path


@pytest.fixture
def out(root):
    d = root / "usr" / "plugins" / "_model_config"
    d.mkdir(parents=True)
    return d / "presets.yaml"


def _exit_code(fn, *a, **k):
    with pytest.raises(SystemExit) as exc:
        fn(*a, **k)
    return exc.value.code


def _manifest(stdout: str) -> dict:
    return json.loads(stdout[stdout.index("{"):stdout.rindex("}") + 1])


def _dyn_args(out_path, **over):
    base = dict(cloud_order="", target="agent-zero", tensorzero_base="http://tz:3000",
                apply_presets=False, check=True, instance="docked", out=str(out_path), host="n")
    base.update(over)
    return argparse.Namespace(**base)


# --- --check exit contract ---------------------------------------------------

def test_check_registry_outage_is_undecided_not_drift(out, monkeypatch, capsys):
    ms._write_a0_presets(ROWS, [], out, apply=True)
    capsys.readouterr()  # drop the setup run's manifest

    def boom():
        raise urllib.error.URLError("supabase down")

    monkeypatch.setattr(ms, "_load_service_models", boom)
    assert _exit_code(ms.cmd_sync_dynamic, _dyn_args(out)) == 2
    m = _manifest(capsys.readouterr().out)
    assert m["check"] == "undecided" and m["reason"] == "registry_unreachable"


@pytest.mark.parametrize("live", [True, False])
def test_check_empty_chat_lane_is_undecided(out, capsys, live):
    if live:
        out.write_text("[]\n")
    assert _exit_code(ms._write_a0_presets, [], [], out, check=True) == 2
    assert _manifest(capsys.readouterr().out)["reason"] == "empty_chat_lane"
    assert not live or out.read_text() == "[]\n"


def test_check_unreadable_live_file_is_undecided(out, capsys):
    out.mkdir()  # exists() but read_text() raises IsADirectoryError
    assert _exit_code(ms._write_a0_presets, ROWS, [], out, check=True) == 2
    assert _manifest(capsys.readouterr().out)["reason"] == "live_unreadable"


def test_check_ignores_the_instance_header(out, monkeypatch):
    ms._write_a0_presets(ROWS, [], out, instance="mesh", apply=True)
    assert "instance: mesh" in out.read_text()
    ms._write_a0_presets(ROWS, [], out, instance="docked", check=True)  # no SystemExit = clean


def test_check_still_reports_real_drift(out):
    ms._write_a0_presets(ROWS, [], out, apply=True)
    other = [dict(ROWS[0], model_id="qwen3:8b")]
    assert _exit_code(ms._write_a0_presets, other, [], out, check=True) == 1


def test_check_with_target_other_than_agent_zero_is_refused(out, monkeypatch):
    def must_not_run(*_a, **_k):
        raise AssertionError("archon/creator lane ran under --check")

    monkeypatch.setattr(ms, "_load_service_models", must_not_run)
    monkeypatch.setattr(ms, "_sync_dynamic_archon", must_not_run)
    monkeypatch.setattr(ms, "_sync_dynamic_creator", must_not_run)
    for target in ("all", "archon", "creator"):
        assert _exit_code(ms.cmd_sync_dynamic, _dyn_args(out, target=target)) == 2


def test_check_and_apply_presets_are_mutually_exclusive():
    parser = ms.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["sync-dynamic", "--check", "--apply-presets"])
    assert exc.value.code == 2


# --- degradation ladder ------------------------------------------------------

def test_degraded_rederivation_is_reguarded(out, monkeypatch):
    # Template parses but only its embedding block survives: the ladder must
    # continue to last-resort rows, never write a header-only file.
    monkeypatch.setattr(ms, "_load_template_rows", lambda: [dict(r) for r in EMBED_ONLY])
    ms._write_a0_presets([], [], out, apply=True)
    doc = yaml.safe_load(out.read_text())
    assert doc and doc[0]["name"] == "Default"
    last_resort_chat = next(r for r in ms.A0_LAST_RESORT_ROWS if r["model_type"] == "chat")
    assert doc[0]["chat"]["name"].endswith(last_resort_chat["model_id"])


def test_template_rows_are_parsed_once_and_handed_out_as_copies(root, monkeypatch):
    calls = []
    real = ms._parse_template_rows
    monkeypatch.setattr(ms, "_parse_template_rows", lambda p: calls.append(p) or real(p))
    monkeypatch.setattr(ms, "_TEMPLATE_ROWS_CACHE", {})
    first = ms._load_template_rows()
    first[0]["model_id"] = "mutated"
    for _ in range(2):
        assert ms._load_template_rows()[0]["model_id"] != "mutated"
    assert len(calls) == 1


# --- per-instance output path --------------------------------------------------

def test_instance_usr_var_is_honoured(root, monkeypatch, tmp_path):
    monkeypatch.setenv("DARKXSIDE_USR_DIR", str(tmp_path / "dx"))
    monkeypatch.setenv("AGENT_ZERO_USR_DIR", str(tmp_path / "docked"))
    assert ms._a0_presets_out_path("darkxside") == tmp_path / "dx" / "plugins" / "_model_config" / "presets.yaml"


def test_relative_instance_usr_var_resolves_against_pmoves(root, monkeypatch):
    monkeypatch.setenv("SPARK_USR_DIR", "./usr")
    assert ms._a0_presets_out_path("spark") == root / "usr" / "plugins" / "_model_config" / "presets.yaml"


@pytest.mark.parametrize("instance", ["darkxside", "mesh"])
def test_variant_without_usr_var_refuses_the_docked_path(root, monkeypatch, instance):
    for var in ms.A0_INSTANCE_USR_ENV.values():
        monkeypatch.delenv(var, raising=False)
    assert _exit_code(ms._a0_presets_out_path, instance) == 2


def test_docked_default_is_unchanged(root, monkeypatch):
    monkeypatch.delenv("AGENT_ZERO_USR_DIR", raising=False)
    assert ms._a0_presets_out_path("docked") == root / ms.A0_PRESETS_SUBPATH


# --- review copies and CB-4 archives -----------------------------------------

def test_review_copies_do_not_collide_across_instances_or_paths(root):
    a = root / "a" / "presets.yaml"
    b = root / "b" / "presets.yaml"
    for p in (a, b):
        p.parent.mkdir(parents=True)
        p.write_text("[]\n")
    ms._write_a0_presets(ROWS, [], a, instance="docked", apply=False)
    ms._write_a0_presets(ROWS, [], b, instance="docked", apply=False)
    ms._write_a0_presets(ROWS, [], a, instance="darkxside", apply=False)
    news = sorted((root / ms.A0_REVIEW_DIR_SUBPATH).glob("*.new"))
    assert len(news) == 3
    assert a.read_text() == "[]\n" and b.read_text() == "[]\n"  # review mode never touches live


def test_archives_are_unique_and_pruned_per_instance(root, out, monkeypatch):
    monkeypatch.setenv("A0_PRESETS_BACKUP_KEEP", "3")
    other = root / "other" / "presets.yaml"
    other.parent.mkdir(parents=True)
    other.write_text("[]\n")
    ms._write_a0_presets(ROWS, [], other, instance="darkxside", apply=True)  # 1 archive of its own
    out.write_text("[]\n")
    for _ in range(5):  # same wall-clock second is fine: names never collide
        ms._write_a0_presets(ROWS, [], out, apply=True)
    review = root / ms.A0_REVIEW_DIR_SUBPATH
    mine = sorted(review.glob(ms._review_file_prefix(out, "docked") + ".bak-*"))
    theirs = sorted(review.glob(ms._review_file_prefix(other, "darkxside") + ".bak-*"))
    assert len(mine) == 3 and len(theirs) == 1
    assert yaml.safe_load(mine[0].read_text())[0]["name"] == "Default"  # oldest pruned first


def test_archive_keep_zero_disables_pruning(root, out, monkeypatch):
    monkeypatch.setenv("A0_PRESETS_BACKUP_KEEP", "0")
    out.write_text("[]\n")
    for _ in range(4):
        ms._write_a0_presets(ROWS, [], out, apply=True)
    assert len(list((root / ms.A0_REVIEW_DIR_SUBPATH).glob("*.bak-*"))) == 4


def test_unparseable_live_file_warns_instead_of_silently_dropping(out, capsys):
    out.write_text("- name: [unclosed\n")
    ms._write_a0_presets(ROWS, [], out, apply=True)
    err = capsys.readouterr().err
    assert "WARNING: live presets unreadable" in err
    baks = list((ms.ROOT / ms.A0_REVIEW_DIR_SUBPATH).glob("*.bak-*"))
    assert [b.read_text() for b in baks] == ["- name: [unclosed\n"]  # original archived


# --- ollama default host -----------------------------------------------------

def test_ollama_default_is_the_compose_service_name(monkeypatch):
    monkeypatch.delenv("PMOVES_OLLAMA_BASE_URL", raising=False)
    assert ms._a0_api_base({}, "ollama", "http://tz:3000") == "http://pmoves-ollama:11434"


# --- Makefile knobs ----------------------------------------------------------

def _plan(env, *args):
    env = dict(env)
    r = subprocess.run(
        ["make", "-n", "--no-print-directory", "-o", "ensure-env-shared", "-C", str(PMOVES),
         "a0-model-sync-check", *args],
        env=env, capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stderr
    line = next(l for l in r.stdout.splitlines() if "models_sync.py sync-dynamic" in l)
    return line


def test_make_ignores_exported_generic_out_and_instance(stub_docker_path):
    env = dict(stub_docker_path, OUT="/tmp/hijacked", INSTANCE="evil")
    env.pop("A0_MODEL_SYNC_OUT", None)
    env.pop("A0_MODEL_SYNC_INSTANCE", None)
    line = _plan(env)
    assert '--instance "docked"' in line and "--out" not in line


def test_make_honours_command_line_out_and_instance(stub_docker_path):
    line = _plan(stub_docker_path, "INSTANCE=darkxside", "OUT=/srv/dx/presets.yaml")
    assert '--instance "darkxside"' in line and '--out "/srv/dx/presets.yaml"' in line


def test_make_empty_instance_falls_back_to_docked(stub_docker_path):
    assert '--instance "docked"' in _plan(stub_docker_path, "INSTANCE=")


def test_make_honours_namespaced_env_knobs(stub_docker_path):
    env = dict(stub_docker_path, A0_MODEL_SYNC_INSTANCE="spark", A0_MODEL_SYNC_OUT="/srv/sp/presets.yaml")
    line = _plan(env)
    assert '--instance "spark"' in line and '--out "/srv/sp/presets.yaml"' in line
