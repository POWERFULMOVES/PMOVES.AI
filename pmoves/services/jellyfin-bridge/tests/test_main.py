from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient


MODULE_NAME = "test_jellyfin_bridge_main"


def _load_module(
    monkeypatch: pytest.MonkeyPatch, extra_env: Optional[Dict[str, str]] = None
):
    env = {
        "JELLYFIN_URL": "http://jf.local",
        "JELLYFIN_API_KEY": "token",
        "JELLYFIN_USER_ID": "user-123",
        "SUPA_REST_URL": "http://supabase.local",
        "JELLYFIN_DEFAULT_LIBRARY_IDS": "core",
        "JELLYFIN_DEFAULT_MEDIA_TYPES": "Movie,Series",
        "JELLYFIN_SERVER_ID": "srv-1",
        "JELLYFIN_DEVICE_ID": "dev-9",
        "JELLYFIN_AUTOLINK": "false",
    }
    if extra_env:
        env.update(extra_env)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    module_path = Path(__file__).resolve().parents[1] / "main.py"
    sys.modules.pop(MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(MODULE_NAME, module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - importlib safety
        raise RuntimeError("failed to create module spec for jellyfin bridge")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


class _DummyResponse:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - no-op
        return None

    def json(self) -> Dict[str, Any]:
        return self._payload


def test_search_accepts_rich_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module(monkeypatch)
    captured: Dict[str, Any] = {}

    def fake_get(url: str, params: Dict[str, Any] | None = None, **kwargs: Any):
        captured["url"] = url
        captured["params"] = params or {}
        items = [{"Id": "1", "Name": "Example Project", "ProductionYear": 2024, "Type": "Movie"}]
        return _DummyResponse({"Items": items})

    monkeypatch.setattr(module.httpx, "get", fake_get)

    query_params: List[tuple[str, Any]] = [
        ("query", "Example"),
        ("library_ids", "lib1"),
        ("library_ids", "lib2"),
        ("media_types", "Movie"),
        ("exclude_item_types", "Episode"),
        ("fields", "Overview"),
        ("sort_by", "ProductionYear"),
        ("sort_order", "Descending"),
        ("parent_id", "collection-99"),
        ("year", "2024"),
        ("recursive", "false"),
        ("limit", "5"),
    ]

    with TestClient(module.app) as client:
        response = client.get("/jellyfin/search", params=query_params)

    assert response.status_code == 200
    data = response.json()
    assert captured["url"].endswith("/Users/user-123/Items")
    params = captured["params"]
    assert params["searchTerm"] == "Example"
    assert params["LibraryIds"] == "lib1,lib2"
    assert params["IncludeItemTypes"] == "Movie"
    assert params["ExcludeItemTypes"] == "Episode"
    assert params["Fields"] == "Overview"
    assert params["SortBy"] == "ProductionYear"
    assert params["SortOrder"] == "Descending"
    assert params["ParentId"] == "collection-99"
    assert params["Years"] == "2024"
    assert params["Recursive"] == "false"
    assert params["Limit"] == "5"
    assert data["items"][0]["Id"] == "1"
    assert data["applied_filters"]["LibraryIds"] == "lib1,lib2"


def test_map_by_title_picks_best_scored_item(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module(monkeypatch)

    video_row = {
        "video_id": "vid-1",
        "title": "Example Project",
        "meta": {"release_year": 2023},
    }

    monkeypatch.setattr(module, "_supa_get", lambda table, match: [video_row] if table == "videos" else [])
    patch_calls: List[Dict[str, Any]] = []

    def fake_patch(table: str, match: Dict[str, Any], patch: Dict[str, Any]):
        patch_calls.append(patch)
        return {}

    monkeypatch.setattr(module, "_supa_patch", fake_patch)

    def fake_get(url: str, params: Dict[str, Any] | None = None, **kwargs: Any):
        assert params and params.get("LibraryIds") == "core"
        items = [
            {
                "Id": "item-a",
                "Name": "Example Project Extended",
                "ProductionYear": 2023,
                "Type": "Movie",
                "Path": "/movies/item-a",
            },
            {
                "Id": "item-b",
                "Name": "Another Example",
                "ProductionYear": 2018,
                "Type": "Movie",
                "Path": "/movies/item-b",
            },
        ]
        return _DummyResponse({"Items": items})

    monkeypatch.setattr(module.httpx, "get", fake_get)

    with TestClient(module.app) as client:
        response = client.post(
            "/jellyfin/map-by-title",
            json={"video_id": "vid-1", "search_filters": {"library_ids": ["core"]}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["mapped"]["jellyfin_item_id"] == "item-a"
    assert patch_calls, "expected Supabase patch to be invoked"
    meta = patch_calls[0]["meta"]
    assert meta["jellyfin_item_id"] == "item-a"
    assert meta["jellyfin_match_score"] >= 0.25
    assert meta["jellyfin_library_ids"] == ["core"]


def test_playback_url_emits_ticks_and_media_source(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module(monkeypatch)
    video_row = {
        "video_id": "vid-9",
        "meta": {
            "jellyfin_item_id": "item-9",
            "jellyfin_media_source_id": "source-77",
            "jellyfin_server_id": "srv-override",
        },
    }

    monkeypatch.setattr(module, "_supa_get", lambda table, match: [video_row])

    with TestClient(module.app) as client:
        response = client.post(
            "/jellyfin/playback-url",
            json={"video_id": "vid-9", "t": 12.345},
        )

    assert response.status_code == 200
    data = response.json()
    params = data["params"]
    assert params["mediaSourceId"] == "source-77"
    assert params["serverId"] == "srv-override"
    assert params["startTime"] == "12"
    assert params["startTimeTicks"] == str(int(round(12.345 * 10_000_000)))
    assert data["url"].startswith("http://jf.local/web/index.html#!/details?")
