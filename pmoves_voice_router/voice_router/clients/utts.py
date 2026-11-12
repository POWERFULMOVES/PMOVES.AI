"""Ultimate TTS Studio client (scaffold): request-builder only; transport deferred."""

from __future__ import annotations

DEFAULT_PATH = "/v1/utter"


def build_utts_request(
    text: str,
    *,
    speaker: str = "default",
    base_url: str | None = None,
) -> dict:
    """Build an Ultimate TTS Studio utter request (pure builder, no network)."""
    if not text:
        raise ValueError("text is required")
    url = (base_url or "http://utts.invalid").rstrip("/") + DEFAULT_PATH
    return {
        "method": "POST",
        "url": url,
        "headers": {"Content-Type": "application/json"},
        "payload": {"text": text, "speaker": speaker},
    }