"""hf-research-agent model-card evidence: parsed without network, scored honestly.

Covers ``card_evidence.py`` (the flattening of ``model-index`` results, the
two-read loader with per-read error capture, the eval-job recipe) and the
scoring deltas criteria 6 and 7 add in ``main.py``. ``main.py`` needs nats-py
and aiohttp at import; when they are absent the scoring tests skip and the
card-evidence tests still run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE = REPO_ROOT / "pmoves" / "services" / "hf-research-agent"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ce():
    sys.path.insert(0, str(SERVICE))
    try:
        mod = _load("card_evidence", SERVICE / "card_evidence.py")
        mod._HF_API = None
        mod._MODEL_CARD = None
        yield mod
    finally:
        sys.path.remove(str(SERVICE))


def _eval(value, **kw):
    base = {"task_type": "text-generation", "dataset_name": "MMLU", "dataset_type": "cais/mmlu",
            "metric_type": "acc", "metric_name": "accuracy", "metric_value": value, "verified": False}
    base.update(kw)
    return SimpleNamespace(**base)


def test_eval_results_keep_numeric_values_only_and_cap(ce):
    data = SimpleNamespace(eval_results=[_eval(0.71), _eval("n/a"), _eval(None), _eval("0.5")]
                           + [_eval(i) for i in range(30)])
    out = ce.eval_results_from_card_data(data)
    assert out[0] == {"task": "text-generation", "dataset": "MMLU", "metric": "accuracy", "value": 0.71, "verified": False}
    assert out[1]["value"] == 0.5
    assert len(out) == ce.MAX_EVAL_RESULTS
    assert ce.eval_results_from_card_data(SimpleNamespace(eval_results=None)) == []
    assert ce.eval_results_from_card_data(SimpleNamespace()) == []


class _Card:
    def __init__(self, data):
        self.data = data

    @classmethod
    def load(cls, model_id, token=None):
        if model_id == "boom/card":
            raise RuntimeError("card 404")
        return cls(SimpleNamespace(license="apache-2.0", base_model="org/base",
                                   library_name=None, eval_results=[_eval(0.8)]))


class _Api:
    def __init__(self, token=None):
        self.token = token

    def model_info(self, model_id):
        if model_id in ("boom/info", "boom/both"):
            raise RuntimeError("info 503")
        return SimpleNamespace(gated="manual", library_name="transformers")


class _CardBoth(_Card):
    @classmethod
    def load(cls, model_id, token=None):
        raise RuntimeError("card 500")


def test_loader_merges_card_and_model_info(ce):
    ce._HF_API, ce._MODEL_CARD = _Api, _Card
    ev = ce.load_card_evidence("org/model", token="t")
    assert ev["available"] is True
    assert ev["license"] == "apache-2.0"
    assert ev["base_model"] == ["org/base"]
    assert ev["library_name"] == "transformers"  # card had none; model_info filled it
    assert ev["gated"] == "manual"
    assert ev["eval_results"][0]["value"] == 0.8
    assert ev["errors"] == []


def test_loader_records_each_failed_read_separately(ce):
    ce._HF_API, ce._MODEL_CARD = _Api, _Card
    ev = ce.load_card_evidence("boom/card")
    assert ev["available"] is True and ev["errors"] == ["card: card 404"]
    assert ev["gated"] == "manual" and ev["eval_results"] == []
    ev = ce.load_card_evidence("boom/info")
    assert ev["available"] is True and ev["errors"] == ["model_info: info 503"]
    assert ev["license"] == "apache-2.0"
    ce._MODEL_CARD = _CardBoth
    ev = ce.load_card_evidence("boom/both")
    assert ev["available"] is False and len(ev["errors"]) == 2


def test_loader_without_huggingface_hub_is_unavailable_not_an_exception(ce, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "huggingface_hub":
            raise ImportError("no hub here")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ev = ce.load_card_evidence("org/model")
    assert ev["available"] is False
    assert ev["errors"][0].startswith("huggingface_hub unavailable")


def test_recipe_mirrors_the_evaluation_skill_flags(ce):
    r = ce.eval_job_recipe("org/model", task="gsm8k", flavor="t4-small")
    assert r.endswith("run_eval_job.py --model org/model --task gsm8k --hardware t4-small")


@pytest.fixture()
def main_mod(monkeypatch):
    pytest.importorskip("nats")
    pytest.importorskip("aiohttp")
    monkeypatch.setenv("HF_MIN_SCORE", "50")
    monkeypatch.setenv("HF_PREFERRED_TAGS", "")
    monkeypatch.setenv("HF_AVOID_TAGS", "")
    sys.path.insert(0, str(SERVICE))
    try:
        yield _load("hf_research_main", SERVICE / "main.py")
    finally:
        sys.path.remove(str(SERVICE))


_MODEL = {"model_id": "org/model", "tags": ["gguf"], "downloads": 20000, "likes": 150, "pipeline_tag": "text-generation"}


def test_card_evidence_adds_exactly_its_points_and_rides_the_envelope(main_mod):
    base = main_mod.HFResearchAgent._evaluate_model(_MODEL, None)
    assert base["score"] == 40 + 25 + 15 + 10
    assert base["max_score"] == 130
    assert base["card_evidence"]["available"] is False
    assert base["eval_results"] == []
    assert "card evidence unavailable" in base["reasons"]

    evidence = {"available": True, "license": "mit", "base_model": ["org/base"], "library_name": "transformers",
                "gated": False, "eval_results": [{"task": "t", "dataset": "d", "metric": "acc", "value": 0.9, "verified": True}], "errors": []}
    full = main_mod.HFResearchAgent._evaluate_model(_MODEL, evidence)
    assert full["score"] == base["score"] + main_mod.EVAL_EVIDENCE_POINTS + main_mod.LICENSE_POINTS
    assert full["eval_results"] == evidence["eval_results"]
    assert full["card_evidence"]["gated"] is False and full["card_evidence"]["license"] == "mit"
    assert full["passed"] and full["eval_job_recipe"].endswith("--model org/model --task mmlu --hardware cpu-basic")

    no_evals = dict(evidence, eval_results=[], license=None)
    partial = main_mod.HFResearchAgent._evaluate_model(_MODEL, no_evals)
    assert partial["score"] == base["score"]
    assert "no model-index evals on card" in partial["reasons"]


def test_failing_model_carries_no_recipe(main_mod):
    weak = {"model_id": "org/weak", "tags": [], "downloads": 5, "likes": 0, "pipeline_tag": ""}
    out = main_mod.HFResearchAgent._evaluate_model(weak, {"available": True, "eval_results": [], "errors": []})
    assert out["passed"] is False and out["eval_job_recipe"] is None
