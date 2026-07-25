"""
Tests for TransitionEngine.

Hermetic — uses fixtures from conftest.py. NATS publisher is replaced with a
fake that records calls; the engine treats `publish_*` calls as best-effort.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from catalog import CatalogLoader
from transition import (
    ChecklistError,
    InvalidTransitionError,
    TransitionEngine,
    TransitionError,
)


class FakePublisher:
    """Records publish calls; no real NATS."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def publish(self, subject: str, payload: Dict[str, Any]) -> bool:
        self.calls.append({"subject": subject, "payload": payload})
        return True

    async def publish_room_launched(self, **kwargs):  # pragma: no cover
        return await self.publish("p7.nats.launch", kwargs)

    async def publish_room_session(self, **kwargs):  # pragma: no cover
        return await self.publish("p7.nats.session", kwargs)

    async def publish_room_updated(self, **kwargs):
        return await self.publish("room.session.updated.v1", kwargs)

    async def publish_config_reloaded(self, **kwargs):  # pragma: no cover
        return await self.publish("pmoves.config.rooms.reloaded.v1", kwargs)

    async def connect(self):
        return True

    async def disconnect(self):
        return None

    @property
    def connected(self):
        return True


@pytest.fixture
def fake_publisher():
    return FakePublisher()


@pytest.fixture
def engine(hermetic_settings, catalog_with_two_rooms, fake_publisher):
    loader = CatalogLoader(hermetic_settings)
    return TransitionEngine(hermetic_settings, loader, fake_publisher)


# ---- State machine ----

@pytest.mark.asyncio
async def test_rehearsal_to_live_with_card_passes(engine, fake_publisher):
    result = await engine.transition(
        "ready.room.test", "live", reason="test", requester="tester"
    )
    assert result["current_stage"] == "live"
    assert result["previous_stage"] == "rehearsal"
    assert result["noop"] is False
    # catalog writeback landed
    assert engine._catalog.current_stage("ready.room.test") == "live"
    # signed event published
    assert any(c["subject"] == "room.session.updated.v1" for c in fake_publisher.calls)


@pytest.mark.asyncio
async def test_rehearsal_to_live_without_card_fails_checklist(engine):
    with pytest.raises(ChecklistError) as exc_info:
        await engine.transition(
            "notready.room.test", "live", reason="test", requester="tester"
        )
    assert len(exc_info.value.details["unchecked"]) > 0
    # any of the unchecked items should mention card_id
    assert any("card_id" in item for item in exc_info.value.details["unchecked"])


@pytest.mark.asyncio
async def test_live_to_review_is_ungated(engine, fake_publisher):
    # First get to live
    await engine.transition("ready.room.test", "live", reason="setup", requester="tester")
    # then to review
    result = await engine.transition(
        "ready.room.test", "review", reason="audit", requester="tester"
    )
    assert result["current_stage"] == "review"


@pytest.mark.asyncio
async def test_live_to_archive_ungated(engine):
    await engine.transition("ready.room.test", "live", reason="setup", requester="tester")
    result = await engine.transition(
        "ready.room.test", "archive", reason="retire", requester="tester"
    )
    assert result["current_stage"] == "archive"


@pytest.mark.asyncio
async def test_rehearsal_to_review_rejected(engine):
    with pytest.raises(InvalidTransitionError):
        await engine.transition(
            "ready.room.test", "review", reason="bad path", requester="tester"
        )


@pytest.mark.asyncio
async def test_rehearsal_to_archive_rejected(engine):
    with pytest.raises(InvalidTransitionError):
        await engine.transition(
            "ready.room.test", "archive", reason="bad path", requester="tester"
        )


@pytest.mark.asyncio
async def test_archive_is_terminal(engine):
    await engine.transition("ready.room.test", "live", reason="x", requester="t")
    await engine.transition("ready.room.test", "archive", reason="x", requester="t")
    with pytest.raises(InvalidTransitionError):
        await engine.transition("ready.room.test", "live", reason="x", requester="t")


@pytest.mark.asyncio
async def test_idempotent_same_stage_is_noop(engine, fake_publisher):
    result = await engine.transition(
        "ready.room.test", "rehearsal", reason="noop", requester="t"
    )
    assert result["noop"] is True
    # No publish event for noop
    assert not any(c["subject"] == "room.session.updated.v1" for c in fake_publisher.calls)


@pytest.mark.asyncio
async def test_invalid_target_stage_rejected(engine):
    with pytest.raises(TransitionError, match="invalid target_stage"):
        await engine.transition(
            "ready.room.test", "bogus", reason="x", requester="t"
        )


# ---- CHIT checklist ----

def test_checklist_passes_for_fully_valid_manifest(engine):
    manifest = engine._catalog.get_manifest("ready.room.test")
    unchecked = engine.check_chit_activation(manifest)
    assert unchecked == [], f"expected all-pass, got: {unchecked}"


def test_checklist_catches_missing_card_id(engine):
    manifest = engine._catalog.get_manifest("notready.room.test")
    unchecked = engine.check_chit_activation(manifest)
    assert any("card_id" in item for item in unchecked)
    # Without card_id, items 2 + 3 should be skipped (not just fail)
    assert any("skipped" in item for item in unchecked)


def test_checklist_catches_unknown_card_id(engine, temp_pmoves_root):
    # Corrupt the signing_cards to remove our card
    import yaml
    path = temp_pmoves_root / "pmoves" / "config" / "signing_identity_cards.yaml"
    path.write_text(yaml.safe_dump({"cards": {}}))
    engine._signing_cards = None  # force reload
    manifest = engine._catalog.get_manifest("ready.room.test")
    unchecked = engine.check_chit_activation(manifest)
    assert any("not found in signing_identity_cards" in item for item in unchecked)


def test_checklist_catches_inactive_card(engine, temp_pmoves_root):
    import yaml
    path = temp_pmoves_root / "pmoves" / "config" / "signing_identity_cards.yaml"
    cards = {
        "00000000-0000-4000-8000-000000000099": {
            "card_id": "00000000-0000-4000-8000-000000000099",
            "active": False,  # <-- inactive
            "ml": {"primary_method": "ssh"},
            "h": {"agent_id": "test-agent"},
        }
    }
    path.write_text(yaml.safe_dump({"cards": cards}))
    engine._signing_cards = None
    manifest = engine._catalog.get_manifest("ready.room.test")
    unchecked = engine.check_chit_activation(manifest)
    assert any("active" in item for item in unchecked)


def test_checklist_catches_agent_id_mismatch(engine, temp_pmoves_root):
    import yaml
    path = temp_pmoves_root / "pmoves" / "config" / "signing_identity_cards.yaml"
    cards = {
        "00000000-0000-4000-8000-000000000099": {
            "card_id": "00000000-0000-4000-8000-000000000099",
            "active": True,
            "ml": {"primary_method": "ssh"},
            "h": {"agent_id": "DIFFERENT-AGENT"},  # <-- mismatch
        }
    }
    path.write_text(yaml.safe_dump({"cards": cards}))
    engine._signing_cards = None
    manifest = engine._catalog.get_manifest("ready.room.test")
    unchecked = engine.check_chit_activation(manifest)
    assert any("agent_id" in item for item in unchecked)


def test_checklist_catches_invalid_primary_method(engine, temp_pmoves_root):
    import yaml
    path = temp_pmoves_root / "pmoves" / "config" / "signing_identity_cards.yaml"
    cards = {
        "00000000-0000-4000-8000-000000000099": {
            "card_id": "00000000-0000-4000-8000-000000000099",
            "active": True,
            "ml": {"primary_method": "carrier-pigeon"},  # <-- invalid
            "h": {"agent_id": "test-agent"},
        }
    }
    path.write_text(yaml.safe_dump({"cards": cards}))
    engine._signing_cards = None
    manifest = engine._catalog.get_manifest("ready.room.test")
    unchecked = engine.check_chit_activation(manifest)
    assert any("primary_method" in item for item in unchecked)


def test_checklist_catches_unreachable_servers(engine):
    # Add mcp_servers to the ready room's manifest that aren't in agent_registry
    manifest = engine._catalog.get_manifest("ready.room.test")
    manifest["mcp_servers"] = ["nonexistent-server"]
    unchecked = engine.check_chit_activation(manifest)
    assert any("nonexistent-server" in item for item in unchecked)


def test_checklist_catches_missing_pgrst_var(engine, temp_pmoves_root, monkeypatch):
    # Wipe env.shared so PGRST var is missing
    (temp_pmoves_root / "pmoves" / "env.shared").write_text("# empty\n")
    monkeypatch.delenv("PGRST_DB_EXTRA_SEARCH_PATH", raising=False)
    engine._sidecar_env = None
    manifest = engine._catalog.get_manifest("ready.room.test")
    unchecked = engine.check_chit_activation(manifest)
    assert any("PGRST" in item for item in unchecked)


def test_checklist_catches_missing_chit_keys_in_env(engine, temp_pmoves_root):
    # Wipe env.shared
    (temp_pmoves_root / "pmoves" / "env.shared").write_text("# empty\n")
    engine._sidecar_env = None
    manifest = engine._catalog.get_manifest("ready.room.test")
    unchecked = engine.check_chit_activation(manifest)
    assert any("CHIT_REQUIRE_SIGNATURE" in item or "CHIT_DECRYPT_ANCHORS" in item for item in unchecked)
