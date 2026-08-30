# AGNOTE: DGX Spark Integration

## Node: pmoves-dgx-spark
- **Hardware**: Gigabyte GB10 Grace-Blackwell workstation
- **Memory**: 128GB unified memory
- **Role**: GPU inference via Ollama
- **Access**: Tailscale tag:gpu, port 11434
- **Provider**: ollama_spark in Agent Zero model_providers.yaml
- **Default Model**: gemma4:31b
- **NATS Subjects**: mesh.gpu.* (5 streams defined in pmoves/nats/mesh_gpu_streams.yaml)
- **TAC Tree**: pmoves/configs/tac_trees/dgx-spark.tac.yaml (278 lines, 6 phases)

## Canonical Working Contract
- `pmoves/docs/architecture/PMOVES_SPARK_PROVENANCE_PARITY.md`

That document is the working parity contract for:
- SPARK-driven message shaping and lexicon extraction
- provenance-first gating before HiRAG ingest
- Merkle/Graphiti binding for shaped content
- Hyperdimensions replay and creator-facing control surfaces

## Status
- ✅ Tailscale ACL rules configured
- ✅ Network inventory registered
- ✅ Makefile include added
- ✅ Ollama Spark provider configured
- ✅ PMOVES Spark preset created
- ✅ Hardware profile created (4090, 2026-05-14): `pmoves/config/profiles/dgx-spark-grace-blackwell.yaml`
- ✅ Agent Zero fork synced to upstream v1.14 (4090, 2026-05-14): `PMOVES.AI-Edition-v1.14`
- ✅ Model strategy documented: `pmoves/docs/SPARK_MODEL_STRATEGY.md` (786 lines, 2026-05-08)
- ✅ NATS stream definitions: `pmoves/nats/mesh_gpu_streams.yaml` (7 streams)
- ✅ Content provenance streams: `pmoves/nats/content_provenance_streams.yaml` (3 consumers)
- ✅ Model deploy script: `scripts/spark_deploy_models.sh` (--dry-run supported)
- ✅ Supply chain hardening applied (2026-05-14): see `research/SUPPLY_CHAIN_HARDENING_PLAN_2026-05-14.md`
- ✅ NATS JetStream streams DEPLOYED (2026-07-07): 6 streams active — AGENTZERO, MESH_GPU, CONTENT_PROVENANCE, GEOMETRY_CGP, BOTZ_COORDINATION, TOKENISM_ATTRIBUTION
- ✅ `content.*` shaping/provenance subjects DEPLOYED (2026-07-07): via init_streams.sh sidecar
- ✅ Spark shape worker DEPLOYED (2026-07-07): `pmoves/services/spark-shape-worker/` — healthy, subscribed to `mesh.gpu.inference.result.v1`
- ✅ Models DEPLOYED on Ollama (2026-07-07): qwen3.5:35b-a3b-q8_0 (36GB), nemotron-3-super:120b (80GB), qwen3:30b-a3b-q4_K_M (17GB), hermes3:8b (4GB), llama3.2:3b (1GB), nomic-embed-text
- ✅ HF MCP server DEPLOYED (2026-07-07): healthy on :8096, NATS connected, ModelFilter import fixed
- ✅ Docker NAT fix applied (2026-07-07): SPARK_NAT_FIX.sh — iptables MASQUERADE for custom bridge networks
- ✅ Vector crash loop fixed (2026-07-07): proxy vars unset + IPv4 healthcheck + LOGFLARE token placeholder (PR #1990)
- ✅ pmoves_public network created (2026-07-07): edge-functions egress bridge (PR #1990)
- ✅ autoMode fleet config applied (2026-07-07): PMOVES_NODE_ID=spark in settings.local.json
- ✅ claude-pmoves launcher installed (2026-07-07): PRs #1987 + #1991
- ✅ 10 MCP servers wired (2026-07-07): cipher, docker, hostinger, tailscale, nats-fleet, cloudflare, 4090-web, huggingface, supabase, supabase-db
- ✅ PMOVES repo synced to origin/main (2026-07-07): commit 2b5a40ea4
- ✅ Channel-monitor DB fix COMPLETE (2026-07-07): recreated via `make channel-monitor-up` — healthy, scanning YouTube channels
- ✅ qwen2.5-coder:32b pull COMPLETE (2026-07-07): 19.9GB deployed
- ✅ Shape worker E2E test PASSED (2026-07-07): published to `mesh.gpu.inference.result.v1`, received both `content.lexicon.shaped.v1` and `mesh.shape.handshake.v1`
- ✅ NATS password fix (2026-07-07): env.shared had `pmoves` — corrected to actual NATS server password, shape worker recreated
- ✅ claude-pmoves launcher verified (2026-07-07): loads 368 vars from env.shared, launches Claude Code
- ⏳ Flare model namespace TODO
- ⏳ raw-content -> shaped-content -> attested-content -> HiRAG gate not wired yet — Phase 3
- ⏳ Hyperdimensions replay of shaped lexicon scenes not wired yet — Phase 4
- ⏳ Build HF agent + HF research agent services (backlog)

## Phase Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Housekeeping (sync, docs, hardening) | ✅ Complete (2026-05-14) |
| 1 | Model deployment (P0: Qwen3.5-35B-A3B + Qwen2.5-Coder-32B) | ✅ Complete (2026-07-07): 7 models deployed |
| 2 | NATS mesh.gpu.* stream deployment | ✅ Complete (2026-07-07): 6 JetStream streams active |
| 3 | Content shaping pipeline (raw→shaped→attested→HiRAG) | 🔄 Shape worker deployed, E2E test passed |
| 4 | Hyperdimensions replay + lexicon control surface | ⏳ Backlog |

## Expanded Role
- SPARK is the heavy inference side of PMOVES message shaping in this lane.
- `z890` owns the trust and infra edges: subjects, JetStream policy, HiRAG gates, and canon.
- Hyperdimensions becomes the replay/control/art surface for shaped packets, not just generic geometry.

## Near-Term Lane
1. Deploy the existing `mesh.gpu.*` streams defined for DGX Spark.
2. Add the parity `content.*` subjects from the working contract.
3. Wire a SPARK shaping worker that emits `content.lexicon.shaped.v1`.
4. Gate HiRAG ingest on attested payloads instead of raw payloads.
5. Feed shaped packets into Hyperdimensions replay via `mesh.shape.handshake.v1`.

Added: 2026-04-17
