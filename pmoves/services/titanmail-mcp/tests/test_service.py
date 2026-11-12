"""Server-side datetime injection and exact-window enforcement at the service boundary."""
from datetime import datetime, timedelta, timezone

import pytest

from titanmail.models import EmailMessage
from titanmail.service import TitanMailService
from titanmail.timewindow import FrozenClock, load_tz
from titanmail.transports import InMemoryTransport, TransportError

NOW = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)


def Z(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def msg(i, when, subject="hello", **kw):
    return EmailMessage(id=f"m{i}", date=Z(when), subject=subject, from_addr="a@x.test",
                        to=["me@x.test"], message_id=f"{i}@x.test", **kw)


MSGS = [msg(1, "2026-11-14T23:59:59Z"), msg(2, "2026-11-15T00:00:00Z"),
        msg(3, "2026-11-15T11:59:59Z", subject="invoice"), msg(4, "2026-11-16T00:00:00Z"),
        msg(5, "2026-11-15T03:00:00-05:00")]


class OverfetchTransport:
    """Returns EVERYTHING regardless of window -- the service must still be exact."""
    name = "overfetch"

    def __init__(self, msgs):
        self.msgs = msgs
        self.calls = []

    async def search(self, window, query, max_results):
        self.calls.append((window, query, max_results))
        return list(self.msgs)

    async def get(self, message_id):
        return None

    def describe(self):
        return {"transport": self.name}


def svc(transport=None, tz="UTC"):
    return TitanMailService(transport or InMemoryTransport(MSGS), clock=FrozenClock(NOW), tz=load_tz(tz))


async def test_now_is_server_clock_with_tz_and_offset():
    out = svc(tz="America/New_York").now()
    assert out["server_time_utc"] == "2026-11-15T12:00:00Z"
    assert out["server_time_local"] == "2026-11-15T07:00:00-05:00"
    assert out["server_tz"] == "America/New_York" and out["utc_offset"] == "-0500"
    assert out["epoch_ms"] == int(NOW.timestamp() * 1000)


async def test_every_search_response_echoes_window_and_server_time():
    out = await svc().search_messages("", "2026-11-15T00:00:00Z", "2026-11-16T00:00:00Z")
    assert out["ok"]
    env = out["envelope"]
    assert env["server_time_utc"] == "2026-11-15T12:00:00Z"
    assert env["window"]["after_utc"] == "2026-11-15T00:00:00Z"
    assert env["window"]["before_utc"] == "2026-11-16T00:00:00Z"
    assert sorted(m["id"] for m in out["messages"]) == ["m2", "m3", "m5"]


async def test_search_without_window_is_refused_not_defaulted_to_today():
    out = await svc().search_messages("invoice")
    assert out["ok"] is False and "never" in out["error"]
    assert out["envelope"]["server_time_utc"] == "2026-11-15T12:00:00Z"
    assert out["envelope"]["window"] is None


async def test_date_operator_in_query_refused():
    out = await svc().search_messages("invoice after:2026/11/01", "2026-11-15T00:00:00Z",
                                      "2026-11-16T00:00:00Z")
    assert out["ok"] is False and "date operator" in out["error"]


async def test_relative_resolved_server_side_and_echoed():
    out = await svc().search_messages("", relative="yesterday")
    w = out["envelope"]["window"]
    assert (w["after_utc"], w["before_utc"]) == ("2026-11-14T00:00:00Z", "2026-11-15T00:00:00Z")
    assert w["source"] == "relative" and w["phrase"] == "yesterday"
    assert [m["id"] for m in out["messages"]] == ["m1"]


async def test_service_trims_overfetching_transport_to_exact_half_open_window():
    t = OverfetchTransport(MSGS)
    out = await svc(t).search_messages("", "2026-11-15T00:00:00Z", "2026-11-15T11:59:59Z")
    assert sorted(m["id"] for m in out["messages"]) == ["m2", "m5"]  # m3 is AT before -> excluded
    window = t.calls[0][0]
    assert window.after_utc == Z("2026-11-15T00:00:00Z")  # the transport got absolute bounds


async def test_limit_truncates_but_total_is_exact():
    out = await svc().search_messages("", "2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z", limit=2)
    assert out["total_in_window"] == 5 and out["returned"] == 2 and out["truncated"] is True
    assert [m["id"] for m in out["messages"]] == ["m4", "m3"]  # newest first


async def test_text_query_applies_inside_window():
    out = await svc().search_messages("INVOICE", "2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z")
    assert [m["id"] for m in out["messages"]] == ["m3"]


async def test_transport_error_is_reported_with_envelope():
    class Boom(OverfetchTransport):
        async def search(self, window, query, max_results):
            raise TransportError("mailpit unreachable")

    out = await svc(Boom([])).search_messages("", relative="today")
    assert out["ok"] is False and out["error_type"] == "TransportError"
    assert out["envelope"]["window"]["phrase"] == "today"


async def test_get_message_found_and_missing():
    s = svc()
    ok = await s.get_message("m3")
    assert ok["ok"] and ok["message"]["subject"] == "invoice" and ok["envelope"]["window"] is None
    missing = await s.get_message("nope")
    assert missing["ok"] is False


async def test_list_threads_and_dedup_report_take_windows():
    s = svc()
    th = await s.list_threads("2026-11-15T00:00:00Z", "2026-11-16T00:00:00Z")
    assert th["ok"] and th["messages_in_window"] == 3 and th["envelope"]["window"]
    dd = await s.dedup_report(relative="this month")
    assert dd["ok"] and dd["messages_examined"] == 5 and dd["duplicates"] == 0
    bad = await s.list_threads()
    assert bad["ok"] is False


def test_naive_message_dates_rejected_at_model_boundary():
    with pytest.raises(ValueError):
        EmailMessage(id="x", date=datetime(2026, 1, 1))  # no tzinfo
    assert timedelta  # keep import used
