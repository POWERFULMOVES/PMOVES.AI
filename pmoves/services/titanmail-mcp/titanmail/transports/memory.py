"""In-memory transport: the CI/offline backend for tests and the eval harness."""
from __future__ import annotations

from typing import Iterable, Optional

from ..models import EmailMessage, matches_query
from ..timewindow import TimeWindow


class InMemoryTransport:
    name = "memory"

    def __init__(self, messages: Iterable[EmailMessage] = ()):
        self._by_id: dict[str, EmailMessage] = {}
        for m in messages:
            self.add(m)

    def add(self, msg: EmailMessage) -> None:
        if msg.id in self._by_id:
            raise ValueError(f"duplicate transport id {msg.id}")
        self._by_id[msg.id] = msg

    async def search(self, window: TimeWindow, query: str, max_results: int) -> list[EmailMessage]:
        hits = [m for m in self._by_id.values()
                if window.contains(m.date) and matches_query(m, query)]
        hits.sort(key=lambda m: (m.date_utc, m.id), reverse=True)
        return hits[:max_results]

    async def get(self, message_id: str) -> Optional[EmailMessage]:
        return self._by_id.get(message_id)

    def describe(self) -> dict:
        return {"transport": self.name, "messages": len(self._by_id)}
