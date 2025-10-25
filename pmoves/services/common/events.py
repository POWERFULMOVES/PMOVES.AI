import json, os, uuid, datetime
from jsonschema import validate

def _contracts_dir() -> str:
    """Determines the directory where event contracts (schemas) are stored.

    The function checks for the contract directory in the following order:
    1. The path specified in the `PMOVES_CONTRACTS_DIR` environment variable.
    2. The `/app/contracts` directory (for containerized environments).
    3. A directory relative to this file (`pmoves/contracts`).
    4. Falls back to `/app/contracts`.

    Returns:
        The path to the contracts directory.
    """
    # Priority: explicit env, /app/contracts, repo-relative pmoves/contracts
    env_dir = os.environ.get("PMOVES_CONTRACTS_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir
    app_dir = "/app/contracts"
    if os.path.isdir(app_dir):
        return app_dir
    here = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.normpath(os.path.join(here, "..", "..", "contracts"))
    if os.path.isdir(repo_dir):
        return repo_dir
    # Fallback to /app/contracts; json loads will raise clearly if missing
    return app_dir

CONTRACTS_DIR = _contracts_dir()

def load_schema(topic: str):
    """Loads the JSON schema for a given event topic.

    Args:
        topic: The name of the event topic (e.g., 'content.published.v1').

    Raises:
        KeyError: If the topic is not defined in `topics.json`.

    Returns:
        The loaded JSON schema as a dictionary.
    """
    topics = json.loads(open(os.path.join(CONTRACTS_DIR, "topics.json")).read())
    if topic not in topics["topics"]:
        raise KeyError(f"Unknown topic: {topic}")
    schema_path = os.path.join(CONTRACTS_DIR, topics["topics"][topic]["schema"])
    return json.loads(open(schema_path).read())

def envelope(topic: str, payload: dict, correlation_id: str|None=None, parent_id: str|None=None, source: str="agent"):
    """Creates and validates a new event envelope.

    This function constructs a standard event envelope, validates both the
    envelope and the payload against their respective JSON schemas, and returns
    the final envelope.

    Args:
        topic: The event topic.
        payload: The event payload.
        correlation_id: An optional ID for tracking a chain of related events.
        parent_id: An optional ID of the event that caused this event.
        source: The name of the component that generated the event.

    Returns:
        The validated event envelope as a dictionary.
    """
    env = {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "version": "v1",
        "source": source,
        "payload": payload
    }
    env_schema = json.loads(open(os.path.join(CONTRACTS_DIR, "schemas/common/envelope.schema.json")).read())
    validate(instance=env, schema=env_schema)
    payload_schema = load_schema(topic)
    validate(instance=payload, schema=payload_schema)
    if correlation_id: env["correlation_id"] = correlation_id
    if parent_id: env["parent_id"] = parent_id
    return env

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

async def publish(topic: str, payload: dict, *, correlation_id: str | None = None, parent_id: str | None = None, source: str = "agent"):
    """Creates, validates, and publishes an event to NATS.

    This is a convenience function that wraps `envelope()` and handles the
    NATS connection and publishing.

    Args:
        topic: The event topic.
        payload: The event payload.
        correlation_id: An optional ID for tracking a chain of related events.
        parent_id: An optional ID of the event that caused this event.
        source: The name of the component that generated the event.

    Returns:
        The event envelope that was published.
    """
    from nats.aio.client import Client as NATS
    env = envelope(topic, payload, correlation_id=correlation_id, parent_id=parent_id, source=source)
    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    await nc.publish(topic, json.dumps(env).encode())
    await nc.close()
    return env
