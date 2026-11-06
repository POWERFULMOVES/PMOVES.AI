"""Synthetic but realistic fixture inbox with known ground truth.

Deterministic for a given seed. Covers, on purpose:
  * >= 90 days (default 273: 2026-02-15 .. 2026-11-15) across six sender timezones,
    so both northern DST transitions (US 2026-03-08 / 2026-11-01, EU 2026-03-29 /
    2026-10-25) and both southern ones (NZ 2026-04-05 / 2026-09-27) are inside it;
  * messages pinned to exact UTC midnights and +/-1 s around them;
  * the US fall-back fold (two distinct instants both written "01:30" local);
  * the US spring-forward gap edge (01:59:59 EST then 03:00:00 EDT);
  * half-hour (+05:30) and +12/+13 offsets whose local date differs from the UTC date;
  * true duplicates (same Message-ID mirror copies; Message-ID-less resends seconds apart);
  * traps that must NOT merge (Message-ID collisions with a different sender, weekly
    newsletters with identical content, same-content resends far apart, "Re: Invoice"
    from different customers);
  * reply threads linked by In-Reply-To/References.

Every message stores its instant with the SENDER's offset, exactly as a Date header
would. Whole seconds only (RFC 5322 Date has no sub-second field).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.message import EmailMessage as MimeMessage
from email.utils import format_datetime
from zoneinfo import ZoneInfo

from ..models import EmailMessage
from ..timewindow import UTC

FIXTURE_NOW = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)  # a Sunday
FIXTURE_START = datetime(2026, 2, 15, 0, 0, 0, tzinfo=UTC)

ZONES = ["UTC", "America/New_York", "America/Los_Angeles", "Europe/London",
         "Asia/Kolkata", "Pacific/Auckland"]
TOPICS = ["invoice", "roadmap", "standup", "deploy", "payroll", "lease", "newsletter",
          "security", "travel", "kitchen"]
PEOPLE = ["ana", "bo", "chen", "dana", "eli", "fatima", "gus", "hana", "ivan", "jun"]
DOMAINS = ["acme.test", "northwind.test", "contoso.test"]
FILLER = ["kindly", "review", "the", "attached", "notes", "when", "you", "have", "a", "moment",
          "thanks", "regards", "see", "below", "for", "details", "on", "this", "item", "update"]
OWNER = "owner@pmoves.test"


@dataclass
class FixtureMessage:
    fixture_id: str
    canonical: str            # logical-message id: equal canonical == true duplicate
    date: datetime            # aware, in the sender's zone
    from_addr: str
    to: list[str]
    subject: str
    body: str
    topic: str
    message_id: str = ""
    in_reply_to: str = ""
    references: str = ""
    tags: list[str] = field(default_factory=list)

    def to_email(self) -> EmailMessage:
        return EmailMessage(
            id=self.fixture_id, date=self.date, subject=self.subject, from_addr=self.from_addr,
            to=list(self.to), message_id=self.message_id, in_reply_to=self.in_reply_to,
            references=self.references, body_text=self.body, snippet=self.body[:250],
            date_source="fixture", extra={"X-Titanmail-Fixture-Id": self.fixture_id})

    def to_mime(self, run_tag: str = "") -> MimeMessage:
        m = MimeMessage()
        m["From"] = self.from_addr
        m["To"] = ", ".join(self.to)
        m["Subject"] = self.subject
        m["Date"] = format_datetime(self.date)  # keeps the sender's offset
        if self.message_id:
            m["Message-ID"] = f"<{self.message_id}>"
        if self.in_reply_to:
            m["In-Reply-To"] = self.in_reply_to
        if self.references:
            m["References"] = self.references
        m["X-Titanmail-Fixture-Id"] = self.fixture_id
        if run_tag:
            m["X-Tags"] = run_tag
        m.set_content(self.body)
        return m


@dataclass
class Fixture:
    messages: list[FixtureMessage]
    now: datetime = FIXTURE_NOW
    seed: int = 0

    def emails(self) -> list[EmailMessage]:
        return [m.to_email() for m in self.messages]

    def true_duplicate_pairs(self) -> set[frozenset]:
        by: dict[str, list[str]] = {}
        for m in self.messages:
            by.setdefault(m.canonical, []).append(m.fixture_id)
        pairs = set()
        for ids in by.values():
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    pairs.add(frozenset((ids[i], ids[j])))
        return pairs

    def span_days(self) -> float:
        ts = [m.date.timestamp() for m in self.messages]
        return (max(ts) - min(ts)) / 86400


def _body(rng: random.Random, topic: str) -> str:
    words = [rng.choice(FILLER) for _ in range(rng.randint(8, 20))]
    words.insert(rng.randint(0, len(words)), topic)
    return " ".join(words) + f" ref {rng.randint(10000, 99999)}"


def build_fixture(seed: int = 20261009, base_count: int = 330) -> Fixture:
    rng = random.Random(seed)
    msgs: list[FixtureMessage] = []
    counter = [0]

    def nid() -> str:
        counter[0] += 1
        return f"fx-{counter[0]:04d}"

    def person() -> str:
        return f"{rng.choice(PEOPLE)}@{rng.choice(DOMAINS)}"

    def add(date: datetime, *, topic: str | None = None, sender: str | None = None,
            subject: str | None = None, body: str | None = None, mid: str | None = "auto",
            canonical: str | None = None, in_reply_to: str = "", references: str = "",
            tags: list[str] | None = None) -> FixtureMessage:
        fid = nid()
        topic = topic or rng.choice(TOPICS)
        if mid == "auto":
            mid = f"{fid}.{rng.randint(1000, 9999)}@mail.{rng.choice(DOMAINS)}"
        m = FixtureMessage(
            fixture_id=fid, canonical=canonical or fid, date=date,
            from_addr=sender or person(), to=[OWNER], topic=topic,
            subject=subject or f"{topic.capitalize()} {rng.choice(['update', 'question', 'notes', 'follow-up'])} {fid[-3:]}",
            body=body or _body(rng, topic), message_id=mid or "",
            in_reply_to=in_reply_to, references=references, tags=tags or [])
        msgs.append(m)
        return m

    span = (FIXTURE_NOW - FIXTURE_START).total_seconds()
    for _ in range(base_count):
        instant = FIXTURE_START + timedelta(seconds=rng.randrange(int(span)))
        add(instant.astimezone(ZoneInfo(rng.choice(ZONES))))

    def at(s: str) -> datetime:
        return datetime.fromisoformat(s)

    edge = [
        # exact UTC midnights and +/-1 s
        "2026-06-30T23:59:59+00:00", "2026-07-01T00:00:00+00:00", "2026-07-01T00:00:01+00:00",
        "2026-10-31T23:59:59+00:00", "2026-11-01T00:00:00+00:00",
        "2026-03-31T23:59:59+00:00", "2026-04-01T00:00:00+00:00",
        # US spring-forward gap edge (America/New_York 2026-03-08)
        "2026-03-08T01:59:59-05:00", "2026-03-08T03:00:00-04:00", "2026-03-08T00:00:00-05:00",
        # US fall-back fold: the same wall clock, two instants
        "2026-11-01T01:30:00-04:00", "2026-11-01T01:30:00-05:00", "2026-11-01T00:00:00-04:00",
        "2026-11-01T23:59:59-05:00",
        # EU transitions
        "2026-03-29T00:59:59+00:00", "2026-03-29T02:00:00+01:00", "2026-10-25T01:30:00+01:00",
        "2026-10-25T01:30:00+00:00",
        # half-hour offset straddling UTC midnight
        "2026-07-01T05:29:59+05:30", "2026-07-01T05:30:00+05:30",
        # +12/+13: local date != UTC date
        "2026-06-01T08:00:00+12:00", "2026-11-15T06:00:00+13:00", "2026-11-16T00:30:00+13:00",
        # recent: inside "today"/"yesterday" for several calendar zones at FIXTURE_NOW
        "2026-11-15T11:59:59+00:00", "2026-11-15T00:00:00+00:00", "2026-11-14T23:59:59+00:00",
        "2026-11-15T04:59:59+00:00", "2026-11-15T05:00:00+00:00", "2026-11-15T10:59:59+00:00",
        "2026-11-15T11:00:00+00:00", "2026-11-09T00:00:00+00:00", "2026-11-08T23:59:59+00:00",
        "2026-11-02T05:00:00+00:00", "2026-10-01T04:00:00+00:00", "2026-10-01T03:59:59+00:00",
        "2026-09-30T11:00:00+00:00", "2026-10-31T11:00:00+00:00", "2026-10-31T10:59:59+00:00",
        "2026-11-08T12:00:00+00:00", "2026-11-08T11:59:59+00:00",
    ]
    for s in edge:
        add(at(s))

    # True duplicates: Message-ID mirror copies (same header Date).
    for src in rng.sample(msgs[:base_count], 18):
        add(src.date, topic=src.topic, sender=src.from_addr, subject=src.subject, body=src.body,
            mid=src.message_id, canonical=src.canonical)
    # True duplicates: Message-ID-less resends seconds apart.
    for _ in range(12):
        d = (FIXTURE_START + timedelta(seconds=rng.randrange(int(span) - 600))).astimezone(
            ZoneInfo(rng.choice(ZONES)))
        a = add(d, mid=None)
        add(d + timedelta(seconds=rng.randint(1, 90)), topic=a.topic, sender=a.from_addr,
            subject=a.subject, body=a.body, mid=None, canonical=a.canonical)

    # Traps that must NOT merge.
    for _ in range(4):  # Message-ID collision, different sender + subject
        src = rng.choice(msgs[:base_count])
        add(src.date + timedelta(days=rng.randint(1, 30)), mid=src.message_id)
    news_body = _body(rng, "newsletter")
    for week in range(10):  # weekly newsletter, identical content, no Message-ID
        add(at("2026-08-03T14:00:00+00:00") + timedelta(days=7 * week), topic="newsletter",
            sender="digest@northwind.test", subject="Weekly newsletter", body=news_body, mid=None)
    for _ in range(3):  # same content resent 10 minutes later: a NEW message
        d = (FIXTURE_START + timedelta(seconds=rng.randrange(int(span) - 3600))).astimezone(UTC)
        a = add(d, mid=None, topic="security", subject="Your security code")
        add(d + timedelta(minutes=10), topic="security", sender=a.from_addr,
            subject=a.subject, body=a.body, mid=None)
    for who in ("ana@acme.test", "bo@contoso.test", "chen@northwind.test"):
        add(at("2026-09-10T15:00:00+00:00"), topic="invoice", sender=who, subject="Re: Invoice")

    # Threads via In-Reply-To / References.
    for _ in range(8):
        root = add((FIXTURE_START + timedelta(seconds=rng.randrange(int(span) - 86400 * 4))).astimezone(
            ZoneInfo(rng.choice(ZONES))))
        refs = f"<{root.message_id}>"
        prev = root
        for _ in range(rng.randint(2, 4)):
            prev = add(prev.date + timedelta(hours=rng.randint(1, 20)), topic=root.topic,
                       subject=f"Re: {root.subject}", in_reply_to=f"<{prev.message_id}>",
                       references=refs)
            refs = f"{refs} <{prev.message_id}>"

    fx = Fixture(messages=msgs, seed=seed)
    _validate(fx)
    return fx


def _validate(fx: Fixture) -> None:
    ids = [m.fixture_id for m in fx.messages]
    assert len(ids) == len(set(ids)), "duplicate fixture ids"
    for m in fx.messages:
        assert m.date.tzinfo is not None and m.date.microsecond == 0
        assert m.date.astimezone(UTC) <= FIXTURE_NOW + timedelta(days=1)
        text = " ".join([m.subject, m.from_addr, " ".join(m.to), m.body]).casefold()
        for t in TOPICS:
            if t != m.topic:
                assert t not in text, f"{m.fixture_id}: topic word {t!r} leaks into a {m.topic} message"
