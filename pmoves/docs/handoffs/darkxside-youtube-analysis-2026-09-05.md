# Handoff: DARKXSIDE YouTube analysis (2026-09-05)

**Lane owner (proposed):** main A0 (`:8080`) dispatching the PMOVES.YT pipeline; Archon for the mint if a dedicated analyst persona is needed. **Raised by:** 5090-CLAUDE.

## What exists (all healthy on the 5090 today)

`pmoves-yt` (:8077), `channel-monitor` (:8097), `transcribe-backend` (:8074) plus frontend, `yt-cookie-writer` / `yt-cookie-refresher` (:8115). Skills: `yt:add-channel`, `yt:ingest-video`, `yt:check-now`, `yt:pending`, `yt:status`, `search:ingest-content`, `search:hirag`. Hi-RAG v2 (Qdrant + Neo4j) is live and now authenticates to Neo4j. Media map: transcripts flow to Open Notebook and on to the Neo4j mindmap; item 4 of `MEDIA_PIPELINE_INTEGRATION_MAP.md` ("wire Neo4j graph writes from transcript segments") is still unbuilt.

## Ask

1. Register the DARKXSIDE channel(s) via `yt:add-channel`. The operator supplies the handle in-session; no cookies in chat, the cookie writer is the Known Road.
2. Ingest the back-catalog; transcribe; land in Open Notebook workspace `darkxside` and in Hi-RAG.
3. Analysis passes over the transcripts: recurring themes, voice and prosody markers (the `shift-from-bpm` BPM vocabulary), CHIT-map anchors, publish-gate candidates. Output as Notebook pages plus Neo4j `MediaRef` and `Anchor` nodes so the mindmap grows from real content rather than the fixture.
4. Provenance: every derived node carries the video id and timestamp; nothing publishes past the room's manual `publish_gate`.

## Gates

Egress IP check first: a KVM exit node presents a datacenter IP and trips the YouTube bot gate. Cookies stay funnel-fed.

## Definition of done

`yt:status` shows the channel monitored with N ingested; the Notebook workspace has per-video pages; the Neo4j `MediaRef` count grows past the 3 fixture nodes; one analysis page per theme, signed via `sign-trail`.
