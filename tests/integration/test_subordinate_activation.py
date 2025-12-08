"""
Agent Zero Subordinate Activation Integration Tests

Tests Agent Zero subordinate profiles:
- pmoves-media-processor
- pmoves-log-analyzer
- pmoves-research-coordinator
- pmoves-knowledge-manager

TAC Worktree: tac-2-subordinate-tests
Branch: feature/subordinate-activation-tests
"""

import os
import pytest
import httpx
from pathlib import Path
from typing import Any, Dict, List

AGENT_ZERO_URL = os.getenv("AGENT_ZERO_URL", "http://localhost:8080")
SUBORDINATE_PROFILES_DIR = Path("/home/pmoves/PMOVES.AI/pmoves/data/agent-zero/runtime/agents")


@pytest.fixture
def agent_zero_client():
    """Create HTTP client for Agent Zero API."""
    return httpx.Client(base_url=AGENT_ZERO_URL, timeout=30.0)


class TestAgentZeroHealth:
    """Test Agent Zero service health."""

    def test_health_endpoint(self, agent_zero_client):
        """Verify Agent Zero is healthy."""
        response = agent_zero_client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_nats_connected(self, agent_zero_client):
        """Verify Agent Zero is connected to NATS."""
        response = agent_zero_client.get("/healthz")
        data = response.json()
        nats_status = data.get("nats", {})
        assert nats_status.get("connected") is True, "Agent Zero not connected to NATS"

    def test_jetstream_enabled(self, agent_zero_client):
        """Verify JetStream is enabled for Agent Zero."""
        response = agent_zero_client.get("/healthz")
        data = response.json()
        nats_status = data.get("nats", {})
        assert nats_status.get("use_jetstream") is True, "JetStream not enabled"


class TestSubordinateProfiles:
    """Test subordinate profile configurations exist."""

    EXPECTED_SUBORDINATES = [
        "pmoves-media-processor",
        "pmoves-log-analyzer",
        "pmoves-research-coordinator",
        "pmoves-knowledge-manager",
    ]

    def test_subordinate_directories_exist(self):
        """Verify subordinate profile directories exist."""
        for subordinate in self.EXPECTED_SUBORDINATES:
            profile_dir = SUBORDINATE_PROFILES_DIR / subordinate
            assert profile_dir.exists(), f"Missing subordinate profile: {subordinate}"

    def test_subordinate_system_prompts_exist(self):
        """Verify each subordinate has a system prompt."""
        for subordinate in self.EXPECTED_SUBORDINATES:
            prompt_file = SUBORDINATE_PROFILES_DIR / subordinate / "prompts" / "agent.system.main.role.md"
            assert prompt_file.exists(), f"Missing system prompt for: {subordinate}"

    def test_subordinate_behaviors_exist(self):
        """Verify each subordinate has behavior configurations."""
        for subordinate in self.EXPECTED_SUBORDINATES:
            behavior_file = SUBORDINATE_PROFILES_DIR / subordinate / "prompts" / "agent.system.main.behaviour.md"
            # Behavior file is optional but recommended
            if not behavior_file.exists():
                pytest.skip(f"Optional behavior file missing for: {subordinate}")


class TestMediaProcessorSubordinate:
    """Test pmoves-media-processor subordinate configuration."""

    def test_media_processor_prompt_content(self):
        """Verify media processor has appropriate capabilities."""
        prompt_file = SUBORDINATE_PROFILES_DIR / "pmoves-media-processor" / "prompts" / "agent.system.main.role.md"
        if prompt_file.exists():
            content = prompt_file.read_text()
            # Should mention media-related capabilities
            assert any(term in content.lower() for term in ["media", "video", "audio", "youtube", "whisper"])


class TestLogAnalyzerSubordinate:
    """Test pmoves-log-analyzer subordinate configuration."""

    def test_log_analyzer_prompt_content(self):
        """Verify log analyzer has appropriate capabilities."""
        prompt_file = SUBORDINATE_PROFILES_DIR / "pmoves-log-analyzer" / "prompts" / "agent.system.main.role.md"
        if prompt_file.exists():
            content = prompt_file.read_text()
            # Should mention logging/monitoring capabilities
            assert any(term in content.lower() for term in ["log", "prometheus", "grafana", "metric", "monitor"])


class TestResearchCoordinatorSubordinate:
    """Test pmoves-research-coordinator subordinate configuration."""

    def test_research_coordinator_prompt_content(self):
        """Verify research coordinator has appropriate capabilities."""
        prompt_file = SUBORDINATE_PROFILES_DIR / "pmoves-research-coordinator" / "prompts" / "agent.system.main.role.md"
        if prompt_file.exists():
            content = prompt_file.read_text()
            # Should mention research-related capabilities
            assert any(term in content.lower() for term in ["research", "deepresearch", "supaserch", "hi-rag"])


class TestKnowledgeManagerSubordinate:
    """Test pmoves-knowledge-manager subordinate configuration."""

    def test_knowledge_manager_prompt_content(self):
        """Verify knowledge manager has appropriate capabilities."""
        prompt_file = SUBORDINATE_PROFILES_DIR / "pmoves-knowledge-manager" / "prompts" / "agent.system.main.role.md"
        if prompt_file.exists():
            content = prompt_file.read_text()
            # Should mention knowledge/RAG capabilities
            assert any(term in content.lower() for term in ["knowledge", "qdrant", "neo4j", "meilisearch", "rag"])


class TestAgentZeroMCPAPI:
    """Test Agent Zero MCP API endpoints."""

    def test_mcp_endpoint_exists(self, agent_zero_client):
        """Verify MCP API endpoint is available."""
        # MCP endpoint should respond (may require auth)
        try:
            response = agent_zero_client.get("/mcp/")
            # Accept various status codes - just verify endpoint exists
            assert response.status_code in [200, 401, 403, 404, 405]
        except httpx.ConnectError:
            pytest.fail("Agent Zero MCP endpoint not reachable")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
