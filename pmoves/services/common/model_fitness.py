"""Model candidate and fitness helpers for the PMOVES model fabric.

TensorZero remains the source of truth for inference telemetry. Local
training/eval systems such as Pinokio and Unsloth contribute supplementary
metrics, but they do not directly activate a model without a signed trail.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

try:
    import yaml
except ImportError:  # pragma: no cover - runtime image should include PyYAML
    yaml = None

from pmoves.tools.chit_security import sign_cgp

_PMOVES_ROOT = Path(__file__).resolve().parents[2]
_AGENT_SIGNATURES = _PMOVES_ROOT / "config" / "agent_signatures.yaml"
_AGENT_REGISTRY = _PMOVES_ROOT / "config" / "agent_registry.yaml"
_SIGNING_CARDS = _PMOVES_ROOT / "config" / "signing_identity_cards.yaml"


@dataclass(frozen=True)
class AgentIdentityStatus:
    agent_id: str
    signature_exists: bool
    registry_ref_exists: bool
    active_card_exists: bool
    trusted: bool
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelCandidateRecord:
    model_id: str
    hf_id: str
    task: str | None
    license: str | None
    params: int | None
    context_length: int | None
    capabilities: list[str]
    backend_fit: list[str]
    vram_mb_estimate: int | None
    quantization_support: list[str]
    intended_lane: str
    validation_status: str = "candidate"
    source: str = "huggingface"
    agent_id: str = "codex"
    signed_trail_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not math.isfinite(number):
        number = default
    return max(0.0, min(1.0, number))


def _safe_nonnegative_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return max(number, 0.0)


def estimate_vram_mb(params: int | None, quantization: str = "fp16") -> int | None:
    """Estimate model VRAM footprint from parameter count and quantization."""

    if not params or params <= 0:
        return None
    bytes_per_param = {
        "fp32": 4.0,
        "bf16": 2.0,
        "fp16": 2.0,
        "int8": 1.0,
        "8bit": 1.0,
        "int4": 0.5,
        "4bit": 0.5,
        "gguf": 0.6,
    }.get(quantization.lower(), 2.0)
    overhead = 1.22
    return int((params * bytes_per_param * overhead) / (1024 * 1024))


def infer_capabilities(card: Mapping[str, Any]) -> list[str]:
    caps: set[str] = set(card.get("capabilities") or [])
    pipeline = str(card.get("pipeline_tag") or card.get("task") or "").lower()
    tags = {str(tag).lower() for tag in card.get("tags") or []}

    if pipeline in {"text-generation", "text2text-generation"}:
        caps.add("text_generation")
    if pipeline in {"feature-extraction", "sentence-similarity"}:
        caps.add("embeddings")
    if pipeline in {"image-to-text", "visual-question-answering"}:
        caps.add("vision_language")
    if pipeline in {"automatic-speech-recognition"}:
        caps.add("asr")
    if pipeline in {"text-to-speech"}:
        caps.add("tts")

    for tag in tags:
        if "coder" in tag or "code" in tag:
            caps.add("coding")
        if "instruct" in tag or "chat" in tag:
            caps.add("chat")
        if "embed" in tag:
            caps.add("embeddings")
        if "rerank" in tag:
            caps.add("reranking")
        if "tool" in tag or "function" in tag:
            caps.add("tool_use")
        if "vision" in tag or tag == "vl":
            caps.add("vision_language")
    return sorted(caps)


def infer_backend_fit(card: Mapping[str, Any]) -> list[str]:
    tags = {str(tag).lower() for tag in card.get("tags") or []}
    library = str(card.get("library_name") or "").lower()
    fits: set[str] = {"pinokio"}

    if library in {"transformers", "sentence-transformers"} or "transformers" in tags:
        fits.add("transformers")
    if "safetensors" in tags or "pytorch" in tags or "text-generation-inference" in tags:
        fits.add("vllm")
    if "gguf" in tags or "llama.cpp" in tags:
        fits.add("ollama")
    if "unsloth" in tags or "lora" in tags or "qlora" in tags:
        fits.add("unsloth")
    if "transformers" in fits and "vllm" in fits:
        fits.add("tensorzero")
    return sorted(fits)


def infer_quantization_support(card: Mapping[str, Any]) -> list[str]:
    tags = {str(tag).lower() for tag in card.get("tags") or []}
    params = card.get("params")
    support = {"fp16"}
    if params:
        support.update({"int8", "int4"})
    if "gguf" in tags:
        support.add("gguf")
    if "bitsandbytes" in tags or "4-bit" in tags or "8-bit" in tags:
        support.update({"int8", "int4"})
    return sorted(support)


def infer_intended_lane(capabilities: list[str]) -> str:
    caps = set(capabilities)
    if caps & {"coding", "tool_use"}:
        return "coding_agents"
    if caps & {"embeddings", "reranking"}:
        return "agent_mesh"
    if caps & {"tts", "asr", "vision_language"}:
        return "p7_and_skills"
    return "agent_mesh"


def build_model_candidate_record(
    card: Mapping[str, Any],
    *,
    agent_id: str = "codex",
    signed_trail_ref: str | None = None,
) -> ModelCandidateRecord:
    """Create a PMOVES model candidate record from HF-style metadata."""

    model_id = str(card.get("model_id") or card.get("hf_id") or card.get("id") or "")
    if not model_id:
        raise ValueError("model_id or hf_id is required")

    capabilities = infer_capabilities(card)
    quantization = infer_quantization_support(card)
    preferred_quant = "int4" if "int4" in quantization else "fp16"
    backend_fit = infer_backend_fit(card)

    return ModelCandidateRecord(
        model_id=model_id,
        hf_id=str(card.get("hf_id") or model_id),
        task=card.get("task") or card.get("pipeline_tag"),
        license=card.get("license"),
        params=card.get("params"),
        context_length=card.get("context_length"),
        capabilities=capabilities,
        backend_fit=backend_fit,
        vram_mb_estimate=estimate_vram_mb(card.get("params"), preferred_quant),
        quantization_support=quantization,
        intended_lane=infer_intended_lane(capabilities),
        agent_id=agent_id,
        signed_trail_ref=signed_trail_ref,
        metadata={
            "hf_url": card.get("hf_url"),
            "downloads": card.get("downloads", 0),
            "likes": card.get("likes", 0),
            "library_name": card.get("library_name"),
            "tags": list(card.get("tags") or []),
        },
    )


def normalize_model_fitness(
    tensorzero_metrics: Mapping[str, Any],
    training_metrics: Mapping[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Normalize TensorZero and optional training/eval metrics to 0..1."""

    training_metrics = training_metrics or {}
    success = clamp01(tensorzero_metrics.get("success_rate"), 0.5)
    task = clamp01(tensorzero_metrics.get("task_score"), success)
    tool = clamp01(tensorzero_metrics.get("tool_success_rate"), success)
    structured = clamp01(tensorzero_metrics.get("structured_output_valid_rate"), success)
    fallback_penalty = 1.0 - clamp01(tensorzero_metrics.get("fallback_rate"), 0.0)

    latency_ms = _safe_nonnegative_float(tensorzero_metrics.get("latency_ms"), None)
    latency_score = 0.5 if latency_ms is None else 1.0 / (1.0 + latency_ms / 5000.0)

    tps = _safe_nonnegative_float(tensorzero_metrics.get("tokens_per_second"), 0.0)
    throughput_score = min(1.0, tps / 80.0) if tps else 0.5

    cost = _safe_nonnegative_float(tensorzero_metrics.get("cost_per_1k_tokens"), None)
    cost_score = 0.5 if cost is None else 1.0 / (1.0 + cost)

    eval_score = clamp01(training_metrics.get("eval_score"), task)
    loss = training_metrics.get("loss")
    loss_value = _safe_nonnegative_float(loss, None) if loss is not None else None
    loss_score = 0.5 if loss_value is None else 1.0 / (1.0 + loss_value)
    publish_score = 1.0 if training_metrics.get("publish_eligible", False) else 0.5
    training_score = (eval_score * 0.6) + (loss_score * 0.25) + (publish_score * 0.15)

    score = (
        success * 0.22
        + task * 0.22
        + tool * 0.12
        + structured * 0.10
        + latency_score * 0.10
        + throughput_score * 0.07
        + cost_score * 0.05
        + fallback_penalty * 0.05
        + training_score * 0.07
    )

    normalized = {
        "success_rate": success,
        "task_score": task,
        "tool_success_rate": tool,
        "structured_output_valid_rate": structured,
        "latency_score": latency_score,
        "throughput_score": throughput_score,
        "cost_score": cost_score,
        "fallback_score": fallback_penalty,
        "training_score": training_score,
    }
    return round(clamp01(score), 6), normalized


def build_model_fitness_event(
    *,
    model_id: str,
    source: str,
    lane: str,
    tensorzero_metrics: Mapping[str, Any],
    training_metrics: Mapping[str, Any] | None = None,
    run_id: str | None = None,
    agent_id: str = "codex",
    passphrase: str | None = None,
) -> dict[str, Any]:
    """Build and CHIT-sign a model.fitness.recorded.v1 payload."""

    score, normalized = normalize_model_fitness(tensorzero_metrics, training_metrics)
    payload = {
        "model_id": model_id,
        "source": source,
        "lane": lane,
        "score": score,
        "metrics": {
            "tensorzero": dict(tensorzero_metrics),
            "training": dict(training_metrics or {}),
            "normalized": normalized,
        },
        "run_id": run_id or str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
    }
    signed = sign_cgp(payload, passphrase=passphrase)
    payload["signature"] = signed["sig"]
    return payload


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required for agent identity validation")
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def verify_agent_identity(
    agent_id: str,
    *,
    require_card: bool = True,
    pmoves_root: Path | None = None,
) -> AgentIdentityStatus:
    """Verify an agent has registry, signature, and optional signing-card presence."""

    root = pmoves_root or _PMOVES_ROOT
    signatures = _load_yaml(root / "config" / "agent_signatures.yaml").get("signatures", {})
    registry = _load_yaml(root / "config" / "agent_registry.yaml")
    cards = _load_yaml(root / "config" / "signing_identity_cards.yaml").get("cards", [])

    signature_exists = agent_id in signatures
    external = set(registry.get("external_contributors") or [])
    agent_entries = registry.get("agents") or {}
    registry_ref_exists = agent_id in external or any(
        key == agent_id or value.get("signature") == agent_id
        for key, value in agent_entries.items()
        if isinstance(value, dict)
    )
    active_card_exists = any(
        isinstance(card, dict)
        and card.get("active")
        and (card.get("h") or {}).get("agent_id") == agent_id
        for card in cards
    )

    errors: list[str] = []
    if not signature_exists:
        errors.append(f"{agent_id} missing from agent_signatures.yaml")
    if not registry_ref_exists:
        errors.append(f"{agent_id} missing from agent_registry.yaml")
    if require_card and not active_card_exists:
        errors.append(f"{agent_id} has no active signing identity card")

    return AgentIdentityStatus(
        agent_id=agent_id,
        signature_exists=signature_exists,
        registry_ref_exists=registry_ref_exists,
        active_card_exists=active_card_exists,
        trusted=not errors,
        errors=errors,
    )


def require_trusted_agent_identity(agent_id: str, *, require_card: bool = True) -> AgentIdentityStatus:
    status = verify_agent_identity(agent_id, require_card=require_card)
    if not status.trusted:
        raise ValueError("; ".join(status.errors))
    return status
