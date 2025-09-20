from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

GATEWAY_URL = os.environ.get("HIRAG_URL", os.environ.get("GATEWAY_URL", "http://localhost:8087"))
FORM_NAME = os.environ.get("AGENT_FORM", "POWERFULMOVES")
FORMS_DIR = Path(os.environ.get("AGENT_FORMS_DIR", "configs/agents/forms"))
KNOWLEDGE_BASE_DIR = Path(os.environ.get("AGENT_KNOWLEDGE_BASE_DIR", "runtime/knowledge"))
MCP_RUNTIME_DIR = Path(os.environ.get("AGENT_MCP_RUNTIME_DIR", "runtime/mcp"))


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


def geometry_decode_text(mode: str, constellation_id: str, k: int = 5) -> Dict[str, Any]:
    body = {"mode": mode, "constellation_id": constellation_id, "k": k}
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


def _stdout(msg: Dict[str, Any]):
    sys.stdout.write(json.dumps(msg) + "\n"); sys.stdout.flush()


COMMAND_REGISTRY: Dict[str, str] = {
    "geometry.publish_cgp": "Publish a constellation graph program to the geometry gateway",
    "geometry.jump": "Jump to a geometry point by ID",
    "geometry.decode_text": "Decode text embeddings from a constellation",
    "geometry.calibration.report": "Send calibration results to geometry gateway",
    "ingest.youtube": "Ingest a YouTube URL via the ingest pipeline",
    "media.transcribe": "Generate or fetch transcript for a video",
    "comfy.render": "Trigger a ComfyUI render via render webhook",
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
        return geometry_decode_text(mode, constellation_id, k)
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

