"""
P7 Transition Engine
====================

Implements the room lifecycle state machine and the canonical CHIT activation
checklist (from `pmoves/docs/ROOM_MANIFEST_CONTRACT.md`).

State machine (per ROOMS_ON_A_STAGE.md):

    rehearsal → live        (gated: full CHIT checklist must pass)
    live      → review      (ungated)
    live      → archive     (ungated)
    review    → live        (ungated, e.g. room promoted back from review)
    review    → archive     (ungated)
    archive   → (terminal; no transitions)

The same stage on either side is a no-op (idempotent transition).

CHIT checklist (from ROOM_MANIFEST_CONTRACT.md § "CHIT Signing-Card Activation
Checklist", canonical — 7 items, 2026-07-20 open-room-lane consolidation):

    1. meta.chit.card_id is present and non-empty, OR the owning room skill
       supplies an active card id at runtime that resolves to a row in
       signing_identity_cards.yaml.
    2. The referenced card passes signing-card.v1.schema.json validation:
       card_id is a UUID, ml.primary_method ∈ {ssh, gpg, github-app},
       h.agent_id matches the manifest's agent_id, active: true.
    3. signing_identity_cards.yaml has a row for the room's operating agent
       with matching key material.
    4. sign-trail returns a signed envelope, OR unsigned-local advisory is
       explicitly accepted by the operator (P7_ALLOW_UNSIGNED_LOCAL=true).
    5. All mcp_servers and a2a_servers declared in the manifest are present
       in agent_registry.yaml and are reachable in the target topology mode
       (we check presence; reachability is the operator's job).
    6. PGRST_DB_EXTRA_SEARCH_PATH includes the schemas the room's skills touch
       (we check the env var is set; PostgREST HTTP probe is a smoke test).
    7. CHIT_REQUIRE_SIGNATURE / CHIT_DECRYPT_ANCHORS documented in sidecar.env
       for the target topology gradient (we read sidecar.env and confirm the
       toggles are set; matching the gradient is the operator's policy).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import yaml

from catalog import CatalogError, CatalogLoader, ManifestError
from config import P7Settings
from nats_pub import NATSPublisher


LOG = logging.getLogger("p7.transition")


# ---- State machine ----

VALID_STAGES = {"rehearsal", "live", "review", "archive"}

# Transition table: from_stage -> set of valid next stages
TRANSITIONS: Dict[str, set] = {
    "rehearsal": {"live"},
    "live": {"review", "archive"},
    "review": {"live", "archive"},
    "archive": set(),  # terminal
}


# ---- Errors ----

class TransitionError(Exception):
    """Base for transition errors."""

    def __init__(self, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class InvalidTransitionError(TransitionError):
    """State-machine rejection (wrong from/to, or terminal)."""
    def __init__(self, current: str, target: str):
        super().__init__(
            f"invalid transition: {current} → {target}",
            status_code=409,
            details={"current_stage": current, "target_stage": target,
                     "valid_next_stages": sorted(TRANSITIONS.get(current, set()))},
        )


class ChecklistError(TransitionError):
    """One or more CHIT activation checklist items failed."""
    def __init__(self, unchecked: List[str]):
        super().__init__(
            f"CHIT activation checklist failed: {len(unchecked)} item(s) unchecked",
            status_code=422,
            details={"unchecked": unchecked},
        )


# ---- Engine ----

class TransitionEngine:
    """
    Mediates room stage transitions.

    Reads catalog/manifests via CatalogLoader, publishes lifecycle events via
    NATSPublisher, and applies the CHIT activation checklist on rehearsal→live.
    """

    def __init__(self, settings: P7Settings, catalog: CatalogLoader,
                 publisher: NATSPublisher):
        self._settings = settings
        self._catalog = catalog
        self._publisher = publisher
        # Lazy-loaded resources
        self._signing_cards: Optional[Dict[str, Any]] = None
        self._agent_registry: Optional[Dict[str, Any]] = None
        self._sidecar_env: Optional[Dict[str, str]] = None

    # ---- public API ----

    async def transition(
        self,
        room_id: str,
        target_stage: str,
        reason: str,
        requester: str,
    ) -> Dict[str, Any]:
        """
        Transition a room to a new stage.

        Returns the updated catalog row + the signed NATS payload that was
        published (or attempted).

        Raises:
            ManifestError — room not in catalog, manifest missing/invalid
            InvalidTransitionError — state machine rejects (409)
            ChecklistError — checklist items unchecked (422)
            CatalogError — atomic writeback failure
        """
        if target_stage not in VALID_STAGES:
            raise TransitionError(
                f"invalid target_stage {target_stage!r}; must be one of {sorted(VALID_STAGES)}",
                status_code=400,
            )

        # 1. Load manifest + current stage.
        # Both touch disk (manifest read + JSON validate); offload to a thread
        # so the event loop isn't blocked during transitions. The CatalogLoader's
        # internal `threading.RLock` keeps state safe across threads.
        manifest = await asyncio.to_thread(self._catalog.get_manifest, room_id)
        current = self._catalog.current_stage(room_id)

        # 2. Idempotent no-op
        if current == target_stage:
            LOG.info("transition no-op: room=%s already at %s", room_id, target_stage)
            return {
                "room_id": room_id,
                "current_stage": current,
                "previous_stage": current,
                "target_stage": target_stage,
                "noop": True,
                "catalog_row": self._catalog.get_room_row(room_id),
            }

        # 3. State machine
        valid_next = TRANSITIONS.get(current or "", set())
        if target_stage not in valid_next:
            raise InvalidTransitionError(current or "(none)", target_stage)

        # 4. CHIT gate (only on rehearsal → live)
        if current == "rehearsal" and target_stage == "live":
            unchecked = self.check_chit_activation(manifest)
            if unchecked:
                raise ChecklistError(unchecked)

        # 5. Atomic writeback to catalog (disk I/O — offload).
        updated_row = await asyncio.to_thread(
            self._catalog.update_stage, room_id, target_stage, reason
        )

        # 6. Publish signed event
        await self._publisher.publish_room_updated(
            room_id=room_id,
            previous_stage=current or "(none)",
            new_stage=target_stage,
            reason=reason,
            requester=requester,
        )

        return {
            "room_id": room_id,
            "current_stage": target_stage,
            "previous_stage": current,
            "target_stage": target_stage,
            "noop": False,
            "reason": reason,
            "requester": requester,
            "catalog_row": updated_row,
        }

    # ---- CHIT activation checklist ----

    def check_chit_activation(self, manifest: Dict[str, Any]) -> List[str]:
        """
        Run all 7 items of the canonical CHIT activation checklist against
        a manifest. Return a list of human-readable descriptions of the
        items that are NOT satisfied. Empty list = all pass.
        """
        unchecked: List[str] = []

        # Item 1: meta.chit.card_id present and non-empty
        meta = manifest.get("meta") or {}
        chit_block = meta.get("chit") or {}
        card_id = chit_block.get("card_id")
        if not card_id or not isinstance(card_id, str):
            unchecked.append(
                "1. manifest.meta.chit.card_id is missing or empty"
            )
            # Items 2/3 depend on the card; mark them as skipped but
            # continue evaluating items 4-7 (which are independent of
            # the card and may surface other issues the operator needs
            # to fix in the same iteration).
            unchecked.append("2. signing card validation: skipped (no card_id)")
            unchecked.append("3. signing_identity_cards.yaml: skipped (no card_id)")
            card = None
        else:
            # Item 2: signing card validates (UUID, primary_method, agent_id match, active)
            card = self._find_signing_card(card_id)
            if card is None:
                unchecked.append(
                    f"2. signing card {card_id!r} not found in signing_identity_cards.yaml"
                )
            else:
                card_errors = self._validate_signing_card(card, manifest.get("agent_id", ""))
                unchecked.extend(f"2. {e}" for e in card_errors)

            # Item 3: signing_identity_cards.yaml has a row for the room's operating agent
            # (only meaningful when a card was found)
            if card is not None:
                agent_id = manifest.get("agent_id", "")
                if card.get("h", {}).get("agent_id") != agent_id:
                    unchecked.append(
                        f"3. signing_identity_cards.yaml: card.h.agent_id "
                        f"{card.get('h', {}).get('agent_id')!r} != manifest.agent_id {agent_id!r}"
                    )

        # Item 4: sign-trail signed, or unsigned-local allowed
        # P7's runtime equivalent is: P7 itself has a signing key (or allows
        # unsigned-local). We check the operator-acknowledged config knob.
        if not self._settings.service_card_id and not self._settings.allow_unsigned_local:
            unchecked.append(
                "4. P7 has no signing card (P7_SERVICE_CARD_ID) AND unsigned-local is not allowed"
            )
        elif not self._settings.service_card_id:
            LOG.info("checklist item 4: unsigned-local advisory accepted by operator")
        # else: P7 has its own signing card — signed envelope will be published.

        # Item 5: mcp_servers / a2a_servers declared in manifest are present in agent_registry
        registry = self._load_agent_registry()
        if registry is None:
            unchecked.append(
                "5. agent_registry.yaml not loaded; cannot verify mcp_servers / a2a_servers"
            )
        else:
            servers_declared = (
                list(manifest.get("mcp_servers", []) or [])
                + list(manifest.get("a2a_servers", []) or [])
            )
            registry_servers = set(registry.get("servers", {}).keys()) if isinstance(
                registry.get("servers"), dict
            ) else set()
            for s in servers_declared:
                if s not in registry_servers:
                    unchecked.append(
                        f"5. server {s!r} declared in manifest not present in agent_registry.yaml"
                    )

        # Item 6: PGRST_DB_EXTRA_SEARCH_PATH includes the room's schemas
        # The canonical sidecar config is `pmoves/env.shared` (the file
        # is referenced as `sidecar.env` in ROOM_MANIFEST_CONTRACT.md for
        # historical reasons; we treat them as the same source of truth).
        # We check both the file contents and the process env directly.
        sidecar_env = self._load_sidecar_env()
        pgrst_set = bool(sidecar_env.get("PGRST_DB_EXTRA_SEARCH_PATH"))
        if not pgrst_set:
            unchecked.append(
                "6. PGRST_DB_EXTRA_SEARCH_PATH not set in env.shared (sidecar.env) or process env"
            )

        # Item 7: CHIT_REQUIRE_SIGNATURE / CHIT_DECRYPT_ANCHORS documented
        chit_keys = {"CHIT_REQUIRE_SIGNATURE", "CHIT_DECRYPT_ANCHORS"}
        missing_keys = [k for k in chit_keys if k not in sidecar_env]
        if missing_keys:
            unchecked.append(
                f"7. env.shared (sidecar.env) is missing keys: {missing_keys}"
            )
        elif self._settings.chit_require_signature and sidecar_env.get("CHIT_REQUIRE_SIGNATURE", "").lower() not in ("true", "1", "yes"):
            unchecked.append(
                "7. CHIT_REQUIRE_SIGNATURE is set to non-truthy value; P7 chit_require_signature=true"
            )

        return unchecked

    # ---- Lazy resource loaders ----

    def _find_signing_card(self, card_id: str) -> Optional[Dict[str, Any]]:
        cards = self._load_signing_cards()
        if cards is None:
            return None
        return cards.get(card_id)

    def _load_signing_cards(self) -> Optional[Dict[str, Dict[str, Any]]]:
        if self._signing_cards is not None:
            return self._signing_cards
        path = self._settings.signing_cards_path_resolved
        if not path.exists():
            LOG.warning("signing_cards not found at %s", path)
            self._signing_cards = {}
            return self._signing_cards
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except Exception as exc:
            LOG.error("signing_cards load failed: %s", exc)
            self._signing_cards = {}
            return self._signing_cards
        # Three accepted shapes (see pmoves/config/signing_identity_cards.yaml):
        # 1. {"cards": [{"card_id": ..., "ml": {...}, "h": {...}}, ...]}
        #    (canonical — the production file uses a list)
        # 2. {"cards": {"<uuid>": {...}, ...}}
        #    (older shape; kept for backward compat)
        # 3. flat dict-of-cards {"<uuid>": {...}, ...}
        cards_field = data.get("cards") if isinstance(data, dict) else None
        if isinstance(cards_field, list):
            # Index by card_id; skip entries without one.
            indexed: Dict[str, Dict[str, Any]] = {}
            for entry in cards_field:
                if isinstance(entry, dict) and entry.get("card_id"):
                    indexed[entry["card_id"]] = entry
            self._signing_cards = indexed
        elif isinstance(cards_field, dict):
            self._signing_cards = cards_field
        elif isinstance(data, dict):
            self._signing_cards = data
        else:
            LOG.warning("signing_cards has unexpected shape: %s", type(data))
            self._signing_cards = {}
        return self._signing_cards

    def _validate_signing_card(self, card: Dict[str, Any], manifest_agent_id: str) -> List[str]:
        """Validate a single card against signing-card.v1.schema.json's spirit."""
        errors: List[str] = []
        # card_id is a UUID
        try:
            uuid.UUID(card.get("card_id", ""))
        except (ValueError, TypeError):
            errors.append("card_id is not a valid UUID")
        # active: true
        if not card.get("active"):
            errors.append("card.active is not true")
        # ml.primary_method ∈ {ssh, gpg, github-app}
        pm = (card.get("ml") or {}).get("primary_method")
        if pm not in ("ssh", "gpg", "github-app"):
            errors.append(f"card.ml.primary_method {pm!r} not in [ssh, gpg, github-app]")
        # h.agent_id matches
        h_agent = (card.get("h") or {}).get("agent_id")
        if h_agent != manifest_agent_id:
            errors.append(
                f"card.h.agent_id {h_agent!r} != manifest.agent_id {manifest_agent_id!r}"
            )
        return errors

    def _load_agent_registry(self) -> Optional[Dict[str, Any]]:
        if self._agent_registry is not None:
            return self._agent_registry
        path = self._settings.agent_registry_path_resolved
        if not path.exists():
            LOG.warning("agent_registry not found at %s", path)
            self._agent_registry = {}
            return self._agent_registry
        try:
            data = yaml.safe_load(path.read_text()) or {}
            self._agent_registry = data
        except Exception as exc:
            LOG.error("agent_registry load failed: %s", exc)
            self._agent_registry = {}
        return self._agent_registry

    def _load_sidecar_env(self) -> Dict[str, str]:
        """Load the canonical sidecar config (pmoves/env.shared; historically
        referred to as `sidecar.env` in ROOM_MANIFEST_CONTRACT.md) and merge
        with process env. Process env wins — useful for tests and for runtime
        overrides (e.g. docker compose env_file).
        """
        if self._sidecar_env is not None:
            return self._sidecar_env
        path = self._settings.resolved("pmoves/env.shared")
        env: Dict[str, str] = {}
        if path.exists():
            for line in path.read_text(errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")
        # Process env wins so tests can override cleanly.
        for k, v in os.environ.items():
            env[k] = v
        self._sidecar_env = env
        return self._sidecar_env
