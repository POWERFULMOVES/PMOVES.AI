"""
P7 Catalog Loader
=================

Loads and manages the room catalog (`pmoves/config/rooms/catalog.json`) and
per-room manifests. Validates manifests against `room.manifest.v1.schema.json`.
Supports atomic writeback of `current_stage` for transitions.

The catalog is the source of truth for which rooms exist and their current
lifecycle stage. Manifests are loaded on demand for transition gating.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import jsonschema

try:
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover
    Registry = None
    Resource = None

from config import P7Settings


LOG = logging.getLogger("p7.catalog")


# Canonical stage set (matches ROOMS_ON_A_STAGE.md and ROOM_MANIFEST_CONTRACT.md).
# NOT the apps[].status vocabulary (planned/active/deprecated).
VALID_STAGES = {"rehearsal", "live", "review", "archive"}


class CatalogError(Exception):
    """Raised when the catalog is malformed or a room lookup fails."""


class ManifestError(Exception):
    """Raised when a per-room manifest fails schema validation."""


class CatalogLoader:
    """
    In-memory catalog + on-demand manifest loader.

    Thread-safe: a single RWLock protects catalog mutations while many readers
    can be in flight. Manifests are loaded fresh on each call (no cache) to
    keep memory low; transition latency is bounded by disk read time.
    """

    def __init__(self, settings: P7Settings):
        self._settings = settings
        self._lock = threading.RLock()
        self._catalog: Dict[str, Any] = {"schema_version": "1.0.0", "rooms": []}
        self._schema: Optional[Dict[str, Any]] = None
        self._schema_load_error: Optional[str] = None
        self.reload()

    # ---- catalog ----

    def reload(self) -> Dict[str, Any]:
        """Re-read the catalog from disk. Returns the new in-memory snapshot."""
        with self._lock:
            path = self._settings.catalog_path
            if not path.exists():
                LOG.warning("catalog not found at %s; starting empty", path)
                self._catalog = {"schema_version": "1.0.0", "rooms": []}
                return self._catalog
            try:
                data = json.loads(path.read_text())
                if "rooms" not in data or not isinstance(data["rooms"], list):
                    raise CatalogError(f"catalog at {path} has no 'rooms' array")
                self._catalog = data
                LOG.info("catalog loaded: schema_version=%s rooms=%d",
                         data.get("schema_version", "?"), len(data["rooms"]))
                return self._catalog
            except json.JSONDecodeError as exc:
                raise CatalogError(f"catalog at {path} is not valid JSON: {exc}") from exc

    def catalog(self) -> Dict[str, Any]:
        """Return a shallow copy of the current catalog snapshot."""
        with self._lock:
            return dict(self._catalog)

    def list_rooms(self) -> List[Dict[str, Any]]:
        """Return the room rows (each with `current_stage` if catalog schema v1.2+)."""
        with self._lock:
            return list(self._catalog.get("rooms", []))

    def get_room_row(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Return the catalog row for a single room, or None if not found."""
        with self._lock:
            for row in self._catalog.get("rooms", []):
                if row.get("room_id") == room_id:
                    return dict(row)
        return None

    def current_stage(self, room_id: str) -> Optional[str]:
        """Return the current stage for a room, or None if not in catalog."""
        row = self.get_room_row(room_id)
        if row is None:
            return None
        return row.get("current_stage")

    def update_stage(self, room_id: str, new_stage: str, reason: str = "") -> Dict[str, Any]:
        """
        Atomic writeback of `current_stage` for a room.

        Updates the in-memory catalog, then writes to disk via temp-file +
        rename. Returns the updated row.

        Raises CatalogError if the room is not in the catalog or the stage is invalid.
        """
        if new_stage not in VALID_STAGES:
            raise CatalogError(f"invalid stage {new_stage!r}; must be one of {sorted(VALID_STAGES)}")
        with self._lock:
            row = None
            for r in self._catalog.get("rooms", []):
                if r.get("room_id") == room_id:
                    row = r
                    break
            if row is None:
                raise CatalogError(f"room {room_id!r} not in catalog")
            row["current_stage"] = new_stage
            row["stage_source"] = "P7 transition (catalog writeback)"
            row["stage_verified_at"] = _utcnow_iso()
            # atomic write: write to temp file in same dir, then rename
            self._write_catalog_atomic(self._catalog)
            LOG.info("catalog writeback: room=%s new_stage=%s reason=%s",
                     room_id, new_stage, reason or "(none)")
            return dict(row)

    def _write_catalog_atomic(self, data: Dict[str, Any]) -> None:
        """Write the catalog to disk atomically (write-temp + rename)."""
        path = self._settings.catalog_path
        path.parent.mkdir(parents=True, exist_ok=True)
        # NamedTemporaryFile in same dir ensures rename is atomic on POSIX + Windows
        fd, tmp_path = tempfile.mkstemp(
            prefix=".catalog.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            # best-effort cleanup of the temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ---- manifest ----

    def _schema_or_error(self) -> Dict[str, Any]:
        if self._schema is None:
            if self._schema_load_error:
                raise ManifestError(self._schema_load_error)
            sp = self._settings.manifest_schema_path
            if not sp.exists():
                self._schema_load_error = f"manifest schema not found at {sp}"
                raise ManifestError(self._schema_load_error)
            try:
                self._schema = json.loads(sp.read_text())
                # $id is required for $ref resolution via referencing.Registry
                self._schema.setdefault("$id", sp.resolve().as_uri())
            except json.JSONDecodeError as exc:
                self._schema_load_error = f"manifest schema at {sp} is not valid JSON: {exc}"
                raise ManifestError(self._schema_load_error) from exc
        return self._schema

    def _skill_schema_or_error(self) -> Optional[Dict[str, Any]]:
        """Load the skill.binding.v1.schema.json if it lives next to the room schema."""
        sp = self._settings.manifest_schema_path
        skill_path = sp.parent / "skill.binding.v1.schema.json"
        if not skill_path.exists():
            return None
        try:
            schema = json.loads(skill_path.read_text())
            schema.setdefault("$id", skill_path.resolve().as_uri())
            return schema
        except json.JSONDecodeError:
            return None

    def get_manifest(self, room_id: str) -> Dict[str, Any]:
        """
        Load a per-room manifest from disk and validate against the schema.

        Returns the parsed manifest dict. Raises ManifestError on missing or
        schema-invalid manifests.
        """
        row = self.get_room_row(room_id)
        if row is None:
            raise ManifestError(f"room {room_id!r} not in catalog")
        manifest_name = row.get("manifest")
        if not manifest_name:
            raise ManifestError(
                f"room {room_id!r} catalog row has no 'manifest' filename"
            )
        path = self._settings.rooms_dir_path / manifest_name
        if not path.exists():
            raise ManifestError(f"manifest file not found: {path}")
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ManifestError(f"manifest at {path} is not valid JSON: {exc}") from exc
        errors = self.validate_manifest(data)
        if errors:
            raise ManifestError(
                f"manifest {path} fails schema validation: {'; '.join(errors)}"
            )
        return data

    def validate_manifest(self, manifest: Dict[str, Any]) -> List[str]:
        """Return a list of validation errors (empty list = valid)."""
        schema = self._schema_or_error()
        skill_schema = self._skill_schema_or_error()
        # Bundle room + skill schemas in a Registry so $ref to the skill
        # binding schema resolves. (Mirrors validate_room_manifests.py.)
        if Registry is not None and Resource is not None and skill_schema is not None:
            registry = Registry().with_resources([
                (schema["$id"], Resource.from_contents(schema)),
                (skill_schema["$id"], Resource.from_contents(skill_schema)),
            ])
            validator = jsonschema.Draft202012Validator(schema, registry=registry)
        else:
            validator = jsonschema.Draft202012Validator(schema)
        return [
            f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
            for err in validator.iter_errors(manifest)
        ]


def _utcnow_iso() -> str:
    """Return current UTC time in ISO 8601 with 'Z' suffix."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
