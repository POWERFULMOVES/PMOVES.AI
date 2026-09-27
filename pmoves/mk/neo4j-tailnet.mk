# mk/neo4j-tailnet.mk — the tailnet forwarder that fronts Neo4j (#3201, option A)
# ===========================================================================
# Neo4j stays internal-only; fleet AGInTs reach bolt (tcp:7687) over the
# tailnet through docker-compose.neo4j-tailnet.yml. Same overlay shape as
# mk/egress.mk. No target here nests $(MAKE).

NEO4J_TAILNET_COMPOSE := docker-compose.neo4j-tailnet.yml

.PHONY: up-neo4j-tailnet neo4j-tailnet-status down-neo4j-tailnet

up-neo4j-tailnet: ## Start the tailnet forwarder that fronts Neo4j (tcp:7687 -> neo4j:7687)
	@# `config -q` validates quietly: it trips the overlay's own
	@# ${TAILSCALE_AUTHKEY:?...} guard when the key was not delivered, and never
	@# prints the key. (Compose reads the key from its --env-file list, not from
	@# this recipe's shell, so a shell-env check would be the wrong test.)
	@$(DC) -f $(NEO4J_TAILNET_COMPOSE) config -q || { \
		echo "[neo4j-tailnet] overlay does not validate; if it names TAILSCALE_AUTHKEY, run: make -C pmoves secrets-funnel" >&2; \
		exit 1; }
	@$(DC) -f $(NEO4J_TAILNET_COMPOSE) up -d neo4j-tailnet

neo4j-tailnet-status: ## Show the forwarder's tailnet status and its serve (forward) config
	@docker exec pmoves-neo4j-tailnet tailscale status --peers=false || true
	@docker exec pmoves-neo4j-tailnet tailscale serve status || true

down-neo4j-tailnet: ## Stop and remove the forwarder (Neo4j itself is untouched)
	@$(DC) -f $(NEO4J_TAILNET_COMPOSE) stop neo4j-tailnet
	@# A stopped container needs no force; "no such container" is fine.
	@docker container rm pmoves-neo4j-tailnet >/dev/null 2>&1 || true
