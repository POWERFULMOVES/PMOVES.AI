"""Chat-relay test configuration and fixtures."""

import os
import pytest


def postgres_available() -> bool:
    """Check if postgres is reachable for integration tests."""
    try:
        import psycopg
        conn = psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "pmoves"),
            password=os.getenv("POSTGRES_PASSWORD", "pmoves"),
            dbname=os.getenv("POSTGRES_DB", "pmoves"),
            connect_timeout=2
        )
        conn.close()
        return True
    except Exception:
        return False


# Skip marker for tests requiring postgres
requires_postgres = pytest.mark.skipif(
    not postgres_available(),
    reason="Postgres not available - skipping integration tests"
)


@pytest.fixture
def postgres_connection():
    """Provide a postgres connection for integration tests.

    Yields a connection that auto-rolls back after each test.
    """
    import psycopg
    conn = psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "pmoves"),
        password=os.getenv("POSTGRES_PASSWORD", "pmoves"),
        dbname=os.getenv("POSTGRES_DB", "pmoves"),
    )
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def supabase_config():
    """Provide Supabase configuration for tests."""
    return {
        "url": os.getenv("SUPABASE_URL", "http://localhost:54321"),
        "service_role_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
    }
