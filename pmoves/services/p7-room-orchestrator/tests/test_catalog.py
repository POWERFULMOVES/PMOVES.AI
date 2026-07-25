"""
Tests for CatalogLoader.

Hermetic — uses fixtures from conftest.py that build a temp pmoves/ subtree.
"""

from __future__ import annotations

import json

import pytest

from catalog import CatalogError, CatalogLoader, ManifestError


def test_load_returns_two_rooms(hermetic_settings, catalog_with_two_rooms):
    loader = CatalogLoader(hermetic_settings)
    cat = loader.catalog()
    assert cat["schema_version"] == "1.2.0"
    assert len(cat["rooms"]) == 2


def test_list_rooms_returns_shallow_copies(hermetic_settings, catalog_with_two_rooms):
    loader = CatalogLoader(hermetic_settings)
    rows = loader.list_rooms()
    assert len(rows) == 2
    assert all("current_stage" in r for r in rows)


def test_get_room_row_found_and_missing(hermetic_settings, catalog_with_two_rooms):
    loader = CatalogLoader(hermetic_settings)
    row = loader.get_room_row("ready.room.test")
    assert row is not None
    assert row["current_stage"] == "rehearsal"
    assert loader.get_room_row("does.not.exist") is None


def test_current_stage_lookup(hermetic_settings, catalog_with_two_rooms):
    loader = CatalogLoader(hermetic_settings)
    assert loader.current_stage("ready.room.test") == "rehearsal"
    assert loader.current_stage("does.not.exist") is None


def test_get_manifest_validates_against_schema(hermetic_settings, catalog_with_two_rooms):
    loader = CatalogLoader(hermetic_settings)
    manifest = loader.get_manifest("ready.room.test")
    assert manifest["room_id"] == "ready.room.test"
    assert manifest["display_name"] == "ready.room.test Test Room"


def test_get_manifest_missing_room_raises(hermetic_settings, catalog_with_two_rooms):
    loader = CatalogLoader(hermetic_settings)
    with pytest.raises(ManifestError, match="not in catalog"):
        loader.get_manifest("does.not.exist")


def test_get_manifest_missing_file_raises(hermetic_settings, catalog_with_two_rooms, rooms_dir):
    # Remove the manifest file but keep the catalog row
    (rooms_dir / "ready.room.test.json").unlink()
    loader = CatalogLoader(hermetic_settings)
    with pytest.raises(ManifestError, match="manifest file not found"):
        loader.get_manifest("ready.room.test")


def test_get_manifest_invalid_json_raises(hermetic_settings, catalog_with_two_rooms, rooms_dir):
    (rooms_dir / "ready.room.test.json").write_text("{not json")
    loader = CatalogLoader(hermetic_settings)
    with pytest.raises(ManifestError, match="not valid JSON"):
        loader.get_manifest("ready.room.test")


def test_update_stage_atomic_writeback(hermetic_settings, catalog_with_two_rooms, tmp_path):
    loader = CatalogLoader(hermetic_settings)
    new_row = loader.update_stage("ready.room.test", "live", reason="test promotion")
    assert new_row["current_stage"] == "live"
    assert new_row["stage_source"] == "P7 transition (catalog writeback)"
    assert "stage_verified_at" in new_row

    # Re-read from disk to confirm atomic writeback landed
    reloaded = CatalogLoader(hermetic_settings)
    reloaded.reload()
    assert reloaded.current_stage("ready.room.test") == "live"


def test_update_stage_invalid_stage_raises(hermetic_settings, catalog_with_two_rooms):
    loader = CatalogLoader(hermetic_settings)
    with pytest.raises(CatalogError, match="invalid stage"):
        loader.update_stage("ready.room.test", "bogus")


def test_update_stage_unknown_room_raises(hermetic_settings, catalog_with_two_rooms):
    loader = CatalogLoader(hermetic_settings)
    with pytest.raises(CatalogError, match="not in catalog"):
        loader.update_stage("does.not.exist", "live")


def test_reload_picks_up_disk_changes(hermetic_settings, catalog_with_two_rooms, rooms_dir):
    loader = CatalogLoader(hermetic_settings)
    # Manually edit the catalog on disk
    cat = json.loads((rooms_dir / "catalog.json").read_text())
    cat["schema_version"] = "1.3.0"
    (rooms_dir / "catalog.json").write_text(json.dumps(cat))
    new_cat = loader.reload()
    assert new_cat["schema_version"] == "1.3.0"
