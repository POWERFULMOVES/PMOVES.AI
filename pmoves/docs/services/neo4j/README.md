# Neo4j — Graph DB

Status: Compose-managed (data plane)

Overview
- Optional entity/alias dictionary and graph features for Hi‑RAG.

Compose
- Service: `neo4j`
- Ports: `7474:7474`, `7687:7687`
- Profile: `data`
- Network: `pmoves-net`

Used by
- `hi-rag-gateway`, `hi-rag-gateway-v2` (entity boost, warm dictionary)
- Seeds in `pmoves/neo4j/cypher/*` (see NEXT_STEPS for alias plan)

Env (clients)
- `NEO4J_URL`, `NEO4J_USER`, `NEO4J_PASSWORD`

Health & troubleshooting
- Verify connectivity: `docker exec pmoves-neo4j-1 cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "RETURN 1"` returns `1`.
- Matching secrets: the first password you set is persisted under `neo4j-data/`; ensure `.env` / `.env.local` contain the same value or the container logs `authentication failure`.
- Warm dictionary sanity: the Hi‑RAG gateways now guard on `keys(e)` before reading `e.type`, so missing `type` properties no longer raise `UnknownPropertyKey` warnings. If you still see them, rebuild via `make recreate-v2` (and `make recreate-legacy` if using v1) to pick up the latest image.
- Reset (only if you intentionally want a clean graph): `docker compose --profile data rm -f -s -v neo4j` removes the volume; you must then rerun the seed cypher scripts.
- Full data bootstrap: `make bootstrap-data` runs the Supabase SQL, this Neo4j seed, and the Qdrant/Meili demo corpus in one shot after a fresh checkout or volume reset.

Make
- `make up` starts neo4j (with healthcheck) before v2.
- `make smoke` covers graph-warm and geometry checks.

## Geometry Bus (CHIT) Integration
- Role: Neo4j hosts the mind‑map alias graph used by CHIT for constellation context and UI drill‑downs.
- How it’s used:
  - v2 gateway warms entity aliases to improve retrieval and labels; mind‑map queries are exercised in `docs/SMOKETESTS.md` (Extended Deep Dive, Mindmap Graph).
  - Geometry UI can link to mind‑map data for constellation overlays.
- Not an HTTP CHIT endpoint itself; it backs the geometry bus with graph features.

Related docs
- UI flows: `docs/Unified and Modular PMOVES UI Design.md`
- CHIT decoder/specs: `pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md`
