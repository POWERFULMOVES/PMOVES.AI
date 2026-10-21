"""TitanMailService -- the transport-neutral core every MCP tool calls.

Each method returns a plain dict carrying an ``envelope``: the server's exact
current instant and timezone, plus the resolved absolute window (or null for
tools that take none). The model never supplies "today"; it reads it here.
"""
from __future__ import annotations

from typing import Optional
from zoneinfo import ZoneInfo

from .dedup import TieBreaker, dedup
from .models import EmailMessage
from .threads import group_threads
from .timewindow import (DEFAULT_MAX_WINDOW_DAYS, Clock, SystemClock, TimeWindow, WindowError,
                         iso_z, reject_date_operators, resolve_window)
from .transports.base import MailTransport, TransportError

MAX_LIMIT = 500
DEFAULT_MAX_CANDIDATES = 5000


class TitanMailService:
    def __init__(self, transport: MailTransport, *, clock: Optional[Clock] = None,
                 tz: ZoneInfo | None = None, max_window_days: int = DEFAULT_MAX_WINDOW_DAYS,
                 max_candidates: int = DEFAULT_MAX_CANDIDATES,
                 tie_breaker: TieBreaker | None = None, dedup_window_seconds: int = 120):
        self.transport = transport
        self.clock = clock or SystemClock()
        self.tz = tz or ZoneInfo("UTC")
        self.max_window_days = max_window_days
        self.max_candidates = max_candidates
        self.tie_breaker = tie_breaker
        self.dedup_window_seconds = dedup_window_seconds

    # -- envelope --------------------------------------------------------------
    def now(self) -> dict:
        n = self.clock.now()
        local = n.astimezone(self.tz)
        return {
            "server_time_utc": iso_z(n),
            "server_time_local": local.isoformat(),
            "server_tz": getattr(self.tz, "key", str(self.tz)),
            "utc_offset": local.strftime("%z"),
            "epoch_ms": int(n.timestamp() * 1000),
            "iso_weekday": local.isoweekday(),
            "transport": self.transport.describe(),
        }

    def _envelope(self, window: Optional[TimeWindow]) -> dict:
        n = self.clock.now()
        return {"server_time_utc": iso_z(n),
                "server_time_local": n.astimezone(self.tz).isoformat(),
                "server_tz": getattr(self.tz, "key", str(self.tz)),
                "window": window.to_dict() if window else None,
                "transport": self.transport.name}

    def _error(self, exc: Exception, window: Optional[TimeWindow] = None) -> dict:
        return {"ok": False, "error": str(exc), "error_type": type(exc).__name__,
                "envelope": self._envelope(window)}

    def _window(self, after_iso: str, before_iso: str, relative: str) -> TimeWindow:
        return resolve_window(after_iso, before_iso, relative, clock=self.clock, tz=self.tz,
                              max_days=self.max_window_days)

    async def _fetch(self, window: TimeWindow, query: str) -> list[EmailMessage]:
        msgs = await self.transport.search(window, query, self.max_candidates)
        # Defense in depth: whatever the transport returned, only the exact half-open
        # window survives. Over-fetching transports (day-padded providers) rely on this.
        exact = [m for m in msgs if window.contains(m.date)]
        exact.sort(key=lambda m: (m.date_utc, m.id), reverse=True)
        return exact

    # -- tools -----------------------------------------------------------------
    async def search_messages(self, query: str = "", after_iso: str = "", before_iso: str = "",
                              limit: int = 50, relative: str = "") -> dict:
        window = None
        try:
            bad = reject_date_operators(query)
            if bad:
                raise WindowError(bad)
            window = self._window(after_iso, before_iso, relative)
            limit = max(1, min(int(limit), MAX_LIMIT))
            msgs = await self._fetch(window, query or "")
        except (WindowError, TransportError, ValueError, TypeError) as exc:
            return self._error(exc, window)
        return {"ok": True, "envelope": self._envelope(window), "query": query or "",
                "total_in_window": len(msgs), "returned": min(limit, len(msgs)),
                "truncated": len(msgs) > limit,
                "messages": [m.summary() for m in msgs[:limit]]}

    async def get_message(self, id: str) -> dict:  # noqa: A002 - tool arg name
        try:
            if not (id or "").strip():
                raise ValueError("id is required")
            msg = await self.transport.get(id.strip())
        except (TransportError, ValueError) as exc:
            return self._error(exc)
        if msg is None:
            return {"ok": False, "error": f"message {id!r} not found",
                    "envelope": self._envelope(None)}
        return {"ok": True, "envelope": self._envelope(None), "message": msg.full()}

    async def list_threads(self, after_iso: str = "", before_iso: str = "",
                           relative: str = "") -> dict:
        window = None
        try:
            window = self._window(after_iso, before_iso, relative)
            msgs = await self._fetch(window, "")
        except (WindowError, TransportError, ValueError) as exc:
            return self._error(exc, window)
        threads = group_threads(msgs)
        return {"ok": True, "envelope": self._envelope(window), "messages_in_window": len(msgs),
                "thread_count": len(threads), "threads": threads,
                "note": "threads are scoped to messages inside the window"}

    async def dedup_report(self, after_iso: str = "", before_iso: str = "",
                           relative: str = "") -> dict:
        window = None
        try:
            window = self._window(after_iso, before_iso, relative)
            msgs = await self._fetch(window, "")
        except (WindowError, TransportError, ValueError) as exc:
            return self._error(exc, window)
        res = dedup(msgs, window_seconds=self.dedup_window_seconds, tie_breaker=self.tie_breaker)
        return {"ok": True, "envelope": self._envelope(window), **res.to_dict(),
                "rules": "deterministic: Message-ID (sender+subject must agree), then "
                         f"from+to+subject+body-hash within {self.dedup_window_seconds}s for "
                         "messages without a Message-ID; AI tie-breaker seam not enabled (v1)"}
