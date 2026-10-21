"""Transport-neutral message model and the normalizers the dedup keys depend on."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import getaddresses, parseaddr
from typing import Iterable, Optional

from .timewindow import UTC, iso_z


def normalize_address(raw: str) -> str:
    """Lower-cased bare address. Conservative on purpose (precision > recall):
    no plus-tag stripping, no Gmail dot folding -- those can merge distinct mailboxes."""
    if not raw:
        return ""
    _, addr = parseaddr(raw)
    addr = (addr or raw).strip().strip("<>").strip()
    return addr.lower()


def normalize_addresses(raws: Iterable[str]) -> list[str]:
    out = []
    for name, addr in getaddresses(list(raws)):
        a = (addr or name).strip().strip("<>").lower()
        if a:
            out.append(a)
    return sorted(set(out))


def normalize_message_id(raw: Optional[str]) -> str:
    """Strip whitespace and angle brackets; lower-case the domain only.
    RFC 5322 left-hand sides are case-sensitive, so they are kept as-is."""
    if not raw:
        return ""
    mid = raw.strip()
    if mid.startswith("<") and mid.endswith(">"):
        mid = mid[1:-1]
    mid = mid.strip()
    if "@" in mid:
        left, _, right = mid.rpartition("@")
        mid = f"{left}@{right.lower()}"
    return mid


def normalize_subject(raw: str) -> str:
    """Whitespace-collapsed, case-folded. Reply/forward prefixes are KEPT:
    'Re: X' and 'X' are different messages."""
    return re.sub(r"\s+", " ", raw or "").strip().casefold()


def body_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", text or "").strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def references_list(raw: Optional[str]) -> list[str]:
    return [normalize_message_id(m) for m in re.findall(r"<[^>]+>", raw or "")]


@dataclass
class EmailMessage:
    id: str                         # transport-native id (mailpit ID, Gmail id, Graph id)
    date: datetime                  # authoritative instant, aware
    subject: str = ""
    from_addr: str = ""
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    message_id: str = ""            # RFC 5322 Message-ID header (raw)
    in_reply_to: str = ""
    references: str = ""
    thread_id: str = ""             # provider thread/conversation id, if any
    snippet: str = ""
    body_text: str = ""
    date_source: str = ""           # which field `date` came from (e.g. "header:Date")
    extra: dict = field(default_factory=dict)  # selected passthrough headers

    def __post_init__(self) -> None:
        if self.date.tzinfo is None:
            raise ValueError(f"message {self.id}: date must be timezone-aware")

    @property
    def date_utc(self) -> datetime:
        return self.date.astimezone(UTC)

    def searchable_text(self) -> str:
        return " ".join([self.subject, self.from_addr, " ".join(self.to), " ".join(self.cc),
                         self.snippet, self.body_text]).casefold()

    def summary(self) -> dict:
        out = {
            "id": self.id,
            "date": self.date.isoformat(),
            "date_utc": iso_z(self.date),
            "date_source": self.date_source,
            "from": self.from_addr,
            "to": self.to,
            "subject": self.subject,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "snippet": (self.snippet or self.body_text)[:250],
        }
        if self.extra:
            out["headers"] = dict(self.extra)
        return out

    def full(self) -> dict:
        out = self.summary()
        out.update(cc=self.cc, in_reply_to=self.in_reply_to, references=self.references,
                   body_text=self.body_text)
        return out


def matches_query(msg: EmailMessage, query: str) -> bool:
    """All whitespace-separated terms must appear (case-insensitive); "quoted phrases" stay whole."""
    terms = [t.strip('"').casefold() for t in re.findall(r'"[^"]+"|\S+', query or "")]
    if not terms:
        return True
    hay = msg.searchable_text()
    return all(t in hay for t in terms)
