# DARKXSIDE Fan-Out Brief — Self-Hosted E2B Danger Room Integration

> **GRAPHITI_MARK:** DARKXSIDE-FANOUT::E2B-SELF-HOSTED-INTEGRATION::2026-08-06
> **From:** CRUSH-GLM52 (SPARK)
> **To:** DARKXSIDE (operator) → Agent Zero (orchestrator) → Archon (implementer)
> **Priority:** P1 — E2B is the sandbox layer for PMOVES agent workflows
> **Supersedes:** Previous brief that incorrectly assumed E2B cloud SaaS

## Architecture — Self-Hosted E2B on PMOVES Fleet

E2B is **NOT** a cloud SaaS in PMOVES. The entire E2B stack is self-hosted:

```
PMOVES Fleet (Tailscale + Pinokio Network)
├── KVM Nodes (Nomad cluster + Firecracker microVM hosts)
│   ├── KVM4-1 — API gateway + E2B API server
│   ├── KVM4-2 — Data hub + E2B orchestrator + ClickHouse
│   └── KVM2 — Exit proxy + client-proxy relay
├── E2B Infrastructure (Danger-infra)
│   ├── Nomad — orchestrates Firecracker microVM lifecycle
│   ├── Firecracker — microVM runtime for sandboxes
│   ├── NBD — network block device for sandbox filesystems
│   ├── envd — environment daemon embedded in sandbox templates
│   └── ClickHouse — sandbox telemetry/metrics
├── E2B SDKs
│   ├── Danger-Room (code execution) — JS + Python SDK
│   └── Danger-Room-Desktop (GUI sandbox) — XFCE + x11vnc + noVNC
├── E2B Spells — pre-packaged sandbox workflows
└── pmoves-e2b-mcp-server — MCP bridge for agent tool calls
```

### How E2B Desktop Works (Self-Hosted)
1. Agent calls `sandbox.create` via MCP → E2B API on KVM4-1
2. E2B orchestrator (KVM4-2) schedules a Firecracker microVM
3. MicroVM boots from template (Ubuntu + XFCE + x11vnc)
4. Agent gets VNC stream + screenshot + click/type control
5. Sandbox is ephemeral — snapshots and terminates on close

### Local Dev Stack (from Danger-infra DEV-LOCAL.md)
```
make local-infra  →  clickhouse, grafana, loki, postgres, redis, otel
make download-public-kernels  →  Linux kernels for Firecracker
make download-public-firecrackers  →  Firecracker binary
E2B_API_URL=http://localhost:3000
E2B_ENVD_API_URL=http://localhost:3002
E2B_ORCHESTRATOR=http://localhost:5008
```

### KVM Requirements for Firecracker
- `modprobe nbd nbds_max=64` — network block devices
- `vm.nr_hugepages=2048` — huge pages for microVM memory
- KVM-enabled CPU (all KVMs have this — they're KVMs)
- Nomad agent installed + joined to cluster

## Current State — 5 Submodules, Zero Integration

| Submodule | Code State | PMOVES Integration | What It Does |
|---|---|---|---|
| **PMOVES-Danger-infra** | Go + Terraform + Nomad + HCL | TBD (has CLAUDE.md, DEV.md, DEV-LOCAL.md) | E2B infra: API, orchestrator, client-proxy, template-manager |
| **PMOVES-E2B-Danger-Room** | JS + Python SDKs + CLI | TBD (has CLAUDE.md) | Code execution sandbox SDK |
| **PMOVES-E2B-Danger-Room-Desktop** | Python SDK + template | TBD (all fields blank) | GUI sandbox with XFCE desktop |
| **PMOVES-E2b-Spells** | JS + Python | TBD (has docker-compose.pmoves.yml template) | Pre-packaged sandbox workflows |
| **pmoves-e2b-mcp-server** | JS + Dockerfile | TBD (has Dockerfile) | MCP server bridging agent → E2B SDK |

### Registry Entries (all stubs)
- `e2b_danger_room` — port: null, health: null, compose_profile: null
- `e2b_desktop` — port: null, health: null, compose_profile: null
- `danger_infra` — port: null, health: null, compose_profile: null
- `e2b_spells` — port: null, health: null
- `pmoves_e2b_mcp_server` — port: null

### Secrets — NONE WIRED
- `E2B_API_KEY` — not in any env.tier-* or secrets_manifest.yaml
- `E2B_ACCESS_TOKEN` — not set
- `E2B_API_URL` — not set (should point to self-hosted API on KVM4-1)
- `E2B_DOMAIN` — not set (Tailscale hostname)

## DARKXSIDE Integration Plan

### Phase 1: Infra Provisioning (DARKXSIDE — operator)
1. **Choose KVM node(s) for Firecracker** — KVM4-1 or KVM4-2 (need KVM + hugepages)
2. **Install Nomad agent** on chosen KVM(s) — joins the PMOVES cluster
3. **Download Firecracker + kernels** — `make download-public-kernels && make download-public-firecrackers`
4. **Configure hugepages + NBD** — `sudo sysctl vm.nr_hugepages=2048 && sudo modprobe nbd nbds_max=64`
5. **Build base template** — `make local-build-base-template` (Ubuntu + XFCE for Desktop)
6. **Set self-hosted endpoints** in env.tier-worker:
   - `E2B_API_KEY=e2b_<self-generated>`
   - `E2B_ACCESS_TOKEN=sk_e2b_<self-generated>`
   - `E2B_API_URL=http://pmoves-kvm4-1:3000` (Tailscale hostname, NOT localhost)
   - `E2B_DOMAIN=pmoves-kvm4-1`
7. **Run secrets-funnel** to distribute keys fleet-wide

### Phase 2: Compose + Service Wiring (Archon — implementer)
1. **E2B MCP server** — containerize `pmoves-e2b-mcp-server`:
   - Port 8210
   - Profile: `["sandbox", "agents"]`
   - Networks: `pmoves_app`, `pmoves_api`
   - Env: `E2B_API_KEY`, `E2B_API_URL`, `E2B_DOMAIN` from tier-worker
   - Tier anchor: `*tier-worker-hardened`
   - Tools: `sandbox.create`, `sandbox.list`, `sandbox.execute`, `sandbox.screenshot`, `sandbox.click`, `sandbox.type`, `sandbox.close`

2. **E2B Desktop SDK service** — Python wrapper in `pmoves/services/e2b-desktop/`:
   - Uses `e2b-desktop` Python SDK against self-hosted E2B API
   - FastAPI on 8211
   - Health: `GET /healthz`
   - Metrics: `GET /metrics`

3. **NATS subjects**:
   - `sandbox.desktop.created.v1` — microVM spawned
   - `sandbox.desktop.action.v1` — agent GUI action (click/type/scroll)
   - `sandbox.desktop.screenshot.v1` — screenshot captured
   - `sandbox.desktop.closed.v1` — microVM terminated
   - `sandbox.code.executed.v1` — code execution result
   - `sandbox.spell.cast.v1` — spell workflow completed

4. **Agent registry** — update all 5 E2B entries with ports, health, compose_profile, NATS

5. **CATALOG** — add E2B MCP + Desktop SDK to `.claude/CATALOG.md`

6. **CHIT toggles** — enable `attribution_gated: true` on sandbox events (every spell cast gets CHIT-signed)

### Phase 3: Validate (Agent Zero — orchestrator)
1. `make -C pmoves up-e2b-mcp`
2. Spawn a sandbox via MCP: `sandbox.create(template="desktop")`
3. Take screenshot
4. Execute code: `sandbox.execute(code="print('hello PMOVES')")`
5. Close sandbox
6. Verify NATS events fire on all 5 subjects
7. Verify CHIT attribution on events

### Phase 4: Pinokio Network Integration (DARKXSIDE + Archon)
1. Register E2B sandbox as a Pinokio app (`pinokio/api/e2b-sandbox/`)
2. PBnJ launcher for one-click sandbox spawn
3. Wire into P7 room system — `sandbox.room.danger` manifest
4. Creator pipeline integration — ComfyUI runs inside sandbox for untrusted model testing

## Fleet Node Suitability for Firecracker

| Node | KVM? | RAM | Role | Firecracker Host? |
|---|---|---|---|---|
| KVM4-1 | Yes | VPS | API gateway | **YES** — already virtualized, has KVM |
| KVM4-2 | Yes | VPS | Data hub | **YES** — best candidate (storage + ClickHouse already there) |
| KVM2 | Yes | VPS | Exit proxy | Maybe — minimal compute |
| SPARK | No (container) | 128GB unified | GPU | No — no nested KVM |
| Z890 | Yes (bare metal) | 64GB | Workstation | **YES** — bare metal, KVM, plenty of RAM |
| 5090 | Yes (bare metal) | 64GB | GPU | Possible — but GPU workloads compete |
| B850 | Yes (bare metal) | 64GB | CPU workstation | **YES** — bare metal, AMD, 64GB |

**Recommendation:** KVM4-2 as primary Firecracker host (data hub, already has ClickHouse for telemetry). Z890 as secondary (bare metal, plenty of RAM). B850 as overflow.

## Webtop Fix (this session)

Port 8140 webtop fixed:
- PMOVES.AI repo mounted `:ro` (prevents root-owned `.crush/`)
- Separate writable volume for `.crush/` database
- `CRUSH_DATA_DIR=/config/.local/share/crush`

## Next Actions

1. **DARKXSIDE:** Choose Firecracker host(s) from the table above
2. **DARKXSIDE:** Install Nomad + Firecracker + configure hugepages on chosen host
3. **Agent Zero:** Dispatch Archon with this brief via `/mcp/execute`
4. **Archon:** Implement Phase 2 (MCP server + Desktop SDK service + NATS + registry)
5. **Agent Zero:** Validate Phase 3 (sandbox lifecycle smoke test)

## Three-Body

- **Delivery:** Archon (implementation)
- **Control:** DARKXSIDE (infra provisioning + review gate)
- **Memory:** AGNOTE trail + this brief + CHIT-signed sandbox events

---

*Prepared by CRUSH-GLM52 (SPARK). The E2B Danger Room is PMOVES' safe experimentation layer — every agent spell, every dangerous code test, every untrusted model runs in a Firecracker microVM that snapshots and disappears. Self-hosted on the fleet, orchestrated by Nomad, attributed by CHIT.*
