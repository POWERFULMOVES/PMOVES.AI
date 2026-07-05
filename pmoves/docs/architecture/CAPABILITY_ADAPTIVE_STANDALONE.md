# Capability-Adaptive Standalone Agent Zero

**Status:** Design spec (2026-06-21) — approved tier model, build deferred to next session.
**Owner lane:** Z890-CLAUDE. **Tracks:** Task #2.
**Related:** PR #1838 (standalone decouple), PR #1855 (plugin bake-in), PR #1856 (A0 MCP toolkit), `project_bringup_dependency_order_gap`, `PMOVES_MOF_ARCHITECTURE.md`.

## 1. Problem

"Standalone" Agent Zero is currently **data-less and minimal**: `make up-agents-standalone` (PR #1838) brings up only `nats + agent-zero + mesh-agent`. But Agent Zero is the **primary orchestrator** — it always needs data (Supabase/forms), memory (Cipher/CHIT), and retrieval (Hi-RAG). Treating standalone as "just the agent" is wrong.

Per the MOF model (capacity-class, not expertise-lane), **standalone should be capability-adaptive**: a node runs as much of the supporting tier as it *can*. A weak VPS runs a lean agent; a capable workstation (Z890) expands its standalone to include the data tier + Consciousness/CHIT + persona/forms, because the node is capable. The orchestrator's reach scales with the pore's capacity.

## 2. Current state (grounded)

- **Probe exists:** `deploy/provision/glances-autodetect.{sh,ps1}` classifies a node into a `SUGGESTED_NODE_TYPE` (+ rationale) from `lscpu`/`lspci`/`lsblk`/`/proc/meminfo` (+ Glances). Emits structured JSON/YAML: `cpu{model,cores_logical}`, `gpus[]{vendor,model,vram_gb,pci_id}`, `memory`, NICs. Known classes: `kvm4-1|kvm4-2|kvm2` (4–8 vCPU, 8–16 GB), `pve-member`, `pve-member-fresh` (≥10 GbE + ≥2 NVMe + ≥64 GB), `gpu-5090` (RTX 5090 + ≥64 GB), `rdna4-workstation` (2× AMD RDNA4 + Ryzen), `dgx-spark`.
- **Lean target exists:** `up-agents-standalone` → `TOPOLOGY_MODE=standalone DOCKED_MODE=false … up -d nats agent-zero mesh-agent`.
- **`up-agents-auto` ALREADY EXISTS** (`pmoves/Makefile:2102`): "auto-detect docked agents if Supabase REST reachable, else standalone (service-discovery driven)". Phase 2 **extends/migrates this existing target** to add capability-tier selection — it does NOT create a new one (avoid duplicating or silently overwriting the current docked-vs-standalone semantics; the tier logic layers on top: tier picks the service *set*, the existing reachability probe still informs docked-vs-standalone within a tier).
- **Discovery:** `tools/service_health_check.py` resolves services env → registry (docked) → Docker-DNS (standalone).
- **MCP toolkit (PR #1856):** A0 is wired as an MCP *client* to `docker`, `pmoves-supabase`, `cipher-api`. On a capable node those targets are now **locally present**, so the toolkit "lights up" exactly when the tier provides them.
- **Service/profile names:** `supabase-db` + `supabase-kong` (+ stack, profile `supabase-local`), `neo4j`, `hi-rag-gateway-v2` (CPU) / `hi-rag-gateway-v2-gpu` (GPU), `consciousness-service` (CHR/CGP, :8105 host), `cipher-api` (Cipher Memory MCP, container :3000), `archon` (persona/forms/prompts).

## 3. Design

### 3.1 Three tiers (approved)

| Tier | Node classes | Standalone service set (beyond the agent core) |
|------|--------------|------------------------------------------------|
| **lean** | `kvm4-1`, `kvm4-2`, `kvm2` (small VPS) | `nats`, `agent-zero`, `mesh-agent` (today's standalone) |
| **capable** | `pve-member`, `pve-member-fresh`, CPU-strong workstations | lean **+** `supabase-local` stack, `neo4j`, `hi-rag-gateway-v2` (CPU), `consciousness-service`, `cipher-api`, `archon` (persona/forms + CHIT) |
| **gpu** | `gpu-5090`, `rdna4-workstation`, `dgx-spark` | capable **+** `hi-rag-gateway-v2-gpu`, `media-video`, `media-audio` (GPU services) |

Agent Zero is the orchestrator in **all** tiers; the tier only sets how far the supporting mesh expands. Z890 classifies as **gpu** (or **capable** if its GPU is reserved elsewhere).

### 3.2 Capability classifier — `tools/node_capability_tier.py`

**Contract:**
- **Input:** the `glances-autodetect` JSON (preferred) — or the bare `SUGGESTED_NODE_TYPE` string, or live re-probe if neither supplied.
- **Output:** `{"tier": "lean|capable|gpu", "rationale": "...", "source": "node-type|thresholds", "services_extra": [...]}` (stdout JSON; also a `--make` mode that prints just the tier for shell use).
- **Mapping precedence:** (1) explicit override env `PMOVES_NODE_TIER`; (2) known `SUGGESTED_NODE_TYPE` → tier (table above); (3) raw thresholds fallback.
- **Raw thresholds (fallback when node-type unknown):**
  - `gpu`  ← a usable GPU present (`gpus[].vram_gb ≥ 12`) **and** capable CPU/RAM
  - `capable` ← `cores_logical ≥ 8` **and** `ram_gb ≥ 32`
  - `lean` ← otherwise
- **Field names must match the probe's actual output:** `glances-autodetect` (both `.sh` and `.ps1`) emits RAM as **`ram_gb`** (not `memory_gb`), CPU as `cpu.cores_logical`, GPUs as `gpus[].vram_gb`. The classifier reads those exact keys.
- Thresholds live in one constant block for easy tuning; document why (Supabase+Neo4j+Hi-RAG comfortably need ~8 cores / ~32 GB headroom alongside the agent).

### 3.3 Bring-up integration — extend the existing `make up-agents-auto`

`up-agents-auto` already exists (`Makefile:2102`) and currently chooses docked-vs-standalone by Supabase REST reachability. Phase 2 **extends** it (does not replace) so it first resolves a capability tier, then selects the service set — the existing reachability probe continues to drive docked-vs-standalone *within* the chosen tier:

```
probe (glances-autodetect) ──▶ node_capability_tier.py ──▶ tier
   tier=lean    → up-agents-standalone  (existing)
   tier=capable → up-core-capable       (new: data tier → bus → agents, dep-ordered)
   tier=gpu     → up-core-capable + GPU services
   (within each tier, the existing Supabase-reachability check still informs
    docked vs standalone wiring)
```
- **Dependency order is mandatory** (per `project_bringup_dependency_order_gap`): data tier (`supabase-local`, `neo4j`) healthy **before** `consciousness-service`/`archon`, and those before `agent-zero`. Use `depends_on: condition: service_healthy` + staged `up` so the agent never boots against an absent data tier.
- Respect `PMOVES_NODE_TIER` override (operator can force a tier).
- Honor existing `DOCKED_MODE`/`TOPOLOGY_MODE` semantics; `up-agents-auto` is the capability-aware front door, not a replacement for `up-core`/docked flows.

### 3.4 Interaction with the MCP toolkit (#1856)

The data services a capable/gpu node brings up are exactly the MCP targets A0 already points at (`pmoves-supabase` → `supabase-kong`, `cipher` → `cipher-api`, plus Hi-RAG/BoTZ when those lanes land). So capability-adaptive standalone makes the orchestrator's MCP toolkit *functional* on capable nodes and *gracefully degraded* (unreachable servers skipped) on lean nodes — no separate config per tier.

## 4. Phased implementation plan

- **Phase 1 — classifier:** `tools/node_capability_tier.py` + unit tests (table mapping + threshold fallback + override). Pure, no infra. Standalone PR.
- **Phase 2 — bring-up:** **extend** the existing `up-agents-auto` (Makefile:2102) + add `up-core-capable`; wire dep-ordered service sets; `PMOVES_NODE_TIER` override. Preserve the current docked-vs-standalone reachability behavior. PR.
- **Phase 3 — live verify on Z890 (capable/gpu):** bring up the capable set, confirm dependency ordering, agent boots with data tier present, MCP toolkit connects to the now-local services. Capture evidence.

## 5. Open questions / coordination

- **BoTZ-gateway + Hi-RAG MCP** (Task #3): owned by 4090 / CO's `feat/hirag-mcp-bridge`. The gpu/capable tier brings up `hi-rag-gateway-v2[-gpu]`; the *MCP* entry for it is added when CO's endpoint lands. BoTZ persona/forms similarly.
- **Neo4j hardening / resource limits:** capable tier adds real memory pressure (Supabase + Neo4j + Hi-RAG). Define per-tier resource ceilings so a "capable" classification doesn't OOM a borderline node.
- **Consciousness ↔ Cipher distinction:** `consciousness-service` (CHR/CGP) vs `cipher-api` (memory MCP) are separate; both belong to the capable tier but serve different roles.
- **Supabase currency** (Task #4): the capable tier pins the self-hosted Supabase stack — keep the gotrue `/auth/v1` + asymmetric-JWT items in view when this tier is exercised.

## 6. Verification strategy

- Phase 1: unit tests over recorded `glances-autodetect` fixtures (one per node class) → asserted tier.
- Phase 2: `make up-agents-auto` dry-run per forced `PMOVES_NODE_TIER` → assert the selected service set + ordering.
- Phase 3: live on Z890 — `service_health_check.py` green across the capable set; `agent-zero` reaches Running with the data tier present; A0 MCP client connects to `cipher-api`/`supabase` (no `Unknown`/connection errors in logs).
