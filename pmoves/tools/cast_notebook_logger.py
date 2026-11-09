#!/usr/bin/env python3
"""
Cast Notebook Logger

Standalone utility for logging Google Cast events to Open-Notebook.

This module provides tools for logging Cast TTS events to Open-Notebook
for conversation history and audit trails.

Usage:
  from pmoves.tools.cast_notebook_logger import CastNotebookLogger

  logger = CastNotebookLogger(
      api_base="http://localhost:5055",
      token="your-token"
  )

  logger.log_cast_event(
      event_type="voice_cast_completed",
      device="Brysons Speakers speaker",
      text="Hello world",
      voice="default",
      duration_ms=2500
  )

Environment:
  - OPEN_NOTEBOOK_API_URL (default: http://localhost:5055)
  - OPEN_NOTEBOOK_API_TOKEN (required)
  - CAST_NOTEBOOK_DEFAULT (default: cast-logs)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import httpx


def _env(name: str, default: str) -> str:
    """Get environment variable with default."""
    v = os.getenv(name)
    return v.strip() if v else default


class CastNotebookLogger:
    """Logger for Cast TTS events to Open-Notebook."""

    def __init__(
        self,
        api_base: str,
        token: str,
        default_notebook: str = "cast-logs",
    ):
        """Initialize Cast Notebook Logger.

        Args:
            api_base: Open-Notebook API base URL.
            token: Bearer token for authentication.
            default_notebook: Default notebook name for Cast logs.
        """
        self.api_base = api_base.rstrip("/") + "/api"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.default_notebook = default_notebook

    def log_cast_event(
        self,
        event_type: str,
        device: str,
        text: str,
        voice: str,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        notebook: Optional[str] = None,
    ) -> Optional[str]:
        """Log a Cast event to Open-Notebook.

        Args:
            event_type: Event type (voice_cast_completed, voice_cast_failed, etc.)
            device: Cast device name.
            text: Text that was synthesized.
            voice: Voice name used.
            duration_ms: Audio duration in milliseconds (optional).
            error: Error message if event failed.
            metadata: Additional metadata dictionary.
            notebook: Notebook name (uses default if not specified).

        Returns:
            Source ID if successful, None otherwise.
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        notebook_name = notebook or self.default_notebook

        # Create human-readable title
        if error:
            title = f"Cast Failed: {event_type} @ {device} - {timestamp}"
        else:
            title = f"Cast Success: {event_type} @ {device} - {timestamp}"

        # Format content
        content = self._format_event(
            event_type=event_type,
            device=device,
            text=text,
            voice=voice,
            duration_ms=duration_ms,
            error=error,
            metadata=metadata,
            timestamp=timestamp,
        )

        payload = {
            "type": "text",
            "title": title,
            "content": content,
            "notebooks": [notebook_name],
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
            source_id = data.get("id")
            sys.stderr.write(f"[cast-notebook] Logged to {notebook_name}: {source_id}\n")
            return source_id
        except httpx.HTTPStatusError as e:
            sys.stderr.write(f"[cast-notebook] HTTP error: {e.response.status_code}\n")
            sys.stderr.write(f"[cast-notebook] Response: {e.response.text}\n")
            return None
        except Exception as e:
            sys.stderr.write(f"[cast-notebook] Log failed: {e}\n")
            return None

    def _format_event(
        self,
        event_type: str,
        device: str,
        text: str,
        voice: str,
        duration_ms: Optional[int],
        error: Optional[str],
        metadata: Optional[Dict[str, Any]],
        timestamp: str,
    ) -> str:
        """Format event as human-readable text.

        Args:
            event_type: Event type.
            device: Cast device name.
            text: Text that was synthesized.
            voice: Voice name.
            duration_ms: Audio duration.
            error: Error message.
            metadata: Additional metadata.
            timestamp: Event timestamp.

        Returns:
            Formatted event content.
        """
        lines = [
            f"# Cast Event: {event_type}",
            "",
            f"**Timestamp:** {timestamp}",
            f"**Device:** {device}",
            f"**Voice:** {voice}",
            "",
        ]

        if duration_ms:
            duration_sec = duration_ms / 1000
            lines.append(f"**Duration:** {duration_sec:.2f}s")
            lines.append("")

        if error:
            lines.append("## Error")
            lines.append("```")
            lines.append(error)
            lines.append("```")
            lines.append("")

        lines.append("## Text")
        lines.append("```")
        lines.append(text)
        lines.append("```")
        lines.append("")

        if metadata:
            lines.append("## Metadata")
            lines.append("```json")
            lines.append(json.dumps(metadata, indent=2))
            lines.append("```")

        return "\n".join(lines)

    def log_cast_completed(
        self,
        device: str,
        text: str,
        voice: str,
        duration_ms: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Log successful Cast completion.

        Args:
            device: Cast device name.
            text: Text that was synthesized.
            voice: Voice name.
            duration_ms: Audio duration in milliseconds.
            metadata: Additional metadata.

        Returns:
            Source ID if successful.
        """
        return self.log_cast_event(
            event_type="voice_cast_completed",
            device=device,
            text=text,
            voice=voice,
            duration_ms=duration_ms,
            metadata=metadata,
        )

    def log_cast_failed(
        self,
        device: str,
        text: str,
        voice: str,
        error: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Log Cast failure.

        Args:
            device: Cast device name.
            text: Text that failed to synthesize.
            voice: Voice name.
            error: Error message.
            metadata: Additional metadata.

        Returns:
            Source ID if successful.
        """
        return self.log_cast_event(
            event_type="voice_cast_failed",
            device=device,
            text=text,
            voice=voice,
            error=error,
            metadata=metadata,
        )


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for manual logging.

    Examples:
      # Log successful cast
      python cast_notebook_logger.py \\
        --event voice_cast_completed \\
        --device "Brysons Speakers speaker" \\
        --text "Hello world" \\
        --voice default \\
        --duration 2500

      # Log failed cast
      python cast_notebook_logger.py \\
        --event voice_cast_failed \\
        --device "Brysons Speakers speaker" \\
        --text "Hello world" \\
        --voice default \\
        --error "Device offline"
    """
    parser = argparse.ArgumentParser(
        prog="cast_notebook_logger",
        description="Log Google Cast events to Open-Notebook"
    )
    parser.add_argument(
        "--event",
        type=str,
        required=True,
        choices=["voice_cast_completed", "voice_cast_failed"],
        help="Event type"
    )
    parser.add_argument(
        "--device",
        type=str,
        required=True,
        help="Cast device name"
    )
    parser.add_argument(
        "--text",
        type=str,
        required=True,
        help="Text that was synthesized"
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="default",
        help="Voice name"
    )
    parser.add_argument(
        "--duration",
        type=int,
        help="Duration in milliseconds (for completed events)"
    )
    parser.add_argument(
        "--error",
        type=str,
        help="Error message (for failed events)"
    )
    parser.add_argument(
        "--metadata",
        type=str,
        help="JSON metadata string"
    )
    parser.add_argument(
        "--notebook",
        type=str,
        default=None,
        help="Notebook name (default: cast-logs)"
    )
    args = parser.parse_args(argv)

    # Get configuration from environment
    api_url = _env("OPEN_NOTEBOOK_API_URL", "http://localhost:5055")
    api_token = os.getenv("OPEN_NOTEBOOK_API_TOKEN")

    if not api_token:
        sys.stderr.write("ERROR: OPEN_NOTEBOOK_API_TOKEN environment variable required\n")
        return 1

    logger = CastNotebookLogger(
        api_base=api_url,
        token=api_token,
    )

    # Parse metadata if provided
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            sys.stderr.write(f"ERROR: Invalid JSON metadata: {args.metadata}\n")
            return 1

    # Log event
    source_id = logger.log_cast_event(
        event_type=args.event,
        device=args.device,
        text=args.text,
        voice=args.voice,
        duration_ms=args.duration,
        error=args.error,
        metadata=metadata,
        notebook=args.notebook,
    )

    if source_id:
        sys.stderr.write(f"✓ Logged to Open-Notebook: {source_id}\n")
        return 0
    else:
        sys.stderr.write("✗ Failed to log event\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
