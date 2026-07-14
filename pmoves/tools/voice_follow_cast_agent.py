#!/usr/bin/env python3
"""
Voice Follow Cast Agent

Subscribes to NATS for agent/voice responses and auto-casts to Google Cast devices.

NATS Subjects:
  - voice.agent.response.v1 (preferred)
  - agent.response.v1 (fallback)

Config via env:
  - CAST_FOLLOW_NATS_URL (default: nats://nats:pmoves@nats:4222; prod: CHIT-managed)
  - CAST_TTS_GATEWAY_URL (default: http://localhost:8060)
  - CAST_DEFAULT_DEVICE (default: None → auto-select)
  - CAST_FOLLOW_VOICE (default: default)
  - OPEN_NOTEBOOK_API_URL (optional: for logging)
  - OPEN_NOTEBOOK_API_TOKEN (required if logging enabled)
  - CAST_NOTEBOOK_ENABLED (default: false)

Example:
  export CAST_TTS_GATEWAY_URL="http://localhost:8060"
  export CAST_DEFAULT_DEVICE="Brysons Speakers speaker"
  export OPEN_NOTEBOOK_API_URL="http://localhost:5055"
  export OPEN_NOTEBOOK_API_TOKEN="your-token"
  export CAST_NOTEBOOK_ENABLED="true"

  python pmoves/tools/voice_follow_cast_agent.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from nats.aio.client import Client as NATS


def _env(name: str, default: str) -> str:
    """Get environment variable with default."""
    v = os.getenv(name)
    return v.strip() if v else default


def _resolve_nats_url() -> str:
    """
    Resolve NATS URL for host-run service.

    Handles Docker-internal URLs by translating them to host-accessible URLs.
    """
    explicit = os.getenv("CAST_FOLLOW_NATS_URL")
    if explicit and explicit.strip():
        return explicit.strip()

    nats_url = os.getenv("NATS_URL", "").strip()
    if nats_url:
        # Translate docker-only alias to host-accessible URL
        # Docker-internal alias / unset both mean "host-run" here: return the
        # host-published IPv4 port. `nats:4222` only resolves inside compose;
        # `localhost` may resolve to ::1 first while NATS binds IPv4 only.
        if nats_url.startswith("nats://nats:") or nats_url.startswith("tls://nats:"):
            return "nats://nats:pmoves@127.0.0.1:4222"
        if nats_url.startswith("nats://localhost:") or nats_url.startswith("tls://localhost:"):
            return nats_url.replace("://localhost:", "://127.0.0.1:", 1)
        return nats_url

    return "nats://nats:pmoves@127.0.0.1:4222"


def _extract_text(payload: Dict[str, Any]) -> Optional[str]:
    """Extract text from multiple envelope formats.

    Handles:
    - {"payload":{"response_text":"..."}} (voice.agent.response.v1)
    - {"response_text":"..."} or {"text":"..."} (looser publishers)
    - {"content":"..."} (alternative format)

    Returns:
        Extracted text or None if no text found.
    """
    # Check nested payload first
    inner = payload.get("payload")
    if isinstance(inner, dict):
        for key in ("response_text", "text", "content", "message"):
            val = inner.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    # Check top-level keys
    for key in ("response_text", "text", "content", "message"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return None


class NotebookClient:
    """Open-Notebook client for logging Cast events."""

    def __init__(self, api_base: str, token: str) -> None:
        """Initialize Notebook client.

        Args:
            api_base: Open-Notebook API base URL.
            token: Bearer token for authentication.
        """
        self.api_base = api_base.rstrip("/") + "/api"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    def create_source(
        self,
        title: str,
        content: str,
        source_type: str = "text",
        notebooks: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Create a source in Open-Notebook.

        Args:
            title: Source title.
            content: Source content.
            source_type: Source type ("link" or "text").
            notebooks: List of notebook names.

        Returns:
            Source ID if successful, None otherwise.
        """
        if notebooks is None:
            notebooks = ["cast-logs"]

        payload = {
            "type": source_type,
            "title": title,
            "content": content,
            "notebooks": notebooks,
            "embed": False,
            "async_processing": True,
        }

        try:
            response = httpx.post(
                f"{self.api_base}/sources",
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("id")
        except Exception as e:
            sys.stderr.write(f"[voice-follow-cast] Notebook log failed: {e}\n")
            return None


class VoiceFollowCastAgent:
    """Voice follow agent with Google Cast integration."""

    def __init__(
        self,
        nats_url: str,
        cast_gateway_url: str,
        default_device: Optional[str] = None,
        voice: str = "default",
        notebook_client: Optional[NotebookClient] = None,
    ):
        """Initialize Voice Follow Cast Agent.

        Args:
            nats_url: NATS connection URL.
            cast_gateway_url: Cast TTS Gateway API URL.
            default_device: Default Cast device name (None for auto-selection).
            voice: Voice name for TTS synthesis.
            notebook_client: Optional Open-Notebook client for logging.
        """
        self.nats_url = nats_url
        self.cast_gateway_url = cast_gateway_url.rstrip("/")
        self.default_device = default_device
        self.voice = voice
        self.notebook_client = notebook_client
        self.nc: Optional[NATS] = None
        self.running = False

    async def cast_speech(self, text: str) -> Dict[str, Any]:
        """Cast speech to Google Cast device.

        Args:
            text: Text to synthesize and cast.

        Returns:
            Response from Cast TTS Gateway.
        """
        url = f"{self.cast_gateway_url}/cast/speech"
        payload = {
            "text": text,
            "device": self.default_device,
            "voice": self.voice,
            "use_flute": True,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def log_to_notebook(
        self,
        text: str,
        result: Dict[str, Any],
        error: Optional[str] = None,
    ) -> None:
        """Log Cast event to Open-Notebook.

        Args:
            text: Text that was cast.
            result: Cast TTS Gateway response.
            error: Optional error message.
        """
        if not self.notebook_client:
            return

        timestamp = datetime.utcnow().isoformat() + "Z"
        device = result.get("device", self.default_device or "Unknown")

        if error:
            title = f"Cast Failed @ {device} - {timestamp}"
            content = f"Error: {error}\nText: {text}"
        else:
            title = f"Cast Success @ {device} - {timestamp}"
            content = f"Device: {device}\nVoice: {self.voice}\nText: {text}"

        self.notebook_client.create_source(
            title=title,
            content=content,
            source_type="text",
            notebooks=["cast-logs"],
        )

    async def handle_response(self, msg) -> None:
        """Handle agent response message.

        Args:
            msg: NATS message.
        """
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return

        if not isinstance(data, dict):
            return

        # Extract text from various envelope formats
        text = _extract_text(data)
        if not text:
            return

        # Avoid casting very long content
        if len(text) > 800:
            text = text[:800].rstrip() + "…"

        sys.stderr.write(f"[voice-follow-cast] {msg.subject}: {text[:140]}\n")

        # Cast speech
        try:
            result = await self.cast_speech(text)

            if result.get("success"):
                sys.stderr.write(f"[voice-follow-cast] Cast successful: {result.get('device')}\n")
                self.log_to_notebook(text, result)
            else:
                error = result.get("error", "Unknown error")
                sys.stderr.write(f"[voice-follow-cast] Cast failed: {error}\n")
                self.log_to_notebook(text, result, error=error)

        except Exception as e:
            error_msg = f"Cast TTS Gateway error: {e}"
            sys.stderr.write(f"[voice-follow-cast] {error_msg}\n")
            self.log_to_notebook(text, {}, error=error_msg)

    async def run(self, subjects: list[str], stop_after_one: bool = False) -> None:
        """Run the voice follow cast agent.

        Args:
            subjects: List of NATS subjects to subscribe to.
            stop_after_one: Whether to stop after first message.
        """
        self.nc = NATS()
        await self.nc.connect(self.nats_url)
        sys.stderr.write(f"✔ voice-follow-cast connected to {self.nats_url}\n")
        sys.stderr.write(f"  ↳ subjects: {', '.join(subjects)}\n")
        sys.stderr.write(f"  ↳ cast_gateway: {self.cast_gateway_url}\n")
        if self.default_device:
            sys.stderr.write(f"  ↳ device: {self.default_device}\n")
        if self.notebook_client:
            sys.stderr.write(f"  ↳ notebook_logging: enabled\n")

        self.running = True
        done = asyncio.Event()

        async def handler(msg):
            if not self.running:
                return
            await self.handle_response(msg)
            if stop_after_one:
                done.set()

        for subj in subjects:
            await self.nc.subscribe(subj, cb=handler)

        if stop_after_one:
            await done.wait()
            await self.nc.drain()
            return

        # Daemon mode: run forever
        while self.running:
            await asyncio.sleep(1)

        await self.nc.drain()

    async def stop(self) -> None:
        """Stop the agent."""
        self.running = False


async def main_async(
    subjects: list[str],
    stop_after_one: bool,
) -> None:
    """Main async entry point."""
    nats_url = _resolve_nats_url()
    cast_gateway_url = _env("CAST_TTS_GATEWAY_URL", "http://localhost:8060")
    default_device = os.getenv("CAST_DEFAULT_DEVICE")
    voice = _env("CAST_FOLLOW_VOICE", "default")

    # Optional Open-Notebook logging
    notebook_client = None
    if _env("CAST_NOTEBOOK_ENABLED", "false").lower() == "true":
        notebook_url = os.getenv("OPEN_NOTEBOOK_API_URL")
        notebook_token = os.getenv("OPEN_NOTEBOOK_API_TOKEN")
        if notebook_url and notebook_token:
            notebook_client = NotebookClient(notebook_url, notebook_token)
        else:
            sys.stderr.write(
                "[voice-follow-cast] Notebook logging enabled but OPEN_NOTEBOOK_API_URL "
                "or OPEN_NOTEBOOK_API_TOKEN not set\n"
            )

    agent = VoiceFollowCastAgent(
        nats_url=nats_url,
        cast_gateway_url=cast_gateway_url,
        default_device=default_device,
        voice=voice,
        notebook_client=notebook_client,
    )

    await agent.run(subjects, stop_after_one=stop_after_one)


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="voice_follow_cast_agent",
        description="Subscribe to agent responses and auto-cast to Google Cast devices"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit after first cast"
    )
    parser.add_argument(
        "--subjects",
        type=str,
        default=None,
        help="Comma-separated NATS subjects (default: voice.agent.response.v1,agent.response.v1)"
    )
    args = parser.parse_args(argv)

    if args.subjects:
        subjects = [s.strip() for s in args.subjects.split(",") if s.strip()]
    else:
        subjects = ["voice.agent.response.v1", "agent.response.v1"]

    try:
        asyncio.run(main_async(subjects, stop_after_one=bool(args.once)))
        return 0
    except KeyboardInterrupt:
        sys.stderr.write("\n[voice-follow-cast] Shutting down...\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
