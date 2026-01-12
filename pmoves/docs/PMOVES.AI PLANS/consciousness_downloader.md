# PMOVES • Consciousness Knowledge Harvest Plan
_Updated: 2025-10-20 (aligns with Supabase CLI + Geometry Bus stack)_

This playbook turns the *Landscape of Consciousness* taxonomy into PMOVES-ready assets that feed CHIT playback, Geometry Bus constellations, Evo Swarm packs, and RAG retrieval pipelines.

---

## 0. Prerequisites
- Supabase CLI runtime configured (`make env-setup`, `make supa-start`)
- Core services running (`make up`, `make up-agents`)
- Optional: n8n (`make up-n8n`) for embedding automation
- PowerShell 7+ (Windows/WSL) with permission to install modules (Selenium)
- Headless Chrome or Chromium available on host

All paths below are relative to the repository root.

---

## 1. Harvest Static Assets
Generate the base directory structure and download static research artifacts.

```bash
make -C pmoves harvest-consciousness
```

This target runs the bash helper, builds processed artifacts, and (if available) applies the Supabase schema automatically.

> To re-run individual helpers:
> - Bash: `bash "pmoves/docs/PMOVES.AI PLANS/consciousness_downloader.sh"`
> - PowerShell: `pwsh -File pmoves/docs/PMOVES.AI PLANS/consciousness_downloader.ps1`

Outputs land under `pmoves/data/consciousness/Constellation-Harvest-Regularization/`:
- `website-mirror/`, `theories/`, `categories/`, `subcategories/`
- `research-papers/` (primary + related papers)
- `data-exports/` (JSON templates)
- `scripts/` (generated automation helpers)

---

## 2. Mirror Dynamic Content
Run the Selenium scraper to capture JavaScript-rendered theory/category pages.

```powershell
pwsh -File pmoves/data/consciousness/Constellation-Harvest-Regularization/scripts/selenium-scraper.ps1
```

The scraper produces `data-exports/discovered-links.json` and refreshed HTML snapshots.

---

## 3. Prepare Embedding Payloads
1. Populate `processed-for-rag/embeddings-ready/` with chunked JSONL files (`consciousness-chunks.jsonl`).
   - Use the provided PowerShell helpers or adapt `pmoves/n8n` flows.
2. Apply the Supabase schema for consciousness datasets. Example (Supabase CLI runtime):
   ```bash
   supabase status --output env > supabase/.tmp_env
   source supabase/.tmp_env
   psql "$${SUPABASE_DB_URL}" -f pmoves/data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/supabase-import/consciousness-schema.sql
   ```
   Adjust the command if you run Postgres via docker-compose (e.g., `docker compose exec postgres psql -U pmoves -d pmoves -f ...`).
3. Import the n8n workflow to push embeddings:
   - `n8n` UI → Workflows → Import → `processed-for-rag/supabase-import/n8n-workflow.json`
   - Bind Hugging Face + Supabase credentials (respect `env.shared` secrets).

---

## 4. Pull Authoritative YouTube Videos
1. Ensure pmoves-yt stack is running (`make -C pmoves up-yt` brings up bgutil-pot-provider + ffmpeg-whisper + pmoves-yt).
2. Run the ingestion helper (supports `--dry-run`):
   ```bash
   make -C pmoves ingest-consciousness-yt ARGS="--max 5"
   ```
   This searches YouTube via yt-dlp using chunk titles, then calls `/yt/ingest` and `/yt/emit` for each match. Results are stored in `processed-for-rag/supabase-import/consciousness-video-sources.json`.
3. Inspect the mapping file and adjust entries if you prefer curated interviews (update `video_id`/`video_url` and rerun to emit geometry again).
4. Verify MinIO now contains the downloaded media/transcripts for Jellyfin and Creator pipelines.

---

## 5. Integrate with Geometry Bus & CHIT
1. Map curated theory rows into CGP packets (new mapper or manual pack builder).
2. Publish via:
   - `make mesh-handshake FILE=pmoves/data/consciousness/.../geometry_payload.json`
   - or Agent Zero: POST to `/events/publish` with `geometry.consciousness.v1`.
3. Validate:
   - `make smoke-geometry`
   - Geometry UI (`make web-geometry`) → jump to newly published constellations.
4. Document packet IDs in `pmoves/docs/PMOVESCHIT/` so CHIT demos can reference the dataset.

---

## 6. Evo Swarm & Retrieval Hooks
- Add consciousness dataset namespaces to Evo Swarm controller defaults (`env.shared`, e.g., `EVOSWARM_CONTENT_NAMESPACES=pmoves.consciousness`).
- Rerun `make up-agents` and verify `geometry.swarm.meta.v1` events include new packs.
- Indexing/testing:
  - `make smoke` (ensures Supabase + Qdrant/Meili ingest reads the new corpus)
  - `make smoke-hirag-v1` or query hi-rag gateway v2 with a consciousness prompt.

---

## 7. Evidence & Documentation
- Log each stage (commands, timestamps, outputs) in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`.
- Archive raw captures under `pmoves/docs/logs/<date>_consciousness_harvest.txt`.
- Update related docs:
  - `pmoves/docs/PMOVESCHIT/PMOVES-CONCHexecution_guide*.md`
  - `pmoves/docs/NEXT_STEPS.md` (mark tasks complete)
  - `pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md` (knowledge sources table)

---

## 8. Follow-on Enhancements
- Automate CGP generation (add mapper to `pmoves/services/common/cgp_mappers.py`).
- Build a `make consciousness-harvest` wrapper target to run steps 1–3.
- Extend n8n flows to notify Agent Zero / Discord when new theories land.
- Consider MinIO storage of media assets for downstream creative automations.

Use this plan as the authoritative reference when onboarding consciousness datasets into PMOVES. Update the document as automation solidifies or new tooling lands.
