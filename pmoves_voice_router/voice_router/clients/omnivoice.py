"""OmniVoice client (scaffold): request-builder only; transport deferred."""

from __future__ import annotations

DEFAULT_PATH = "/synthesize"


def build_omnivoice_request(
    text: str,
    *,
    voice: str = "default",
    base_url: str | None = None,
) -> dict:
    """Build an OmniVoice synth request (pure builder, no network)."""
    if not text:
        raise ValueError("text is required")
    url = (base_url or "http://omnivoice.invalid").rstrip("/") + DEFAULT_PATH
    return {
        "method": "POST",
        "url": url,
        "headers": {"Content-Type": "application/json"},
        "payload": {"text": text, "voice": voice},
    }