"""Capacity routing + license gate for creator work-orders."""
from pathlib import Path
import yaml
from model_registry import lookup_model, requires_ack


def load_nodes(path: Path) -> list:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    # Fail-fast: a malformed registry entry should error at load, not later on
    # node["reach"]/node["node_id"] access deep in the routing path.
    for n in nodes:
        if not all(k in n for k in ("node_id", "vram_gb", "caps", "reach")):
            raise ValueError(f"malformed node registry entry: {n}")
    return nodes


def select_node(node_caps: dict, nodes: list):
    """Lowest-VRAM node that satisfies min_vram_gb and all required caps.

    Nodes marked ``schedulable: false`` are excluded. The capacity registry has
    to name every machine on the fleet — the anchor validator derives known
    hostnames from it, so a node absent from the registry makes correct
    documentation look like a typo. But "this box exists" and "a worker can
    consume a job on it" are different claims, and the registry could previously
    only make the second one.

    That gap is not cosmetic here, because this function picks the LOWEST-VRAM
    match: an un-bootstrapped edge node is not a harmless extra row, it *wins*
    every small job it nominally qualifies for and those jobs get dispatched to
    a host with no worker to run them. Defaults to True, so every existing
    registry entry keeps its current behaviour.
    """
    need = set(node_caps.get("needs", []))
    min_vram = node_caps.get("min_vram_gb", 0)
    candidates = [
        n for n in nodes
        if n.get("schedulable", True)
        and n.get("vram_gb", 0) >= min_vram
        and need.issubset(set(n.get("caps", [])))
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda n: n.get("vram_gb", 0))


def route(workorder: dict, nodes: list, models: dict) -> dict:
    """License gate first, then capacity match. node_caps may be omitted and is
    then derived from the workflow's registry caps. Returns a RouteResult dict."""
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
    # Explicit node_caps win; otherwise derive from the workflow's registry caps.
    # `or` treats an empty/falsy node_caps as absent (fall back to workflow caps);
    # the work-order schema rejects an empty node_caps object before dispatch, so
    # this only matters to direct callers of route().
    node_caps = workorder.get("node_caps") or model.get("caps")
    if not node_caps:
        return {"ok": False, "node_id": None, "reason": "no-caps"}
    node = select_node(node_caps, nodes)
    if node is None:
        return {"ok": False, "node_id": None, "reason": "no-capacity"}
    # Node shape (node_id/reach present) is guaranteed by load_nodes, which fails
    # fast on a malformed registry entry — so this access can't KeyError here.
    return {"ok": True, "node_id": node["node_id"], "reason": "routed", "reach": node["reach"]}
