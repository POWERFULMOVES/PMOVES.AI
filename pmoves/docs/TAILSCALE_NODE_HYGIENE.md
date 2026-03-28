# Tailscale Node Hygiene

_Last updated: 2026-03-28_

Periodic cleanup of stale Tailscale nodes reduces the mesh attack surface and keeps the admin console navigable.

## Stale Nodes (as of 2026-03-28)

Keep exact device IDs, live tailnet IPs, personal device names, and user-associated hostnames in the
admin console, a local ignored export, or Cipher. Committed docs should use role-based descriptions only.

| Node Class | Last Seen | Notes |
|------------|-----------|-------|
| `legacy-windows-host` | 288.3 days ago | Old workstation registration; replaced by current fleet nodes |
| `legacy-phone` | 247.6 days ago | Old mobile registration |
| `legacy-dev-node` | 137.6 days ago | Decommissioned node |
| `legacy-botz-node` | 97.5 days ago | Previous BoTZ development registration |
| `unknown-temp-linux` | 3.3 days ago | Unknown or temporary Linux registration; confirm before removal |

One currently active mobile device was last seen on 2026-03-28 and should not be treated as stale.

## Cleanup Procedure

Node removal is a **manual operation** (destructive, affects the entire tailnet).

### 1. Verify the node is truly decommissioned

```bash
# Check from any online node
tailscale ping <node-name>
# If it responds, the node is NOT stale -- do not remove
```

### 2. Remove via Tailscale Admin Console or Admin API

1. Go to https://login.tailscale.com/admin/machines
2. Find the stale node
3. Click the three-dot menu > **Remove device**
4. Confirm removal

API alternative:

```bash
curl -fsS \
  -u "${TAILSCALE_API_KEY}:" \
  "https://api.tailscale.com/api/v2/tailnet/-/devices"

curl -fsS -X DELETE \
  -u "${TAILSCALE_API_KEY}:" \
  "https://api.tailscale.com/api/v2/device/<deviceId>"
```

Notes:
- `TAILSCALE_API_KEY` is an admin credential. Keep it in GitHub environment secrets, a `*_FILE` secret mount, or a local ignored file only.
- Tailscale API access tokens authenticate with HTTP Basic auth: API key as username, empty password.
- The repo-local API schema for these endpoints lives at `pmoves/docs/API_Docs/tailscale-api.yaml`.
- When you execute removal, capture the exact device ID only in the operator log or Cipher handoff, not in committed docs.

### 3. Verify removal

```bash
tailscale status
# The removed node should no longer appear
```

## Active Node Classes (reference)

| Node Class | Role |
|------------|------|
| `mobile-workstation` | 4090 laptop |
| `primary-gpu-node` | Z890 development / GPU node |
| `api-gateway-node` | VPS gateway |
| `edge-arm-node` | Jetson / ARM edge node |
| `wsl-overlay` | WSL2 companion runtime |
| `host-os` | Primary Windows host |
| `tablet-client` | Tablet operator device |
| `phone-client` | Phone operator device |

## Schedule

Review `tailscale status` monthly. Any node offline > 60 days without a planned return should be investigated for removal.
