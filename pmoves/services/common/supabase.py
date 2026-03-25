import os
from typing import Any, Dict, List, Optional
from supabase import create_client, Client

from .env import get_secret

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

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



def upsert_row(table: str, row: Dict[str, Any], on_conflict: Optional[str] = None) -> None:
    query = client().table(table)
    if on_conflict:
        query = query.upsert(row, on_conflict=on_conflict)
    else:
        query = query.insert(row)
    query.execute()

def upsert_publisher_audit(row: Dict[str, Any]) -> None:
    if row:
        client().table("publisher_audit").upsert(row, on_conflict="publish_event_id").execute()


def _extract_rpc_bool(result: Any) -> bool:
    if isinstance(result, bool):
        return result
    if isinstance(result, dict):
        for value in result.values():
            if isinstance(value, bool):
                return value
    if isinstance(result, list):
        for item in result:
            if isinstance(item, bool):
                return item
            if isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, bool):
                        return value
    return bool(result)


def _studio_board_meta(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def reconcile_studio_board_publish_completion(
    row_id: int,
    publish_event_id: str,
    published_event_id: Optional[str],
    published_at: Optional[str] = None,
    publish_meta: Optional[Dict[str, Any]] = None,
) -> bool:
    if not publish_event_id:
        return False

    response = (
        client()
        .table("studio_board")
        .select("id,status,meta")
        .eq("id", row_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        return False

    row = rows[0] if isinstance(rows[0], dict) else {}
    status = row.get("status")
    meta = _studio_board_meta(row.get("meta"))
    current_request_id = meta.get("publish_request_id")
    current_request_text = str(current_request_id) if current_request_id is not None else ""

    if status == "published":
        if current_request_text and current_request_text != publish_event_id:
            return False
        if published_event_id and meta.get("published_event_id") not in (None, published_event_id):
            return False
        return True

    if status not in ("approved", "publishing"):
        return False
    if current_request_text and current_request_text != publish_event_id:
        return False

    updated_meta = {
        key: value
        for key, value in meta.items()
        if key
        not in {
            "publish_failed_at",
            "publish_failure_reason",
            "publish_failure_stage",
            "publish_failure_meta",
        }
    }
    updated_meta.update(
        {
            "studio_board_id": row_id,
            "publish_state": "published",
            "publish_request_id": publish_event_id,
            "publish_event_sent_at": published_at,
            "published_at": published_at,
            "published_event_id": published_event_id,
        }
    )
    if publish_meta:
        for key, value in publish_meta.items():
            if value is not None:
                updated_meta[key] = value

    response = (
        client()
        .table("studio_board")
        .update(
            {
                "status": "published",
                "meta": updated_meta,
            }
        )
        .eq("id", row_id)
        .in_("status", ["approved", "publishing"])
        .execute()
    )
    updated_rows = getattr(response, "data", None) or []
    return len(updated_rows) > 0


def claim_studio_board_publish(
    row_id: int,
    publish_event_id: str,
    requested_at: Optional[str] = None,
) -> bool:
    params: Dict[str, Any] = {
        "p_row_id": row_id,
        "p_publish_event_id": publish_event_id,
    }
    if requested_at:
        params["p_requested_at"] = requested_at
    response = client().rpc("claim_studio_board_publish", params).execute()
    return _extract_rpc_bool(getattr(response, "data", None))


def complete_studio_board_publish(
    row_id: int,
    publish_event_id: str,
    published_event_id: Optional[str],
    published_at: Optional[str] = None,
    publish_meta: Optional[Dict[str, Any]] = None,
) -> bool:
    params: Dict[str, Any] = {
        "p_row_id": row_id,
        "p_publish_event_id": publish_event_id,
        "p_published_event_id": published_event_id,
        "p_publish_meta": publish_meta or {},
    }
    if published_at:
        params["p_published_at"] = published_at
    response = client().rpc("complete_studio_board_publish", params).execute()
    return _extract_rpc_bool(getattr(response, "data", None))


def fail_studio_board_publish(
    row_id: int,
    publish_event_id: str,
    stage: str,
    reason: str,
    failed_at: Optional[str] = None,
    failure_meta: Optional[Dict[str, Any]] = None,
) -> bool:
    params: Dict[str, Any] = {
        "p_row_id": row_id,
        "p_publish_event_id": publish_event_id,
        "p_stage": stage,
        "p_reason": reason,
        "p_failure_meta": failure_meta or {},
    }
    if failed_at:
        params["p_failed_at"] = failed_at
    response = client().rpc("fail_studio_board_publish", params).execute()
    return _extract_rpc_bool(getattr(response, "data", None))
