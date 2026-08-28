#!/usr/bin/env python3
"""NATS publisher for cache-hit cost-savings attribution.

Publishes to tokenism.attribution.recorded.v1 on cache hits.
Fire-and-forget, fail-open on AVAILABILITY -- fail-CLOSED on CORRECTNESS.

WHY THE ASYMMETRY. This subject feeds the settlement ledger, and `address` is
inside the Merkle leaf: a wrong record cannot be amended later, only appended
to. Dropping an attribution event costs one cache-hit's savings. Writing a
malformed one poisons a ledger meant to be authoritative. So a failed
CONNECTION is still shrugged off; a payload that does not satisfy the contract
is refused and logged at error level, never published.

WHAT WAS MEASURED, 2026-08-25. The payload this module sent shared ZERO fields
with its own contract:

    contract required : chit_id, address, action, amount, week, timestamp
    payload sent      : agent_id, tokens_saved, cost_saved_usd, cache_key
    additionalProperties: false

Six of six required fields missing, four of four sent fields forbidden. There
are no callers today and `tokenism_enabled` defaults to True, so the first call
site anyone wires fires it. `pmoves/services/common/events.py:38` has carried
`validate_payload(topic, payload)` -- driven by the same
`contracts/topics.json` -- the whole time; this module never called it.

NOT FIXED HERE, deliberately: the field mapping. `address` (string, tokenism.*)
versus `contributor_id` (uuid, token.*) is an open design question with both
ledgers still empty, and inventing an `address` to satisfy a validator would
put a guess inside a Merkle leaf -- a worse outcome than the bug being fixed.
Refusing to publish is correct until that is decided.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from config import CacheSettings, get_settings

logger = logging.getLogger(__name__)


def _contracts_dir() -> Path | None:
    """Locate contracts/, or None if unreachable from this image."""
    env_dir = os.environ.get("PMOVES_CONTRACTS_DIR")
    if env_dir and (Path(env_dir) / "topics.json").is_file():
        return Path(env_dir)
    # Repo layout: pmoves/services/semantic-cache/ -> pmoves/contracts/.
    # In the container this file is copied to /app/tokenism.py, which has
    # only two parents -- indexing [2] there raised IndexError instead of
    # returning None, turning a clean refusal into a crash on the publish
    # path. Walking the parents cannot go out of range.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "contracts"
        if (candidate / "topics.json").is_file():
            return candidate
    return None


def validate_attribution(payload: dict) -> tuple[bool, str]:
    """(ok, reason). Refuses when the contract cannot be checked.

    An unreachable schema is NOT treated as permission to publish. That is the
    exact shape of the defect this guard exists to stop -- a check reporting
    success because it could not run.
    """
    contracts = _contracts_dir()
    if contracts is None:
        return False, (
            "contracts/topics.json is not reachable from this image, so the "
            "payload cannot be checked; refusing rather than writing an "
            "unvalidated record to the settlement ledger. Set "
            "PMOVES_CONTRACTS_DIR or mount contracts/."
        )
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return False, "jsonschema is not installed; cannot validate, refusing"

    try:
        topics = json.loads((contracts / "topics.json").read_text(encoding="utf-8"))
        rel = topics["topics"][TokenismPublisher.SUBJECT]["schema"]
        schema = json.loads((contracts / rel).read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError) as exc:
        return False, f"schema for {TokenismPublisher.SUBJECT} unusable: {exc}"

    from jsonschema import FormatChecker

    checker = FormatChecker()
    errors = sorted(
        Draft202012Validator(schema, format_checker=checker).iter_errors(payload),
        key=lambda e: list(e.path),
    )
    if errors:
        return False, "; ".join(e.message for e in errors[:6])

    # A FormatChecker ALONE does not enforce `format: date-time`. The
    # date-time checker is only registered when `rfc3339_validator` is
    # installed, and it is not here. Measured: `timestamp: "not-a-date"`
    # produced ZERO errors both with and without the FormatChecker. Adding
    # it and calling the job done would ship a validator that LOOKS
    # format-checking and is not -- the exact defect this guard removes.
    #
    # So the ledger's timestamp is checked explicitly rather than left to an
    # optional dependency being present.
    if "date-time" not in checker.checkers:
        stamp = payload.get("timestamp")
        try:
            datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return False, (
                f"timestamp {stamp!r} is not a valid date-time (checked "
                "explicitly: jsonschema's date-time checker is unregistered "
                "without rfc3339_validator, so the schema's `format` "
                "annotation alone enforces nothing here)"
            )
    return True, "ok"


class TokenismPublisher:
    """Publishes attribution events to NATS for Tokenism cost tracking."""

    SUBJECT = "tokenism.attribution.recorded.v1"

    def __init__(self, settings: CacheSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._nc = None

    async def _ensure_connected(self) -> bool:
        """Lazily connect to NATS. Returns False if unavailable."""
        if self._nc is not None:
            return True
        if not self.settings.tokenism_enabled:
            return False
        try:
            from nats import connect as nats_connect

            self._nc = await nats_connect(self.settings.nats_url)
            return True
        except Exception as exc:
            logger.debug("NATS connection failed (fail-open): %s", exc)
            self._nc = None
            return False

    async def publish_attribution(
        self,
        agent_id: str,
        tokens_saved: int,
        cost_saved_usd: float,
        cache_key: str,
    ) -> None:
        """Publish a cache-hit attribution event."""
        if not await self._ensure_connected():
            return
        try:
            payload = {
                "agent_id": agent_id,
                "tokens_saved": tokens_saved,
                "cost_saved_usd": cost_saved_usd,
                "cache_key": cache_key,
            }
            ok, reason = validate_attribution(payload)
            if not ok:
                # error, not debug: this is a dropped ledger write, and the
                # caller is entitled to know its attribution never landed.
                logger.error(
                    "Tokenism attribution REFUSED (not published) for agent=%s "
                    "cache_key=%s: %s",
                    agent_id, cache_key, reason,
                )
                return
            await self._nc.publish(
                self.SUBJECT, json.dumps(payload).encode()
            )
        except Exception as exc:
            logger.debug("Tokenism publish failed (fail-open): %s", exc)

    async def close(self) -> None:
        if self._nc is not None:
            try:
                await self._nc.close()
            except Exception:
                pass
            self._nc = None
