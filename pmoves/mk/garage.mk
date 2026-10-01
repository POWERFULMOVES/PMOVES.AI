# garage.mk -- Garage storage node for the JuiceFS pmoves-media object store.
# Plan: docs/architecture/JUICEFS_GARAGE_MIGRATION_PLAN.md (§1.3, §6.1, Step a).
#
#   make -C pmoves garage-render GARAGE_TIER=1|2 [GARAGE_PEERS=<file>]
#       Render config/garage/rendered/garage.toml for THIS node (gitignored).
#       Tier 1 (always-on) gets lmdb, tier 2 (desktop) gets sqlite.
#   make -C pmoves garage-preflight
#       Stat (never read) the three secret files: present, non-empty, owned by
#       GARAGE_UID, and no group/other bits, which Garage refuses at boot.
#   make -C pmoves up-garage / garage-status / down-garage
#
# Per-node inputs (environment or the node's gitignored overrides, never committed):
#   GARAGE_DATA_ROOT     host dir holding meta/ data/ snapshots/ (e.g. the NVMe1 seat)
#   GARAGE_SECRETS_DIR   host dir with the funnel-delivered secret files
#   GARAGE_UID/GID       owner of both; the container runs as this user
#   GARAGE_IMAGE_DIGEST  sha256 of the fork-built manifest list (PMOVES-garage CI)
#
# Operator-only, never from these targets: `garage key create` (prints a
# secret), `garage admin-token create` (prints a token), `garage layout apply`.

GARAGE_COMPOSE := docker-compose.garage.yml
GARAGE_RENDER  := python3 tools/garage_render_config.py
GARAGE_TIER    ?=
GARAGE_PEERS   ?=
GARAGE_SECRETS_DIR ?= $(or $(CHIT_VAULT),./secrets)/garage
GARAGE_UID     ?= $(shell id -u)
GARAGE_GID     ?= $(shell id -g)
# The preflight and the container must see the SAME dir and uid.
GARAGE_ENV     := GARAGE_SECRETS_DIR="$(GARAGE_SECRETS_DIR)" GARAGE_UID="$(GARAGE_UID)" GARAGE_GID="$(GARAGE_GID)"

.PHONY: garage-render garage-preflight up-garage garage-status down-garage

garage-render: ## Render this node's Garage config (GARAGE_TIER=1|2, optional GARAGE_PEERS=<file>)
	@test -n "$(GARAGE_TIER)" || { echo "[garage] set GARAGE_TIER=1 (always-on, lmdb) or 2 (desktop, sqlite)" >&2; exit 1; }
	@$(GARAGE_RENDER) render --tier "$(GARAGE_TIER)" $(if $(GARAGE_PEERS),--peers "$(GARAGE_PEERS)")

garage-preflight: ## Check the Garage secret files' presence, owner and 0600 mode (never reads them)
	@$(GARAGE_RENDER) check-secrets --dir "$(GARAGE_SECRETS_DIR)" --uid "$(GARAGE_UID)"

up-garage: garage-preflight ## Start this node's Garage (requires a rendered config and the preflight)
	@test -f config/garage/rendered/garage.toml || { \
		echo "[garage] REFUSING: no rendered config; run garage-render first." >&2; exit 1; }
	@# `config -q` trips the overlay's own :? guards (digest, data root, uid)
	@# without printing any value.
	@$(GARAGE_ENV) $(DC) -f $(GARAGE_COMPOSE) config -q || { \
		echo "[garage] overlay does not validate; check GARAGE_IMAGE_DIGEST, GARAGE_DATA_ROOT, GARAGE_UID/GID" >&2; exit 1; }
	@$(GARAGE_ENV) $(DC) -f $(GARAGE_COMPOSE) up -d --no-deps garage

garage-status: ## Show Garage cluster status from this node (node ids and addresses; no secrets)
	@docker exec pmoves-garage /garage status

down-garage: ## Stop and remove this node's Garage container (data on GARAGE_DATA_ROOT is untouched)
	@$(DC) -f $(GARAGE_COMPOSE) stop garage
	@docker container rm pmoves-garage >/dev/null 2>&1 || true
