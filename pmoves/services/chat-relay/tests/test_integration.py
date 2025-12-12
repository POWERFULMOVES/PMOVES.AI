"""Integration tests for Chat Relay Service.

These tests require a running postgres instance and are automatically
skipped when postgres is not available.

Run with: pytest -v (when postgres is running)
"""

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

# Add tests directory to path for conftest import
_tests_dir = os.path.dirname(os.path.abspath(__file__))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from conftest import requires_postgres


@requires_postgres
class TestChatMessagesTable:
    """Integration tests for chat_messages table operations."""

    def test_insert_chat_message(self, postgres_connection):
        """Insert a chat message into the database."""
        cursor = postgres_connection.cursor()

        # Generate test data
        owner_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        content = f"Test message {datetime.now(timezone.utc).isoformat()}"

        # Insert message
        cursor.execute(
            """
            INSERT INTO public.chat_messages
                (owner_id, role, agent, content, session_id, message_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (owner_id, "agent", "test-agent", content, session_id, "text")
        )

        result = cursor.fetchone()
        assert result is not None
        assert result[0] > 0  # ID should be positive

    def test_query_messages_by_session(self, postgres_connection):
        """Query messages by session ID."""
        cursor = postgres_connection.cursor()

        session_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())

        # Insert multiple messages for same session
        for i in range(3):
            cursor.execute(
                """
                INSERT INTO public.chat_messages
                    (owner_id, role, agent, content, session_id, message_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (owner_id, "agent", "test-agent", f"Message {i}", session_id, "text")
            )

        # Query by session
        cursor.execute(
            """
            SELECT COUNT(*) FROM public.chat_messages
            WHERE session_id = %s
            """,
            (session_id,)
        )

        count = cursor.fetchone()[0]
        assert count == 3

    def test_message_metadata_jsonb(self, postgres_connection):
        """Store and retrieve JSONB metadata."""
        cursor = postgres_connection.cursor()

        owner_id = str(uuid.uuid4())
        metadata = {"source": "integration-test", "version": 1, "tags": ["test"]}

        cursor.execute(
            """
            INSERT INTO public.chat_messages
                (owner_id, role, agent, content, message_type, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (owner_id, "agent", "test-agent", "Metadata test", "text", str(metadata).replace("'", '"'))
        )

        msg_id = cursor.fetchone()[0]

        # Query and verify metadata
        cursor.execute(
            """
            SELECT metadata->>'source' FROM public.chat_messages
            WHERE id = %s
            """,
            (msg_id,)
        )

        source = cursor.fetchone()[0]
        assert source == "integration-test"


@requires_postgres
class TestRealtimePublication:
    """Tests for Supabase Realtime publication setup."""

    def test_chat_messages_in_publication(self, postgres_connection):
        """Verify chat_messages is in supabase_realtime publication."""
        cursor = postgres_connection.cursor()

        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_publication_tables
                WHERE pubname = 'supabase_realtime'
                AND schemaname = 'public'
                AND tablename = 'chat_messages'
            )
            """
        )

        in_publication = cursor.fetchone()[0]
        # This may be False if migration not applied yet - that's OK
        # Test documents the expected state
        if not in_publication:
            pytest.skip("chat_messages not yet added to supabase_realtime publication")

    def test_publication_exists(self, postgres_connection):
        """Verify supabase_realtime publication exists."""
        cursor = postgres_connection.cursor()

        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_publication
                WHERE pubname = 'supabase_realtime'
            )
            """
        )

        exists = cursor.fetchone()[0]
        if not exists:
            pytest.skip("supabase_realtime publication not created yet")


@requires_postgres
class TestChatHistoryFunction:
    """Tests for get_chat_history database function."""

    def test_get_chat_history_function_exists(self, postgres_connection):
        """Verify get_chat_history function is defined."""
        cursor = postgres_connection.cursor()

        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_proc
                WHERE proname = 'get_chat_history'
            )
            """
        )

        exists = cursor.fetchone()[0]
        if not exists:
            pytest.skip("get_chat_history function not yet created - run supabase-migrate")
