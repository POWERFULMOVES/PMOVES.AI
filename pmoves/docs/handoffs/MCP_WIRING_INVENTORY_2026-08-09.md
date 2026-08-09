# MCP wiring audit — Step 1 inventory (4090 → SPARK)

**Date:** 2026-08-09
**From:** 4090-claude (field)
**For:** `MCP_WIRING_AUDIT_SPARK_2026-08-09.md` — this is that handoff's Step 1, done so SPARK starts from a matrix with blockers named rather than a blank page.
**Not a claim.** SPARK still CLAIMs the audit lane; this is input to it.

Verified on disk against `origin/main` unless marked INFERRED.

---

## Two corrections to the parent handoff

### 1. `PMOVES-jcodemunch-mcp` is NOT an n8n MCP

The parent handoff records it as *"n8n MCP (v1.108.64) … needs `N8N_API_URL`/`N8N_API_KEY` … blocked on the n8n owner password reset."* That is a different surface. Verified against upstream `jgravelle/jcodemunch-mcp`:

**jCodeMunch is a code-exploration MCP.** Tree-sitter AST indexing, symbol-level retrieval instead of whole-file reads — 90+ tools including `search_symbols`, `get_symbol_source`, `find_importers`, `get_blast_radius`, `get_call_hierarchy`, `assemble_task_context`, `check_edit_safe`. 70+ languages. Upstream claims ~96% token reduction (27.9×).

**It needs no secrets at all.** `pip install jcodemunch-mcp` (or `uvx`), local-first, index at `~/.code-index/`. No API key for core functionality.

So it is **not** blocked on the n8n password — it is one of the cheapest wires available. The n8n credential story in the parent handoff is real, but belongs to the n8n lane (below), not to this fork.

This matters beyond bookkeeping: jcodemunch + a consumer-side MCP client is *symbol-level retrieval without loading files*. That is the "capability lives in the field, not the model" pattern applied to code reading — a small model asks for a symbol instead of ingesting a repo.

### 2. `flute-gateway/mcp_bridge.py` is mounted, and it is authenticated

An earlier pass recorded it as *"unwired and dead code — `create_mcp_router()` never imported or mounted."* Not so. `origin/main:pmoves/services/flute-gateway/main.py:617-625`:

```python
from mcp_bridge import create_mcp_router  # noqa: E402

app.include_router(
    create_mcp_router(
        get_provider=lambda: ultimate_tts_provider,
        get_nats_client=lambda: nats_client,
    ),
    dependencies=[Depends(verify_api_key)],
)
```

Mounted **and** gated by `verify_api_key`. The auth arrived via PR #2491's fix commit. Note the gating only works because `create_mcp_router` returns a real `APIRouter` — `include_router(dependencies=…)` does **not** apply to a Starlette `Mount`, so this was a plausible silent no-op that happens to be correct.

It is still absent from every registration surface, so it is **live but unregistered**, not dead.

---

## Matrix

| Surface | Transport | Auth | Registered | Status |
|---|---|---|---|---|
| `pmoves-cipher` `:8105` | SSE `/mcp/sse` | Bearer `CIPHER_API_TOKEN` | `.claude/mcp.json` ✔ · `mcp_inventory.json` ✔ | **wired + working** |
| `agent-zero` `:8080/mcp` | http | none noted | both ✔ | **wired** |
| `pmoves-nats-mcp` | stdio | `NATS_URL` today | both ✔ | **wired**; PR #2496 adds CORE `.creds` + CHIT-signed publish |
| `pmoves-hirag-mcp` | stdio | none (proxies HIRAG_URL) | **absent from both** | **UNWIRED — cheapest fix in the audit** |
| Ultimate-TTS Gradio MCP | Gradio built-in SSE | none | absent | **UNWIRED but ALREADY LIVE** — `GRADIO_MCP_SERVER` defaults `"true"` |
| `flute-gateway/mcp_bridge.py` | hand-rolled SSE, no SDK | `verify_api_key` ✔ | absent | **live, unregistered** (see correction 2) |
| `pmoves-e2b-mcp-server` | stdio | `E2B_API_KEY` | absent | **UNWIRED** — Dockerfile exists, no compose service |
| `PMOVES-jcodemunch-mcp` | stdio (`uvx`) | **none** | absent | **UNWIRED, no secrets needed** (see correction 1) |
| `pmoves-cipher-mcp` | stdio (legacy) | n/a | disabled entry, annotated | **intentionally retired** — leave it |
| `PMOVES-Archon` | consumer-side only | n/a | `disabled: true` in inventory | **correctly disabled** — Archon consumes MCP per workflow node; it is not a fleet surface |
| `PMOVES-Pipecat` `MCPClient` | consumer-side | n/a | n/a | **unused** — zero hits in `flute_pipecat/` |
| DoX nested forks (×3) | unknown | unknown | absent | **parked** — subtree has no compose reference; needs an architecture decision first |
| `PMOVES-BotZ-gateway` (.NET) | n/a | n/a | absent | Microsoft's MCP Gateway product vendored whole. **Not** `pmoves/services/botz-gateway`. Inventory only |
| `n8n-agent` (`config/mcp/n8n-agent.yaml`) | stdio via `docker exec` | `N8N_API_KEY` | config exists | **describes a container that does not exist** in any compose file |

---

## Registration surfaces — there are three, and they disagree

1. **`.claude/mcp.json`** — 13 entries. Note Claude Code does not auto-read this; it needs `--mcp-config`, so presence here is not the same as callable.
2. **`pmoves/config/mcp_inventory.json`** — the canonical **generator source**; `pmoves/tools/mcp_config_generator.py` emits client-native configs from it. **This is the one that is out of sync** — hirag, e2b, jcodemunch, flute-gateway and gradio-tts are missing from it too, not just from `.claude/mcp.json`.
3. **`pmoves/config/mcp/*.yaml`** — a looser descriptor layer (`n8n.yaml` literally says *"Install the pmoves n8n MCP adaptor (todo)"*). Not consumed by the generator as far as this pass could tell.

**Recommendation for SPARK:** make `.claude/mcp.json` generated from `mcp_inventory.json` rather than maintained beside it. Two hand-maintained lists of the same thing is the drift pattern this repo has been paying for all week — four copies of cleanup logic, two `claude-pmoves.sh`, a deny-list duplicating `patterns.yaml`. Same shape.

---

## Three unrelated things are called "MCP" here

Anyone asked to "wire the MCP" has three wrong answers available:

- **(a) Real MCP servers** exposing tools — cipher, agent-zero, nats-mcp, hirag, e2b, jcodemunch, flute-bridge, Gradio-TTS.
- **(b) Consumer-side clients** — pipecat's `MCPClient` and Archon's per-node `mcp:` config. These *call* MCP servers; they are not surfaces to register.
- **(c) The "GRADIO MCP" rail** in `pmoves/configs/tac_trees/voice-engines-integration.tac.yaml` — a `gradio_client` **test harness**. Not the protocol at all.

Any rebuilt TAC or wiring doc should disambiguate these explicitly.

---

## Ranked: cheapest to wire first

1. **`pmoves-hirag-mcp`** — populated, server complete with tests, README ships copy-paste registration JSON, defaults already point at `:8086`/`:8087`. **Zero new code, zero secrets.**
2. **Ultimate-TTS Gradio MCP** — already running with MCP enabled by default. One `.claude/mcp.json` SSE entry. No code, no secret.
3. **`PMOVES-jcodemunch-mcp`** — `uvx jcodemunch-mcp` + one entry. No secrets. Confirm first whether the fork exists for a hardening reason or whether upstream suffices.
4. **`pmoves-e2b-mcp-server`** — one secrets-funnel entry (`E2B_API_KEY`) + one stdio entry.
5. **`flute-gateway` bridge** — already live and authed; just needs registering. Low risk now that the auth landed.
6. **n8n lane** — **two independent blockers**: `make -C pmoves n8n-bootstrap` is operator-gated on an owner password reset, *and* `n8n-agent.yaml`'s container does not exist in compose. Neither is SPARK's to clear alone.
7. **DoX subtree + `PMOVES-BotZ-gateway`** — architecture decision before any wiring effort.

Items 1–3 are a single sitting and need nothing from the operator.

---

## Open questions for SPARK

- Are `pmoves_5090_web` (in `mcp_inventory.json`) and `pmoves-ai-profile.yaml` the same Docker MCP Toolkit profile under two names, or two divergent ones?
- What actually serves `BOTZ_MCP_URL:8102`, which the deployed `pmoves/services/botz-gateway` consumes? Not located in this pass, and **not** the .NET `PMOVES-BotZ-gateway`.
- True upstream of DoX's `external/PMOVES-n8n-mcp` — submodule uninitialized, attribution unverified. Do not trust a guess here.

**Not verified this pass:** PR #2496's auth changes against current code (in-flight); the Gradio MCP SSE path against a live container; whether `python/pmoves_mcp/` in Archon is dead post-TS-rewrite.
