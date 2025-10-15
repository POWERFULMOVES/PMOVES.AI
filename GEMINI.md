# Gemini Workspace & Project Next Steps

This document outlines the immediate priorities and next steps for the PMOVES.AI project, as understood from the project's own documentation (`AGENTS.md`, `pmoves/docs/NEXT_STEPS.md`, `pmoves/docs/ROADMAP.md`).

## Current Milestone: M2 - Creator & Publishing

The project is currently focused on completing the **M2 (Creator & Publishing)** milestone.

### Immediate Priorities (from `NEXT_STEPS.md`)

1.  **Finish the M2 Automation Loop**:
    *   Execute the Supabase -> Agent Zero -> Discord activation checklist.
    *   Populate `.env` with Discord webhook credentials and test.
    *   Activate n8n workflows for approval polling and publishing.
    *   Validate Jellyfin integration and metadata propagation.
    *   Log all steps and evidence in `SESSION_IMPLEMENTATION_PLAN.md`.

2.  **Jellyfin Publisher Reliability**:
    *   Expand error handling and reporting.
    *   Backfill historical Jellyfin entries with enriched metadata.

3.  **Graph & Retrieval Enhancements (Kickoff M3)**:
    *   Seed Neo4j with the brand alias dictionary.
    *   Outline relation-extraction passes from captions/notes.
    *   Prepare a parameter sweep plan for the reranker.

4.  **PMOVES.YT High-Priority Lane**:
    *   Design and document a resilient download module.
    *   Specify multipart upload and checksum verification for MinIO.
    *   Define metadata enrichment requirements and schema updates.
    *   Draft the `faster-whisper` GPU migration plan.
    *   Document Gemma integration paths.
    *   Define API hardening, observability, and security tasks.

5.  **Platform Operations & Tooling**:
    *   Draft a Supabase RLS hardening checklist.
    *   Plan optional CLIP + Qwen2-Audio integrations.
    *   Outline a presign notebook walkthrough.

6.  **Grounded Personas & Packs Launch**:
    *   Apply database migrations for grounded personas and geometry support.
    *   Update `.env` with new feature toggles.
    *   Seed baseline YAML manifests for personas and packs.
    *   Wire the retrieval-eval harness as a persona publish gate.
    *   Exercise the creator pipeline end-to-end and document events.
    *   Confirm geometry bus emissions populate the ShapeStore cache.
    *   Draft a CI-oriented pack manifest linter.

### Next Session Focus

*   Implement `media-video` and `media-audio` analysis pipelines.
*   Switch to `faster-whisper` with GPU auto-detect.
*   Enable CLIP embeddings on keyframes.
*   Implement end-to-end n8n flows.
*   Finalize Jellyfin refresh hook and Discord rich embeds.
*   Perform Supabase RLS hardening.
*   Integrate Qwen2-Audio provider.
*   Add Gemma summaries and new endpoints to PMOVES.YT.

## General Guidance (from `AGENTS.md`)

*   **Documentation**: All changes must be accompanied by clear and up-to-date documentation.
*   **Commits & PRs**: Commits should be focused and descriptive. PRs must have context-rich descriptions.
*   **Scope Alignment**: All work should align with the `ROADMAP.md` and `NEXT_STEPS.md`.
*   **Repository Structure**: Core application code is in `pmoves/`. General documentation is in `docs/`.

This file will be used to guide my actions and ensure alignment with the project's goals.
