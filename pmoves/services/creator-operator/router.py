"""Capacity routing + license gate for creator work-orders."""
from pathlib import Path
import yaml
from model_registry import lookup_model, requires_ack


def load_nodes(path: Path) -> list:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data.get("nodes", [])


def select_node(node_caps: dict, nodes: list):
    """Lowest-VRAM node that satisfies min_vram_gb and all required caps."""
    need = set(node_caps.get("needs", []))
    min_vram = node_caps.get("min_vram_gb", 0)
    candidates = [
        n for n in nodes
        if n.get("vram_gb", 0) >= min_vram and need.issubset(set(n.get("caps", [])))
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda n: n.get("vram_gb", 0))


def route(workorder: dict, nodes: list, models: dict) -> dict:
    """License gate first, then capacity match. Returns a RouteResult dict."""
    # workflow_id comes from external input (Archon/Discord) and the schema accepts
    # any non-empty string, so an unregistered id is a routine case, not a crash:
    # surface it as unknown-workflow (dispatcher maps to rejected), never a KeyError.
    try:
        model = lookup_model(models, workorder["workflow_id"])
    except KeyError:
        return {"ok": False, "node_id": None, "reason": "unknown-workflow"}
    ack = workorder.get("license_ack", {})
    if requires_ack(model) and not ack.get("ack", False):
        return {"ok": False, "node_id": None, "reason": "license-not-acked"}
    node = select_node(workorder["node_caps"], nodes)
    if node is None:
        return {"ok": False, "node_id": None, "reason": "no-capacity"}
    # Slice 1 trusts the node-registry shape (node_id/reach present): operator_nodes.yaml
    # is a controlled internal file, not user input. Next slice (>1 node) adds a
    # validate_nodes() at load time so a malformed entry fails there, not on this line.
    return {"ok": True, "node_id": node["node_id"], "reason": "routed", "reach": node["reach"]}
