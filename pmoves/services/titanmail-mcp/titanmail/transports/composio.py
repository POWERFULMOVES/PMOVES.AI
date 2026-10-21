"""Composio transport -- Gmail / Outlook through Composio's tool-execution API.

Call path: ``POST {base}/tools/execute/{tool_slug}`` with header ``x-api-key`` and
body ``{"user_id", "connected_account_id"?, "version"?, "arguments": {...}}``; the
response is ``{"data": {...}, "error": str|null, "successful": bool, "log_id": str}``.
Source: https://docs.composio.dev/reference/api-reference/tools/postToolsExecuteByToolSlug
(REST v3.1, base https://backend.composio.dev/api/v3.1), read 2026-10-21.

The REST endpoint is used instead of the `composio` Python SDK on purpose: the SDK
(0.28.0 on PyPI, 2026-10-21) pulls in `openai`, `pysher` and a generated client for
what is one authenticated POST, and its docs label direct `tools.execute` as legacy
in favour of sessions. The REST endpoint is the same execution path and keeps this
cassette small. Composio's own docs recommend sessions for *agent* integrations;
TitanMail is not an agent, it is a fixed-tool server, which is the case direct
execution remains supported for.

Tool slugs (all overridable by env, so a slug rename is config, not code):
  Gmail   GMAIL_FETCH_EMAILS, GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID
  Outlook OUTLOOK_LIST_MESSAGES, OUTLOOK_GET_MESSAGE
Verified to EXIST, with the input parameters used below, on the toolkit pages
https://docs.composio.dev/toolkits/gmail.md and .../outlook.md (2026-10-21).
NOT verified: the shape of each tool's `data` payload (the docs type it only as
"data: Data from the action execution") -- the parsers below are tolerant and the
field names they read are flagged UNVERIFIED until a live call is captured.

Exact-datetime injection. Composio documents that GMAIL_FETCH_EMAILS `after:`/
`before:` "evaluate whole calendar days in UTC; before: is exclusive" (Google's own
docs say PST unless epoch seconds are used). Either way they are day-granular, so
this transport pads the window by a day on each side and the service trims to the
exact half-open window on Gmail's `internalDate`. Outlook gets an exact OData
filter on `receivedDateTime` (ISO-8601 Z), and is trimmed by the service as well.

Auth: COMPOSIO_API_KEY from the environment only. The key is never logged, never
echoed in errors, and never part of describe().
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any, Optional

import httpx

from ..models import EmailMessage, matches_query
from ..timewindow import UTC, TimeWindow, iso_z
from .base import TransportError

DEFAULT_BASE = "https://backend.composio.dev/api/v3.1"

SLUG_DEFAULTS = {
    "gmail": {"search": "GMAIL_FETCH_EMAILS", "get": "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID"},
    "outlook": {"search": "OUTLOOK_LIST_MESSAGES", "get": "OUTLOOK_GET_MESSAGE"},
}

OUTLOOK_SELECT = ["id", "subject", "from", "toRecipients", "ccRecipients", "receivedDateTime",
                  "sentDateTime", "bodyPreview", "conversationId", "internetMessageId"]


def _hdr(headers: Any, name: str) -> str:
    if isinstance(headers, list):
        for h in headers:
            if isinstance(h, dict) and str(h.get("name", "")).lower() == name.lower():
                return str(h.get("value", ""))
    if isinstance(headers, dict):
        for k, v in headers.items():
            if k.lower() == name.lower():
                return str(v[0] if isinstance(v, list) and v else v)
    return ""


def _ts(value: Any) -> Optional[datetime]:
    """epoch ms (str/int), ISO-8601, or RFC 5322 -> aware datetime."""
    if value in (None, ""):
        return None
    s = str(value).strip()
    if s.isdigit():
        n = int(s)
        return datetime.fromtimestamp(n / 1000 if n > 10**11 else n, UTC)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (TypeError, ValueError, IndexError):
        return None


def _addr_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        out = []
        for r in raw:
            if isinstance(r, dict):  # Graph recipient {"emailAddress": {"address": ...}}
                a = (r.get("emailAddress") or {}).get("address") or r.get("address") or ""
                if a:
                    out.append(a)
            elif r:
                out.extend(a for _, a in getaddresses([str(r)]) if a)
        return out
    if isinstance(raw, str) and raw:
        return [a for _, a in getaddresses([raw]) if a]
    return []


class ComposioTransport:
    def __init__(self, provider: str, *, api_key: Optional[str] = None, user_id: str = "",
                 connected_account_id: str = "", base_url: str = DEFAULT_BASE,
                 toolkit_version: str = "", slugs: Optional[dict] = None, page_size: int = 100,
                 max_pages: int = 50, timeout: float = 30.0,
                 client: Optional[httpx.AsyncClient] = None):
        provider = provider.lower().strip()
        if provider not in SLUG_DEFAULTS:
            raise ValueError(f"provider must be gmail or outlook, not {provider!r}")
        self.provider = provider
        self.name = f"composio:{provider}"
        self._api_key = api_key if api_key is not None else os.getenv("COMPOSIO_API_KEY", "")
        self.user_id = user_id
        self.connected_account_id = connected_account_id
        self.base_url = base_url.rstrip("/")
        self.toolkit_version = toolkit_version
        self.slugs = {**SLUG_DEFAULTS[provider], **(slugs or {})}
        self.page_size = page_size
        self.max_pages = max_pages
        self._timeout = timeout
        self._client = client

    def __repr__(self) -> str:  # never include the key
        return f"ComposioTransport(provider={self.provider!r}, base_url={self.base_url!r})"

    def describe(self) -> dict:
        return {"transport": self.name, "base_url": self.base_url, "slugs": self.slugs,
                "api_key_configured": bool(self._api_key),
                "date_authority": "internalDate" if self.provider == "gmail" else "receivedDateTime"}

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def execute(self, slug: str, arguments: dict) -> Any:
        if not self._api_key:
            raise TransportError("COMPOSIO_API_KEY is not set")
        body: dict[str, Any] = {"arguments": arguments}
        if self.user_id:
            body["user_id"] = self.user_id
        if self.connected_account_id:
            body["connected_account_id"] = self.connected_account_id
        if self.toolkit_version:
            body["version"] = self.toolkit_version
        try:
            r = await self._http().post(f"{self.base_url}/tools/execute/{slug}", json=body,
                                        headers={"x-api-key": self._api_key})
        except httpx.HTTPError as exc:
            raise TransportError(f"composio {slug}: {type(exc).__name__}") from exc
        try:
            payload = r.json()
        except ValueError:
            payload = {}
        if r.status_code != 200:
            err = payload.get("error") if isinstance(payload, dict) else None
            msg = err.get("message") if isinstance(err, dict) else str(err or "")[:200]
            raise TransportError(f"composio {slug} -> HTTP {r.status_code}: {msg}")
        if not payload.get("successful", False):
            raise TransportError(f"composio {slug} unsuccessful: {str(payload.get('error'))[:200]}")
        data = payload.get("data")
        if isinstance(data, str):  # some tools return JSON-in-a-string
            try:
                data = json.loads(data)
            except ValueError:
                pass
        return data

    # -- Gmail ------------------------------------------------------------
    def _gmail_query(self, window: TimeWindow, query: str) -> str:
        lo = (window.after_utc - timedelta(days=1)).strftime("%Y/%m/%d")
        hi = (window.before_utc + timedelta(days=2)).strftime("%Y/%m/%d")
        return " ".join(p for p in ((query or "").strip(), f"after:{lo}", f"before:{hi}") if p)

    def _gmail_msg(self, m: dict) -> Optional[EmailMessage]:
        payload = m.get("payload") or {}
        headers = payload.get("headers") if isinstance(payload, dict) else None
        # UNVERIFIED field names: internalDate / messageTimestamp / messageId / threadId /
        # sender / to / subject / preview / messageText.
        date = _ts(m.get("internalDate")) or _ts(m.get("messageTimestamp")) or _ts(_hdr(headers, "Date"))
        if date is None:
            return None
        source = ("gmail:internalDate" if m.get("internalDate") else
                  "gmail:messageTimestamp" if m.get("messageTimestamp") else "header:Date")
        preview = m.get("preview")
        snippet = preview.get("body", "") if isinstance(preview, dict) else (m.get("snippet") or "")
        return EmailMessage(
            id=str(m.get("messageId") or m.get("id") or ""), date=date, date_source=source,
            subject=m.get("subject") or _hdr(headers, "Subject"),
            from_addr=next(iter(_addr_list(m.get("sender") or _hdr(headers, "From"))), ""),
            to=_addr_list(m.get("to") or _hdr(headers, "To")),
            cc=_addr_list(_hdr(headers, "Cc")),
            message_id=_hdr(headers, "Message-ID") or _hdr(headers, "Message-Id"),
            in_reply_to=_hdr(headers, "In-Reply-To"), references=_hdr(headers, "References"),
            thread_id=str(m.get("threadId") or ""), snippet=snippet or "",
            body_text=m.get("messageText") or "",
        )

    # -- Outlook ----------------------------------------------------------
    def _outlook_msg(self, m: dict) -> Optional[EmailMessage]:
        date = _ts(m.get("receivedDateTime"))
        if date is None:
            return None
        frm = (m.get("from") or {}).get("emailAddress") or {}
        body = m.get("body") or {}
        return EmailMessage(
            id=str(m.get("id") or ""), date=date, date_source="graph:receivedDateTime",
            subject=m.get("subject") or "", from_addr=frm.get("address", ""),
            to=_addr_list(m.get("toRecipients")), cc=_addr_list(m.get("ccRecipients")),
            message_id=m.get("internetMessageId") or "", thread_id=m.get("conversationId") or "",
            snippet=m.get("bodyPreview") or "",
            body_text=body.get("content", "") if isinstance(body, dict) else "",
        )

    @staticmethod
    def _items(data: Any) -> tuple[list, str]:
        if not isinstance(data, dict):
            return [], ""
        items = data.get("messages") or data.get("value") or []
        token = data.get("nextPageToken") or data.get("next_page_token") or ""
        return (items if isinstance(items, list) else []), token

    async def search(self, window: TimeWindow, query: str, max_results: int) -> list[EmailMessage]:
        out: list[EmailMessage] = []
        token = ""
        for _ in range(self.max_pages):
            if self.provider == "gmail":
                args: dict[str, Any] = {"query": self._gmail_query(window, query), "user_id": "me",
                                        "max_results": min(self.page_size, 500),
                                        "include_payload": True, "verbose": False}
            else:
                # Exact server-side window; Graph forbids $search with $filter, so free text is
                # matched client-side on the returned fields.
                args = {"folder": "allfolders", "top": min(self.page_size, 1000),
                        "filter": (f"receivedDateTime ge {iso_z(window.after_utc)} and "
                                   f"receivedDateTime lt {iso_z(window.before_utc)}"),
                        "orderby": ["receivedDateTime desc"], "select": OUTLOOK_SELECT,
                        "user_id": "me"}
            if token:
                args["page_token"] = token
            data = await self.execute(self.slugs["search"], args)
            items, token = self._items(data)
            parse = self._gmail_msg if self.provider == "gmail" else self._outlook_msg
            for it in items:
                msg = parse(it) if isinstance(it, dict) else None
                if msg is None:
                    continue
                if self.provider == "outlook" and not matches_query(msg, query):
                    continue
                if window.contains(msg.date):
                    out.append(msg)
            if not token or len(out) >= max_results:
                break
        else:
            raise TransportError(f"composio page cap ({self.max_pages}) reached; narrow the window")
        out.sort(key=lambda m: (m.date_utc, m.id), reverse=True)
        return out[:max_results]

    async def get(self, message_id: str) -> Optional[EmailMessage]:
        if self.provider == "gmail":
            data = await self.execute(self.slugs["get"], {"message_id": message_id, "format": "full",
                                                          "user_id": "me"})
            msg = self._gmail_msg(data) if isinstance(data, dict) else None
            if msg is not None and not msg.body_text:
                msg.body_text = _gmail_plain_body((data or {}).get("payload") or {})
            return msg
        data = await self.execute(self.slugs["get"], {"message_id": message_id, "user_id": "me"})
        return self._outlook_msg(data) if isinstance(data, dict) else None


def _gmail_plain_body(payload: dict) -> str:
    """Decode the first text/plain part (base64url) of a Gmail API payload."""
    stack = [payload]
    while stack:
        part = stack.pop(0)
        if not isinstance(part, dict):
            continue
        if part.get("mimeType") == "text/plain":
            data = (part.get("body") or {}).get("data") or ""
            if data:
                try:
                    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
                except (ValueError, TypeError):
                    return ""
        stack.extend(part.get("parts") or [])
    return ""
