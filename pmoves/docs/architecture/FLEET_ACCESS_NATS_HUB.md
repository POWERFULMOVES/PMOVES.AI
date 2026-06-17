# Fleet Access & NATS Hub Architecture (Tailscale-native)

> **Status:** design blueprint (2026-06-16). Execution is staged — nothing here
> is applied to the live tailnet yet. The SSH unblock stopgap is PR #1828.
>
> **Pattern source:** [Tailscale — Connect inference servers (AI infrastructure access)](https://tailscale.com/docs/use-cases/ai-infrastructure-access/connect-inference-servers)

## 1. Why this doc exists

Restoring the NATS fleet bus on `pmoves-kvm4-2` (PRs #1813 / #1824 / #1826 / #1830)
surfaced two **structural** gaps that are bigger than NATS:

1. **Cross-node service reachability.** PMOVES service networks (`pmoves_bus`,
   `pmoves_data`, …) are `internal: true`. Docker installs **no published-port
   DNAT** for a container on an internal-only network, so a service's `ports:` are
   recorded but never plumbed — invisible on a single-node stack, fatal for the
   cross-node mesh. #1824 worked around it (multi-home nats onto a non-internal
   network + bind to the tailnet IP), but every new cross-node service would hit
   the same class of bug.
2. **Fleet nodes are user-owned, not tagged.** The ACL *defines* `tag:pmoves` /
   `tag:gpu` / `tag:vps` / `tag:lab` / `tag:exit` / `tag:partner` / `tag:guest` +
   `tagOwners`, but the actual devices carry **no tag** — they authenticate as the
   owner's user. That single gap is the root of three separate problems (below).

Tailscale's official AI-infrastructure access pattern resolves all of this with
**tagged infra + grants (deny-by-default) + per-tenant tags + service sidecars**.
This doc maps that pattern onto PMOVES.

## 2. The keystone: tag the fleet as infrastructure

Today the fleet nodes are user-owned devices. Per the Tailscale pattern, fleet
nodes should carry **machine-identity tags** (re-enrolled with tagged auth keys).
This one change fixes three things at once:

| Problem | How tagging fixes it |
|---------|----------------------|
| **Owner forced into SSH check-mode** (the #1828 issue) | Tagged devices have no user owner, so they leave every user's `autogroup:self`. The `member→self` check rule then *can't* match owner→fleet SSH. (See [[reference: tailscale ssh check-mode]] — owner role ≠ admin role, and check beats accept regardless of rule order, so excluding the fleet from the check rule's target is the only robust fix.) |
| **Server re-auth churn** | "Tagged devices have automatic key expiry disabled" — servers never need periodic browser re-auth. |
| **No basis for multi-tenant isolation** | Grants are `src group → dst tag → ports`. Without tagged infra there is nothing to scope tenant access *to*. |

**Tag plan (roles, additive to `tag:pmoves`):**

| Node class | Tags |
|------------|------|
| Bus hub (kvm4-2) | `tag:pmoves`, `tag:hub` |
| GPU compute (5090 / 4090 / spark) | `tag:pmoves`, `tag:gpu` |
| VPS edge (kvm4-1) | `tag:pmoves`, `tag:vps`, `tag:exit` |
| Linux container host (b850) | `tag:pmoves`, `tag:lab` |
| Storage (JuiceFS nodes) | `tag:pmoves`, `tag:storage` |
| Inference (TensorZero / Ollama / Agent Zero) | `tag:pmoves`, `tag:inference` |

> Re-tagging is **outward-facing and per-node** (re-enroll each device with a
> tagged auth key; the device loses its user identity). Stage it one node at a
> time and keep auth keys out of git. This is the substance of the long-standing
> "Tailscale never properly configured" thread.

## 3. NATS hub as a separate concern

**Decision (2026-06-16):** the bus is a **dedicated hub**, separate from
storage/compute. NATS is *not* co-located with inference or storage concerns.

- The hub node carries `tag:hub`; it is the canonical bus all nodes dial
  (`nats.pmoves.ai:4222`).
- **Exposure (hybrid): keep NATS on the working path.** NATS already reaches the
  fleet via the #1824 fix (non-internal docker network + `NATS_BIND` = node tailnet
  IP, mesh-only). Don't churn what works. A NATS Tailscale sidecar is an *optional*
  future refinement, not required.
- **`pmoves_bus_pub` is dropped.** The earlier "dedicated published-bus docker
  network" (option 3) is superseded — the *hub* is the separation of concerns, and
  net-new services use sidecars (§4) rather than a shared published docker network.

## 4. Storage & inference: Tailscale sidecars (hybrid)

Net-new cross-node services join the tailnet **directly** via a Tailscale sidecar
container, instead of docker host-publish + DNAT:

```yaml
services:
  juicefs:                      # or: inference, etc.
    image: <service-image>
    network_mode: service:ts-juicefs   # share the sidecar's network namespace
    depends_on: [ts-juicefs]
  ts-juicefs:
    image: tailscale/tailscale:stable
    hostname: juicefs           # → MagicDNS name juicefs.<tailnet>.ts.net
    environment:
      - TS_AUTHKEY=${TS_AUTHKEY_JUICEFS}   # ephemeral, tagged auth key (tag:storage)
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_EXTRA_ARGS=--advertise-tags=tag:pmoves,tag:storage
    volumes:
      - ts-juicefs-state:/var/lib/tailscale
    cap_add: [NET_ADMIN, SYS_MODULE]
```

Why this is the target for JuiceFS / inference (not the NATS host-publish path):
- **Sidesteps the entire internal-network/DNAT/host-bind bug class** (the #1824
  problem) — the service is *on* the tailnet, reached by MagicDNS, not by
  publishing a host port.
- **Ephemeral tagged keys** auto-remove the device when the container stops (no
  orphaned tailnet nodes).
- **Per-service machine identity** → clean grant targets (`dst: tag:storage`).

## 5. Access control: `acls` → grants, deny-by-default

Migrate the network `acls` array to **grants** (the `ssh` array stays as-is —
grants only supersede network ACLs, not SSH rules). Grants are deny-by-default:

```jsonc
"grants": [
  // Owner/admins: full access to the whole fleet.
  { "src": ["autogroup:admin", "autogroup:owner"], "dst": ["tag:pmoves"], "ip": ["*"] },

  // Fleet east-west: bus + storage + inference reachable across tagged nodes.
  { "src": ["tag:pmoves"], "dst": ["tag:hub"],       "ip": ["4222", "9223"] },
  { "src": ["tag:pmoves"], "dst": ["tag:storage"],   "ip": ["*"] },
  { "src": ["tag:pmoves"], "dst": ["tag:inference"], "ip": ["*"] }
]
```

## 6. Multi-tenant model ("real co-tenants")

Per-tenant **tag + group** pairs, isolated by grants — exactly the doc's pattern.
Maps onto the existing `tag:partner` / `tag:guest`:

```jsonc
"tagOwners": {
  "tag:tenant-a": ["autogroup:admin"],
  "tag:tenant-b": ["autogroup:admin"]
},
"groups": {
  "group:tenant-a-users": ["a-user@example.com"],
  "group:tenant-b-users": ["b-user@example.com"],
  "group:tenants": ["a-user@example.com", "b-user@example.com"]  // union, for the SSH check rule
},
"grants": [
  { "src": ["group:tenant-a-users"], "dst": ["tag:tenant-a"], "ip": ["*"] },
  { "src": ["group:tenant-b-users"], "dst": ["tag:tenant-b"], "ip": ["*"] }
]
```

- Tenants reach **only** their own tagged resources (deny-by-default blocks the rest).
- SSH check-mode (browser re-auth) applies to `group:tenants` on `autogroup:self`
  (their *own* user-owned devices) — never the owner's tagged fleet. This is the
  durable form of PR #1828; #1828's empty `group:tenants` is the placeholder this
  fills in.

## 7. Staged rollout

1. **Now — SSH unblock (PR #1828).** Scope the check rule to `group:tenants` +
   add `autogroup:owner` to accept. No device changes. Apply manually at
   `login.tailscale.com/admin/acls` (no gitops-apply exists for the policy).
2. **Tag the fleet (§2).** Re-enroll nodes one at a time with tagged auth keys.
   After this, the §6 SSH model is correct *by construction* and server re-auth
   churn ends.
3. **Migrate `acls` → grants (§5).** Deny-by-default east-west on tagged roles.
4. **Sidecar net-new services (§4).** JuiceFS first (`tag:storage`), then inference
   (`tag:inference`), as they deploy. NATS stays on its hub path.
5. **Onboard tenants (§6).** Per-tenant tag/group/grant; populate `group:tenants`.

## 8. Caveats / open questions

- **No gitops-apply** for `pmoves/configs/tailscale-acl-policy.json` — every change
  is applied manually in the admin console. A future apply-workflow (Tailscale API
  via `TAILSCALE_API_KEY`, already a repo secret) would close this gap.
- Re-tagging is **destructive to user identity** on each device and is outward-facing
  — operator-gated, staged, auth keys never committed.
- `acls`→grants is a tailnet-wide change; validate in the console's preview before
  applying.

## References

- Tailscale: [Connect inference servers](https://tailscale.com/docs/use-cases/ai-infrastructure-access/connect-inference-servers),
  [Tailscale SSH (kb/1193)](https://tailscale.com/kb/1193/tailscale-ssh),
  [Tags (kb/1068)](https://tailscale.com/kb/1068/tags),
  [Grants vs ACLs](https://tailscale.com/docs/reference/grants-vs-acls)
- PMOVES: `pmoves/configs/tailscale-acl-policy.json`, PR #1828 (SSH stopgap),
  PRs #1813/#1824/#1826/#1830 (NATS bus restoration),
  `pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md`
