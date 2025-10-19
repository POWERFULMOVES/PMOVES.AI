# PMOVES top-level Makefile

# -------- External-mode → Compose profiles ----------
# If EXTERNAL_* is true, we skip the corresponding local service profile.
# Profiles are defined on services in docker-compose.yml.
compose_profiles = data,workers,gateway
ifeq ($(EXTERNAL_NEO4J),true)
  neo4j_profile :=
else
  neo4j_profile := ,neo4j-local
endif
ifeq ($(EXTERNAL_MEILI),true)
  meili_profile :=
else
  meili_profile := ,meili-local
endif
ifeq ($(EXTERNAL_QDRANT),true)
  qdrant_profile :=
else
  qdrant_profile := ,qdrant-local
endif
ifeq ($(EXTERNAL_SUPABASE),true)
  supa_profile :=
else
  supa_profile := ,supabase-local
endif
COMPOSE_PROFILES ?= $(compose_profiles)$(neo4j_profile)$(meili_profile)$(qdrant_profile)$(supa_profile)
export COMPOSE_PROFILES

PYTHON ?= python3
BOOTSTRAP_FLAGS ?=

# -------- Updates ----------
.PHONY: update
update:  ## Pull repo + images, recreate stack
	@git pull --rebase
	@docker compose pull --quiet
	@docker compose up -d
	@echo "✔ Updated & reconciled containers."

# -------- Backups / Restore helpers ----------
.PHONY: backup restore
BACKUP_DIR ?= backups/$$(date +%Y%m%d_%H%M%S)
backup: ## Dump Postgres, snapshot Qdrant, mirror MinIO bucket, Meili dump (best-effort)
	@mkdir -p "$(BACKUP_DIR)"
	@echo "→ Backing up Postgres…"
	-@docker compose exec -T postgres pg_dump -U $$POSTGRES_USER -d $$POSTGRES_DB > "$(BACKUP_DIR)/postgres.sql"
	@echo "→ Snapshotting Qdrant…"
	-@curl -fsS "http://localhost:6333/collections/$$QDRANT_COLLECTION/snapshots" -X POST -H 'content-type: application/json' -d '{}' > "$(BACKUP_DIR)/qdrant_snapshot.json"
	@echo "→ Mirroring MinIO bucket '$(MINIO_BUCKET)' (requires mc alias 'local')…"
	-@docker compose exec -T minio mc mirror --overwrite local/$$MINIO_BUCKET "$(BACKUP_DIR)/minio_$$MINIO_BUCKET"
	@echo "→ Dumping Meilisearch…"
	-@curl -fsS "http://localhost:7700/dumps" -X POST -H "X-Meili-API-Key: $$MEILI_MASTER_KEY" -d '{}' > "$(BACKUP_DIR)/meili_dump.json"
	@echo "✔ Backup written to: $(BACKUP_DIR)"

restore: ## See docs/LOCAL_DEV.md for restore steps
	@echo "See docs/LOCAL_DEV.md (Restore) for step-by-step instructions."

# -------- GPU profile ----------
.PHONY: up-gpu
up-gpu: ## Start with optional GPU accelerations where supported
	@docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d
	@echo "✔ Stack started with GPU profile."

.PHONY: up down clean up-workers up-yt up-media up-jellyfin up-nats ps supabase-up supabase-stop supabase-clean supa-extract-remote env-setup env-check
.PHONY: discord-ping discord-ping-ps demo-content-published health-publisher-discord up-agents health-agent-zero health-jellyfin-bridge seed-approval seed-approval-ps m2-preflight evidence-stamp evidence-stamp-ps evidence-log evidence-log-ps m2-seed-demo n8n-webhook-demo
.PHONY: notebook-up notebook-down notebook-logs

# Pin a stable Docker Compose project name so make targets
# always operate on the same stack regardless of cwd/path.
PROJECT ?= pmoves
export PROJECT

NOTEBOOK_COMPOSE ?= docker-compose.open-notebook.yml
NOTEBOOK_PROJECT ?= $(PROJECT)-notebook

JELLYFIN_AI_BASE ?= jellyfin-ai
export JELLYFIN_AI_BASE
# Supabase provider: 'cli' for Supabase CLI stack, 'compose' for docker-compose stack
SUPA_PROVIDER ?= cli

# Data services differ by provider: with CLI we don't run Postgres/PostgREST here
DATA_SERVICES := minio presign

ifeq ($(EXTERNAL_QDRANT),true)
else
DATA_SERVICES += qdrant
endif

ifeq ($(EXTERNAL_NEO4J),true)
else
DATA_SERVICES += neo4j
endif

ifeq ($(EXTERNAL_MEILI),true)
else
DATA_SERVICES += meilisearch
endif

ifeq ($(SUPA_PROVIDER),cli)
else
ifeq ($(EXTERNAL_SUPABASE),true)
else
DATA_SERVICES += postgres postgrest
endif
endif

down:
	docker compose -p $(PROJECT) down

clean:
	docker compose -p $(PROJECT) down -v --remove-orphans

notebook-up: ## Launch the Open Notebook stack alongside pmoves-net
	docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) up -d open-notebook

notebook-down: ## Stop the Open Notebook container and remove its resources
	docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) down

notebook-logs: ## Follow logs for the Open Notebook service
	docker compose -p $(NOTEBOOK_PROJECT) -f $(NOTEBOOK_COMPOSE) logs -f open-notebook

# Bring only worker services (ensures data deps are active)
up-workers:
	docker compose -p $(PROJECT) --profile data --profile workers up -d hi-rag-gateway-v2 retrieval-eval render-webhook langextract extract-worker

# YouTube ingest + whisper stack
up-yt:
	docker compose -p $(PROJECT) --profile data --profile workers up -d ffmpeg-whisper pmoves-yt

# Optional media analyzers (video+audio)
up-media:
	docker compose -p $(PROJECT) --profile data --profile workers up -d media-video media-audio

# Jellyfin bridge only
up-jellyfin:
	docker compose -p $(PROJECT) up -d jellyfin-bridge

# Bring up agents stack (NATS, Agent Zero, Archon, Mesh Agent) and publisher-discord
.PHONY: up-agents
up-agents:
	docker compose -p $(PROJECT) --profile agents up -d nats agent-zero archon mesh-agent publisher-discord

.PHONY: up-n8n
up-n8n:
	docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.n8n.yml up -d n8n

# Status helper
ps:
	docker compose -p $(PROJECT) ps

# Switch between local (CLI) and self-hosted Supabase by swapping .env.local
.PHONY: supa-use-local supa-use-remote up-cli up-compose
supa-use-local:
	- pwsh -NoProfile -Command "Copy-Item -Force .env.supa.local.example .env.local"
	- sh -c 'cp -f .env.supa.local.example .env.local 2>/dev/null || true'

supa-use-remote:
	- pwsh -NoProfile -Command "if (Test-Path .\.env.supa.remote) { Copy-Item -Force .\.env.supa.remote .\.env.local } else { Copy-Item -Force .\.env.supa.remote.example .\.env.local }"
	- sh -c 'if [ -f .env.supa.remote ]; then cp -f .env.supa.remote .env.local; else cp -f .env.supa.remote.example .env.local; fi 2>/dev/null || true'

up-cli:
	SUPA_PROVIDER=cli $(MAKE) up

up-compose:
	SUPA_PROVIDER=compose $(MAKE) up

# Start a local NATS broker and enable events in .env.local
up-nats:
	docker compose -p $(PROJECT) --profile agents up -d nats
	- pwsh -NoProfile -Command "if (-not (Test-Path .\.env.local)) { New-Item -ItemType File -Path .\.env.local | Out-Null }; $c = Get-Content .\.env.local | Where-Object { $_ -notmatch '^(YT_NATS_ENABLE|NATS_URL)=' }; $c + @('YT_NATS_ENABLE=true','NATS_URL=nats://nats:4222') | Set-Content .\.env.local"
	- sh -c 'touch .env.local; tmp=$$(mktemp); grep -v -E "^(YT_NATS_ENABLE|NATS_URL)=" .env.local > "$$tmp"; printf "YT_NATS_ENABLE=true\nNATS_URL=nats://nats:4222\n" >> "$$tmp"; mv "$$tmp" .env.local' 2>/dev/null || true

# Supabase lightweight services (realtime/storage/gotrue/studio) using main Postgres (Compose mode)
SUPA_FILE ?= docker-compose.supabase.yml
SUPA_PROJECT ?= pmoves

supabase-up:
	docker compose -p $(PROJECT) -f docker-compose.yml -f $(SUPA_FILE) up -d gotrue realtime storage studio

supabase-stop:
	docker compose -p $(PROJECT) -f docker-compose.yml -f $(SUPA_FILE) stop gotrue realtime storage studio

supabase-clean:
	- docker volume rm $(PROJECT)_supabase-storage 2> NUL || true

# Supabase CLI targets (Option A). Requires 'supabase' CLI in PATH.
.PHONY: supa-init supa-start supa-stop supa-status
supa-init:
	where supabase > NUL 2>&1 || (echo Supabase CLI not found. Install via 'winget install supabase.supabase' or 'npm i -g supabase' && exit 1)
	supabase init

supa-start:
	where supabase > NUL 2>&1 || (echo Supabase CLI not found. Install via 'winget install supabase.supabase' or 'npm i -g supabase' && exit 1)
	supabase start

supa-stop:
	where supabase > NUL 2>&1 || (echo Supabase CLI not found. Install via 'winget install supabase.supabase' or 'npm i -g supabase' && exit 1)
	supabase stop

supa-status:
	where supabase > NUL 2>&1 || (echo Supabase CLI not found. Install via 'winget install supabase.supabase' or 'npm i -g supabase' && exit 1)
	supabase status

supa-extract-remote:
	pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/extract_supa_md.ps1 -Source supa.md -Out .env.supa.remote

# Environment helpers
env-setup:
	- pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_setup.ps1
	- bash scripts/env_setup.sh || true

env-check:
	- pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1
	- bash scripts/env_check.sh || true

.PHONY: supabase-bootstrap
supabase-bootstrap:
	@if docker ps --format '{{.Names}}' | grep -q '^supabase_db_pmoves$$'; then \
	  echo "→ Supabase CLI stack detected; applying schema + seed SQL"; \
	  set -eu; \
	  for f in supabase/initdb/*.sql; do \
	    echo "   • Init $$f"; \
	    cat "$$f" | docker exec -i supabase_db_pmoves psql -U postgres -d postgres -v ON_ERROR_STOP=1 >/dev/null; \
	  done; \
	  for f in supabase/migrations/*.sql; do \
	    echo "   • Migration $$f"; \
	    cat "$$f" | docker exec -i supabase_db_pmoves psql -U postgres -d postgres -v ON_ERROR_STOP=1 >/dev/null; \
	  done; \
	  if [ -f db/v5_12_grounded_personas.sql ]; then \
	    echo "   • Schema db/v5_12_grounded_personas.sql"; \
	    cat db/v5_12_grounded_personas.sql | docker exec -i supabase_db_pmoves psql -U postgres -d postgres -v ON_ERROR_STOP=1 >/dev/null; \
	  fi; \
	  if [ -f db/v5_12_seed.sql ]; then \
	    echo "   • Seed db/v5_12_seed.sql"; \
	    cat db/v5_12_seed.sql | docker exec -i supabase_db_pmoves psql -U postgres -d postgres -v ON_ERROR_STOP=1 >/dev/null; \
	  fi; \
	  echo "✔ Supabase schema + seeds applied."; \
	else \
	  echo "↷ Supabase CLI stack not running (supabase_db_pmoves missing); skipping Supabase bootstrap."; \
	fi

.PHONY: neo4j-bootstrap
neo4j-bootstrap:
	@bash scripts/neo4j_bootstrap.sh

.PHONY: smoke-webhook-ci
smoke-webhook-ci:
	@echo "Render-webhook smoke (dry-run by default). Use LIVE=1 to POST."
	@cd pmoves && \
	 if [ "$(LIVE)" = "1" ]; then \
	   python tools/smoke_webhook.py --live; \
	 else \
	   python tools/smoke_webhook.py; \
	 fi

.PHONY: test-discord-format
test-discord-format:
	@echo "Running publisher-discord embed formatting tests" && \
	 pytest -q pmoves/services/publisher-discord/tests -k formatting

.PHONY: up-legacy
up-legacy:
	docker compose -p $(PROJECT) --profile data up -d qdrant neo4j minio meilisearch presign
	docker compose -p $(PROJECT) --profile workers up -d hi-rag-gateway retrieval-eval render-webhook

.PHONY: discord-ping
discord-ping:
	@which jq >/dev/null 2>&1 || (echo "jq is required for discord-ping" && exit 1)
	@if [ -z "$$DISCORD_WEBHOOK_URL" ]; then echo "Set DISCORD_WEBHOOK_URL in env or .env/.env.local" && exit 1; fi
	@MSG="$${MSG:-PMOVES Discord wiring check}"; \
	sh -c './pmoves/scripts/discord_ping.sh "'"$${MSG}"'"'

.PHONY: discord-ping-ps
discord-ping-ps:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/discord_ping.ps1 -Message "$(MSG)"

.PHONY: smoke
smoke:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke tests" && exit 1)
	@echo "[1/12] Qdrant ready..." && curl -sf http://localhost:6333/readyz >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[2/12] Meilisearch ready..." && curl -sf http://localhost:7700/health >/dev/null && echo OK || (echo WARN: skipping; true)
	@echo "[3/12] Neo4j UI..." && curl -sf http://localhost:7474 >/dev/null && echo OK || (echo WARN: UI not reachable; true)
	@echo "[4/12] presign health..." && curl -sf http://localhost:8088/healthz >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[5/12] render-webhook health..." && curl -sf http://localhost:8085/healthz >/dev/null && echo OK || (echo FAIL && exit 1)
	@REST_BASE="$${SUPA_REST_URL:-http://127.0.0.1:54321/rest/v1}"; \
	 APIKEY="$${SUPABASE_ANON_KEY:-sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH}"; \
	 echo "[6/12] PostgREST reachable..." && curl -sf "$${REST_BASE}/it_errors?select=id&limit=1" -H "apikey: $$APIKEY" >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[7/12] Insert via render-webhook..." && curl -sf -X POST http://localhost:8085/comfy/webhook \
	 -H "Content-Type: application/json" \
	 -H "Authorization: Bearer $${RENDER_WEBHOOK_SHARED_SECRET:-change_me}" \
	 -d '{"bucket":"outputs","key":"demo.png","s3_uri":"s3://outputs/demo.png","presigned_get":null,"title":"Demo","namespace":"pmoves","author":"local","tags":["demo"],"auto_approve":false}' >/dev/null && echo OK || (echo FAIL && exit 1)
	@REST_BASE="$${SUPA_REST_URL:-http://127.0.0.1:54321/rest/v1}"; \
	 APIKEY="$${SUPABASE_ANON_KEY:-sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH}"; \
	 echo "[8/12] Verify studio_board row..." && curl -sf "$${REST_BASE}/studio_board?order=id.desc&limit=1" -H "apikey: $$APIKEY" | jq -e '.[0].title != null' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[9/12] Hi-RAG v2 query..." && curl -sf localhost:8087/hirag/query -H 'content-type: application/json' -d '{"query":"what is pmoves?","namespace":"pmoves","k":3,"alpha":0.7}' | jq -e '.hits != null' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[10/12] Agent Zero health..." && curl -sf http://localhost:8080/healthz | jq -e '.nats.connected == true' >/dev/null && echo OK || (echo FAIL && exit 1)
	@CID=$$(uuidgen | tr 'A-Z' 'a-z' | cut -d- -f1); \
	 POINT_ID="p.smoke.$${CID}"; \
	 CONST_ID="c.smoke.$${CID}"; \
	 TMP=$$(mktemp); \
	 REF_ID="yt:smoke-$${CID}"; \
	 export RUN_ID="$${CID}" POINT_ID="$${POINT_ID}" CONST_ID="$${CONST_ID}" REF_ID="$$REF_ID"; \
	 python3 -c 'import json, os, sys; obj={"type":"geometry.cgp.v1","data":{"spec":"chit.cgp.v0.1","meta":{"source":"smoke-test","namespace":"pmoves","run_id":os.environ["RUN_ID"]},"super_nodes":[{"id":"sn.smoke","constellations":[{"id":os.environ["CONST_ID"],"summary":"smoke geometry validation","radial_minmax":[0.05,0.85],"spectrum":[0.08,0.12,0.18,0.22,0.18,0.12,0.07,0.03],"anchor":[0.52,-0.41,0.23,0.11],"points":[{"id":os.environ["POINT_ID"],"modality":"video","ref_id":os.environ["REF_ID"],"t_start":12.5,"frame_idx":300,"proj":0.82,"conf":0.93,"text":"geometry smoke anchor"}]}]}]}}; json.dump(obj, sys.stdout)' > $$TMP; \
	 echo "[11/12] Geometry event ingest..." && curl -sf http://localhost:8087/geometry/event -H 'content-type: application/json' -d @$${TMP} >/dev/null && echo OK || { echo FAIL; rm -f $$TMP; exit 1; }; \
	 echo "[12/12] Geometry jump & calibration..." && curl -sf "http://localhost:8087/shape/point/$${POINT_ID}/jump" | jq -e --arg ref "$$REF_ID" '.locator.ref_id == $$ref' >/dev/null && curl -sf http://localhost:8087/geometry/calibration/report -H 'content-type: application/json' -d "$$(jq -c '.data' $$TMP)" | jq -e '.constellations != null' >/dev/null && echo OK || { echo FAIL; rm -f $$TMP; exit 1; }; \
	 rm -f $$TMP
	@echo "Smoke tests passed."

.PHONY: smoke-rerank
smoke-rerank:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "Request with rerank=true (may be disabled if model not available)"
	curl -s localhost:8087/hirag/query -H 'content-type: application/json' -d '{"query":"what is pmoves?","namespace":"pmoves","k":3,"alpha":0.7, "use_rerank": true}' | jq .
	@echo "If used_rerank=false, ensure internet/model access, or set RERANK_ENABLE=false."

.PHONY: retrieval-eval-smoke
retrieval-eval-smoke:
	@set -eu; \
	DATASETS=$$(ls services/retrieval-eval/datasets/*.jsonl 2>/dev/null || true); \
	if [ -z "$$DATASETS" ]; then \
	  echo "No retrieval-eval datasets found under services/retrieval-eval/datasets/."; \
	  exit 1; \
	fi; \
	for ds in $$DATASETS; do \
	  echo "→ Evaluating $$ds"; \
	  $(PYTHON) services/retrieval-eval/evaluate.py "$$ds" --no-query-details; \
	done
.PHONY: eval-jsonl
eval-jsonl:
	@if [ -z "$(FILE)" ]; then echo "Usage: make eval-jsonl FILE=/abs/path/queries.jsonl [K=10]"; exit 1; fi
	docker compose build retrieval-eval
	docker compose run --rm --entrypoint python --volume "$(FILE):/data/queries.jsonl:ro" retrieval-eval /app/evaluate.py /data/queries.jsonl $(K)

.PHONY: smoke-presign-put
smoke-presign-put:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "Generating presign PUT and uploading a small text file..."
	@URL=$$(curl -s -X POST http://localhost:8088/presign/put \
	  -H 'content-type: application/json' \
	  -H "Authorization: Bearer $${PRESIGN_SHARED_SECRET:-change_me}" \
	  -d '{"bucket":"outputs","key":"hello.txt","content_type":"text/plain","expires":300}' ) && \
	  echo $$URL | jq -r '.url' | xargs -I {} sh -c "echo 'hello pmoves' | curl -s -X PUT -H 'Content-Type: text/plain' --data-binary @- '{}' >/dev/null" && echo OK || (echo FAIL && exit 1)

.PHONY: smoke-pdf
smoke-pdf:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke-pdf" && exit 1)
	@test -f pmoves/datasets/sample.pdf || (echo "datasets/sample.pdf missing" && exit 1)
	@echo "[1/4] Create presign URL for sample.pdf" && \
	URL=$$(curl -s -X POST http://localhost:8088/presign/put \
	  -H 'content-type: application/json' \
	  -H "Authorization: Bearer $${PRESIGN_SHARED_SECRET:-change_me}" \
	  -d '{"bucket":"assets","key":"pdfs/sample.pdf","content_type":"application/pdf","expires":300}' ) && echo OK || (echo FAIL && exit 1)
	@echo "[2/4] Upload sample.pdf to MinIO" && \
	echo "$$URL" | jq -r .url | xargs -I {} curl -s -X PUT -H 'Content-Type: application/pdf' --data-binary @pmoves/datasets/sample.pdf '{}' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[3/4] Trigger pdf-ingest" && \
	curl -sf http://localhost:8092/pdf/ingest -H 'content-type: application/json' \
	  -d '{"bucket":"assets","key":"pdfs/sample.pdf","namespace":"pmoves","title":"Sample PDF","publish_events":false}' \
	  | jq -e '.ok == true and .chunks >= 1' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[4/4] Verify chunks in extract-worker response" && \
	curl -sf http://localhost:8092/pdf/ingest -H 'content-type: application/json' \
	  -d '{"bucket":"assets","key":"pdfs/sample.pdf","namespace":"pmoves","doc_id":"pdf:sample","publish_events":false}' \
	  | jq -e '.ingest.chunks >= 1' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "PDF ingest smoke passed."

.PHONY: mindmap-seed
mindmap-seed:
	@echo "Seeding Neo4j with CHIT mindmap demo data..."
	docker compose -p $(PROJECT) exec neo4j cypher-shell -a bolt://localhost:7687 -u $${NEO4J_USER:-neo4j} -p $${NEO4J_PASSWORD:-neo4j} -f /cypher/003_seed_chit_mindmap.cypher

.PHONY: mindmap-smoke
mindmap-smoke:
	@echo "Querying /mindmap demo constellation..."
	python scripts/mindmap_query.py --base $${MINDMAP_BASE:-http://localhost:8000} --cid $${MINDMAP_CONSTELLATION_ID:-8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111} --limit $${MINDMAP_LIMIT:-5}

.PHONY: seed-data
seed-data:
	@echo "Building hi-rag-gateway-v2 (to include seed scripts) if needed..."
	docker compose build hi-rag-gateway-v2
	@echo "Seeding Qdrant + Meilisearch with small demo docs..."
	docker compose run --rm --entrypoint python hi-rag-gateway-v2 /app/scripts/seed_local.py


.PHONY: load-jsonl
load-jsonl:
	@if [ -z "$(FILE)" ]; then echo "Usage: make load-jsonl FILE=path/to/data.jsonl [NAMESPACE=pmoves]"; exit 1; fi
	@echo "Building hi-rag-gateway-v2 (to include loader script) if needed..."
	docker compose build hi-rag-gateway-v2
	@echo "Loading JSONL into Qdrant/Meili from $(FILE) ..."
	docker compose run --rm --entrypoint python --volume "$(FILE):/data/input.jsonl:ro" hi-rag-gateway-v2 /app/scripts/load_jsonl.py /data/input.jsonl $(NAMESPACE)

.PHONY: load-csv
load-csv:
	@if [ -z "$(FILE)" ]; then echo "Usage: make load-csv FILE=path/to/data.csv [NAMESPACE=pmoves]"; exit 1; fi
	docker compose build hi-rag-gateway-v2
	docker compose run --rm --entrypoint python --volume "$(FILE):/data/input.csv:ro" hi-rag-gateway-v2 /app/scripts/load_csv.py /data/input.csv $(NAMESPACE)

.PHONY: export-jsonl
export-jsonl:
	@if [ -z "$(OUT)" ]; then echo "Usage: make export-jsonl OUT=/abs/path/output.jsonl [NAMESPACE=pmoves] [LIMIT=1000]"; exit 1; fi
	docker compose build hi-rag-gateway-v2
	docker compose run --rm --entrypoint python --volume "$(OUT):/data/output.jsonl" hi-rag-gateway-v2 /app/scripts/export_jsonl.py /data/output.jsonl $(NAMESPACE) $(LIMIT)

.PHONY: smoke-langextract
smoke-langextract:
	@echo "Extracting chunks from datasets/log_sample.xml via langextract..."
	@JSONL=$$(curl -s -X POST http://localhost:8084/extract/jsonl -H 'content-type: application/json' --data-binary @- <<- 'EOF'
	{
	  "xml": "$$(python - <<- 'PY'
	import json
	print(open('datasets/log_sample.xml','r',encoding='utf-8').read().replace('\\','\\\\').replace('"','\\"').replace('\n','\\n'))
	PY
	)"
	}
	EOF
	) && echo "OK: parsed" || (echo FAIL && exit 1)
	@echo "Writing temp jsonl and loading to Qdrant/Meili..."
	@echo "$$JSONL" | jq -r .jsonl > .tmp_extracted.jsonl
	@make load-jsonl FILE=$(PWD)/.tmp_extracted.jsonl NAMESPACE=pmoves
	@rm -f .tmp_extracted.jsonl

.PHONY: smoke-archon
smoke-archon:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke-archon" && exit 1)
	@bash -c 'set -euo pipefail; \
	ARCHON_URL="$${ARCHON_HEALTH_URL:-http://localhost:8091/healthz}"; \
	printf "[Archon] GET %s\n" "$$ARCHON_URL"; \
	resp=$$(curl -fsS "$$ARCHON_URL"); \
	status=$$(printf "%s" "$$resp" | jq -r ".status // empty"); \
	if [ "$$status" != "ok" ]; then \
	  echo "Archon health degraded or unavailable (status=$$status)"; \
	  exit 1; \
	fi; \
	printf "%s\n" "$$resp"'

.PHONY: chit-contract-check
chit-contract-check:
	@bash "$(CURDIR)/../scripts/check_chit_contract.sh"

.PHONY: jellyfin-verify
jellyfin-verify:
	@bash -c 'set -euo pipefail; \
	 if [ -f env.jellyfin-ai ]; then set -a; . env.jellyfin-ai; set +a; fi; \
	 python3 "$(CURDIR)/../scripts/check_jellyfin_credentials.py"'

.PHONY: up-jellyfin-ai
up-jellyfin-ai:
	@test -f env.jellyfin-ai || cp env.jellyfin-ai.example env.jellyfin-ai
	@mkdir -p $(JELLYFIN_AI_BASE)/config $(JELLYFIN_AI_BASE)/cache $(JELLYFIN_AI_BASE)/media $(JELLYFIN_AI_BASE)/output
	@mkdir -p $(JELLYFIN_AI_BASE)/neo4j/data $(JELLYFIN_AI_BASE)/neo4j/logs $(JELLYFIN_AI_BASE)/neo4j/import $(JELLYFIN_AI_BASE)/neo4j/plugins
	@mkdir -p $(JELLYFIN_AI_BASE)/qwen/models $(JELLYFIN_AI_BASE)/qwen/cache
	@mkdir -p $(JELLYFIN_AI_BASE)/logs $(JELLYFIN_AI_BASE)/redis
	@echo "Starting Jellyfin AI stack..."
	@JELLYFIN_AI_BASE=$(JELLYFIN_AI_BASE) docker compose -p $(PROJECT) -f docker-compose.yml -f docker-compose.jellyfin-ai.yml up -d --force-recreate \
		jellyfin jellyfin-neo4j jellyfin-qwen-audio jellyfin-redis jellyfin-audio-processor jellyfin-api-gateway jellyfin-dashboard
	@echo "✓ Jellyfin AI stack started successfully!"
	@echo ""
	@echo "Services:"
	@echo "  - Jellyfin Media Server:  http://localhost:8096"
	@echo "  - Dashboard:              http://localhost:8400"
	@echo "  - API Gateway:            http://localhost:8300"
	@echo "  - Ollama (Qwen2-Audio):   http://localhost:11434"
	@echo "  - Neo4j Browser:          bolt://localhost:7687"
	@echo ""
	@echo "Note: Qwen2-Audio model is already pulled and ready to use!"


.PHONY: flight-check
flight-check:
ifeq ($(OS),Windows_NT)
	@pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1
else
	@bash scripts/env_check.sh
endif

.PHONY: flight-check-retro
flight-check-retro:
	@echo "Installing retro flightcheck deps (uv preferred, fallback to pip)" && \
	( command -v uv >/dev/null 2>&1 && uv pip install -q -r tools/flightcheck/requirements.txt || $(PYTHON) -m pip install -q -r tools/flightcheck/requirements.txt ) && \
	$(PYTHON) tools/flightcheck/retro_flightcheck.py

.PHONY: preflight
preflight:
	@echo "Running PMOVES preflight checks..."
	@$(PYTHON) scripts/bootstrap_env.py --check
	@$(PYTHON) tools/flightcheck/retro_flightcheck.py --quick || true
	@$(PYTHON) tools/flightcheck/retro_flightcheck.py --theme neon --beep || true

.PHONY: env-dedupe
env-dedupe:
	@python tools/env_dedupe.py

.PHONY: help
help:
	@echo "Targets:"
	@echo "  up               Start core data + workers via docker compose"
	@echo "  down             Stop all containers"
	@echo "  clean            Stop and remove volumes (destructive)"
	@echo "  smoke            Run local smoke tests"
	@echo "  smoke-rerank     Run a sample query with rerank=true"
	@echo "  seed-data        Seed Qdrant/Meilisearch with demo docs"
	@echo "  load-jsonl       Load a JSONL file (FILE=/abs/path)"
	@echo "  load-csv         Load a CSV file (FILE=/abs/path)"
	@echo "  export-jsonl     Export namespace to JSONL (OUT=/abs/path)"
	@echo "  smoke-presign-put Test presign PUT and upload"
	@echo "  smoke-pdf        Upload and index a sample PDF via pdf-ingest"
	@echo "  mindmap-seed     Load CHIT demo constellation into Neo4j"
	@echo "  mindmap-smoke    Query /mindmap using the seeded constellation"
	@echo "  smoke-langextract Extract chunks via langextract and load"
	@echo "  smoke-archon     Check Archon healthz endpoint (requires NATS + Supabase)"
	@echo "  jellyfin-verify  Validate Jellyfin credentials and branding"
	@echo "  up-jellyfin-ai   Launch the optional Jellyfin AI media stack overlay"
	@echo "  chit-contract-check Run local CHIT contract grep (mirrors CI)"
	@echo "  flight-check     Run environment preflight (deps, ports, .env)"
	@echo "  flight-check-retro Retro-styled Rich CLI preflight"
	@echo "  env-dedupe       Remove duplicate keys from .env (keeps last, writes .bak)"
	@echo "  logs-core        Tail core services (docker compose logs -f ...)"
	@echo "  setup            Run Codex/bootstrap env setup (make, conda deps)"
	@echo "  venv             Create a local Python virtualenv (.venv) and install deps"
	@echo "  venv-min         Create a minimal .venv and install tools/requirements-minimal.txt"
	@echo "  supabase-migrate Apply supabase/migrations/*.sql via docker compose"
	@echo "  smoke-geometry   Post a CGP, jump a point, decode text, and run calibration"
	@echo "  smoke-geometry-db Validate seeded geometry rows via PostgREST"
	@echo "  codebook-gen     Generate structured_dataset.jsonl from a source JSONL"
	@echo "  mcp-agent-zero   Run Agent Zero MCP stdio shim (FORM=CREATOR|RESEARCHER|POWERFULMOVES)"
	@echo "  mcp-archon       Run Archon MCP stdio shim (FORM=...)"
	@echo "  mesh-up          Start NATS + mesh-agent"
	@echo "  mesh-handshake   Publish a shape-capsule to the mesh (FILE=cgp.json)"
	@echo "  web-geometry     Open geometry UI and seed a demo CGP"

.PHONY: logs-core
logs-core:
	@echo "Tailing core services (Ctrl-C to stop)..."
	@docker compose logs -f qdrant meilisearch neo4j postgres postgrest minio presign render-webhook hi-rag-gateway-v2 retrieval-eval

.PHONY: logs-core-15m
logs-core-15m:
	@docker compose logs --since 15m qdrant meilisearch neo4j postgres postgrest minio presign render-webhook hi-rag-gateway-v2 retrieval-eval

.PHONY: setup
setup:
	@if [ "$(OS)" = "Windows_NT" ]; then \
		pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/codex_bootstrap.ps1 -CondaEnvName $${CONDA_ENV:-PMOVES.AI} ; \
	else \
		bash scripts/codex_bootstrap.sh $${CONDA_ENV:-pmoves-ai} ; \
	fi

.PHONY: bootstrap
bootstrap:
	@$(PYTHON) scripts/bootstrap_env.py $(BOOTSTRAP_FLAGS)

.PHONY: supabase-migrate
supabase-migrate:
	@if [ "$(OS)" = "Windows_NT" ]; then \
		pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/apply_migrations_docker.ps1 ; \
	else \
		bash scripts/apply_migrations_docker.sh ; \
	fi

.PHONY: smoke-geometry
smoke-geometry:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke-geometry" && exit 1)
	@echo '{"type":"geometry.cgp.v1","data":{"spec":"chit.cgp.v0.1","super_nodes":[{"constellations":[{"id":"c.test.1","summary":"beat-aligned hook","spectrum":[0.05,0.1,0.2,0.3,0.2,0.1,0.03,0.02],"points":[{"id":"p.test.1","modality":"video","ref_id":"yt123","t_start":12.5,"frame_idx":300,"proj":0.8,"conf":0.9,"text":"chorus line"}]}]}]}}' > .tmp_cgp.json
	@echo "[1/4] POST /geometry/event" && curl -sf http://localhost:8087/geometry/event -H 'content-type: application/json' -d @.tmp_cgp.json >/dev/null && echo OK || (echo FAIL && rm -f .tmp_cgp.json && exit 1)
	@echo "[2/4] GET /shape/point/p.test.1/jump" && curl -sf http://localhost:8087/shape/point/p.test.1/jump | jq -e '.locator.modality=="video" and .locator.ref_id=="yt123"' >/dev/null && echo OK || (echo FAIL && rm -f .tmp_cgp.json && exit 1)
	@echo "[3/4] POST /geometry/decode/text (geometry mode)" && curl -sf http://localhost:8087/geometry/decode/text -H 'content-type: application/json' -d '{"mode":"geometry","constellation_id":"c.test.1","k":3}' | jq -e '.points|length>=1' >/dev/null && echo OK || (echo WARN: decoder disabled; true)
	@echo "[4/4] POST /geometry/calibration/report" && curl -sf http://localhost:8087/geometry/calibration/report -H 'content-type: application/json' -d @.tmp_cgp.json | jq -e '.constellations|length>=1' >/dev/null && echo OK || (echo FAIL && rm -f .tmp_cgp.json && exit 1)
	@rm -f .tmp_cgp.json
	@echo "Geometry smoke passed."

.PHONY: smoke-geometry-db
smoke-geometry-db:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke-geometry-db" && exit 1)
	@SUPA_URL=${SUPABASE_REST_URL:-${SUPA_REST_URL:-http://localhost:3000}} ; \
	 CONST_ID=8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111 ; \
	 echo "[1/3] GET $SUPA_URL/constellations?id=eq.$CONST_ID" ; \
	 curl -sf "$SUPA_URL/constellations" --get --data-urlencode "id=eq.$CONST_ID" --data-urlencode "select=id,summary,meta" | jq -e 'length==1' >/dev/null && echo OK || (echo FAIL && exit 1) ; \
	 echo "[2/3] GET $SUPA_URL/shape_points?constellation_id=eq.$CONST_ID" ; \
	 curl -sf "$SUPA_URL/shape_points" --get --data-urlencode "constellation_id=eq.$CONST_ID" --data-urlencode "select=id,modality,ref_id,t_start,t_end,proj,conf" | jq -e 'map(select(.modality=="video"))|length>=1' >/dev/null && echo OK || (echo FAIL && exit 1) ; \
	 echo "[3/3] GET $SUPA_URL/shape_index?shape_id=eq.$CONST_ID" ; \
	 curl -sf "$SUPA_URL/shape_index" --get --data-urlencode "shape_id=eq.$CONST_ID" --data-urlencode "select=loc_hash,meta" | jq -e 'length>=2' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "Geometry DB smoke passed."

.PHONY: codebook-gen
codebook-gen:
	@if [ -z "$(FILE)" ]; then echo "Usage: make codebook-gen FILE=/abs/source.jsonl OUT=datasets/structured_dataset.jsonl"; exit 1; fi
	@python tools/chit_codebook_gen.py $(FILE) $(OUT)

.PHONY: mcp-agent-zero
mcp-agent-zero:
	@AGENT_FORM=$${FORM:-POWERFULMOVES} python services/agent-zero/mcp_server.py

.PHONY: mcp-archon
mcp-archon:
	@ARCHON_FORM=$${FORM:-POWERFULMOVES} python services/archon/mcp_server.py

.PHONY: mesh-up
mesh-up:
	docker compose --profile agents --profile data up -d nats mesh-agent

.PHONY: mesh-handshake
mesh-handshake:
	@if [ -z "$(FILE)" ]; then echo "Usage: make mesh-handshake FILE=cgp.json"; exit 1; fi
	@python tools/publish_handshake.py $(FILE)

## ---- PMOVES.YT ----
.PHONY: yt-smoke
yt-smoke:
	@echo "[YT] Health check" && curl -sf http://localhost:8077/healthz >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[YT] Ingest sample" && curl -sS -X POST http://localhost:8077/yt/ingest -H 'content-type: application/json' -d '{"url":"https://www.youtube.com/watch?v=2Vv-BfVoq4g","namespace":"pmoves","bucket":"assets"}' | jq -e '.ok==true' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[YT] Summarize (ollama default)" && curl -sS -X POST http://localhost:8077/yt/summarize -H 'content-type: application/json' -d '{"video_id":"2Vv-BfVoq4g","style":"short"}' | jq -e '.ok==true' >/dev/null && echo OK || (echo "WARN: summarization skipped" )

.PHONY: yt-emit-smoke
yt-emit-smoke:
	@if [ -z "$(URL)" ]; then echo "Usage: make yt-emit-smoke URL=<youtube_url>"; exit 1; fi
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "[YT] Info" && curl -sS -X POST http://localhost:8077/yt/info -H 'content-type: application/json' -d '{"url":"$(URL)"}' | tee .tmp_info.json >/dev/null
	@VID=$$(jq -r '.info.id' .tmp_info.json); echo "VIDEO=$$VID"; \
	  echo "[YT] Ingest" && curl -sS -X POST http://localhost:8077/yt/ingest -H 'content-type: application/json' -d '{"url":"$(URL)","namespace":"pmoves","bucket":"assets"}' | jq -e '.ok==true' >/dev/null && echo OK || (echo FAIL && exit 1); \
	  echo "[YT] Emit (chunks+CGP)" && curl -sS -X POST http://localhost:8077/yt/emit -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\",\"namespace\":\"pmoves\"}" | tee .tmp_emit.json | jq -e '.ok==true and .chunks>=1 and (.upserted|tonumber) >= 1' >/dev/null && echo OK || (echo FAIL && exit 1); \
	  echo "[YT] Profile (if autotune)" && jq -r '.profile // "(none)"' .tmp_emit.json; \
	  echo "[Geometry] Jump point 0" && curl -sS http://localhost:8087/shape/point/p:yt:$$VID:0/jump | jq -e ".locator.modality==\"video\" and .locator.ref_id==\"$${VID}\"" >/dev/null && echo OK || (echo FAIL && exit 1); \
	  rm -f .tmp_info.json

.PHONY: yt-playlist-smoke
yt-playlist-smoke:
	@if [ -z "$(URL)" ]; then echo "Usage: make yt-playlist-smoke URL=<playlist_or_channel_url>"; exit 1; fi
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "[YT] Playlist start" && curl -sS -X POST http://localhost:8077/yt/playlist -H 'content-type: application/json' -d '{"url":"$(URL)","namespace":"pmoves","bucket":"assets","max_videos":3}' | tee .tmp_playlist.json >/dev/null
	@JOB=$$(jq -r '.job_id // empty' .tmp_playlist.json); if [ -z "$$JOB" ]; then echo "No job_id returned"; exit 1; fi; echo JOB=$$JOB; \
	  echo "[YT] Poll yt_items for job (up to 10x)"; \
	  for i in $$(seq 1 10); do \
	    sleep 6; \
	    curl -s "http://localhost:3000/yt_items?job_id=eq.$$JOB&select=video_id,status&order=created_at.asc" | tee .tmp_items.json >/dev/null; \
	    CNT=$$(jq 'length' .tmp_items.json); \
	    if [ "$$CNT" -ge 1 ]; then echo "items=$$CNT"; break; fi; \
	    echo "retry $$i"; \
	  done; \
	  VID=$$(jq -r 'map(select(.status=="completed")) | .[0].video_id // empty' .tmp_items.json); \
	  if [ -z "$$VID" ]; then VID=$$(jq -r '.[0].video_id // empty' .tmp_items.json); fi; \
	  if [ -z "$$VID" ]; then echo "No video_id found in yt_items"; exit 1; fi; echo VIDEO=$$VID; \
	  echo "[YT] Emit (chunks+CGP)" && curl -sS -X POST http://localhost:8077/yt/emit -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\",\"namespace\":\"pmoves\"}" | tee .tmp_emit.json | jq -e '.ok==true and .chunks>=1 and (.upserted|tonumber) >= 1' >/dev/null && echo OK || (echo FAIL && exit 1); \
	  echo "[Geometry] Jump point 0" && curl -sS http://localhost:8087/shape/point/p:yt:$$VID:0/jump | jq -e '.locator.modality=="video" and .locator.ref_id==$$VID' >/dev/null && echo OK || (echo FAIL && exit 1); \
	  rm -f .tmp_playlist.json .tmp_items.json .tmp_emit.json

.PHONY: web-geometry
web-geometry:
	@echo "Opening http://localhost:8087/geometry/ ..."
	@if [ "$(OS)" = "Windows_NT" ]; then \
		start "" http://localhost:8087/geometry/ ; \
	else \
		xdg-open http://localhost:8087/geometry/ 2>/dev/null || open http://localhost:8087/geometry/ ; \
	fi
	@$(MAKE) smoke-geometry

.PHONY: discord-smoke
discord-smoke:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "[Discord] Health" && curl -sf http://localhost:8092/healthz | jq -e '.ok==true' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[Discord] Publish test" && curl -sS -X POST http://localhost:8092/publish -H 'content-type: application/json' -d '{"content":"PMOVES test ping"}' | jq -e '.ok==true' >/dev/null && echo OK || (echo FAIL && exit 1)

.PHONY: jellyfin-smoke
jellyfin-smoke:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "[Jellyfin] Health" && curl -sf http://localhost:8093/healthz | jq -e '.ok==true' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[Jellyfin] Playback URL for latest video" && VID=$$(curl -s 'http://localhost:3000/videos?order=id.desc&select=video_id&limit=1' | jq -r '.[0].video_id // empty'); \
	if [ -z "$$VID" ]; then echo "No videos found in Supabase; run yt-emit-smoke first"; exit 0; fi; \
	curl -sS -X POST http://localhost:8093/jellyfin/playback-url -H 'content-type: application/json' -d "{\"video_id\":\"$$VID\",\"t\":5}" | jq -e '.ok==true and (.url|length)>0' >/dev/null && echo OK || (echo FAIL && exit 1)
.PHONY: demo-content-published
demo-content-published:
	@which jq >/dev/null 2>&1 || (echo "jq is required for demo-content-published" && exit 1)
	@URL=$${AGENT_ZERO_BASE_URL:-http://localhost:8080}; \
	FILE=$${FILE:-pmoves/contracts/samples/content.published.v1.sample.json}; \
	[ -f "$$FILE" ] || (echo "Sample file not found: $$FILE" && exit 1); \
	jq -c '{topic:"content.published.v1", payload:.}' "$$FILE" | \
	curl -s -X POST "$$URL/events/publish" -H 'content-type: application/json' --data-binary @- | jq .

.PHONY: health-publisher-discord
health-publisher-discord:
	@echo "Checking publisher-discord on http://localhost:8094/healthz" && \
	curl -sf http://localhost:8094/healthz | jq .

.PHONY: health-agent-zero
health-agent-zero:
	@echo "Checking Agent Zero on http://localhost:8080/healthz" && \
	curl -sf http://localhost:8080/healthz | jq .

.PHONY: health-jellyfin-bridge
health-jellyfin-bridge:
	@echo "Checking Jellyfin Bridge on http://localhost:8093/healthz" && \
	curl -sf http://localhost:8093/healthz | jq .

.PHONY: m2-preflight
m2-preflight:
	@which jq >/dev/null 2>&1 || (echo "jq is required for m2-preflight" && exit 1)
	@echo "[1/3] Agent Zero health" && curl -sf http://localhost:8080/healthz | jq .
	@echo "[2/3] Publisher-Discord health" && curl -sf http://localhost:8094/healthz | jq .
	@echo "[3/3] Discord webhook ping (if configured)" && \
	if [ -n "$$DISCORD_WEBHOOK_URL" ]; then \
	  MSG="PMOVES Preflight: $(shell date +%F-%T)" ./pmoves/scripts/discord_ping.sh "PMOVES M2 preflight ping" >/dev/null || true; \
	  echo "Ping attempted (check Discord)"; \
	else \
	  echo "DISCORD_WEBHOOK_URL not set; skipping ping"; \
	fi

.PHONY: venv
venv:
	@if [ "$(OS)" = "Windows_NT" ]; then \
		pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/create_venv.ps1 ; \
	else \
		bash pmoves/scripts/create_venv.sh ; \
	fi

.PHONY: venv-min
venv-min:
	@if [ "$(OS)" = "Windows_NT" ]; then \
		pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/create_venv_min.ps1 ; \
	else \
		bash pmoves/scripts/create_venv_min.sh ; \
	fi

.PHONY: win-bootstrap
win-bootstrap:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/windows_bootstrap.ps1

.PHONY: evidence-stamp
evidence-stamp:
	@./pmoves/tools/evidence_stamp.sh "$${LABEL:-evidence}" "$${EXT:-png}"

.PHONY: evidence-stamp-ps
evidence-stamp-ps:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/tools/evidence_stamp.ps1 -Label "$(LABEL)" -Ext "$(EXT)"

.PHONY: evidence-log
evidence-log:
	@./pmoves/tools/evidence_log.sh "$(LABEL)" "$(PATH)" "$(NOTE)"

.PHONY: evidence-log-ps
evidence-log-ps:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/tools/evidence_log.ps1 -Label "$(LABEL)" -Path "$(PATH)" -Note "$(NOTE)"

.PHONY: m2-seed-demo
m2-seed-demo:
	@echo "[M2] Running preflight + seeding demo row..."
	$(MAKE) m2-preflight || true
	$(MAKE) seed-approval TITLE="$(TITLE)" URL="$(URL)" NAMESPACE="$(NAMESPACE)"
	@echo "Next: Activate n8n workflows (poller then echo publisher) and verify Discord."

.PHONY: n8n-webhook-demo
n8n-webhook-demo:
	@which jq >/dev/null 2>&1 || (echo "jq is required for n8n-webhook-demo" && exit 1)
	@URL=$${URL:-http://localhost:5678/webhook/pmoves/content-published}; \
	FILE=$${FILE:-pmoves/contracts/samples/content.published.v1.sample.json}; \
	[ -f "$$FILE" ] || (echo "Sample file not found: $$FILE" && exit 1); \
	jq -c '{topic:"content.published.v1", payload:.}' "$$FILE" | \
	curl -s -X POST "$$URL" -H 'content-type: application/json' --data-binary @- | jq .

.PHONY: seed-approval
seed-approval:
	@TITLE="$${TITLE:-Demo}"; URL="$${URL:-s3://outputs/demo/example.png}"; NS="$${NAMESPACE:-$${INDEXER_NAMESPACE:-pmoves}}"; \
	echo "Seeding studio_board: title='$${TITLE}', url='$${URL}', namespace='$${NS}'"; \
	./pmoves/tools/seed_studio_board.sh "$${TITLE}" "$${URL}" "$${NS}"

.PHONY: seed-approval-ps
seed-approval-ps:
	@pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/tools/seed_studio_board.ps1 -Title "$(TITLE)" -Url "$(URL)" -Namespace "$(NAMESPACE)"
