"""Server-side time authority for TitanMail.

Mandate (a) of the seed spec: no email query may rely on a model-inferred
"today". This module is the only place TitanMail learns what time it is
(:class:`Clock`), the only place it parses a caller-supplied datetime
(:func:`parse_iso`), and the only place a relative phrase such as "last week"
becomes an absolute window (:func:`resolve_relative`). Every tool response
echoes the :class:`TimeWindow` it actually used, so a caller can always see the
absolute bounds and the server timestamp the answer was computed against.

Window semantics are half-open and absolute: ``after <= t < before``, compared
in UTC. A datetime without an explicit UTC offset is rejected rather than
guessed at -- a naive "2026-10-01T00:00" is exactly the ambiguity this service
exists to remove.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc

# Ten years. A window wider than this is almost certainly a mistake, and a
# provider page-walk over it is expensive.
DEFAULT_MAX_WINDOW_DAYS = 3660


class WindowError(ValueError):
    """A caller-supplied window could not be resolved. The message is shown to the caller."""


class Clock(Protocol):
    def now(self) -> datetime:  # pragma: no cover - protocol
        """Current instant, timezone-aware."""


class SystemClock:
    """The real clock. Always returns an aware UTC datetime."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """A clock pinned to one instant -- for tests and the eval harness."""

    def __init__(self, instant: datetime):
        if instant.tzinfo is None:
            raise ValueError("FrozenClock needs an aware datetime")
        self._instant = instant

    def now(self) -> datetime:
        return self._instant


def load_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown IANA timezone {name!r}") from exc


def iso_z(dt: datetime) -> str:
    """UTC ISO-8601 with a literal Z, seconds precision unless sub-second is set."""
    dt = dt.astimezone(UTC)
    spec = "milliseconds" if dt.microsecond else "seconds"
    return dt.isoformat(timespec=spec).replace("+00:00", "Z")


def parse_iso(value: str, field: str) -> datetime:
    """Parse an ISO-8601 datetime that MUST carry an explicit UTC offset (or Z)."""
    if not isinstance(value, str) or not value.strip():
        raise WindowError(f"{field} is required: an ISO-8601 datetime with an explicit offset, "
                          "e.g. 2026-10-01T00:00:00Z or 2026-10-01T00:00:00-04:00")
    raw = value.strip()
    try:
        dt = datetime.fromisoformat(raw.replace("z", "Z"))
    except ValueError as exc:
        raise WindowError(
            f"{field}={raw!r} is not an ISO-8601 datetime. Relative phrases such as 'last week' "
            "go in the `relative` parameter, where the server resolves them."
        ) from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise WindowError(
            f"{field}={raw!r} has no UTC offset. TitanMail does not guess a timezone: "
            "append Z or an offset such as -04:00."
        )
    return dt


@dataclass(frozen=True)
class TimeWindow:
    after: datetime          # inclusive
    before: datetime         # exclusive
    source: str              # "explicit" | "relative"
    phrase: str = ""         # the relative phrase, when source == "relative"
    rule: str = ""           # how the phrase was resolved, in words
    tz: str = "UTC"          # calendar timezone used by the resolver

    def contains(self, t: datetime) -> bool:
        return self.after <= t < self.before

    @property
    def after_utc(self) -> datetime:
        return self.after.astimezone(UTC)

    @property
    def before_utc(self) -> datetime:
        return self.before.astimezone(UTC)

    def to_dict(self) -> dict:
        out = {
            "after": self.after.isoformat(),
            "before": self.before.isoformat(),
            "after_utc": iso_z(self.after),
            "before_utc": iso_z(self.before),
            "semantics": "after <= message_time < before (absolute, compared in UTC)",
            "span_seconds": int((self.before - self.after).total_seconds()),
            "source": self.source,
        }
        if self.source == "relative":
            out.update(phrase=self.phrase, rule=self.rule, calendar_tz=self.tz)
        return out


# ---------------------------------------------------------------------------
# Relative-phrase resolver
# ---------------------------------------------------------------------------

RELATIVE_GRAMMAR = (
    "today | yesterday | this week | last week | this month | last month | this year | "
    "last year | last N hours | last N days | last N weeks  ('past' is accepted for 'last'; "
    "weeks start Monday; calendar phrases use the server calendar timezone; 'last N <unit>' "
    "is a rolling window ending at the server's current instant)"
)

_ROLLING = re.compile(r"^(?:last|past)\s+(\d{1,4})\s+(hour|hours|day|days|week|weeks)$")


def _midnight(d: date, tz: ZoneInfo) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=tz)


def _month_start(year: int, month: int) -> date:
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def resolve_relative(phrase: str, now: datetime, tz: ZoneInfo) -> TimeWindow:
    """Resolve a relative phrase against the SERVER's clock. Unknown phrases are rejected."""
    norm = re.sub(r"\s+", " ", (phrase or "").strip().lower())
    norm = norm.replace("past ", "last ") if norm.startswith("past ") else norm
    if not norm:
        raise WindowError("relative phrase is empty")
    local_now = now.astimezone(tz)
    today = local_now.date()
    tzname = getattr(tz, "key", str(tz))

    def cal(after_d: date, before_d: date, rule: str) -> TimeWindow:
        return TimeWindow(_midnight(after_d, tz), _midnight(before_d, tz), "relative",
                          phrase=phrase, rule=rule, tz=tzname)

    if norm == "today":
        return cal(today, today + timedelta(days=1), "local midnight today -> local midnight tomorrow")
    if norm == "yesterday":
        return cal(today - timedelta(days=1), today, "local midnight yesterday -> local midnight today")
    monday = today - timedelta(days=today.weekday())
    if norm == "this week":
        return cal(monday, monday + timedelta(days=7), "Monday 00:00 this ISO week -> next Monday 00:00")
    if norm in ("last week", "previous week"):
        return cal(monday - timedelta(days=7), monday, "Monday 00:00 previous ISO week -> Monday 00:00 this week")
    if norm == "this month":
        return cal(_month_start(today.year, today.month), _month_start(today.year, today.month + 1),
                   "1st of this month 00:00 -> 1st of next month 00:00")
    if norm in ("last month", "previous month"):
        return cal(_month_start(today.year, today.month - 1), _month_start(today.year, today.month),
                   "1st of previous month 00:00 -> 1st of this month 00:00")
    if norm == "this year":
        return cal(date(today.year, 1, 1), date(today.year + 1, 1, 1), "Jan 1 00:00 -> next Jan 1 00:00")
    if norm in ("last year", "previous year"):
        return cal(date(today.year - 1, 1, 1), date(today.year, 1, 1), "previous Jan 1 00:00 -> Jan 1 00:00")
    m = _ROLLING.match(norm)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if n <= 0:
            raise WindowError(f"relative phrase {phrase!r}: N must be positive")
        hours = n * {"hour": 1, "day": 24, "week": 24 * 7}[unit.rstrip("s")]
        start = now - timedelta(hours=hours)
        return TimeWindow(start.astimezone(UTC), now.astimezone(UTC), "relative", phrase=phrase,
                          rule=f"rolling {hours}h ending at the server's current instant", tz=tzname)
    raise WindowError(f"unsupported relative phrase {phrase!r}. Supported: {RELATIVE_GRAMMAR}. "
                      "Or pass explicit after_iso/before_iso.")


def resolve_window(after_iso: str = "", before_iso: str = "", relative: str = "", *,
                   clock: Clock, tz: ZoneInfo,
                   max_days: int = DEFAULT_MAX_WINDOW_DAYS) -> TimeWindow:
    """The single entry point every tool uses to obtain its window."""
    after_iso = (after_iso or "").strip()
    before_iso = (before_iso or "").strip()
    relative = (relative or "").strip()
    if relative and (after_iso or before_iso):
        raise WindowError("pass EITHER explicit after_iso+before_iso OR relative, not both")
    if relative:
        win = resolve_relative(relative, clock.now(), tz)
    else:
        if not after_iso or not before_iso:
            raise WindowError("a window is required: pass both after_iso and before_iso "
                              "(ISO-8601 with offset) or a `relative` phrase. TitanMail never "
                              "infers 'today' on the caller's behalf.")
        win = TimeWindow(parse_iso(after_iso, "after_iso"), parse_iso(before_iso, "before_iso"),
                         "explicit")
    if not win.after < win.before:
        raise WindowError(f"empty window: after ({win.after.isoformat()}) must be earlier than "
                          f"before ({win.before.isoformat()})")
    if win.before - win.after > timedelta(days=max_days):
        raise WindowError(f"window spans more than {max_days} days; narrow it")
    return win


# Date operators a model might smuggle into free text to do its own date math.
# The window lives in parameters, not in the query string.
_DATE_OPERATOR = re.compile(
    r"(?i)(?<![\w-])(after|before|since|until|older|newer|older_than|newer_than|received|sent|date)"
    r"\s*(:|>=|<=|>|<|=)"
)


def reject_date_operators(query: str) -> Optional[str]:
    """Return an error message if ``query`` carries date operators, else None."""
    m = _DATE_OPERATOR.search(query or "")
    if m:
        return (f"query contains a date operator ({m.group(0).strip()!r}). Put the window in "
                "after_iso/before_iso (or `relative`) so the server resolves it -- date math in "
                "free text is exactly the failure mode TitanMail removes.")
    return None
