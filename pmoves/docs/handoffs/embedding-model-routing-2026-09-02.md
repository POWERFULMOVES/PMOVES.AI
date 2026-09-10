# Handoff — embedding model routing: one hardcoded name, many data types

**From:** 4090-CLAUDE (PMOVES-4090)
**To:** 4090-CLAW
**Date:** 2026-09-02
**Status:** design brief — no code change proposed yet
**Doubles as:** the `handoff:` artifact for `KNOWN_ROAD=compose:handoff:embedding-model-routing-2026-09-02.md`

---

## Why this exists

Founder directive, 2026-09-02:

> we have container with gpu support we also have huggingface integration there
> are embeddings for diff typs of data medical for example so we might use diff
> model

One `EMBEDDING_MODEL` was always going to be the wrong shape. This brief records
what is measured, names the seam that has to open, and leaves the design open
rather than guessing at it.

## What is measured (2026-09-02, PMOVES-4090)

The Cipher embedding path was dead for an unknown period and reported success
the whole time. Three independent causes, each necessary, none sufficient:

1. `tensorzero.toml` asked for `env::MINIMAX_TOKEN_PLAN_API_KEY`, a name the
   pipeline never supplied. TensorZero fails its **entire** config load on one
   missing provider key, so the gateway crash-looped every 60s and no routing of
   any kind worked.
2. `tensorzero.toml:770` asked Ollama for `qwen3-embedding:4b`; Ollama had only
   `:8b`. Pulled `4b`. (Verified against this commit: `:770` is the
   `qwen3_embedding_4b_local` provider's `model_name`; `:793` is `bge-m3`.
   A brief that routes protected Compose work has to point at the line the
   implementer will actually edit.)
3. **The one that survived the first two fixes.** Cipher budgets
   `AbortSignal.timeout(10000)` for the embed call (`embedding.ts:73`, and the
   same for the Ollama fallback at `:96`). A **warm** call through TensorZero
   measured **7206 ms** — 2.8 s of headroom. Cold, Ollama must first load a 4B
   model, which exceeds the budget. The fallback then hits the *same model on
   the same host*, so it times out identically. Both print `unreachable`, which
   means SLOW here, not disconnected: HTTP 200 was verified from inside
   `pmoves-cipher-api-1` minutes before those lines were written.

Proof of (3): pinning the model resident (`keep_alive: -1`) made the very next
store return `embedded: true`, first time. `ensureCollection()` then created
`pmoves_cipher_memory` with `dense 2560d Cosine` + `sparse bm25`. **BM25 had
never been reachable** — it is created only after a first successful embed.

### Failure mode worth internalising

When `embed()` returns null, store and search fall through to
`lexicalFallback()` (`memory-routes.ts:223-246`), which **ignores the query text
entirely** and filters only on `agentId` / `category`. The query
`"zzzqqqxyzzy nonexistent unrelated term xylophone marmalade"` returned five
genuine, confidently-ordered PMOVES memories. Because every row is a real
memory, nothing looks wrong. **Treat any Cipher search as unranked text-match
until a fresh store returns `embedded: true`.**

## The seam that has to open

`EMBEDDING_MODEL` is **hardcoded** — no `${VAR:-default}`:

- `pmoves/docker-compose.yml:3689`
- `pmoves/docker-compose.agents.yml:876`

Both are `readOnlyPaths`. Any multi-model work needs
`KNOWN_ROAD=compose:handoff:embedding-model-routing-2026-09-02.md` (this file).

Note also `docker-compose.yml:3039` and `docker-compose.agents.yml:724` carry
`EMBEDDING_MODEL=${EMBEDDING_MODEL:-all-MiniLM-L6-v2}` for a *different*
service — so two different defaults for the same variable name already coexist
in one compose file. Whatever shape is chosen must not make that worse.

## Open design questions — for 4090-CLAW, not decided here

1. **Dedicated GPU embedding container vs host Ollama.** The current path is
   Cipher → TensorZero → `host.docker.internal:11434` (Ollama on the host, not a
   container). What already exists that this should build on, rather than a
   new service?

   **A container does not by itself remove the cold load.** An earlier draft
   said it did. An Ollama-backed container lazy-loads on first request and
   unloads again on the default `keep_alive` idle timeout, so it reproduces
   cause (3) above after every restart, eviction, or idle gap — the same
   failure, now behind a service boundary that makes it harder to see. What
   actually removes it is a **residency guarantee**, and the option chosen
   has to state which one it provides:

   - load at startup and never evict (`keep_alive: -1` plus a warmup call on
     boot — this is the lever already proven here: pinning the model resident
     made the very next store return `embedded: true` first time), **or**
   - a server whose model is resident by construction rather than by policy
     (TEI, vLLM, Infinity all load at startup and do not evict), **or**
   - a timeout large enough to absorb a cold load.

   Note the budget is tight even when warm: 7206 ms measured against Cipher's
   10 s, so 2.8 s of headroom. Residency is necessary; on this evidence it may
   not be sufficient, and the timeout deserves revisiting either way.
2. **Per-data-type models.** Medical, code, audio, and general text want
   different embedding models. Does the selection live in Cipher (per
   `category`?), in TensorZero routing, or in the caller? Note
   `tensorzero.toml` already declares **eleven** embedding models — the
   routing vocabulary exists; nothing selects between them at runtime.
   Counted at this commit:

   - **five local**, all Ollama on `host.docker.internal:11434`:
     `qwen3_embedding_4b_local`, `qwen3_embedding_8b_local`,
     `gemma_embed_local`, `bge_m3_local`, `archon_nomic_embed_local`
   - **six remote**: `archon_bge_large_together`, `archon_e5_large_together`,
     `together_embedding` (Together), `openai_text_embedding_small` (OpenAI),
     `openrouter_embedding` (OpenRouter), `venice_embedding` (Venice)

   An earlier draft said five and listed only the local ones. That matters
   here specifically: this inventory is the basis for deciding whether
   existing routing can be reused, and under-counting it argues for building
   vocabulary that already exists. The remote routes also carry their own
   dimensions and their own key requirements, both of which bear on question
   3 below.
3. **Dimension is not free.** The Qdrant collection is created at the dimension
   of whatever model embedded first (`2560` today, from `EMBEDDING_DIM`).
   Different models mean different dimensions, which means **separate
   collections or named vectors** — not a drop-in swap. Decide this before
   anything is repointed.
4. **HuggingFace integration.** The `huggingface-skills` plugin pack is enabled
   and `hf_whoami` authenticates as `DARKXSIDE`. Licence gate applies:
   Apache/MIT/BSD/CC-BY only, never CC-BY-NC — check before adopting any
   embedding model from the Hub.

## Do not repeat these

Four hypotheses were measured and killed while finding cause (3). Recorded so
nobody re-runs them:

- **Qdrant auth header form.** `embedding.ts:117` sends
  `Authorization: Bearer`; this Qdrant accepts **both** that and `api-key`,
  both 200. Not a bug.
- **Qdrant unreachable.** 200 using Cipher's own 43-char key.
- **`EMBEDDING_DIM` mismatch.** 2560 configured, 2560 returned. Correct.
- **Missing collection as a cause.** It is a *symptom* — `ensureCollection()`
  creates it on the first successful embed.

## Still open

- `keep_alive: -1` is a **runtime pin that dies with the Ollama process.** It is
  a workaround, not a road. Two real options: `OLLAMA_KEEP_ALIVE` on the host
  Ollama service, or raise/parameterise the 10 s budget in the `Pmoves-cipher`
  fork. A 7.2 s warm call against a 10 s budget has too little margin either
  way — and if a GPU embedding container lands, both become moot.
- **Every memory written before 2026-09-02T16:50 has no vector.** Fixing the
  embedder does not retroactively embed them. Until a backfill runs, semantic
  recall covers new writes only and everything older is reachable solely through
  the query-ignoring lexical path. **This is the highest-value follow-up** — the
  corpus is the fleet's memory.

## Related

- Cipher memories `bw9HL_fwTVPn` (root cause + killed hypotheses),
  `iip3aA8ZRqfP` (env shadowing). Both `embedded: true`, so they are
  semantically retrievable; older records are not.
- PRs #2881 (registry length), #2882 (env shadow detection), #2883 (MiniMax TP
  key is not an alias).
