"""Mandate (a): the server owns the clock; windows are explicit, absolute, offset-bearing."""
from datetime import datetime, timedelta, timezone

import pytest

from titanmail.timewindow import (FrozenClock, WindowError, load_tz, parse_iso,
                                  reject_date_operators, resolve_relative, resolve_window)

NOW = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)  # Sunday
UTC = load_tz("UTC")
NY = load_tz("America/New_York")
AKL = load_tz("Pacific/Auckland")


def Z(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@pytest.mark.parametrize("value", ["2026-10-01", "2026-10-01T00:00:00", "2026-10-01 00:00",
                                   "last week", "today", "", "   "])
def test_parse_iso_rejects_naive_dates_and_phrases(value):
    with pytest.raises(WindowError):
        parse_iso(value, "after_iso")


@pytest.mark.parametrize("value,utc", [
    ("2026-10-01T00:00:00Z", "2026-10-01T00:00:00+00:00"),
    ("2026-10-01T00:00:00-04:00", "2026-10-01T04:00:00+00:00"),
    ("2026-07-01T05:30:00+05:30", "2026-07-01T00:00:00+00:00"),
    ("2026-10-01T00:00:00.250+00:00", "2026-10-01T00:00:00.250000+00:00"),
])
def test_parse_iso_accepts_explicit_offsets(value, utc):
    assert parse_iso(value, "x").astimezone(timezone.utc).isoformat() == utc


def test_window_is_required_never_inferred():
    clock = FrozenClock(NOW)
    with pytest.raises(WindowError, match="never"):
        resolve_window("", "", "", clock=clock, tz=UTC)
    with pytest.raises(WindowError):
        resolve_window("2026-10-01T00:00:00Z", "", "", clock=clock, tz=UTC)


def test_explicit_and_relative_are_mutually_exclusive():
    with pytest.raises(WindowError, match="EITHER"):
        resolve_window("2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z", "today",
                       clock=FrozenClock(NOW), tz=UTC)


def test_empty_and_oversized_windows_rejected():
    clock = FrozenClock(NOW)
    with pytest.raises(WindowError, match="empty window"):
        resolve_window("2026-10-02T00:00:00Z", "2026-10-02T00:00:00Z", clock=clock, tz=UTC)
    with pytest.raises(WindowError, match="spans more than"):
        resolve_window("2000-01-01T00:00:00Z", "2026-10-02T00:00:00Z", clock=clock, tz=UTC,
                       max_days=365)


def test_window_is_half_open():
    w = resolve_window("2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z", clock=FrozenClock(NOW), tz=UTC)
    assert w.contains(Z("2026-10-01T00:00:00Z"))
    assert w.contains(Z("2026-10-01T23:59:59Z"))
    assert not w.contains(Z("2026-10-02T00:00:00Z"))
    assert not w.contains(Z("2026-09-30T23:59:59Z"))
    # same instant expressed in another offset is still inside/outside identically
    assert not w.contains(Z("2026-10-01T20:00:00-04:00"))
    assert w.contains(Z("2026-10-01T19:59:59-04:00"))


def test_window_echo_contains_absolute_bounds():
    w = resolve_window("2026-10-01T00:00:00-04:00", "2026-10-02T00:00:00-04:00",
                       clock=FrozenClock(NOW), tz=UTC)
    d = w.to_dict()
    assert d["after_utc"] == "2026-10-01T04:00:00Z"
    assert d["before_utc"] == "2026-10-02T04:00:00Z"
    assert d["source"] == "explicit" and d["span_seconds"] == 86400


@pytest.mark.parametrize("tz,phrase,lo,hi", [
    (UTC, "today", "2026-11-15T00:00:00Z", "2026-11-16T00:00:00Z"),
    (UTC, "yesterday", "2026-11-14T00:00:00Z", "2026-11-15T00:00:00Z"),
    (UTC, "last week", "2026-11-02T00:00:00Z", "2026-11-09T00:00:00Z"),
    (UTC, "Past 7 Days", "2026-11-08T12:00:00Z", "2026-11-15T12:00:00Z"),
    (UTC, "last 3 hours", "2026-11-15T09:00:00Z", "2026-11-15T12:00:00Z"),
    (UTC, "last year", "2025-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    # DST: Oct 1 and Nov 1 midnights in New York are EDT (-04); Nov 15 is EST (-05)
    (NY, "last month", "2026-10-01T04:00:00Z", "2026-11-01T04:00:00Z"),
    (NY, "this month", "2026-11-01T04:00:00Z", "2026-12-01T05:00:00Z"),
    (NY, "today", "2026-11-15T05:00:00Z", "2026-11-16T05:00:00Z"),
    # Auckland is already Monday 2026-11-16 01:00 NZDT (+13)
    (AKL, "today", "2026-11-15T11:00:00Z", "2026-11-16T11:00:00Z"),
    (AKL, "this week", "2026-11-15T11:00:00Z", "2026-11-22T11:00:00Z"),
    (AKL, "last month", "2026-09-30T11:00:00Z", "2026-10-31T11:00:00Z"),
])
def test_relative_resolver_uses_server_clock_and_calendar(tz, phrase, lo, hi):
    w = resolve_relative(phrase, NOW, tz)
    assert w.after_utc == Z(lo) and w.before_utc == Z(hi)
    assert w.source == "relative" and w.rule


def test_relative_resolution_moves_with_the_clock_not_the_caller():
    a = resolve_relative("today", NOW, UTC)
    b = resolve_relative("today", NOW + timedelta(days=1), UTC)
    assert b.after_utc - a.after_utc == timedelta(days=1)


@pytest.mark.parametrize("phrase", ["recently", "last tuesday", "the other day", "last 0 days",
                                    "next week", "last 5 fortnights"])
def test_unknown_relative_phrases_are_rejected(phrase):
    with pytest.raises(WindowError):
        resolve_relative(phrase, NOW, UTC)


@pytest.mark.parametrize("q", ["invoice after:2026/10/01", "before: 2026-10-01", "older_than:7d",
                               "newer_than:2d", "received>=2025-10-01", "date:today"])
def test_date_operators_in_free_text_rejected(q):
    assert reject_date_operators(q)


@pytest.mark.parametrize("q", ["", "invoice", "after the meeting", "before we deploy", "today's agenda",
                               "from:ana@acme.test subject:lease"])
def test_plain_text_is_allowed(q):
    assert reject_date_operators(q) is None
