import pytest

from pmoves.services.evoswarm.persona_optimizer import PersonaOptimizer


@pytest.mark.asyncio
async def test_evoswarm_optimizer_is_seeded_and_deterministic(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-evoswarm-secret")
    current = {
        "temperature": 0.15,
        "behavior_weights": {"decode": 0.8, "retrieve": 0.1, "generate": 0.1},
        "boosts": {"entity": 0.1, "keyword": 4.9},
    }
    eval_history = [{"pass": True}, {"pass": False}, {"pass": True}]

    first = PersonaOptimizer(max_iterations=12, population_size=8, random_seed=5090)
    second = PersonaOptimizer(max_iterations=12, population_size=8, random_seed=5090)

    first_best, first_fitness, first_metrics = await first._run_evoswarm_optimization(current, eval_history)
    second_best, second_fitness, second_metrics = await second._run_evoswarm_optimization(current, eval_history)

    assert first_best == second_best
    assert first_fitness == second_fitness
    assert first_metrics["operator"] == "deterministic_hybrid_pso_evolution"
    assert first_metrics["seed"] == second_metrics["seed"] == 5090


@pytest.mark.asyncio
async def test_evoswarm_optimizer_improves_baseline_and_signs_provenance(monkeypatch):
    monkeypatch.setenv("CHIT_PASSPHRASE", "test-evoswarm-secret")
    optimizer = PersonaOptimizer(max_iterations=16, population_size=10, random_seed=4482)
    current = {
        "temperature": 0.0,
        "behavior_weights": {"decode": 1.0, "retrieve": 0.0, "generate": 0.0},
        "boosts": {"entity": 0.0, "keyword": 5.0},
    }
    eval_history = [{"pass": True}, {"pass": True}, {"pass": False}]

    baseline = optimizer._compute_fitness(optimizer._normalize_candidate(current), eval_history)
    best, fitness, metrics = await optimizer._run_evoswarm_optimization(current, eval_history)

    assert fitness >= baseline
    assert metrics["fitness_improvement"] >= 0
    assert abs(sum(best["behavior_weights"].values()) - 1.0) < 0.00001
    assert 0 <= best["temperature"] <= 1
    assert 0 <= best["boosts"]["entity"] <= 5
    assert 0 <= best["boosts"]["keyword"] <= 5
    assert metrics["provenance"]["signature"]["alg"] == "HMAC-SHA256"
