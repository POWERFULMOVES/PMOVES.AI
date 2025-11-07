from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

from services.common.forms import (
    DEFAULT_AGENT_FORM,
    DEFAULT_AGENT_FORMS_DIR,
    resolve_form_name,
    resolve_forms_dir_path,
)

GATEWAY_URL = os.environ.get("HIRAG_URL", os.environ.get("GATEWAY_URL", "http://localhost:8086"))
FORM_NAME = resolve_form_name(fallback=DEFAULT_AGENT_FORM)
FORMS_DIR = resolve_forms_dir_path(fallback=DEFAULT_AGENT_FORMS_DIR)
KNOWLEDGE_BASE_DIR = Path(os.environ.get("AGENT_KNOWLEDGE_BASE_DIR", "runtime/knowledge"))
MCP_RUNTIME_DIR = Path(os.environ.get("AGENT_MCP_RUNTIME_DIR", "runtime/mcp"))
NOTEBOOK_API_URL = os.environ.get(
    "OPEN_NOTEBOOK_API_URL", os.environ.get("NOTEBOOK_API_URL")
)
NOTEBOOK_API_TOKEN = os.environ.get(
    "OPEN_NOTEBOOK_API_TOKEN", os.environ.get("NOTEBOOK_API_TOKEN")
)
NOTEBOOK_WORKSPACE = os.environ.get(
    "OPEN_NOTEBOOK_WORKSPACE", os.environ.get("NOTEBOOK_WORKSPACE")
)


def load_form(name: str) -> Dict[str, Any]:
    p = FORMS_DIR / f"{name}.yaml"
    if not p.exists():
        raise RuntimeError(f"form not found: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def geometry_publish_cgp(cgp: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{GATEWAY_URL}/geometry/event", json={"type":"geometry.cgp.v1", "data": cgp}, timeout=20)
    r.raise_for_status()
    return r.json()


def geometry_jump(point_id: str) -> Dict[str, Any]:
    r = requests.get(f"{GATEWAY_URL}/shape/point/{point_id}/jump", timeout=10)
    r.raise_for_status(); return r.json()


def geometry_decode_text(
    mode: str, constellation_id: str, k: int = 5, shape_id: Optional[str] = None
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "mode": mode,
        "constellation_id": constellation_id,
        "k": k,
        "constellation_ids": [constellation_id],
        "per_constellation": k,
    }
    if shape_id:
        body["shape_id"] = shape_id
    r = requests.post(f"{GATEWAY_URL}/geometry/decode/text", json=body, timeout=60)
    r.raise_for_status(); return r.json()


def geometry_calibration_report(data: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{GATEWAY_URL}/geometry/calibration/report", json={"data": data}, timeout=20)
    r.raise_for_status(); return r.json()


def ingest_youtube(url: str) -> Dict[str, Any]:
    yt = os.environ.get("YT_URL", "http://localhost:8077")
    r = requests.post(f"{yt}/yt/ingest", json={"url": url}, timeout=120)
    r.raise_for_status(); return r.json()


def media_transcript(video_id: str) -> Dict[str, Any]:
    yt = os.environ.get("YT_URL", "http://localhost:8077")
    r = requests.post(f"{yt}/yt/transcript", json={"video_id": video_id}, timeout=600)
    r.raise_for_status(); return r.json()


def comfy_render(flow_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    rw = os.environ.get("RENDER_WEBHOOK_URL", "http://localhost:8085")
    # Minimal placeholder: forward to render-webhook if such endpoint exists in your service
    r = requests.post(f"{rw}/comfy/render", json={"flow_id": flow_id, "inputs": inputs}, timeout=120)
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "detail": r.text[:300]}
    return r.json()


def _ensure_notebook_credentials() -> None:
    if not NOTEBOOK_API_URL:
        raise RuntimeError(
            "Open Notebook API URL not configured (set OPEN_NOTEBOOK_API_URL or NOTEBOOK_API_URL)"
        )
    if not NOTEBOOK_API_TOKEN:
        raise RuntimeError(
            "Open Notebook API token not configured (set OPEN_NOTEBOOK_API_TOKEN or NOTEBOOK_API_TOKEN)"
        )


def _summarize_note(note: Dict[str, Any]) -> Optional[str]:
    summary = note.get("summary") or note.get("excerpt")
    if summary:
        return summary
    content = note.get("content") or note.get("body")
    if not content:
        return None
    content = str(content).strip()
    if len(content) <= 280:
        return content
    return content[:277].rstrip() + "..."


def notebook_search(payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_notebook_credentials()

    query = (payload.get("query") or payload.get("text") or "").strip()
    notebook_id = payload.get("notebook_id") or payload.get("notebookId")
    source_ids = payload.get("source_ids") or payload.get("sourceIds")
    tags = payload.get("tags")
    workspace = (
        payload.get("workspace")
        or payload.get("workspace_id")
        or payload.get("workspaceId")
    )
    limit = int(payload.get("limit", 10))
    if limit <= 0:
        raise ValueError("'limit' must be greater than zero")

    filters: Dict[str, Any] = {}
    if notebook_id:
        filters["notebook_id"] = notebook_id
    if workspace:
        filters["workspace"] = workspace
    elif NOTEBOOK_WORKSPACE:
        filters.setdefault("workspace", NOTEBOOK_WORKSPACE)
    if source_ids:
        if isinstance(source_ids, str):
            source_ids = [source_ids]
        filters["source_ids"] = source_ids
    if tags:
        if isinstance(tags, str):
            tags = [tags]
        filters["tags"] = tags

    if not query and not filters:
        raise ValueError("Provide at least a 'query' or filter (e.g. 'notebook_id')")

    request_body: Dict[str, Any] = {"limit": limit}
    if query:
        request_body["query"] = query
    if filters:
        request_body["filters"] = filters

    headers = {
        "Authorization": f"Bearer {NOTEBOOK_API_TOKEN}",
        "Accept": "application/json",
    }

    response = requests.post(
        f"{NOTEBOOK_API_URL.rstrip('/')}/api/v1/notebooks/search",
        json=request_body,
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    results = data.get("results") or data.get("items") or []
    curated: List[Dict[str, Any]] = []
    for item in results:
        note: Dict[str, Any]
        note = item.get("note") or item
        source = item.get("source") or {}
        summary = item.get("summary") or _summarize_note(note)
        curated.append(
            {
                "id": note.get("id") or item.get("id"),
                "title": note.get("title") or note.get("name"),
                "summary": summary,
                "score": item.get("score"),
                "notebook_id": note.get("notebook_id") or filters.get("notebook_id"),
                "source": {
                    "id": source.get("id") or item.get("source_id") or note.get("source_id"),
                    "type": source.get("type") or item.get("source_type"),
                    "url": source.get("url") or note.get("url") or item.get("url"),
                },
            }
        )

    total = data.get("total")
    if total is None:
        total = len(results)

    return {
        "ok": True,
        "query": query or None,
        "filters": filters,
        "total": total,
        "notes": curated,
        "next_cursor": data.get("next_cursor") or data.get("next"),
    }


def _stdout(msg: Dict[str, Any]):
    sys.stdout.write(json.dumps(msg) + "\n"); sys.stdout.flush()


COMMAND_REGISTRY: Dict[str, str] = {
    "geometry.publish_cgp": "Publish a constellation graph program to the geometry gateway",
    "geometry.jump": "Jump to a geometry point by ID",
    "geometry.decode_text": "Decode text embeddings (mode, constellation_id, k=5, optional shape_id)",
    "geometry.calibration.report": "Send calibration results to geometry gateway",
    "ingest.youtube": "Ingest a YouTube URL via the ingest pipeline",
    "media.transcribe": "Generate or fetch transcript for a video",
    "comfy.render": "Trigger a ComfyUI render via render webhook",
    "notebook.search": "Search Open Notebook for curated notes",
    "form.get": "Return the currently configured MCP form",
    "form.switch": "Switch the active MCP form",
}


def execute_command(cmd: Optional[str], payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute an MCP command using the local runtime helpers."""

    payload = payload or {}
    if not cmd:
        raise ValueError("'cmd' is required")
    if cmd == "geometry.publish_cgp":
        return geometry_publish_cgp(payload.get("cgp") or {})
    if cmd == "geometry.jump":
        point_id = payload.get("point_id")
        if not point_id:
            raise ValueError("'point_id' is required")
        return geometry_jump(point_id)
    if cmd == "geometry.decode_text":
        mode = payload.get("mode", "geometry")
        constellation_id = payload.get("constellation_id")
        if not constellation_id:
            raise ValueError("'constellation_id' is required")
        k = int(payload.get("k", 5))
        shape_id = payload.get("shape_id")
        return geometry_decode_text(mode, constellation_id, k, shape_id=shape_id)
    if cmd == "geometry.calibration.report":
        return geometry_calibration_report(payload.get("data") or {})
    if cmd == "ingest.youtube":
        url = payload.get("url")
        if not url:
            raise ValueError("'url' is required")
        return ingest_youtube(url)
    if cmd == "media.transcribe":
        video_id = payload.get("video_id")
        if not video_id:
            raise ValueError("'video_id' is required")
        return media_transcript(video_id)
    if cmd == "comfy.render":
        flow_id = payload.get("flow_id")
        if not flow_id:
            raise ValueError("'flow_id' is required")
        inputs = payload.get("inputs") or {}
        return comfy_render(flow_id, inputs)
    if cmd == "notebook.search":
        return notebook_search(payload)
    if cmd == "form.get":
        current_form = payload.get("name", FORM_NAME)
        return {"form": load_form(current_form)}
    if cmd == "form.switch":
        name = payload.get("name", FORM_NAME)
        new_form = load_form(name)
        return {"ok": True, "form": new_form}
    raise ValueError(f"unknown_cmd:{cmd}")


def list_commands() -> List[Dict[str, Any]]:
    """Return metadata for exposed MCP commands."""

    return [
        {"name": name, "description": desc}
        for name, desc in sorted(COMMAND_REGISTRY.items())
    ]


def main():
    # Lightweight MCP-like shim over stdio: accepts line-delimited JSON commands
    form = load_form(FORM_NAME)
    _stdout({"event": "ready", "form": form.get("name")})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            _stdout({"error": "invalid_json"}); continue
        cmd = req.get("cmd")
        try:
            _stdout(execute_command(cmd, req))
        except Exception as e:
            _stdout({"error": str(e)})


if __name__ == "__main__":
    main()

