"""Work-order dispatcher: validate -> route -> decide. Pure handle_workorder is
unit-tested; run_responder wires it to NATS (live, not unit-tested)."""
from schemas import validate_workorder
from router import route
from config import Config


def handle_workorder(workorder: dict, nodes: list, models: dict) -> dict:
    try:
        validate_workorder(workorder)
    except Exception as exc:
        return {"decision": "rejected", "reason": str(exc)}

    r = route(workorder, nodes, models)
    if r["ok"]:
        return {
            "decision": "assigned",
            "node_id": r["node_id"],
            "reach": r["reach"],
            "subject": Config.SUBJECT_ASSIGNED,
            "workorder": workorder,
        }
    if r["reason"] == "license-not-acked":
        return {"decision": "refused", "reason": r["reason"]}
    return {"decision": "parked", "reason": r["reason"]}


async def run_responder():  # pragma: no cover - requires live NATS
    import json
    import nats
    from router import load_nodes
    from model_registry import load_models

    nodes = load_nodes(Config.NODES_PATH)
    models = load_models(Config.MODELS_PATH)
    nc = await nats.connect(Config.NATS_URL)

    async def _cb(m):
        out = handle_workorder(json.loads(m.data), nodes, models)
        if out["decision"] == "assigned":
            await nc.publish(Config.SUBJECT_ASSIGNED, json.dumps(out["workorder"]).encode())

    await nc.subscribe(Config.SUBJECT_WORKORDER, cb=_cb)
    return nc
