# Infra Analysis — MCP Hosting on the KVM VPSes & Fleet Distribution

**Date:** 2026-08-27
**Author:** AutoClaw (PMOVES-4090 field claw), at founder direction (DARKXSIDE)
**Status:** ANALYSIS + VALIDATION PLAN — **no deploys performed.** Per founder golden rule: local validation on the 4090 (or the claw instance) precedes any VPS deployment.
**Inputs:** live tailnet probes (2026-08-27), `pmoves/config/mcp_inventory.json`, `MCP_TOOLKIT.md`, `BOTZ_MCP_GATEWAY_DEPLOY_SPEC.md`, `kvm-exit-node-hosting-strategy.md`, `FLEET_CAPACITY_ANALYSIS.md`, `fleet-recreation-placement-plan-2026-07-22.md`, PR research (`.openclaw/tmp/pr-research-2026-08-27.md`), capacity mining (`.openclaw/tmp/capacity-analysis-2026-08-27.md`).

---

## 0. Executive summary

1. **No MCP server runs on any KVM VPS today** (live-verified 2026-08-27: 25+ ports probed on kvm2/kvm4-1/kvm4-2). The VPSes run service workloads: NATS hub (kvm4-2), RustDesk relay (kvm2), API/egress tier (kvm4-1) — plus **undocumented live drift**: llama.cpp :8081 on *both* KVM4s and Prometheus :9090 on kvm4-1, none of which appear in committed compose/docs.
2. **The MCP substrate decision is already made in PRs**: **Docker MCP Gateway** (compose fleet, port **8189**, `--static`, auth via CHIT secrets pipeline) — merged via #2656/#2665/#2681 with a verified 23-tool bring-up sequence. **The BotZ MCP gateway (:8052) draft is superseded for federation** — it is K8s-only and cannot federate existing servers. Any new "deploy the MCP gateway" work should clone **#2665's pipeline**, not the BotZ spec.
3. **Best-fit VPS for the fleet-facing gateway: kvm4-1** (8C/16GB, ~6GB usable headroom, already the API/agent tier, egress-separated). **kvm2 has the most free RAM (~7.5GB)** and is the right host for light public SSE surfaces behind its nginx. **kvm4-2 is over-subscribed (~29GB declared container limits on a 16GB host) — add nothing until fixed.**
4. **KiloCode registration has a fully templated path** (#2739/#2754 merged; identity gate #2787; KiloCode baseline `kilocode_glm` #2114 + `kilo.json` #2101 + bearer fix #2729). Open blockers: **#2755** (gate runnability) and **#2788** (5090 hostname collision). A KiloCode harness key must be added to the gate's validated list (`{claude-code, crush}` today).
5. **This instance (4090 AutoClaw) is already registered** — PR #2739 (`register claude_4090`) is merged. IDENTITY.md / USER.md were customized 2026-08-27 for PMOVES.AI alignment.

---

## 1. Verified current state (live, 2026-08-27)

### 1.1 Fleet tailnet (from `make -C pmoves fleet-status`)
Online: pmoves-4090 (this node), 5090, z890, kvm2, kvm4-1, kvm4-2, kiloclaw, nano-*, elder-melchor, b850, googletv, desktop, missling-link. Offline: spark, several phones/tablets.

### 1.2 KVM VPS live services (TCP/HTTP probes over tailnet)

| Node | Open (probed) | Identity (HTTP fingerprint) | In committed docs? |
|---|---|---|---|
| pmoves-kvm2 | RustDesk 21116/21117 (via fleet-status) | hbbs/hbbr REACHABLE | ✅ |
| pmoves-kvm4-1 | **:8081**, **:9090** | :8081 = **llama.cpp** (llama-server UI), :9090 = **Prometheus** | ❌ **drift** — docs place Prometheus on kvm4-2, llama.cpp on B850 |
| pmoves-kvm4-2 | **:8081** | :8081 = **llama.cpp** | ❌ **drift** |

Nothing answered on any MCP-standard port (19681 AutoClaw bridge, 8105 cipher, 8090/8189 docker MCP gateway, 8081 A0-SSE-as-documented, 8051 archon, 8052 BotZ, 8086 hirag, 8000 Kong, 8102 bots, plus a 14-port common-service sweep).

**Action item (drift):** reconcile via the canonical read path — Hostinger MCP (`vps-get-virtual-machines-v1` + metrics), `make -C pmoves port-audit` equivalents, and a VPS inventory refresh PR. The KVM4-1 Hermes profile *expects* local cipher (`:8105`) and docker MCP gateway (`:8090`) that are not actually running.

### 1.3 MCP surfaces are per-node loopback by design

- AutoClaw bridge `127.0.0.1:19681` (this node: productivity 31 tools ✅, github 40 tools ✅; connector:cloudflare needs OAuth; filesystem server offline — minor local config fix pending).
- Cipher `:8105` (SSE + bearer), Agent Zero `:8080`/`:8081`, Archon `:3090` (inventory default :8051 is **stale**), Docker MCP Toolkit gateway `:8090` (stdio/SSE, profile `pmoves_5090_web`, ~200 tools; 4090 ✅ 5090 ✅, Z890/SPARK/B850 TODO).
- Fleet URLs in `mcp_inventory.json` point at `${TS_Z890}` — **stale/aspirational for A0** (live A0 is on 5090 + kvm4-1) and unreachable cross-node because services bind `127.0.0.1` (four-tier PORT_BINDING_MODEL: widen only via reviewed `*_BIND` in git-ignored `env.mesh-bind.local`).

---

## 2. What PMOVES.AI can host on the VPSes (tier-fit)

Founder strategy of record (`docs/architecture/kvm-exit-node-hosting-strategy.md`): tier separation (API/agent → kvm4-1, data → kvm4-2, proxy/relay → kvm2), **GPU stays on-prem**, **PBNJ + Pinokio never on KVMs**, Tailscale-first, exit-node product never colocated with API on kvm4-1.

| Workload class | Fit | Host |
|---|---|---|
| **Docker MCP Gateway** (fleet SSE, :8189, `--static`) | ✅ Primary candidate | **kvm4-1** — API-tier co-location, ~6GB headroom; ingress backhauled from kvm2 nginx |
| Light public SSE MCP bridges / per-client endpoints | ✅ | **kvm2** — best headroom (~7.5GB), nginx SSL termination already there; PBNJ dashboard :3001 planned |
| Data-plane MCPs (supabase-db, cipher, observability) | ⚠️ gated | **kvm4-2 only after the 29GB-on-16GB over-subscription is fixed** (32GB tier / split Supabase / migrate data tier). NATS hub = fleet-critical, coordinate any recreation |
| stdio MCPs (docker, hostinger, tailscale, hf, nats-fleet) | ❌ keep node-local | stdio execs locally; wrap in SSE proxy if fleet exposure is needed (natural VPS workload) |
| GPU inference, PBNJ, Pinokio, heavy agents | ❌ | on-prem only (founder rule) |
| DARKXSIDE sidecar pattern | ✅ shape reference | single-container A0 sidecar (`up-darkxside-sidecar`) is the blessed tiny VPS footprint |

**Cost/platform constraints:** 3× Hostinger KVM = $30/mo; no VPC/GPU/in-place resize (resize = recreate; snapshot first); no floating IPs; Tailscale is the private overlay; canonical VPS reads via **Hostinger MCP**, never raw SSH; kvm2 + kvm4-2 have **console-injection PENDING** for the 2026-04-02 SSH key regen.

---

## 3. Optimal distribution plan (MCP across nodes)

**Principle: re-proxy, don't move.** SSE/HTTP MCPs can re-anchor freely; stdio stays local; `env.mesh-bind.local` + `port-audit` is the only sanctioned way to widen a bind; endpoints always flow from `mcp_inventory.json` through `mcp_config_generator.py` (`${TS_*}` indirection, #2769 — never baked IPs).

| # | Service | Current | Target | Why |
|---|---|---|---|---|
| 1 | Docker MCP Gateway :8189 | 4090/5090 local | **kvm4-1** (fleet-facing), 4090 stays control-plane | One fleet SSE front; co-locates with API tier; ingress via kvm2 nginx |
| 2 | Cipher :8105 | loopback (Z890 per inventory; kvm4-2 per hosting strategy — **reconcile**) | keep + expose via gateway adapter, or reviewed `CIPHER_BIND` to tailnet w/ bearer | #2729 fixed bearer-401; `/mcp/sse` path verified |
| 3 | Agent Zero MCP | live on 5090 + kvm4-1 (inventory says Z890 — **stale**) | fix inventory defaults to live anchors | A0 API :8080 / MCP :8081 |
| 4 | Public light MCP/SSE bridges | — | **kvm2** behind nginx | headroom + role |
| 5 | Data-plane MCPs | — | kvm4-2, post-fix | data gravity |
| 6 | Prometheus/llama.cpp on KVM4s (drift) | undocumented | either document or retire | bring live truth into compose/UP_TARGET_INVENTORY |

**Inventory hygiene:** regenerate `.claude/mcp.json` / `kilo.json` / hermes profile `mcp_servers:` blocks from `mcp_inventory.json` after any anchor change (inventory-first rule, PR #2126/#2769).

---

## 4. KiloCode registration path (from PR research)

1. **Merge gates first:** review **#2755** (gate runnability) and **#2788** (5090 hostname collision; 4th recreate) — only #2788 matters if KiloCode binds to the 5090 node.
2. **Follow the merged template** (#2739/#2754): registry key snake_case w/ leading letter; human name stays in `external_contributors` (attribution ≠ operation); `nats:` empty; `port: null`; team `orchestration`; `node_affinity` from node-vocabulary.
3. **Extend the identity gate harness list** (#2787 gate) with the KiloCode harness key — currently only `{claude-code, crush}` validate; a declared-but-unwired identity FAILS the gate.
4. **Extend, don't fork, the KiloCode baseline:** `kilocode_glm` (#2114), `kilo.json` cipher SSE `:8105/mcp/sse` (#2101, bearer fix #2729 applied), `kilo.mk` health targets (`kilocode.agent.status.v1` heartbeat).
5. **KVM-hosted KiloCode** must carry `pmoves.bootstrap/v1` `x-cgp-*` annotations — `kiloclaw` is already a Mavis routing target (#2651).
6. This 4090 AutoClaw instance: already registered (#2739 merged) — no action needed.

**Recommended order:** #2755 + #2788 → KiloCode registration PR → KVM gateway deployment (cloning #2665's verified pipeline).

---

## 5. 4090-first validation plan (gate before any VPS deploy)

**Lane A — Docker MCP Gateway rehearsal (on 4090):**
1. `make -C pmoves secrets-funnel` (env.tier-agent provides gateway token).
2. Clone #2665's verified sequence on the 4090 compose stack: gateway manifest (pmoves profile) → secrets rotate → funnel → `up` → `mcp-gateway-verify` — expect **23 tools** green.
3. Point this instance's mcporter at the local gateway endpoint and round-trip one low-effect tool per adapter.
4. CHIT `sign-trail` at close.

**Lane B — Cipher tailnet rebind rehearsal (on 4090):**
1. Copy `CIPHER_BIND` widening into git-ignored `env.mesh-bind.local` (never a raw compose diff).
2. `make -C pmoves port-audit`; restart via Known Road (`secrets-funnel` + single-service up).
3. From a second tailnet identity (this claw acts as client), verify `http://<4090-ts>:8105/mcp/sse` answers **401 without token / 200 with bearer**.
4. Revert bind after rehearsal or keep per operator decision; record results in the claim lane.

**Lane C — governance wrap:**
- Three-Body: CLAIM (branch + scope + TTL) in `AGNOTE4482PHI.t1.md` before Lane A/B implementation; Control-body read-only review; RELEASE + signed ACK at close.
- Only after A+B pass: mirror to kvm4-1 via `vps-deployer` / `fleet-node-deployer` Known Roads (Hostinger MCP reads; no raw SSH; snapshot before any recreate).

---

## 6. Immediate next actions (decision-sized)

| # | Action | Owner |
|---|---|---|
| 1 | Review/merge #2755, #2788 | operator + Control |
| 2 | VPS inventory refresh via Hostinger MCP; reconcile llama.cpp/Prometheus drift | infra lane (claim) |
| 3 | Fix kvm4-2 over-subscription (32GB tier / split Supabase / migrate) | operator decision |
| 4 | KiloCode registration PR (template §4) + gate harness-key extension | registration lane |
| 5 | Lane A/B rehearsals on 4090 | this claw, after CLAIM |
| 6 | Fix local mcporter `filesystem` entry (hardcode path) + connector:cloudflare OAuth | this claw, trivial |

---

*Unsigned-local CHIT note: sign-trail run at close; unsigned output acceptable in dev per governance.*
