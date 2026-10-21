"""models_sync ollama-apply: suit ollama_config -> Ollama variant plan, drift, offload verdict."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "models_sync", REPO_ROOT / "pmoves" / "tools" / "models" / "models_sync.py")
assert SPEC is not None and SPEC.loader is not None
ms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ms)


def _suit(**over):
    doc = {"name": "s", "provider": "ollama_local",
           "model_config": {"model_name": "m:4b", "context_window": 8192,
                            "ollama_config": {"num_gpu": 999}}}
    doc.update(over)
    return doc


def test_plan_maps_context_window_to_num_ctx_and_defaults_the_variant():
    p = ms.suit_ollama_plan(_suit())
    assert p["base"] == "m:4b"
    assert p["variant"] == "m:4b-pmoves"
    assert p["parameters"] == {"num_gpu": 999, "num_ctx": 8192}


def test_explicit_num_ctx_and_variant_win():
    doc = _suit()
    doc["model_config"]["ollama_config"].update(num_ctx=2048, variant="m:custom")
    p = ms.suit_ollama_plan(doc)
    assert p["parameters"]["num_ctx"] == 2048 and p["variant"] == "m:custom"


def test_non_ollama_or_blockless_suits_yield_no_plan():
    assert ms.suit_ollama_plan(_suit(provider="anthropic")) is None
    assert ms.suit_ollama_plan({"provider": "ollama_local", "model_config": {"model_name": "x"}}) is None


def test_descriptive_keys_are_not_reported_unknown_keys_are():
    doc = _suit()
    doc["model_config"]["ollama_config"].update(quantization="Q4", ubatch=1024, mystery=1)
    p = ms.suit_ollama_plan(doc)
    # ubatch is llama.cpp's -ub; Ollama has no such parameter, so it is neither
    # sent to /api/create nor dropped silently -- it is reported as ignored.
    assert p["ignored"] == ["mystery", "ubatch"]
    assert "ubatch" not in p["parameters"]


def test_drift_compares_as_strings_the_way_ollama_reports_them():
    p = ms.suit_ollama_plan(_suit())
    assert ms.suit_ollama_drift(p, {"num_gpu": "999", "num_ctx": "8192"}) == {}
    assert ms.suit_ollama_drift(p, {"num_gpu": "999"}) == {"num_ctx": (8192, None)}


def test_offload_verdicts():
    p = ms.suit_ollama_plan(_suit())
    assert ms.suit_offload_verdict(p, {}).startswith("UNDECIDED")
    full = {"m:4b-pmoves": {"size": 5_000_000_000, "size_vram": 5_000_000_000}}
    part = {"m:4b-pmoves": {"size": 5_400_000_000, "size_vram": 3_200_000_000}}
    assert ms.suit_offload_verdict(p, full).startswith("VERIFIED")
    assert ms.suit_offload_verdict(p, part).startswith("DRIFTED")


def test_the_embedding_suit_plans_its_named_variant():
    plans = ms.suit_ollama_plans("qwen3-embedding-4b")
    assert len(plans) == 1
    assert plans[0]["variant"] == "qwen3-embedding:4b-pmoves"
    assert plans[0]["parameters"] == {"num_gpu": 999, "num_ctx": 8192}


def test_untagged_model_name_matches_ollama_listing():
    p = ms.suit_ollama_plan(_suit(model_config={"model_name": "nomic-embed-text",
                                                "ollama_config": {"num_gpu": 999}}))
    assert p["base"] == "nomic-embed-text:latest"
    assert p["variant"] == "nomic-embed-text:latest-pmoves"


def _fake_ollama(monkeypatch, blobs, params="num_gpu 999\nnum_ctx 8192", fail_create=False,
                 plans=None, bad_json_show=False):
    import argparse, io, json, urllib.error
    calls = []
    fail = set(blobs) if fail_create is True else set(fail_create or ())

    def api(path, body=None, timeout=600):
        calls.append((path, body))
        if path == "/api/tags":
            return {"models": [{"name": n} for n in blobs]}
        if path == "/api/ps":
            return {"models": []}
        if path == "/api/show":
            if bad_json_show:
                raise json.JSONDecodeError("Expecting value", "<html>502</html>", 0)
            return {"parameters": params, "modelfile": f"FROM /m/blobs/{blobs[body['model']]}"}
        if path == "/api/create":
            if body["from"] in fail:
                raise urllib.error.HTTPError("u", 500, "boom", {}, io.BytesIO())
            blobs[body["model"]] = blobs[body["from"]]
            return {}
        raise AssertionError(path)

    monkeypatch.setattr(ms, "_ollama_api", api)
    plans = plans or [ms.suit_ollama_plan(_suit())]
    monkeypatch.setattr(ms, "suit_ollama_plans", lambda suit: plans)
    return calls, argparse.Namespace


def test_repulled_base_is_drift_and_apply_rebuilds_the_variant(monkeypatch):
    blobs = {"m:4b": "sha256-new", "m:4b-pmoves": "sha256-old"}
    calls, ns = _fake_ollama(monkeypatch, blobs)
    assert ms.cmd_ollama_apply(ns(suit="", apply=False, check=True)) == 1
    assert ms.cmd_ollama_apply(ns(suit="", apply=True, check=False)) == 0
    assert blobs["m:4b-pmoves"] == "sha256-new"
    assert any(p == "/api/create" for p, _ in calls)


def test_api_error_is_a_clean_failure_not_a_traceback(monkeypatch, capsys):
    calls, ns = _fake_ollama(monkeypatch, {"m:4b": "sha256-a"}, fail_create=True)
    assert ms.cmd_ollama_apply(ns(suit="", apply=True, check=False)) == 1
    out = capsys.readouterr().out
    assert out.startswith("FAILED") and "Ollama API error" in out


def test_one_failing_suit_does_not_stop_the_rest(monkeypatch, capsys):
    second = _suit(name="t", model_config={"model_name": "n:1b", "ollama_config": {"num_gpu": 999}})
    plans = [ms.suit_ollama_plan(_suit()), ms.suit_ollama_plan(second)]
    blobs = {"m:4b": "sha256-a", "n:1b": "sha256-b"}
    calls, ns = _fake_ollama(monkeypatch, blobs, params="num_gpu 999",
                             fail_create={"m:4b"}, plans=plans)
    assert ms.cmd_ollama_apply(ns(suit="", apply=True, check=False)) == 1
    assert [b["from"] for p, b in calls if p == "/api/create"] == ["m:4b", "n:1b"]
    out = capsys.readouterr().out
    assert "APPLIED t: n:1b" in out and "1 of 2 suit(s) FAILED" in out


def test_non_json_reply_mid_apply_is_a_clean_failure(monkeypatch, capsys):
    calls, ns = _fake_ollama(monkeypatch, {"m:4b": "sha256-a", "m:4b-pmoves": "sha256-a"},
                             bad_json_show=True)
    assert ms.cmd_ollama_apply(ns(suit="", apply=False, check=True)) == 1
    assert "Ollama API error" in capsys.readouterr().out


def test_non_json_reply_from_tags_is_unreachable_not_a_traceback(monkeypatch, capsys):
    import argparse

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"<html>502 Bad Gateway</html>"

    monkeypatch.setattr(ms.urllib.request, "urlopen", lambda req, timeout=0: _Resp())
    monkeypatch.setattr(ms, "suit_ollama_plans", lambda suit: [ms.suit_ollama_plan(_suit())])
    assert ms.cmd_ollama_apply(argparse.Namespace(suit="", apply=False, check=False)) == 3
    assert "Ollama unreachable" in capsys.readouterr().out
