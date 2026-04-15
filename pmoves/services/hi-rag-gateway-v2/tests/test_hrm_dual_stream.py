"""Tests for the enhanced HRM dual-stream sidecar package."""

import importlib
import math
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

repo_root = Path(__file__).resolve().parents[4]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

hrm_dir = str(Path(__file__).resolve().parent.parent / "hrm")
service_dir = str(Path(__file__).resolve().parent.parent)
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)

# ---------------------------------------------------------------------------
# Import HRM modules
# ---------------------------------------------------------------------------

from hrm import HRMSidecar, HRMSidecarConfig, PonderingController, HierarchicalReasoner
from hrm.sidecar import is_torch_available

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ===================================================================
# Test HRMSidecarConfig
# ===================================================================

class TestHRMSidecarConfig:
    def test_defaults(self):
        cfg = HRMSidecarConfig()
        assert cfg.enabled is False
        assert cfg.device == "cpu"
        assert cfg.fast_threshold == 0.3
        assert cfg.max_ponder_steps == 8
        assert cfg.min_ponder_steps == 1
        assert cfg.halt_threshold == 0.9
        assert cfg.d_model == 128
        assert cfg.nhead == 4
        assert cfg.reasoning_levels == 3

    def test_custom_values(self):
        cfg = HRMSidecarConfig(
            enabled=True,
            device="cuda",
            fast_threshold=0.5,
            max_ponder_steps=12,
        )
        assert cfg.enabled is True
        assert cfg.device == "cuda"
        assert cfg.fast_threshold == 0.5
        assert cfg.max_ponder_steps == 12


# ===================================================================
# Test HRMSidecar
# ===================================================================

class TestHRMSidecar:
    def test_disabled_returns_disabled_stream(self):
        """When HRM_ENABLED=False, process returns disabled stream."""
        cfg = HRMSidecarConfig(enabled=False)
        sidecar = HRMSidecar(cfg)
        result = sidecar.process([1.0, 2.0, 3.0])
        assert result["stream"] == "disabled"
        assert result["ponder_steps"] == 0
        assert result["embedding"] == [1.0, 2.0, 3.0]

    def test_fast_stream_low_complexity(self):
        """Queries with complexity < fast_threshold use fast stream."""
        cfg = HRMSidecarConfig(enabled=True, d_model=4, nhead=2, dim_feedforward=16)
        sidecar = HRMSidecar(cfg)
        result = sidecar.process(
            query_embedding=[1.0, 2.0, 3.0, 4.0],
            complexity_score=0.1,  # below default 0.3 threshold
        )
        assert result["stream"] == "fast"
        assert result["ponder_steps"] == 0
        assert result["reasoning_levels"] == 0
        assert "trace" in result
        assert result["trace"][0]["level"] == "fast"

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_deep_stream_high_complexity(self):
        """Queries with complexity >= fast_threshold use deep stream."""
        cfg = HRMSidecarConfig(
            enabled=True,
            d_model=4,
            nhead=2,
            dim_feedforward=16,
            max_ponder_steps=4,
        )
        sidecar = HRMSidecar(cfg)
        result = sidecar.process(
            query_embedding=torch.randn(4),
            complexity_score=0.8,  # above default 0.3 threshold
        )
        assert result["stream"] == "deep"
        assert result["complexity"] == 0.8
        assert result["ponder_steps"] >= 0
        assert "trace" in result

    def test_status_disabled(self):
        """Status endpoint reflects disabled state."""
        cfg = HRMSidecarConfig(enabled=False)
        sidecar = HRMSidecar(cfg)
        status = sidecar.status()
        assert status["enabled"] is False
        assert status["architecture"] == "dual-stream"

    def test_status_enabled(self):
        """Status endpoint reflects enabled state."""
        cfg = HRMSidecarConfig(enabled=True, d_model=4, nhead=2, dim_feedforward=16)
        sidecar = HRMSidecar(cfg)
        status = sidecar.status()
        assert status["enabled"] is True
        assert status["architecture"] == "dual-stream"
        assert "fast_threshold" in status
        assert "max_ponder_steps" in status

    def test_backward_compatibility_no_model(self):
        """Sidecar works without torch (no-op mode)."""
        cfg = HRMSidecarConfig(enabled=False)
        sidecar = HRMSidecar(cfg)
        # Should not raise even with None inputs
        result = sidecar.process(None, None)
        assert result["stream"] == "disabled"

    def test_estimate_complexity_heuristic(self):
        """Complexity estimation falls back to heuristic."""
        cfg = HRMSidecarConfig(enabled=True, d_model=4, nhead=2, dim_feedforward=16)
        sidecar = HRMSidecar(cfg)
        # With no context, complexity should be 0.0
        score = sidecar._estimate_complexity([1.0] * 4, None)
        assert score == 0.0

        # With 10 contexts, complexity should be 0.5
        contexts = [[float(i)] * 4 for i in range(10)]
        score = sidecar._estimate_complexity([1.0] * 4, contexts)
        assert score == 0.5

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_torch_tensor_passthrough(self):
        """Torch tensors are accepted as input."""
        cfg = HRMSidecarConfig(enabled=True, d_model=4, nhead=2, dim_feedforward=16)
        sidecar = HRMSidecar(cfg)
        t = torch.randn(4)
        result = sidecar.process(t, complexity_score=0.1)
        assert result["stream"] == "fast"


# ===================================================================
# Test PonderingController
# ===================================================================

class TestPonderingController:
    def test_defaults(self):
        pc = PonderingController()
        assert pc.min_steps == 1
        assert pc.max_steps == 8
        assert pc.halt_threshold == 0.9

    def test_custom_steps(self):
        pc = PonderingController(min_steps=2, max_steps=4, halt_threshold=0.8)
        assert pc.min_steps == 2
        assert pc.max_steps == 4
        assert pc.halt_threshold == 0.8

    def test_no_torch_returns_identity(self):
        """Without torch, ponder returns identity with 0 steps."""
        pc = PonderingController()
        # Test with plain data (not tensor)
        result, steps = pc.ponder("some_state")
        assert result == "some_state"
        assert steps == 0

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_ponder_with_tensor(self):
        """Ponder with torch tensor should return normalized state."""
        pc = PonderingController(
            min_steps=1, max_steps=4, halt_threshold=0.9,
            d_model=4, nhead=2, dim_feedforward=16,
        )
        state = torch.randn(1, 1, 4)
        result, steps = pc.ponder(state)
        assert isinstance(result, torch.Tensor)
        assert steps >= 0
        assert steps <= pc.max_steps

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_ponder_with_transform(self):
        """Ponder accepts a custom transform callable."""
        pc = PonderingController(
            min_steps=1, max_steps=3, halt_threshold=0.9,
            d_model=4, nhead=2, dim_feedforward=16,
        )
        state = torch.randn(1, 1, 4)

        call_count = 0
        def my_transform(x):
            nonlocal call_count
            call_count += 1
            return x + 0.01

        result, steps = pc.ponder(state, transform=my_transform)
        assert isinstance(result, torch.Tensor)

    def test_stats_tracking(self):
        """Pondering stats are tracked correctly."""
        pc = PonderingController()
        stats = pc.get_stats()
        assert stats["total_calls"] == 0
        assert stats["avg_steps"] == 0.0

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_stats_after_ponder(self):
        """Stats reflect actual ponder calls."""
        pc = PonderingController(
            min_steps=1, max_steps=4, halt_threshold=0.9,
            d_model=4, nhead=2, dim_feedforward=16,
        )
        state = torch.randn(1, 1, 4)
        pc.ponder(state)
        pc.ponder(state)
        stats = pc.get_stats()
        assert stats["total_calls"] == 2
        assert stats["avg_steps"] > 0

    def test_reset_stats(self):
        """Reset clears stats."""
        pc = PonderingController()
        pc._stats = [{"steps": 3}, {"steps": 5}]
        pc.reset_stats()
        assert pc.get_stats()["total_calls"] == 0


# ===================================================================
# Test HierarchicalReasoner
# ===================================================================

class TestHierarchicalReasoner:
    def test_defaults(self):
        r = HierarchicalReasoner()
        assert r.levels == 3

    def test_custom_levels(self):
        r = HierarchicalReasoner(levels=1)
        assert r.levels == 1

    def test_levels_clamped(self):
        r = HierarchicalReasoner(levels=10)
        assert r.levels == 3
        r = HierarchicalReasoner(levels=0)
        assert r.levels == 1

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_reason_with_tensor(self):
        """Reasoning produces trace entries for each level."""
        r = HierarchicalReasoner(levels=3)
        state = torch.randn(1, 1, 8)
        result = r.reason(state)
        assert "trace" in result
        assert len(result["trace"]) == 3
        assert result["trace"][0]["level"] == "surface"
        assert result["trace"][1]["level"] == "semantic"
        assert result["trace"][2]["level"] == "structural"

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_reason_single_level(self):
        """Single-level reasoning only produces one trace entry."""
        r = HierarchicalReasoner(levels=1)
        state = torch.randn(1, 1, 8)
        result = r.reason(state)
        assert len(result["trace"]) == 1
        assert result["trace"][0]["level"] == "surface"

    def test_reason_from_embeddings(self):
        """Embedding-based reasoning works without torch model."""
        r = HierarchicalReasoner(levels=3)
        result = r.reason_from_embeddings(
            query_embedding=[1.0, 2.0, 3.0],
            context_embeddings=[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        )
        assert "trace" in result
        assert len(result["trace"]) == 3
        assert result["trace"][0]["level"] == "surface"
        assert result["trace"][0]["action"] == "norm_analysis"
        assert result["trace"][1]["level"] == "semantic"
        assert result["trace"][1]["action"] == "context_similarity"
        assert result["trace"][2]["level"] == "structural"
        assert result["trace"][2]["action"] == "spread_analysis"

    def test_reason_from_embeddings_none(self):
        """Handles None embeddings gracefully."""
        r = HierarchicalReasoner()
        result = r.reason_from_embeddings(None, None)
        assert "trace" in result
        assert len(result["trace"]) == 3

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_surface_level_norm(self):
        """Surface level computes norm statistics."""
        r = HierarchicalReasoner(levels=1)
        state = torch.ones(1, 1, 4)
        result = r.reason(state)
        trace = result["trace"][0]
        assert trace["level"] == "surface"
        assert "mean_norm" in trace

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_semantic_level_similarity(self):
        """Semantic level computes similarity."""
        r = HierarchicalReasoner(levels=2)
        state = torch.randn(2, 1, 4)
        result = r.reason(state)
        trace = result["trace"][1]
        assert trace["level"] == "semantic"
        assert "avg_similarity" in trace

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_structural_level_variance(self):
        """Structural level computes variance."""
        r = HierarchicalReasoner(levels=3)
        state = torch.randn(1, 1, 8)
        result = r.reason(state)
        trace = result["trace"][2]
        assert trace["level"] == "structural"
        assert "structural_score" in trace


# ===================================================================
# Test config defaults via environment
# ===================================================================

class TestConfigDefaults:
    def test_hrm_disabled_by_default(self):
        """HRM is opt-in (disabled by default)."""
        cfg = HRMSidecarConfig()
        assert cfg.enabled is False

    def test_fast_threshold_default(self):
        """Fast threshold defaults to 0.3."""
        cfg = HRMSidecarConfig()
        assert cfg.fast_threshold == 0.3

    def test_max_ponder_steps_default(self):
        """Max ponder steps defaults to 8."""
        cfg = HRMSidecarConfig()
        assert cfg.max_ponder_steps == 8

    def test_halt_threshold_default(self):
        """Halt threshold defaults to 0.9."""
        cfg = HRMSidecarConfig()
        assert cfg.halt_threshold == 0.9


# ===================================================================
# Test is_torch_available
# ===================================================================

@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed in CI")
class TestTorchAvailability:
    def test_torch_available_consistent(self):
        """is_torch_available matches actual torch availability."""
        assert is_torch_available() is HAS_TORCH
