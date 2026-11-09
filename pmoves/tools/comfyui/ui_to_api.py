#!/usr/bin/env python3
"""Extract an API-format prompt from a ComfyUI UI-format workflow.

Follows links backward from an output node (default: last VHS_VideoCombine),
resolving rgthree GetNode->SetNode indirections. Widget values are mapped to
NAMED inputs using the live server's /object_info INPUT_TYPES order, which is
exactly how the UI itself serializes - no guessing.

Usage:
  python3 ui_to_api.py WORKFLOW.json [--server http://localhost:8189]
      [--output-node ID] [--set NODE.INPUT=VALUE ...] [-o OUT.json]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.request

SKIP_TYPES = {"Note", "MarkdownNote", "Label (rgthree)", "Reroute",
              "PrimitiveStringMultiline", "PrimitiveFloat", "INTConstant"}


def object_info(server: str) -> dict:
    with urllib.request.urlopen(f"{server}/object_info", timeout=30) as r:
        return json.loads(r.read())


def widget_input_names(info: dict, ctype: str, node: dict) -> list[str]:
    """Widget-order input names for a class = required+optional keys minus
    inputs that arrive as links on THIS node instance."""
    spec = (info.get(ctype) or {}).get("input", {})
    names: list[str] = []
    linked = {i.get("name") for i in node.get("inputs") or [] if i.get("link") is not None}
    for group in ("required", "optional"):
        for name in (spec.get(group) or {}):
            if name not in linked and name not in names:
                names.append(name)
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow", type=pathlib.Path)
    ap.add_argument("--server", default="http://localhost:8189")
    ap.add_argument("--output-node")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("-o", "--out", type=pathlib.Path)
    args = ap.parse_args()

    doc = json.loads(args.workflow.read_text(encoding="utf-8"))
    if "nodes" not in doc:
        payload = json.dumps(doc, indent=2)
        print(payload)
        return 0

    nodes = doc["nodes"]
    links = {str(l[0]): (str(l[1]), int(l[2])) for l in doc.get("links", [])}
    by_id = {str(n["id"]): n for n in nodes}
    set_nodes = {str(n["id"]): n for n in nodes if n.get("type") == "SetNode"}
    get_to_set: dict[str, str] = {}
    for n in nodes:
        if n.get("type") == "GetNode":
            title = (n.get("title") or "").strip()
            for sid, s in set_nodes.items():
                if (s.get("title") or "").strip() == title:
                    get_to_set[str(n["id"])] = sid
                    break

    def input_link(node: dict, iname: str):
        """Returns ("node", id, slot) | ("value", widget_value) | None.
        GetNodes resolve to their SetNode's LINK if it has one, else to the
        SetNode's first WIDGET value (rgthree convention: primitives publish
        through Set/Get as widgets, not links)."""
        for inp in node.get("inputs") or []:
            if inp.get("name") != iname or inp.get("link") is None:
                continue
            src = links.get(str(inp["link"]))
            if src is None:
                return None
            src_id, src_slot = src
            hops = 0
            while by_id.get(src_id, {}).get("type") in ("GetNode", "PrimitiveStringMultiline", "INTConstant", "PrimitiveFloat") and hops < 8:
                if by_id.get(src_id, {}).get("type") == "GetNode":
                    sid = get_to_set.get(src_id)
                    if not sid:
                        return None
                    snode = set_nodes[sid]
                    linked = [i for i in snode.get("inputs") or [] if i.get("link") is not None]
                    if linked:
                        nxt = links.get(str(linked[0]["link"]))
                        if nxt is None:
                            return None
                        src_id, src_slot = nxt
                        hops += 1
                        continue
                    wvals = snode.get("widgets_values")
                    if isinstance(wvals, list) and wvals:
                        v = wvals[0]
                        if isinstance(v, dict):
                            v = v.get("value", v)
                        return ("value", v)
                    return None
                # Primitive producers: widget value becomes a literal input
                snode = by_id.get(src_id) or {}
                wvals = snode.get("widgets_values")
                if isinstance(wvals, list) and wvals:
                    v = wvals[0]
                    if isinstance(v, dict):
                        v = v.get("value", v)
                    return ("value", v)
                return None
            return ("node", src_id, src_slot)
        return None

    info = object_info(args.server)

    target = args.output_node
    if not target:
        vids = [str(n["id"]) for n in nodes if n.get("type") == "VHS_VideoCombine"]
        if not vids:
            print("no VHS_VideoCombine; pass --output-node", file=sys.stderr)
            return 2
        target = vids[-1]

    api: dict[str, dict] = {}
    visited: set[str] = set()

    def walk(nid: str) -> None:
        if nid in visited or nid not in by_id:
            return
        visited.add(nid)
        node = by_id[nid]
        ctype = node["type"]
        if ctype in SKIP_TYPES:
            return
        inputs: dict = {}
        for inp in node.get("inputs") or []:
            name = inp.get("name")
            if name is None:
                continue
            src = input_link(node, name)
            if src is None:
                continue
            if src[0] == "value":
                if name not in inputs:
                    inputs[name] = src[1]
            else:
                inputs[name] = [src[1], src[2]]
        wvals = node.get("widgets_values")
        if isinstance(wvals, list):
            names = widget_input_names(info, ctype, node)
            for i, val in enumerate(wvals):
                if i < len(names) and names[i] not in inputs:
                    v = val
                    if isinstance(v, dict):
                        v = v.get("value", v)
                    inputs[names[i]] = v
        api[nid] = {"class_type": ctype, "inputs": inputs}

        for inp in node.get("inputs") or []:
            src = input_link(node, inp.get("name") or "")
            if src and src[0] == "node":
                walk(src[1])

    walk(target)

    for patch in args.set:
        if "=" not in patch:
            print(f"bad --set {patch}", file=sys.stderr)
            return 2
        addr, value = patch.split("=", 1)
        if "." not in addr:
            print(f"bad --set addr {addr}", file=sys.stderr)
            return 2
        nid, field = addr.rsplit(".", 1)
        if nid not in api:
            print(f"--set node {nid} not in graph", file=sys.stderr)
            return 2
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
        api[nid]["inputs"][field] = value

    payload = json.dumps(api, indent=2)
    if args.out:
        args.out.write_text(payload + "\n")
        print(f"wrote {args.out} ({len(api)} nodes)", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
