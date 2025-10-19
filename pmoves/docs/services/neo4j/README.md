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

Make
- `make up` starts neo4j (with healthcheck) before v2.
- `make smoke` covers graph-warm and geometry checks.
