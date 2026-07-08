# =============================================================================
# Kong Route Seeder -- PMOVES.AI
# =============================================================================
# Include in top-level Makefile:
#   include pmoves/mk/kong.mk
#
# Depends on:
#   - python3 with PyYAML installed
#   - Kong Admin API reachable at KONG_ADMIN_URL (default: http://localhost:8001)
#   - model-suit YAMLs in pmoves/configs/model-suits/*.yaml
#
# Environment:
#   KONG_ADMIN_URL   Kong Admin API base URL (default: http://localhost:8001)
# =============================================================================

KONG_ADMIN_URL ?= http://localhost:8001
SEEDER_SCRIPT  := pmoves/tools/kong_route_seeder.py
MODEL_SUITS_DIR := pmoves/configs/model-suits

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

.PHONY: kong-seed-routes kong-prune-routes kong-list-routes kong-reset-routes kong-health kong-list-services kong-help

## Seed Kong routes from model suits (idempotent)
kong-seed-routes: $(SEEDER_SCRIPT)
	@echo "[KONG] Seeding routes from $(MODEL_SUITS_DIR) ..."
	python3 $(SEEDER_SCRIPT) --kong-url $(KONG_ADMIN_URL) --model-suits-dir $(MODEL_SUITS_DIR)

## Seed Kong routes (dry-run -- shows what would be done)
kong-dry-run: $(SEEDER_SCRIPT)
	@echo "[KONG] Dry-run seeding routes from $(MODEL_SUITS_DIR) ..."
	python3 $(SEEDER_SCRIPT) --kong-url $(KONG_ADMIN_URL) --model-suits-dir $(MODEL_SUITS_DIR) --dry-run

## Remove routes for deleted model suits
kong-prune-routes: $(SEEDER_SCRIPT)
	@echo "[KONG] Pruning stale routes ..."
	python3 $(SEEDER_SCRIPT) --kong-url $(KONG_ADMIN_URL) --model-suits-dir $(MODEL_SUITS_DIR) --prune

## Seed + prune in one pass
kong-sync: $(SEEDER_SCRIPT)
	@echo "[KONG] Syncing routes (seed + prune) ..."
	python3 $(SEEDER_SCRIPT) --kong-url $(KONG_ADMIN_URL) --model-suits-dir $(MODEL_SUITS_DIR) --prune

## List all Kong routes via Admin API (handles pagination)
kong-list-routes:
	@echo "[KONG] Listing all routes ..."
	@python3 -c "import sys, json, urllib.request; \
		url = '$(KONG_ADMIN_URL)/routes'; \
		all_data = []; \
		while url: \
			data = json.loads(urllib.request.urlopen(url, timeout=10).read().decode()); \
			all_data.extend(data.get('data', [])); \
			url = data.get('next'); \
		json.dump({'data': all_data}, sys.stdout, indent=2)"
	@echo ""

## List all Kong services
kong-list-services:
	@echo "[KONG] Listing all services ..."
	@curl -s $(KONG_ADMIN_URL)/services | python3 -m json.tool 2>/dev/null || \
		echo "ERROR: Kong Admin API not reachable at $(KONG_ADMIN_URL)"

## Delete all auto-seeded routes and re-seed (DANGER)
## WARNING: Race condition -- routes may be re-created between delete and seed
## if another process intervenes. Use kong-sync for safe atomic updates.
kong-reset-routes: $(SEEDER_SCRIPT)
	@echo "[KONG] DANGER: This will delete all auto-seeded routes and re-create them."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo "[KONG] Deleting auto-seeded routes ..."
	@curl -s $(KONG_ADMIN_URL)/routes | python3 -c "import sys,json; [print(r['name']) for r in json.load(sys.stdin).get('data',[]) if 'auto-seeded' in (r.get('tags') or [])]" 2>/dev/null | \
		while read r; do echo "  Deleting route: $$r"; curl -s -X DELETE $(KONG_ADMIN_URL)/routes/$$r; done
	@echo "[KONG] Re-seeding ..."
	python3 $(SEEDER_SCRIPT) --kong-url $(KONG_ADMIN_URL) --model-suits-dir $(MODEL_SUITS_DIR)

## Check Kong Admin API health
kong-health:
	@echo "[KONG] Checking Admin API health ..."
	@curl -s -o /dev/null -w "%{http_code}" $(KONG_ADMIN_URL)/status | grep -q "200" && \
		echo "  Kong Admin API: OK" || \
		echo "  Kong Admin API: UNREACHABLE"

## Show Kong seeder help
kong-help: $(SEEDER_SCRIPT)
	python3 $(SEEDER_SCRIPT) --help
