"""Work-order dispatcher: validate -> route -> decide. Pure handle_workorder is
unit-tested; run_responder wires it to NATS (live, not unit-tested)."""
import json
from pathlib import Path
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
    if r["reason"] == "unknown-workflow":
        # Not parkable — an unregistered workflow won't become valid by waiting.
        return {"decision": "rejected", "reason": r["reason"]}
    return {"decision": "parked", "reason": r["reason"]}


def park_workorder(workorder: dict, pending_dir) -> Path:
    """Persist a parked (no-capacity) work-order so it is NOT dropped; a future
    slice re-dispatches from here when a node registers."""
    d = Path(pending_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{workorder['workorder_id']}.json"
    path.write_text(json.dumps(workorder), encoding="utf-8")
    return path


async def run_responder():  # pragma: no cover - requires live NATS
    import nats
    from router import load_nodes
    from model_registry import load_models

    nodes = load_nodes(Config.NODES_PATH)
    models = load_models(Config.MODELS_PATH)
    nc = await nats.connect(Config.NATS_URL)

    async def _cb(m):
        wo = json.loads(m.data)
        out = handle_workorder(wo, nodes, models)
        decision = out["decision"]
        if decision == "assigned":
            await nc.publish(Config.SUBJECT_ASSIGNED, json.dumps(out["workorder"]).encode())
        elif decision == "parked":
            park_workorder(wo, Config.PENDING_DIR)            # not dropped
        elif decision in ("refused", "rejected"):
            await nc.publish(Config.SUBJECT_GUIDANCE, json.dumps({
                "workorder_id": wo.get("workorder_id"),
                "decision": decision,
                "reason": out.get("reason"),
            }).encode())

    await nc.subscribe(Config.SUBJECT_WORKORDER, cb=_cb)
    return nc
