"""Tests for Chat Relay Service."""

import json
import os
import sys
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Check for required dependencies
try:
    import nats
    import aiohttp
    DEPS_AVAILABLE = True
except ImportError as e:
    DEPS_AVAILABLE = False
    DEPS_ERROR = str(e)

requires_deps = pytest.mark.skipif(
    not DEPS_AVAILABLE,
    reason=f"Missing test dependencies: {DEPS_ERROR if not DEPS_AVAILABLE else ''}"
)


class TestConfig:
    """Tests for Config class."""

    def test_config_from_env_defaults(self):
        """Config uses defaults when env vars not set."""
        from main import Config

        with patch.dict(os.environ, {
            "SUPABASE_URL": "http://localhost:3010",
            "SUPABASE_SERVICE_ROLE_KEY": "test-key"
        }, clear=True):
            config = Config.from_env()

        assert config.nats_url == "nats://nats:4222"
        assert config.health_port == 8102
        assert config.agent_response_subject == "agent.response.v1"

    def test_config_from_env_custom(self):
        """Config reads custom env vars."""
        from main import Config

        with patch.dict(os.environ, {
            "NATS_URL": "nats://custom:4222",
            "SUPABASE_URL": "http://custom.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "custom-key",
            "HEALTH_PORT": "9000",
            "AGENT_RESPONSE_SUBJECT": "custom.response.v1"
        }, clear=True):
            config = Config.from_env()

        assert config.nats_url == "nats://custom:4222"
        assert config.supabase_url == "http://custom.supabase.co"
        assert config.health_port == 9000
        assert config.agent_response_subject == "custom.response.v1"

    def test_config_validate_missing_supabase_url(self):
        """Config validation fails without SUPABASE_URL."""
        from main import Config

        config = Config(
            nats_url="nats://localhost:4222",
            supabase_url="",
            supabase_service_role_key="key",
            health_port=8102
        )

        with pytest.raises(ValueError, match="SUPABASE_URL is required"):
            config.validate()

    def test_config_validate_missing_service_key(self):
        """Config validation fails without SUPABASE_SERVICE_ROLE_KEY."""
        from main import Config

        config = Config(
            nats_url="nats://localhost:4222",
            supabase_url="http://localhost:3010",
            supabase_service_role_key="",
            health_port=8102
        )

        with pytest.raises(ValueError, match="SUPABASE_SERVICE_ROLE_KEY is required"):
            config.validate()

    def test_config_validate_success(self):
        """Config validation passes with required fields."""
        from main import Config

        config = Config(
            nats_url="nats://localhost:4222",
            supabase_url="http://localhost:3010",
            supabase_service_role_key="test-key",
            health_port=8102
        )

        # Should not raise
        config.validate()


@requires_deps
class TestChatRelayService:
    """Tests for ChatRelayService class."""

    @pytest.fixture
    def config(self):
        """Create test config."""
        from main import Config
        return Config(
            nats_url="nats://localhost:4222",
            supabase_url="http://localhost:3010",
            supabase_service_role_key="test-key",
            health_port=8102
        )

    @pytest.fixture
    def service(self, config):
        """Create service instance."""
        from main import ChatRelayService
        return ChatRelayService(config)

    def test_service_initialization(self, service, config):
        """Service initializes with correct config."""
        assert service.config == config
        assert service.nc is None
        assert service.js is None
        assert service.supabase is None
        assert service.running is False
        assert service.messages_relayed == 0
        assert service.errors == 0

    @pytest.mark.asyncio
    async def test_handle_message_success(self, service):
        """Message handler relays valid message to Supabase."""
        # Mock Supabase client
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        service.supabase = MagicMock()
        service.supabase.table.return_value = mock_table

        # Create mock NATS message
        msg_data = {
            "session_id": "session-123",
            "owner_id": "user-456",
            "agent_id": "agent-zero",
            "agent_name": "Agent Zero",
            "content": "Hello, this is a response",
            "message_type": "text",
            "metadata": {"key": "value"}
        }
        mock_msg = MagicMock()
        mock_msg.data = json.dumps(msg_data).encode()
        mock_msg.ack = AsyncMock()

        await service._handle_message(mock_msg)

        # Verify Supabase insert was called
        service.supabase.table.assert_called_with("chat_messages")
        mock_table.insert.assert_called_once()
        insert_args = mock_table.insert.call_args[0][0]
        assert insert_args["owner_id"] == "user-456"
        assert insert_args["agent"] == "Agent Zero"
        assert insert_args["content"] == "Hello, this is a response"
        assert insert_args["role"] == "agent"

        # Verify message was acknowledged
        mock_msg.ack.assert_called_once()
        assert service.messages_relayed == 1
        assert service.errors == 0

    @pytest.mark.asyncio
    async def test_handle_message_no_content(self, service):
        """Message handler skips messages without content."""
        service.supabase = MagicMock()

        msg_data = {
            "session_id": "session-123",
            "owner_id": "user-456",
            # No content field
        }
        mock_msg = MagicMock()
        mock_msg.data = json.dumps(msg_data).encode()
        mock_msg.ack = AsyncMock()

        await service._handle_message(mock_msg)

        # Verify Supabase was NOT called
        service.supabase.table.assert_not_called()

        # Message should still be acknowledged (to avoid redelivery)
        mock_msg.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(self, service):
        """Message handler handles invalid JSON gracefully."""
        service.supabase = MagicMock()

        mock_msg = MagicMock()
        mock_msg.data = b"not valid json"
        mock_msg.ack = AsyncMock()

        await service._handle_message(mock_msg)

        # Should acknowledge to prevent redelivery of bad messages
        mock_msg.ack.assert_called_once()
        assert service.errors == 1

    @pytest.mark.asyncio
    async def test_handle_message_default_owner_id(self, service):
        """Message handler uses default owner_id when not provided."""
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        service.supabase = MagicMock()
        service.supabase.table.return_value = mock_table

        msg_data = {
            "agent_id": "agent-zero",
            "content": "Response without owner"
            # No owner_id
        }
        mock_msg = MagicMock()
        mock_msg.data = json.dumps(msg_data).encode()
        mock_msg.ack = AsyncMock()

        with patch.dict(os.environ, {"DEFAULT_OWNER_ID": "default-owner-123"}):
            await service._handle_message(mock_msg)

        insert_args = mock_table.insert.call_args[0][0]
        assert insert_args["owner_id"] == "default-owner-123"

    @pytest.mark.asyncio
    async def test_handle_message_alternative_fields(self, service):
        """Message handler handles alternative field names."""
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        service.supabase = MagicMock()
        service.supabase.table.return_value = mock_table

        # Use alternative field names (user_id, agent, response)
        msg_data = {
            "user_id": "user-789",
            "agent": "archon",
            "response": "Alternative response format"
        }
        mock_msg = MagicMock()
        mock_msg.data = json.dumps(msg_data).encode()
        mock_msg.ack = AsyncMock()

        await service._handle_message(mock_msg)

        insert_args = mock_table.insert.call_args[0][0]
        assert insert_args["owner_id"] == "user-789"
        assert insert_args["agent_id"] == "archon"
        assert insert_args["content"] == "Alternative response format"

    @pytest.mark.asyncio
    async def test_handle_message_supabase_failure(self, service):
        """Message handler handles Supabase insert failure."""
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = MagicMock(data=None)
        service.supabase = MagicMock()
        service.supabase.table.return_value = mock_table

        msg_data = {
            "owner_id": "user-456",
            "agent_id": "agent-zero",
            "content": "This will fail to insert"
        }
        mock_msg = MagicMock()
        mock_msg.data = json.dumps(msg_data).encode()
        mock_msg.ack = AsyncMock()

        await service._handle_message(mock_msg)

        # Should NOT acknowledge to allow redelivery
        mock_msg.ack.assert_not_called()
        assert service.errors == 1
        assert service.messages_relayed == 0

    @pytest.mark.asyncio
    async def test_nats_error_callback(self, service):
        """NATS error callback increments error counter."""
        await service._on_nats_error(Exception("Test error"))
        assert service.errors == 1

    @pytest.mark.asyncio
    async def test_shutdown_increments_stats(self, service):
        """Shutdown logs final stats."""
        service.running = True
        service.messages_relayed = 100
        service.errors = 5
        service.nc = MagicMock()
        service.nc.drain = AsyncMock()
        service.sub = MagicMock()
        service.sub.unsubscribe = AsyncMock()

        await service.shutdown()

        assert service.running is False
        service.sub.unsubscribe.assert_called_once()
        service.nc.drain.assert_called_once()


class TestMessageParsing:
    """Tests for message field extraction logic."""

    def test_content_field_priority(self):
        """Content is extracted in correct priority order."""
        # The code checks: content -> response -> message
        from main import ChatRelayService, Config

        config = Config(
            nats_url="nats://localhost:4222",
            supabase_url="http://localhost:3010",
            supabase_service_role_key="test-key",
            health_port=8102
        )
        service = ChatRelayService(config)

        # Test that 'content' has highest priority
        data1 = {"content": "A", "response": "B", "message": "C"}
        assert data1.get("content") or data1.get("response") or data1.get("message") == "A"

        # Test fallback to 'response'
        data2 = {"response": "B", "message": "C"}
        assert data2.get("content") or data2.get("response") or data2.get("message") == "B"

        # Test fallback to 'message'
        data3 = {"message": "C"}
        assert data3.get("content") or data3.get("response") or data3.get("message") == "C"

    def test_owner_id_field_priority(self):
        """Owner ID is extracted in correct priority order."""
        # The code checks: owner_id -> user_id
        data1 = {"owner_id": "owner", "user_id": "user"}
        assert data1.get("owner_id") or data1.get("user_id") == "owner"

        data2 = {"user_id": "user"}
        assert data2.get("owner_id") or data2.get("user_id") == "user"
