# Access Roster — Provisioning Overlay

> **Who can reach what.** Rendered from [`roster/users.yaml`](roster/users.yaml) +
> [`roster/groups.yaml`](roster/groups.yaml). This is the operational overlay: the
> `access` / `access_policy` blocks below are what a provisioning step turns into
> Tailscale ACL groups + RustDesk enrollment. Declarations here; provisioning is a
> separate, auditable action. Tailnet hostnames only — never IPs.

## Access grants

| Actor | Type | Tailscale | Exit tag | RustDesk | Notes |
|-------|------|-----------|----------|----------|-------|
| `darkxside` | human | member · **admin** | — | enrolled · owner | Emperor |
| `claude-4090` | agent | via `pmoves-4090` | — | via host · owner | — |
| `kilocode` | agent | via `pmoves-5090` | — | — | — |
| `codex` | agent | — | — | — | git contributor |
| `cipher` | agent | — | — | — | memory (:8105, internal net) |
| `minimax-floos` | agent | — | — | — | voice |
| `node-4090` | node | member · **admin** | — | **not enrolled** · owner | staged: `enroll-4090-rustdesk.cmd` |
| `node-5090` | node | (infra) | — | — | TODO enroll |
| `node-spark` | node | (infra) | — | — | TODO enroll |
| `node-z890` | node | (infra) | — | — | re-enroll after reinstall |
| `node-knuckles` | node | (infra) | — | — | TODO enroll |
| `node-kvm2` | node | member · infra | `tag:exit` | — | **RustDesk relay host** (hbbs/hbbr) |
| `node-kvm4-1` | node | member · infra | `tag:exit` | — | designated egress (Mullvad upstream) |
| `node-kvm4-2` | node | member · infra | `tag:exit` | — | exit node |

## Group access policy

| Guild | Tailscale group | Exit tag | RustDesk role |
|-------|-----------------|----------|---------------|
| Core | admin | — | owner |
| DAO Governance | — | — | — |
| Infra Cloud | infra | `tag:exit` | owner |
| Delivery | infra | — | — |
| Voice / FlOO$ | — | — | — |

## Provisioning recipe (declaration → live access)

**Tailscale (mesh membership + exit approval)**
- ACL groups live in `pmoves/configs/tailscale-acl-policy.json`. A guild's
  `tailscale_group` maps to a group there; add the member's device.
- Exit nodes: bring up with a **`tag:exit` reusable authkey** → advertise **and**
  self-approve (autoApprovers already set for `tag:exit`). No console click per node.
- Verify: `/fleet:acl-audit`, `exit-node-healthcheck.sh --mode status`.

**RustDesk (self-hosted relay on `pmoves-kvm2`)**
- Desktop node → `pmoves/scripts/fleet/rustdesk-enroll.{sh,ps1} --host pmoves-kvm2 --key <server pubkey>`
  (Windows service nodes need elevation).
- Mobile / portable → `/fleet:enroll ROLE=<role> DEVICE="<label>"` → CHIT-signed token + QR,
  scanned in the RustDesk app. **Relay is mesh-only** → the device must be on the tailnet first.
- Verify: `/fleet:rustdesk-check`.

**The loop:** add a user to `users.yaml` with a guild → the guild's `access_policy`
tells you exactly which Tailscale group + RustDesk role to provision. One source, one recipe.

---

_Pending enrollments: 4090 (staged launcher), 5090/SPARK/Knuckles (TODO), Z890 (after reinstall)._
