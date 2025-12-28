#!/usr/bin/env python3
"""
Unit Tests for AgentGym PPO Training Orchestrator.

Tests the PPOTrainingOrchestrator:
- Run ID validation (RUN_ID_PATTERN)
- start_training validates inputs
- cancel_training handles nonexistent jobs
- Training status tracking
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../services/agentgym-rl-coordinator")
)

from coordinator.training import PPOTrainingOrchestrator, RUN_ID_PATTERN


# ============================================================================
# Test PPOTrainingOrchestrator
# ============================================================================

class TestPPOTrainingOrchestrator:
    """Test PPO training orchestration functionality"""

    @pytest.fixture
    def orchestrator(self):
        """Create a test orchestrator instance"""
        return PPOTrainingOrchestrator(
            supabase_url="http://localhost:3010",
            supabase_key="test-key",
            vendor_path="/tmp/test_vendor",
        )

    def test_run_id_pattern_valid(self):
        """RUN_ID_PATTERN should match valid run IDs"""
        valid_ids = ["test-run", "test_run", "TestRun123", "my-ppo-experiment-01"]
        for run_id in valid_ids:
            assert RUN_ID_PATTERN.match(run_id), f"Should match: {run_id}"

    def test_run_id_pattern_invalid(self):
        """RUN_ID_PATTERN should reject invalid run IDs"""
        invalid_ids = ["", "test run", "test/run", "test.run", "test run!@#"]
        for run_id in invalid_ids:
            if run_id:  # Skip empty string for regex matching
                assert not RUN_ID_PATTERN.match(run_id), f"Should reject: {run_id}"

    @pytest.mark.asyncio
    async def test_start_training_validates_run_id_empty(self, orchestrator):
        """start_training should raise ValueError for empty run_id"""
        with pytest.raises(ValueError, match="run_id must be a non-empty string"):
            await orchestrator.start_training("")

    @pytest.mark.asyncio
    async def test_start_training_validates_run_id_invalid(self, orchestrator):
        """start_training should raise ValueError for invalid run_id characters"""
        with pytest.raises(ValueError, match=r"Invalid run_id.*Use only alphanumeric"):
            await orchestrator.start_training("test run with spaces")

    @pytest.mark.asyncio
    async def test_cancel_training_nonexistent_job(self, orchestrator):
        """cancel_training should return False for nonexistent job"""
        result = await orchestrator.cancel_training("nonexistent-job-12345")
        assert result is False

    def test_orchestrator_initialization(self, orchestrator):
        """Orchestrator should initialize with correct attributes"""
        assert orchestrator.supabase_url == "http://localhost:3010"
        assert orchestrator.vendor_path == "/tmp/test_vendor"
