# Cole Medin "OFFICIAL Archon Guide" — Learning Map Against PMOVES-Archon

Source: `DMXyDpnzNpY` (23:18, transcribed 2026-09-13 on SPARK GB10 — 283 segments, cookieless
download path, CUDA-13 ffmpeg-whisper). Transcript: `/tmp/cole_medin_transcript.txt` (local).

## What the guide teaches (canonical usage)

| Concept | Guide's framing | PMOVES-Archon status (live :3090, v0.6.0) |
|---|---|---|
| Archon = UI + MCP server | One tool managing knowledge, projects, tasks; MCP exposes the same surface to any coding assistant | Live; A0 consumes Archon via REST (`A0_MCP_ARCHON_ENDPOINT=http://archon-server:8051`) — MCP-first framing matches Cole's intended surface |
| Knowledge Base | Curate docs per project; sources ingest into a searchable KB | `cole-medin-knowledge-base` repo ingestion via llms.txt-first path is the mapped lane (see below) |
| llms.txt ingestion | llms.txt as the entrypoint for crawling a docs site | Confirmed as the canonical ingest path for the KB repo; prefer llms.txt over sitemap for this corpus |
| Postgres + pgvector RAG | "Postgres as the underlying database" with vector search under the hood | PMOVES runs Archon against the shared Supabase Postgres; keep pgvector extension parity when creating Archon KBs |
| Providers | Configure AI providers (OpenRouter et al.) in settings | PMOVES doctrine: model access routes through TensorZero (local-first fabric), not direct provider keys — diverges from the guide deliberately |
| Kanban task board | Human+AI shared task management | Unmapped — optional; PMOVES task surface is the register/AGNOTE system, not Archon boards |

## Deltas worth adopting

1. **llms.txt-first ingestion is now the default posture** for any docs corpus we hand Archon —
   it is what the author tests against and it degrades gracefully to per-page crawl.
2. **KB-per-project scoping**: Cole scopes each KB to one project/library. Our single shared KB
   approach should move toward per-project KBs as Archon adoption grows (cleaner MCP search results).
3. **MCP parity check**: anything the UI can do should be reachable over MCP — validate our
   A0→Archon bridge against the guide's task/KB workflows as a conformance set.

## Deltas we reject (recorded, not accidental)

- **Direct provider keys in Archon settings** — violates the model-fabric contract
  (`pmoves/docs/MODEL_FABRIC_CONTRACT.md`); Archon gets models via TensorZero.
- **Archon as the task system of record** — the claim register (AGNOTE4482PHI.t1.md) is the
  PMOVES system of record; Archon boards are downstream views at most.

## Provenance

- Video: https://www.youtube.com/watch?v=DMXyDpnzNpY
- Author: Cole Medin (coleam00) — Archon's author
- Transcript pipeline: pmoves-yt :8077 → yt-dlp cookieless (valid empty Netscape header) →
  MinIO (funnel-canonical creds) → ffmpeg-whisper :8078 (arm64 CUDA-13 image, PR #3049)
