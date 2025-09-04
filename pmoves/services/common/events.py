import json, os, uuid, datetime
from jsonschema import validate

CONTRACTS_DIR = os.environ.get("PMOVES_CONTRACTS_DIR", "/app/contracts")

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
