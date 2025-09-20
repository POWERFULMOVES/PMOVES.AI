import uuid
import datetime

def envelope(topic: str, payload: dict, correlation_id: str | None = None, parent_id: str | None = None, source: str = "pmoves-yt"):
    """Minimal schema-free envelope as a local shim for pmoves-yt.

    This makes `from services.common.events import envelope` resolve even when the
    shared repo module is not packaged into the container. It mirrors the local
    fallback used in yt.py.
    """
    env = {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "version": "v1",
        "source": source,
        "payload": payload,
    }
    if correlation_id:
        env["correlation_id"] = correlation_id
    if parent_id:
        env["parent_id"] = parent_id
    return env

