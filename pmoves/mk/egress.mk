# mk/egress.mk — YT egress routing via Tailscale exit node (Phase 9Q)
# ===========================================================================
#
# Make targets that toggle outbound routing of pmoves-yt, bgutil-pot-provider,
# invidious-companion, and invidious through a Tailscale exit node.
#
# IMPORTANT (2026-07-28 discovery): YouTube datacenter IPs get FLAGGED by
# YouTube's bot detection. Residential IPs work. The egress sidecar is kept
# as an optional fallback, but the DEFAULT for YT download traffic should be
# host-direct (residential). See YT_EGRESS_RUNBOOK.md § "Direct vs Egress".
#
# Two mechanisms:
#   1. Host-level exit node: `tailscale set --exit-node=<node>` (affects ALL traffic)
#   2. Container sidecar: docker-compose.yt-egress.yml (opt-in per-container proxy)
#
# See pmoves/docs/operations/YT_EGRESS_RUNBOOK.md for full operator guide.

YT_EGRESS_COMPOSE := docker-compose.yt-egress.yml
YT_EGRESS_SERVICES := pmoves-yt bgutil-pot-provider invidious-companion invidious
YT_EGRESS_EXIT_HOST := pmoves-kvm4-1

.PHONY: up-yt-egress down-yt-egress yt-egress-preflight yt-egress-status yt-egress-verify yt-direct yt-egress-check

up-yt-egress: ensure-env-shared yt-egress-preflight ## Route YT services through KVM4-1 exit node
	@if [ -z "$${TAILSCALE_AUTHKEY:-}" ]; then \
		echo "ERROR: TAILSCALE_AUTHKEY not set in env.shared — egress sidecar cannot join tailnet." >&2; \
		echo "Fix: run 'make -C pmoves secrets-funnel' or set TAILSCALE_AUTHKEY manually." >&2; \
		exit 1; \
	fi
	@echo "[yt-egress] Starting Tailscale sidecar (tailscale-yt-egress)..."
	@$(DC) -f docker-compose.yml -f $(YT_EGRESS_COMPOSE) up -d tailscale-yt-egress
	@echo "[yt-egress] Waiting 20s for tailnet join + exit-node handshake..."
	@sleep 20
	@echo "[yt-egress] Recreating YT-facing services with proxy env..."
	@$(DC) -f docker-compose.yml -f $(YT_EGRESS_COMPOSE) up -d --force-recreate $(YT_EGRESS_SERVICES)
	@echo "[yt-egress] Activation complete. Verifying..."
	@$(MAKE) --no-print-directory yt-egress-verify

down-yt-egress: ## Stop egress sidecar, revert YT services to residential IP
	@echo "[yt-egress] Stopping sidecar..."
	@$(DC) -f $(YT_EGRESS_COMPOSE) stop tailscale-yt-egress 2>/dev/null || true
	@$(DC) -f $(YT_EGRESS_COMPOSE) rm -f tailscale-yt-egress 2>/dev/null || true
	@echo "[yt-egress] Recreating YT services without proxy env..."
	@$(DC) up -d --force-recreate $(YT_EGRESS_SERVICES)
	@echo "[yt-egress] Deactivation complete. Services now egress via host IP."

yt-direct: ## Ensure YT services use host-direct (residential) egress — clears host exit node
	@echo "[yt-direct] Clearing host-level Tailscale exit node (if set)..."
	@if command -v tailscale >/dev/null 2>&1; then \
		current=$$(tailscale status --json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('ExitNodeStatus',{}).get('TailscaleIPs',[''])[0])" 2>/dev/null || echo ""); \
		if [ -n "$$current" ] && [ "$$current" != "none" ]; then \
			tailscale set --exit-node=; \
			echo "[yt-direct] Host exit node cleared."; \
		else \
			echo "[yt-direct] No host exit node set — already direct."; \
		fi; \
	fi
	@echo "[yt-direct] Stopping container egress sidecar (if running)..."
	@$(DC) -f $(YT_EGRESS_COMPOSE) stop tailscale-yt-egress 2>/dev/null || true
	@$(DC) -f $(YT_EGRESS_COMPOSE) rm -f tailscale-yt-egress 2>/dev/null || true
	@echo "[yt-direct] Recreating YT services with direct egress..."
	@$(DC) up -d --force-recreate $(YT_EGRESS_SERVICES) 2>/dev/null || true
	@echo "[yt-direct] Done. Verify with: make yt-egress-check"

yt-egress-check: ## Show current egress mode + test YouTube extraction
	@echo "=== Host exit node ==="
	@if command -v tailscale >/dev/null 2>&1; then \
		tailscale status --json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);ens=d.get('ExitNodeStatus',{});ip=ens.get('TailscaleIPs',['none']);print(f'Exit node: {ip[0] if ip else \"none\"}')" 2>/dev/null || echo "(tailscale not connected)"; \
	else echo "(tailscale CLI not found)"; fi
	@echo ""
	@echo "=== Container egress IP ==="
	@yt_container=$$(docker ps -q --filter "name=pmoves-pmoves-yt" 2>/dev/null | head -1); \
	if [ -n "$$yt_container" ]; then \
		docker exec $$yt_container python3 -c "import requests;print(requests.get('https://api.ipify.org',timeout=5).text)" 2>/dev/null || echo "(check failed)"; \
	else echo "(pmoves-yt not running)"; fi
	@echo ""
	@echo "=== Container proxy env ==="
	@yt_container=$$(docker ps -q --filter "name=pmoves-pmoves-yt" 2>/dev/null | head -1); \
	if [ -n "$$yt_container" ]; then \
		docker exec $$yt_container python3 -c "import os;print('HTTP_PROXY:',os.getenv('HTTP_PROXY','(empty)'));print('HTTPS_PROXY:',os.getenv('HTTPS_PROXY','(empty)'))" 2>/dev/null || echo "(check failed)"; \
	else echo "(pmoves-yt not running)"; fi

yt-egress-preflight: ## Verify KVM4-1 is advertising exit node before activating
	@echo "[yt-egress] Preflight: checking $(YT_EGRESS_EXIT_HOST) Tailscale exit-node advertisement..."
	@if command -v tailscale >/dev/null 2>&1; then \
		status_json=$$(tailscale status --json 2>/dev/null); \
		if [ -z "$$status_json" ]; then \
			echo "ERROR: tailscale CLI installed but not connected to tailnet." >&2; \
			exit 1; \
		fi; \
		if echo "$$status_json" | grep -q '"ExitNodeOption": *true' && \
		   echo "$$status_json" | grep -B2 '"ExitNodeOption": *true' | grep -q '$(YT_EGRESS_EXIT_HOST)'; then \
			echo "[yt-egress] $(YT_EGRESS_EXIT_HOST) is advertising as exit node."; \
		else \
			echo "ERROR: $(YT_EGRESS_EXIT_HOST) not advertising exit-node option." >&2; \
			echo "Fix: ssh $(YT_EGRESS_EXIT_HOST) 'sudo tailscale set --advertise-exit-node' and approve in Tailscale admin UI." >&2; \
			echo "See pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md (2026-04-12 4090-CLAUDE entry) for setup history." >&2; \
			exit 1; \
		fi; \
	else \
		echo "[yt-egress] (host tailscale CLI not available; preflight skipped — sidecar will attempt connection)"; \
	fi

yt-egress-status: ## Show Tailscale sidecar status + current YT egress IPs
	@echo "--- Tailscale sidecar status ---"
	@docker exec pmoves-tailscale-yt-egress tailscale status --peers=false 2>/dev/null \
		|| echo "[yt-egress] Sidecar not running."
	@echo
	@echo "--- YT service container states ---"
	@docker ps --filter "name=pmoves-yt" --filter "name=bgutil-pot-provider" \
		--filter "name=invidious-companion" --filter "name=invidious" \
		--filter "name=tailscale-yt-egress" \
		--format "table {{.Names}}\t{{.Status}}" 2>&1 | head -10

yt-egress-verify: ## Compare host IP vs PMOVES.YT egress IP + test-ingest reference video (fails on error)
	@set -e; \
	yt_container=$$($(DC) -f docker-compose.yml -f $(YT_EGRESS_COMPOSE) ps -q pmoves-yt 2>/dev/null | head -1); \
	if [ -z "$$yt_container" ]; then \
		echo "ERROR: pmoves-yt container not running. Activate first via 'make -C pmoves up-yt-egress'." >&2; \
		exit 1; \
	fi; \
	echo "--- Host IP (residential baseline) ---"; \
	host_ip=$$(curl -sf --max-time 5 https://api.ipify.org); \
	echo "$$host_ip"; \
	echo; \
	echo "--- PMOVES.YT container egress IP (expected: $(YT_EGRESS_EXIT_HOST) / Hostinger range) ---"; \
	container_ip=$$(docker exec $$yt_container sh -c 'wget -qO- --timeout=10 https://api.ipify.org 2>/dev/null'); \
	if [ -z "$$container_ip" ]; then \
		echo "ERROR: pmoves-yt IP check failed — container reachable but no egress IP returned." >&2; \
		exit 1; \
	fi; \
	echo "$$container_ip"; \
	if [ "$$host_ip" = "$$container_ip" ]; then \
		echo "ERROR: container IP matches host IP — egress proxy is NOT active." >&2; \
		exit 1; \
	fi; \
	echo; \
	echo "--- Test ingest (dQw4w9WgXcQ, short known-good video) ---"; \
	response=$$(curl -sf --max-time 30 -X POST http://localhost:8077/yt/ingest \
		-H 'Content-Type: application/json' \
		-d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'); \
	echo "$$response" | head -c 500; \
	echo

# ---------------------------------------------------------------------------
# Community-mesh egress A/B + capacity planner (Fordham Hill pilot tooling).
# Portable node-level probe: measure what an exit node buys a household vs the
# raw local uplink, and map participating homes onto measured node capacity.
# Script: deploy/provision/mesh-egress-ab.sh (curl+awk; adds tailscale for `ab`).
# Runbook: pmoves/docs/operations/MESH_EGRESS_AB_RUNBOOK.md
# ---------------------------------------------------------------------------
MESH_AB := ../deploy/provision/mesh-egress-ab.sh

.PHONY: mesh-egress-ab mesh-egress-measure mesh-capacity

mesh-egress-ab: ## Auto A/B: direct vs every approved exit node (needs tailscale CLI; self-restoring)
	@bash $(MESH_AB) ab $(ARGS)

mesh-egress-measure: ## Measure CURRENT egress only (portable; e.g. ARGS='--label starlink-direct --save snap.json')
	@bash $(MESH_AB) measure $(ARGS)

mesh-capacity: ## Map homes onto node capacity: make mesh-capacity DOWN=845 HOMES=200
	@bash $(MESH_AB) capacity --down $(or $(DOWN),845) $(if $(HOMES),--homes $(HOMES),) $(ARGS)

# On-VPS exit-node observer — solo-operator pilot observation (no agent on any home).
# Pairs with Hostinger MCP (VM CPU/RAM/bandwidth, agent-free) for the full picture.
EXIT_OBS := ../deploy/provision/exit-node-observer.sh

.PHONY: exit-node-observe
exit-node-observe: ## Run the on-VPS observer on a node: make exit-node-observe NODE=pmoves-kvm4-1 [FMT=--json|--prom]
	@cat $(EXIT_OBS) | ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes root@$(or $(NODE),pmoves-kvm4-1) \
		'cat > /tmp/exit-node-observer.sh && bash /tmp/exit-node-observer.sh $(or $(FMT),human)'

# CONTINUOUS obs: install node_exporter + textfile collector + both metric-writer
# timers (native tailscale metrics + the pmoves observer) so Grafana is actually fed.
# Runbook + unit files: pmoves/monitoring/prometheus/tailscale-textfile-collector.md
OBS_INSTALL := ../deploy/provision/install-exit-node-obs.sh

.PHONY: exit-node-obs-install
exit-node-obs-install: ## Deploy continuous exit-node obs to a node: make exit-node-obs-install NODE=pmoves-kvm4-2 [BW_CAP_TB=8]
	@node="$(or $(NODE),pmoves-kvm4-2)"; \
	echo "[obs-install] staging installer + observer on $$node ..."; \
	ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes root@$$node 'mkdir -p /opt/pmoves-obs-stage'; \
	scp -o StrictHostKeyChecking=accept-new -o BatchMode=yes \
		$(OBS_INSTALL) $(EXIT_OBS) root@$$node:/opt/pmoves-obs-stage/; \
	ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes root@$$node \
		'chmod +x /opt/pmoves-obs-stage/*.sh && BW_CAP_TB=$(or $(BW_CAP_TB),16) bash /opt/pmoves-obs-stage/install-exit-node-obs.sh'

# ---------------------------------------------------------------------------
# YouTube playlist metadata crawl via Data API v3 (IP-agnostic).
# Crawls all videos in a playlist and stores metadata in Supabase.
# Script: pmoves/tools/yt_playlist_crawl.py (runs inside pmoves-yt container).
# ---------------------------------------------------------------------------

YT_PLAYLIST_ID ?= PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8
YT_CRAWL_NAMESPACE ?= darkxside

.PHONY: yt-playlist-crawl yt-playlist-ingest-stats

yt-playlist-crawl: ## Crawl YouTube playlist metadata via Data API: make yt-playlist-crawl [YT_PLAYLIST_ID=...] [YT_CRAWL_NAMESPACE=...]
	@if ! docker ps --format '{{.Names}}' | grep -q '^pmoves-pmoves-yt-1$$'; then \
		echo "ERROR: pmoves-yt container not running. Start with 'make -C pmoves up'." >&2; \
		exit 1; \
	fi
	@echo "[yt-crawl] Copying crawl script to container..."
	@docker cp tools/yt_playlist_crawl.py pmoves-pmoves-yt-1:/app/yt_playlist_crawl.py
	@echo "[yt-crawl] Starting playlist crawl (playlist: $(YT_PLAYLIST_ID), namespace: $(YT_CRAWL_NAMESPACE))..."
	@# Write secrets to a temporary env-file to avoid leaking via /proc/pid/cmdline
	@tmpenv=$$(mktemp); \
	echo "SUPA_REST_URL=$${SUPA_REST_URL:-http://supabase-kong:8000}" > $$tmpenv; \
	echo "SUPABASE_SERVICE_ROLE_KEY=$$(grep SUPABASE_SERVICE_ROLE_KEY env.tier-agent 2>/dev/null | cut -d= -f2)" >> $$tmpenv; \
	echo "GOOGLE_CLIENT_ID=$$(grep CHANNEL_MONITOR_GOOGLE_CLIENT_ID env.tier-agent 2>/dev/null | cut -d= -f2)" >> $$tmpenv; \
	echo "GOOGLE_CLIENT_SECRET=$$(grep CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET env.tier-agent 2>/dev/null | cut -d= -f2)" >> $$tmpenv; \
	docker exec --env-file /dev/stdin pmoves-pmoves-yt-1 python3 /app/yt_playlist_crawl.py \
		--playlist "$(YT_PLAYLIST_ID)" \
		--namespace "$(YT_CRAWL_NAMESPACE)" < $$tmpenv; \
	rm -f $$tmpenv

# Renamed from yt-playlist-stats: it collided with the enrichment-stats target
# below (line ~262) and make silently kept the LAST definition, so this INGESTION
# query was unreachable. Distinct names now — this one answers "did the crawl
# land rows?", the other answers "how are those rows classified?".
yt-playlist-ingest-stats: ## Show crawled video ingestion stats from Supabase (row counts, downloaded, durations)
	@if ! docker ps --format '{{.Names}}' | grep -q '^pmoves-supabase-db-1$$'; then \
		echo "ERROR: Supabase DB container not running." >&2; \
		exit 1; \
	fi
	@echo "=== YouTube Playlist Video Stats ==="
	@docker exec -e PGPASSWORD=$$(grep POSTGRES_PASSWORD env.tier-data 2>/dev/null | cut -d= -f2) \
		pmoves-supabase-db-1 psql -U supabase_admin -d postgres -c "
		SET search_path TO pmoves_core;
		SELECT count(*) AS total, count(DISTINCT video_id) AS unique_videos,
		       count(*) FILTER (WHERE downloaded) AS downloaded,
		       count(*) FILTER (WHERE duration_seconds > 0) AS with_duration
		FROM youtube_videos;
		SELECT
		    CASE WHEN duration_seconds < 300 THEN 'short(<5m)'
		         WHEN duration_seconds < 1200 THEN 'medium(5-20m)'
		         WHEN duration_seconds < 3600 THEN 'long(20-60m)'
		         ELSE 'very_long(1h+)' END AS duration_bucket,
		    count(*) AS cnt
		FROM youtube_videos WHERE duration_seconds IS NOT NULL
		GROUP BY 1 ORDER BY cnt DESC;
	"

# ---------------------------------------------------------------------------
# DARKXSIDE Playlist Enrichment — resonance taxonomy + School of PowerfulMoves
# ---------------------------------------------------------------------------

.PHONY: yt-playlist-enrich yt-playlist-stats yt-playlist-curriculum yt-health-videos yt-wealth-videos

yt-playlist-enrich: ## Classify playlist videos by resonance domain + curriculum track
	@if ! docker ps --format '{{.Names}}' | grep -q '^pmoves-pmoves-yt-1$$'; then \
		echo "ERROR: pmoves-yt not running" >&2; exit 1; \
	fi
	@echo "[enrich] Copying enrichment script..."
	@docker cp tools/yt_playlist_enrich.py pmoves-pmoves-yt-1:/app/yt_playlist_enrich.py
	@echo "[enrich] Running classification (multi-pass for >500 videos)..."
	@for i in 1 2 3 4 5; do \
		docker exec \
			-e SUPA_REST_URL=http://supabase-kong:8000 \
			-e SUPABASE_SERVICE_ROLE_KEY=$$(grep SUPABASE_SERVICE_ROLE_KEY env.tier-agent 2>/dev/null | cut -d= -f2) \
			pmoves-pmoves-yt-1 python3 /app/yt_playlist_enrich.py 2>&1 | tail -2; \
	done

yt-playlist-stats: ## Show playlist enrichment statistics (resonance, curriculum, persona)
	@docker exec \
		-e SUPA_REST_URL=http://supabase-kong:8000 \
		-e SUPABASE_SERVICE_ROLE_KEY=$$(grep SUPABASE_SERVICE_ROLE_KEY env.tier-agent 2>/dev/null | cut -d= -f2) \
		pmoves-pmoves-yt-1 python3 /app/yt_playlist_enrich.py --stats

yt-playlist-curriculum: ## Show School of PowerfulMoves curriculum tracks
	@docker exec -e PGPASSWORD=$$(grep POSTGRES_PASSWORD env.tier-data 2>/dev/null | head -1 | cut -d= -f2) \
		pmoves-supabase-db-1 psql -U supabase_admin -d pmoves -c "
	SET search_path TO pmoves_core;
	SELECT curriculum_track, curriculum_subject, count(*) as videos,
	       round(avg(duration_seconds)/60,1) as avg_min,
	       count(*) FILTER (WHERE downloaded) as downloaded
	FROM youtube_videos WHERE curriculum_track IS NOT NULL
	GROUP BY curriculum_track, curriculum_subject ORDER BY videos DESC;
	"

yt-health-videos: ## Show health-tagged videos (nutrition, fitness, wellness)
	@docker exec -e PGPASSWORD=$$(grep POSTGRES_PASSWORD env.tier-data 2>/dev/null | head -1 | cut -d= -f2) \
		pmoves-supabase-db-1 psql -U supabase_admin -d pmoves -c "
	SET search_path TO pmoves_core;
	SELECT health_topic, count(*) as videos,
	       round(avg(duration_seconds)/60,1) as avg_min,
	       count(*) FILTER (WHERE downloaded) as downloaded
	FROM youtube_videos WHERE health_topic IS NOT NULL
	GROUP BY health_topic ORDER BY videos DESC;
	"

yt-wealth-videos: ## Show wealth-tagged videos (investing, entrepreneurship, budget)
	@docker exec -e PGPASSWORD=$$(grep POSTGRES_PASSWORD env.tier-data 2>/dev/null | head -1 | cut -d= -f2) \
		pmoves-supabase-db-1 psql -U supabase_admin -d pmoves -c "
	SET search_path TO pmoves_core;
	SELECT wealth_topic, count(*) as videos,
	       round(avg(duration_seconds)/60,1) as avg_min,
	       count(*) FILTER (WHERE view_count > 1000000) as viral
	FROM youtube_videos WHERE wealth_topic IS NOT NULL
	GROUP BY wealth_topic ORDER BY videos DESC;
	"

# ---------------------------------------------------------------------------
# Cross-node JuiceFS mount (mesh shared storage)
# Run on remote nodes to mount the shared JuiceFS media filesystem.
# ---------------------------------------------------------------------------

.PHONY: juicefs-cross-node-setup juicefs-mount-status juicefs-mount-local juicefs-storage-check

# MagicDNS hostname, not a literal Tailscale IP — committed files carry no IPs, and
# the DARKXSIDE room's own egress_redaction_floor lists no-literal-lan-or-tailscale-ips
# as a fail-closed rule. JUICEFS_HOST_IP is kept as a deprecated alias so existing
# invocations keep working; prefer JUICEFS_HOST.
JUICEFS_HOST ?= $(or $(JUICEFS_HOST_IP),pmoves-b850-ai-top)

juicefs-cross-node-setup: ## Mount JuiceFS on this node (run on remote): make juicefs-cross-node-setup JUICEFS_HOST=<hostname> DB_PASS=<supabase-db-pass>
	@JUICEFS_HOST=$(JUICEFS_HOST) DB_PASS=$(or $(DB_PASS),$(error DB_PASS required)) bash scripts/juicefs-cross-node-setup.sh

# The check that would have caught the cross-node blocker months earlier. Storage is
# baked into a volume at format time: "file" means the data blocks live on the
# formatting host's local disk, so no other node can read them no matter how the
# metadata is wired. See
# pmoves/docs/handoffs/juicefs-cross-node-storage-blocker-2026-08-04.md
juicefs-storage-check: ## Report the JuiceFS volume's storage backend (file = single-node!)
	@echo "=== JuiceFS volume storage backend ==="
	@docker exec juicefs-mount sh -c 'juicefs status "$$(tr "\0" "\n" < /proc/1/cmdline | grep -m1 -E "^(postgres|redis|mysql)://")" 2>/dev/null' 2>/dev/null \
	    | grep -iE '"(Name|Storage|Bucket)"' \
	    | sed -E 's#(://)[^/ "]*@#\1[REDACTED]@#g' \
	    || echo "  juicefs-mount not running — nothing to check"
	@echo "  NOTE: Storage:\"file\" means this volume is single-node by construction."

# Renamed from juicefs-status: it collided with the JuiceFS *PoC gateway* target
# in Makefile:292, and make kept that one — so this MOUNT check was unreachable
# and `make juicefs-status` on a mount node silently reported gateway state
# instead. Distinct names now: juicefs-status = S3 gateway PoC health,
# juicefs-mount-status = is the JuiceFS mount up and are content dirs visible.
juicefs-mount-status: ## Show JuiceFS mount status (mount container + content dirs)
	@echo "=== JuiceFS Mount ==="
	@# `docker ps` exits 0 with EMPTY output when nothing matches, so the old
	@# `|| echo "not running"` never fired and this target printed two blank
	@# headings on a node with no mount at all — indistinguishable from a healthy
	@# mount holding no dirs. Test the output, not the exit code.
	@out="$$(docker ps --filter name=juicefs-mount --format '{{.Names}} {{.Status}}' 2>/dev/null)"; \
	  if [ -n "$$out" ]; then echo "$$out"; \
	  else echo "  juicefs-mount NOT RUNNING on this node"; \
	       echo "  (z890 runs only the S3 gateway - see juicefs-cross-node-storage-blocker-2026-08-04.md)"; fi
	@echo ""
	@echo "=== Content Dirs ==="
	@dirs="$$(docker exec juicefs-mount find /mnt/media -maxdepth 2 -type d 2>/dev/null | sort)"; \
	  if [ -n "$$dirs" ]; then echo "$$dirs"; else echo "  mount not accessible / no dirs"; fi

juicefs-mount-local: ## Start JuiceFS mount on this node (local Supabase DB)
	@echo "Starting JuiceFS mount (local DB)..."
	$(eval JFS_HOST_HOME := $(HOME))
	$(eval JFS_MOUNT_POINT := $(JFS_HOST_HOME)/pmoves-fs)
	@mkdir -p "$(JFS_MOUNT_POINT)"
	@test -n "$(SUPABASE_DB_PASSWORD)" || { echo "ERROR: SUPABASE_DB_PASSWORD not set — source it from the CHIT secrets pipeline"; exit 1; }
	@# Per-host bounded cache flags: measure the /data volume's host backing dir so
	@# this node never inherits JuiceFS's 100 GiB default nor self-disables caching
	@# on a near-full disk. Canonical logic: scripts/juicefs-cache-bounds.sh.
	@# Fail-safe guards: make runs this via `sh -c` (no -e), so an empty-failure
	@# would chain straight into `docker run` with zero bounds. Refuse unbounded.
	@JFS_CACHE_FLAGS="$$(JFS_CACHE_DIR=/data/jfsCache JFS_CACHE_MEASURE_DIR='$(JFS_HOST_HOME)/.local/share/juicefs-data' bash scripts/juicefs-cache-bounds.sh)" || { echo "ERROR: cache-bounds helper failed"; exit 1; }; \
	test -n "$$JFS_CACHE_FLAGS" || { echo "ERROR: empty cache bounds — refusing unbounded mount"; exit 1; }; \
	META_PASSWORD='$(SUPABASE_DB_PASSWORD)' docker run -d \
	    --name juicefs-mount \
	    --restart unless-stopped \
	    --privileged \
	    --network host \
	    --entrypoint sh \
	    -e META_PASSWORD \
	    -e JFS_MOUNT="$(JFS_MOUNT_POINT)" \
	    -e JFS_CACHE_FLAGS="$$JFS_CACHE_FLAGS" \
	    -v $(JFS_HOST_HOME)/.local/share/juicefs-data:/data \
	    -v $(JFS_MOUNT_POINT):$(JFS_MOUNT_POINT):rshared \
	    juicedata/mount:ce-v1.3.0 \
	    -c 'exec juicefs mount --enable-xattr $$JFS_CACHE_FLAGS "postgres://supabase_admin@localhost:5432/postgres?search_path=juicefs_meta&sslmode=disable" "$$JFS_MOUNT"'
	@echo "Use 'make juicefs-mount-status' to verify"
