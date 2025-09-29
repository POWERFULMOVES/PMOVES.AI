import os
from typing import List, Dict, Any
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

_client: Client | None = None

def client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY required")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

def insert_detections(rows: List[Dict[str, Any]]) -> None:
    if rows:
        client().table("detections").insert(rows).execute()

def insert_segments(rows: List[Dict[str, Any]]) -> None:
    if rows:
        client().table("segments").insert(rows).execute()

def insert_emotions(rows: List[Dict[str, Any]]) -> None:
    if rows:
        client().table("emotions").insert(rows).execute()


def upsert_publisher_audit(row: Dict[str, Any]) -> None:
    if row:
        client().table("publisher_audit").upsert(row, on_conflict="publish_event_id").execute()
