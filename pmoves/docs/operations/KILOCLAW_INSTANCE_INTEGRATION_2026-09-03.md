# KiloClaw Instance Integration — Ops Baseline 2026-09-03

> **Instance:** `kiloclaw` (hosted KiloClaw, tailnet `100.87.181.8`, user-owned `cataclysmstudios@`)
> **Scope:** Configure this instance as the cloud/mirror PMOVES.AI ops claw — composio operations surface, geometry-bus activation tracking, reticulum overlay status, LinkedIn persona source gathering.
> **Method:** Every fact below was verified live from this instance on 2026-09-03. Nothing is inherited from Claude-context on other nodes.

---

## 1. Verified fleet state (from this node)

| Node | Tailnet IP | Status |
|---|---|---|
| `kiloclaw` (this) | 100.87.181.8 | user-owned, linux |
| `pmoves-4090` | 100.105.8.81 | tagged, windows — local field claw seat (PMOVES--4090Z.AIClAW) |
| `pmoves-5090` | 100.73.74.3 | tagged, windows |
| `pmoves-z890` | 100.113.38.37 | tagged, windows |
| `pmoves-kvm4-1` | 100.110.13.48 | tagged, linux, idle — **TensorZero/API-gateway node** |
| `pmoves-kvm4-2` | 100.124.50.76 | tagged, linux, idle — **NATS hub + designated Reticulum hub** |
| `pmoves-kvm2` | 100.74.146.76 | tagged, linux, idle — egress/SSL node |
| `pmoves-spark`, `nano-pmoves`, `pmoves-nano-1`, `pmoves-b850-ai-top`, others | — | online/intermittent |

**Network reachability (verified):**
- `tailscale ping` OK to all KVMs (~20ms) and pmoves-4090 (DERP ~49ms).
- **Direct TCP to `pmoves-kvm4-2:4222` from this node is BLOCKED** (tailscale ACL: user-owned device vs tagged fleet devices).
- **SSH port 22 to KVM tailnet IPs is BLOCKED** from this node.
- `tailscale ssh` (daemon-routed) to `root@pmoves-kvm4-2` **works** — this is the Known Road for KVM access from kiloclaw.
- Repo on kvm4-2: `/opt/PMOVES.AI` (compose project `pmoves`).

## 2. Geometry bus (NATS) — current state

- Hub: `pmoves-nats-1` container on **kvm4-2**, up 6 weeks, healthy, `nats:2.11.8-alpine`, JetStream + monitoring enabled.
- Binds tailnet IP only (`100.124.50.76:4222`); loopback refused. Creds `nats:pmoves` (documented weak default; real password overrides via env).
- **AUTH VERIFIED** from inside the hub network (`docker run --network host` probe): connect + auth OK.
- **BUS IS IDLE: zero publishers/subscribers observed in a 6s wildcard subscribe.** The geometry bus needs activation — consumers/subscribers (flute geometry subscriber, agent task subscribers, geometry publishers) are not running on any KVM.

### Activation runbook (KVM-side, Known Road)

Per governance, production VPS changes go through the on-node Make targets, not raw SSH from here. From an operator shell on kvm4-2 (`/opt/PMOVES.AI`):

```bash
cd /opt/PMOVES.AI/pmoves
# 1. bring up the geometry-subscriber stack. There is no Known Road make target
#    for this one yet; agentgym-rl-coordinator is the geometry subscriber here
#    (it subscribes to geometry.event.v1 + tokenism.geometry.event.v1), and the
#    only invocation the repo documents is the profile in its compose header:
docker compose -f docker-compose.yml -f docker-compose.agentgym.yml \
  --profile agentgym --profile supabase-local up -d
# 2. start harness subscribers (kiloclaw/hermes lanes)
uv run pmoves/tools/agent_task_subscriber.py --agent glm-5.1 --alias kiloclaw &
# 3. flute geometry subscriber (consumes geometry.cgp.v1)
uv run pmoves/tools/flute_geometry_subscriber.py &
# 4. verify publishers/subscribers are live on the bus
make geometry-bus-status     # -> pmoves/tools/geometry_bus_health.py
```

**Validation ladder (updated tests + validations):**
1. `pmoves/tests/test_flute_geometry_subscriber.py` — run locally before deploy (golden rule: validate on 4090/this instance first).
2. `pmoves/tools/geometry_bus_health.py` (`make geometry-bus-status`) — live publisher/subscriber map per subject.
3. `pmoves/tools/nats_cap_verify.py` — capability verification.
4. Registry subjects to watch (from `pmoves/config/agent_registry.yaml`): `geometry.cgp.v1`, `geometry.packet.encoded/decoded.v1`, `geometry.attribution.request/result.v1`, `geometry.consciousness.event.v1`, `geometry.visualization.request.v1`, `mesh.node.announce.v1`, `mesh.gpu.status.v1`, `pmoves.agent.task.v1` / `pmoves.agent.result.v1` (kiloclaw dispatch lane), `tokenism.geometry.event.v1` (legacy dual-publish window per MIRROR_FLUTE_EXECUTION_PLAN §3.2).

### This instance's bus access pattern

Direct connect is ACL-blocked. Two working options, verified/derived:
- **On-node execution** via `tailscale ssh root@pmoves-kvm4-2 'docker run --rm --network host -i python:3.12-slim sh -c "pip install -q nats-py; python3 -"' < probe.py` — proven working this session.
- **ACL fix (operator decision):** allow `kiloclaw` → tagged fleet `*:4222` in the Tailscale ACL, or tag this node as a fleet device. Until then, kiloclaw orchestrates the bus through on-node Known Roads.

## 3. Reticulum overlay — current state

- **kvm4-2 (designated hub): `rnsd` NOT installed, port 4243 NOT listening.** The DARKXSIDE Haven fan-out (`docs/handoffs/DARKXSIDE_HAVEN_RETICULUM_FANOUT_2026-08-06.md`) is design-complete, deploy-not-started.
- Stand-up (per the fan-out doc): `pip3 install rns` on kvm4-2 + `TCPServerInterface` on `0.0.0.0:4243`; Jetsons get `TCPClientInterface -> pmoves-kvm4-2:4243` + AutoInterface `group_id = pmoves`; NATS bridge subjects (`reticulum.message.received/sent.v1`, `haven.mesh.node.joined/left.v1`, `haven.mesh.health.v1`) via planned `pmoves/services/reticulum-bridge/` (port 8220) — **service dir does not exist yet**.
- Note: 4243 will need to be reachable from tagged devices through the tailnet (same ACL question as 4222).

## 4. Composio operations surface (org `pmoves_ai`, account `cataclysmstudios@gmail.com`)

| Toolkit | Status | Permission | Ops use |
|---|---|---|---|
| youtube ×2 | ACTIVE | always_allow | playlist/video gathering (persona source) |
| linkedin | ACTIVE | always_allow | future publishing validation (calendar § Prerequisites) |
| cloudflare | ACTIVE | always_allow | DNS for persona.pmoves.ai cutover (the hard blocker) |
| hostinger | ACTIVE | always_allow | VPS/domains ops |
| github | ACTIVE | ask_every_call | repo ops (each call asks) |
| perplexityai | EXPIRED | — | re-link if used |
| **gmail** | **NOT LINKED** | — | **`composio link gmail` needed** — the persona pipeline's missing source |
| tailscale/nats | n/a | — | no composio toolkits; native CLI + tailscale ssh used instead |

**Broken local paths found:** `gog` CLI OAuth = `invalid_grant` (re-auth needed for gmail/drive/calendar); `gh` CLI token invalid (use composio github or re-auth). No `ssh` client was installed on this node (installed openssh-client this session; `tailscale ssh` was already the working path).

## 5. Persona / LinkedIn source inventory (gathered 2026-09-03)

**YouTube (live via composio, 25 playlists):**
- `ai` playlist `PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8`: **2,234 videos** (docs cited 2,028 crawled)
- **`PMOVES.AI` playlist `PLa64xecRY4d0`: 345 videos, created 2026-08-11** — new, postdates all three persona docs; channel handle @PMOVESAI, channel id `UCtb7g7E6kmf0Il7btcx9RTQ`
- Top research playlists: science/technology 273, sustainable agriculture 226, science/state of the day 164, nutrition 157, sustainable energy 124, 3d print 68, science/history 71, electrical 25
- Creative: Art 11, Content 9, Rap 6, tf 5, Mk 22, cattracks 2

**Discord (guild 1146608275652104194, wired on this instance):** `#pmovesai` (PMOVES Publisher ingest feed), `#soundcloud`, `#announcements` (automated service feed), `#deep-research`, `#creator`, `#agent-trails`, `#knowledge-base` — persona-grade source channels.

**Gmail/Drive:** blocked (gog invalid_grant; composio gmail not yet linked) — link and re-gather.

**Site prerequisites re-verified 2026-09-03:** `persona.pmoves.ai` **NXDOMAIN** (still the hard blocker); `pmoves.ai` → 403; `/chit-tour/` → 404. Cloudflare access via composio is the unlock path.

**Registry counts (live):** **104 agents** (docs: 98), **14 teams** (docs: 13), **13 rooms** ✓, **79 gitlinked submodules** (docs: 64). Body counts in `06_linkedin_profile.md` need a full sweep before publishing.

## 6. Instance config deltas (this node)

- [x] Repo synced: `~/workspace/PMOVES.AI` @ `410e8169c` (pulled this session; pre-existing uncommitted local changes left untouched)
- [x] `Pmoves-cipher` cloned @ `PMOVES.AI-Edition-Hardened` (619054b0) — scripts are ByteRover/openclaw setup utilities, NOT reticulum transport; reticulum design lives in the fan-out handoff doc
- [x] openssh-client installed (tailscale ssh was already functional)
- [ ] `composio link gmail` — operator OAuth click
- [ ] `gog` re-auth (`invalid_grant`)
- [ ] gh re-auth or rely on composio github
- [ ] Tailscale ACL decision: kiloclaw → fleet 4222/4243
- [ ] Bus activation on kvm4-2 (§2 runbook) + subscriber set
- [ ] reticulum hub stand-up on kvm4-2 (§3)

## 7. Recommended division of labor

- **kiloclaw (this instance):** cloud ops surface — composio (youtube/linkedin/cloudflare/hostinger), persona source gathering, docs truth-keeping, bus health monitoring via on-node probes, DNS cutover when the operator green-lights it.
- **pmoves-4090 (local field claw):** local validation before any deploy (founder's golden rule), harness dispatch seat.
- **KVMs:** bus runtime (kvm4-2 hub + subscribers; kvm4-1 gateway), activated via on-node Known Roads.
