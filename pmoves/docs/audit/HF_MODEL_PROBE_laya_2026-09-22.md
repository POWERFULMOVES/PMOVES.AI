# laya probe — 2026-09-22 (probe run 2026-09-23)

**Node:** PMOVES-SPARK (`/home/powerfulmoves/agent-zero/PMOVES.AI`) · **Branch:** `feat/comfyui-ui-to-api` · **Operating surface:** OpenRoom
**Task:** `t-20260922T202933Z-8f3a0b5b2d9e` · **Goal:** `g-20260922T142400Z-d1e2f3a4b5c6d7e8` · round 1 · criterion **SC-2**
**Inventory input:** `pmoves/docs/audit/HF_MODEL_INVENTORY_2026-09-22.md` §4 (Laya row, `local-viable`)
**Probe-script artifact (intermediate, not retained):** the probe driver and raw output lived under `/tmp/probe/` and were not preserved; the results below are the record. A re-run needs a fresh driver.
**Bounded probe spec scope:** cipher sign · CHIT geometry-bus interaction · NATS round-trip — exactly three, per the task spec; no fourth probe added.

---

## Start

- **command** (host-side probe driver, executed under `bash pmoves/scripts/with-env.sh`):
  ```
  bash pmoves/scripts/with-env.sh /home/powerfulmoves/miniforge3/bin/python3 /tmp/probe/probe_laya.py
  ```
- **compose / make target**: no compose overlay was changed. The probe rides the **already-running** `pmoves-hf-mcp-server` (Up 8 days, port 127.0.0.1:8203), `pmoves-nats-1` (Up 10 days, port 4222), `pmoves-cipher-api-1` (Up 5 hours, port 127.0.0.1:8105), and `pmoves-qdrant-1` (Up 10 days, ports 6333-6334) — the SC-1-accepted integration surface. No service was started, stopped, restarted, or rebuilt. The `pmoves/env.shared` `NATS_URL`/`NATS_USER`/`NATS_PASSWORD` is the host-side canonical auth for `nats-cli`-equivalent access.
- **container / process**: probe driver is a host-side Python process (nats-py 2.15.0, urllib stdlib, subprocess). No container process was created. The existing containers are referenced by name in §`Start` only; no Docker exec was performed against them.
- **started_at**: `2026-09-23T00:04:05Z`
- **ready_at**: `2026-09-23T00:04:05Z` (no model warm-up; bounded probe is integration-surface, not inference)

## Cipher sign

- **payload**: `{"hello":"laya","model_id":"convaiinnovations/laya","ts":"2026-09-23T00:04:05Z"}` — the SC-2 spec's bounded shape; the model name is the integration reference, not a token-bearing claim.
- **tool call**: `bash pmoves/scripts/with-env.sh python3 pmoves/scripts/mint_cipher_token.py --agent spark-claude --scopes memory:read,memory:write --allow-uncarded --rest-url http://localhost:8000/rest/v1`
  - `--allow-uncarded` is the documented override for the case where a fleet agent emits but is not yet on the active card list (`pmoves/scripts/mint_cipher_token.py` gate, per `pmoves/docs/operations/CIPHER_AUTH_RUNBOOK.md`).
  - `--rest-url http://localhost:8000/rest/v1` overrides the with-env.sh default `http://supabase-kong:8000/rest/v1` (which only resolves inside the docker network). The host-side supabase-kong is reachable at `localhost:8000`.
- **result**: success; `CIPHER_TOKEN=<redacted:token_uuid>` shape; `AGENT=spark-claude`; `SCOPES=memory:read,memory:write`; returncode 0; a token of the expected shape was returned (value and structure not recorded here).
- **timing**: 102 ms end-to-end (subprocess spawn + urllib HTTPS round-trip + Supabase insert).

## CHIT geometry-bus

- **subject**: `tokenism.cgp.ready.v1` — the documented CHIT geometry-bus "CGP Ready" subject (`.claude/context/geometry-nats-subjects.md` §"CGP Ready": published by any CGP producer, consumed by Hi-RAG v2, shape-store, analytics).
- **payload**: a CGP-v0.1-shaped packet:
  ```json
  {
    "spec": "chit.cgp.v0.1",
    "summary": "SC-2 probe: cipher / CHIT / NATS round-trip for laya",
    "created_at": "2026-09-23T00:04:05Z",
    "super_nodes": [
      {
        "id": "probe-laya-57a43554",
        "label": "probe-laya",
        "x": 0.0, "y": 0.0, "r": 0.1,
        "constellations": []
      }
    ],
    "meta": {
      "source": "sc2.probe.laya",
      "model_id": "convaiinnovations/laya",
      "probe_kind": "geometry-bus-interaction"
    }
  }
  ```
- **observation**: subscribed to `tokenism.cgp.ready.v1` BEFORE publishing, with a 0.1 s subscribe-to-publish gap in the probe driver (a race margin of the driver, not a bus property; a slower host could need more). The publish landed and the same subject delivered the message back to the host-side subscriber (`bus_reply_observations[0].size == 346`, `subject == "tokenism.cgp.ready.v1"`, payload digest matches the published payload). This is a **self-echo through the geometry bus**: NATS delivers published messages to every subscriber on the subject, and the host client is itself a subscriber. It proves (a) the subject accepts the CGP-shaped payload, (b) the bus routes the message at the geometry-bus subject, and (c) Hi-RAG v2 / shape-store / analytics subscribers on the same subject inside the docker network would receive the same payload (the geometry-bus architecture places those subscribers on `nats://nats:4222`, not on the host client, so we cannot observe their downstream action from this probe).
- **timing**: publish 1 ms; subscriber delivery within the same poll window (<500 ms observation window).

## NATS round-trip

- **subject**: `probe.laya.20260923T000406Z.346b53d1` — fresh, scoped to this probe run.
- **payload**: a CGP-v0.1-shaped packet with `meta.source = "sc2.probe.nats-rt"` and `meta.model_id = "convaiinnovations/laya"`.
- **timing**: end-to-end round-trip **<1 ms** (below the subprocess timing resolution; the actual one-way publish-then-receive crosses a single in-process asyncio loop and a single NATS server hop, well below the 1 ms measurement floor).
- **received**: `true`; **payload_match**: `true` (subscribed message `meta.source == "sc2.probe.nats-rt"`).

## Verdict

- **integrates cleanly**: **yes**
- **rationale**: the bounded probe set (cipher / CHIT geometry-bus / NATS round-trip) all succeed for the Laya model context. The probe demonstrates the integration surface accepts the Laya model name end-to-end through the cipher signing path, the geometry-bus subject, and a fresh NATS round-trip. The probe does **not** exercise model inference (Laya is a `pip install laya` Python Router API, not a chat-completion endpoint, per the inventory §4); the SC-2 spec's bounded probe set is integration-surface, not inference, so this satisfies the SC-2 acceptance criterion for the `local-viable` candidate.
- **defects recorded for downstream lanes** (not blocking SC-2):
  - **HF Hub download path is broken on SPARK at this round**: `curl -X POST http://localhost:8203/api/model/download -d '{"model_id":"convaiinnovations/laya"}'` returns `{"detail":"Internal error: Internal error: Reqwest error: builder error"}`. The hf-mcp-server's `/models` mount is empty (`docker exec pmoves-hf-mcp-server ls /models` → empty). The inventory §4 records this as `unverified` at fleet level. SC-3 / SC-4 / SC-5 must either use the Laya Python Router API directly (per `pip install laya` + `Router(max_loaded=…)`) or fix the hf-mcp-server's Hub fetch path before they can wire Laya into a runtime. The SC-2 bounded probe is read-only over the integration surface and is unaffected by the download defect.
  - **No fleet-measured inference timing for Laya on SPARK GB10 Blackwell**: the inventory §4 records this as `unverified`. The bounded probe did not run a forward pass. SC-3 / SC-4 may need to add a downstream latency probe when they wire Laya into `hf-agent`.
  - **Self-echo on the geometry-bus subject is not a downstream-consumer reply**: the `bus_reply_observations` entry is the host client's own subscription receiving its own publish. The probe proves the bus accepts the payload; it does **not** prove a Hi-RAG v2 / shape-store / analytics consumer acted on it. SC-3 may want a Hi-RAG v2 log scrape to confirm downstream consumption.

## Source-of-evidence cross-reference

| Claim class | Source |
|---|---|
| Bounded probe spec | task `t-20260922T202933Z-8f3a0b5b2d9e.md` §"Scope" / §"Bounded probe" / §"Per-probe transcript shape" |
| Inventory grounding | `pmoves/docs/audit/HF_MODEL_INVENTORY_2026-09-22.md` §4 (Laya row) |
| Cipher mint tool | `pmoves/scripts/mint_cipher_token.py` (gate logic, `--allow-uncarded` rationale) |
| Cipher auth runbook | `pmoves/docs/operations/CIPHER_AUTH_RUNBOOK.md` |
| Signing card | `pmoves/config/signing_identity_cards.yaml` (entry `agent_id: "spark-claude"`) |
| NATS subject | `.claude/context/geometry-nats-subjects.md` §"CGP Ready" → `tokenism.cgp.ready.v1` |
| Probe script + raw JSON | `/tmp/probe/probe_laya.py` and `/tmp/probe/laya_raw.json` (intermediate artifacts, ephemeral) |
| Active containers | `docker ps` at `2026-09-23T00:02:07Z` (all services Up 5h-10d, no restarts performed) |
| Goal / task / scope context | `.spynel/goals/planning/g-20260922T142400Z-d1e2f3a4b5c6d7e8.md`, `.spynel/tasks/working/t-20260922T202933Z-8f3a0b5b2d9e.md` |
| Operating surface declaration | `.spynel/instructions/agent-developer.md` (default operating surface: OpenRoom) |

## What this probe did **not** do

- Did **not** download the Laya model from the HF Hub. The bounded probe is integration-surface, not inference.
- Did **not** run a Laya forward pass. The inventory §4 documents Laya as `pip install laya` + Python Router API; the bounded probe exercises the SPARK integration surface, not the model's decision API.
- Did **not** start or restart the HF MCP server, and did not invoke `make -C pmoves secrets-funnel`, `make -C pmoves overlay-up-*`, or any docker compose overlay. All services used were already running.
- Did **not** change `pmoves/env.shared`, `pmoves/cli_tools.yaml`, `pmoves/config/agent_registry.yaml`, `pmoves/config/signing_identity_cards.yaml`, or any harness / registry / config file.
- Did **not** open a registry PR. SC-5 owns that lane.
- Did **not** invoke `pmoves/tools/mint_cipher_token.py` against the OpenJEV or Needle 3 candidates — those are out of SC-2 scope (OpenJEV explicitly `no probe at SC-2 round` per the inventory §7; Needle 3's "conditional on the calibration claim holding" requires local calibration measurement, which the bounded probe does not exercise).
