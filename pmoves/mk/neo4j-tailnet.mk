# mk/neo4j-tailnet.mk — the tailnet forwarder that fronts Neo4j (#3201, option A)
# ===========================================================================
# Neo4j stays internal-only; fleet AGInTs reach bolt (tcp:7687) over the
# tailnet through docker-compose.neo4j-tailnet.yml. Same overlay shape as
# mk/egress.mk. No target here nests make.
#
# up-neo4j-tailnet NEVER recreates Neo4j: it runs with --no-deps, and refuses
# unless the running pmoves-neo4j is already attached to pmoves_graph_front
# (which only a deliberate, gated Neo4j recreate does -- see #3201's runbook).

NEO4J_TAILNET_COMPOSE := docker-compose.neo4j-tailnet.yml

.PHONY: up-neo4j-tailnet neo4j-tailnet-status down-neo4j-tailnet

up-neo4j-tailnet: ## Start the tailnet forwarder that fronts Neo4j (tcp:7687 -> neo4j:7687); never recreates Neo4j
	@# Preflight 1 (names only): the live pmoves-neo4j must already be on the graph front.
	@nets=$$(docker inspect --type container -f '{{range $$k, $$v := .NetworkSettings.Networks}}{{$$k}} {{end}}' pmoves-neo4j 2>/dev/null) || { \
		echo "[neo4j-tailnet] REFUSING: container pmoves-neo4j not found; bring Neo4j up first." >&2; exit 1; }; \
	case " $$nets " in \
		*" pmoves_graph_front "*) ;; \
		*) echo "[neo4j-tailnet] REFUSING: pmoves-neo4j is not attached to pmoves_graph_front." >&2; \
		   echo "  Recreate Neo4j first, as its own gated step (#3201 runbook), then re-run this." >&2; exit 1;; \
	esac
	@# Preflight 2: `config -q` validates quietly; it trips the overlay's own key
	@# guard when the dedicated key was not delivered, and never prints the key.
	@$(DC) -f $(NEO4J_TAILNET_COMPOSE) config -q || { \
		echo "[neo4j-tailnet] overlay does not validate; if it names the dedicated key, delivering it is an operator step (#3201)" >&2; \
		exit 1; }
	@# --no-deps: never let depends_on recreate Neo4j from here.
	@$(DC) -f $(NEO4J_TAILNET_COMPOSE) up -d --no-deps neo4j-tailnet

neo4j-tailnet-status: ## Show the forwarder's tailnet status and its serve (forward) config
	@docker exec pmoves-neo4j-tailnet tailscale status --peers=false || true
	@docker exec pmoves-neo4j-tailnet tailscale serve status || true

down-neo4j-tailnet: ## Stop and remove the forwarder (Neo4j itself is untouched)
	@$(DC) -f $(NEO4J_TAILNET_COMPOSE) stop neo4j-tailnet
	@# A stopped container needs no force; "no such container" is fine.
	@docker container rm pmoves-neo4j-tailnet >/dev/null 2>&1 || true
