.PHONY: up down clean
up:
	docker compose --profile data up -d qdrant neo4j minio meilisearch postgres postgrest presign
	docker compose --profile workers up -d hi-rag-gateway-v2 retrieval-eval render-webhook langextract extract-worker

down:
	docker compose down

clean:
	docker compose down -v

.PHONY: up-legacy
up-legacy:
	docker compose --profile data up -d qdrant neo4j minio meilisearch presign
	docker compose --profile workers up -d hi-rag-gateway retrieval-eval render-webhook

.PHONY: smoke
smoke:
	@which jq >/dev/null 2>&1 || (echo "jq is required for smoke tests" && exit 1)
	@echo "[1/9] Qdrant ready..." && curl -sf http://localhost:6333/ready >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[2/9] Meilisearch ready..." && curl -sf http://localhost:7700/health >/dev/null && echo OK || (echo WARN: skipping; true)
	@echo "[3/9] Neo4j UI..." && curl -sf http://localhost:7474 >/dev/null && echo OK || (echo WARN: UI not reachable; true)
	@echo "[4/9] presign health..." && curl -sf http://localhost:8088/healthz >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[5/9] render-webhook health..." && curl -sf http://localhost:8085/healthz >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[6/9] PostgREST reachable..." && curl -sf http://localhost:3000 >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[7/9] Insert via render-webhook..." && curl -sf -X POST http://localhost:8085/comfy/webhook \
	 -H "Content-Type: application/json" \
	 -H "Authorization: Bearer $${RENDER_WEBHOOK_SHARED_SECRET:-change_me}" \
	 -d '{"bucket":"outputs","key":"demo.png","s3_uri":"s3://outputs/demo.png","presigned_get":null,"title":"Demo","namespace":"pmoves","author":"local","tags":["demo"],"auto_approve":false}' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[8/9] Verify studio_board row..." && curl -sf "http://localhost:3000/studio_board?order=id.desc&limit=1" | jq -e '.[0].title != null' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "[9/9] Hi-RAG v2 query..." && curl -sf localhost:8087/hirag/query -H 'content-type: application/json' -d '{"query":"what is pmoves?","namespace":"pmoves","k":3,"alpha":0.7}' | jq -e '.hits != null' >/dev/null && echo OK || (echo FAIL && exit 1)
	@echo "Smoke tests passed."

.PHONY: smoke-rerank
smoke-rerank:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "Request with rerank=true (may be disabled if model not available)"
	curl -s localhost:8087/hirag/query -H 'content-type: application/json' -d '{"query":"what is pmoves?","namespace":"pmoves","k":3,"alpha":0.7, "use_rerank": true}' | jq .
	@echo "If used_rerank=false, ensure internet/model access, or set RERANK_ENABLE=false."

.PHONY: eval-jsonl
eval-jsonl:
	@if [ -z "$(FILE)" ]; then echo "Usage: make eval-jsonl FILE=/abs/path/queries.jsonl [K=10]"; exit 1; fi
	docker compose build retrieval-eval
	docker compose run --rm --entrypoint python --volume "$(FILE):/data/queries.jsonl:ro" retrieval-eval /app/evaluate.py /data/queries.jsonl $(K)

.PHONY: smoke-presign-put
smoke-presign-put:
	@which jq >/dev/null 2>&1 || (echo "jq is required" && exit 1)
	@echo "Generating presign PUT and uploading a small text file..."
	@URL=$$(curl -s -X POST http://localhost:8088/presign/put -H 'content-type: application/json' -H "Authorization: Bearer $${PRESIGN_SHARED_SECRET:-change_me}" -d '{"bucket":"outputs","key":"hello.txt","content_type":"text/plain","expires":300}') && \
	 echo $$URL | jq -r '.url' | xargs -I {} sh -c "echo 'hello pmoves' | curl -s -X PUT -H 'Content-Type: text/plain' --data-binary @- '{}' >/dev/null" && echo OK || (echo FAIL && exit 1)

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

.PHONY: flight-check
flight-check:
	@if [ "$(OS)" = "Windows_NT" ]; then \
		pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1 ; \
	else \
		bash scripts/env_check.sh ; \
	fi

.PHONY: flight-check-retro
flight-check-retro:
	@echo "Installing retro flightcheck deps (uv preferred, fallback to pip)" && \
	( command -v uv >/dev/null 2>&1 && uv pip install -q -r tools/flightcheck/requirements.txt || python -m pip install -q -r tools/flightcheck/requirements.txt ) && \
	python tools/flightcheck/retro_flightcheck.py

.PHONY: preflight
preflight:
	@echo "Running PMOVES preflight checks..."
	@python tools/flightcheck/retro_flightcheck.py --quick || true
	@python tools/flightcheck/retro_flightcheck.py --theme neon --beep

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
	@echo "  smoke-langextract Extract chunks via langextract and load"
	@echo "  flight-check     Run environment preflight (deps, ports, .env)"
	@echo "  flight-check-retro Retro-styled Rich CLI preflight"
	@echo "  env-dedupe       Remove duplicate keys from .env (keeps last, writes .bak)"
	@echo "  logs-core        Tail core services (docker compose logs -f ...)"
	@echo "  setup            Run Codex/bootstrap env setup (make, conda deps)"
	@echo "  supabase-migrate Apply supabase/migrations/*.sql via docker compose"
	@echo "  smoke-geometry   Post a CGP, jump a point, decode text, and run calibration"
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
	docker compose --profile agents up -d nats mesh-agent

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
	  echo "[Geometry] Jump point 0" && curl -sS http://localhost:8087/shape/point/p:yt:$$VID:0/jump | jq -e '.locator.modality=="video" and .locator.ref_id==$$VID' >/dev/null && echo OK || (echo FAIL && exit 1); \
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
