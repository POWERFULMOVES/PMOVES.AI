# Handoff: PR-A — Add Network-Tier YAML Anchors to `docker-compose.base.yml`

**For:** Z890-CLAUDE (or SPARK / 5090-CLAUDE)  
**Requires:** `COMPOSE_EDIT=1` (damage-control hook bypass — approved by operator under Known Roads)  
**Branch:** new branch off `main`, e.g. `infra/compose-network-tier-anchors`  
**File:** `pmoves/docker-compose.base.yml`  
**Doctrine:** `pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md` §Pending PR-A

---

## Context

PR #1466 (`infra/network-hardening-1465`) landed the doctrine doc, assertion tool, and
alias enforcement wrapper. The final piece (PR-A) is adding 4 YAML anchor definitions
to `docker-compose.base.yml` so services can reference canonical network-tier settings
without duplicating subnet/driver/internal values.

The 6 networks are already defined in `docker-compose.base.yml` lines 518–581 with
correct subnets and drivers. The anchors sit ABOVE the `networks:` key and reference
those definitions — they do not change any service networking behavior.

---

## Exact Change

Insert the following block **before** line 518 (`networks:`) in `pmoves/docker-compose.base.yml`:

```yaml
# ── Network-Tier Anchors (§1465 PR-A) ─────────────────────────────────────────
# Reference these in service definitions to guarantee correct tier membership.
# Pattern: <<: *x-network-<tier>
#
# Usage example:
#   networks:
#     - pmoves_bus      # <<: *x-network-bus-hardened implies this tier
#
# These anchors document intent; compose merges them at parse time.

x-network-internal-only: &x-network-internal-only
  # Air-gapped internal bridge — no outbound internet
  driver: bridge
  internal: true

x-network-bus-hardened: &x-network-bus-hardened
  # NATS message bus — internal, high-trust, no internet
  # Containers on this tier: NATS, services consuming NATS (agent-zero, archon, flute-gateway)
  driver: bridge
  internal: true

x-network-external-bridged: &x-network-external-bridged
  # Internet-capable bridge — for LLM API calls, pip installs, upstream services
  # Only pmoves_external uses this tier. Restrict attach via service-tier anchors.
  driver: bridge
  internal: false

x-network-tailnet-published: &x-network-tailnet-published
  # Tailnet-reachable network (internet-capable + port-forwarded via Tailscale)
  # Windows Docker Desktop: bind to 0.0.0.0, restrict at Tailscale ACL layer.
  # See: pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md §Windows Docker Desktop
  driver: bridge
  internal: false

```

No changes to the existing `networks:` definitions below — the anchors document but
do not alter the current topology.

---

## How to Execute

```bash
# In the z890 worktree for PMOVES.AI:
COMPOSE_EDIT=1 <editor> pmoves/docker-compose.base.yml
# Insert the block above immediately before the "networks:" key (line 518)

# Validate compose parses correctly:
docker compose -f pmoves/docker-compose.base.yml config --quiet && echo "parse OK"

git add pmoves/docker-compose.base.yml
git commit -m "feat(compose): add network-tier YAML anchors (#1465 PR-A)

Four anchors document intent for each network tier:
- x-network-internal-only (air-gapped internal bridge)
- x-network-bus-hardened (NATS bus tier)
- x-network-external-bridged (internet-capable)
- x-network-tailnet-published (Tailscale-ACL-restricted, Windows caveat)

No behavior change — existing network definitions are unchanged.
See: pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md §Pending PR-A
"
git push origin infra/compose-network-tier-anchors
# Open PR targeting main
```

---

## Verification

```bash
# Compose must parse cleanly:
docker compose -f pmoves/docker-compose.base.yml config --quiet && echo "parse OK"

# All 6 networks must still appear:
docker compose -f pmoves/docker-compose.base.yml config | grep -E "name: pmoves_"
# Expected 6 lines: pmoves_data, pmoves_api, pmoves_app, pmoves_bus, pmoves_monitoring, pmoves_external

# Run the assertion tool to confirm subnets unchanged:
bash pmoves/scripts/audit_network_reality.sh --ports-only
```

---

## Related

- `pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md` §Pending: Network-Tier Hardening Anchors (PR-A)
- PR #1466 (`infra/network-hardening-1465`) — doctrine + assertion tool (merged)
- Issue #1465 — network hardening lane
- `pmoves/scripts/audit_network_reality.sh` — run after to confirm no subnet drift
