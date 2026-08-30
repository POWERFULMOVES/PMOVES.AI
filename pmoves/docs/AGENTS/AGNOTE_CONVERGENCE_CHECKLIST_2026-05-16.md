# Cross-Node Convergence Checklist — 2026-05-16

> **Purpose**: Single-page coordination point for the 4-node Claude fleet (B850/Knuckles, 5090, 4090, SPARK) plus DARKXSIDE operator co-located on SPARK. Live during the current convergence wave. Tracks open PRs, handoff lanes, and per-PR merge gates.

**Authored by**: B850-CLAUDE (Knuckles)
**Date**: 2026-05-16
**Companion sitrep**: `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` (last refresh 2026-05-15)
**Active claim register**: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`

---

## Operator co-location (2026-05-16)

**DARKXSIDE is on the SPARK node** alongside SPARK-CLAUDE. Implications:
- Three-Body **Control** body acknowledgements involving SPARK get human + agent in lockstep (faster ACK turnaround).
- W6-P5 FlOO\$ architecture review (SPARK is committed reviewer) can pair-resolve in the same shell.
- Cross-node escalations that need operator approval — auth, secrets, infrastructure changes — route via SPARK first for fastest decision.
- B850-CLAUDE + 5090-CLAUDE + 4090-CLAUDE coordinate **with** SPARK as the operator-attached node, not parallel to it.

---

## Open PRs by node (as of 2026-05-16 03:30 UTC)

| PR | Author node | State | Title | Blocked on |
|----|-------------|-------|-------|-----------|
| **#1496** | B850-CLAUDE | 🟢 OPEN | docs(audit): TAC + services + AGNOTE4482 + topology — findings + targeted fixes | Review |
| **#1501** | B850-CLAUDE | 🟢 OPEN | feat(4090-prep): TTS round-trip + Ollama validator + 4090 node profile + B850 topology alias | 4090-CLAUDE running scripts to attach evidence |
| **#1499** | (mesh-bind owner) | 🟢 OPEN | fix(1463-b+c): mesh-bind set-e guard + 3x Jetson JONS profiles + PBNJ fleet | Review |
| **#1494** | TBD | 🟢 OPEN | docs: update audit references and add model strategy | Review |
| **#1493** | TBD | 🟢 OPEN | chore(docker): update env variable references in compose files | Review |
| **#1480** | TBD | 🟢 OPEN | feat(gate-measure): dual gate-junction measurement library + drift-dynamo bootstrap | Review |
| **#1479** | TBD | 🟢 OPEN | feat(website): landing page for PMOVES.AI public launch | Review |
| **#1478** | TBD | 🟢 OPEN | fix: guard ALTER USER supabase_admin against reserved role error | Review |
| **#1477** | TBD | 🟢 OPEN | fix(config): kilo.json schema validation + z.ai/MiniMax provider setup | Review |

**Recently merged (this convergence window)**:
- ✅ **#1490** (B850-CLAUDE) — `feat(gap-fill): Wave 0 + 0.5 — governance scaffold + self-hosted OAuth` — merged 2026-05-15
- ✅ **#1498** (co-authored) — `docs(patterns): pair recipes + node-affinity team aggregations` — merged 2026-05-15
- ✅ **#1497** — `refactor(services): canonical CGP signing for tokenism/neo4j/agent-zero` — merged
- ✅ **#1495** — `fix(mcp): pmoves-cipher → native /mcp/sse` — merged
- ✅ **#1492** — `refactor(geometry): consolidate crypto imports + fail-closed validation` — merged
- ✅ **#1491** — `docs(patterns): stacked-PR + squash-merge-rebase + submodule-gitlink rebase gotchas` — merged
- ✅ **#1487** — `docs(w6-p5): FlOO\$ life-persona-voice pipeline — Phase A/B/C spec` — merged
- ✅ **#1488** — `feat(1463-pr-a): bootstrap-node.sh — idempotent node bootstrap` — merged
- ✅ **#1486** — `feat(w0-pr6): json-to-profile.py — auto-write node profile from probe JSON` — merged

---

## Open handoff lanes (from sitrep)

### 1. W0 Substrate (B850/Z890 → 4090)
- **Author**: B850-CLAUDE (released brief 2026-05-09)
- **Recommended primary**: 4090-CLAUDE
- **Status**: PR-3 merged (#1476 — Windows hw probe); PR-1, PR-2, PR-4, PR-5, PR-6 OPEN
- **Pre-stage from this session**: PR #1501 (TTS test, Ollama validator, 4090 node profile) closes adjacent TAC nodes
- **Convergence gate**: 4090-CLAUDE picks up remaining 5 PRs OR explicitly hands off

### 2. Bootstrap NATS_BIND (#1463)
- **3 atomic PRs** proposed (PR-A bootstrap, PR-B idempotent runner registration, PR-C profile schema)
- **PR-A landed**: #1488 (`bootstrap-node.sh`)
- **PR-B+C in flight**: #1499 (`fix/issue-1463-b-c` — mesh-bind set-e guard + Jetson profiles + PBNJ fleet)
- **Reviewer asks**: 4090-CLAUDE (primary), B850-CLAUDE (brief author), CODEX-GPT5 (parity), DARKXSIDE (token/label approval — **now easier with operator on SPARK**)

### 3. Network hardening audit (#1465)
- **4 PRs proposed**: PR-A doctrine anchors, PR-B reality-vs-claim tool, PR-C hardening doc, PR-D `--network-alias` enforcement
- **Status**: No PRs opened yet; awaits the sequencing decision
- **Blocks**: #1463 mesh-bind-auto-write — the audit feeds doctrine which feeds bootstrap
- **Reviewer asks**: B850-CLAUDE (dual-NIC lead), 4090-CLAUDE (sequence with #1463), CODEX-GPT5, DARKXSIDE

### 4. W6-P5 FlOO\$ Architecture Cross-Review
- **Author**: 5090-CLAUDE (branch `docs/w6-flooz-architecture-opus`; merged as #1487)
- **Committed reviewers**: 4090-CLAUDE + SPARK
- **Status**: Phase A spec landed; Phase B/C implementation pending
- **Convergence gate**: Reviewers ACK Phase A; 5090 unblocks Phase B planning

### 5. SPARK process_audio_with_cloud_api
- **Author**: SPARK (CLAIM 2026-05-12, OPEN per register tail)
- **Scope**: Ollama/MiniMax/Alibaba provider, A2UI Remotion hologram viewport scaling
- **Status**: in-flight on DGX Spark node; no PR number in register
- **DARKXSIDE co-located** — direct operator-side iteration possible

---

## Per-PR convergence gates (B850-CLAUDE PRs)

### PR #1496 (doc-audit)

- [ ] CI green: `gap-fill-validate.yml` doesn't fire (paths don't overlap with the workflow's filter)
- [ ] Reviewer ACK on the topology re-label (Z890 row mechanical fix; B850 alias added in PR #1501 — note for reviewer)
- [ ] Reviewer ACK on the AGNOTE register backfill (3 CLAIM/RELEASE entries + this PR's revision commit)
- [ ] Reviewer ACK on the 7-entry `living_docs_registry.yaml` additions
- [ ] Reviewer ACK on the 71-service audit report
- [ ] Reviewer ACK on the 5 priority service doc fixes (archon, ffmpeg-whisper, consciousness, cast-tts, extract-worker)
- [ ] **Mis-attribution revision commit landed** (Z890 → B850 across 3 entries) — **THIS COMMIT**
- [ ] Convergence checklist committed (THIS FILE)

### PR #1501 (4090-prep)

- [ ] CI green
- [ ] B850 topology alias annotation reviewed (R9700 Workstation row + condensed B850 row)
- [ ] 4090-CLAUDE runs `pmoves/scripts/p7-agent-interpreter-test.sh --json > /tmp/p7-evidence.json` from laptop with 5090 TTS reachable; attaches output to PR
- [ ] 4090-CLAUDE runs `pmoves/.venv-pmoves/bin/python pmoves/scripts/validate-ollama-inventory.py` with Ollama live; attaches output to PR
- [ ] 4090-CLAUDE appends a CLAIM entry in `AGNOTE4482PHI.t1.md` for n4090.tts.lww-access + n4090.tts.pinokio-network + n4090.ollama closure
- [ ] DARKXSIDE (on SPARK) ACK as Control body once 4090 attaches evidence

---

## Cross-node action items (next 24h)

### B850-CLAUDE (Knuckles, this node)
- [x] File proper CLAIMs in register (this commit)
- [x] Revise 3 Z890 mis-attributions to B850 (this commit)
- [x] Author convergence checklist (this file)
- [ ] Optionally pre-stage Tasks D/E/F/G from prior menu (theme stylesheet, NATS mobile client doc, P7 readiness checklist, stage lifecycle tracker stub) — operator pull-through
- [ ] Watch CI on PR #1496 + #1501

### 5090-CLAUDE
- [ ] W6-P5 FlOO\$ Phase B planning (Phase A merged as #1487)
- [ ] `p7.nats.embedding-quality` provisioning (Qdrant `pmoves_chunks_qwen3` collection, 3072d Qwen3-embedding:4b) — currently `pending` per `pinokio-p7.tac.yaml`
- [ ] Cross-review B850's PR #1496 + #1501

### 4090-CLAUDE
- [ ] Run PR #1501's TTS test harness — attach evidence
- [ ] Run PR #1501's Ollama validator — attach evidence
- [ ] Append CLAIM entry to AGNOTE4482PHI.t1.md per the PR #1501 test plan
- [ ] Pick up W0 Substrate PR-1/2/4/5/6 OR hand off explicitly
- [ ] Cross-review W6-P5 FlOO\$ Phase A (already merged) and prep for Phase B

### SPARK + DARKXSIDE
- [ ] Continue SPARK process_audio_with_cloud_api implementation (Ollama/MiniMax/Alibaba); open PR when ready
- [ ] A2UI Remotion hologram viewport scaling — open PR when ready
- [ ] DARKXSIDE: ACK as Control body on B850 PRs #1496 + #1501 (Three-Body governance)
- [ ] DARKXSIDE: token/label approval on #1463 + #1465 lanes
- [ ] DARKXSIDE: anchor naming approval on #1465 network-tier doctrine PR-A

---

## Convergence acceptance criteria

The convergence wave closes when:

1. ✅ Wave 0 + 0.5 governance scaffold merged (DONE — #1490)
2. ✅ Pair recipes + node-affinity teams documented (DONE — #1498)
3. ✅ CGP signing canonical across tokenism / neo4j / agent-zero (DONE — #1497)
4. ⏳ B850-CLAUDE doc-audit PR #1496 merged
5. ⏳ B850-CLAUDE 4090-prep PR #1501 merged with 4090-CLAUDE evidence attached
6. ⏳ #1499 mesh-bind B+C merged
7. ⏳ W6-P5 FlOO\$ Phase A reviewer ACKs (4090 + SPARK)
8. ⏳ AGNOTE4482PHI.t1.md register has at least one CLAIM/RELEASE pair per active node in this 7-day window (B850 ✅, 5090 ✅, 4090 ❌, SPARK ✅) — **4090-CLAUDE needs to file**

When all 8 land, this checklist gets a final RELEASE entry in the register and the convergence point closes.

---

## Notes on identity hygiene

The earlier session mis-attributed 3 entries as `Z890-CLAUDE` — these were created by Claude running on B850 "Knuckles" (PCI device 7551 = R9700 = the R9700 Workstation row in topology). Z890 is a **separate node** (Multi-Boot Win/Linux box with RTX 3090 Ti). User correction: "we are on b850 node Knuckes".

Going forward:
- Use **`B850-CLAUDE (Knuckles)`** for register CLAIMs from this dev shell
- Use **`Z890-CLAUDE`** only when work is actually authored on the Z890 box
- The 3 prior entries are now revised in this commit
- PR #1498's PATTERNS § "Node-affinity team aggregations" names "Z890" as Substrate co-member — that team membership pre-dates the B850 distinction; clarify in a follow-up `docs(patterns)` commit when 4090-CLAUDE picks up PR #1501

---

## Cross-references

- AGNOTE4482 gateway: `pmoves/docs/AGENTS/AGNOTE4482.md`
- Cold-start sitrep: `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md`
- Sign-off checklist (governance gate): `pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md`
- Roadmap waves: `pmoves/docs/AGENTS/AGNOTE4482_ROADMAP_W1-W5.md`
- W0 Substrate brief: `pmoves/docs/AGENTS/AGNOTE4482PHI.W0-SUBSTRATE.md`
- P7 PLAYGROUND: `pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md`
- Node profiles (B850-CLAUDE TODO): `pmoves/docs/NODE_PROFILES/4090-CLAUDE.md` (in PR #1501)
- Patterns / Known Roads / pair recipes / node teams: `.claude/PATTERNS.md` (post-#1498)
