# Pre-restart preflight — identity, provenance, and the GEOMETRY BUS

**Produced 2026-08-25 from B850/Knuckles, before the fleet restart and GEOMETRY BUS turn-on.**

Method: eleven agents in a dynamic workflow — eight parallel surveys (bootstrap,
provenance, CGP/geometry, EVO SWARM, agent-card/A2A, tokenism attribution,
P7/P7PLAYGROUND, harness-model fit), then a bootstrap-contract pass and an
**adversarial pass** whose only job was to find claims the surveys had overstated.
473 tool calls, ~1.47M tokens, zero agent errors.

Every claim below is cited to `file:line` or command output. Where the adversarial
pass overturned a survey, the corrected version is used and marked **[CORRECTED]** —
four survey claims were wrong and are labelled as such rather than quietly dropped.

**Read §5 first if you are about to turn the bus on.**

---

# PMOVES.AI Pre-Restart Synthesis — GEOMETRY BUS Turn-On

**Node:** B850/Knuckles · **Branch:** `docs/mcp-gateway-wiring-research` · **Verified:** 2026-08-25
Live state re-checked at write time: NATS uptime 3h52m, 35,745 msgs in, **11 JetStream streams, all 0 messages**, only `AGENTZERO` has bound consumers (2). 66 containers up.

Where an adversarial pass corrected an earlier survey, the corrected version is used and marked **[CORRECTED]**.

---

## 1. Live vs specified-only

### Live and actually doing work
| Thing | Evidence |
|---|---|
| NATS broker, JetStream on, 11 streams provisioned | `curl 127.0.0.1:9223/jsz?streams=1` — GEOMETRY_CGP `['geometry.>']`, TOKENISM_ATTRIBUTION `['tokenism.>']`, both `retention=limits` (the interest-retention silent-discard hazard is **fixed**) |
| 8 live core-NATS subs on `geometry.cgp.v1` from tokenism-simulator; 4 `tokenism.*` subs from publisher-discord | `/connz?subs=1`, 21 connections |
| model-registry :8110 — CHIT-signed **model fitness** subsystem, healthy, migrations applied | **[CORRECTED]** `pmoves-model-registry-1 Up 10 days (healthy)`; `/openapi.json` includes `/api/model-fitness`; `pmoves/services/common/model_fitness.py:220-274`; migrations `20260522000000_model_fitness_candidates.sql`, `20260527060000_tighten_model_fitness_rls.sql` |
| Per-agent Ed25519 keygen + OpenSSH keyring | **[CORRECTED]** `pmoves/tools/keygen_cards.py:119`; `pmoves/config/allowed_signers` exists, 1044 B, **3 real ssh-ed25519 keys** (crush, darkxside, spark-runner); gate wired at `pmoves/mk/preflight.mk:130,133` |
| P7 rehearsal→live CHIT gate (7-item checklist, 422 on fail, atomic catalog writeback) | `pmoves/services/p7-room-orchestrator/transition.py:215-317`, `catalog.py:120-156` |
| Hi-RAG v2 genuinely activates `geometry.swarm.meta.v1` parameter packs | `hi-rag-gateway-v2/geometry_bus.py:346,381` |
| A2A JWT auth, fail-closed on misconfig | `agent-zero/python/features/a2a/server.py:72-124` |

### Running but producing nothing
- **flute-gateway** — up 9 days healthy, `flute_chit_cgp_published_total` has HELP/TYPE lines and **zero samples** = never incremented. Zero TTS requests. Only sample is 22,867 healthz hits.
- **consciousness-service** — up 10 days; CGP publish is gated per-request on `request.publish_to_nats` (`main.py:346,437`). Nothing calls it with `publish=true`.
- **evo-controller** — up 10 days, crash-looping on its poll HTTP call (`httpx.ConnectError` repeatedly), never reaches its publish step. Even if it did: it emits a **hardcoded** pack `{"K":8,"bins":32,"tau":0.2,"beta":0.7}` with `"energy":{"note":"placeholder"}` (`app.py:196-204`) and throws fetched CGPs into `logger.debug`.
- **tokenism-simulator** — subscribed, but its JetStream durable subscribe fails `NotFoundError` and silently degrades to core NATS: at-most-once, no replay. This is why `GEOMETRY_CGP` shows `consumers=0` despite 8 live subs (`nats_consumer.py:239-260`, confirmed in container logs).

### Not deployed at all on this node
gateway, hi-rag-gateway, hi-rag-gateway-v2, shape-store, supaserch, deepresearch, extract-worker, ffmpeg-whisper, semantic-cache, showtime-api, agentgym-rl-coordinator, **p7** (8120/8122 both unreachable), **node-registry**, **model-fitness-bridge**, **evoswarm/persona_optimizer** (no Dockerfile, in no compose file).

### Specified-only — code exists, nothing runs it
- `p7.nats.launch` — publisher function exists, **only tests call it** (`nats_pub.py:205`; callers `tests/test_transition.py:34`, `tests/test_api.py:61`). Half of the documented "P7 control plane" is never emitted.
- `tokenism.cgp.weekly.v1` — **[CORRECTED]** a publisher *does* exist (`PMOVES-ToKenism-Multi/.../chit-nats-publisher.ts:286 publishWeeklyCGP`). It has **no production caller**; `new CHITNATSPublisher` appears only in tests and an unused factory. Reader-3's "zero publishers anywhere in the repo" was wrong; Reader-6 was right.
- AgentGym integration for evo-controller — 499 lines, **never imported** (`EvoSwarmController` declares no base class; grep for `AgentGymIntegration` finds only the definition + docs).
- AgentGym "PPO training" — a simulation writing fabricated `mean_reward` 0.5→0.8 into Supabase (`coordinator/training.py:212-238`).
- `archon.mint.*` — no publisher, no subscriber, no `archon_minted_artifacts` migration (grep `--include=*.sql` → nothing). Minting is a slash command that stages JSON to `/tmp` and asks a human to run `nats pub`.
- Foyer / review-room / voice-room / media-room / war-room — zero files.
- `pmoves/tools/fittings.py`, `pmoves/configs/model-roles.yaml` — not in tree, **not on main**; only on `origin/feat/model-harness-fitting`.

**Blunt summary:** the bus is *provisioned, subscribed, and silent*. Zero messages have ever traversed any of the 11 streams — not just geometry. `CONTENT_PROVENANCE`, `HELPDESK`, `ARCHON`, `ROOMS`, `MESH_GPU`, `COMFY_COLLAB`, `voice_relay` are equally empty. This is a fleet-wide condition, not a geometry-specific one.

---

## 2. The bootstrap contract (ordered)

An agent self-deploying to a bare node must: reach the node → get credentials → get the code → get a runtime → resolve identity → prove provenance → rejoin the bus → register → be routable → be verified.

| # | Step | Status | Detail |
|---|---|---|---|
| **R1** | Reach node (tailscale join) | **BROKEN** | `post-flash-bootstrap.sh:99` advertises `tag:pmoves,tag:jetson,tag:nemotron,tag:edge,tag:arm64,tag:production`; ACL `tagOwners` = `[exit,gateway,gpu,guest,lab,partner,pmoves,vps]`. **5 of 6 undeclared** → `tailscale up` rejects → `set -euo pipefail` kills the run at **step 3 of 6**. Same defect in z890 lane (`10-tailscale-enroll.sh:86`). |
| **R1a** | Obtain a Tailscale auth key | **MUST-BUILD** | `make fleet-enroll` is a RustDesk token generator: `pmoves/mk/infra.mk:279` usage string offers only `owner\|partner\|guest`; scripts pass `ROLE=edge`. No `tskey` anywhere in `generate-enrollment.py`. Only honest doc: `deploy/runbooks/fresh-install-fleet.md:34` ("pre-auth key from admin console"). |
| **R2** | Obtain real credentials | **BROKEN** | Funnel consumer exists (`pull_chit_bundle.sh`, `make secrets-pull`) but **no provisioning script calls it** — grep over `deploy/ pmoves/scripts/` returns only definitions/comments. Every lane runs `env-setup` → placeholders. Node comes up with syntactically valid, functionally empty creds. |
| **R2a** | Unattended credential path | **MUST-BUILD** | `pull_chit_bundle.sh:41` hard-requires interactive `gh auth login`, and depends on a CI artifact with **1-day retention**. Worse: `claws/bootstrap-node.sh:92` installs gh from a hardcoded `linux_amd64` tarball — arm64 nodes can never get the tool that fetches their own secrets. |
| **R3** | Get the code | **BROKEN (Jetson)** | `post-flash-bootstrap.sh:134` `git clone --depth 1`, no `--recurse-submodules`. 75 submodules absent, including compose build contexts (`docker-compose.yml:3399 ../PMOVES-Archon`, `:2205`, `:3702`, `:5622`). Compounds with arm64: only ~10 services publish arm64; the node must build locally from contexts it doesn't have. z890 lane handles this (`40-repo-clone.sh:57-60`). |
| **R4** | Land an agent runtime | **MUST-BUILD** | Jetson lane never calls `claws/bootstrap-node.sh` or `deploy-claw.sh`. No Claude Code, no gh, no claw scope, no MCP bootstrap. Two different files named `bootstrap-node.sh` with different step models; nothing composes them. |
| **R5** | Resolve identity | **EXISTS, EMPTY** | `resolve_identity(harness, ...)` is already harness-keyed (`node_identity.py:170,208`). Live on this host: `--harness claude-code` → *"no identity is declared for harness 'claude-code' (declared harnesses: none)"* rc=1. Sole declaration is one node, one key (`node-vocabulary.yaml:58-59`). |
| **R6** | Prove provenance | **PARTIAL** | Signing primitive is **one shared symmetric HMAC** for the whole fleet (`chit_security.py:45,91-100`) — same secret signs and verifies. **[CORRECTED]** per-agent Ed25519 tooling *does* exist and 3 keys are in `allowed_signers`; what's missing is any runtime verifier that uses them (only stated consumer is `git verify-commit` via hand-set git config). |
| **R7** | Rejoin the bus | **EXISTS, TRIVIAL** | Verified live: `docker inspect pmoves-nats-1` → `["-js","-m","8222","--user","nats","--pass","pmoves"]` — compose defaults resolved. Access is not the problem; attribution is. |
| **R7a** | NATS leaf / per-node identity | **MUST-BUILD** | Lab-verified account/leaf template (`pmoves/config/nats/pmoves-nats.conf`) is **mounted by nothing** — grep across all compose/scripts returns empty. No make targets for leaf bring-up. Leaf start is a hand-typed `docker run` in a config comment. |
| **R8** | Register presence | **BROKEN BY A STRING** | `pmoves/services/node-registry/` is a complete 4-module service (~74 KB) with subscriber, storage, and the `/query` endpoint work-marshaling already calls (`work-marshaling/__init__.py:538`). It subscribes to **`compute.nodes.announce.v1`** (zero publishers). mesh-agent publishes **`mesh.node.announce.v1`** (zero subscribers). **Two finished halves wired to different subject strings.** |
| **R8a** | node-registry deployability | **MUST-BUILD** | No Dockerfile, no compose entry, and it expects a JetStream stream `compute` that `init_streams.sh` does not create → silently falls back to core NATS (`registry.py:157-168`). |
| **R9** | Be routable | **MUST-BUILD** | `work-marshaling/__init__.py:520-533,563-566` routes on `{online_only, requires_gpu, tier, min_cpu, min_ram_mb}` sorted by `utilization_score`. No skill, success rate, or reputation term. **[CORRECTED]** the *measurement* half exists and is deployed (model_fitness); the **routing consumer does not** — grep for `model_fitness_records\|fitness_score` outside the 3 owning files → one unrelated local var. |
| **R10** | Verify membership | **MUST-BUILD** | `pmoves/scripts/bootstrap-node.sh` steps 4–7 are all warn-and-continue: NATS probe warns and skips if `nats` CLI missing; runner registration prints manual instructions; mesh announce warns "announce skipped"; MCP bootstrap warns. **Nothing fails the run.** `verify-jetson-fleet.sh:121` is a warn-only ping. "Done" is unfalsifiable. |

**Cheapest high-value item in the whole contract: R8.** A rename or a 10-line bridge subscriber plus a Dockerfile turns fleet registration from "unbuilt" into "working". It is not a new service.

---

## 3. Identity, provenance, lineage

### What survives a model change
Exactly one thing: the git `Co-Authored-By:` trailer. Last 500 commits show **8 distinct model strings** (285 "Claude Opus 5", 161 lowercase variant, 77 "Claude Opus 5 (1M context)", 60 "Claude Opus 4.8", 48 "Claude Fable 5", 77 Mavis, 62 Agent Zero, 7 "Opus 4.8 (1M)"). That's per-commit free text with no schema.

The signed artifact records **nothing**. `signature.v1.schema.json` properties are exactly `[agent_id, display_name, glyph, color, accent, voice, phase, timestamp, resonance, summary, selected_alter, handoff, signing_card_id, cgp_attribution]` with `additionalProperties: false` — **sealed against adding a model field at emit time**. No model, no provider, no node, no commit SHA.

### What survives a provider change
Nothing. One mutable path on one alter (`agent_signatures.yaml:75 provider_cascade:`). No per-event capture anywhere.

### What survives an identity change
Nothing structural. The only ancestry edge is `alters:` — one level deep, child-under-parent. It cannot express "z890-claude became b850-claude". The system's own workaround proves the gap: **six hand-edited `[CORRECTION 2026-05-16: attributed to B850-CLAUDE ... mis-signed as Z890-CLAUDE]` annotations were inserted into existing register lines**. History was rewritten in place because there is no forward link.

### The three structural defects
1. **Pointer, not snapshot.** `signature.v1` stores `agent_id` + `selected_alter` as pointers into a mutable YAML. Edit `claude-opus-5`'s model field tomorrow and every past signature silently now claims the new model. The registry is already drifted: `claude-opus`'s registered co_author is "Claude Opus 4.6" (`agent_signatures.yaml:28`) — **zero** of the last 500 commits carry that string.
2. **No append-only ledger.** The single signed artifact is `pmoves/docs/logs/graphiti_signed_latest.json`, opened `"w"` every run (`sign_trail.py:349`), **gitignored** (`pmoves/.gitignore:34`), `git ls-files` → 0. At any instant exactly one signed payload exists on disk. And no JetStream stream covers `agent.>` (verified: the 11 streams are voice_relay, GEOMETRY_CGP, TOKENISM_ATTRIBUTION, BOTZ_COORDINATION, MESH_GPU, ROOMS, AGENTZERO, CONTENT_PROVENANCE, COMFY_COLLAB, HELPDESK, ARCHON). NATS publishes of signed trails are fire-and-forget into nothing.
3. **Shared key.** Any holder of `CHIT_PASSPHRASE` can sign as any `agent_id`. The repo says so about itself: `pmoves/docs/pilots/fordham-hill/08-voter-identity-key-custody.md:31-32` names `chit_security.py:91` as "the flaw to fix".

### Corrections to earlier reads
- **[CORRECTED]** "1 of 25 cards has an ssh_fingerprint" was a grep quoting artifact. The real number is **3** — two cards write the value unquoted (`signing_identity_cards.yaml:169` crush, `:329` spark-runner). `python3 -m pmoves.tools.keygen_cards audit` → `complete (3)` / `pending-ml (22)`.
- **[CORRECTED]** "no reverse check that an emitting agent_id has a card" is wrong. `model_fitness.py:316-366 verify_agent_identity()/require_trusted_agent_identity()` loads all three files and raises. Scope is narrow (model-onboarding path only, one caller at `hf_model_onboard.py:322`) — but it exists and is the pattern to generalize.

### Attribution-model consequence
`address` is the sole key of `recordsByAddress`, the Dirichlet maps, and the GroToken holder map — **and it is inside the hashed Merkle leaf** (`shape-attribution.ts:142-150`). There is no rotation, alias, or merge mechanism. A participant who changes address starts empty, and you cannot repair history without invalidating every Merkle root for that week/category. Separately: `verifyProof(leafHash, proof)` recomputes the root from `proof.path` and compares to `proof.merkleRoot` — **both from the same object** — so a fabricated record carrying its own root passes verification.

**Bottom line:** the durable provenance record in this repo is unsigned prose markdown (`docs/AGENT_TRAIL.md` 1118 lines; `AGNOTE4482PHI.t1.md` 2156 lines), while the cryptographic layer is ephemeral and overwritten. That is backwards from what every architecture doc implies.

---

## 4. The sibling-identity question

*"Crush running GLM 5.2" and "Claude Code running Opus" — same role, different harness+model. Can the system name them as two things and relate them?*

**No. The join field exists and is empty.**

**Exists:**
- The identity resolver is **already harness-keyed**: `resolve_identity(harness, ...)` reading a per-node `default_identity: {harness → registry key}` map. This is precisely the right axis.
- On the fitting branch (`origin/feat/model-harness-fitting`, 15 commits ahead, **not on main**), a `fit: {harness: {role: [observations]}}` table exists with a validator.

**The blockers, concretely:**
1. **Populated for one node, one harness.** `default_identity` appears once in the whole vocabulary. Live: `node_identity.py --harness crush` → "declared harnesses: none", rc=1.
2. **Two disjoint harness key spaces.** `default_identity` uses free text `claude-code`; `fit` validates against registry entries with `kind: harness` — of which there are exactly **two** (`clawz` at :2064, `kilocode_glm` at :144, and **zero on main**). Registry keys contain no hyphens, so `claude-code` matches no entry. `crush` and `claude_4090` are not marked `kind: harness`. Neither harness in the question can appear in a fitting today.
3. **No model on any coding identity.** Of 100 registry agents, exactly **one** has a `models` key (`mai_ui`, a UI vision model). `claude_4090` does not say it runs Opus; `crush` does not say it runs GLM. Half of what distinguishes the two sessions is not a property of the identity.
4. **No sibling relation is expressible.** `role_class` (`planner|worker|reviewer`) is carried by **2 of 100** entries and is too coarse — every worker would be a sibling of every other. The idea exists only as prose: `agent-profiles/kilocode_glm.yaml:63-71 multi_agent.siblings` lists `{agent: claude-opus, tool: "Claude Code CLI", role: analysis_and_field_briefs}` by hand.
5. **Three disjoint role vocabularies.** Session roles (`.claude/agents/*.md`, 21 files, injected as *prose* into `--append-system-prompt` at `claude-pmoves.sh:131`); `role_class` (3 values); task roles (`model-roles.yaml`, 19 values, branch-only). "Siblings in role" is ambiguous until these are related.
6. **`harness_mappings` is misnamed** — its keys are task roles (`deep_debugging`, `code_review`), not harnesses. Zero code consumers (`grep -rn harness_mapping --include=*.py --include=*.ts` → nothing). `kong_route_seeder.py:239-268` is the only model-suits reader and it takes routing identity only.
7. **The fitting branch defers the router by design** — its own plan (`docs/superpowers/plans/2026-08-25-model-harness-fitting.md:22,967`) marks §4 router "deferred to the follow-on plan".
8. **`PMOVES_NODE_IDENTITY` is a single unqualified scalar**, applied *before* the harness lookup (`node_identity.py:207-209`). Two harnesses in one shell cannot be overridden separately.

Nowhere in the system does the tuple `(identity, harness, model, role)` exist.

---

## 5. What blocks turning on the GEOMETRY BUS — ranked

**B1 — Nothing publishes.** *(Root cause. Everything below is secondary.)*
- flute-gateway: lifetime counters never incremented over 9 days.
- consciousness-service: publish gated on a per-request flag nothing sets.
- evo-controller: crash-looping before its publish step.
- supaserch / deepresearch / extract-worker / ffmpeg-whisper / semantic-cache: not deployed.
- The only working end-to-end producer is **`pmoves/tools/beats_to_cgp.py` — an operator-run typer CLI**, not a service.
**Turn-on action:** run `beats_to_cgp` manually first. It is the only thing that will put a byte on the bus today.

**B2 — No JetStream consumer binds.** tokenism-simulator's durable subscribe fails `NotFoundError` and falls back to core NATS. Streams with `retention=limits` and zero consumers are write-only archives — any packet published while a consumer is down is invisible to it forever. **Fix before B1, or the first traffic is unobservable.**

**B3 — A live publisher violates its own contract, into the settlement ledger.** `semantic-cache/tokenism.py:53-58` sends `{agent_id, tokens_saved, cost_saved_usd, cache_key}` to `tokenism.attribution.recorded.v1`, whose schema requires `{chit_id, address, action, amount, week, timestamp}` with `additionalProperties: false`. Wrong on all 6 required fields plus 4 forbidden. **Nothing validates at the broker.** If this service comes up, it writes invalid rows into `TOKENISM_ATTRIBUTION` undetected, and publisher-discord renders "Attribution Recorded: None". *(It currently has zero callers — keep it that way, or fix the payload first.)*

**B4 — No schema enforcement between publisher and stream.** The only fence found is client-side in `beats_to_cgp.py:418`. 8 tokenism + 6 geometry schemas exist and are enforced only in tests and one CLI.

**B5 — The head of the attribution chain has no production caller.** `tokenism.cgp.weekly.v1` has a publisher **[CORRECTED]** but nothing invokes it, so `tokenism.swarm.population.v1` (published only from inside the weekly handler) is a dead chain hanging off a dormant head. The EvoSwarm feedback loop is unreachable regardless of bus health.

**B6 — Subject catalog is unreliable in three ways.**
- The context doc lists 12 subjects; code has **21**. Undocumented: `geometry.beats.control.v1`, `geometry.cgp.v2`, `geometry.health.v1`, `geometry.wealth.v1`, `geometry.packet.decoded.v1`, `geometry.packet.encoded.v1`, `geometry.publish.gate.v1`, `tokenism.prosodic.bpm.v1`, `tokenism.calibration.result.v1`, `tokenism.simulation.result.v1` — including the two the only working producer actually uses.
- **[CORRECTED]** There are **two divergent copies** of `geometry-nats-subjects.md`: `.claude/context/` (488 lines, 10 subjects) vs `pmoves/.claude/context/` (639 lines, 13 subjects). Subject-count audits are not reproducible until one is deleted or symlinked.
- The graphiti registry is stale and **under-reports**: `nats_subject_registry.py:46` marks `geometry.cgp.v1` "defined_only — no subscriber code" while three services subscribe and one holds 8 live connections. Audits built on it will mis-rank what to fix.

**B7 — Doc⇄code contradictions that will misdirect debugging.**
- Doc: SupaSerch publishes `tokenism.cgp.ready.v1` gated by `SUPASERCH_CGP_PUBLISH`. Code publishes `geometry.cgp.v1` (`app.py:36,261`); the env var has **zero hits in code** **[CORRECTED — it does appear in docs and the duplicate context copy]**.
- Doc: `geometry.cgp.v1` is "published via Supabase Realtime". It is an ordinary NATS core subject. This sends debuggers to the wrong system entirely.
- Doc: consciousness-service publishes "always (n/a)". It's per-request gated — which is exactly why the healthy container is silent.

**B8 — Hardcoded NATS credential in a committed tool.** `beats_to_cgp.py:77` `nats://nats:pmoves@nats:4222` as the default. Public repo; same leak class `geometry_bus_health.py` was explicitly rewritten to remove. **Fix before running the tool that turns the bus on.**

**B9 — Two version axes routinely confused.** Packet `spec` is `chit.cgp.v0.1/v0.2`; subject/envelope `type` is `geometry.cgp.v1`. Code accepts both (`shape_store.py:490`, `gateway/api/chit.py:234-235`) — fine, but any new producer will guess wrong at least once.

**Restart order that actually yields a green bus:**
1. Fix B8 (credential), then B2 (create the durable, or make the fallback loud instead of silent).
2. Run `beats_to_cgp` by hand → confirm a nonzero `msgs` on `GEOMETRY_CGP` and a bound consumer.
3. Only then bring up gated publishers, keeping semantic-cache out until B3 is fixed.
4. `uv run pmoves/tools/geometry_bus_health.py --json` as the acceptance gate (last run: `active 0, idle 8, missing 16, health_pct 0.0`).

---

## 6. Open questions for the operator

1. **Node-bound identity is a doctrinal reversal, not a gap-fill.** `agent_signatures.yaml:45` ("the node is a location, not an identity") and `ROOM_MANIFEST_CONTRACT.md:55` (manifests must not hardcode node names) both state the opposite of "home node where the identity was formed". Portability is currently free — but so is impersonation; they are the same absence. **Do you want forgery resistance at the cost of the stated portability doctrine?**

2. **Which anchors attribution — `address` (string, tokenism.*) or `contributor_id` (uuid, token.*)?** They share no field, no mapping table, no code path. Both ledgers are empty (`TOKENISM_ATTRIBUTION` 0 msgs; `work_attestations` may not even be applied). This is a **greenfield design decision**, not a migration. Pick before the first byte lands, because `address` is inside the Merkle leaf and cannot be changed after.

3. **Which JetPack does a fresh Jetson get?** The repo pins three answers: bootstrap+verify target JetPack 7.0/R37/CUDA 12.8; `jetson-jons-{1,2,3}.yaml:27` pin `l4t-jetpack:r36.4.4` (JetPack 6.2); `docker-compose.arm64.override.yml:14-17` names JetPack 7.2+/CUDA 13. **Unsure which is current — I did not resolve it.**

4. **Merge, finish, or abandon `origin/feat/model-harness-fitting`?** It carries `fittings.py` and `model-roles.yaml`, is 15 commits ahead, is not on main, and defers the router by design. This decides whether the sibling-identity answer is "invent from scratch" or "merge, then add the join". *I did not check PR state or the claim register.*

5. **Which "role" means sibling — session role (`node-steward`) or task role (`code_review`)?** The launcher injects the first as prose; the fit table keys on the second. A design that silently picks one will mismatch the other consumer.

6. **Retire the 8122 P7 stanza?** Two compose blocks ship the same image: `p7` (8120, `P7_PMOVES_ROOT=/etc/pmoves`, `docker-compose.yml:3622-3660`) and `p7-room-orchestrator` (8122, `/app`, `:4075-4130`). Both are in the `agents` profile, so bringing that profile up starts both. `SERVICE_DOCS_MATRIX.md:31` documents the **8122** one — an operator following the service matrix probes the instance the Makefile comments call "legacy". *No deprecation ticket found.*

7. **Seeded-live rooms bypass the CHIT gate.** Only 3 of 13 manifests carry `meta.chit.card_id`; `persona.room.livingdoc.json` ships `stage: live` with no card, and three rooms carry `current_stage: live` sourced from `"ROOMS_ON_A_STAGE.md typical-stage table"` — a documentation table, not an activation event. `transition.py:183` gates only API-driven rehearsal→live. **Re-gate on restart, or accept that 'live' means two different things?**

8. **Was the Discord/brand half of the P7 alignment intentionally dropped?** README/CLAUDE.md now carry rooms-on-a-stage; `deploy/brand/S14_DRAFTS.md` still ships MOF/lattice-only channel copy with zero room vocabulary, and `plans/P7_SITE_DOCS_ALIGNMENT_DRAFT.md` remains "Draft — operator review required". Cannot tell from the repo.

9. **Has `model_fitness_records` ever been written to?** `/api/model-fitness` is POST-only; I had no PostgREST credentials to query the table. The bridge that would feed it (`model-fitness-bridge`) is in **no compose file**, and the collector is a CLI — so idle is likely but **unverified**. This decides whether the fitness layer is "deployed and used" or "deployed and idle like GEOMETRY_CGP".

10. **Two unverified carry-overs I did not re-execute:** (a) the `fleet-enroll ROLE=edge` rejection — confirmed indirectly via `infra.mk:279`'s usage string, not by re-running; (b) `verify_cgp` call-site enumeration for the post-hoc verifier claim. Treat both as probable, not proven.
---

## Provenance of this document

Produced by `B850-CLAUDE (Knuckles)`, Opus 5, Claude Code harness, on the
`knuckles` node, 2026-08-25 — at a moment when that identity had **no wire
presence**: `:9223/leafz` reported `leafnodes: 0, remotes: 0`, and it published
nothing to NATS. The irony is load-bearing rather than decorative: a report on
why the bus is silent, written by something the bus could not observe.

Its companion is `CONTROL_B850-CLAUDE_PRE-GROUNDING.md`, the control specimen for
the same identity, written the same day for post-restart comparison.

`agent_signature: ACK::B850-CLAUDE::PRE-RESTART-PREFLIGHT::Opus-5::2026-08-25`
CHIT trail **unsigned-local** — which §3 of this document explains is the only
state currently available, since the signing key is shared fleet-wide.

<!-- GRAPHITI_MARK: B850-CLAUDE::PRE-RESTART-PREFLIGHT::2026-08-25 -->
