from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
import yaml

from services.common.forms import (
    DEFAULT_AGENT_FORM,
    DEFAULT_AGENT_FORMS_DIR,
    resolve_form_name,
    resolve_forms_dir_path,
)

ARCHON_SERVER_URL = os.environ.get("ARCHON_SERVER_URL", os.environ.get("ARCHON_HTTP_URL", "http://localhost:8181")).rstrip("/")
ARCHON_API_URL = os.environ.get("ARCHON_API_URL", f"{ARCHON_SERVER_URL}/api").rstrip("/")
ARCHON_SOCKET_URL = os.environ.get("ARCHON_SOCKET_URL", ARCHON_SERVER_URL)
ARCHON_API_TOKEN = os.environ.get("ARCHON_API_TOKEN")
FORM_NAME = resolve_form_name(
    prefer_keys=("ARCHON_FORM",),
    fallback=DEFAULT_AGENT_FORM,
)
FORMS_DIR = resolve_forms_dir_path(
    prefer_keys=("ARCHON_FORMS_DIR",),
    fallback=DEFAULT_AGENT_FORMS_DIR,
)
DEFAULT_TIMEOUT = float(os.environ.get("ARCHON_HTTP_TIMEOUT", "45"))
LONG_TIMEOUT = float(os.environ.get("ARCHON_LONG_HTTP_TIMEOUT", "180"))


class ArchonClient:
    """HTTP client for the Archon orchestration layer."""

    def __init__(
        self,
        api_url: str,
        *,
        socket_url: Optional[str] = None,
        default_timeout: float = 45.0,
        long_timeout: float = 180.0,
        api_token: Optional[str] = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.socket_url = socket_url.rstrip("/") if socket_url else None
        self.default_timeout = default_timeout
        self.long_timeout = long_timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        if api_token:
            self.session.headers["Authorization"] = f"Bearer {api_token}"

    def _build_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.api_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        response = self.session.request(
            method,
            self._build_url(path),
            params=params,
            json=json_payload,
            data=data,
            files=files,
            timeout=timeout or self.default_timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - network error surface
            detail = response.text.strip()
            if len(detail) > 400:
                detail = detail[:400] + "..."
            raise RuntimeError(f"Archon API error ({response.status_code}): {detail}") from exc

        if not response.content:
            return {"success": True}

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                return response.json()
            except ValueError:
                return {"success": True, "raw": response.text}
        return {"success": True, "data": response.text}

    # Knowledge operations -------------------------------------------------
    def perform_rag_query(self, query: str, match_count: int, source: Optional[str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query, "match_count": match_count}
        if source:
            payload["source"] = source
        return self._request("POST", "/rag/query", json_payload=payload)

    def search_code_examples(self, query: str, match_count: int, source: Optional[str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query, "match_count": match_count}
        if source:
            payload["source"] = source
        return self._request("POST", "/code-examples", json_payload=payload)

    def get_available_sources(self) -> Dict[str, Any]:
        return self._request("GET", "/rag/sources")

    def crawl_url(
        self,
        url: str,
        *,
        knowledge_type: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        update_frequency: Optional[int] = None,
        max_depth: Optional[int] = None,
        extract_code_examples: Optional[bool] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"url": url}
        if knowledge_type:
            payload["knowledge_type"] = knowledge_type
        if tags is not None:
            payload["tags"] = list(tags)
        if update_frequency is not None:
            payload["update_frequency"] = int(update_frequency)
        if max_depth is not None:
            payload["max_depth"] = int(max_depth)
        if extract_code_examples is not None:
            payload["extract_code_examples"] = bool(extract_code_examples)
        return self._request("POST", "/knowledge/crawl", json_payload=payload, timeout=self.long_timeout)

    def upload_document(
        self,
        file_path: Path,
        *,
        tags: Optional[Iterable[str]] = None,
        knowledge_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not file_path.exists():
            raise RuntimeError(f"document not found: {file_path}")

        data: Dict[str, Any] = {}
        if knowledge_type:
            data["knowledge_type"] = knowledge_type
        if tags is not None:
            data["tags"] = json.dumps(list(tags))

        with file_path.open("rb") as fh:
            files = {"file": (file_path.name, fh)}
            return self._request(
                "POST",
                "/documents/upload",
                data=data or None,
                files=files,
                timeout=self.long_timeout,
            )

    def delete_source(self, source_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/sources/{source_id}")

    # Project operations ---------------------------------------------------
    def list_projects(self) -> Dict[str, Any]:
        return self._request("GET", "/projects")

    def create_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/projects", json_payload=payload, timeout=self.long_timeout)

    def get_project(self, project_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}")

    def update_project(self, project_id: str, update_fields: Dict[str, Any]) -> Dict[str, Any]:
        if not update_fields:
            raise ValueError("update_fields cannot be empty")
        return self._request("PUT", f"/projects/{project_id}", json_payload=update_fields)

    def delete_project(self, project_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/projects/{project_id}")

    def get_project_features(self, project_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}/features")

    # Task operations ------------------------------------------------------
    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        include_closed: Optional[bool] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        if project_id:
            params["project_id"] = project_id
        if include_closed is not None:
            params["include_closed"] = str(bool(include_closed)).lower()
        return self._request("GET", "/tasks", params=params or None)

    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/tasks", json_payload=payload)

    def get_task(self, task_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/tasks/{task_id}")

    def update_task(self, task_id: str, update_fields: Dict[str, Any]) -> Dict[str, Any]:
        if not update_fields:
            raise ValueError("update_fields cannot be empty")
        return self._request("PUT", f"/tasks/{task_id}", json_payload=update_fields)

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/tasks/{task_id}")

    # Document operations --------------------------------------------------
    def list_project_documents(self, project_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}/docs")

    def create_project_document(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", f"/projects/{project_id}/docs", json_payload=payload)

    def get_project_document(self, project_id: str, document_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}/docs/{document_id}")

    def update_project_document(
        self,
        project_id: str,
        document_id: str,
        update_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not update_fields:
            raise ValueError("update_fields cannot be empty")
        return self._request(
            "PUT",
            f"/projects/{project_id}/docs/{document_id}",
            json_payload=update_fields,
        )

    def delete_project_document(self, project_id: str, document_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/projects/{project_id}/docs/{document_id}")

    # Versioning operations -----------------------------------------------
    def list_project_versions(self, project_id: str, field_name: Optional[str]) -> Dict[str, Any]:
        params = {"field_name": field_name} if field_name else None
        return self._request("GET", f"/projects/{project_id}/versions", params=params)

    def create_project_version(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request(
            "POST",
            f"/projects/{project_id}/versions",
            json_payload=payload,
        )

    def get_project_version(self, project_id: str, field_name: str, version_number: int) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/projects/{project_id}/versions/{field_name}/{version_number}",
        )

    def restore_project_version(
        self,
        project_id: str,
        field_name: str,
        version_number: int,
        *,
        restored_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {"restored_by": restored_by} if restored_by else None
        return self._request(
            "POST",
            f"/projects/{project_id}/versions/{field_name}/{version_number}/restore",
            json_payload=payload,
        )


CLIENT = ArchonClient(
    ARCHON_API_URL,
    socket_url=ARCHON_SOCKET_URL,
    default_timeout=DEFAULT_TIMEOUT,
    long_timeout=LONG_TIMEOUT,
    api_token=ARCHON_API_TOKEN,
)


def _ensure_iterable(value: Optional[Any]) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


def load_form(name: str) -> Dict[str, Any]:
    form_data: Dict[str, Any] = {}
    path = FORMS_DIR / f"{name}.yaml"
    if path.exists():
        form_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    commands_metadata = []
    for command, meta in COMMAND_DEFINITIONS.items():
        entry = {
            "name": command,
            "description": meta["description"],
        }
        if meta.get("arguments"):
            entry["arguments"] = meta["arguments"]
        commands_metadata.append(entry)

    categories = [
        {
            "name": category_name,
            "description": details["description"],
            "commands": details["commands"],
        }
        for category_name, details in FORM_CATEGORIES.items()
    ]

    merged: Dict[str, Any] = {
        "name": form_data.get("name", name),
        "description": form_data.get(
            "description",
            "Archon MCP orchestration form exposing knowledge, project, and task tooling.",
        ),
        "commands": commands_metadata,
        "metadata": {
            "categories": categories,
            "archon": {
                "api_url": CLIENT.api_url,
                "socket_url": CLIENT.socket_url,
            },
        },
    }

    for key, value in form_data.items():
        if key in {"commands", "metadata"}:
            continue
        merged[key] = value

    return merged


def _validate_required(payload: Dict[str, Any], key: str) -> Any:
    value = payload.get(key)
    if value in (None, ""):
        raise ValueError(f"'{key}' is required")
    return value


def handle_perform_rag_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = _validate_required(payload, "query")
    match_count = int(payload.get("match_count", payload.get("k", 5)))
    source = payload.get("source") or payload.get("namespace")
    return CLIENT.perform_rag_query(query, match_count, source)


def handle_search_code_examples(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = _validate_required(payload, "query")
    match_count = int(payload.get("match_count", 5))
    source = payload.get("source")
    return CLIENT.search_code_examples(query, match_count, source)


def handle_get_available_sources(_: Dict[str, Any]) -> Dict[str, Any]:
    return CLIENT.get_available_sources()


def handle_crawl_single_page(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = _validate_required(payload, "url")
    knowledge_type = payload.get("knowledge_type")
    tags = _ensure_iterable(payload.get("tags"))
    extract = payload.get("extract_code_examples")
    return CLIENT.crawl_url(
        url,
        knowledge_type=knowledge_type,
        tags=tags,
        update_frequency=payload.get("update_frequency"),
        max_depth=int(payload.get("max_depth", 1)),
        extract_code_examples=extract if extract is not None else True,
    )


def handle_smart_crawl(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = _validate_required(payload, "url")
    knowledge_type = payload.get("knowledge_type")
    tags = _ensure_iterable(payload.get("tags"))
    extract = payload.get("extract_code_examples")
    return CLIENT.crawl_url(
        url,
        knowledge_type=knowledge_type,
        tags=tags,
        update_frequency=payload.get("update_frequency"),
        max_depth=payload.get("max_depth"),
        extract_code_examples=extract,
    )


def handle_upload_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    path_value = _validate_required(payload, "path")
    path = Path(path_value)
    tags = payload.get("tags")
    if isinstance(tags, str):
        try:
            parsed = json.loads(tags)
            if isinstance(parsed, list):
                tags = parsed
            else:
                tags = [tags]
        except json.JSONDecodeError:
            tags = [tags]
    return CLIENT.upload_document(
        path,
        tags=_ensure_iterable(tags),
        knowledge_type=payload.get("knowledge_type"),
    )


def handle_delete_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    source_id = payload.get("source_id") or payload.get("source")
    if not source_id:
        raise ValueError("'source' or 'source_id' is required")
    return CLIENT.delete_source(str(source_id))


def handle_manage_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    action = (payload.get("action") or "").lower()
    if action == "list":
        return CLIENT.list_projects()
    if action == "get":
        project_id = _validate_required(payload, "project_id")
        return CLIENT.get_project(str(project_id))
    if action == "create":
        title = _validate_required(payload, "title")
        project_payload = {
            "title": title,
            "description": payload.get("description"),
            "github_repo": payload.get("github_repo"),
            "docs": payload.get("docs"),
            "features": payload.get("features"),
            "data": payload.get("data"),
            "technical_sources": payload.get("technical_sources"),
            "business_sources": payload.get("business_sources"),
            "pinned": payload.get("pinned"),
        }
        project_payload = {k: v for k, v in project_payload.items() if v is not None}
        return CLIENT.create_project(project_payload)
    if action == "update":
        project_id = _validate_required(payload, "project_id")
        update_fields = payload.get("update_fields") or {}
        if not isinstance(update_fields, dict):
            raise ValueError("'update_fields' must be an object")
        return CLIENT.update_project(str(project_id), update_fields)
    if action == "delete":
        project_id = _validate_required(payload, "project_id")
        return CLIENT.delete_project(str(project_id))
    raise ValueError(f"unsupported project action: {action or 'unknown'}")


def handle_manage_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    action = (payload.get("action") or "").lower()
    if action == "list":
        filter_by = payload.get("filter_by")
        filter_value = payload.get("filter_value")
        params: Dict[str, Any] = {}
        if filter_by == "project":
            params["project_id"] = filter_value
        elif filter_by == "status":
            params["status"] = filter_value
        else:
            if payload.get("project_id"):
                params["project_id"] = payload.get("project_id")
            if payload.get("status"):
                params["status"] = payload.get("status")
        include_closed = payload.get("include_closed")
        return CLIENT.list_tasks(
            status=params.get("status"),
            project_id=params.get("project_id"),
            include_closed=include_closed,
        )
    if action == "get":
        task_id = _validate_required(payload, "task_id")
        return CLIENT.get_task(str(task_id))
    if action == "create":
        project_id = _validate_required(payload, "project_id")
        title = _validate_required(payload, "title")
        task_payload = {
            "project_id": project_id,
            "title": title,
            "description": payload.get("description"),
            "status": payload.get("status"),
            "assignee": payload.get("assignee"),
            "task_order": payload.get("task_order"),
            "feature": payload.get("feature"),
        }
        task_payload = {k: v for k, v in task_payload.items() if v is not None}
        return CLIENT.create_task(task_payload)
    if action == "update":
        task_id = _validate_required(payload, "task_id")
        update_fields = payload.get("update_fields") or {}
        if not isinstance(update_fields, dict):
            raise ValueError("'update_fields' must be an object")
        return CLIENT.update_task(str(task_id), update_fields)
    if action == "delete":
        task_id = _validate_required(payload, "task_id")
        return CLIENT.delete_task(str(task_id))
    raise ValueError(f"unsupported task action: {action or 'unknown'}")


def handle_manage_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    action = (payload.get("action") or "").lower()
    project_id = payload.get("project_id")
    if action != "list":
        project_id = _validate_required(payload, "project_id")
    if action == "list":
        project_id = _validate_required(payload, "project_id")
        return CLIENT.list_project_documents(str(project_id))
    if action == "get":
        document_id = _validate_required(payload, "document_id")
        return CLIENT.get_project_document(str(project_id), str(document_id))
    if action == "create":
        document_type = _validate_required(payload, "document_type")
        title = _validate_required(payload, "title")
        doc_payload = {
            "document_type": document_type,
            "title": title,
            "content": payload.get("content"),
            "tags": payload.get("tags"),
            "author": payload.get("author"),
        }
        return CLIENT.create_project_document(str(project_id), doc_payload)
    if action == "update":
        document_id = _validate_required(payload, "document_id")
        update_fields = payload.get("update_fields") or {}
        if not isinstance(update_fields, dict):
            raise ValueError("'update_fields' must be an object")
        return CLIENT.update_project_document(str(project_id), str(document_id), update_fields)
    if action == "delete":
        document_id = _validate_required(payload, "document_id")
        return CLIENT.delete_project_document(str(project_id), str(document_id))
    raise ValueError(f"unsupported document action: {action or 'unknown'}")


def handle_manage_versions(payload: Dict[str, Any]) -> Dict[str, Any]:
    action = (payload.get("action") or "").lower()
    project_id = _validate_required(payload, "project_id")
    if action == "list":
        field_name = payload.get("field_name")
        return CLIENT.list_project_versions(str(project_id), field_name)
    if action == "create":
        field_name = _validate_required(payload, "field_name")
        content = payload.get("content")
        if not isinstance(content, dict):
            raise ValueError("'content' must be an object")
        version_payload = {
            "field_name": field_name,
            "content": content,
            "change_summary": payload.get("change_summary"),
            "change_type": payload.get("change_type"),
            "document_id": payload.get("document_id"),
            "created_by": payload.get("created_by"),
        }
        return CLIENT.create_project_version(str(project_id), version_payload)
    if action == "get":
        field_name = _validate_required(payload, "field_name")
        version_number = int(_validate_required(payload, "version_number"))
        return CLIENT.get_project_version(str(project_id), str(field_name), version_number)
    if action == "restore":
        field_name = _validate_required(payload, "field_name")
        version_number = int(_validate_required(payload, "version_number"))
        return CLIENT.restore_project_version(
            str(project_id),
            str(field_name),
            version_number,
            restored_by=payload.get("restored_by"),
        )
    raise ValueError(f"unsupported version action: {action or 'unknown'}")


def handle_get_project_features(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = _validate_required(payload, "project_id")
    return CLIENT.get_project_features(str(project_id))


COMMAND_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "perform_rag_query": {
        "description": "Run a semantic RAG query against the Archon knowledge base.",
        "handler": handle_perform_rag_query,
        "category": "Knowledge",
        "arguments": [
            {"name": "query", "type": "string", "required": True},
            {"name": "match_count", "type": "integer", "default": 5},
            {"name": "source", "type": "string", "required": False},
        ],
    },
    "search_code_examples": {
        "description": "Search indexed code examples related to a query.",
        "handler": handle_search_code_examples,
        "category": "Knowledge",
        "arguments": [
            {"name": "query", "type": "string", "required": True},
            {"name": "match_count", "type": "integer", "default": 5},
            {"name": "source", "type": "string", "required": False},
        ],
    },
    "crawl_single_page": {
        "description": "Crawl and index a single URL without following deep links.",
        "handler": handle_crawl_single_page,
        "category": "Knowledge",
        "arguments": [
            {"name": "url", "type": "string", "required": True},
            {"name": "knowledge_type", "type": "string", "required": False},
            {"name": "tags", "type": "array", "required": False},
        ],
    },
    "smart_crawl_url": {
        "description": "Run Archon's smart crawler with configurable depth and tagging.",
        "handler": handle_smart_crawl,
        "category": "Knowledge",
        "arguments": [
            {"name": "url", "type": "string", "required": True},
            {"name": "max_depth", "type": "integer", "required": False},
            {"name": "tags", "type": "array", "required": False},
        ],
    },
    "upload_document": {
        "description": "Upload and process a local document into the knowledge base.",
        "handler": handle_upload_document,
        "category": "Knowledge",
        "arguments": [
            {"name": "path", "type": "string", "required": True},
            {"name": "knowledge_type", "type": "string", "required": False},
            {"name": "tags", "type": "array", "required": False},
        ],
    },
    "get_available_sources": {
        "description": "List available knowledge sources for filtering queries.",
        "handler": handle_get_available_sources,
        "category": "Knowledge",
    },
    "delete_source": {
        "description": "Remove a knowledge source and its indexed content.",
        "handler": handle_delete_source,
        "category": "Knowledge",
        "arguments": [{"name": "source", "type": "string", "required": True}],
    },
    "manage_project": {
        "description": "Perform CRUD operations on Archon projects.",
        "handler": handle_manage_project,
        "category": "Projects",
        "arguments": [{"name": "action", "type": "string", "required": True}],
    },
    "manage_task": {
        "description": "Create, update, list, and delete Archon tasks.",
        "handler": handle_manage_task,
        "category": "Projects",
        "arguments": [{"name": "action", "type": "string", "required": True}],
    },
    "manage_document": {
        "description": "Manage project documents associated with an Archon project.",
        "handler": handle_manage_document,
        "category": "Projects",
        "arguments": [{"name": "action", "type": "string", "required": True}],
    },
    "manage_versions": {
        "description": "Work with project version history for structured fields.",
        "handler": handle_manage_versions,
        "category": "Projects",
        "arguments": [{"name": "action", "type": "string", "required": True}],
    },
    "get_project_features": {
        "description": "Fetch a project's AI-generated feature breakdown.",
        "handler": handle_get_project_features,
        "category": "Projects",
        "arguments": [{"name": "project_id", "type": "string", "required": True}],
    },
}


FORM_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "Knowledge": {
        "description": "Knowledge ingestion, crawling, and semantic retrieval tools.",
        "commands": [
            "perform_rag_query",
            "search_code_examples",
            "crawl_single_page",
            "smart_crawl_url",
            "upload_document",
            "get_available_sources",
            "delete_source",
        ],
    },
    "Projects": {
        "description": "Project, task, and documentation management commands.",
        "commands": [
            "manage_project",
            "manage_task",
            "manage_document",
            "manage_versions",
            "get_project_features",
        ],
    },
}


CURRENT_FORM_NAME = FORM_NAME


def _stdout(msg: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def execute_command(cmd: Optional[str], payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not cmd:
        raise ValueError("'cmd' is required")

    cleaned_payload = {k: v for k, v in (payload or {}).items() if k != "cmd"}

    global CURRENT_FORM_NAME
    if cmd == "form.get":
        return {"form": load_form(CURRENT_FORM_NAME)}
    if cmd == "form.switch":
        name = cleaned_payload.get("name") or FORM_NAME
        CURRENT_FORM_NAME = name
        return {"ok": True, "form": load_form(name)}

    meta = COMMAND_DEFINITIONS.get(cmd)
    if not meta:
        raise ValueError(f"unknown_cmd:{cmd}")
    handler = meta["handler"]
    return handler(cleaned_payload)


def main() -> None:
    form = load_form(CURRENT_FORM_NAME)
    _stdout({"event": "ready", "form": form.get("name")})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            _stdout({"error": "invalid_json"})
            continue
        try:
            response = execute_command(req.get("cmd"), req)
            _stdout(response)
        except Exception as exc:  # noqa: BLE001
            _stdout({"error": str(exc)})


if __name__ == "__main__":
    main()
