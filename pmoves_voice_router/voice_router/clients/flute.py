"""Flute relay client (scaffold): request-builder only; transport deferred."""

from __future__ import annotations

DEFAULT_PATH = "/v1/relay/speak"


def build_flute_request(
    text: str,
    *,
    stream: bool = True,
    base_url: str | None = None,
) -> dict:
    """Build a Flute relay speak request (pure builder, no network)."""
    if not text:
        raise ValueError("text is required")
    url = (base_url or "http://flute.invalid").rstrip("/") + DEFAULT_PATH
    accept = "text/event-stream" if stream else "audio/wav"
    return {
        "method": "POST",
        "url": url,
        "headers": {"Content-Type": "application/json", "Accept": accept},
        "payload": {"text": text, "stream": stream},
    }