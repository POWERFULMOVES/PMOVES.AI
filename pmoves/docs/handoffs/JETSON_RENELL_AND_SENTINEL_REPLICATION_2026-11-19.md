# Handoff briefs: Jetson renell + fleet-sentinel replication (2026-11-19)

From: CRUSH-SPARK (KIMI) — spark lane, PR #3353 branch.
Both lanes below are remote-node work; this Crush session is SSH-blocked,
so each is packaged as an executable brief for the receiving node's agent.

Companion PRs (merge order matters):

1. **Pmoves-cipher#37** — routable announce host + 60s heartbeat (VERIFIED live
   on spark: sentinel shows cipher-memory healthy, announce age ~60s bound).
2. **PMOVES.AI #3353** — flute announce heartbeat (VERIFIED live on spark,
   age ~30s bound) + `PMOVES_ANNOUNCE_HOST=cipher-api` compose env +
   3-source index (`pmoves/data/research/three_source_index.json`).
3. After #37 merges: gitlink bump `Pmoves-cipher` on the receiving PR (do NOT
   build from a drifted checkout — `up-cipher`'s pin gate exists for this).

## Brief A — Jetson renell (JONS-1/2/3), per twin verdict (c): RENELL, not rename

Sequenced per node, blue/green; NEVER parallel across the three JONS.

1. **Interim alias-map**: on the JONS node, map old device names
   (`jons-1/2/3`, `pmoves-jons-N`) to the target `pmoves-nemotron-N` identity
   in `pmoves/configs/node-vocabulary.yaml` + Tailscale alias so existing
   trails resolve during the transition. Interim only — remove after step 5.
2. **Fresh enroll**: `make -C pmoves fleet-enroll ROLE=edge DEVICE=pmoves-nemotron-N`
   (new signing card row per AGNOTE-pmoves-rdna4.md policy: seed only when the
   agent_id starts emitting).
3. **Verify green**: `make -C pmoves jetson-verify DEVICE=nemotron-N` — do not
   proceed to the next step until this is green.
4. **Edge compose up**: `docker compose -f docker-compose.jetson-edge.override.yml`
   (NATS leaf + Ollama edge + Whisper INT8), confirm NATS leaf connects to the
   broker with the CURRENT password (`wcs1gWbl…` cutover, 2026-10-10) and
   announces on `services.announce.v1`.
5. **Revoke old device**: retire the old `jons-N` Tailscale/device identity and
   drop the interim alias-map entries. Room `jons-edge.room.control` stays the
   room; only the device identities renell.
6. Repeat for the next node. Log CLAIM/RELEASE in `AGNOTE4482PHI.t1.md` per node.

Input for step "diff firmware vs latest provisioning scripts": the 95
provisioning-candidate videos in `pmoves/data/research/three_source_index.json`
(`sources.videos.provisioning_candidates`) — the DARKXSIDE AI playlist crawl.

## Brief B — fleet-sentinel replication (elder-melchor, Knuckles)

Prereqs: PR #3353 merged on the node's checkout; NATS_URL in env files must be
the post-cutover broker credential (`python3 -m pmoves.tools.derive_nats_url
--promote` mirrors it into tier files).

1. `make -C pmoves up-sentinel` — registry at `http://localhost:8116/registry.json`.
2. Verify announces arrive and health flips to healthy within ~2 poll cycles
   (30s poll interval). Expected early announce: `cipher-memory` (with
   PMOVES_ANNOUNCE_HOST env from #3353) and any flute-gateway on that node.
3. Known-good reference (spark, 2026-11-19): cipher-memory
   `url=http://cipher-api:8105` healthy, announce age ≤60s.
4. Watch for the session-env shadowing hazard before ANY compose command:
   `env -u NATS_URL -u SUPABASE_SERVICE_ROLE_KEY -u SUPABASE_SERVICE_KEY` —
   launcher-exported stale values override env-files (recurring incident class,
   2026-10-13).

## Knuckles voice addendum (Lane 4 step 1)

`make up-voice-amd` full Docker build validation, chatterbox engine, Flute
routing check. Prerequisite context: #3366 (amd-overlay fix). The ROCm override
exists but has never been end-to-end tested; capture the build log as evidence
in the trail entry.
