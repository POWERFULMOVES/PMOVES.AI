import os
from typing import Any, Dict, List, Optional
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

_client: Client | None = None

def client() -> Client:
    """Provides a singleton Supabase client instance.

    Initializes the client on first call.

    Raises:
        RuntimeError: If SUPABASE_URL or SUPABASE_KEY are not set.

    Returns:
        The Supabase client instance.
    """
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY required")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

def insert_detections(rows: List[Dict[str, Any]]) -> None:
    """Inserts rows into the 'detections' table.

    Args:
        rows: A list of dictionaries representing the rows to insert.
    """
    if rows:
        client().table("detections").insert(rows).execute()

def insert_segments(rows: List[Dict[str, Any]]) -> None:
    """Inserts rows into the 'segments' table.

    Args:
        rows: A list of dictionaries representing the rows to insert.
    """
    if rows:
        client().table("segments").insert(rows).execute()

def insert_emotions(rows: List[Dict[str, Any]]) -> None:
    """Inserts rows into the 'emotions' table.

    Args:
        rows: A list of dictionaries representing the rows to insert.
    """
    if rows:
        client().table("emotions").insert(rows).execute()



def upsert_row(table: str, row: Dict[str, Any], on_conflict: Optional[str] = None) -> None:
    """Inserts or updates a single row in a specified table.

    Args:
        table: The name of the table.
        row: The dictionary representing the row to upsert/insert.
        on_conflict: The column name to use for conflict resolution in an upsert.
            If None, a simple insert is performed.
    """
    query = client().table(table)
    if on_conflict:
        query = query.upsert(row, on_conflict=on_conflict)
    else:
        query = query.insert(row)
    query.execute()

def upsert_publisher_audit(row: Dict[str, Any]) -> None:
    """Upserts a row into the 'publisher_audit' table.

    This is a convenience function that specifically targets the 'publisher_audit'
    table and uses 'publish_event_id' for conflict resolution.

    Args:
        row: The dictionary representing the audit row to upsert.
    """
    if row:
        client().table("publisher_audit").upsert(row, on_conflict="publish_event_id").execute()

