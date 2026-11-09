# HF Seat Curator + Research Watch (SPARK, 24/7) — Lane Spec

> Cold-read spec. Authored on 5090 (2026-08-04) from operator direction; the
> executing node is SPARK. Companion to the model-seat mechanism shipped in
> PR #2376 (jellyfin-ai `AUDIO_MODEL_URL`/`AUDIO_MODEL_ID`).

## Operator seeds (verbatim, seed-don't-prune)

> "needs to run on Spark node for 24/7 also hf agent local so is first looking
> for new model for seat and hermes perfect candidate cus 3 local models to run
> and allow spark to experiment test what discoverai and other research groups
> are trying and work on my boy Richard Aragons new dendrite setup he is who i
> got math from to do pbnj so his chennel is one to have monitored i actually
> want agents to assist with drafting posts also my posts on his and other
> channels documents my ideation and building of theory or hypothesis as he
> reminded my of something i was toying around with in my head for a while and
> clicked like that video when max tegmark is describing when models grok"

## TL;DR

Three coupled loops, all resident on SPARK, all **propose-only** into
DARKXSIDE's room (never auto-apply):

1. **Seat Curator** — HF agent (local) scans the Hub for new multi-modal /
   audio-native models, evaluates candidates locally on SPARK, and files a
   swap proposal per seat.
2. **Research Watch** — channel monitoring (Richard Aragon, Discover AI,
   other research groups) through the now-unblocked YT pipeline →
   transcription → notebook ingestion; SPARK reproduces/experiments with
   what the channels are trying (first target: Aragon's dendrite setup).
3. **Post Drafting + Ideation Capture** — agents draft replies/comments for
   the operator's channels; the operator's own posts are ARCHIVED as
   first-class theory documentation (hypothesis-building corpus).

## Why Hermes, why SPARK

- **hermes-agent** (NousResearch HERMES integration, already in the agent
  registry) is the operator's named candidate: it runs **3 local models**,
  which maps 1:1 onto the three loops (discovery/eval, research digest,
  drafting) without cloud dependency — the "hf agent local" requirement.
- **SPARK** is the 24/7 node with headroom to *test* candidates, not just
  list them: pull a GGUF, run the seat's eval probe, measure, dispose.
  Workstation nodes (5090/4090) sleep; SPARK doesn't.

## Component 1 — Seat Curator

- **Seat registry** (the contract): every seat is (consumer, URL var, ID var,
  modality, eval probe). Initial seats:
  | Seat | Vars | Current occupant |
  |---|---|---|
  | jellyfin media-analysis | `AUDIO_MODEL_URL` / `AUDIO_MODEL_ID` | `qwen3-vl:8b` (native Ollama) |
  | transcribe-and-fetch diarization | provider-agnostic cloud_api / registry | pyannote (placeholder — memory canon) |
  | embeddings | `qwen3-embedding` family | `qwen3-embedding:8b` (2560d ledger note applies) |
- **Loop**: hf-mcp (paper_search + hub search, sorted by lastModified) →
  filter by modality/license/quant availability → `ollama pull hf.co/<repo>:<quant>`
  on SPARK → run the seat's eval probe (per-seat: e.g. media-analysis =
  caption+QA on 3 fixture clips; diarization = DER on a fixture) → write
  **proposal artifact** (candidate, evidence, deltas vs occupant, rollback =
  one env var) → drop into `rooms/darkxside/inbox/` (JuiceFS gateway) →
  pub-gate note in the DARKXSIDE notebook with an approve checkbox.
- **Apply step is operator-gated**: on approval, the swap is
  `AUDIO_MODEL_ID=<new>` (+ pull on the target node). Nothing auto-applies.

## Component 2 — Research Watch

- **channel_monitoring seeds** (table `pmoves.channel_monitoring`, live):
  - Richard Aragon — `UCyqdVXH6EMYjxF5AKPg4NLw` — priority 1. Lineage note:
    the operator's PBnJ math derives from Aragon's work; his **new dendrite
    setup** is the first reproduction target on SPARK. Substack
    (`richardaragon.substack.com`) is a sibling source (Geometry Beneath the
    Weights / Hidden Geometry of Numbers).
  - Discover AI (`@code4AI`, formerly code_your_own_AI) — priority 2 —
    "what discoverai and other research groups are trying." (Handle needs
    ID resolution on first crawl.)
  - Watchlist is operator-extendable; additions are a one-row insert.
- **Flow**: channel-monitor discovers → yt pipeline (cookies + deno + PO
  provider, all live as of 2026-08-03) downloads → transcribe-and-fetch →
  Open Notebook / Hi-RAG ingestion → Hermes digest per video with a
  "reproducible on SPARK?" verdict → experiments queue.
- **Dendrite lane**: standing work item — study + reproduce Aragon's
  dendrite architecture on SPARK; findings artifacts to the room; connects
  to the GEOMETRY_BUS/PBnJ math lineage.

## Component 3 — Post Drafting + Ideation Capture

- Agents draft comment/reply candidates for the operator's posts on watched
  channels (draft → room inbox → operator edits/posts; agents NEVER post
  directly — posting is an outward-facing act, operator-only).
- **Ideation capture**: the operator's comments/posts on Aragon's and other
  channels are primary documentation of theory/hypothesis development — the
  watch loop archives them (comment text + video context + date) into the
  notebook corpus. Seed context: Aragon's video reminded the operator of a
  long-gestating idea that "clicked like that video when Max Tegmark is
  describing when models grok" — the grokking-moment framing is itself part
  of the theory corpus.

## Out of scope (this spec)

- Auto-applying seat swaps (deliberately excluded — pub-gate only).
- Cross-node NATS mesh plumbing for SPARK→5090 proposals (existing JuiceFS
  gateway + room inbox suffices to start).
- The dendrite reproduction itself (it gets its own findings docs).

## Next steps

1. SPARK: provision hermes-agent with its 3 local models + hf-mcp access
   (SPARK/4090 lane — this spec is the handoff).
2. 5090 (done with this spec): channel_monitoring seeded (Aragon, Discover
   AI); seat mechanism live (PR #2376); room inbox operational.
3. First curated cycle: Hermes proposes either (a) a media-analysis seat
   candidate or (b) the first Aragon digest — whichever lands first proves
   the loop.

**Three-body:** delivery = SPARK/Hermes (loops) + 5090 (this spec, seeds);
control = DARKXSIDE (every proposal gate); memory = this spec + room
artifacts + notebook pub-gate notes.
