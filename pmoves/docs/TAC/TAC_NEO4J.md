# TAC Tree: Neo4j (graph store + mindmap)

> Technology-Architecture-Context tree for the PMOVES.AI graph database: where its image comes from, how compose
> runs it, which agents use it and for what, and how to operate it. Written 2026-10-01 from measured state on
> Knuckles (B850) in lane `ops/knuckles-neo4j-from-fork`. Vendor citations: `OM` = Neo4j Operations Manual 5.x
> (https://neo4j.com/docs/operations-manual/5), `UMG` = https://neo4j.com/docs/upgrade-migration-guide/current.

## 1. Service Identity

| Field | Value |
|-------|-------|
| **Service** | `neo4j` in `pmoves/docker-compose.yml` (`docker-compose.core.yml` is generated from it by `scripts/split_compose.py`) |
| **Container** | `pmoves-neo4j` (single name source: `scripts/neo4j_container.py`, #3193) |
| **Edition / version** | Community 5.26.30 (the 5.26 LTS line) |
| **Data** | volume `pmoves_neo4j-data` -> `/data` |
| **Tier** | data (`make -C pmoves up-data-tier`) |
| **Class** | Utility |
| **Owning lane** | `ops/knuckles-neo4j-from-fork` (B850-CLAUDE, Knuckles) |

## 2. Provenance: fork, image, pin

| Layer | State (2026-10-01) |
|---|---|
| Fork | `POWERFULMOVES/PMOVES-neo4j` (fork of `neo4j/neo4j`, GPL-3.0) |
| `PMOVES.AI-Edition-Hardened` | upstream **2026.09** + `PMOVES.AI_INTEGRATION.md` (fork PR #3) |
| `PMOVES.AI-Edition-5.26` | upstream tag **5.26.30** (`d3ee2744`); source-build work in fork PR #4 |
| Superproject gitlink | `9632778b` = #3's merge (2026.09 source) |
| Runtime image | `neo4j:5.26.30-community@sha256:037cf575...` from Docker Hub (vendor-built) |
| `fork_registry.json` | `sync: false` by decision (an upstream move is a store-version decision) |

**The pin and the runtime disagree** today: the gitlink names 2026.09 source while the fleet runs a vendor 5.26.30 binary.
The plan closes that in two phases:

- **Phase A (no store change):** build 5.26.30 from `PMOVES.AI-Edition-5.26`, A/B it against the vendor image, publish to
  GHCR, digest-pin it in compose, and re-point the gitlink at the branch that matches runtime.
- **Phase B (CRITICAL, separate lane):** 2026.x. UMG "Changes from Neo4j 5.26 LTS to Neo4j 2025.01 and later" is a
  migration, and APOC moves in lockstep. Rehearse with an offline dump, a sandbox load and the cypher smoke before operator go.

The vendor image is assembled from three repositories, and a from-source build needs all three:

| Part | Upstream | License | In the PMOVES build |
|---|---|---|---|
| Server tarball | `neo4j/neo4j` (Maven, `packaging/standalone/standalone-community`) | GPL-3.0 | the fork itself |
| APOC core (`labs/apoc-<v>-core.jar`) | `neo4j/apoc` (Gradle) | Apache-2.0 | built from tag `5.26.30`, tag object and commit verified |
| Image packaging (entrypoint, plugin loader) | `neo4j/docker-neo4j` | Apache-2.0 | vendored at tag `neo4j-5.26.30` into the fork's `docker/local-package/`, byte-identical to the vendor image's `/startup` |

Version caveat (measured): the tag's 161 poms say `5.26.30-SNAPSHOT`. `Implementation-Version` comes from
`project.version`, so a naive build reports `-SNAPSHOT` in `neo4j --version`, `dbms.components()` and the Bolt server agent.
`mvn versions:set -DnewVersion=5.26.30` rewrites all 161. The fork's build asserts that 0 remain.

Precedents: fork-to-GHCR build = `archon` in `.github/workflows/integrations-ghcr.matrix.json`; digest pin =
`pmoves-gpu-orchestrator` in `docker-compose.yml`; SHA-checked source clone = `pmoves/docker/minio-src`. The doctrine is
`docs/operations/COMPOSE_BUILD_PROVENANCE.md` "Compliant shapes" (fork Dockerfile, or a digest-pinned published image).

## 3. Topology

- Networks: `pmoves_app`, `pmoves_bus`, `pmoves_data` (alias `neo4j` on each, #3196) plus `pmoves_graph_front`, the
  internal link to the tailnet forwarder `neo4j-tailnet` (`docker-compose.neo4j-tailnet.yml`, #3201).
- Clients use **`bolt://neo4j:7687`**, never `neo4j://`. `server.default_advertised_address` defaults to `localhost`
  (`OM/configuration/configuration-settings`), so routing via `neo4j://` would send fleet clients to localhost;
  `server.bolt.advertised_address` is the alternative (`OM/configuration/connectors`, Example 2).
- Host ports: `${NEO4J_BIND:-0.0.0.0}:7474/7687` are still published. The reconciliation removes them (section 4),
  because the forwarder is the fleet path and Docker-published ports bypass the host firewall on this node.

## 4. Configuration contract (compose vs vendor guidance)

Rows marked **pending** are prepared as ONE compose change (grant `compose:pr:<N>`), so the store is recreated once.

| Item | Current | Vendor guidance | Target |
|---|---|---|---|
| image | vendor digest | provenance doctrine | Phase A GHCR image, digest-pinned (**pending** A/B) |
| `ports:` + `NEO4J_BIND` | published, default `0.0.0.0` | `OM/docker/ports` | removed; forwarder only (**pending**) |
| plugins | `NEO4JLABS_PLUGINS=["apoc"]` | `OM/docker/plugins`: `NEO4J_PLUGINS`; the entrypoint warns the old name "has been renamed" | `NEO4J_PLUGINS=["apoc"]` (**pending**). Note: the plugin step adds `dbms.security.procedures.unrestricted=apoc.*` (`neo4j-plugins.json`) unless that key is already set, so the explicit list below must stay |
| APOC file key | `NEO4J_apoc_import_file_use__neo4j__config__true` (typo; live `apoc.conf` holds the junk key) | APOC install docs: `NEO4J_apoc_import_file_use__neo4j__config=true` | corrected (**pending**) |
| APOC unrestricted | `apoc.coll.*,apoc.text.*,apoc.path.*,apoc.algo.*` | `OM/security/securing-extensions`: unrestrict only what you call; never `apoc.*` | exactly what the Neo4j MCP's `get-schema` needs (measure in a sandbox); no in-repo service calls APOC |
| APOC export / CSV file import | enabled | `OM/security/checklist` | export off once `make neo4j-backup` no longer uses `apoc.export` |
| strict validation | `false` | `OM/configuration/configuration-settings` (default `true`) | back to `true` after the `env_file` fix, proven in a sandbox |
| LOAD CSV egress | `internal.dbms.cypher_ip_blocklist=0.0.0.0/0,::/0` | internal key; the documented `LOAD ON CIDR` is Enterprise-only | keep; verify after recreate. Unknown: whether it covers `apoc.load.*` |
| `env_file: env.tier-data` | whole data tier | the entrypoint turns every `NEO4J_*` variable into a setting and does not exclude `NEO4J_PASSWORD` | removed (**pending**). It would write `PASSWORD=<plaintext>` into neo4j.conf if the funnel ever emitted that key (the template does), and it hands Neo4j MinIO, Postgres, Meili and Qdrant secrets it never uses. `${NEO4J_PASSWORD}` in `NEO4J_AUTH` is interpolated from compose's `--env-file` layering (`COMPOSE_ENV_FILES` in pmoves/Makefile: `env.shared`, then the tier files), which `env_file:` (container environment) does not feed |
| auth | `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:?...}` | `OM/docker/docker-compose-standalone`: `NEO4J_AUTH_FILE` via Docker secrets (recommended) | fix the `:?` text; `NEO4J_AUTH_FILE` is an operator decision (funnel change) |
| memory | none set; 4G limit | `OM/docker/configuration`: Docker defaults are "very limited" (512M pagecache, 512M heap); `OM/performance/memory-configuration`: heap initial = max | heap and pagecache from `neo4j-admin server memory-recommendation --memory=4g` (**pending**) |
| `/logs` | anonymous volume (orphaned on each recreate) | `OM/docker/mounting-volumes` | named `neo4j-logs` (**pending**) |
| healthcheck | `wget localhost:7474` | Community has no unauthenticated database-availability endpoint | keep as liveness; authenticated `RETURN 1` belongs to the make road |
| `security_opt` | set in docker-compose.yml; stripped from the generated core.yml by design | `OM/docker/security` | add neo4j to `docker-compose.hardened.yml` |
| other definitions | elder-melchor overlay `${NEO4J_PASSWORD:-<retired literal, redacted 2026-10>}`; `jellyfin-neo4j` `${JELLYFIN_NEO4J_PASSWORD:-<retired literal, redacted 2026-10>}`, tag-only `neo4j:5.26.22`, 4.x memory keys, `gds.*` allowlisted with no GDS plugin | no default credentials | `:?` guards; jellyfin on a digest (**pending**, compose) |

## 5. Consumers and the graph contract

Community Edition has **exactly one** standard database (`OM/database-administration`), so every consumer below shares
`neo4j`. They are separated by label only.

| Consumer | Deployed | Labels | Schema it creates | Needs |
|---|---|---|---|---|
| hi-rag-gateway-v2 (+v1/gpu) | compose | reads `Constellation/Point/MediaRef`, `Entity` | none (relies on `neo4j/cypher/001`) | plain Cypher |
| cipher-api (`Pmoves-cipher/src/pmoves/graph.ts`) | compose, running | `:Memory`, `SAME_CATEGORY` | `memory_id_unique`, `memory_agent_category` | plain Cypher; graph off without `NEO4J_PASSWORD` |
| Agent Zero MCP `neo4j` (`tools/seed_agent_zero_mcp.py`) | compose, running | any | none | **APOC** (neo4j/mcp refuses to start in STDIO mode without it; `get-schema` uses APOC meta); GDS optional |
| archon | compose, running | not measured | | |
| services/gateway (mindmap writer, `pmoves/services/gateway/gateway/api/workflow.py`) | **not in any compose file** | MERGEs `Constellation/Point/MediaRef` | none | uniqueness constraints |
| graph-linker | **not in any compose file** | `Asset/Generation/Media/Topic/Namespace/KBItem/Agent/Workflow` | `services/graph-linker/migrations/01_init.cypher`, applied by graph-linker itself at startup (`app.py:83`), so the first start creates `agent_name` (section 10.1) | CHIT: since PR #3255 `chit_sig`/`chit_kid`/`chit_signed_at` are persisted on the `Asset`, `Generation`, `Media`, `Topic`, `Namespace` and `KBItem` nodes and the `HAS_TOPIC` edge (NOT `Agent`, `Workflow`, or the `EMITTED`/`PRODUCED`/`USED_WORKFLOW`/`CONTAINS` edges); a write is refused without a key. A stored signature is verifiable only against the source event: the MAC covers the write's Cypher parameter dict, and the node keeps a transformed subset of it (e.g. `ts` is stored as `datetime()`), so `chit_signer.verify_write()` needs the original event parameters, not just the node. |
| consciousness-service | compose | none | none | none: it has no Neo4j driver |
| jellyfin-ai | profile | its OWN `jellyfin-neo4j` | | separate database |

Known contract gaps:
- `Constellation.id`, `Point.id` and `MediaRef.uid` are MERGE keys with no uniqueness constraint (the Cypher manual's MERGE
  guidance needs one for concurrent writers and for index lookups).
- `:Agent` gets three different UNIQUE keys from three sources: `id` (`tools/chit_mindmap_seed.cypher`), `name` (graph-linker)
  and `agent_id` (graphiti `0003`). One owner has to choose.
- GDS and vector or full-text indexes are not needed by any consumer (vectors live in Qdrant).

## 6. Mindmap

- Endpoint: `GET /mindmap/{constellation_id}?modalities=&minProj=&minConf=&limit=` on hi-rag-gateway-v2 (`routes/geometry.py`).
- Query shape: `(:Constellation {id})-[:HAS]->(:Point)-[:LOCATES]->(:MediaRef)`, filtered on `p.modality`, `p.proj`, `p.conf`.
- Data today is fixture data: `neo4j/cypher/010_chit_geometry_fixture.cypher`. The only live writer (services/gateway)
  is not deployed. `002_chit_constraints.cypher` makes `Anchor.id`, `Constellation.id`, `Point.id` and `MediaRef.uid`
  unique (ported from `docs/pmoves_all_in_one/pmoves_chit_patch/neo4j/migrations/001_chit.cql:1-4`).
- Smoke: `011_chit_geometry_smoke.cypher` returns `CHIT_SMOKE_OK` only for one `Anchor-[:FORMS]->Constellation`, 3 Points,
  3 MediaRefs and at least 2 modalities. `neo4j-bootstrap` exits 1 on anything else and applies every file once.
- Every statement of every road file is self-contained: cypher-shell does not carry variables across `;`. Until 2026-10,
  `003_seed_chit_mindmap.cypher` (now deleted; it duplicated 010) and `010:19` reused variables across `;`, so each
  edge statement MERGEd an **unlabeled** node pair. On an empty graph that is 6 blank nodes, and FORMS reached no
  Anchor. `tests/test_neo4j_cypher_static.py` parses every road file for that shape.
- **Operator step for an existing graph (not run by this lane; credentialed session via with-env.sh):**
  1. Duplicate precheck before `002` (CREATE CONSTRAINT fails on duplicates):
     `MATCH (n:Anchor|Constellation|Point) WITH labels(n)[0] AS l, n.id AS k, count(*) AS c WHERE c > 1 RETURN l, k, c;`
     and `MATCH (m:MediaRef) WITH m.uid AS k, count(*) AS c WHERE c > 1 RETURN k, c;` must both return no rows.
  2. Count the residue first and keep the number: `MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n);`. Delete only
     unlabeled nodes whose every edge is FORMS/HAS/LOCATES, which is 003's shape, and compare the count first.
     Other writers, such as the consciousness shell loader's `:150`/`:156`, also leave unlabeled nodes.
- The consciousness taxonomy (`load-consciousness-neo4j`, `data/consciousness/neo4j-consciousness-schema.cypher`) had
  15 statements opening `WITH <var>` on the previous statement's variable, plus 21 standalone edge MERGEs. The load
  aborted at `:66` after committing the root, one category and a blank pair. Each statement now re-MATCHes its parent
  by key. A graph that ran the old file may hold that blank pair too (step 2 above, `HAS_CATEGORY`/`HAS_SUBCATEGORY`).
  `data/consciousness/load_neo4j_consciousness.sh` is a manual-only duplicate with its own blank-node MERGEs at
  `:150`/`:156` and a second `Entity` key (`Entity.id` beside `001`'s `Entity.value`). Retire it in favour of the road.
- The CHIT taxonomy graph (`CHITPillar`, `NATSSubject`, `CGPElement`, `Agent`, `CHITModule`) is a separate seed:
  `make -C pmoves chit-mindmap-seed`.

## 7. Operations

| Need | Road |
|---|---|
| start (never recreates; see the warning below) / stop / restart / logs / status | `make -C pmoves neo4j-up` / `neo4j-down` / `neo4j-restart` / `neo4j-logs` / `neo4j-status` |
| constraints, alias CSV, CHIT fixture + smoke | `make -C pmoves neo4j-bootstrap` |
| one file from `neo4j/cypher/` | `make -C pmoves neo4j-migrate VERSION=001` |
| consciousness taxonomy | `make -C pmoves load-consciousness-neo4j` |
| CHIT taxonomy graph | `make -C pmoves chit-mindmap-seed` |

Every cypher road (the `neo4j-migrate` / `load-consciousness-neo4j` / `chit-mindmap-seed` macro and
`scripts/neo4j_bootstrap.sh` behind `neo4j-bootstrap`) hands the password to cypher-shell through its `NEO4J_USERNAME` /
`NEO4J_PASSWORD` env vars (`cypher-shell --help`: "Can also be specified using the environment variable NEO4J_PASSWORD"),
copied in by `docker exec -e NAME`, so it is never on argv. An unset OR empty password fails closed before any docker call
(`tests/test_neo4j_make_roads.py`, which runs them against a recording `docker` stub). Exceptions that remain:
`neo4j-backup`, `neo4j-restore` and `neo4j-reset` (below).

> **Recreate hazard until PR #3251 lands.** main's `neo4j` service still carries `env_file: env.tier-data` and
> `0.0.0.0` host ports. A plain `docker compose up -d` recreates a container whenever its config hash changes, and one
> rotated value in `env.tier-data` is enough. A recreate then puts Neo4j back on that config and spends #3251's one
> planned recreate. `make neo4j-up` therefore runs `up -d --no-recreate --wait neo4j` (docker compose up:
> `--no-recreate` "If containers already exist, don't recreate them"). **`make up-data-tier` and `make up` carry the
> same hazard and do NOT pass `--no-recreate`.** On a node with a live graph, do not run them for Neo4j's sake until
> #3251 has landed; start Neo4j with `make neo4j-up`.

**Backup and restore (Community):**
- There is no online backup: `neo4j-admin database backup` is Enterprise-only.
- `dump` and `load` require the DBMS to be stopped (`OM/backup-restore/offline-backup`, `OM/backup-restore/restore-dump`).
- Dump **both** `neo4j` and `system`.
- Prove a clean stop with `neo4j-admin database info` (`Database in use: false`, `Store needs recovery: false`).
- A volume copy is not vendor-supported, so keep it only as a secondary rollback.
- `make neo4j-backup` / `neo4j-restore` do not follow this yet: they dump a RUNNING database, pass a `:-changeme` password
  fallback on argv, and fall back to `apoc.export`. They are a separate lane. Until then use the corrected runbook from this lane.
- `make neo4j-reset` puts the password on argv and is destructive by design.

## 8. Security posture

- Auth on. `NEO4J_AUTH` only seeds a NEW store ("Setting NEO4J_AUTH does not override the existing authentication",
  `OM/docker/introduction`), so the real gate is the post-recreate authentication check.
- The vendor entrypoint (`docker/local-package/docker-entrypoint.sh` in the fork, byte-identical to the image's `/startup`)
  accepts `NEO4J_AUTH` only if it matches `^([^/]+)/([^/]+)/?(true)?$` (line 308), so a password containing `/` is rejected;
  so are the password `neo4j` (line 313) and one shorter than 8 characters (line 324). On a rejected value it prints the
  WHOLE `NEO4J_AUTH`, password included, to stdout and stderr (lines 355-356), which lands in `docker logs`. The success
  path logs the command with the password masked (line 351, debug only). Generated passwords (`secrets.token_urlsafe`) never contain `/`.
- Consumer fallbacks to the password `neo4j` still exist in service code: `hi-rag-gateway-v2/config.py`,
  `graph-linker/linker.py`, `pmoves/services/gateway/gateway/api/mindmap.py`, `tools/seed_agent_zero_mcp.py`. They should fail closed the way cipher does.
- APOC is least privilege (section 4). LOAD CSV egress is blocked. There are no host ports once the compose change lands.

## 9. Protected paths and grants

| Path | Class | Road |
|---|---|---|
| `pmoves/docker-compose*.yml` | readOnlyPaths | `KNOWN_ROAD=compose:<reason>` |
| any `Dockerfile` (including in the fork clone) | readOnlyPaths | `KNOWN_ROAD=dockerfile:<reason>` |
| `.github/workflows/*` | noDeletePaths only | none needed for edits |
| `pmoves/Makefile`, `pmoves/docs/TAC/*`, `pmoves/config/fork_registry.json` | unprotected | none |

## 10. Open items / COULD-NOT-MEASURE

- **Open, for the provenance lane (`ops/knuckles-neo4j-chit-provenance`), constraints deliberately unchanged here:
  three uniqueness keys on `:Agent` in one database.**
  - `Agent.id`: constraint `agent_id`, `tools/chit_mindmap_seed.cypher:12`.
  - `Agent.name`: constraint `agent_name`, `services/graph-linker/migrations/01_init.cypher:3`.
  - `Agent.agent_id`: constraint `agent_agent_id_unique`, `services/graphiti/migrations/0003_polarity_partition.cypher:13`.

  The failure depends on order. After graph-linker has merged `(:Agent {name:"Agent Zero"})`, the chit seed's
  `MERGE (:Agent {id:"agent-zero"}) SET .name="Agent Zero"` makes a second node and violates `agent_name`, so the seed
  aborts. In the other order, graph-linker's `MERGE (ag:Agent {name:$source})` silently forks the identity. The
  candidate from the CHIT review is one key, `Agent.id` = the `pmoves/config/agent_registry.yaml` `agents:` key. That
  needs a live mapping step, and whether the other two constraints exist live is COULD-NOT-MEASURE.
- `services/graphiti/migrations/0003_polarity_partition.cypher` is NOT idempotent: `datetime()` inside the MERGE
  relationship pattern (`:31`, `:37`, `:43`, `:49`) adds a new `OPERATES_AT` edge on every run. It is not fixed here
  because no road applies it. It is outside the road set, and its only reference is a TAC `expect:` file-exists check.
  Fix it before anything runs it. The static checker in `tests/test_neo4j_cypher_static.py` flags all four.
- The fallback password literal removed from `load_neo4j_consciousness.sh`, `verify_chr_conch.sh` and a review doc in
  2026-10 remains in git history. Whether it equals the live `NEO4J_PASSWORD` is COULD-NOT-MEASURE. Rotate it
  (operator step).

- A full source build and the A/B against the vendor image (the sandbox preflight returned exit 3 on 2026-10-01).
- The APOC procedures the Neo4j MCP actually calls, and whether A0's `mcp://neo4j` resolves to the neo4j/mcp binary.
- archon's Cypher surface.
- Live labels and counts (needs a credentialed session through with-env.sh).
- Whether `internal.dbms.cypher_ip_blocklist` also stops `apoc.load.*`.
- Whether strict validation can be re-enabled.
- Superseded history: `docs/NEO4J_SUBMODULE_PROMOTION.md` and `docs/NEO4J_SUBMODULE_INTEGRATION_COMPLETE.md` (2026-03)
  describe a PMOVES-supabase-style submodule with its own Makefile and db/. That submodule was never built; this TAC replaces them.

### 10.1 `:Agent` single key: design (ops/knuckles-neo4j-chit-provenance, PR #3255). NOT applied

**Decision proposed: `Agent.id` = the `agents:` key in `pmoves/config/agent_registry.yaml`** (snake_case; 111 keys on
2026-10-01). The registry is the declared source of truth for agent identity (`.claude/CLAUDE.md`, "Agent taxonomy").
The only uniqueness constraint on `:Agent` is the existing `agent_id` (on `Agent.id`, `tools/chit_mindmap_seed.cypher:12`).
`name` becomes a plain display property. The signing card (`signing_identity_cards.yaml`, e.g. `b850-claude`) is a
different axis. Link it with `(:Agent)-[:SIGNS_AS]->(:SigningCard {kid})` rather than adding a fourth key.

**Seed mapping** (`tools/chit_mindmap_seed.cypher:58-73`, 16 agents):

| Seed id | Registry key | Basis |
|---|---|---|
| `agent-zero` | `agent_zero` | exact (kebab→snake) |
| `archon` | `archon` | exact |
| `supaserch` | `supaserch` | exact |
| `extract-worker` | `extract_worker` | exact |
| `cipher-memory` | `cipher_memory` | exact |
| `flute-gateway` | `flute_gateway` | exact |
| `pmoves-yt` | `pmoves_yt` | exact |
| `tensorzero` | `tensorzero` | exact |
| `creator` | `creator` | exact (note: `fordham_creator` is a different agent) |
| `hyperdimensions` | `hyperdimensions` | exact |
| `mesh-agent` | `mesh_agent` | exact |
| `hirag` | **operator** (proposed `hirag_v2`) | registry display name "Hi-RAG v2" = seed name |
| `deepresearch` | **operator** (proposed `deep_research`) | registry display name "DeepResearch" = seed name |
| `hf-mcp` | **operator** (proposed `hf_mcp_server`) | registry display name "HF MCP Server" = seed name |
| `botz` | **operator** | no single match: `botz_gateway`, `botz_architect`, `botz_builder`, `botz_auditor` |
| `tokenism` | **operator** | no registry entry. Add one (the simulator is CHIT-aware, port 8103) or drop the seed node |

The three "proposed" rows match on display name only, so they are listed for the operator rather than decided here.

**Writer changes (land BEFORE graph-linker is deployed):**
- **Ordering hazard.** graph-linker applies `migrations/01_init.cypher` at startup (`app.py:83` → `neo4j_client.py`
  `apply_migrations`), and that file creates `agent_name`. Deploying graph-linker as-is recreates the conflicting
  constraint on the first start, and its `MERGE (ag:Agent {name:$source})` forks identities. Change its migration and
  its Cypher in the same PR as the deploy, or before.
- graph-linker: resolve the envelope `source` to a registry key and `MERGE (ag:Agent {id:$agent_id})`. An unresolved
  source does not create an `:Agent`. It stays as `g.source` on the Generation, and a counter records the miss
  ("inform, don't decide"). Delete `agent_name` from `01_init.cypher`.
- chit seed: emit registry keys. Better: generate the Agent and NATSSubject nodes from `agent_registry.yaml` and
  `contracts/topics.json` instead of copying them by hand.
- graphiti `0003`: delete `agent_agent_id_unique` and match on `a.id`. Fix its non-idempotent `datetime()`-in-MERGE first (above).

**Migration plan (operator, credentialed session via `with-env.sh`; nothing here has been run):**
0. Offline dump of `neo4j` and `system` (section 7).
1. Inventory, read-only:
   `SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties WHERE 'Agent' IN labelsOrTypes RETURN name, properties;`
   `MATCH (a:Agent) RETURN a.id, a.name, a.agent_id, COUNT { (a)--() } AS degree ORDER BY a.id;`
2. Duplicate prechecks. **Every query must return 0 rows/0 before step 3. Otherwise STOP and bring the output back.**
   - Two seed ids mapping to one registry key, or a target key that already exists:
     `UNWIND $mapping AS m OPTIONAL MATCH (a:Agent {id: m.old}) OPTIONAL MATCH (b:Agent {id: m.new}) WITH m.new AS k, count(DISTINCT a) + count(DISTINCT b) AS c WHERE c > 1 RETURN k, c;`
   - Duplicate ids already present: `MATCH (a:Agent) WHERE a.id IS NOT NULL WITH a.id AS k, count(*) AS c WHERE c > 1 RETURN k, c;`
   - Nodes with no `id` (written by graph-linker's `name` key or graphiti's `agent_id`): `MATCH (a:Agent) WHERE a.id IS NULL RETURN count(a);`.
     Expected 0, because neither writer has been deployed. If it is non-zero, each one needs an explicit mapping, which
     is a merge of two nodes and out of scope for this plan.
3. Drop the two foreign keys: `DROP CONSTRAINT agent_name IF EXISTS;` and `DROP CONSTRAINT agent_agent_id_unique IF EXISTS;`.
4. `agent_id`: if step 1 shows it on `Agent.id`, keep it. If it is missing, or a constraint by another name covers
   `Agent.id`, drop that one and run `CREATE CONSTRAINT agent_id IF NOT EXISTS FOR (a:Agent) REQUIRE a.id IS UNIQUE;`.
   That runs only after step 2 is clean, because CREATE CONSTRAINT fails on existing duplicates.
5. Remap in ONE statement, which makes it one transaction: `UNWIND $mapping AS m MATCH (a:Agent {id: m.old}) SET a.id = m.new;`.
   With `agent_id` live, a collision aborts the whole statement rather than half-applying it.
6. Verify: the inventory shows exactly one `:Agent` constraint, `MATCH (a:Agent) WHERE a.id IS NULL` = 0, and every
   `a.id` is a registry key (compare against the YAML offline).
7. Then re-run `make -C pmoves chit-mindmap-seed` with the registry-keyed seed. Its MERGEs now match the remapped nodes.

### 10.2 Signed `:SeedSet` + `graph.seed.applied.signed.v1`: design. NOT registered yet

Nothing that seeds this graph is signed (rows 1-8 of the CHIT review inventory). Proposal:

- **Record.** After a road applies a file, it writes `MERGE (s:SeedSet {id: $sha256_of_file_bytes}) SET s.file, s.git_sha,
  s.applied_at, s.road, s.applied_by, s.node_count, s.rel_count, s.chit_sig, s.chit_kid, s.chit_signed_at`. The signed
  document is the **whole event**: every field of the `graph.seed.applied.signed.v1` payload except `sig`, namely
  `{seed_set_id, file, sha256, git_sha, applied_at, road, applied_by, node_count, rel_count}` (`applied_by` =
  signing-card `agent_id`; the counts are present on every event, 0 when unknown). It is signed with `sign_cgp` and no
  `passphrase=` argument, like graph-linker. `verify_cgp` strips only `sig` and MACs everything else
  (`tools/chit_security.py:384-386` in `verify_cgp_detailed`; `sign_cgp` does the same at `:340-342`), so signing a subset of the published fields would make every event fail
  verification. Each seed statement also does `SET x.prov = $seed_set`, so
  every node and edge points back to its SeedSet. Verification recomputes the file hash and calls `verify_cgp_detailed`.
  With today's single deployment key the result is `OK_UNPINNED` (attribution, not authentication).
- **Event.** On success the road publishes the signed record on **`graph.seed.applied.signed.v1`**. The `*.signed.v1`
  suffix follows the `agent.graphiti.signed.v1` precedent. It does **not** publish on `chit.signed.v1`, which is a live
  multi-consumer channel with a different `{schema,tier}` envelope (`tools/sign_trail.py:62-69`, review #2048).
- **Fail-closed.** No key means the road exits 3 (could-not-sign) and applies nothing. An unsigned seed is opt-in and
  must be explicit, never the silent default.
- **Where.** A stdlib helper (`tools/neo4j_seed_sign.py`) called from `scripts/neo4j_bootstrap.sh` and the
  `neo4j_apply_cypher` macro after a successful apply. That is Originated: no seed signer exists in the repo.
- **Registration, which needs grants** (drafts are in the PR #3255 description):
  - `pmoves/contracts/topics.json` entry, with `"publisher": ["neo4j_seed_sign"]`: unprotected for edits, but its
    `schema` must exist first.
  - `pmoves/contracts/schemas/graph/seed.applied.signed.v1.schema.json`: readOnlyPaths, needs `KNOWN_ROAD=schema:<reason>`.
  - `.claude/context/nats-subjects.md` catalog entry: readOnlyPaths with **no road**, so it is an operator edit.
  - Capture: no JetStream stream catches core publishes on this node today. Add `graph.seed.>` to a stream, or the
    event is fire-and-forget.
