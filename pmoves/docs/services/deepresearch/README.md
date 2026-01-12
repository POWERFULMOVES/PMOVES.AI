# DeepResearch Service

The DeepResearch worker connects the PMOVES event bus to Alibaba Tongyi DeepResearch
(either via OpenRouter or a locally hosted stack) and mirrors finished summaries into
Open Notebook for downstream review. The worker listens for
`research.deepresearch.request.v1` envelopes on NATS, orchestrates a research run, and
publishes `research.deepresearch.result.v1` responses enriched with Notebook metadata.

## Compose profile & runtime

- **Compose service:** `deepresearch`
- **Profile:** `agents`
- **Depends on:** `nats`
- **Dockerfile:** `services/deepresearch/Dockerfile`
- **Default command:** `python -m services.deepresearch.worker`

Start the service together with the other agents:

```bash
make up-agents
```

The container will clone `Alibaba-NLP/DeepResearch` at commit
`3f2845ffea03f198a84716a580e2cbb4145b0465` during build so that operators can flip to
"local" execution once the planning stack is deployed.

## Configuration

| Variable | Description |
| --- | --- |
| `DEEPRESEARCH_MODE` | `openrouter` (default) or `local`. Controls which runner executes the query. |
| `DEEPRESEARCH_TIMEOUT` | Overall timeout (seconds) applied to model/API calls. |
| `OPENROUTER_API_KEY` | Required when `DEEPRESEARCH_MODE=openrouter`. |
| `DEEPRESEARCH_OPENROUTER_MODEL` | Model slug passed to OpenRouter (defaults to `tongyi-deepresearch`). |
| `DEEPRESEARCH_OPENROUTER_API_BASE` | Base URL for OpenRouter (defaults to `https://openrouter.ai/api`). |
| `DEEPRESEARCH_API_BASE` | Base URL for a locally hosted DeepResearch planning API when `DEEPRESEARCH_MODE=local`. |
| `DEEPRESEARCH_PLANNING_ENDPOINT` | Path appended to `DEEPRESEARCH_API_BASE` for local runs (default `/api/research`). |
| `DEEPRESEARCH_NOTEBOOK_ID` | Optional default Open Notebook workspace ID for mirroring summaries. |
| `DEEPRESEARCH_NOTEBOOK_TITLE_PREFIX` | Prefix applied to Notebook source titles when publishing results. |
| `DEEPRESEARCH_NOTEBOOK_EMBED` / `DEEPRESEARCH_NOTEBOOK_ASYNC` | Control Notebook ingest behaviour (content embedding + async processing). |
| `OPEN_NOTEBOOK_API_URL` / `OPEN_NOTEBOOK_API_TOKEN` | Provide the Notebook API endpoint and bearer token when mirroring research summaries. |
| `DEEPRESEARCH_LOG_LEVEL` | Optional log level override (defaults to `INFO`). |

Per-request overrides for Notebook publishing (`notebook.notebook_id`, `title_prefix`,
`embed`, `async_processing`) are honoured if present in the request envelope payload.

## Event contracts

DeepResearch uses two new topics registered in `pmoves/contracts/topics.json`:

- `research.deepresearch.request.v1` → `contracts/schemas/research/deepresearch.request.v1.schema.json`
- `research.deepresearch.result.v1` → `contracts/schemas/research/deepresearch.result.v1.schema.json`

Sample payloads live under `contracts/samples/research/` and can be replayed with the
existing `services/common/events.envelope` helper for smoke tests.

## Open Notebook integration

When Notebook credentials are supplied the worker will automatically create a `text`
source via `POST /api/sources/json`. The content includes the summary, bullet notes,
linked sources, and—when the payload is small enough—the raw JSON returned by DeepResearch.
The returned `id` is stored on the result envelope as `notebook_entry_id` and echoed in
`payload.metadata.notebook.entry_id` for downstream automation.

Failures to publish to Notebook are logged and captured in
`payload.metadata.notebook.error` so operators can retry once connectivity is restored.

## Smoke test

With the service running you can publish a synthetic request (replace the API key and
Notebook fields with valid values):

```bash
python - <<'PY'
import asyncio, json
from services.common import events

async def main():
    payload = json.loads(open("pmoves/contracts/samples/research/deepresearch.request.v1.json", "r", encoding="utf-8").read())
    await events.publish("research.deepresearch.request.v1", payload)

asyncio.run(main())
PY
```

Confirm the worker emits `research.deepresearch.result.v1` by tailing the topic with
`pmoves/tools/realtime_listener.py` or by checking the Notebook workspace for a newly
created source.

## Next steps

- Stand up the local DeepResearch planning service (the upstream repository ships a
  `docker-compose` profile) and point `DEEPRESEARCH_API_BASE` at it to remove reliance on
  OpenRouter.
- Expand result parsing with tool/action telemetry once the local planner protocol is
  finalised.
- Add Prometheus counters for request counts, error rates, and Notebook publish latency
  when the observability stack is wired into the agents profile.
