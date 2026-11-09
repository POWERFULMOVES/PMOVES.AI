"""Tests for the model-fitness-bridge event handlers."""

import asyncio
import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Model IDs used in tests are abstract — the bridge is model-agnostic.
# In production, model_ids come from live HF discovery (hf-agent) or
# the model-registry API — never hardcoded.
TEST_MODEL = "test-benchmark-model"
TEST_RL_MODEL = "test-rl-adapter"
TEST_HF_REPO = "powerfulmoves/test-rl-published"


# --- Benchmark handler tests ---

@pytest.mark.asyncio
async def test_benchmark_completed_normalizes_tps():
    """High throughput → high score."""
    from app import on_benchmark_completed

    with patch("app.call_model_fitness", new_callable=AsyncMock) as mock:
        await on_benchmark_completed({
            "model": TEST_MODEL,
            "tokens_per_second": 100,
            "latency_ms": 500,
            "errors": 0,
            "total_requests": 10,
            "lane": "chat",
        })
        mock.assert_called_once()
        call_kwargs = mock.call_args.kwargs
        assert call_kwargs["source"] == "pinokio"
        assert call_kwargs["model_id"] == TEST_MODEL
        assert 0.8 < call_kwargs["score"] <= 1.0


@pytest.mark.asyncio
async def test_benchmark_completed_zero_tps():
    """Zero throughput → low score."""
    from app import on_benchmark_completed

    with patch("app.call_model_fitness", new_callable=AsyncMock) as mock:
        await on_benchmark_completed({
            "model": TEST_MODEL,
            "tokens_per_second": 0,
            "errors": 5,
            "total_requests": 10,
        })
        mock.assert_called_once()
        assert mock.call_args.kwargs["score"] < 0.5


@pytest.mark.asyncio
async def test_benchmark_score_clamped_0_1():
    """Score must be in [0, 1]."""
    from app import on_benchmark_completed

    with patch("app.call_model_fitness", new_callable=AsyncMock) as mock:
        await on_benchmark_completed({
            "model": "extreme-bench",
            "tokens_per_second": 999999,
            "latency_ms": 0,
            "errors": 0,
            "total_requests": 1,
        })
        assert mock.call_args.kwargs["score"] <= 1.0


# --- AgentGym handler tests ---

@pytest.mark.asyncio
async def test_agentgym_train_completed():
    """RL training completion records fitness."""
    from app import on_agentgym_train_completed

    with patch("app.call_model_fitness", new_callable=AsyncMock) as mock:
        await on_agentgym_train_completed({
            "model_id": TEST_RL_MODEL,
            "mean_reward_normalized": 0.85,
            "episodes": 100,
            "training_steps": 5000,
        })
        mock.assert_called_once()
        assert mock.call_args.kwargs["source"] == "evoswarm"
        assert mock.call_args.kwargs["score"] == 0.85


@pytest.mark.asyncio
async def test_agentgym_model_published_registers_candidate():
    """Model publication registers a new candidate."""
    from app import on_agentgym_model_published

    with patch("app.call_model_candidates", new_callable=AsyncMock) as mock:
        await on_agentgym_model_published({
            "hf_id": TEST_HF_REPO,
            "mean_reward_normalized": 0.9,
        })
        mock.assert_called_once()
        assert mock.call_args.kwargs["hf_id"] == TEST_HF_REPO


@pytest.mark.asyncio
async def test_agentgym_published_no_hf_id_skips():
    """Missing hf_id should not crash."""
    from app import on_agentgym_model_published

    with patch("app.call_model_candidates", new_callable=AsyncMock) as mock:
        await on_agentgym_model_published({"model_name": "test"})
        mock.assert_not_called()


# --- Fitness API caller tests ---

@pytest.mark.asyncio
async def test_call_model_fitness_success():
    from app import call_model_fitness

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok"}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = await call_model_fitness(
            model_id=TEST_MODEL,
            source="pinokio",
            lane="chat",
            score=0.8,
            metrics={"tps": 50},
        )
        assert result["status"] == "ok"


# --- Health endpoint test ---

def test_healthz():
    from fastapi.testclient import TestClient
    from app import app

    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "model-fitness-bridge"
    assert "llama.benchmark.completed.v1" in resp.json()["subjects"]
