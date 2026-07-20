"""
Pytest configuration for P7 service tests.

Each test gets a hermetic temp dir containing a fresh catalog, signing
cards, agent registry, and a 2-room manifest set. The P7_* env vars are
overridden via Pydantic settings so the service uses the temp paths.

Tests run without NATS (the publisher's `connect` is a no-op when
nats_url is unreachable; logs-only mode kicks in and asserts still pass).
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

import pytest


# Make the service modules importable. The Dockerfile uses sys.path shims in
# each module; we replicate that here for pytest.
SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

VALID_MANIFEST_TEMPLATE = {
    "room_id": "{room_id}",
    "version": "1.0.0",
    "display_name": "{room_id} Test Room",
    "description": "Test room",
    "agent_id": "test-agent",
    "shell": {
        "theme": {"theme_id": "test"},
        "layout": {
            "default_route": "/test",
            "panels": [{"panel_id": "main", "kind": "chat", "position": "center", "size": 100, "pinned": True}],
        },
    },
    "apps": [
        {"app_id": "chat-app", "kind": "chat", "route": "/chat", "capabilities": ["chat"]},
    ],
    "notebook": {
        "provider": "external",
        "workspace_ref": "test",
        "sync": {"mode": "mirrored", "writeback_targets": ["entries"]},
    },
    "skill_bindings": [
        {
            "binding_id": "test-binding",
            "skill_id": "test-skill",
            "room_id": "{room_id}",
            "surface": {"app_id": "chat-app", "target": "toolbar"},
            "execution": {"mode": "inline"},
            "context": {"sources": ["room-state"]},
            "outputs": [{"target": "chat-response", "delivery": "notify", "artifact_type": "text"}],
        }
    ],
    "policies": {
        "model_routing": "hybrid",
        "publish": {"allow_nats_emit": True, "allow_external_publish": False, "allowed_subjects": []},
        "memory": {"graphiti": False, "notebook_writeback": False, "chit_handoff": False},
    },
}


def _write_manifest(rooms_dir: Path, room_id: str, extra_meta: dict | None = None) -> Path:
    # Format the template with the room_id (template uses {room_id} placeholders)
    data = json.loads(json.dumps(VALID_MANIFEST_TEMPLATE))  # deep copy
    text = json.dumps(data)
    text = text.replace("{room_id}", room_id)
    data = json.loads(text)
    if extra_meta:
        data["meta"] = extra_meta
    path = rooms_dir / f"{room_id}.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def _write_signing_cards(path: Path, cards: dict) -> None:
    path.write_text(yaml_dump({"cards": cards}))


def _write_agent_registry(path: Path, servers: list[str]) -> None:
    path.write_text(yaml_dump({"servers": {s: {"url": f"http://{s}"} for s in servers}}))


def _write_env_shared(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines))


def yaml_dump(obj) -> str:
    import yaml
    return yaml.safe_dump(obj, sort_keys=False)


@pytest.fixture
def temp_pmoves_root(tmp_path: Path) -> Path:
    """Create a hermetic pmoves/ subtree in a temp dir and return the root."""
    root = tmp_path
    (root / "pmoves").mkdir()
    rooms_dir = root / "pmoves" / "config" / "rooms"
    rooms_dir.mkdir(parents=True)
    contracts_dir = root / "pmoves" / "contracts" / "schemas" / "room"
    contracts_dir.mkdir(parents=True)
    config_dir = root / "pmoves" / "config"
    config_dir.mkdir(exist_ok=True)
    return root


@pytest.fixture
def rooms_dir(temp_pmoves_root: Path) -> Path:
    return temp_pmoves_root / "pmoves" / "config" / "rooms"


@pytest.fixture
def manifest_schema(temp_pmoves_root: Path) -> Path:
    """Copy the real schema into the temp root so jsonschema can load it.
    Also copies the referenced skill.binding.v1.schema.json so $ref resolves.
    """
    real_dir = Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "room"
    target_dir = temp_pmoves_root / "pmoves" / "contracts" / "schemas" / "room"
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in ("room.manifest.v1.schema.json", "skill.binding.v1.schema.json"):
        src = real_dir / name
        if src.exists():
            (target_dir / name).write_text(src.read_text())
    return target_dir / "room.manifest.v1.schema.json"


@pytest.fixture
def catalog_with_two_rooms(rooms_dir: Path, manifest_schema: Path) -> Path:
    """
    Write a catalog + 2 manifests: one ready-for-live (with meta.chit.card_id),
    one without (so the CHIT checklist will fail).
    """
    # Ready room: has a meta.chit.card_id
    ready_meta = {
        "chit": {
            "card_id": "00000000-0000-4000-8000-000000000099",
            "creator_id": "test",
        }
    }
    _write_manifest(rooms_dir, "ready.room.test", extra_meta=ready_meta)
    # Not-ready room: no meta.chit.card_id
    _write_manifest(rooms_dir, "notready.room.test", extra_meta={})

    catalog = {
        "schema_version": "1.2.0",
        "rooms": [
            {
                "room_id": "ready.room.test",
                "agent_id": "test-agent",
                "alter": "ready-test",
                "display_name": "Ready Room",
                "manifest": "ready.room.test.json",
                "current_stage": "rehearsal",
                "stage_source": "test",
                "stage_verified_at": "2026-07-20T00:00:00Z",
            },
            {
                "room_id": "notready.room.test",
                "agent_id": "test-agent",
                "alter": "notready-test",
                "display_name": "NotReady Room",
                "manifest": "notready.room.test.json",
                "current_stage": "rehearsal",
                "stage_source": "test",
                "stage_verified_at": "2026-07-20T00:00:00Z",
            },
        ],
    }
    catalog_path = rooms_dir / "catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2))
    return catalog_path


@pytest.fixture
def signing_cards_with_match(temp_pmoves_root: Path) -> Path:
    """Write a signing_cards.yaml with a row for 'test-agent' and the card_id used above."""
    path = temp_pmoves_root / "pmoves" / "config" / "signing_identity_cards.yaml"
    cards = {
        "00000000-0000-4000-8000-000000000099": {
            "card_id": "00000000-0000-4000-8000-000000000099",
            "active": True,
            "ml": {"primary_method": "ssh"},
            "h": {"agent_id": "test-agent"},
        }
    }
    _write_signing_cards(path, cards)
    return path


@pytest.fixture
def agent_registry_with_servers(temp_pmoves_root: Path) -> Path:
    path = temp_pmoves_root / "pmoves" / "config" / "agent_registry.yaml"
    _write_agent_registry(path, ["test-mcp", "test-a2a"])
    return path


@pytest.fixture
def env_shared(temp_pmoves_root: Path) -> Path:
    path = temp_pmoves_root / "pmoves" / "env.shared"
    _write_env_shared(path, [
        "PGRST_DB_EXTRA_SEARCH_PATH=public,pmoves",
        "CHIT_REQUIRE_SIGNATURE=true",
        "CHIT_DECRYPT_ANCHORS=local",
    ])
    return path


@pytest.fixture
def hermetic_settings(
    temp_pmoves_root: Path,
    catalog_with_two_rooms: Path,
    manifest_schema: Path,
    signing_cards_with_match: Path,
    agent_registry_with_servers: Path,
    env_shared: Path,
    monkeypatch,
):
    """
    Set env vars so P7Settings reads from the temp root. Returns the P7Settings
    instance. Note: pmoves_root is set to the temp root so relative paths resolve.
    """
    monkeypatch.setenv("P7_PMOVES_ROOT", str(temp_pmoves_root))
    monkeypatch.setenv("P7_NATS_URL", "nats://127.0.0.1:1")  # unreachable; tests verify log-only fallback
    monkeypatch.setenv("P7_SERVICE_CARD_ID", "")
    monkeypatch.setenv("P7_SIGNING_KEY", "")
    monkeypatch.setenv("P7_ALLOW_UNSIGNED_LOCAL", "true")
    # Reload settings to pick up env
    from config import P7Settings
    s = P7Settings()
    return s
