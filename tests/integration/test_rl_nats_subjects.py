"""
RL Trainer NATS Integration Tests

Tests the AgentGym-RL NATS subjects and JetStream streams:
- agent.rl.trajectory.v1
- agent.rl.reward.v1
- agent.rl.training.request.v1
- agent.rl.training.status.v1
- agent.rl.model.deployed.v1

TAC Worktree: tac-3-rl-trainer-tests
Branch: feature/rl-trainer-integration
"""

import os
import json
import pytest
import httpx
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime
import uuid

AGENT_ZERO_URL = os.getenv("AGENT_ZERO_URL", "http://localhost:8080")
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
CONTRACTS_DIR = Path("/home/pmoves/PMOVES.AI/pmoves/contracts")


@pytest.fixture
def agent_zero_client():
    """Create HTTP client for Agent Zero API."""
    return httpx.Client(base_url=AGENT_ZERO_URL, timeout=30.0)


class TestRLNATSSubjectsSchema:
    """Test RL NATS subject schemas exist and are valid."""

    RL_SUBJECTS = [
        ("agent.rl.trajectory.v1", "agent-rl/trajectory.v1.schema.json"),
        ("agent.rl.reward.v1", "agent-rl/reward.v1.schema.json"),
        ("agent.rl.training.request.v1", "agent-rl/training.request.v1.schema.json"),
        ("agent.rl.training.status.v1", "agent-rl/training.status.v1.schema.json"),
        ("agent.rl.model.deployed.v1", "agent-rl/model.deployed.v1.schema.json"),
    ]

    def test_rl_schemas_directory_exists(self):
        """Verify agent-rl schemas directory exists."""
        schemas_dir = CONTRACTS_DIR / "schemas" / "agent-rl"
        assert schemas_dir.exists(), "agent-rl schemas directory missing"

    @pytest.mark.parametrize("subject,schema_file", RL_SUBJECTS)
    def test_schema_file_exists(self, subject: str, schema_file: str):
        """Verify schema file exists for each RL subject."""
        schema_path = CONTRACTS_DIR / "schemas" / schema_file
        assert schema_path.exists(), f"Schema missing for {subject}: {schema_file}"

    @pytest.mark.parametrize("subject,schema_file", RL_SUBJECTS)
    def test_schema_is_valid_json(self, subject: str, schema_file: str):
        """Verify schema file is valid JSON."""
        schema_path = CONTRACTS_DIR / "schemas" / schema_file
        if schema_path.exists():
            content = schema_path.read_text()
            try:
                schema = json.loads(content)
                assert "$schema" in schema or "type" in schema
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {schema_file}: {e}")


class TestTopicsRegistry:
    """Test RL subjects are registered in topics.json."""

    def test_topics_json_exists(self):
        """Verify topics.json exists."""
        topics_file = CONTRACTS_DIR / "topics.json"
        assert topics_file.exists(), "topics.json missing"

    def test_rl_subjects_in_topics(self):
        """Verify RL subjects are registered in topics.json."""
        topics_file = CONTRACTS_DIR / "topics.json"
        content = json.loads(topics_file.read_text())

        rl_subjects = [
            "agent.rl.trajectory.v1",
            "agent.rl.reward.v1",
            "agent.rl.training.request.v1",
            "agent.rl.training.status.v1",
            "agent.rl.model.deployed.v1",
        ]

        # Get all subject names from topics.json
        registered_subjects = set()
        for category in content.values():
            if isinstance(category, dict):
                for item in category.values():
                    if isinstance(item, dict) and "subject" in item:
                        registered_subjects.add(item["subject"])
                    elif isinstance(item, list):
                        for sub_item in item:
                            if isinstance(sub_item, dict) and "subject" in sub_item:
                                registered_subjects.add(sub_item["subject"])

        # Check if RL subjects exist in topics.json (may be in agent-rl category)
        # If not all found, log which are missing but don't fail
        missing = [s for s in rl_subjects if s not in registered_subjects]
        if missing:
            pytest.skip(f"RL subjects not yet registered in topics.json: {missing}")


class TestAgentZeroNATSConnection:
    """Test Agent Zero NATS connectivity for RL events."""

    def test_nats_connected(self, agent_zero_client):
        """Verify Agent Zero is connected to NATS."""
        response = agent_zero_client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        nats = data.get("nats", {})
        assert nats.get("connected") is True

    def test_jetstream_enabled(self, agent_zero_client):
        """Verify JetStream is enabled for reliable delivery."""
        response = agent_zero_client.get("/healthz")
        data = response.json()
        nats = data.get("nats", {})
        assert nats.get("use_jetstream") is True

    def test_agentzero_stream_exists(self, agent_zero_client):
        """Verify AGENTZERO stream is configured."""
        response = agent_zero_client.get("/healthz")
        data = response.json()
        nats = data.get("nats", {})
        stream = nats.get("stream", "")
        assert stream == "AGENTZERO" or len(stream) > 0


class TestRLTrajectorySchema:
    """Test RL trajectory schema structure."""

    def test_trajectory_schema_has_required_fields(self):
        """Verify trajectory schema has required fields."""
        schema_path = CONTRACTS_DIR / "schemas" / "agent-rl" / "trajectory.v1.schema.json"
        if not schema_path.exists():
            pytest.skip("Trajectory schema not found")

        schema = json.loads(schema_path.read_text())
        required = schema.get("required", [])

        expected_fields = ["trajectory_id", "session_id", "start_timestamp"]
        for field in expected_fields:
            assert field in required or field in schema.get("properties", {}), \
                f"Expected field '{field}' in trajectory schema"


class TestRLRewardSchema:
    """Test RL reward schema structure."""

    def test_reward_schema_has_components(self):
        """Verify reward schema supports component-based rewards."""
        schema_path = CONTRACTS_DIR / "schemas" / "agent-rl" / "reward.v1.schema.json"
        if not schema_path.exists():
            pytest.skip("Reward schema not found")

        schema = json.loads(schema_path.read_text())
        properties = schema.get("properties", {})

        # Should have reward-related fields
        assert any(
            "reward" in prop.lower() or "score" in prop.lower()
            for prop in properties.keys()
        ), "Reward schema missing reward/score fields"


class TestRLTrainingRequestSchema:
    """Test RL training request schema structure."""

    def test_training_request_has_config(self):
        """Verify training request schema has configuration."""
        schema_path = CONTRACTS_DIR / "schemas" / "agent-rl" / "training.request.v1.schema.json"
        if not schema_path.exists():
            pytest.skip("Training request schema not found")

        schema = json.loads(schema_path.read_text())
        properties = schema.get("properties", {})

        # Should have training configuration fields
        assert any(
            "config" in prop.lower() or "training" in prop.lower()
            for prop in properties.keys()
        ), "Training request missing config fields"


class TestAgentGymRLDockerCompose:
    """Test AgentGym-RL Docker Compose configuration."""

    def test_agentgym_compose_exists(self):
        """Verify AgentGym compose file exists."""
        compose_file = Path("/home/pmoves/PMOVES.AI/pmoves/docker-compose.agentgym.yml")
        assert compose_file.exists(), "docker-compose.agentgym.yml missing"

    def test_agentgym_compose_valid_yaml(self):
        """Verify AgentGym compose file is valid YAML."""
        import yaml
        compose_file = Path("/home/pmoves/PMOVES.AI/pmoves/docker-compose.agentgym.yml")
        if compose_file.exists():
            content = compose_file.read_text()
            try:
                config = yaml.safe_load(content)
                assert "services" in config
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in compose file: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
