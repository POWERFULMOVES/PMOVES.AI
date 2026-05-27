import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from pmoves.services.common.model_fitness import (
    build_model_candidate_record,
    build_model_fitness_event,
    normalize_model_fitness,
    verify_agent_identity,
)
from pmoves.services.common.events import validate_payload
from pmoves.tools.hf_model_onboard import ModelCard, generate_model_candidate_record


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "pmoves" / "contracts"


def test_hf_candidate_record_infers_backend_vram_and_lane():
    card = {
        "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "hf_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "pipeline_tag": "text-generation",
        "task": "text-generation",
        "params": 7_000_000_000,
        "context_length": 32768,
        "license": "apache-2.0",
        "tags": ["transformers", "safetensors", "code", "instruct"],
        "library_name": "transformers",
        "downloads": 100,
        "likes": 10,
    }

    candidate = build_model_candidate_record(card, agent_id="agent-zero-codex", signed_trail_ref="trail-1")

    assert candidate.hf_id == "Qwen/Qwen2.5-Coder-7B-Instruct"
    assert candidate.intended_lane == "coding_agents"
    assert "tensorzero" in candidate.backend_fit
    assert "int4" in candidate.quantization_support
    assert candidate.vram_mb_estimate and candidate.vram_mb_estimate > 0
    assert candidate.signed_trail_ref == "trail-1"


def test_hf_onboard_cli_candidate_matches_common_builder():
    model_card = ModelCard(
        model_id="BAAI/bge-large-en-v1.5",
        name="bge-large-en-v1.5",
        author="BAAI",
        pipeline_tag="feature-extraction",
        task="feature-extraction",
        params=335_000_000,
        context_length=512,
        license="mit",
        tags=["sentence-transformers", "embeddings", "safetensors"],
        library_name="sentence-transformers",
        hf_url="https://huggingface.co/BAAI/bge-large-en-v1.5",
    )

    candidate = generate_model_candidate_record(model_card, agent_id="codex")

    assert candidate["intended_lane"] == "agent_mesh"
    assert "embeddings" in candidate["capabilities"]
    assert candidate["source"] == "huggingface"


def test_model_fitness_normalization_is_bounded_and_deterministic():
    tensorzero_metrics = {
        "success_rate": 0.9,
        "task_score": 0.8,
        "tool_success_rate": 0.75,
        "structured_output_valid_rate": 0.95,
        "latency_ms": 1200,
        "tokens_per_second": 64,
        "cost_per_1k_tokens": 0,
        "fallback_rate": 0.1,
    }
    training_metrics = {"eval_score": 0.82, "loss": 0.4, "publish_eligible": True}

    first, first_metrics = normalize_model_fitness(tensorzero_metrics, training_metrics)
    second, second_metrics = normalize_model_fitness(tensorzero_metrics, training_metrics)

    assert 0 <= first <= 1
    assert first == second
    assert first_metrics == second_metrics
    assert first_metrics["training_score"] > 0.5


def test_model_fitness_normalization_tolerates_malformed_metrics():
    score, metrics = normalize_model_fitness(
        {
            "success_rate": "not-a-number",
            "task_score": float("nan"),
            "latency_ms": ["bad"],
            "tokens_per_second": {"bad": True},
            "cost_per_1k_tokens": "bad",
        },
        {"eval_score": "bad", "loss": "bad", "publish_eligible": False},
    )

    assert 0 <= score <= 1
    assert metrics["latency_score"] == 0.5
    assert metrics["throughput_score"] == 0.5
    assert metrics["cost_score"] == 0.5


def test_signed_model_fitness_event_validates_against_contract(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-model-fitness-secret")
    event = build_model_fitness_event(
        model_id="Qwen/Qwen2.5-Coder-7B-Instruct",
        source="tensorzero",
        lane="coding_agents",
        tensorzero_metrics={"success_rate": 0.9, "task_score": 0.8},
        training_metrics={"eval_score": 0.8, "publish_eligible": True},
        run_id="run-1",
        agent_id="agent-zero-codex",
    )

    topics = json.loads((CONTRACTS_DIR / "topics.json").read_text(encoding="utf-8"))["topics"]
    schema_path = CONTRACTS_DIR / topics["model.fitness.recorded.v1"]["schema"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(event)
    validate_payload("model.fitness.recorded.v1", event)
    assert event["signature"]["alg"] == "HMAC-SHA256"


@pytest.mark.parametrize("agent_id", ["agent-zero-codex", "hermes", "coder_claw"])
def test_required_optimizer_identities_are_trusted(agent_id):
    status = verify_agent_identity(agent_id)

    assert status.trusted, status.errors
    assert status.signature_exists
    assert status.registry_ref_exists
    assert status.active_card_exists


def test_unknown_identity_is_not_trusted():
    status = verify_agent_identity("missing-agent")

    assert not status.trusted
    assert status.errors
