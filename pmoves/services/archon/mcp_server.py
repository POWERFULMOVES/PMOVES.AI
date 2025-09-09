from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import requests
import yaml

GATEWAY_URL = os.environ.get("HIRAG_URL", os.environ.get("GATEWAY_URL", "http://localhost:8087"))
FORM_NAME = os.environ.get("ARCHON_FORM", os.environ.get("AGENT_FORM","POWERFULMOVES"))
FORMS_DIR = Path(os.environ.get("AGENT_FORMS_DIR", "configs/agents/forms"))


def load_form(name: str) -> Dict[str, Any]:
    p = FORMS_DIR / f"{name}.yaml"
    if not p.exists():
        raise RuntimeError(f"form not found: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def knowledge_rag_query(query: str, namespace: str = "pmoves", k: int = 8, alpha: float = 0.7) -> Dict[str, Any]:
    body = {"query": query, "namespace": namespace, "k": k, "alpha": alpha}
    r = requests.post(f"{GATEWAY_URL}/hirag/query", json=body, timeout=30)
    r.raise_for_status();
    # v1 vs v2 gateways differ; normalize lightly
    data = r.json()
    if "hits" in data:
        return data
    return {"query": query, "k": k, "used_rerank": False, "hits": data.get("results", [])}


def knowledge_codebook_update(jsonl_path: str) -> Dict[str, Any]:
    # Move/Copy file to datasets/structured_dataset.jsonl (default path used by gateway)
    dst = Path("datasets/structured_dataset.jsonl")
    src = Path(jsonl_path)
    if not src.exists():
        raise RuntimeError(f"codebook source not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return {"ok": True, "path": str(dst)}


def geometry_publish_cgp(cgp: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{GATEWAY_URL}/geometry/event", json={"type":"geometry.cgp.v1", "data": cgp}, timeout=20)
    r.raise_for_status(); return r.json()


def geometry_decode_text(mode: str, constellation_id: str, k: int = 5) -> Dict[str, Any]:
    r = requests.post(f"{GATEWAY_URL}/geometry/decode/text", json={"mode": mode, "constellation_id": constellation_id, "k": k}, timeout=60)
    r.raise_for_status(); return r.json()


def _stdout(msg: Dict[str, Any]):
    sys.stdout.write(json.dumps(msg) + "\n"); sys.stdout.flush()


def main():
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
            if cmd == "knowledge.rag.query":
                _stdout(knowledge_rag_query(req.get("query",""), req.get("namespace","pmoves"), int(req.get("k",8)), float(req.get("alpha",0.7))))
            elif cmd == "knowledge.codebook.update":
                _stdout(knowledge_codebook_update(req.get("path")))
            elif cmd == "geometry.publish_cgp":
                _stdout(geometry_publish_cgp(req.get("cgp") or {}))
            elif cmd == "geometry.decode_text":
                _stdout(geometry_decode_text(req.get("mode","geometry"), req.get("constellation_id"), int(req.get("k",5))))
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

