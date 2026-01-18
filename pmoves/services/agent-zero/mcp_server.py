from __future__ import annotations

import json
import os
import sys
import uuid
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

# E2B Configuration
E2B_MCP_SERVER_URL = os.environ.get("E2B_MCP_SERVER_URL", "http://e2b-mcp-server:7073")
E2B_API_KEY = os.environ.get("E2B_API_KEY", "")
E2B_SANDBOX_URL = os.environ.get("E2B_SANDBOX_URL", "http://e2b-sandbox:7070")
E2B_DESKTOP_URL = os.environ.get("E2B_DESKTOP_URL", "http://e2b-desktop:6080")


def load_form(name: str) -> Dict[str, Any]:
    p = FORMS_DIR / f"{name}.yaml"
    if not p.exists():
        raise RuntimeError(f"Form not found: {name}")
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


# =============================================================================
# E2B Agentic Computer Use Functions
# =============================================================================

def _e2b_headers() -> Dict[str, str]:
    """Get headers for E2B API requests."""
    headers = {"Content-Type": "application/json"}
    if E2B_API_KEY and E2B_API_KEY.strip():
        headers["X-E2B-API-Key"] = E2B_API_KEY
    return headers


def _generate_error_id() -> str:
    """Generate unique error ID for tracking."""
    return str(uuid.uuid4())[:8]


def _e2b_request(
    method: str,
    url: str,
    json_body: Dict = None,
    timeout: int = 30
) -> Optional[requests.Response]:
    """
    Make E2B API request with proper error handling.

    Returns None on network errors, allowing caller to handle gracefully.
    """
    try:
        response = requests.request(
            method,
            url,
            json=json_body,
            headers=_e2b_headers(),
            timeout=timeout
        )
        return response
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.RequestException:
        return None


def _e2b_json_response(response: requests.Response, error_context: str) -> Dict[str, Any]:
    """
    Safely parse JSON response from E2B API.

    Handles:
    - 204 No Content responses
    - Malformed JSON responses
    - Error responses (>= 400)

    Args:
        response: The HTTP response object
        error_context: Context string for error messages (e.g., "sandbox_create")

    Returns:
        Dict with 'ok' status and response data or error details
    """
    # Error responses
    if response.status_code >= 400:
        error_id = _generate_error_id()
        return {
            "ok": False,
            "status": response.status_code,
            "detail": response.text[:300],
            "error_id": f"e2b_{error_context}_{error_id}"
        }

    # 204 No Content - no JSON body
    if response.status_code == 204:
        return {"ok": True, "data": None}

    # Successful response - parse JSON safely
    try:
        result = response.json()
    except (json.JSONDecodeError, ValueError) as e:
        error_id = _generate_error_id()
        return {
            "ok": False,
            "status": response.status_code,
            "detail": f"Invalid JSON response: {str(e)}",
            "error_id": f"e2b_{error_context}_{error_id}"
        }

    # Add ok status to result
    if isinstance(result, dict):
        result["ok"] = True
    else:
        result = {"ok": True, "data": result}

    return result


def e2b_sandbox_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new E2B sandbox for code execution."""
    duration = int(payload.get("duration", 3600))
    memory_mb = int(payload.get("memory_mb", 2048))
    cpu_limit = int(payload.get("cpu_limit", 2))

    request_body = {
        "duration": duration,
        "memory_mb": memory_mb,
        "cpu_limit": cpu_limit
    }

    response = _e2b_request(
        "POST",
        f"{E2B_MCP_SERVER_URL}/sandbox/create",
        request_body,
        timeout=30
    )

    if response is None:
        return {"ok": False, "error": "request_failed", "detail": "Failed to reach E2B server"}

    return _e2b_json_response(response, "sandbox_create")


def e2b_sandbox_execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute code in an existing E2B sandbox."""
    sandbox_id = payload.get("sandbox_id")
    if not sandbox_id:
        raise ValueError("'sandbox_id' is required")

    language = payload.get("language", "python")
    code = payload.get("code", "")

    if not code:
        raise ValueError("'code' is required")

    request_body = {
        "sandbox_id": sandbox_id,
        "language": language,
        "code": code
    }

    response = _e2b_request(
        "POST",
        f"{E2B_MCP_SERVER_URL}/sandbox/execute",
        request_body,
        timeout=120
    )

    if response is None:
        return {"ok": False, "error": "request_failed", "detail": "Failed to reach E2B server"}

    return _e2b_json_response(response, "sandbox_execute")


def e2b_sandbox_terminate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Terminate an existing E2B sandbox."""
    sandbox_id = payload.get("sandbox_id")
    if not sandbox_id:
        raise ValueError("'sandbox_id' is required")

    response = _e2b_request(
        "DELETE",
        f"{E2B_MCP_SERVER_URL}/sandbox/{sandbox_id}",
        timeout=10
    )

    if response is None:
        return {"ok": False, "error": "request_failed", "detail": "Failed to reach E2B server"}

    return _e2b_json_response(response, "sandbox_terminate")


def e2b_desktop_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new E2B desktop sandbox with GUI access."""
    duration = int(payload.get("duration", 3600))
    memory_mb = int(payload.get("memory_mb", 2048))
    resolution = payload.get("resolution", "1920x1080")

    request_body = {
        "duration": duration,
        "memory_mb": memory_mb,
        "resolution": resolution
    }

    response = _e2b_request(
        "POST",
        f"{E2B_MCP_SERVER_URL}/desktop/create",
        request_body,
        timeout=60
    )

    if response is None:
        return {"ok": False, "error": "request_failed", "detail": "Failed to reach E2B server"}

    result = _e2b_json_response(response, "desktop_create")

    # Add NoVNC URL if available
    if result.get("ok") and isinstance(result.get("data"), dict) and "desktop_id" in result.get("data", {}):
        result["novnc_url"] = f"{E2B_DESKTOP_URL}/desktop/{result['data']['desktop_id']}"

    return result


def e2b_spell_execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an E2B spell (predefined code pattern)."""
    spell_name = payload.get("spell_name")
    if not spell_name:
        raise ValueError("'spell_name' is required")

    parameters = payload.get("parameters", {})
    timeout = int(payload.get("timeout", 300))

    request_body = {
        "spell_name": spell_name,
        "parameters": parameters,
        "timeout": timeout
    }

    response = _e2b_request(
        "POST",
        f"{E2B_MCP_SERVER_URL}/spell/execute",
        request_body,
        timeout=timeout + 10
    )

    if response is None:
        return {"ok": False, "error": "request_failed", "detail": "Failed to reach E2B server"}

    return _e2b_json_response(response, "spell_execute")


def e2b_surf_scrape(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Scrape/web surf a URL and extract content."""
    url = payload.get("url")
    if not url:
        raise ValueError("'url' is required")

    depth = int(payload.get("depth", 2))
    extract_content = payload.get("extract_content", True)
    follow_links = payload.get("follow_links", False)

    request_body = {
        "url": url,
        "depth": depth,
        "extract_content": extract_content,
        "follow_links": follow_links
    }

    response = _e2b_request(
        "POST",
        f"{E2B_MCP_SERVER_URL}/surf/scrape",
        request_body,
        timeout=120
    )

    if response is None:
        return {"ok": False, "error": "request_failed", "detail": "Failed to reach E2B server"}

    return _e2b_json_response(response, "surf_scrape")


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
    # E2B Agentic Computer Use Commands
    "e2b.sandbox.create": "Create a new E2B sandbox for code execution (duration, memory_mb, cpu_limit)",
    "e2b.sandbox.execute": "Execute code in an existing E2B sandbox (sandbox_id, language, code)",
    "e2b.sandbox.terminate": "Terminate an existing E2B sandbox (sandbox_id)",
    "e2b.desktop.create": "Create a new E2B desktop sandbox with GUI access (duration, memory_mb, resolution)",
    "e2b.spell.execute": "Execute an E2B spell (predefined code pattern) (spell_name, parameters, timeout)",
    "e2b.surf.scrape": "Scrape/web surf a URL and extract content (url, depth, extract_content, follow_links)",
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
    # E2B Agentic Computer Use Commands
    if cmd == "e2b.sandbox.create":
        return e2b_sandbox_create(payload)
    if cmd == "e2b.sandbox.execute":
        return e2b_sandbox_execute(payload)
    if cmd == "e2b.sandbox.terminate":
        return e2b_sandbox_terminate(payload)
    if cmd == "e2b.desktop.create":
        return e2b_desktop_create(payload)
    if cmd == "e2b.spell.execute":
        return e2b_spell_execute(payload)
    if cmd == "e2b.surf.scrape":
        return e2b_surf_scrape(payload)
    raise ValueError(f"Unknown E2B command: {cmd}")


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

