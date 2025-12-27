"""Chat-relay test configuration and fixtures."""

import os
import pytest


def postgres_available() -> bool:
    """Check if postgres is reachable for integration tests.

    Supports both Supabase CLI (port 65432) and docker-compose (port 5432).
    """
    try:
        import psycopg

        # Try environment variables first, then Supabase CLI defaults, then docker-compose defaults
        host = os.getenv("POSTGRES_HOST", "127.0.0.1")
        port = int(os.getenv("POSTGRES_PORT", "65432"))  # Supabase CLI default
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        dbname = os.getenv("POSTGRES_DB", "postgres")

        conn = psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            connect_timeout=2
        )
        conn.close()
        return True
    except Exception:
        # Try fallback to docker-compose defaults
        try:
            conn = psycopg.connect(
                host="localhost",
                port=5432,
                user="pmoves",
                password="pmoves",
                dbname="pmoves",
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


def _get_postgres_connection():
    """Get postgres connection, trying Supabase CLI first, then docker-compose."""
    import psycopg

    # Try Supabase CLI defaults first
    try:
        return psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", "65432")),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            dbname=os.getenv("POSTGRES_DB", "postgres"),
        )
    except Exception:
        # Fallback to docker-compose defaults
        return psycopg.connect(
            host="localhost",
            port=5432,
            user="pmoves",
            password="pmoves",
            dbname="pmoves",
        )


@pytest.fixture
def postgres_connection():
    """Provide a postgres connection for integration tests.

    Yields a connection that auto-rolls back after each test.
    """
    conn = _get_postgres_connection()
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
