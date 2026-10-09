# Roster — Users & Groups (org + access overlay)

> The people-and-access layer for Cataclysm Studios Inc. This roster does **not**
> redefine the fleet's agents or nodes — those already live in canonical sources.
> It is an **overlay on top** that owns three things and **references** the rest.

## What this roster OWNS vs REFERENCES

| Owns (source of truth here) | References (canonical elsewhere) |
|-----------------------------|----------------------------------|
| **Humans** — members, contact, tier | **Agents / teams** → [`pmoves/configs/agent-teams.yaml`](../../../pmoves/configs/agent-teams.yaml) (62 agents · 11 teams · node_affinity) |
| **Org guilds** — Core, Governance, Infra Cloud → charters | **Agent personas** → [`pmoves/docs/AGENTS/PERSONAS.md`](../../../pmoves/docs/AGENTS/PERSONAS.md) (identity/voice/behavior, AGNOTE4482-governed) |
| **Access grants** — Tailscale groups, exit tags, RustDesk role | **Node hardware** → `pmoves/config/profiles/<node>.yaml` + agent-teams `node_affinity` |

So: **do not re-list the 62 agents or node specs here.** For a non-human actor, the roster
carries a thin record: its `ref` (into agent-teams.yaml), its `persona` (into PERSONAS.md,
if any), its guild membership, and its **access grant** — nothing that duplicates the source.

## The lattice → overlays model

```text
   humans + org-guilds + access-grants   (this dir, source of truth)
                    │   ⟵ references ⟶  agent-teams.yaml + PERSONAS.md + node profiles
        ┌───────────┼───────────────────┐
        ▼           ▼                   ▼
   ROSTER.md   L5-LEGENDARY/        PMOVES-PROVISIONS/
   (root)      GOVERNANCE_ROSTER.md ACCESS_ROSTER.md
   discovery   governance view      provisioning view
```

Relevant data floats up; each overlay surfaces the slice for where it lives.

## Schema — `users.yaml`

```yaml
version: 1
humans:                              # OWNED — full detail
  - id: <kebab>
    display_name: ""
    role: ""
    contact: <email>
    tier: owner | member | guest
    guilds: [<group id>, ...]
    contributor_ref: "agent-teams.yaml → External Contributors: <name>"  # if listed there
    access:
      tailscale: { member: true, groups: [<acl group>] }
      rustdesk:  { enrolled: true|false, role: owner|partner|guest }

actors:                              # REFERENCE — agents & nodes; access only
  - id: <kebab>
    kind: agent | node
    ref: "agent-teams.yaml → <team>: <name>"   # canonical definition lives there
    persona: "PERSONAS.md → <persona>"          # agents only, or null
    host: <tailnet hostname>                     # agent — node it runs on
    tailnet_host: <hostname>                     # node — NEVER an IP
    exit_node: true | false                      # node
    guilds: [<group id>, ...]
    access:
      tailscale: { member: true, groups: [<acl group>], exit_tag: tag:exit|null }
      rustdesk:  { enrolled: true|false, role: ..., via_host: <hostname> }
```

## Schema — `groups.yaml`

Org guilds (people/access), **distinct from** the 11 *functional* agent teams in
`agent-teams.yaml`. A guild maps membership → charter → access policy.

```yaml
version: 1
groups:
  - id: <kebab>
    label: ""
    purpose: ""
    charter: <path to .md, or null>
    functional_teams: [<agent-teams.yaml team>, ...]   # optional cross-link
    members: [<user/actor id>, ...]
    access_policy:
      tailscale_group: <acl group>       # → pmoves/configs/tailscale-acl-policy.json
      exit_tag: tag:exit | null
      rustdesk_role: owner|partner|guest|null
```

## Add a user / group

1. Human → append to `users.yaml:humans`. Agent/node → append to `users.yaml:actors`
   with a `ref` into `agent-teams.yaml` (add it there first if it's genuinely new).
2. Wire guild membership both ways (`guilds` ↔ `members`).
3. Re-render the overlays.
4. Access provisioning consumes the `access` / `access_policy` blocks:
   - **Tailscale** ACL groups → `pmoves/configs/tailscale-acl-policy.json` (+ `tag:exit` authkey).
   - **RustDesk** → `pmoves/scripts/fleet/rustdesk-enroll.{sh,ps1}` or a `/fleet:enroll` QR.

## Guardrails

- **No IPs** — tailnet hostnames only.
- **Don't duplicate** agent-teams.yaml / PERSONAS.md / node profiles — reference them.
- Access grants are declarations; provisioning is a separate auditable step.
