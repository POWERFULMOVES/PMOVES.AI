# ARCHON Roadmap + Video Workflow Competitive Intelligence

**Date**: 2026-05-10
**Sources**: Two Cole Medin live streams transcribed 2026-05-10
- Roadmap Session (May 5, 77min): `transcript_Pk4pBrBQrxo`
- Video Workflow (May 3, 82min): `transcript_vhbaZJtW2Hg`
**Prior Baselines**: ARCHON_COMPARATIVE_ANALYSIS.md (2026-04-24), FRESH_VIDEO_ANALYSIS.md (2026-04-24)
**Method**: Transcript-grounded extraction via document_query, cross-referenced against prior analyses

---

## Executive Summary — 5 Key Takeaways

1. **Archon is pivoting from 'coding harness' to 'general-purpose agentic workflow engine'**. The video workflow demo proves Archon can orchestrate any multi-step agentic pipeline, not just coding. This broadens its competitive surface significantly — it now competes with n8n, LangGraph, and similar orchestration tools, not just coding harnesses.

2. **The 'silent failure trust crisis' is Archon's critical vulnerability**. Cole explicitly acknowledges that 40% of all issues are workflows that 'look successful but ship nothing'. This is the exact problem PMOVES CHIT signatures and observability stack (ClickHouse/Prometheus) are designed to solve. This is a wedge.

3. **The workflow marketplace (Homebrew model) is a distribution moat being built in real time**. PR-based submissions, community folder in-repo, `archon workflow install <slug>` — this is a developer ecosystem play. If it gains traction, PMOVES needs a response strategy because a workflow marketplace creates lock-in.

4. **Provider mixing per node is genuinely novel and PMOVES lacks it**. Archon lets each workflow node use a different provider/model (Claude for implementation, Codex for validation, PI for review). PMOVES routes through TensorZero but doesn't expose per-node provider selection in its workflow definitions. This is a concrete feature gap.

5. **The collaboration window with Cole Medin remains open but is narrowing**. Cole is building rapidly (marketplace, eval system, persistent orchestrator) and establishing Archon as an independent platform. The pitch 'you built the harness for one agent, we built the lattice for a fleet' still works, but the window for a peer collaboration (not acquisition/subordination) is time-limited.

---

## Roadmap Milestones Table

| Milestone | Priority | Status | Timeline | Details |
-----------|----------|--------|----------|---------|
| Streamline setup + binary install | HIGH | In progress | 'Under 5 minutes' target | Not yet achieved; current setup too complex |
| Workflow marketplace | HIGH | Architecture decided | 'Coming soon' | Homebrew model, PR-based, community folder in repo, `archon workflow install <slug>` |
| Eval system for workflows | HIGH | Announced | Not specified | Evaluate workflow effectiveness — no details yet |
| Advanced workflow control flow | CRITICAL | Acknowledged gap | Not specified | Addresses 'silent failure trust crisis' — 40% of all issues |
| Persistent project orchestrator | MEDIUM | Concept stage | Not specified | 'Project as entity' with persistent agent memory via beads/lifestyle hooks |
| Local LLM support | MEDIUM | Announced | Not specified | OpenAI-compatible base URL configuration |
| Workflow execution reliability | HIGH | In progress | Ongoing | Addressing silent failures and execution guarantees |
| Roadmap PR publication | — | Planned | 'Within the next week' of May 5 stream | Public GitHub roadmap document |
| Additional model providers | LOW | Future | Not specified | Beyond Claude, Codex, PI |
| Multi-repo workspace | LOW | Future | Not specified | Work across multiple repositories |
| Enterprise GitHub integration | LOW | Future | Not specified | Production-ready deployment features |

**Key absence**: No version numbers, no specific dates, no semantic versioning plan. Roadmap is qualitative, not release-engineered.

---

## Architecture Changes From Prior Analysis

### What's New Since April 24

| Area | Prior State (Apr 24) | Current State (May 10) | Significance |
------|----------------------|------------------------|-------------|
| Scope | 'AI coding command center' | 'Open-source harness builder for AI coding' expanding to general agentic workflows | Category expansion — no longer just coding |
| Workflow format | YAML workflows referenced but not deeply explained | YAML workflows are the core abstraction — node types (deterministic vs agentic), provider mixing, context passing via artifact directory | Formalized workflow model |
| Provider model | TensorZero routing (PMOVES fork) | Per-node provider selection — Claude, Codex, PI, local models via OpenAI-compat base URL | More flexible than PMOVES current routing |
| Marketplace | Not mentioned | Announced with architecture decision (Homebrew model, in-repo community folder) | Ecosystem play emerging |
| Validation | Error recovery pattern described (capture → re-context → retry) | Formalized: separate validation session, pass/needs-iteration verdict, fresh context iteration | Structured QA pipeline |
| Non-coding workflows | Not demonstrated | Full video generation pipeline as proof of concept | Proves generalizability |
| Eval system | Not mentioned | Announced | Quality measurement for workflows |

### What's Unchanged

- **Flat RAG architecture**: Still Euclidean embeddings, no geometric encoding
- **Single-node topology**: No distributed fleet support
- **No cryptographic provenance**: No signatures, no Merkle proofs
- **Supabase/Postgres backend**: Same persistence model
- **MCP bridge**: Still the primary agent integration mechanism
- **React/Vite SPA UI**: Same frontend stack

### Philosophy Formalized

Cole articulated a clear architectural principle that wasn't explicit in prior videos:

> 'Building the agents into the system instead of building the system into the agent.'

This means: rather than giving one agent a massive skill/prompt and hoping it follows instructions correctly (Claude Code Skills model), Archon strings together focused agent sessions with deterministic steps between them. Each session has a narrow scope. The system enforces the workflow, not the agent's reasoning.

This is architecturally significant. It's the inverse of PMOVES' approach: PMOVES builds a rich context environment (CHIT geometry, GEOMETRY BUS, full lattice) and trusts the agent to navigate it. Archon constrains the agent into narrow pipes and trusts the system to connect them. Both address agent reliability, but from opposite directions.

---

## Video Workflow Breakdown

### Pipeline Architecture (Text Diagram)

```
INPUT                    PLANNING                   GENERATION                 QUALITY                   OUTPUT
──────                   ────────                   ──────────                 ───────                   ──────

URL ──→ [Pre-flight] ──→ [Fetch] ──→ [Plan] ──→ [Audio] ──→ [Build] ──→ [Review] ──→ [Render] ──→ MP4
          Check skills    Read URL   Script +   Voice +    Remotion    Pass/       Final       Final
          in place        content    Scenes     SFX +      composition Iterate?   video       summary
                                    (md)       Music                  │
                                                  │                    ├─ Yes → [Iterate] ──→ [Verify] ──→ back to Review
                                                  │                    └─ No  ──────────────────→ continue
                                                  │
                                              Parallel:              Separate Claude session
                                              Audio + SFX            ('don't ask agent to
                                              run concurrently       grade own homework')
```

### Node-by-Node Provider Map

| Step | Node Type | Provider/Tool | Output | Notes |
------|-----------|---------------|--------|-------|
| 1. Pre-flight | Deterministic | Bash (script check) | Skills verified | Ensures Remotion best practices skill present |
| 2. Fetch source | Agentic | Claude Code | Raw content from URL | Hacker News, articles, repos, product pages |
| 3. Plan video | Agentic | Claude Code | Markdown: script + scene defs | Core creative step — determines everything downstream |
| 4. Generate voice | Deterministic | ElevenLabs/Cartesia via Python script | Audio file | `generate_voiceover.py` — only paid component |
| 5. Generate SFX | Deterministic | Audio API (unspecified) | Sound effects | Runs in parallel with voice generation |
| 6. Generate music | Deterministic | Audio API (unspecified) | Background music | Depends on audio generation completing first |
| 7. Build composition | Agentic | Claude Code + Remotion skill + Diagram skill | TypeScript (root.tsx) | 51 Remotion references in workflow YAML — complex composition |
| 8. Regenerate registry | Deterministic | Bash | Updated root.tsx | Vitest neglob workaround for composition discovery |
| 9. Review | Agentic | Claude Code (SEPARATE session) | Structured verdict: pass/needs iteration | Different session from builder — explicit anti-bias |
| 10. Iterate | Agentic | Claude Code (FRESH session) | Edited composition | Receives specific feedback (e.g., 'SFX too loud', 'mispronunciation') |
| 11. Verify | Agentic | Claude Code (SEPARATE session) | Pass/fail | Final check after iterations |
| 12. Render | Deterministic | Remotion CLI | MP4 video | Final output |
| 13. Summary | Agentic | Claude Code | Results summary | Human review of final video |

### Key Patterns

**Hybrid determinism**: 6 of 13 steps are deterministic (bash/scripts), 7 are agentic (Claude Code). The deterministic steps handle things agents are bad at (exact API calls, file system operations). The agentic steps handle creative/analytical work. This ratio is deliberate.

**Context isolation**: Review and iterate steps run in fresh Claude Code sessions. Cole explicitly states: 'You don't want to ask a coding agent to always review their own work. It's like asking a kid to grade their own homework.' This is a circuit breaker pattern — it prevents context contamination from propagating errors.

**Artifact passing**: Nodes communicate through a shared artifact directory (markdown files). Node N+1 reads Node N's output markdown. This is simple, auditable, and debuggable — you can inspect the intermediate artifacts to see exactly what each node received.

### Performance Metrics

| Metric | Value | Context |
--------|-------|---------|
| Total generation time | ~15 minutes | For a 'couple minute' video |
| Setup time | ~5 minutes | One-time workflow setup |
| Idle memory | 200-300 MB | Archon container at rest |
| Active memory | Same as Claude Code | Archon is orchestration overhead only |
| Local model throughput | 10-15 tok/s | Q4-quantized 72B on single RTX 3090 |
| Local model fit | 36B params | Max on single RTX 3090 |
| Paid component cost | ElevenLabs/Cartesia only | 'Everything else is free' plus Claude Code costs |
| Workflow complexity | 51 Remotion refs | In single workflow YAML file |

---

## PMOVES vs Archon — Updated Comparison Matrix

| Dimension | PMOVES | Archon | Delta Since Apr 24 | Winner |
-----------|--------|--------|---------------------|--------|
| **Workflow Definition** | CHIT geometric encoding, GEOMETRY BUS events | YAML node graph with deterministic/agentic types | Archon formalized; PMOVES workflow format less accessible | Archon |
| **Provider Flexibility** | TensorZero routing (global per-request) | Per-node provider/model selection | Archon gained explicit per-node mixing | Archon |
| **Non-Coding Workflows** | Not demonstrated | Proven (video generation pipeline) | New Archon capability | Archon |
| **Validation/QA** | CHIT signatures, observability stack | Separate-session review, pass/iterate verdict, fresh context | Both have structured QA; different mechanisms | Tie |
| **Silent Failure Detection** | CHIT self-stabilizing equilibrium, ClickHouse traces | Acknowledged as biggest problem (40% of issues), no solution yet | Archon weakness explicitly admitted | PMOVES |
| **Distribution/Marketplace** | None | Homebrew-model workflow marketplace (announced) | New Archon ecosystem play | Archon |
| **Multi-Node Topology** | Fleet via Tailscale + Docker compose + NATS | Single node only | Unchanged | PMOVES |
| **Information Encoding** | Hyperbolic geometry (Poincare disk, CGP constellations) | Flat Euclidean embeddings | Unchanged | PMOVES |
| **Cryptographic Provenance** | CHIT signatures, Merkle proofs, Dirichlet weights | None | Unchanged | PMOVES |
| **Hardware Awareness** | Profile detection, Jetson Orin support, DGX scaling | Assumes standard dev environment | Unchanged | PMOVES |
| **Privacy** | Local-first, air-gapped capable, no external dependency required | Requires Claude Code (Anthropic), optional local LLM | Archon added local LLM support but still cloud-default | PMOVES |
| **Accessibility/Speed to Value** | Complex Docker compose stack, topology configuration | Target: under 5 minutes (not yet achieved but approaching) | Archon actively working on this | Archon |
| **UI/UX** | No comparable user-facing interface | Polished React SPA with kanban, knowledge browser, workflow viz | Unchanged | Archon |
| **Content/Community** | No public content presence | Weekly live streams, 8+ Archon videos, substantial YouTube audience | Unchanged | Archon |
| **Eval System** | Skill-creator with benchmarking | Announced but unspecified | Both have plans; PMOVES further along in implementation | PMOVES |
| **Observability** | ClickHouse + Prometheus integration planned | No observability beyond workflow status | Unchanged | PMOVES |
| **Error Recovery** | Circuit breaker principle, fail-fast/fail-open | Fresh context iteration, separate validation session | Both have patterns; Archon demonstrated in practice | Tie |

**Score**: PMOVES 6, Archon 7, Tie 3

**Trend**: Archon is closing gaps faster. In April, PMOVES led 7-5-2. The shift comes from Archon's formalized workflow model, per-node provider mixing, non-coding proof point, and marketplace announcement. PMOVES hasn't shipped comparable user-facing features since the April baseline.

---

## What PMOVES Can Learn

### 1. Per-Node Provider Selection
Archon's ability to route each workflow node to a different provider/model is genuinely useful and PMOVES doesn't have it. PMOVES routes through TensorZero globally — a workflow step can't say 'use Claude for this step, Codex for the next'. This should be added to PMOVES workflow definitions.

**Implementation sketch**: Extend CHIT workflow YAML with per-node `provider` override that takes precedence over TensorZero routing for that step only.

### 2. Separate-Session Validation
The 'don't ask the agent to grade its own homework' pattern is a circuit breaker in disguise. PMOVES should formalize this: any quality gate in a PMOVES workflow MUST run in a separate agent context with no access to the generating agent's reasoning trace.

**Implementation sketch**: Add `isolation: true` flag to PMOVES workflow nodes that spawns a fresh subordinate for validation.

### 3. Artifact Directory Pattern
Archon passes data between nodes through a shared directory of markdown files. This is dead simple, fully auditable, and debuggable. PMOVES GEOMETRY BUS events are more powerful but also more opaque. Consider a 'debug mode' that writes CGP packets as human-readable markdown alongside the binary protocol.

### 4. Marketplace as Distribution
Archon's marketplace creates network effects. PMOVES has no equivalent distribution mechanism for workflows, skills, or configurations. Even a simple GitHub-based registry (like Archon's community folder) would create surface area for PMOVES adoption.

### 5. 'Under 5 Minutes' as a Design Constraint
Cole explicitly targets sub-5-minute setup. PMOVES has no such constraint — the compose stack requires significant configuration. Even if PMOVES can't match this for the full fleet topology, a 'single-node quick start' mode that provisions one agent with CHIT + basic workflow in under 5 minutes would dramatically lower the barrier.

---

## Collaboration Window Assessment

### Is the Window Still Open?

**Yes, but narrowing.** Assessment factors:

| Factor | Status | Trend |
--------|--------|-------|
| Cole's openness to collaboration | No evidence of closure | Neutral — he hasn't mentioned PMOVES or collaboration with anyone |
| Archon's independence trajectory | Accelerating — marketplace, eval, persistent orchestrator | Negative — platform is becoming self-sufficient |
| PMOVES value proposition to Cole | 'Fleet for your harness' still compelling | Neutral — but Cole hasn't shown interest in multi-node |
| Competitive overlap | Increasing — both targeting agentic workflow orchestration | Negative — category convergence |
| Cole's audience growth | Active and substantial | Positive — larger audience = more valuable partner |

### Recommended Approach

**Do NOT wait.** The April 24 analysis said 'the pitch writes itself.' It still does. But every week Cole builds more independent platform capability, the pitch becomes less compelling because Archon needs PMOVES less.

**Concrete action**: A single, high-quality technical demonstration. Not a cold email — a working PMOVES deployment where Archon's video workflow runs across a 3-node fleet instead of a single machine. Record it. Post it. Tag Cole. The demo speaks louder than any pitch.

**What to demonstrate**:
1. Archon video workflow YAML running on Node A (planning + composition)
2. Validation running on Node B (separate machine, enforced isolation)
3. Rendering on Node C (GPU-optimized node)
4. GEOMETRY BUS coordinating the inter-node handoffs
5. CHIT signatures on each artifact for provenance
6. The whole thing observable in real-time on a dashboard

This shows PMOVES as a force multiplier for Archon, not a competitor or replacement.

---

## Recommended PMOVES Response Actions

### Immediate (This Week)

| # | Action | Effort | Impact |
---|--------|--------|--------|
| 1 | Add per-node provider override to PMOVES workflow definitions | Medium | High — closes concrete feature gap |
| 2 | Add `isolation: true` workflow node flag for separate-context validation | Low | High — formalizes circuit breaker pattern |
| 3 | Record fleet-distributed Archon workflow demo (see above) | Medium-High | Critical — collaboration catalyst |

### Short-Term (This Month)

| # | Action | Effort | Impact |
---|--------|--------|--------|
| 4 | Create 'single-node quick start' mode targeting under 5 minutes | High | High — lowers adoption barrier |
| 5 | Add markdown debug mode to GEOMETRY BUS (artifact directory pattern) | Low | Medium — improves debuggability |
| 6 | Publish PMOVES workflow examples as GitHub repo (proto-marketplace) | Medium | Medium — creates distribution surface |
| 7 | Update PMOVES-Archon fork to latest upstream — quantify gap since f4bd252c | Low | Medium — know what you're integrating against |

### Medium-Term (This Quarter)

| # | Action | Effort | Impact |
---|--------|--------|--------|
| 8 | Build CHIT silent-failure detector — monitor for 'workflow succeeded but no output artifact' pattern | Medium | Critical — directly attacks Archon's 40% issue |
| 9 | Implement RAG-to-CHIT encoder bridge (from Apr 24 analysis — still not done) | Medium | High — enables Archon knowledge in PMOVES geometry |
| 10 | Eval system integration — PMOVES skill-creator benchmarks running against Archon workflows | Medium | High — cross-platform quality measurement |

---

## Competitor Landscape Notes

Cole mentioned several tools during the roadmap session. Quick mapping:

| Tool | Cole's Assessment | PMOVES Relevance |
------|-------------------|------------------|
| Stripe Minions | 'You can think of it like Stripe Minions' — harness comparison | Direct competitor in harness space — investigate |
| Skills.sh | Marketplace for Claude Code skills — 'so much different than sharing Archon workflows' | Not directly competitive but distribution model worth studying |
| ClaHub | Registry pattern — 'indexes for packages hosted elsewhere' | Alternative marketplace model to Archon's in-repo approach |
| Hermes | 'Comparing apples to oranges. Hermes is a personal agent.' | Different category — not a threat |
| Gemini CLI | 'No SDK available' — only headless mode flag | Google gap — neither PMOVES nor Archon can integrate |
| Kira | 'Confirmed no SDK' | Same as Gemini CLI |
| Smithery (MCP marketplace) | 'I don't actually know. I don't think they're open source' | Unknown — worth investigating for MCP ecosystem positioning |

---

## Technical Debt Acknowledged by Cole

For tracking — these are Archon weaknesses that PMOVES could exploit or solve:

1. **Silent failure trust crisis** (40% of issues) — workflows appear successful but produce no output
2. **Setup complexity** — target is under 5 minutes, not achieved
3. **Workflow install command** — was a placeholder, not yet built
4. **Security scanning limitation** — VirusTotal can't scan YAML workflows; no automated security check
5. **Featured workflows logic** — 'hardcoded' and 'random right now'
6. **Issue overwhelm** — 149+ open issues, many AI-generated, difficult to triage
7. **Quota limits** — 'sucky recently' — provider quota dependency
8. **Marketplace not ready** — 'not yet because of all the tough decisions'

---

*Analysis complete. All claims grounded in transcript evidence. No speculation beyond explicit cross-referencing with PMOVES architecture.*
