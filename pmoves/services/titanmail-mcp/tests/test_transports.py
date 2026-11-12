"""Transport contracts against mocked HTTP (httpx.MockTransport) -- no network."""
import json
from datetime import datetime, timezone

import httpx
import pytest

from titanmail.timewindow import TimeWindow
from titanmail.transports import ComposioTransport, MailpitTransport, TransportError

W = TimeWindow(datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc),
               datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc), "explicit")

SUMMARIES = [  # mailpit list/search shape (swagger MessageSummary)
    {"ID": "A", "MessageID": "a@x.test", "Created": "2026-11-20T10:00:00Z",  # received LATER
     "From": {"Name": "Ana", "Address": "ana@x.test"}, "To": [{"Name": "", "Address": "me@x.test"}],
     "Subject": "inside by header", "Snippet": "hello"},
    {"ID": "B", "MessageID": "b@x.test", "Created": "2026-11-01T12:00:00Z",
     "From": {"Address": "bo@x.test"}, "To": [], "Subject": "outside by header", "Snippet": ""},
]
HEADERS = {
    "A": {"Date": ["Sat, 31 Oct 2026 21:30:00 -0400"], "Message-Id": ["<a@x.test>"],
          "X-Titanmail-Fixture-Id": ["fx-1"]},  # = 2026-11-01T01:30Z -> inside
    "B": {"Date": ["Mon, 02 Nov 2026 00:00:00 +0000"], "Message-Id": ["<b@x.test>"],
          "In-Reply-To": ["<a@x.test>"], "References": ["<a@x.test>"],
          "From": ["Bo <bo@x.test>"], "To": ["Me <me@x.test>"], "Subject": ["=?utf-8?q?caf=C3=A9?="]},
}


def mailpit_mock(seen):
    def handler(req: httpx.Request):
        seen.append(req)
        p = req.url.path
        if p in ("/api/v1/messages", "/api/v1/search"):
            start = int(req.url.params.get("start", 0))
            limit = int(req.url.params.get("limit", 50))
            page = SUMMARIES[start:start + limit]
            return httpx.Response(200, json={"messages": page, "messages_count": len(SUMMARIES),
                                             "start": start, "total": len(SUMMARIES)})
        if p.endswith("/headers"):
            mid = p.split("/")[-2]
            return httpx.Response(200, json=HEADERS[mid]) if mid in HEADERS else httpx.Response(404)
        if p.startswith("/view/"):
            return httpx.Response(200, text="body text")
        return httpx.Response(500, text="unexpected " + p)
    return handler


async def test_mailpit_uses_header_date_not_received_time():
    seen = []
    t = MailpitTransport("http://mp:8025", page_size=1,
                         client=httpx.AsyncClient(transport=httpx.MockTransport(mailpit_mock(seen))))
    out = await t.search(W, "", 100)
    assert [m.id for m in out] == ["A"]
    assert out[0].date_source == "header:Date"
    assert out[0].extra == {"X-Titanmail-Fixture-Id": "fx-1"}
    assert sum(1 for r in seen if r.url.path == "/api/v1/messages") == 2  # paginated, page_size=1


async def test_mailpit_scope_and_query_go_to_search_endpoint():
    seen = []
    t = MailpitTransport("http://mp:8025", scope_query="tag:run-1",
                         client=httpx.AsyncClient(transport=httpx.MockTransport(mailpit_mock(seen))))
    await t.search(W, "invoice", 100)
    q = [r for r in seen if r.url.path == "/api/v1/search"][0]
    assert q.url.params["query"] == "tag:run-1 invoice"


async def test_mailpit_prefilter_only_when_created_equals_date():
    seen = []
    t = MailpitTransport("http://mp:8025", use_message_dates=True,
                         client=httpx.AsyncClient(transport=httpx.MockTransport(mailpit_mock(seen))))
    await t.search(W, "", 100)
    q = [r for r in seen if r.url.path == "/api/v1/search"][0]
    assert q.url.params["query"] == "after:2026/10/31 before:2026/11/04"
    assert q.url.params["tz"] == "UTC"


async def test_mailpit_get_never_marks_read():
    seen = []
    t = MailpitTransport("http://mp:8025",
                         client=httpx.AsyncClient(transport=httpx.MockTransport(mailpit_mock(seen))))
    msg = await t.get("B")
    assert msg.subject == "café" and msg.body_text == "body text" and msg.from_addr == "bo@x.test"
    assert msg.in_reply_to == "<a@x.test>"
    # GET /api/v1/message/{ID} marks a message read in mailpit; only headers + view are allowed
    assert {r.url.path for r in seen} == {"/api/v1/message/B/headers", "/view/B.txt"}
    assert await t.get("missing") is None


async def test_mailpit_unreachable_is_transport_error():
    def boom(req):
        raise httpx.ConnectError("refused")
    t = MailpitTransport("http://mp:8025", client=httpx.AsyncClient(transport=httpx.MockTransport(boom)))
    with pytest.raises(TransportError, match="unreachable"):
        await t.search(W, "", 10)


async def test_mailpit_scan_cap_refuses_partial_results():
    def big(req):
        return httpx.Response(200, json={"messages": SUMMARIES, "messages_count": 10_000})
    t = MailpitTransport("http://mp:8025", max_scan=2, page_size=2,
                         client=httpx.AsyncClient(transport=httpx.MockTransport(big)))
    with pytest.raises(TransportError, match="scan cap"):
        await t._summaries(W, "")  # noqa: SLF001


# --- Composio -------------------------------------------------------------------------

KEY = "ck_test_SECRET_do_not_log"


def composio_mock(seen, data, status=200, successful=True):
    def handler(req: httpx.Request):
        seen.append(req)
        return httpx.Response(status, json={"data": data, "error": None if successful else "bad",
                                            "successful": successful, "log_id": "l1"})
    return handler


async def test_composio_gmail_request_shape_and_day_padding():
    seen = []
    data = {"messages": [
        {"messageId": "g1", "threadId": "t1", "internalDate": str(int(datetime(2026, 11, 1, 6, tzinfo=timezone.utc).timestamp() * 1000)),
         "subject": "in", "sender": "Ana <ana@x.test>", "to": "me@x.test",
         "payload": {"headers": [{"name": "Message-ID", "value": "<g1@x.test>"}]}},
        {"messageId": "g2", "internalDate": str(int(datetime(2026, 11, 2, 0, tzinfo=timezone.utc).timestamp() * 1000)),
         "subject": "at before -> out"},
    ]}
    t = ComposioTransport("gmail", api_key=KEY, user_id="u1",
                          client=httpx.AsyncClient(transport=httpx.MockTransport(composio_mock(seen, data))))
    out = await t.search(W, "invoice", 50)
    assert [m.id for m in out] == ["g1"]
    assert out[0].message_id == "<g1@x.test>" and out[0].thread_id == "t1"
    req = seen[0]
    assert str(req.url) == "https://backend.composio.dev/api/v3.1/tools/execute/GMAIL_FETCH_EMAILS"
    assert req.headers["x-api-key"] == KEY
    body = json.loads(req.content)
    assert body["user_id"] == "u1"
    assert body["arguments"]["query"] == "invoice after:2026/10/31 before:2026/11/04"


async def test_composio_outlook_exact_odata_window():
    seen = []
    data = {"value": [{"id": "o1", "receivedDateTime": "2026-11-01T00:00:00Z", "subject": "Invoice",
                       "from": {"emailAddress": {"address": "ana@x.test"}},
                       "toRecipients": [{"emailAddress": {"address": "me@x.test"}}],
                       "internetMessageId": "<o1@x.test>", "conversationId": "c1"},
                      {"id": "o2", "receivedDateTime": "2026-11-01T05:00:00Z", "subject": "other"}]}
    t = ComposioTransport("outlook", api_key=KEY,
                          client=httpx.AsyncClient(transport=httpx.MockTransport(composio_mock(seen, data))))
    out = await t.search(W, "invoice", 50)
    assert [m.id for m in out] == ["o1"]  # text matched client-side (Graph forbids $search+$filter)
    args = json.loads(seen[0].content)["arguments"]
    assert seen[0].url.path.endswith("/OUTLOOK_LIST_MESSAGES")
    assert args["filter"] == ("receivedDateTime ge 2026-11-01T00:00:00Z and "
                              "receivedDateTime lt 2026-11-02T00:00:00Z")


async def test_composio_slugs_are_config():
    seen = []
    t = ComposioTransport("gmail", api_key=KEY, slugs={"search": "GMAIL_RENAMED"},
                          client=httpx.AsyncClient(transport=httpx.MockTransport(composio_mock(seen, {}))))
    await t.search(W, "", 5)
    assert seen[0].url.path.endswith("/GMAIL_RENAMED")


async def test_composio_key_never_leaks():
    seen = []
    t = ComposioTransport("gmail", api_key=KEY,
                          client=httpx.AsyncClient(transport=httpx.MockTransport(
                              composio_mock(seen, {}, status=401))))
    with pytest.raises(TransportError) as ei:
        await t.search(W, "", 5)
    assert KEY not in str(ei.value)
    assert KEY not in repr(t) and KEY not in json.dumps(t.describe())
    assert t.describe()["api_key_configured"] is True


async def test_composio_missing_key_and_unsuccessful():
    with pytest.raises(TransportError, match="COMPOSIO_API_KEY"):
        await ComposioTransport("gmail", api_key="").search(W, "", 5)
    seen = []
    t = ComposioTransport("gmail", api_key=KEY, client=httpx.AsyncClient(
        transport=httpx.MockTransport(composio_mock(seen, {}, successful=False))))
    with pytest.raises(TransportError, match="unsuccessful"):
        await t.search(W, "", 5)


def test_composio_provider_validated():
    with pytest.raises(ValueError):
        ComposioTransport("yahoo", api_key=KEY)


async def test_mailpit_synthetic_message_ids_are_treated_as_absent():
    """mailpit inserts `<random>@mailpit` into header-less mail (measured on v1.31.6)."""
    hdrs = {"S1": {"Date": ["Sun, 01 Nov 2026 05:00:00 +0000"], "Message-Id": ["<6DCHCbZrS9@mailpit>"]}}
    summ = [{"ID": "S1", "MessageID": "6DCHCbZrS9@mailpit", "Created": "2026-11-01T05:00:00Z",
             "From": {"Address": "a@x.test"}, "To": [], "Subject": "s"}]

    def handler(req):
        if req.url.path.endswith("/headers"):
            return httpx.Response(200, json=hdrs["S1"])
        return httpx.Response(200, json={"messages": summ, "messages_count": 1})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert (await MailpitTransport("http://mp", client=client).search(W, "", 5))[0].message_id == ""
    keep = MailpitTransport("http://mp", ignore_synthetic_message_ids=False, client=client)
    assert (await keep.search(W, "", 5))[0].message_id == "<6DCHCbZrS9@mailpit>"
