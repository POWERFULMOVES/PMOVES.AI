"""The MailTransport protocol.

A transport fetches candidates for an ABSOLUTE window. It may over-fetch (a
provider whose date filter is day-granular should pad the window and let the
service trim), but it must never under-fetch: the service layer re-applies the
exact half-open window to every message a transport returns, so over-fetching
costs bandwidth while under-fetching costs correctness.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..models import EmailMessage
from ..timewindow import TimeWindow


class TransportError(RuntimeError):
    """A provider call failed. Messages must never contain credentials."""


@runtime_checkable
class MailTransport(Protocol):
    name: str

    async def search(self, window: TimeWindow, query: str, max_results: int) -> list[EmailMessage]:
        """Candidates whose authoritative time falls in ``window`` (superset allowed) and whose
        text matches ``query`` (empty = all). ``max_results`` caps provider page-walking."""

    async def get(self, message_id: str) -> Optional[EmailMessage]:
        """One message by transport-native id, or None if absent."""

    def describe(self) -> dict:
        """Non-secret description for health/now() output."""
