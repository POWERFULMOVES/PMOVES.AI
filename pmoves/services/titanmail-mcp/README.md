# titanmail-mcp

Date-exact, dedup-aware email retrieval over MCP. Seed spec:
`research/analyses/2026-10-09_TITANMAIL_MCP_SPEC.md`. Status: **built, not deployed**.

## Tools

| Tool | Signature | Notes |
|---|---|---|
| `search_messages` | `(query="", after_iso="", before_iso="", limit=50, relative="")` | window required; date operators in `query` rejected |
| `get_message` | `(id)` | headers + text body; never marks mail read |
| `list_threads` | `(after_iso="", before_iso="", relative="")` | provider thread id, else In-Reply-To/References |
| `dedup_report` | `(after_iso="", before_iso="", relative="")` | read-only report |
| `now` | `()` | server's exact instant, IANA zone, UTC offset |

Every response carries `envelope.server_time_utc` and `envelope.window` (absolute,
half-open `after <= t < before`). Datetimes without an offset are rejected. Relative
phrases (`today`, `yesterday`, `this/last week|month|year`, `last N hours|days|weeks`)
are resolved by the server clock in `TITANMAIL_TZ`; anything else is rejected.

## Transports
- `mailpit` (dev; PMOVES-Mike's `mailpit`). Uses `/api/v1/messages`, `/api/v1/search`,
  `/api/v1/message/{ID}/headers`, `/view/{ID}.txt`. The RFC 5322 `Date` header is
  authoritative (mailpit's `Created` is receive time). mailpit-synthesised
  `<x>@mailpit` Message-IDs are treated as absent.
- `composio-gmail` / `composio-outlook`: `POST {COMPOSIO base}/tools/execute/{slug}`
  with `x-api-key`. Slugs `GMAIL_FETCH_EMAILS`, `GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID`,
  `OUTLOOK_LIST_MESSAGES`, `OUTLOOK_GET_MESSAGE` (configurable). Not yet run live.

## Dedup
Message-ID first (sender+subject must agree, else reported as a conflict), then
from+to+subject+body-hash within 120 s for Message-ID-less mail. Ambiguous cases are
reported, never merged. `TieBreaker` is the seam for a later AI tie-breaker.

## Harness (`eval/run_harness.py`)
468-message synthetic inbox over 273 days (DST both hemispheres, UTC-midnight ±1 s,
+05:30/+13:00 offsets, duplicates and no-merge traps), 182 queries with independent
ground truth. Fails (exit 1) below 99% date accuracy or 99.9% dedup precision; exit 3
is could-not-measure.

```bash
make -C pmoves titanmail-test
make -C pmoves titanmail-eval                       # offline, in-memory, via MCP call_tool
make -C pmoves titanmail-eval ARGS="--transport mailpit --mailpit-url http://127.0.0.1:8025 --seed-smtp 127.0.0.1:1025"
```
Live mode writes ~470 tagged messages; use a throwaway mailpit (`MP_MAX_MESSAGES`
default 500 prunes older mail).

## Run
`make -C pmoves up-titanmail-mcp` once the compose service is applied. Port 8209 on the
host (loopback) -> 8092. Lock regen: `uv pip compile requirements.txt -o requirements.lock --python-version 3.12 --universal`.
