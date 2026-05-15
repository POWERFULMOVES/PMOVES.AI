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
- ⏳ Flare model namespace TODO
- ⏳ NATS JetStream streams (defined, not deployed) — Phase 2
- ⏳ `content.*` shaping/provenance subjects (defined, not deployed) — Phase 3
- ⏳ raw-content -> shaped-content -> attested-content -> HiRAG gate not wired yet — Phase 3
- ⏳ Hyperdimensions replay of shaped lexicon scenes not wired yet — Phase 4

## Phase Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Housekeeping (sync, docs, hardening) | ✅ Complete (2026-05-14) |
| 1 | Model deployment (P0: Qwen3.5-35B-A3B + Qwen2.5-Coder-32B) | ⏳ Script ready, awaiting host execution |
| 2 | NATS mesh.gpu.* stream deployment | ⏳ YAML ready, awaiting JetStream |
| 3 | Content shaping pipeline (raw→shaped→attested→HiRAG) | ⏳ Streams defined, wiring needed |
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
