"""Comprehensive tests for pmoves.services.archon.mcp_server.

Covers:
- ArchonClient HTTP methods (build_url, _request, CRUD operations)
- Command handler functions (rag_query, crawl, project/task/document/version management)
- execute_command routing and form handling
- Input validation and error handling
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# ArchonClient tests
# ---------------------------------------------------------------------------

from services.archon.mcp_server import ArchonClient


class FakeResponse:
    """Lightweight mock for requests.Response."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        text: str = "",
        content: bytes = b"",
        headers: Dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json = json_data
        # If json_data provided, ensure content is non-empty so _request parses it
        self.content = content if content else (b"has-content" if json_data is not None else b"")
        self.text = text if text is not None else ("" if json_data is None else json.dumps(json_data))
        self.headers = headers or {"content-type": "application/json"}

    def json(self) -> Any:
        if self._json is not None:
            return self._json
        raise ValueError("No JSON")

    def raise_for_status(self) -> None:
        if not (200 <= self.status_code < 300):
            import requests
            raise requests.HTTPError(response=self)


@pytest.fixture
def mock_session():
    """Return a MagicMock that acts like requests.Session, recording calls."""
    session = MagicMock()
    session.headers = MagicMock()
    return session


@pytest.fixture
def client(mock_session: MagicMock) -> ArchonClient:
    cl = ArchonClient("http://localhost:8181/api", api_token="test-token")
    cl.session = mock_session
    return cl


def _set_response(mock_session: MagicMock, **kwargs: Any) -> FakeResponse:
    resp = FakeResponse(**kwargs)
    mock_session.request.return_value = resp
    return resp


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------

class TestBuildUrl:
    def test_prepends_slash(self, client: ArchonClient) -> None:
        assert client._build_url("rag/query") == "http://localhost:8181/api/rag/query"

    def test_no_double_slash(self, client: ArchonClient) -> None:
        assert client._build_url("/rag/query") == "http://localhost:8181/api/rag/query"

    def test_trailing_api_slash(self) -> None:
        cl = ArchonClient("http://host/api/")
        assert cl.api_url == "http://host/api"


# ---------------------------------------------------------------------------
# _request base method
# ---------------------------------------------------------------------------

class TestRequest:
    def test_successful_json_response(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"result": "ok"})
        result = client._request("GET", "/test")
        assert result == {"result": "ok"}

    def test_empty_content_returns_success(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, content=b"", text="")
        result = client._request("GET", "/test")
        assert result == {"success": True}

    def test_non_json_content_type(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, text="<html>", content=b"<html>", headers={"content-type": "text/html"})
        result = client._request("GET", "/test")
        assert result == {"success": True, "data": "<html>"}

    def test_json_parse_fallback(self, client: ArchonClient, mock_session: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"not-json"
        mock_resp.text = "not-json"
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = ValueError("bad json")
        mock_session.request.return_value = mock_resp
        result = client._request("GET", "/test")
        assert result == {"success": True, "raw": "not-json"}

    def test_http_error_raises_runtime(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, status_code=500, text="Internal Server Error")
        with pytest.raises(RuntimeError, match="Archon API error"):
            client._request("GET", "/fail")

    def test_long_error_text_truncated(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, status_code=400, text="x" * 500)
        with pytest.raises(RuntimeError, match=r"\.\.\."):
            client._request("GET", "/fail")

    def test_custom_timeout(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={})
        client._request("GET", "/test", timeout=10.0)
        _, kwargs = mock_session.request.call_args
        assert kwargs["timeout"] == 10.0

    def test_default_timeout(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={})
        client._request("GET", "/test")
        _, kwargs = mock_session.request.call_args
        assert kwargs["timeout"] == 45.0  # default_timeout


# ---------------------------------------------------------------------------
# Knowledge operations
# ---------------------------------------------------------------------------

class TestKnowledgeOps:
    def test_perform_rag_query(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"results": []})
        result = client.perform_rag_query("test query", 5, None)
        assert result == {"results": []}
        _, kwargs = mock_session.request.call_args
        assert kwargs["json"] == {"query": "test query", "match_count": 5}

    def test_perform_rag_query_with_source(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={})
        client.perform_rag_query("q", 3, "my_source")
        _, kwargs = mock_session.request.call_args
        assert kwargs["json"]["source"] == "my_source"

    def test_search_code_examples(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"examples": []})
        result = client.search_code_examples("python", 10, None)
        assert result == {"examples": []}

    def test_get_available_sources(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"sources": ["a", "b"]})
        result = client.get_available_sources()
        assert result == {"sources": ["a", "b"]}

    def test_crawl_url_minimal(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"task_id": "t1"})
        result = client.crawl_url("https://example.com")
        assert result == {"task_id": "t1"}
        _, kwargs = mock_session.request.call_args
        assert kwargs["json"] == {"url": "https://example.com"}
        assert kwargs["timeout"] == 180.0  # long_timeout

    def test_crawl_url_full_options(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={})
        client.crawl_url(
            "https://example.com",
            knowledge_type="docs",
            tags=["a", "b"],
            update_frequency=60,
            max_depth=3,
            extract_code_examples=True,
        )
        _, kwargs = mock_session.request.call_args
        payload = kwargs["json"]
        assert payload["knowledge_type"] == "docs"
        assert payload["tags"] == ["a", "b"]
        assert payload["update_frequency"] == 60
        assert payload["max_depth"] == 3
        assert payload["extract_code_examples"] is True

    def test_delete_source(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"deleted": True})
        result = client.delete_source("src-1")
        assert result == {"deleted": True}
        args, kwargs = mock_session.request.call_args
        assert args[0] == "DELETE"


# ---------------------------------------------------------------------------
# Project operations
# ---------------------------------------------------------------------------

class TestProjectOps:
    def test_list_projects(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"projects": []})
        result = client.list_projects()
        assert result == {"projects": []}

    def test_create_project(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"id": "p1"})
        result = client.create_project({"title": "Test"})
        assert result == {"id": "p1"}

    def test_get_project(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"id": "p1", "title": "T"})
        result = client.get_project("p1")
        assert result["id"] == "p1"

    def test_update_project(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"updated": True})
        result = client.update_project("p1", {"title": "New"})
        assert result == {"updated": True}

    def test_update_project_empty_fields_raises(self, client: ArchonClient) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            client.update_project("p1", {})

    def test_delete_project(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"deleted": True})
        result = client.delete_project("p1")
        assert result == {"deleted": True}

    def test_get_project_features(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"features": []})
        result = client.get_project_features("p1")
        assert result == {"features": []}


# ---------------------------------------------------------------------------
# Task operations
# ---------------------------------------------------------------------------

class TestTaskOps:
    def test_list_tasks_no_filters(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"tasks": []})
        result = client.list_tasks()
        assert result == {"tasks": []}

    def test_list_tasks_with_filters(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"tasks": []})
        client.list_tasks(status="open", project_id="p1", include_closed=True)
        _, kwargs = mock_session.request.call_args
        assert kwargs["params"]["status"] == "open"
        assert kwargs["params"]["project_id"] == "p1"
        assert kwargs["params"]["include_closed"] == "true"

    def test_create_task(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"id": "tk1"})
        result = client.create_task({"title": "Do thing"})
        assert result == {"id": "tk1"}

    def test_get_task(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"id": "tk1"})
        result = client.get_task("tk1")
        assert result["id"] == "tk1"

    def test_update_task_empty_raises(self, client: ArchonClient) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            client.update_task("tk1", {})

    def test_delete_task(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"deleted": True})
        result = client.delete_task("tk1")
        assert result == {"deleted": True}


# ---------------------------------------------------------------------------
# Document operations
# ---------------------------------------------------------------------------

class TestDocumentOps:
    def test_list_project_documents(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"docs": []})
        result = client.list_project_documents("p1")
        assert result == {"docs": []}

    def test_create_project_document(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"id": "d1"})
        result = client.create_project_document("p1", {"title": "Doc"})
        assert result == {"id": "d1"}

    def test_get_project_document(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"id": "d1"})
        result = client.get_project_document("p1", "d1")
        assert result["id"] == "d1"

    def test_update_project_document_empty_raises(self, client: ArchonClient) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            client.update_project_document("p1", "d1", {})

    def test_delete_project_document(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"deleted": True})
        result = client.delete_project_document("p1", "d1")
        assert result == {"deleted": True}


# ---------------------------------------------------------------------------
# Version operations
# ---------------------------------------------------------------------------

class TestVersionOps:
    def test_list_versions(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"versions": []})
        result = client.list_project_versions("p1", None)
        assert result == {"versions": []}

    def test_list_versions_with_field(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"versions": []})
        client.list_project_versions("p1", "features")
        _, kwargs = mock_session.request.call_args
        assert kwargs["params"] == {"field_name": "features"}

    def test_create_version(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"id": "v1"})
        result = client.create_project_version("p1", {"field_name": "features", "content": {}})
        assert result == {"id": "v1"}

    def test_get_version(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"version": 1})
        result = client.get_project_version("p1", "features", 1)
        assert result == {"version": 1}

    def test_restore_version(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={"restored": True})
        result = client.restore_project_version("p1", "features", 1)
        assert result == {"restored": True}

    def test_restore_version_with_restored_by(self, client: ArchonClient, mock_session: MagicMock) -> None:
        _set_response(mock_session, json_data={})
        client.restore_project_version("p1", "features", 1, restored_by="user@example.com")
        _, kwargs = mock_session.request.call_args
        assert kwargs["json"]["restored_by"] == "user@example.com"


# ---------------------------------------------------------------------------
# Upload document
# ---------------------------------------------------------------------------

class TestUploadDocument:
    def test_upload_existing_file(self, client: ArchonClient, mock_session: MagicMock, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        _set_response(mock_session, json_data={"uploaded": True})
        result = client.upload_document(test_file)
        assert result == {"uploaded": True}
        _, kwargs = mock_session.request.call_args
        assert "files" in kwargs

    def test_upload_nonexistent_file_raises(self, client: ArchonClient, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="document not found"):
            client.upload_document(tmp_path / "missing.txt")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

from services.archon.mcp_server import (
    handle_perform_rag_query,
    handle_search_code_examples,
    handle_get_available_sources,
    handle_crawl_single_page,
    handle_smart_crawl,
    handle_upload_document,
    handle_delete_source,
    handle_manage_project,
    handle_manage_task,
    handle_manage_document,
    handle_manage_versions,
    handle_get_project_features,
    execute_command,
    _validate_required,
    _ensure_iterable,
    COMMAND_DEFINITIONS,
    FORM_CATEGORIES,
)


class TestValidateRequired:
    def test_returns_value_when_present(self) -> None:
        assert _validate_required({"key": "val"}, "key") == "val"

    def test_raises_when_missing(self) -> None:
        with pytest.raises(ValueError, match="is required"):
            _validate_required({}, "key")

    def test_raises_when_empty_string(self) -> None:
        with pytest.raises(ValueError, match="is required"):
            _validate_required({"key": ""}, "key")


class TestEnsureIterable:
    def test_none_returns_none(self) -> None:
        assert _ensure_iterable(None) is None

    def test_string_wraps_in_list(self) -> None:
        assert _ensure_iterable("tag1") == ["tag1"]

    def test_list_returns_list(self) -> None:
        assert _ensure_iterable(["a", "b"]) == ["a", "b"]


class TestRagHandlers:
    @patch("services.archon.mcp_server.CLIENT")
    def test_handle_perform_rag_query(self, mock_client: MagicMock) -> None:
        mock_client.perform_rag_query.return_value = {"results": []}
        result = handle_perform_rag_query({"query": "test", "match_count": 10})
        mock_client.perform_rag_query.assert_called_once_with("test", 10, None)

    @patch("services.archon.mcp_server.CLIENT")
    def test_handle_perform_rag_query_with_namespace(self, mock_client: MagicMock) -> None:
        mock_client.perform_rag_query.return_value = {}
        handle_perform_rag_query({"query": "test", "namespace": "ns1"})
        mock_client.perform_rag_query.assert_called_once_with("test", 5, "ns1")

    @patch("services.archon.mcp_server.CLIENT")
    def test_handle_perform_rag_query_missing_query_raises(self, mock_client: MagicMock) -> None:
        with pytest.raises(ValueError, match="is required"):
            handle_perform_rag_query({})

    @patch("services.archon.mcp_server.CLIENT")
    def test_handle_search_code_examples(self, mock_client: MagicMock) -> None:
        mock_client.search_code_examples.return_value = {"examples": []}
        result = handle_search_code_examples({"query": "python", "match_count": 3})
        mock_client.search_code_examples.assert_called_once_with("python", 3, None)


class TestCrawlHandlers:
    @patch("services.archon.mcp_server.CLIENT")
    def test_handle_crawl_single_page(self, mock_client: MagicMock) -> None:
        mock_client.crawl_url.return_value = {"task_id": "t1"}
        result = handle_crawl_single_page({"url": "https://example.com"})
        mock_client.crawl_url.assert_called_once()
        call_args = mock_client.crawl_url.call_args
        assert call_args[0][0] == "https://example.com"

    @patch("services.archon.mcp_server.CLIENT")
    def test_handle_crawl_single_page_missing_url(self, mock_client: MagicMock) -> None:
        with pytest.raises(ValueError, match="is required"):
            handle_crawl_single_page({})

    @patch("services.archon.mcp_server.CLIENT")
    def test_handle_smart_crawl(self, mock_client: MagicMock) -> None:
        mock_client.crawl_url.return_value = {"task_id": "t2"}
        result = handle_smart_crawl({"url": "https://example.com", "max_depth": 2})
        assert result == {"task_id": "t2"}


class TestProjectHandlers:
    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_project_list(self, mock_client: MagicMock) -> None:
        mock_client.list_projects.return_value = {"projects": []}
        result = handle_manage_project({"action": "list"})
        assert result == {"projects": []}

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_project_create(self, mock_client: MagicMock) -> None:
        mock_client.create_project.return_value = {"id": "p1"}
        result = handle_manage_project({"action": "create", "title": "New Project"})
        mock_client.create_project.assert_called_once()

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_project_update(self, mock_client: MagicMock) -> None:
        mock_client.update_project.return_value = {"updated": True}
        result = handle_manage_project({
            "action": "update",
            "project_id": "p1",
            "update_fields": {"title": "Updated"},
        })
        mock_client.update_project.assert_called_once_with("p1", {"title": "Updated"})

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_project_delete(self, mock_client: MagicMock) -> None:
        mock_client.delete_project.return_value = {"deleted": True}
        result = handle_manage_project({"action": "delete", "project_id": "p1"})
        mock_client.delete_project.assert_called_once_with("p1")

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_project_get(self, mock_client: MagicMock) -> None:
        mock_client.get_project.return_value = {"id": "p1"}
        result = handle_manage_project({"action": "get", "project_id": "p1"})
        mock_client.get_project.assert_called_once_with("p1")

    def test_manage_project_unsupported_action(self) -> None:
        with pytest.raises(ValueError, match="unsupported project action"):
            handle_manage_project({"action": "foobar"})

    def test_manage_project_update_non_dict_fields(self) -> None:
        with pytest.raises(ValueError, match="must be an object"):
            handle_manage_project({
                "action": "update",
                "project_id": "p1",
                "update_fields": "not-dict",
            })


class TestTaskHandlers:
    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_task_list(self, mock_client: MagicMock) -> None:
        mock_client.list_tasks.return_value = {"tasks": []}
        result = handle_manage_task({"action": "list"})
        assert result == {"tasks": []}

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_task_create(self, mock_client: MagicMock) -> None:
        mock_client.create_task.return_value = {"id": "tk1"}
        result = handle_manage_task({
            "action": "create",
            "project_id": "p1",
            "title": "Task",
        })
        mock_client.create_task.assert_called_once()

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_task_list_by_project(self, mock_client: MagicMock) -> None:
        mock_client.list_tasks.return_value = {}
        handle_manage_task({"action": "list", "filter_by": "project", "filter_value": "p1"})
        mock_client.list_tasks.assert_called_once_with(
            status=None, project_id="p1", include_closed=None
        )

    def test_manage_task_unsupported_action(self) -> None:
        with pytest.raises(ValueError, match="unsupported task action"):
            handle_manage_task({"action": "unknown"})


class TestDocumentHandlers:
    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_document_list(self, mock_client: MagicMock) -> None:
        mock_client.list_project_documents.return_value = {"docs": []}
        result = handle_manage_document({"action": "list", "project_id": "p1"})
        assert result == {"docs": []}

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_document_create(self, mock_client: MagicMock) -> None:
        mock_client.create_project_document.return_value = {"id": "d1"}
        result = handle_manage_document({
            "action": "create",
            "project_id": "p1",
            "document_type": "spec",
            "title": "Spec Doc",
        })
        mock_client.create_project_document.assert_called_once()

    def test_manage_document_unsupported_action(self) -> None:
        with pytest.raises(ValueError, match="unsupported document action"):
            handle_manage_document({"action": "unknown", "project_id": "p1"})


class TestVersionHandlers:
    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_versions_list(self, mock_client: MagicMock) -> None:
        mock_client.list_project_versions.return_value = {"versions": []}
        result = handle_manage_versions({"action": "list", "project_id": "p1"})
        assert result == {"versions": []}

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_versions_create(self, mock_client: MagicMock) -> None:
        mock_client.create_project_version.return_value = {"id": "v1"}
        result = handle_manage_versions({
            "action": "create",
            "project_id": "p1",
            "field_name": "features",
            "content": {"items": []},
        })
        mock_client.create_project_version.assert_called_once()

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_versions_get(self, mock_client: MagicMock) -> None:
        mock_client.get_project_version.return_value = {"version": 1}
        result = handle_manage_versions({
            "action": "get",
            "project_id": "p1",
            "field_name": "features",
            "version_number": 1,
        })
        mock_client.get_project_version.assert_called_once_with("p1", "features", 1)

    @patch("services.archon.mcp_server.CLIENT")
    def test_manage_versions_restore(self, mock_client: MagicMock) -> None:
        mock_client.restore_project_version.return_value = {"restored": True}
        result = handle_manage_versions({
            "action": "restore",
            "project_id": "p1",
            "field_name": "features",
            "version_number": 2,
        })
        mock_client.restore_project_version.assert_called_once()

    def test_manage_versions_content_not_dict(self) -> None:
        with pytest.raises(ValueError, match="must be an object"):
            handle_manage_versions({
                "action": "create",
                "project_id": "p1",
                "field_name": "features",
                "content": "not-dict",
            })

    def test_manage_versions_unsupported_action(self) -> None:
        with pytest.raises(ValueError, match="unsupported version action"):
            handle_manage_versions({"action": "unknown", "project_id": "p1"})


# ---------------------------------------------------------------------------
# execute_command routing
# ---------------------------------------------------------------------------

class TestExecuteCommand:
    @patch("services.archon.mcp_server.CLIENT")
    def test_unknown_cmd_raises(self, mock_client: MagicMock) -> None:
        with pytest.raises(ValueError, match="unknown_cmd"):
            execute_command("nonexistent_cmd", {})

    def test_no_cmd_raises(self) -> None:
        with pytest.raises(ValueError, match="is required"):
            execute_command(None, {})

    @patch("services.archon.mcp_server.CLIENT")
    def test_cmd_payload_strips_cmd_key(self, mock_client: MagicMock) -> None:
        mock_client.perform_rag_query.return_value = {}
        execute_command("perform_rag_query", {"cmd": "perform_rag_query", "query": "q"})
        mock_client.perform_rag_query.assert_called_once_with("q", 5, None)

    def test_form_get(self) -> None:
        result = execute_command("form.get", {})
        assert "form" in result
        assert "name" in result["form"]

    def test_form_switch(self) -> None:
        result = execute_command("form.switch", {"name": "test-form"})
        assert result["ok"] is True
        assert "form" in result


# ---------------------------------------------------------------------------
# COMMAND_DEFINITIONS / FORM_CATEGORIES coverage
# ---------------------------------------------------------------------------

class TestCommandDefinitions:
    def test_all_commands_have_handlers(self) -> None:
        for cmd, meta in COMMAND_DEFINITIONS.items():
            assert "description" in meta, f"{cmd} missing description"
            assert "handler" in meta, f"{cmd} missing handler"
            assert callable(meta["handler"]), f"{cmd} handler not callable"

    def test_all_categories_reference_valid_commands(self) -> None:
        for cat_name, cat_data in FORM_CATEGORIES.items():
            assert "description" in cat_data, f"{cat_name} missing description"
            assert "commands" in cat_data, f"{cat_name} missing commands"
            for cmd in cat_data["commands"]:
                assert cmd in COMMAND_DEFINITIONS, f"{cmd} in {cat_name} not defined"


# ---------------------------------------------------------------------------
# Source delete handler
# ---------------------------------------------------------------------------

class TestDeleteSourceHandler:
    @patch("services.archon.mcp_server.CLIENT")
    def test_delete_source_with_source_id(self, mock_client: MagicMock) -> None:
        mock_client.delete_source.return_value = {"deleted": True}
        result = handle_delete_source({"source_id": "s1"})
        mock_client.delete_source.assert_called_once_with("s1")

    @patch("services.archon.mcp_server.CLIENT")
    def test_delete_source_with_source(self, mock_client: MagicMock) -> None:
        mock_client.delete_source.return_value = {"deleted": True}
        result = handle_delete_source({"source": "s1"})
        mock_client.delete_source.assert_called_once_with("s1")

    def test_delete_source_missing_raises(self) -> None:
        with pytest.raises(ValueError, match="is required"):
            handle_delete_source({})


# ---------------------------------------------------------------------------
# Upload document handler
# ---------------------------------------------------------------------------

class TestUploadDocumentHandler:
    @patch("services.archon.mcp_server.CLIENT")
    def test_upload_with_tags_string(self, mock_client: MagicMock, tmp_path: Path) -> None:
        test_file = tmp_path / "doc.txt"
        test_file.write_text("content")
        mock_client.upload_document.return_value = {"uploaded": True}
        result = handle_upload_document({"path": str(test_file), "tags": "single-tag"})
        mock_client.upload_document.assert_called_once()

    @patch("services.archon.mcp_server.CLIENT")
    def test_upload_with_json_tags(self, mock_client: MagicMock, tmp_path: Path) -> None:
        test_file = tmp_path / "doc.txt"
        test_file.write_text("content")
        mock_client.upload_document.return_value = {"uploaded": True}
        handle_upload_document({"path": str(test_file), "tags": json.dumps(["a", "b"])})
        call_kwargs = mock_client.upload_document.call_args
        assert call_kwargs[1]["tags"] == ["a", "b"]

    def test_upload_missing_path_raises(self) -> None:
        with pytest.raises(ValueError, match="is required"):
            handle_upload_document({})


# ---------------------------------------------------------------------------
# Get project features handler
# ---------------------------------------------------------------------------

class TestGetProjectFeaturesHandler:
    @patch("services.archon.mcp_server.CLIENT")
    def test_get_features(self, mock_client: MagicMock) -> None:
        mock_client.get_project_features.return_value = {"features": []}
        result = handle_get_project_features({"project_id": "p1"})
        mock_client.get_project_features.assert_called_once_with("p1")

    def test_get_features_missing_project_id(self) -> None:
        with pytest.raises(ValueError, match="is required"):
            handle_get_project_features({})
