"""Mailpit transport -- the local development/test mail source (PMOVES-Mike's `mailpit`).

Endpoints used (verified against axllent/mailpit's swagger.json, API v1, and the
docs at https://mailpit.axllent.org/docs/api-v1/ on 2026-10-21):

  GET /api/v1/messages?start=&limit=            list, newest first (by received time)
  GET /api/v1/search?query=&start=&limit=&tz=   search (mailpit search-filter syntax)
  GET /api/v1/message/{ID}/headers              all headers, {name: [values]}
  GET /view/{ID}.txt                            text body

`GET /api/v1/message/{ID}` is deliberately NOT used: it marks the message as read,
and a read-only retrieval tool must not mutate the mailbox.

Which timestamp is authoritative. Mailpit's list/search summaries only carry
`Created` -- the time mailpit RECEIVED the message over SMTP. Unless mailpit runs
with MP_USE_MESSAGE_DATES=true (Mike's compose does not set it), every seeded
message has Created == "the moment it was seeded", which says nothing about when
the mail was written. This transport therefore takes the RFC 5322 `Date` header
from the headers endpoint as authoritative (date_source "header:Date") and only
falls back to `Created` when a message has no Date header.

Mailpit's own `before:`/`after:` filters work on Created and are day-granular, so
they are used only as a padded PREFILTER and only when ``use_message_dates`` says
Created == Date. The exact half-open window is always applied by the service.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
from typing import Optional

import httpx

from ..models import EmailMessage
from ..timewindow import UTC, TimeWindow
from .base import TransportError

PASSTHROUGH_HEADERS = ("X-Titanmail-Fixture-Id",)


def _first(headers: dict, name: str) -> str:
    for k, v in headers.items():
        if k.lower() == name.lower():
            if isinstance(v, list):
                return str(v[0]) if v else ""
            return str(v)
    return ""


def _decode(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001 - malformed encoded-words: keep the raw text
        return value


def _parse_created(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _parse_header_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None or dt.tzinfo is None:
        # RFC 5322 "-0000" means "no zone information"; treat as UTC but say so.
        return dt.replace(tzinfo=UTC) if dt else None
    return dt


class MailpitTransport:
    name = "mailpit"

    def __init__(self, base_url: str, *, scope_query: str = "", use_message_dates: bool = False,
                 ignore_synthetic_message_ids: bool = True,
                 page_size: int = 200, max_scan: int = 5000, concurrency: int = 16,
                 timeout: float = 15.0, client: Optional[httpx.AsyncClient] = None):
        self.base_url = base_url.rstrip("/")
        self.scope_query = scope_query.strip()
        self.use_message_dates = use_message_dates
        self.ignore_synthetic_message_ids = ignore_synthetic_message_ids
        self.page_size = max(1, min(int(page_size), 1000))
        self.max_scan = max_scan
        self._sem = asyncio.Semaphore(concurrency)
        self._client = client
        self._timeout = timeout
        self._hdr_cache: dict[str, dict] = {}

    def _real_mid(self, mid: str) -> str:
        """Mailpit INSERTS a `Message-Id: <random>@mailpit` header into any message that
        arrives without one (measured against mailpit v1.31.6, 2026-10-21). Two copies of
        the same header-less mail therefore get two different synthetic ids, which would
        defeat the fallback dedup key. Treat them as "no Message-ID"."""
        if self.ignore_synthetic_message_ids and mid.strip().strip("<>").lower().endswith("@mailpit"):
            return ""
        return mid

    def describe(self) -> dict:
        return {"transport": self.name, "url": self.base_url, "scope_query": self.scope_query,
                "use_message_dates": self.use_message_dates,
                "date_authority": "Created" if self.use_message_dates else "header:Date"}

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _get_json(self, path: str, params: Optional[dict] = None):
        try:
            r = await self._http().get(f"{self.base_url}{path}", params=params)
        except httpx.HTTPError as exc:
            raise TransportError(f"mailpit unreachable at {self.base_url}: {type(exc).__name__}") from exc
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise TransportError(f"mailpit {path} -> HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    async def _headers(self, mid: str) -> dict:
        if mid not in self._hdr_cache:
            async with self._sem:
                h = await self._get_json(f"/api/v1/message/{mid}/headers")
            self._hdr_cache[mid] = h or {}
        return self._hdr_cache[mid]

    def _prefilter(self, window: TimeWindow) -> str:
        if not self.use_message_dates:
            return ""
        # Day-granular and of unverified inclusivity -> pad one day each side.
        lo = (window.after_utc - timedelta(days=1)).strftime("%Y/%m/%d")
        hi = (window.before_utc + timedelta(days=2)).strftime("%Y/%m/%d")
        return f"after:{lo} before:{hi}"

    async def _summaries(self, window: TimeWindow, query: str) -> list[dict]:
        q = " ".join(p for p in (self.scope_query, (query or "").strip(), self._prefilter(window)) if p)
        out: list[dict] = []
        start = 0
        while True:
            if q:
                body = await self._get_json("/api/v1/search", {"query": q, "start": start,
                                                             "limit": self.page_size, "tz": "UTC"})
            else:
                body = await self._get_json("/api/v1/messages", {"start": start, "limit": self.page_size})
            page = (body or {}).get("messages") or []
            out.extend(page)
            start += len(page)
            total = int((body or {}).get("messages_count") or 0)
            if not page or start >= total:
                return out
            if len(out) >= self.max_scan:
                raise TransportError(f"mailpit scan cap ({self.max_scan}) reached before the "
                                     "window was exhausted; refusing to return a partial result. "
                                     "Narrow the window/query or raise TITANMAIL_MAILPIT_MAX_SCAN.")
            if self.use_message_dates:
                oldest = _parse_created(page[-1].get("Created", ""))
                if oldest and oldest < window.after_utc - timedelta(days=1):
                    return out

    def _build(self, summ: dict, headers: dict) -> EmailMessage:
        mid = summ.get("ID", "")
        date = None
        source = ""
        if not self.use_message_dates:
            date = _parse_header_date(_first(headers, "Date"))
            source = "header:Date" if date else ""
        if date is None:
            date = _parse_created(summ.get("Created", ""))
            source = "mailpit:Created"
        if date is None:
            raise TransportError(f"mailpit message {mid} has no usable timestamp")
        frm = summ.get("From") or {}
        return EmailMessage(
            id=mid, date=date, date_source=source,
            subject=summ.get("Subject", "") or "",
            from_addr=(frm.get("Address") or "") if isinstance(frm, dict) else "",
            to=[a.get("Address", "") for a in (summ.get("To") or []) if isinstance(a, dict)],
            cc=[a.get("Address", "") for a in (summ.get("Cc") or []) if isinstance(a, dict)],
            message_id=self._real_mid(_first(headers, "Message-Id") or summ.get("MessageID", "")),
            in_reply_to=_first(headers, "In-Reply-To"),
            references=" ".join(headers.get("References", []) if isinstance(headers.get("References"), list)
                                else [_first(headers, "References")]),
            snippet=summ.get("Snippet", "") or "",
            extra={h: _first(headers, h) for h in PASSTHROUGH_HEADERS if _first(headers, h)},
        )

    async def search(self, window: TimeWindow, query: str, max_results: int) -> list[EmailMessage]:
        summaries = await self._summaries(window, query)
        if self.use_message_dates:
            hdrs = [{} for _ in summaries]
        else:
            hdrs = await asyncio.gather(*(self._headers(s.get("ID", "")) for s in summaries))
        msgs = [self._build(s, h) for s, h in zip(summaries, hdrs)]
        # Over-fetch is allowed; the service trims to the exact window. Pre-trim here too so
        # max_results applies to in-window messages, not to whatever mailpit listed first.
        msgs = [m for m in msgs if window.contains(m.date)]
        msgs.sort(key=lambda m: (m.date_utc, m.id), reverse=True)
        return msgs[:max_results]

    async def get(self, message_id: str) -> Optional[EmailMessage]:
        headers = await self._get_json(f"/api/v1/message/{message_id}/headers")
        if headers is None:
            return None
        try:
            r = await self._http().get(f"{self.base_url}/view/{message_id}.txt")
            text = r.text if r.status_code == 200 else ""
        except httpx.HTTPError:
            text = ""
        date = _parse_header_date(_first(headers, "Date"))
        if date is None:
            raise TransportError(f"mailpit message {message_id} has no Date header")
        refs = headers.get("References")
        return EmailMessage(
            id=message_id, date=date, date_source="header:Date",
            subject=_decode(_first(headers, "Subject")),
            from_addr=next((a for _, a in getaddresses([_first(headers, "From")]) if a), ""),
            to=[a for _, a in getaddresses([_decode(v) for v in headers.get("To", [])]) if a],
            cc=[a for _, a in getaddresses([_decode(v) for v in headers.get("Cc", [])]) if a],
            message_id=self._real_mid(_first(headers, "Message-Id")),
            in_reply_to=_first(headers, "In-Reply-To"),
            references=" ".join(refs) if isinstance(refs, list) else (refs or ""),
            body_text=text,
            extra={h: _first(headers, h) for h in PASSTHROUGH_HEADERS if _first(headers, h)},
        )
