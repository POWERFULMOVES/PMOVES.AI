# AGNOTE4482 — Agent Zero `v1.3` Gap Report

GRAPHITI_MARK: `AGNOTE4482::AGENT_ZERO::V1_3_GAP`

> **Purpose**: validate the real upstream Agent Zero release state, compare it against the PMOVES hardened suit, and recommend the sync posture before more room/stage or P7 suit expansion.
> **Validated on**: 2026-03-28
> **Scope**: upstream `agent0ai/agent-zero`, PMOVES fork `POWERFULMOVES/PMOVES-Agent-Zero`, and the current local gitlink pin used on the z890 lane.
> **Sync completed**: 2026-04-25 — Fork synced to upstream v1.9 via Fresh Overlay strategy. Branch `PMOVES.AI-Edition-v1.9` pushed to `POWERFULMOVES/PMOVES-Agent-Zero`. Gap closed from 604 to 0 commits. Old branch `PMOVES.AI-Edition-Hardened` retained as fallback. MiniMax litellm format corrected (openai-compatible → openai).

---

## Validated State

- **Upstream source of truth**: `agent0ai/agent-zero` published `v1.2` on **March 26, 2026** and `v1.3` on **March 27, 2026**.
- **PMOVES fork reality**: `POWERFULMOVES/PMOVES-Agent-Zero` is still centered on `PMOVES.AI-Edition-Hardened`, last pushed on **March 7, 2026**, and does not currently publish matching GitHub releases/tags.
- **Current PMOVES pin**: the local PMOVES submodule checkout is commit `2e000aa304e52ed47ca4d5eb4a9ce64a35c916a2`, dated **March 7, 2026**.
- **Important consequence**: when the team says "Agent Zero is at 1.3," that is true for upstream, but not yet true for the PMOVES hardened fork or gitlink pin.

---

## Commit Math

- `PMOVES.AI-Edition-Hardened...v1.3` currently resolves to **24 PMOVES-only commits** and **502 upstream-only commits**.
- The current local gitlink pin and the hardened branch head resolve to the same commit (`2e000aa`), so the **runtime pin is carrying the same 24 / 502 gap**.
- This is not a "small overlay drift" situation. It is a real branch split that needs deliberate preservation and re-application work.

---

## What Upstream `v1.3` Added Since The PMOVES Pin

Representative upstream-only changes visible in the gap:

| Area | Representative upstream change |
|------|--------------------------------|
| Web UI / UX | `feat(webui): add page-head extension point to index.html`, chat focus polish, active-chat fixes |
| Plugin lifecycle | chat compaction plugin, plugin installer/model-config state handling, restart/self-update state fixes |
| Release operations | dynamic release-note generation in Docker publish workflow plus fallback/error handling |
| Scheduler / runtime fixes | `fix scheduler api calls`, plugin index refresh cleanup, PR/release hygiene fixes |

**Interpretation:** upstream `v1.3` is not just a version bump. It includes meaningful movement in extensibility, self-update behavior, UX polish, and release automation.

---

## PMOVES Overlays That Must Survive A Sync

Representative PMOVES-only commits show the hardened suit is carrying platform-specific value that should not be discarded:

| PMOVES overlay | Why it matters |
|----------------|----------------|
| Security hardening | path containment re-enabled, root supervisord programs dropped, non-root container posture, NATS auth/export/credential defaults |
| Operator context | `CLAUDE.md`, Codex operator home, PMOVES integration docs, branching guidance |
| Runtime overlays | `docker-compose.pmoves.yml`, `env.shared`, `envared`, `chit/secrets_manifest_v2.yaml`, credential bootstrap scripts |
| PMOVES feature wiring | persona-based agent creation with Supabase, TensorZero provider config, Prometheus metrics |
| Governance / audit | CODEOWNERS, Dependabot config, PMOVES audit CI gates |

**Interpretation:** the PMOVES branch should be treated as a hardened overlay pack, not as an accidental stale fork.

---

## Release Notes And CVE Funnel

PMOVES already has enough architecture to keep this from becoming a blind drift problem, but the cadence needs to be explicit.

### Weekly intake

- Check upstream Agent Zero tags/releases and record any new version in the hardening lane.
- Review CodeQL and Dependabot status in the root PMOVES audit surfaces.
- Capture only actionable deltas, not full release prose dumps.

### Sprint intake

- Compare the current PMOVES pin against the latest upstream release.
- Classify changes into:
  - **adopt**
  - **preserve PMOVES overlay**
  - **drop / ignore**
- Record the decision in AGNOTE/P7 docs when the result affects the room/stage prospectus or suit vocabulary.

### Canonical sinks

- `docs/hardening/PMOVES-hardening-tracker.md`
- `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md`
- `pmoves/docs/NEXT_STEPS.md`
- `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md`

**Recommended rhythm:** weekly security/release intake, sprint-level sync decisions, release-gate verification before any new gitlink bump.

---

## Sync Options

### 1. Acknowledge upstream `v1.3`, do nothing else

- Lowest effort
- Keeps PMOVES stable
- Leaves the suit story, docs, and runtime pin out of sync

### 2. Controlled `v1.3` suit-sync lane

- Create a dedicated Agent Zero sync branch/worktree
- Reconcile upstream `v1.3` into the fork
- Re-apply PMOVES overlays intentionally
- Re-validate personas, Supabase wiring, MCP defaults, monitoring, and hardening

**Recommendation:** this is the correct path.

### 3. Treat upstream `v1.3` as a drop-in fast-forward

- Not recommended
- The branch split is too large and PMOVES-only hardening is too meaningful

---

## Recommended Next Move

1. Treat upstream `v1.3` as the new external wardrobe baseline.
2. Open a dedicated sync lane for `PMOVES-Agent-Zero`, not a mixed PMOVES.AI root PR.
3. Preserve and explicitly re-apply the PMOVES overlays listed above.
4. After the submodule suit is stable, refresh the PMOVES gitlink and only then continue P7/room/stage suit expansion.
5. Keep the release-notes/CVE funnel active so `v1.4+` does not recreate the same ambiguity.

---

## Prospectus Implication

For AGNOTE4482 and P7, the clean consensus frame is:

- **rooms** are the audience-facing topology
- **stage** is the live state model
- **suits** are the runtime/operator/persona overlays

Upstream Agent Zero `v1.3` should be treated as the base suit cut. PMOVES then decides which hardening, persona, MCP, and operator layers remain custom on top.
