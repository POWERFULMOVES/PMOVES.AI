List and manage stale Tailscale nodes (offline > 60 days).

## Usage

Run this command to:
- Identify stale Tailscale nodes that should be cleaned up
- Reduce the mesh attack surface
- Keep the Tailscale admin console navigable

## Arguments

- No args — List stale nodes (read-only)
- `--remove <hostname>` — Remove a specific stale node (requires user confirmation)

## Implementation

### Step 1: Get current node status

```bash
tailscale status
```

Parse output for nodes with "offline, last seen X days ago" where X > 60.

### Step 2: Classify nodes

For each offline node, classify:
- **STALE (>60d):** Recommend removal
- **RECENT (<60d):** Note but do not recommend removal
- **ACTIVE:** Skip (online or idle)

Cross-reference against known node classes from `pmoves/docs/TAILSCALE_NODE_HYGIENE.md`:
- `mobile-workstation` (4090 laptop)
- `primary-gpu-node` (Z890)
- `api-gateway-node` (VPS)
- `edge-arm-node` (Jetson)
- `phone-client`, `tablet-client`

### Step 3: Report

Output a table (hostnames only, NEVER IPs):

| Hostname | OS | Last Seen | Classification | Action |
|----------|----|-----------|----------------|--------|
| (name) | (os) | (duration) | STALE/RECENT/ACTIVE | Remove / Keep / Investigate |

### Step 4: Remove (if --remove specified)

**This is destructive and requires user confirmation.**

Node removal uses the Tailscale Admin API:
```bash
# Get device ID (never display to user)
DEVICE_ID=$(curl -fsS -u "${TAILSCALE_API_KEY}:" \
  "https://api.tailscale.com/api/v2/tailnet/-/devices" | \
  jq -r '.devices[] | select(.hostname == "<hostname>") | .id')

# Remove (after user confirms)
curl -fsS -X DELETE -u "${TAILSCALE_API_KEY}:" \
  "https://api.tailscale.com/api/v2/device/${DEVICE_ID}"
```

**Required:** `TAILSCALE_API_KEY` environment variable (admin credential).

### Step 5: Verify removal

```bash
tailscale status | grep "<hostname>" && echo "WARNING: Node still visible" || echo "Node removed successfully"
```

## Security

- NEVER output raw Tailscale IPs or device IDs
- `TAILSCALE_API_KEY` is an admin credential — never display
- Node removal is destructive — always confirm with user
- Verify node is truly decommissioned before removing (`tailscale ping` first)
- Log removals to Cipher for audit trail

## Known Road

```
make -C pmoves fleet-stale-audit
```

## Related

- `/fleet:status` — Quick fleet overview
- `/fleet:acl-audit` — Verify ACL policy alignment
- `pmoves/docs/TAILSCALE_NODE_HYGIENE.md` — Cleanup criteria and procedures
- `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md` — Full runbook
