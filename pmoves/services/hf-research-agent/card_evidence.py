"""Model-card evidence for the HF research worker.

The heuristics in ``main.py`` score Hub metadata (downloads, likes, tags). A
model's own card carries evidence those numbers cannot: the ``model-index``
block with reported benchmark results, the licence, the base model, and
whether the weights are gated. ``huggingface_hub`` parses ``model-index`` into
``ModelCardData.eval_results`` (``EvalResult`` objects); this module turns that
into a plain envelope the worker can score and publish, and nothing more.

This is the same surface the ``hugging-face-evaluation`` skill reads
(``ModelCard.load`` -> ``card.data``), so a score here and a model-index
written by that skill agree on their source. Operator ask, 2026-10-11: use the
huggingface skills to upgrade hf agent and hf researcher.

No network call is made at import time; ``huggingface_hub`` is imported lazily
so the worker starts (and the tests run) without it.
"""

from __future__ import annotations

from typing import Any

MAX_EVAL_RESULTS = 20

# Test seams: a test may set these to fakes instead of monkeypatching the Hub.
_HF_API: Any = None
_MODEL_CARD: Any = None


def _hub() -> tuple[Any, Any, Exception | None]:
    if _HF_API is not None and _MODEL_CARD is not None:
        return _HF_API, _MODEL_CARD, None
    try:
        from huggingface_hub import HfApi, ModelCard  # type: ignore
    except Exception as exc:  # ImportError and anything a broken install raises
        return None, None, exc
    return HfApi, ModelCard, None


def eval_results_from_card_data(data: Any) -> list[dict[str, Any]]:
    """Flatten ``ModelCardData.eval_results`` to plain dicts.

    Keeps only numeric metric values (a model-index entry with a string value
    is not evidence), caps the list, and never raises on a malformed entry.
    """
    results = getattr(data, "eval_results", None) or []
    out: list[dict[str, Any]] = []
    for entry in results:
        raw = getattr(entry, "metric_value", None)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "task": getattr(entry, "task_type", None) or "",
                "dataset": getattr(entry, "dataset_name", None) or getattr(entry, "dataset_type", None) or "",
                "metric": getattr(entry, "metric_name", None) or getattr(entry, "metric_type", None) or "",
                "value": value,
                "verified": bool(getattr(entry, "verified", False)),
            }
        )
        if len(out) >= MAX_EVAL_RESULTS:
            break
    return out


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return [str(value)]


def load_card_evidence(model_id: str, token: str | None = None) -> dict[str, Any]:
    """Read licence, base model, library, gated state and model-index results.

    Two Hub reads: the card (README front matter) and ``model_info`` (gated and
    library fields live there). Each failure is recorded under ``errors`` and
    the other read still counts; ``available`` is False only when both failed
    or the library is missing.
    """
    hf_api_cls, model_card_cls, err = _hub()
    if err is not None:
        return {"available": False, "errors": [f"huggingface_hub unavailable: {err}"], "eval_results": []}

    evidence: dict[str, Any] = {
        "available": True,
        "license": None,
        "base_model": [],
        "library_name": None,
        "gated": None,
        "eval_results": [],
        "errors": [],
    }
    try:
        card = model_card_cls.load(model_id, token=token or None)
        data = card.data
        evidence["license"] = getattr(data, "license", None) or None
        evidence["base_model"] = _as_list(getattr(data, "base_model", None))
        evidence["library_name"] = getattr(data, "library_name", None) or None
        evidence["eval_results"] = eval_results_from_card_data(data)
    except Exception as exc:
        evidence["errors"].append(f"card: {exc}")
    try:
        info = hf_api_cls(token=token or None).model_info(model_id)
        gated = getattr(info, "gated", None)
        evidence["gated"] = gated if gated is not None else None
        evidence["library_name"] = evidence["library_name"] or getattr(info, "library_name", None) or None
    except Exception as exc:
        evidence["errors"].append(f"model_info: {exc}")
    evidence["available"] = len(evidence["errors"]) < 2
    return evidence


def eval_job_recipe(model_id: str, task: str = "mmlu", flavor: str = "cpu-basic") -> str:
    """The HF Jobs command that would benchmark this model for real.

    Mirrors ``hugging-face-evaluation/scripts/run_eval_job.py`` (``--model``,
    ``--task``, ``--hardware``), which wraps ``hf jobs uv run --flavor ...
    --secrets HF_TOKEN``. Returned as text: this worker never submits a job
    or spends compute; an operator or a later lane does, deliberately.
    """
    return (
        "uv run <huggingface-skills>/hugging-face-evaluation/scripts/run_eval_job.py "
        f"--model {model_id} --task {task} --hardware {flavor}"
    )
