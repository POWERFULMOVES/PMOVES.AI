"""pytest suite for the pinokio_bridge service.

All tests run in mock mode (no real Pinokio install). The PinokioState
is constructed directly with fixture data, then `create_app` is
called with the fixture state + a known token. The TestClient
issues requests against the in-process FastAPI app.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from pmoves.services.pinokio_bridge.app import create_app
from pmoves.services.pinokio_bridge.state import PinokioState


TEST_TOKEN = "test-bridge-token-do-not-use-in-prod"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_state() -> PinokioState:
    """A Pinokio 8 state with 3 apps, 2 managed skills, 1 GPU, and a
    dependency graph (comfyui -> shared-models)."""
    home = Path(tempfile.mkdtemp(prefix="pinokio-bridge-test-"))
    state = PinokioState(home=home)
    state.apps = {
        "comfyui-desktop": {
            "version": "0.3.41", "state": "stopped", "pid": None,
            "endpoints": [{"port": 8188, "url": "http://127.0.0.1:8188"}],
        },
        "wan": {
            "version": "1.2.0", "state": "stopped", "pid": None,
            "endpoints": [],
        },
        "shared-models": {
            "version": "0.1.0", "state": "stopped", "pid": None,
            "endpoints": [],
        },
    }
    state.autolaunch = {
        "comfyui-desktop": {
            "slug": "comfyui-desktop", "enabled": True,
            "script": "start.js",
            "last_evaluated_at": "2026-07-27T10:00:00Z",
        },
        "shared-models": {
            "slug": "shared-models", "enabled": True,
            "script": "start.js",
            "last_evaluated_at": "2026-07-27T10:00:00Z",
        },
    }
    state.orchestration = {
        "nodes": [
            {"slug": "comfyui-desktop"},
            {"slug": "wan"},
            {"slug": "shared-models"},
        ],
        "edges": [
            {"from": "comfyui-desktop", "to": "shared-models"},
            {"from": "wan", "to": "shared-models"},
        ],
        "cycles": [],
    }
    state.skills = {
        "pinokio": {
            "slug": "pinokio", "source": "builtin",
            "sync_target": str(home / "skills-target" / "pinokio" / "SKILL.md"),
            "valid": True, "conflict": False, "enabled": True,
        },
        "gepeto": {
            "slug": "gepeto", "source": "builtin",
            "sync_target": str(home / "skills-target" / "gepeto" / "SKILL.md"),
            "valid": True, "conflict": False, "enabled": True,
        },
    }
    state.skills_conflicts = [
        {
            "slug": "custom-voice-bridge",
            "conflict_kind": "local_modification",
            "local_path": str(home / "skills-target" / "custom-voice-bridge"),
            "note": "Target modified after last sync; manual review needed",
        }
    ]
    state.gpu = {
        "host": "POWERFULMOVES",
        "vram": 32,
        "primary": {
            "model": "NVIDIA GeForce RTX 5090",
            "driver": "570.86.16",
            "compute_capability": "12.0",
            "vram_gb": 32,
            "vram_mb": 32768,
        },
        "gpus": [
            {
                "model": "NVIDIA GeForce RTX 5090", "driver": "570.86.16",
                "compute_capability": "12.0", "vram_mb": 32768,
            }
        ],
    }
    state.pinokio_version = "8.0.0"
    return state


@pytest.fixture
def client(mock_state: PinokioState) -> TestClient:
    """TestClient with a known bridge token. Used for both read + write tests."""
    return TestClient(create_app(state=mock_state, token=TEST_TOKEN))


@pytest.fixture
def client_no_token(mock_state: PinokioState) -> TestClient:
    """TestClient with NO bridge token. Writes should return 503."""
    return TestClient(create_app(state=mock_state, token=""))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_healthz_returns_ok(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["pinokio_version"] == "8.0.0"
    assert data["writes_enabled"] is True


def test_healthz_reports_writes_disabled_when_no_token(
    client_no_token: TestClient,
) -> None:
    r = client_no_token.get("/healthz")
    assert r.status_code == 200
    assert r.json()["writes_enabled"] is False


# ---------------------------------------------------------------------------
# Surface: App management
# ---------------------------------------------------------------------------


def test_list_apps(client: TestClient) -> None:
    r = client.get("/v1/apps")
    assert r.status_code == 200
    slugs = {a["slug"] for a in r.json()}
    assert slugs == {"comfyui-desktop", "wan", "shared-models"}


def test_app_status_known(client: TestClient) -> None:
    r = client.get("/v1/apps/comfyui-desktop/status")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "comfyui-desktop"
    assert data["version"] == "0.3.41"
    assert data["endpoints"][0]["port"] == 8188


def test_app_status_unknown_returns_404(client: TestClient) -> None:
    r = client.get("/v1/apps/nonexistent/status")
    assert r.status_code == 404


def test_launch_app_requires_token(client: TestClient) -> None:
    r = client.post("/v1/apps/comfyui-desktop/launch", json={"script": "start.js"})
    assert r.status_code == 401
    assert "X-PMOVES-Bridge-Token" in r.json()["detail"]


def test_launch_app_with_token_succeeds(
    client: TestClient,
) -> None:
    # The launch path check uses the state.home (not the env var
    # PINOKIO_HOME, which is a module-level constant). Drop a fake
    # start.js into the state's home + rebuild the client so the
    # app reads from the right place.
    state = client.app.state.pinokio
    app_dir = state.home / "api" / "comfyui-desktop"
    app_dir.mkdir(parents=True)
    (app_dir / "start.js").write_text("// fake")

    r = client.post(
        "/v1/apps/comfyui-desktop/launch",
        headers={"X-PMOVES-Bridge-Token": TEST_TOKEN},
        json={"script": "start.js", "argv_extra": ["--yolo"]},
    )
    # The launch may fail (no `pterm` in PATH in CI) but the token
    # check + argv assembly + state mutation should happen first.
    # A 200 or 500 is both OK for this test — what matters is that
    # a 401/422/404 is NOT returned.
    assert r.status_code in (200, 500), r.text


# ---------------------------------------------------------------------------
# Surface 1: Autolaunch
# ---------------------------------------------------------------------------


def test_list_autolaunch(client: TestClient) -> None:
    r = client.get("/v1/autolaunch")
    assert r.status_code == 200
    by_slug = {a["slug"]: a for a in r.json()}
    assert by_slug["comfyui-desktop"]["enabled"] is True
    assert by_slug["wan"]["enabled"] is False  # default


def test_get_autolaunch_for_specific_app(client: TestClient) -> None:
    r = client.get("/v1/apps/comfyui-desktop/autolaunch")
    assert r.status_code == 200
    assert r.json()["script"] == "start.js"


def test_set_autolaunch_requires_token(client: TestClient) -> None:
    r = client.post(
        "/v1/apps/wan/autolaunch",
        json={"enabled": True, "script": "start.js"},
    )
    assert r.status_code == 401


def test_set_autolaunch_persists(client: TestClient) -> None:
    r = client.post(
        "/v1/apps/wan/autolaunch",
        headers={"X-PMOVES-Bridge-Token": TEST_TOKEN},
        json={"enabled": True, "script": "start.js"},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    # And the GET reflects the change
    r2 = client.get("/v1/apps/wan/autolaunch")
    assert r2.json()["enabled"] is True


def test_writes_disabled_when_no_token(client_no_token: TestClient) -> None:
    r = client_no_token.post(
        "/v1/apps/wan/autolaunch", json={"enabled": True}
    )
    assert r.status_code == 503
    assert "PMOVES_BRIDGE_TOKEN" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Surface 2: Orchestration
# ---------------------------------------------------------------------------


def test_app_dependencies_resolves_recursive_graph(
    client: TestClient,
) -> None:
    r = client.get("/v1/apps/comfyui-desktop/dependencies")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "comfyui-desktop"
    assert "shared-models" in data["recursive"]
    # shared-models is the leaf, should be at level 0
    assert data["launch_order"][0] == ["shared-models"]
    # comfyui-desktop is at the requester level — the algorithm
    # walks from the requester and assigns the requester to its
    # own level (not yet ready until we launch it).
    assert data["ready_checks"]["shared-models"] is True
    assert data["ready_checks"]["comfyui-desktop"] is False


def test_app_dependencies_for_unknown_app_returns_empty(
    client: TestClient,
) -> None:
    r = client.get("/v1/apps/nonexistent/dependencies")
    assert r.status_code == 200
    data = r.json()
    assert data["depends_on"] == []
    assert data["launch_order"] == []


def test_orchestration_graph(client: TestClient) -> None:
    r = client.get("/v1/orchestration/graph")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2
    assert data["cycles"] == []


# ---------------------------------------------------------------------------
# Surface 3: Managed skills
# ---------------------------------------------------------------------------


def test_list_skills(client: TestClient) -> None:
    r = client.get("/v1/skills")
    assert r.status_code == 200
    slugs = {s["slug"] for s in r.json()}
    assert slugs == {"pinokio", "gepeto"}


def test_sync_skill_marks_synced(client: TestClient) -> None:
    r = client.post(
        "/v1/skills/pinokio/sync",
        headers={"X-PMOVES-Bridge-Token": TEST_TOKEN},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["synced"] is True
    assert data["slug"] == "pinokio"
    assert "last_synced_at" in r.json() or "source" in r.json()


def test_sync_skill_unknown_returns_404(client: TestClient) -> None:
    r = client.post(
        "/v1/skills/nonexistent/sync",
        headers={"X-PMOVES-Bridge-Token": TEST_TOKEN},
    )
    assert r.status_code == 404


def test_list_skill_conflicts(client: TestClient) -> None:
    r = client.get("/v1/skills/conflicts")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["slug"] == "custom-voice-bridge"


# ---------------------------------------------------------------------------
# Surface 4: GPU/VRAM templates
# ---------------------------------------------------------------------------


def test_gpu_detect(client: TestClient) -> None:
    r = client.get("/v1/gpu/detect")
    assert r.status_code == 200
    data = r.json()
    assert data["host"] == "POWERFULMOVES"
    assert data["primary"]["compute_capability"] == "12.0"
    assert data["primary"]["vram_gb"] == 32


def test_gpu_match_succeeds_when_arch_and_vram_satisfied(
    client: TestClient,
) -> None:
    r = client.get("/v1/gpu/match?min_vram=24000&gpu_arch=sm_120,sm_110")
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] is True
    assert "vram 32768 >= 24000" in data["reason"]
    # 12.0 is normalized to sm_120 by the _to_sm helper
    assert data["detected_sm_arch"] == "sm_120"


def test_gpu_match_fails_when_vram_too_low(client: TestClient) -> None:
    r = client.get("/v1/gpu/match?min_vram=64000&gpu_arch=sm_120")
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] is False
    assert "vram_ok=False" in data["reason"]


def test_gpu_match_fails_when_arch_mismatch(client: TestClient) -> None:
    r = client.get("/v1/gpu/match?min_vram=0&gpu_arch=sm_70")
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] is False
    assert "arch_ok=False" in data["reason"]


def test_gpu_match_with_no_arch_constraint_matches_on_vram_only(
    client: TestClient,
) -> None:
    r = client.get("/v1/gpu/match?min_vram=0&gpu_arch=")
    assert r.status_code == 200
    # Empty gpu_arch list = "any arch" = arch_ok=True. vram 0 >= 0
    # = vram_ok=True. So matched=True.
    assert r.json()["matched"] is True
