# Cataclysm Studios Inc — Roster

> **Discovery overlay.** The org + access layer, rendered from
> [`PMOVES-PROVISIONS/roster/users.yaml`](PMOVES-PROVISIONS/roster/users.yaml) +
> [`groups.yaml`](PMOVES-PROVISIONS/roster/groups.yaml). It **owns** humans, org
> guilds, and access grants; it **references** the canonical sources for agents/nodes
> and personas — it does not redefine them:
>
> - Agents / teams / node_affinity → [`pmoves/configs/agent-teams.yaml`](../pmoves/configs/agent-teams.yaml) (62 agents · 11 teams)
> - Agent personas → [`pmoves/docs/AGENTS/PERSONAS.md`](../pmoves/docs/AGENTS/PERSONAS.md)
> - Node hardware → `pmoves/config/profiles/<node>.yaml`
>
> Other overlays: governance → [`L5-LEGENDARY/GOVERNANCE_ROSTER.md`](L5-LEGENDARY/GOVERNANCE_ROSTER.md) ·
> access → [`PMOVES-PROVISIONS/ACCESS_ROSTER.md`](PMOVES-PROVISIONS/ACCESS_ROSTER.md).
> Edit the YAML, re-render — never hand-edit overlay data.

## Humans

### DARKXSIDE (Russell Richardson) — `darkxside`
- **Role:** Founder / Operator — Emperor (final signoff, direction)
- **Guilds:** Core · Infra Cloud · DAO Governance · **Tier:** owner
- **Contact:** cataclysmstudios@gmail.com
- Also in `agent-teams.yaml` → External Contributors (`powerfulmoves`)

_Add collaborators / DAO members / Fordham Hill participants in `users.yaml:humans`._

## Agents  *(access + guild layer; identity lives in the canonical sources)*

| Actor | Canonical ref (`agent-teams.yaml`) | Persona | Host | Guilds |
|-------|-----------------------------------|---------|------|--------|
| **4090-claude** `claude-4090` | External Contributors: claude-opus | — | `pmoves-4090` | Infra Cloud · Delivery |
| **KiloCode** `kilocode` | External Contributors: kilocode | — | `pmoves-5090` | Delivery |
| **Codex** `codex` | External Contributors: codex | — | — | Delivery |
| **Cipher** `cipher` | Research & Knowledge: cipher_memory (:8105) | — | — | Core |
| **MiniMax (FlOO$)** `minimax-floos` | Media & Voice _(TODO)_ | PERSONAS.md → FlOO$ suits | — | Voice |

## Nodes  *(access + tailnet host; hardware in node profiles)*

| Node | Canonical ref | Tailnet host | Exit | Guilds |
|------|---------------|--------------|------|--------|
| **4090** `node-4090` | node_affinity: powerfulmoves | `pmoves-4090` | — | Core · Infra Cloud |
| **5090** `node-5090` | profile: 5090.yaml | `pmoves-5090` | — | Infra Cloud |
| **SPARK** `node-spark` | profile: spark.yaml | `pmoves-spark` | — | Infra Cloud |
| **Z890** `node-z890` | node_affinity: z890 | `pmoves-z890` | — | Infra Cloud |
| **Knuckles** `node-knuckles` | profile: knuckles.yaml | `pmoves-knuckles` | — | Infra Cloud |
| **pmoves-kvm2** `node-kvm2` | node_affinity: kvm2 | `pmoves-kvm2` | ✓ | Infra Cloud |
| **pmoves-kvm4-1** `node-kvm4-1` | node_affinity: kvm4-1 | `pmoves-kvm4-1` | ✓ | Infra Cloud |
| **pmoves-kvm4-2** `node-kvm4-2` | node_affinity: kvm4-2 | `pmoves-kvm4-2` | ✓ | Infra Cloud |

_Tailnet hostnames marked TODO in `users.yaml` need operator confirmation._

## Org Guilds  *(people/access — distinct from the 11 functional agent teams)*

| Guild | Purpose | Charter | Functional teams | Members |
|-------|---------|---------|------------------|---------|
| **Core** | Founding operators + decision-makers | — | — | darkxside, cipher, node-4090 |
| **DAO Governance** | Constitution, attribution, audit | [DAO Constitution](L2-DESIGN/constitution/Cataclysm_DAO_Constitution_v0.1.md) | Evolution & CHIT | darkxside |
| **Infra Cloud** | Fleet infra — runners, exit nodes, mesh | [Guild Charter](L2-DESIGN/charters/Infra_Cloud_Guild_Charter_v0.1.md) | Infrastructure & Networking · Observability | 11 actors |
| **Delivery** | Three-Body implementation lane | — | Sandbox & Execution | claude-4090, kilocode, codex |
| **Voice / FlOO$** | Persona voice pipeline | — | Media & Voice | minimax-floos |

---

_Add a user/group: edit `PMOVES-PROVISIONS/roster/{users,groups}.yaml` (new agent/node → add to
`agent-teams.yaml` first, reference it here), re-render. Access grants feed Tailscale ACL groups +
RustDesk enrollment — see `PMOVES-PROVISIONS/ACCESS_ROSTER.md`._
