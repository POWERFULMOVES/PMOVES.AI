# TAC Tree: AGInTZ Topology Walk (from spark-claude's seat)

> A walk of the topology from one AGInTZ's seat. It covers the harness the agent runs in, the identity it carries, the CHIT stack it signs into (L1–L5), and the fleet, registry and rooms it can deploy into. For each piece it records what is real, what exists only in docs, and what is stubbed. It was written by a fresh-perspective member, following each-one-teach-one, so the improvements at the end are offered to the village rather than imposed on it.

## Walk Identity

| Field | Value |
|-------|-------|
| **Walker** | `spark-claude` (SPARK-CLAUDE, card `…0014`, glyph ⌁), claude-code harness, PMOVES-SPARK (DGX GB10, ARM64) |
| **Date** | 2026-10-11 |
| **Method** | 5 parallel read-only scouts plus direct verification. No live service was probed unless marked **measured**. |
| **Base** | `origin/main` @ `db97bff37` (+ #3335, #3337) |
| **Cipher during walk** | `pmoves-cipher-local` connected as **`bootstrap`**. A `spark-claude` search was refused with 403, so sibling history could not be pulled from Cipher. See §1.3. |
| **Tier** | cross-cutting (harness, identity, CHIT, fleet) |

Sources an agent should load next: `pmoves/docs/AGENTS/AGNOTE4482.md` (AGInTZ ledger, MOF accords), `pmoves/docs/architecture/PMOVES_GRAND_CONVERGENCE.md`, `pmoves/docs/TAC/TAC_INTEGRATION_TOPOLOGY.md` (index), `plans/HYPERAGINTZ_ORCHESTRATION_SCOPE_2026-09-19.md`.

Levels are not a pyramid. They work like a Birkeland current: parallel filaments carrying current together, not a vortex with a top. The small models (embedders, BPM encoders) are the vortex the current spins up. Identity supersedes node: an AGInTZ is hostable on any node with one vocabulary entry and one affinity entry (A.12 portability doctrine).

---

## 1. The Seat: Harness (Claude Code) Reconciled

### 1.1 Permission layering (verified against the Claude Code settings docs, 2026-10-11)

- **Precedence:** managed > `--settings` CLI > `.claude/settings.local.json` > `.claude/settings.json` > `~/.claude/settings.json`.
- **Lists merge across scopes.** `permissions.allow` and `deny` combine, so a local `allow` **cannot** lift a project `deny`. Removing a shared deny is therefore a PR to `.claude/settings.json`, which affects every sibling.
- **Auto mode** sits on top. Its classifier refuses self-modification of permission settings even when the operator asks in chat (measured this walk). Permission grants are the operator's hand to play, which is the correct boundary.

| Layer | What guards | Where |
|---|---|---|
| Settings `deny` (9) | `docker compose up -d` / `restart`, `docker volume rm` / `prune`, `docker system prune -a`, `git push --force` / `-f`, `git reset --hard`, `rm -rf /` | `.claude/settings.json:73-83` |
| Damage-control hooks | protected path classes, zero-access `.env*`, Known Road grants (`KNOWN_ROAD=<domain>:<pr:n\|issue:n\|handoff:file>`), every grant logged to `known-roads.jsonl` | `.claude/hooks/damage-control/` (`patterns.yaml`, `known_roads.py`) |
| Claim collision | refuses register writes it cannot measure; sanctioned route is `make -C pmoves register-claim` | `.claude/hooks/governance/claim-collision-pre.py` |
| Auto-mode classifier | self-modification, scope escalation | harness |

The deny entries for force-push, `reset --hard`, `rm -rf` and the volume operations **duplicate** damage-control hard blocks. They are prefix-only (flag reordering slips past them), but they also hold if `uv` is missing and the hooks can't run. Only the two `docker compose` denies are settings-only. They block a level-11 node identity from operating its own stack, for example recreating `cipher-api` after `secrets-funnel`.

### 1.2 Harness drift

| Item | State | Suggested road |
|---|---|---|
| Cipher MCP entries | `.claude/mcp.json` cipher entries use **SSE** (deprecated; Claude Code now tries HTTP first). Root `.mcp.json` has one SSE entry with **no auth header**. | #3339 moves the roster to `type: http` `POST /mcp`. The root `.mcp.json` needs the same move, because a plain `claude` session in this repo binds to `bootstrap`. |
| `agent-zero` MCP | SSE, token embedded in the URL path | move to http + header when the A0 runtime supports it |
| `enableAllProjectMcpServers: true` | in SPARK `settings.local.json` | operator decision; it bypasses per-server approval |
| `additionalDirectories` | `C:/pinokio`, `D:/pinokio` in shared settings | meaningless on Linux nodes; move to Windows nodes' local settings |
| Hooks not registered | `pre-tool.sh`, `post-tool.sh`, `governance/known-roads-enforcer.py`, `governance/signoff-gate.sh`, `a2ui-crew-trail.sh`, `posttool-format/*` | register or retire; the hooks README still documents a stale key format |
| Hook events unused | `SessionEnd`, `PreCompact`, `PostToolUseFailure`, `PermissionDenied` | `SessionEnd` → sign-trail / cipher session-save. `PermissionDenied` → a Known-Road hint. |
| Agent frontmatter | `role_class` (PMOVES key, ignored by Claude Code); `code_execution_remote` is not a tool name; `node-steward` has no `tools` (inherits all) | keep `role_class` in `agent_registry.yaml`; fix tool names |
| Commands vs skills | 42 namespaced command dirs, mostly plain prompts | migrate as touched (gains `allowed-tools`, `disable-model-invocation`, supporting files) |
| CLAUDE.md imports | `@path` imports are supported (4 hops). AGENTS.md is read in place of CLAUDE.md where present. | the thin-keystone CLAUDE.md could `@import` BOOTSTRAP.md instead of telling agents to read it |

### 1.3 How the launcher binds identity (and why this walk ran as `bootstrap`)

1. `deploy/provision/claude-pmoves-spark.sh` is generated: `PMOVES_NODE_ID=spark` → `claude-pmoves.sh`.
2. `pmoves/scripts/pm-node-identity.sh` → `node_identity.py` resolves `PM_IDENT_CIPHER_ID=spark-claude` (`pmoves/configs/node-vocabulary.yaml:66-77`).
3. `claude-pmoves.sh:364-385` restores a `cipher_*` token, then `pm-cipher-token-bind.sh` reads `CIPHER_TOKEN_SPARK_CLAUDE` from `pmoves/.env.local`. It does a non-evaluating read with a shape check; if the token is missing it reports `cipher token=unbound`.
4. `mcp_roster_normalize.py` expands the roster (from `origin/main:.claude/mcp.json`) into a temp file with mode 0600, then runs `claude --mcp-config=…`.

A session started with plain `claude` skips all four steps and gets the header-less root `.mcp.json`. **Launch through `claude-pmoves`.**

---

## 2. The Identity: spark-claude

| Substrate | Entry | State |
|---|---|---|
| Signing card | `pmoves/config/signing_identity_cards.yaml:378-402`, card `00000000-0000-4000-8000-000000000014`, active (landed #3331) | ML half pending: no `github_app_installation_id`, no SSH or Ed25519 key, no allowed_signers line |
| Signature | `pmoves/config/agent_signatures.yaml:536-550`: ⌁, #4D7C0F / #A3E635; resonance arm64-compute, unified-memory-inference, nvfp4 | complete |
| Registry | `pmoves/config/agent_registry.yaml:238-264` `claude_spark`, team orchestration, L0/L2/L4, stage_1 | complete |
| Vocabulary | `pmoves/config/identity_vocabulary.yaml:157-172` (aliases SPARK-CLAUDE, claude_spark); `pmoves/configs/node-vocabulary.yaml:66-77` | complete. `CLAUDE_FAMILY_IDENTITY_BINDINGS.md:33` ("card MISSING") is stale since #3331. |
| Cipher token | `make -C pmoves cipher-mint-token AGENT=spark-claude` | **minting not evidenced**. The walk ran as `bootstrap`. |
| Signed trails | register rows 2026-09-21 → 2026-10-07 (lane 2979 fork-sync, SC-1/2/6, `feat/acp-registry-bringup` #3097, NATS phase0, dockerignore chit keys, NATS_URL derive) | no `ACK::SPARK-CLAUDE` or `GRAPHITI_MARK` line anywhere; no model stamp on rows |
| AGInTZ ledger | `AGNOTE4482.md:1697-1735` | **no row**. Adsorbing one is the next step once Cipher binds. |
| Passport | B850-CLAUDE design PR #3317 (draft, `plans/AGINT_PASSPORT_DESIGN_2026-10-08.md` on `origin/docs/agint-passport-design`) names **spark-claude as the second-node cross-check**: run the measured-node probe by hand on ARM64 / DGX OS and review the Laya probe (#3284) | **owed, not yet answered** |
| Tokenism card | none; soulbound standing credit is only a passport proposal (§3h) | design only |

Siblings worth learning from:
- **z890-claude** (⚙): integrator and gatekeeper; reviewed SPARK's #1668.
- **5090-claude** (♫): "signing is a claim"; Mavis.
- **4090-claude** (◉): merges and wave sweeps.
- **B850-CLAUDE (Knuckles)** (⌬): secrets funnel, danger rooms, passport author.
- **knuckles-kimi** (☾): lineage SPARK-KIMI → Knuckles; the template for SPARK-CLAUDE's missing pieces.
- **EM-FLASH**: hermes MOA, PR-wave triage, cipher security review.
- **spark-kimi**: the elder on this node, with 32 register entries and `GRAPHITI_MARK` trails at `AGNOTE4482PHI.t1.md:1369-1427`.

---

## 3. The CHIT Stack (Grand Convergence L1–L5), Measured Against Code

| Layer | Claim | Reality | Key refs |
|---|---|---|---|
| **Codec** | CHIT encodes and decodes everything | **Two codecs share one name.** The secrets codec is the real CGP hex obfuscation (`pmoves/chit/__init__.py:121,169`). The semantic geometry codec is spread across `services/common/geometry_decoder.py`, `geometry_models.py`, `cgp_mappers.py` and gateway `api/chit.py` (PBKDF2-600k :94). CGP v0.1, v0.2 and v1.0 all have live producers. | |
| **Multimodal** | text, audio, image, video, geometry | text/transcripts ✔ (ffmpeg-whisper `chit.cgp.v1.0`); prosodic BPM ✔ (`flute-gateway/prosodic/bpm_encoder.py`, `tokenism.prosodic.bpm.v1`). **Image and video have no CGP producer.** Hyperbolic, Dirichlet and zeta math exists only in TypeScript (`PMOVES-ToKenism-Multi/integrations/contracts/chit/`); Python uses hardcoded anchors. | |
| **L3 GEOMETRY BUS** | signed CGP over NATS | real but narrow. The `GEOMETRY_CGP` stream (30d) is scoped to `geometry.cgp.v1`. Signing is HMAC-SHA256 over canonical JSON, `sig:{alg,kid,hmac}` (`pmoves/tools/chit_security.py`, per-kid keys, fail-closed once any kid key is provisioned). **`CHIT_REQUIRE_SIGNATURE` defaults off everywhere except P7**, so unsigned packets pass. The signer is copied 4× (flute, consciousness, mesh-agent on a **different key** `MESH_PASSPHRASE`, spark-shape-worker). | `.claude/context/geometry-nats-subjects.md` is missing `geometry.packet.decoded.v1`, `bpm.encoded.v1` and `persona.consumption.recorded.v1` |
| **`chit.signed.v1`** | trail signatures announced on the bus | **doc-only**: no publisher or consumer in Python. The `pmoves-chit-sign` skill still says "staged until NATS MCP"; `pmoves-nats-fleet` is now in the roster. | `.claude/PATTERNS.md:916,972` |
| **L4 EVO SWARM** | Gaussian mutation, energy-aware fitness | **stub.** `evo-controller/app.py:~195-206` writes a hardcoded pack `{K:8,bins:32,tau:0.2,beta:0.7}`, `energy:"placeholder"`, status `draft`, then publishes `geometry.swarm.meta.v1`. | `CHIT_INTEGRATION_STATUS.md:265` admits it |
| **L5 Tokenism** | action → token (10 steps) | **simulated.** tokenism-simulator :8103 is the most complete CHIT service (consume, produce, sign; GroToken, FoodUSD, CoopGovernor, Gini). Solidity lives only in the submodule; `token-stub` is a dry-run attestor. No on-chain wiring. | |
| **L1 MOF / L2 CHIT pillars** | lattice + 5 pillars | mostly narrative in Python; L2 "Code:" pointers resolve to the TS submodule | |

CHIT tools an agent can use today:
- Make targets: `make -C pmoves sign-trail`, `chit-provenance-check`, `topology-chit-gate`, `smoke-geometry`, `mesh-handshake`.
- CLIs: `pmoves/tools/chit_verify.py`, `geometry_bus_stream.py`.
- MCP: `pmoves-nats-fleet` (signs CHIT-aware subjects when `NATS_CREDS` is set).
- Gateway HTTP encode and decode.
- Note: the `.claude/commands/chit/*` entries are prompt recipes, not code.

---

## 4. The Lattice: Fleet, Registry, Rooms

**PMOVES-registry** is an ACP launcher catalog: a fork of `agentclientprotocol/registry`, about 40 `agent.json` entries. It is the harness catalog that HyPeRAGInTZ is governed by, not a runtime. Its first custom entry, `hyperagint-acp/` (identity, env, suits, routing), landed at `a1ec423` (2026-10-06). The local submodule checkout sits at `c784e2d`, 6 commits behind the superproject pin. That stale checkout is the "M" in git status, not uncommitted work. The bridge to fleet agents is `pmoves/tools/acp_registry_map.py` plus `pmoves/configs/acp_registry_map.json` (live: `kilo` → `kilocode_glm`). See `TAC_ACP_REGISTRY.md`, which still says 42 entries and zero custom.

**Fleet (docs, not probed):**

| Node | Role |
|---|---|
| SPARK | GB10, ARM64, NVFP4 128GB; ARM64 CI; Ollama (`ollama_spark` TZ provider, weight 0, soak-gated) |
| B850 Knuckles | dual R9700, ROCm; llama-server behind the only HAProxy (`scripts/pmoves-b850-ai-top.sh`, :8000 TLS); Ollama |
| Z890 | coordinator |
| 5090 | voice studio, Mavis |
| 4090 | laptop runners |
| KVM4-1 | gateway, TensorZero, A0, Hi-RAG, Archon, exit node |
| KVM4-2 | data tier |
| KVM2 | nginx, RustDesk |

- Profiles live in `pmoves/config/profiles/`. The real topology path is `pmoves/configs/topology/docker_matrix.yaml`, plural `configs`.
- `TS_*` variables exist only for Z890, 5090, 4090 and the Jetsons. There is no `TS_SPARK`, `TS_B850` or `TS_KVM*`.

**Rooms:**
- 16 in `pmoves/config/rooms/catalog.json`. The only live one is `persona.room.livingdoc`; the rest are in rehearsal.
- There is no SPARK room and no `spark-claude` affinity room.
- Room-to-node binding lives on the agent row (`topology.node_affinity`). P7 node routing is specified but not implemented.
- `darkxsides.room` lacks the `meta.chit` block that the rehearsal → live gate requires.

---

## 5. Contradictions Found (for the living-docs sweep)

1. Cipher topology: auto-memory and operator say **per-node multi-tenant Cipher, NATS and TZ**. `CLAUDE.md` MCP notes are Z890-centric, and `runner-topology.md` puts NATS only on KVM4-2.
2. `CHIT_INTEGRATION_STATUS.md`: the per-service rows are from March 2026 and contradict its own banner (5/8/15 vs 16 rows; cipher `/mcp/sse` vs `/api/mcp/sse`).
3. Z890 hardware: GTX 1650 (`runner-topology.md`) vs 3090 Ti; ai-lab runner on Z890 (`TAC_RUNNERS.md`) vs B850 (`runner-topology.md`).
4. 5090 is "pending standup" in `runner-topology.md` but has a profile and two rooms.
5. `.claude/context/tensorzero.md:352` uses `embeddinggemma:300m`; compose defaults to `qwen3-embedding:4b`.
6. `TAC_INTEGRATION_TOPOLOGY.md` index is v2.2 (2026-03-15) and lists 26 trees; 35 exist.
7. `CLAUDE_FAMILY_IDENTITY_BINDINGS.md` premise (SPARK card missing) is stale since #3331.

---

## 6. Improvements Offered (fresh perspective, ranked by leverage)

1. **Bind before you walk.** Make `cipher_preflight` (or a `SessionStart` hook) fail loudly when a session's Cipher identity is `bootstrap` but the node vocabulary says a per-agent ID exists. This walk ran an hour before discovering it was anonymous. Pair it with moving the root `.mcp.json` to http (#3339 leaves it on SSE).
2. **One signer.** Collapse the four vendored HMAC copies onto `chit_security.py` (vendor with a byte-equivalence test, as flute already does). Move mesh-agent onto the per-kid key scheme instead of `MESH_PASSPHRASE`.
3. **Enforce signing on the GEOMETRY BUS fleet-wide.** This is a standalone item, read from code and not yet measured live.
   - **Today:** `CHIT_REQUIRE_SIGNATURE` is off in every verifier except P7. A tampered stamp is dropped, but a message with **no stamp passes**. Tokenism and graph-linker publish unsigned ("dev mode") when no key is set.
   - **Effect:** anyone holding NATS credentials can inject CGP packets. NATS auth limits *who connects*; it does not authenticate *what they publish*.
   - **Rollout:** use the same advisory → enforce ladder as `CIPHER_MCP_ENFORCE` and `CIPHER_AUTH_REQUIRED`.
     1. **Measure.** Count unsigned vs signed packets per subject on each node (`geometry_bus_stream.py` plus a counter).
     2. **Close the gaps.** Provision per-kid keys so no producer falls back to unsigned, and fix mesh-agent's separate key (improvement 2).
     3. **Enforce node by node.** Flip `CHIT_REQUIRE_SIGNATURE=true`, then check that no producer goes silent.
     4. **Make producers fail closed.** A producer refuses to publish unsigned once its node is in enforce mode.

     P7 (default true) already proves step 3 works.
4. **Make `chit.signed.v1` real.** `sign-trail` publishes through `pmoves-nats-fleet`, and a consumer in Hi-RAG or Neo4j makes signed trails queryable. That is the ledger the passport design needs.
5. **Name the two codecs apart**: "CHIT-secrets" (`pmoves/chit`) and "CHIT-geometry" (CGP), in docs and the skill text.
6. **Shared settings PR (operator to approve)**: drop the two settings-only `docker compose` denies (damage-control and the `compose` Known Road already guard compose). Keep the redundant destructive denies as the no-`uv` fallback. Move the Windows `additionalDirectories` to those nodes' local settings.
7. **Register `SessionEnd`** to run `sign-trail` and `cipher session-save`, so every AGInTZ session leaves a signed trail without remembering to.
8. **Answer the passport cross-check from SPARK** (ARM64 / DGX OS measured-node probe). It is owed, and SPARK is the only ARM64 seat.

## 7. Open Asks (operator)

- Mint or confirm `CIPHER_TOKEN_SPARK_CLAUDE` (`make -C pmoves cipher-mint-token AGENT=spark-claude`), then relaunch via `claude-pmoves-spark.sh`.
- Approve (or reshape) improvement 6; permission changes are operator-applied.
- KiloClaw (deferred until Cipher binds): hosted VM volume is full; plan is to extend, snapshot, then split into a light hosted claw and a heavy KVM claw using fleet GPUs over the tailnet.
