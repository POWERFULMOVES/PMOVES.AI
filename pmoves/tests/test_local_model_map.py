"""local_model_map: the three SPARK mismatches of 2026-10-21 must be flagged.

Stubbed HTTP (no Ollama, no Hub) + fixture journal text. Read-only tool, so
nothing here mutates anything; the make test renders the recipe with -n.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "local_model_map", REPO_ROOT / "pmoves" / "tools" / "models" / "local_model_map.py")
assert SPEC is not None and SPEC.loader is not None
lmm = importlib.util.module_from_spec(SPEC)
sys.modules["local_model_map"] = lmm  # dataclasses resolve their module
SPEC.loader.exec_module(lmm)

B30 = "a" * 64   # qwen3:30b-a3b weights (shared by the -gpu variant)
BEMB = "b" * 64  # qwen3-embedding:4b weights


def _show(arch, native, caps, blob, params="", parent=""):
    return {"parameters": params, "model_info": {"general.architecture": arch, f"{arch}.context_length": native},
            "capabilities": caps, "details": {"parent_model": parent, "format": "gguf"},
            "modelfile": f"FROM /models/blobs/sha256-{blob}\n"}


SHOW = {
    "qwen3:30b-a3b-q4_K_M": _show("qwen3moe", 40960, ["completion", "tools"], B30),
    "qwen3:30b-a3b-gpu": _show("qwen3moe", 40960, ["completion", "tools"], B30,
                               "num_ctx 32768\nnum_gpu 999", "qwen3:30b-a3b-q4_K_M"),
    "qwen3-embedding:4b": _show("qwen3", 40960, ["embedding"], BEMB),
}


def fake_fetch(ps_models=()):
    def fetch(method, url, body=None):
        if url.endswith("/api/tags"):
            return {"models": [{"name": t, "digest": "d" * 64, "size": 5_000_000_000,
                                "details": {"quantization_level": "Q4_K_M"}} for t in SHOW]}
        if url.endswith("/api/ps"):
            return {"models": list(ps_models)}
        if url.endswith("/api/show"):
            return SHOW[body["model"]]
        raise AssertionError(f"unexpected url {url}")
    return fetch


# The three cases, in the journal's own line shapes (Ollama 0.30 / llama-server).
JOURNAL = f"""\
ollama[1]: msg="loading model via llama-server" model=/m/blobs/sha256-{B30}
ollama[1]: load_tensors: offloaded 49/49 layers to GPU
ollama[1]: llama_context: n_ctx         = 8192
ollama[1]: slot update_slots: id  0 | task 10 | new prompt, n_ctx_slot = 8192, n_keep = 0, task.n_tokens = 8192
ollama[1]: slot      release: id  0 | task 10 | stop processing: n_tokens = 8193, truncated = 1
ollama[1]: msg="loading model via llama-server" model=/m/blobs/sha256-{BEMB}
ollama[1]: load_tensors: offloaded 16/37 layers to GPU
ollama[1]: llama_context: n_ctx         = 8192
ollama[1]: slot update_slots: id  0 | task 20 | new prompt, n_ctx_slot = 8192, n_keep = 0, task.n_tokens = 8191
ollama[1]: slot      release: id  0 | task 20 | stop processing: n_tokens = 8191, truncated = 0
ollama[1]: [GIN] 2026/10/21 - 18:59:19 | 200 |  6.47s |     172.30.6.41 | POST     "/v1/embeddings"
ollama[1]: msg="loading model via llama-server" model=/m/blobs/sha256-{B30}
ollama[1]: load_tensors: offloaded 49/49 layers to GPU
ollama[1]: llama_context: n_ctx         = 32768
ollama[1]: slot update_slots: id  0 | task 30 | new prompt, n_ctx_slot = 32768, n_keep = 0, task.n_tokens = 26700
ollama[1]: slot update_slots: id  0 | task 31 | new prompt, n_ctx_slot = 32768, n_keep = 0, task.n_tokens = 30800
"""

PRESETS = """\
- name: Default
  chat: {provider: ollama, name: qwen3:30b-a3b-q4_K_M, ctx_length: 32768}
  utility: {provider: ollama, name: qwen3:30b-a3b-gpu, ctx_length: 32768}
"""

TZ = """\
[embedding_models.qwen3_embedding_4b_local]
routing = ["ollama_local_embedding"]
[embedding_models.qwen3_embedding_4b_local.providers.ollama_local_embedding]
type = "openai"
api_base = "http://host.docker.internal:11434/v1"
model_name = "qwen3-embedding:4b"
"""

COMPOSE = """\
services:
  extract-worker:
    environment:
      - TENSORZERO_EMBED_MODEL=${TENSORZERO_EMBED_MODEL:-tensorzero::embedding_model_name::qwen3_embedding_4b_local}
"""


def _run(tmp_path, capsys, *extra, ps_models=()):
    (tmp_path / "journal.txt").write_text(JOURNAL)
    (tmp_path / "presets.yaml").write_text(PRESETS)
    (tmp_path / "tz.toml").write_text(TZ)
    (tmp_path / "compose.yml").write_text(COMPOSE)
    (tmp_path / "suits").mkdir(exist_ok=True)
    rc = lmm.main([
        "--json", "--no-hf", "--journal-file", str(tmp_path / "journal.txt"),
        "--a0-presets", str(tmp_path / "presets.yaml"), "--tz-config", str(tmp_path / "tz.toml"),
        "--compose", str(tmp_path / "compose.yml"), "--suits-dir", str(tmp_path / "suits"),
        "--hf-mappings", str(tmp_path / "none.yaml"), "--no-unified-memory", *extra,
    ], fetch=fake_fetch(ps_models))
    return rc, {r["tag"]: r for r in json.loads(capsys.readouterr().out)["rows"]}


def _evidence(row, kind):
    return [v["evidence"] for v in row["verdicts"] if v["kind"] == kind]


def test_case1_a0_prompt_past_the_8192_default_is_truncating(tmp_path, capsys):
    _, rows = _run(tmp_path, capsys)
    row = rows["qwen3:30b-a3b-q4_K_M"]
    assert row["verdict"] == "TRUNCATING"
    ev = _evidence(row, "TRUNCATING")
    assert any("truncated=1" in e for e in ev)
    assert any("ctx_length=32768" in e and "slot is 8192" in e for e in ev)


def test_case2_embedding_inputs_clipped_at_slot_minus_one(tmp_path, capsys):
    _, rows = _run(tmp_path, capsys)
    row = rows["qwen3-embedding:4b"]
    assert row["verdict"] == "TRUNCATING"
    assert any("task.n_tokens=8191" in e for e in _evidence(row, "TRUNCATING"))
    assert any("extract-worker" in c and "qwen3_embedding_4b_local" in c for c in row["consumers"])
    assert any("16/37" in e for e in _evidence(row, "UNDER-GPU"))


def test_case3_claude_code_prompt_leaves_no_output_room_in_32768(tmp_path, capsys):
    _, rows = _run(tmp_path, capsys, ps_models=[{"name": "qwen3:30b-a3b-gpu", "context_length": 32768}])
    row = rows["qwen3:30b-a3b-gpu"]
    assert row["verdict"] == "TRUNCATING"
    ev = _evidence(row, "TRUNCATING")
    assert any("30800" in e and "slot 32768" in e and "native 40960" in e for e in ev)
    # attributed to the variant, not to the base tag on the same weights
    assert all(d["slot"] != 32768 for d in rows["qwen3:30b-a3b-q4_K_M"]["demand"])


def test_check_exits_1_on_conflict_and_0_without(tmp_path, capsys):
    rc, _ = _run(tmp_path, capsys, "--check")
    assert rc == 1
    rc, _ = _run(tmp_path, capsys)
    assert rc == 0


def test_ollama_unreachable_is_could_not_measure(capsys):
    def down(method, url, body=None):
        raise OSError("connection refused")
    assert lmm.main(["--no-hf", "--no-journal"], fetch=down) == 3


def test_suit_drift_and_over_native(tmp_path):
    suits = tmp_path / "suits"
    suits.mkdir()
    (suits / "e.yaml").write_text(
        "name: e\nprovider: ollama_local\nmodel_config:\n  model_name: qwen3-embedding:4b\n"
        "  ollama_config: {num_gpu: 999, num_ctx: 65536}\nhuggingface: {model_id: Qwen/Qwen3-Embedding-4B}\n")
    (suits / "m.yaml").write_text("name: m\nprovider: ollama_spark\nmodel_config:\n  model_name: gemma4:31b-q4\n")
    rt = lmm.collect_runtime("http://x", fake_fetch())
    rows = {r.tag: r for r in lmm.build_rows(rt, lmm.load_suits(suits), {}, None, [], unified_memory=False,
                                             output_reserve=2048, hf_lookup=None)}
    assert rows["gemma4:31b-q4"].primary == "SUIT-DRIFT"
    drift = [v.evidence for v in rows["qwen3-embedding:4b"].verdicts if v.kind == "SUIT-DRIFT"]
    assert drift and "num_gpu suit=999" in drift[0]
    over = [v.evidence for v in rows["qwen3-embedding:4b"].verdicts if v.kind == "OVER-NATIVE"]
    assert over and "65536 > native 40960" in over[0]
    assert rows["qwen3-embedding:4b"].hf_repo == "Qwen/Qwen3-Embedding-4B"
    assert rows["qwen3:30b-a3b-gpu"].hf_source == "unmapped"


def test_hf_layer_uses_card_evidence_when_present():
    class Card:
        @staticmethod
        def load_card_evidence(repo, token=None, timeout=None):
            return {"license": "apache-2.0", "gated": False, "library_name": "sentence-transformers", "errors": []}

    def fetch(method, url, body=None):
        assert url.endswith("/config.json")
        return {"max_position_embeddings": 40960, "rope_scaling": None}

    out = lmm.hf_layer("Qwen/Qwen3-Embedding-4B", fetch, Card)
    assert out["source"].startswith("hf-research-agent") and out["license"] == "apache-2.0"
    assert out["native_ctx"] == 40960


def test_missing_journalctl_is_a_skipped_layer_not_a_failure():
    def runner(*a, **k):
        raise FileNotFoundError("journalctl")
    text, why = lmm.read_journal("-1h", runner=runner)
    assert text is None and "not available" in why


def test_make_target_renders_flags(stub_docker_path):
    proc = subprocess.run(
        ["make", "-n", "-C", str(REPO_ROOT / "pmoves"), "models-layer-map", "CHECK=1", "JSON=1", "NO_HF=1", "SINCE=-2h"],
        capture_output=True, text=True, timeout=60, env=stub_docker_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert "tools/models/local_model_map.py" in proc.stdout
    assert '--since "-2h"' in proc.stdout and "--check" in proc.stdout and "--json" in proc.stdout and "--no-hf" in proc.stdout
