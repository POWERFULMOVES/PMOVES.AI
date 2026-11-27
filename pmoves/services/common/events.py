import json
import os
import uuid
import datetime
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker, RefResolver, validate

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

class UnknownTopicError(KeyError):
    """Raised when a topic is not registered in contracts/topics.json.

    Subclasses KeyError so existing ``except KeyError`` callers keep working,
    while HTTP surfaces can map it to a 4xx instead of an unhandled 500.
    """

    def __init__(self, topic: str):
        super().__init__(f"Unknown topic: {topic}")
        self.topic = topic


def _load_topics() -> dict:
    return json.loads(open(os.path.join(CONTRACTS_DIR, "topics.json")).read())["topics"]

def known_topics() -> list[str]:
    """Sorted names of every topic registered in contracts/topics.json."""
    return sorted(_load_topics())

def load_schema(topic: str):
    return json.loads(open(schema_path(topic)).read())

def schema_path(topic: str) -> str:
    topics = _load_topics()
    if topic not in topics:
        raise UnknownTopicError(topic)
    return os.path.join(CONTRACTS_DIR, topics[topic]["schema"])

def validate_payload(topic: str, payload: dict):
    """Validate a topic payload, resolving schema-local relative refs."""
    path = schema_path(topic)
    schema = json.loads(open(path).read())
    resolver = RefResolver(
        base_uri=Path(path).resolve().as_uri(),
        referrer=schema,
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(
        schema,
        resolver=resolver,
        format_checker=FormatChecker(),
    ).validate(payload)
    return payload

def envelope(topic: str, payload: dict, correlation_id: str|None=None, parent_id: str|None=None, source: str="agent"):
    env = {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
        "version": "v1",
        "source": source,
        "payload": payload
    }
    env_schema = json.loads(open(os.path.join(CONTRACTS_DIR, "schemas/common/envelope.schema.json")).read())
    validate(instance=env, schema=env_schema)
    validate_payload(topic, payload)
    if correlation_id: env["correlation_id"] = correlation_id
    if parent_id: env["parent_id"] = parent_id
    return env

NATS_URL = os.environ.get("NATS_URL", "")

async def publish(topic: str, payload: dict, *, correlation_id: str | None = None, parent_id: str | None = None, source: str = "agent"):
    """Publish an envelope to NATS and return the envelope."""
    from nats.aio.client import Client as NATS
    env = envelope(topic, payload, correlation_id=correlation_id, parent_id=parent_id, source=source)
    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    await nc.publish(topic, json.dumps(env).encode())
    await nc.close()
    return env
