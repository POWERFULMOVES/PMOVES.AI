import json, os, uuid, datetime
from jsonschema import validate

def _contracts_dir() -> str:
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
    topics = json.loads(open(os.path.join(CONTRACTS_DIR, "topics.json")).read())
    if topic not in topics["topics"]:
        raise KeyError(f"Unknown topic: {topic}")
    schema_path = os.path.join(CONTRACTS_DIR, topics["topics"][topic]["schema"])
    return json.loads(open(schema_path).read())

def envelope(topic: str, payload: dict, correlation_id: str|None=None, parent_id: str|None=None, source: str="agent"):
    env = {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "ts": datetime.datetime.now(timezone.utc).isoformat() + "Z",
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
    """Publish an envelope to NATS and return the envelope."""
    from nats.aio.client import Client as NATS
    env = envelope(topic, payload, correlation_id=correlation_id, parent_id=parent_id, source=source)
    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    await nc.publish(topic, json.dumps(env).encode())
    await nc.close()
    return env
