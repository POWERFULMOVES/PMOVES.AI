from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests
import yaml

GATEWAY_URL = os.environ.get("HIRAG_URL", os.environ.get("GATEWAY_URL", "http://localhost:8087"))
FORM_NAME = os.environ.get("AGENT_FORM", "POWERFULMOVES")
FORMS_DIR = Path(os.environ.get("AGENT_FORMS_DIR", "configs/agents/forms"))


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
            if cmd == "geometry.publish_cgp":
                _stdout(geometry_publish_cgp(req.get("cgp") or {}))
            elif cmd == "geometry.jump":
                _stdout(geometry_jump(req.get("point_id")))
            elif cmd == "geometry.decode_text":
                _stdout(geometry_decode_text(req.get("mode","geometry"), req.get("constellation_id"), int(req.get("k",5))))
            elif cmd == "geometry.calibration.report":
                _stdout(geometry_calibration_report(req.get("data") or {}))
            elif cmd == "ingest.youtube":
                _stdout(ingest_youtube(req.get("url")))
            elif cmd == "media.transcribe":
                _stdout(media_transcript(req.get("video_id")))
            elif cmd == "comfy.render":
                _stdout(comfy_render(req.get("flow_id"), req.get("inputs") or {}))
            elif cmd == "form.get":
                _stdout({"form": form})
            elif cmd == "form.switch":
                name = req.get("name", "POWERFULMOVES")
                newf = load_form(name)
                _stdout({"ok": True, "form": newf})
            else:
                _stdout({"error": f"unknown_cmd:{cmd}"})
        except Exception as e:
            _stdout({"error": str(e)})


if __name__ == "__main__":
    main()

