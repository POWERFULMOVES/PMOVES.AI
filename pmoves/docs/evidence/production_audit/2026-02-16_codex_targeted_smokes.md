# Production Audit Evidence — 2026-02-16 (Codex targeted gates)

Branch: codex/layered-local-prod-audit
Commit HEAD: 3ba8cd9d
Timestamp (UTC): 2026-02-16 07:43:01

## Preflight
Command: make -C pmoves preflight
```text
make: Entering directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'

== PMOVES Environment Check ==
CWD: C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves
OS:  Microsoft Windows 11 Pro
PS:  7.5.4

Commands:
[OK] conda          conda 25.11.1
[OK] docker         Docker version 29.2.0, build 0b9d198
[OK] git            git version 2.50.1.windows.1
[OK] make           GNU Make 4.4.1
[OK] node           v22.17.1
[OK] npm            
[OK] pip            
[--] poetry         
[OK] python         Python 3.13.5
[OK] python3        Python was not found; run without arguments to install from the Microsoft Store, or disable this shortcut from Settings > Apps > Advanced app settings > App execution aliases.
[OK] rg             ripgrep 14.1.1 (rev 4649aa9700)
[OK] uv             uv 0.8.4 (e176e1714 2025-07-30)
[OK] compose        Docker Compose version v5.0.2

Repo shape:
has_comfyui:   False
has_contracts: True
has_datasets:  True
has_docs:      True
has_n8n:       True
has_neo4j:     True
has_schemas:   False
has_services:  True
has_supabase:  True

Contracts:
contracts/topics.json: valid
topics keys: topics, v

Ports:
3000   free
6333   free
7474   free
7700   free
8084   free
8085   free
8087   free
8088   free

.env status:
.env present:       False
.env.example:       True
Missing keys (present in .env.example but not in .env):
- AGENT_ZERO_BASE_URL
- AGENT_ZERO_EVENTS_TOKEN
- ALLOWED_BUCKETS
- AUTOLINK_INTERVAL_SEC
- AWS_DEFAULT_REGION
- CHANNEL_MONITOR_CONFIG_PATH
- CHANNEL_MONITOR_DATABASE_URL
- CHANNEL_MONITOR_NAMESPACE
- CHANNEL_MONITOR_QUEUE_URL
- CHANNEL_MONITOR_SECRET
- CHANNEL_MONITOR_STATUS_SECRET
- CHANNEL_MONITOR_STATUS_URL
- CHIT_CLIP_MODEL
- CHIT_CODEBOOK_PATH
- CHIT_DECODE_AUDIO
- CHIT_DECODE_IMAGE
- CHIT_DECODE_TEXT
- CHIT_DECRYPT_ANCHORS
- CHIT_PASSPHRASE
- CHIT_PERSIST_DB
- CHIT_REQUIRE_SIGNATURE
- CHIT_T5_MODEL
- CLAUDE_SESSION_CHANNEL_ID
- CLOUDFLARE_ACCOUNT_ID
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_LLM_MODEL
- DISCORD_AVATAR_URL
- DISCORD_BOT_TOKEN
- DISCORD_SUBJECTS
- DISCORD_USERNAME
- DISCORD_WEBHOOK_URL
- DISCORD_WEBHOOK_USERNAME
- ENTITY_CACHE_MAX
- ENTITY_CACHE_TTL
- EVAL_HTTP_PORT
- EXTERNAL_MEILI
- EXTERNAL_NEO4J
- EXTERNAL_QDRANT
- EXTERNAL_SUPABASE
- EXTRACT_PUBLISH_TOKEN
- EXTRACT_PUBLISH_URL
- EXTRACT_WORKER_URL
- FFW_URL
- FRAME_BUCKET
- GEMINI_API_KEY
- GEMINI_MODEL
- GOTRUE_SITE_URL
- GRAPH_BOOST
- HF_API_KEY
- HF_EMBED_MODEL
- HF_GEMMA_MODEL
- HF_TOKEN
- HF_USE_GPU
- HIRAG_HTTP_PORT
- HIRAG_RERANK_ENABLED
- HIRAG_URL
- INDEXER_NAMESPACE
- JELLYFIN_API_KEY
- JELLYFIN_API_URL
- JELLYFIN_AUTOLINK
- JELLYFIN_LIBRARY_ID
- JELLYFIN_PUBLIC_BASE_URL
- JELLYFIN_PUBLISHED_URL
- JELLYFIN_URL
- JELLYFIN_USER_ID
- LANGEXTRACT_FEEDBACK_METRIC
- LANGEXTRACT_FEEDBACK_TOKEN
- LANGEXTRACT_FEEDBACK_URL
- LANGEXTRACT_PROVIDER
- LANGEXTRACT_REQUEST_ID
- LANGEXTRACT_URL
- MEILI_MASTER_KEY
- MEILI_URL
- MINIO_ACCESS_KEY
- MINIO_BUCKET
- MINIO_ENDPOINT
- MINIO_SECRET_KEY
- MINIO_SECURE
- N8N_RUNNERS_AUTH_TOKEN
- NATS_URL
- NEO4J_DICT_LIMIT
- NEO4J_DICT_REFRESH_SEC
- NEO4J_PASSWORD
- NEO4J_URL
- NEO4J_USER
- NEXT_PUBLIC_SUPABASE_ANON_KEY
- NEXT_PUBLIC_SUPABASE_AUTH_CALLBACK_URL
- NEXT_PUBLIC_SUPABASE_OAUTH_ENABLED
- NEXT_PUBLIC_SUPABASE_PASSWORD_AUTH_ENABLED
- NEXT_PUBLIC_SUPABASE_URL
- NOTEBOOK_SYNC_DB_PATH
- NOTEBOOK_SYNC_INTERVAL_SECONDS
- NOTEBOOK_SYNC_NAMESPACE
- OLLAMA_EMBED_MODEL
- OLLAMA_URL
- OPEN_NOTEBOOK_API_TOKEN
- OPEN_NOTEBOOK_API_URL
- OPENAI_API_BASE
- OPENAI_API_KEY
- OPENAI_COMPAT_API_KEY
- OPENAI_COMPAT_BASE_URL
- OPENAI_COMPAT_EMBED_MODEL
- OPENAI_MODEL
- PDF_DEFAULT_BUCKET
- PDF_DEFAULT_NAMESPACE
- PDF_INGEST_EXTRACT_URL
- PDF_MAX_PAGES
- PGDATABASE
- PGHOST
- PGPASSWORD
- PGPORT
- PGRST_DB_ANON_ROLE
- PGRST_DB_SCHEMA
- PGUSER
- POSTGRES_DB
- POSTGRES_PASSWORD
- POSTGRES_USER
- PRESIGN_SHARED_SECRET
- PUBLISHER_NOTIFY_DISCORD_WEBHOOK
- PUBLISHER_REFRESH_ON_PUBLISH
- QDRANT_COLLECTION
- QDRANT_URL
- RENDER_AUTO_APPROVE
- RENDER_WEBHOOK_SHARED_SECRET
- RERANK_ENABLE
- RERANK_K
- RERANK_MODEL
- RERANK_TOPN
- SENTENCE_MODEL
- SUPA_REST_INTERNAL_URL
- SUPA_REST_URL
- SUPABASE_ANON_KEY
- SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID
- SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET
- SUPABASE_JWT_SECRET
- SUPABASE_PUBLIC_STORAGE_BASE
- SUPABASE_REALTIME_SECRET
- SUPABASE_REST_URL
- SUPABASE_SERVICE_ROLE_KEY
- SUPABASE_STORAGE_URL
- TAILSCALE_ADMIN_ONLY
- TAILSCALE_CIDRS
- TAILSCALE_ONLY
- TENSORZERO_API_KEY
- TENSORZERO_BASE_URL
- TENSORZERO_LARGE_MODEL
- TENSORZERO_PG_DB
- TENSORZERO_PG_PASSWORD
- TENSORZERO_PG_USER
- TENSORZERO_SMALL_MODEL
- USE_MEILI
- YT_ARCHIVE_DIR
- YT_BUCKET
- YT_CONCURRENCY
- YT_DOWNLOAD_ARCHIVE
- YT_ENABLE_DOWNLOAD_ARCHIVE
- YT_GEMMA_MODEL
- YT_INDEX_LEXICAL
- YT_PLAYLIST_MAX
- YT_POSTPROCESSORS_JSON
- YT_RATE_LIMIT
- YT_SEG_AUTOTUNE
- YT_SEG_GAP_THRESH
- YT_SEG_MAX_CHARS
- YT_SEG_MAX_DUR
- YT_SEG_MIN_CHARS
- YT_SEG_TARGET_DUR
- YT_SUBTITLE_AUTO
- YT_SUBTITLE_LANGS
- YT_SUMMARY_PROVIDER
- YT_WRITE_INFO_JSON
Note: jq is recommended for Makefile smoke tests.
events_to_cgp.py:   present
\nDone.
PASS: submodule integrity check passed
  - gitlinks mapped (normalized): 48
  - uninitialized: 0
  - drifted: 0
  - conflicts: 0
runner-check: repo=POWERFULMOVES/PMOVES.AI
runner-check: required groups:
  - self-hosted, vps
  - ai-lab, gpu, self-hosted
runner-check: discovered runners:
  - pmoves-ai-lab-runner: online/idle [Linux,X64,ai-lab,gpu,self-hosted]
  - pmoves-vps-runner: online/idle [Linux,X64,self-hosted,vps]
OK: self-hosted, vps -> pmoves-vps-runner
OK: ai-lab, gpu, self-hosted -> pmoves-ai-lab-runner
runner-check: all required runner lanes available.
make: Leaving directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
```
Exit code: 2

## Flight Check
Command: make -C pmoves flight-check
```text
make: Entering directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
+-----------------------------------------------------------------------------+
| PMOVES: SYSTEMS CHECK                                                       |
+-----------------------------------------------------------------------------+
> PMOVES initial diagnostic boot sequence
+-----------------------------------------------------------------------------+
| quick scan                                                                  |
+-----------------------------------------------------------------------------+
{
  "cwd": "C:\\Users\\russe\\Documents\\GitHub\\PMOVES.AI\\pmoves",
  "tools": {
    "docker": true,
    "git": true,
    "node": true,
    "npm": false,
    "python": true,
    "uv": true,
    "jq": false,
    "rg": true,
    "make": true
  },
  "compose": true,
  "ports": {
    "3000": "free",
    "4222": "free",
    "5432": "free",
    "6333": "free",
    "7474": "free",
    "7687": "free",
    "7700": "free",
    "8077": "free",
    "8078": "free",
    "8079": "free",
    "8080": "LISTENING",
    "8082": "free",
    "8083": "free",
    "8084": "free",
    "8085": "free",
    "8086": "LISTENING",
    "8087": "free",
    "8088": "free",
    "8090": "free",
    "8091": "LISTENING",
    "8092": "free",
    "8093": "free",
    "8094": "free",
    "9000": "free",
    "9001": "free"
  },
  "env_missing": [
    "AGENT_ZERO_BASE_URL",
    "AGENT_ZERO_EVENTS_TOKEN",
    "ALLOWED_BUCKETS",
    "AUTOLINK_INTERVAL_SEC",
    "AWS_DEFAULT_REGION",
    "CHANNEL_MONITOR_CONFIG_PATH",
    "CHANNEL_MONITOR_DATABASE_URL",
    "CHANNEL_MONITOR_NAMESPACE",
    "CHANNEL_MONITOR_QUEUE_URL",
    "CHANNEL_MONITOR_SECRET",
    "CHANNEL_MONITOR_STATUS_SECRET",
    "CHANNEL_MONITOR_STATUS_URL",
    "CHIT_CLIP_MODEL",
    "CHIT_CODEBOOK_PATH",
    "CHIT_DECODE_AUDIO",
    "CHIT_DECODE_IMAGE",
    "CHIT_DECODE_TEXT",
    "CHIT_DECRYPT_ANCHORS",
    "CHIT_PASSPHRASE",
    "CHIT_PERSIST_DB",
    "CHIT_REQUIRE_SIGNATURE",
    "CHIT_T5_MODEL",
    "CLAUDE_SESSION_CHANNEL_ID",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_LLM_MODEL",
    "DISCORD_AVATAR_URL",
    "DISCORD_BOT_TOKEN",
    "DISCORD_SUBJECTS",
    "DISCORD_USERNAME",
    "DISCORD_WEBHOOK_URL",
    "DISCORD_WEBHOOK_USERNAME",
    "ENTITY_CACHE_MAX",
    "ENTITY_CACHE_TTL",
    "EVAL_HTTP_PORT",
    "EXTERNAL_MEILI",
    "EXTERNAL_NEO4J",
    "EXTERNAL_QDRANT",
    "EXTERNAL_SUPABASE",
    "EXTRACT_PUBLISH_TOKEN",
    "EXTRACT_PUBLISH_URL",
    "EXTRACT_WORKER_URL",
    "FFW_URL",
    "FRAME_BUCKET",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GOTRUE_SITE_URL",
    "GRAPH_BOOST",
    "HF_API_KEY",
    "HF_EMBED_MODEL",
    "HF_GEMMA_MODEL",
    "HF_TOKEN",
    "HF_USE_GPU",
    "HIRAG_HTTP_PORT",
    "HIRAG_RERANK_ENABLED",
    "HIRAG_URL",
    "INDEXER_NAMESPACE",
    "JELLYFIN_API_KEY",
    "JELLYFIN_API_URL",
    "JELLYFIN_AUTOLINK",
    "JELLYFIN_LIBRARY_ID",
    "JELLYFIN_PUBLIC_BASE_URL",
    "JELLYFIN_PUBLISHED_URL",
    "JELLYFIN_URL",
    "JELLYFIN_USER_ID",
    "LANGEXTRACT_FEEDBACK_METRIC",
    "LANGEXTRACT_FEEDBACK_TOKEN",
    "LANGEXTRACT_FEEDBACK_URL",
    "LANGEXTRACT_PROVIDER",
    "LANGEXTRACT_REQUEST_ID",
    "LANGEXTRACT_URL",
    "MEILI_MASTER_KEY",
    "MEILI_URL",
    "MINIO_ACCESS_KEY",
    "MINIO_BUCKET",
    "MINIO_ENDPOINT",
    "MINIO_SECRET_KEY",
    "MINIO_SECURE",
    "N8N_RUNNERS_AUTH_TOKEN",
    "NATS_URL",
    "NEO4J_DICT_LIMIT",
    "NEO4J_DICT_REFRESH_SEC",
    "NEO4J_PASSWORD",
    "NEO4J_URL",
    "NEO4J_USER",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_AUTH_CALLBACK_URL",
    "NEXT_PUBLIC_SUPABASE_OAUTH_ENABLED",
    "NEXT_PUBLIC_SUPABASE_PASSWORD_AUTH_ENABLED",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NOTEBOOK_SYNC_DB_PATH",
    "NOTEBOOK_SYNC_INTERVAL_SECONDS",
    "NOTEBOOK_SYNC_NAMESPACE",
    "OLLAMA_EMBED_MODEL",
    "OLLAMA_URL",
    "OPENAI_API_BASE",
    "OPENAI_API_KEY",
    "OPENAI_COMPAT_API_KEY",
    "OPENAI_COMPAT_BASE_URL",
    "OPENAI_COMPAT_EMBED_MODEL",
    "OPENAI_MODEL",
    "OPEN_NOTEBOOK_API_TOKEN",
    "OPEN_NOTEBOOK_API_URL",
    "PDF_DEFAULT_BUCKET",
    "PDF_DEFAULT_NAMESPACE",
    "PDF_INGEST_EXTRACT_URL",
    "PDF_MAX_PAGES",
    "PGDATABASE",
    "PGHOST",
    "PGPASSWORD",
    "PGPORT",
    "PGRST_DB_ANON_ROLE",
    "PGRST_DB_SCHEMA",
    "PGUSER",
    "POSTGRES_DB",
    "POSTGRES_PASSWORD",
    "POSTGRES_USER",
    "PRESIGN_SHARED_SECRET",
    "PUBLISHER_NOTIFY_DISCORD_WEBHOOK",
    "PUBLISHER_REFRESH_ON_PUBLISH",
    "QDRANT_COLLECTION",
    "QDRANT_URL",
    "RENDER_AUTO_APPROVE",
    "RENDER_WEBHOOK_SHARED_SECRET",
    "RERANK_ENABLE",
    "RERANK_K",
    "RERANK_MODEL",
    "RERANK_TOPN",
    "SENTENCE_MODEL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID",
    "SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET",
    "SUPABASE_JWT_SECRET",
    "SUPABASE_PUBLIC_STORAGE_BASE",
    "SUPABASE_REALTIME_SECRET",
    "SUPABASE_REST_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_STORAGE_URL",
    "SUPA_REST_INTERNAL_URL",
    "SUPA_REST_URL",
    "TAILSCALE_ADMIN_ONLY",
    "TAILSCALE_CIDRS",
    "TAILSCALE_ONLY",
    "TENSORZERO_API_KEY",
    "TENSORZERO_BASE_URL",
    "TENSORZERO_LARGE_MODEL",
    "TENSORZERO_PG_DB",
    "TENSORZERO_PG_PASSWORD",
    "TENSORZERO_PG_USER",
    "TENSORZERO_SMALL_MODEL",
    "USE_MEILI",
    "YT_ARCHIVE_DIR",
    "YT_BUCKET",
    "YT_CONCURRENCY",
    "YT_DOWNLOAD_ARCHIVE",
    "YT_ENABLE_DOWNLOAD_ARCHIVE",
    "YT_GEMMA_MODEL",
    "YT_INDEX_LEXICAL",
    "YT_PLAYLIST_MAX",
    "YT_POSTPROCESSORS_JSON",
    "YT_RATE_LIMIT",
    "YT_SEG_AUTOTUNE",
    "YT_SEG_GAP_THRESH",
    "YT_SEG_MAX_CHARS",
    "YT_SEG_MAX_DUR",
    "YT_SEG_MIN_CHARS",
    "YT_SEG_TARGET_DUR",
    "YT_SUBTITLE_AUTO",
    "YT_SUBTITLE_LANGS",
    "YT_SUMMARY_PROVIDER",
    "YT_WRITE_INFO_JSON"
  ]
}
make: Leaving directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
```
Exit code: 0

## Core Smoke
Command: make -C pmoves smoke
```text
make: Entering directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
-> Running scripts/smoke.ps1
[1/12] Qdrant ready...
Smoke tests failed: Qdrant not ready yet
make: Leaving directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
```
Exit code: 2

## GPU Smoke (strict)
Command: make -C pmoves smoke-gpu
```text
make: Entering directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
[GPU] Check v2-gpu (:8087) up...
[FAIL] v2-gpu root endpoint unavailable on :8087 (HTTP 0)
[GPU] Check v2-gpu (:8087) up...
[FAIL] v2-gpu root endpoint unavailable on :8087 (HTTP 0)
[GPU] Check v2-gpu (:8087) up...
[FAIL] v2-gpu root endpoint unavailable on :8087 (HTTP 0)
make: Leaving directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
```
Exit code: 2

## Codex Health Quick
Command: make -C pmoves codex-health-quick
```text
make: Entering directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
--  agent-zero     404  http://localhost:8081/healthz
ok  archon         200  http://localhost:8091/healthz
ok  hirag-v2       200  http://localhost:8086/hirag/admin/stats
--  flute-gateway    0  http://localhost:8092/healthz
--  evo-controller   0  http://localhost:8090/healthz
--  botz-gateway     0  http://localhost:8097/healthz
{
  "strict": false,
  "results": {
    "agent-zero": {
      "ok": false,
      "status": 404,
      "url": "http://localhost:8081/healthz"
    },
    "archon": {
      "ok": true,
      "status": 200,
      "url": "http://localhost:8091/healthz"
    },
    "hirag-v2": {
      "ok": true,
      "status": 200,
      "url": "http://localhost:8086/hirag/admin/stats"
    },
    "flute-gateway": {
      "ok": false,
      "status": 0,
      "url": "http://localhost:8092/healthz"
    },
    "evo-controller": {
      "ok": false,
      "status": 0,
      "url": "http://localhost:8090/healthz"
    },
    "botz-gateway": {
      "ok": false,
      "status": 0,
      "url": "http://localhost:8097/healthz"
    }
  }
}
make: Leaving directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
```
Exit code: 0

## Codex Audit
Command: make -C pmoves codex-audit
```text
make: Entering directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
Wrote C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves\docs\AGENTS\CODEX_SUBMODULE_INTEGRATION_AUDIT.md
Wrote pmoves/docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md
make: Leaving directory 'C:/Users/russe/Documents/GitHub/PMOVES.AI/pmoves'
```
Exit code: 0

