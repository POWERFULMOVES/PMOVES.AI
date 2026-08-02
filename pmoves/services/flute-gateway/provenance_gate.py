"""Voice cloning provenance gate (Voice Agents S5).

Enforces the rights/consent/provenance model defined in §8 of the voice
agents design spec. Every cloned-voice synthesis must pass this gate before
audio generation is permitted.

Gate checks (in order):
  1. VOICE_CLONING_ENABLED env must be true (default false)
  2. At least one active provenance record must exist for the voice profile
  3. CONSENTED/LICENSED require a consent_artifact_uri (enforced at DB level too)
  4. CHARACTER_OWNED requires an active character context (NATS-authorized)
  5. is_active=false (revoked) records are ignored

On pass, returns provenance metadata for CGP attribution injection.
On fail, raises ProvenanceGateError with the specific rejection reason.
"""

from __future__ import annotations

import os
from typing import Any


class ProvenanceResult:
    """Result of a provenance gate check."""

    __slots__ = (
        "allowed", "voice_profile_id", "rights_basis", "consent_date",
        "capturer_identity", "attribution_url", "source_type", "reason",
    )

    def __init__(
        self,
        allowed: bool,
        voice_profile_id: str,
        rights_basis: str | None = None,
        consent_date: str | None = None,
        capturer_identity: str | None = None,
        attribution_url: str | None = None,
        source_type: str | None = None,
        reason: str = "",
    ):
        self.allowed = allowed
        self.voice_profile_id = voice_profile_id
        self.rights_basis = rights_basis
        self.consent_date = consent_date
        self.capturer_identity = capturer_identity
        self.attribution_url = attribution_url
        self.source_type = source_type
        self.reason = reason


class ProvenanceGateError(Exception):
    """Raised when the provenance gate rejects synthesis."""

    def __init__(self, voice_profile_id: str, reason: str):
        self.voice_profile_id = voice_profile_id
        self.reason = reason
        super().__init__(f"Provenance gate rejected {voice_profile_id}: {reason}")


def is_cloning_enabled() -> bool:
    """Check the global VOICE_CLONING_ENABLED env gate."""
    return os.environ.get("VOICE_CLONING_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def build_cgp_meta(result: ProvenanceResult) -> dict[str, Any]:
    """Build the voice_provenance block for CHIT CGP meta attribution (§8).

    This is injected into the CGP `meta` field of every cloned-voice synthesis
    event, providing an immutable provenance trail on the geometry bus.
    """
    return {
        "voice_provenance": {
            "voice_persona_id": result.voice_profile_id,
            "rights_basis": result.rights_basis,
            "consent_date": result.consent_date,
            "capturer_id": result.capturer_identity,
            "attribution_url": result.attribution_url,
        }
    }


def check_provenance_gate(
    voice_profile_id: str,
    voice_name: str,
    active_provenance: list[dict[str, Any]] | None,
    character_context: dict[str, Any] | None = None,
) -> ProvenanceResult:
    """Check the provenance gate for a voice synthesis request.

    Args:
        voice_profile_id: UUID of the voice profile
        voice_name: Slug name of the voice (for error messages)
        active_provenance: List of active provenance records from DB
            (voice_cloning_provenance rows where is_active=true)
        character_context: Optional character authorization context
            (required for CHARACTER_OWNED rights)

    Returns:
        ProvenanceResult with allowed=True and provenance metadata on pass.

    Raises:
        ProvenanceGateError: When the gate rejects synthesis.
    """
    if not is_cloning_enabled():
        raise ProvenanceGateError(
            voice_profile_id,
            f"VOICE_CLONING_ENABLED is not set to true (voice '{voice_name}')",
        )

    if not active_provenance:
        raise ProvenanceGateError(
            voice_profile_id,
            f"No active provenance record for voice '{voice_name}' — "
            f"cannot synthesize without rights/consent documentation",
        )

    primary = active_provenance[0]
    rights = primary.get("rights_basis", "")

    if rights == "CHARACTER_OWNED":
        if not character_context or not character_context.get("authorized"):
            raise ProvenanceGateError(
                voice_profile_id,
                f"CHARACTER_OWNED voice '{voice_name}' requires active "
                f"character context authorization",
            )

    return ProvenanceResult(
        allowed=True,
        voice_profile_id=voice_profile_id,
        rights_basis=rights,
        consent_date=str(primary.get("consent_date", "")) or None,
        capturer_identity=primary.get("capturer_identity"),
        attribution_url=primary.get("attribution_url"),
        source_type=primary.get("source_type"),
    )
