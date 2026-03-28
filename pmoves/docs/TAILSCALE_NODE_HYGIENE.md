# Tailscale Node Hygiene

_Last updated: 2026-03-28_

Periodic cleanup of stale Tailscale nodes reduces the mesh attack surface and keeps the admin console navigable.

## Stale Nodes (as of 2026-03-28)

| Node | Device ID | Last Seen | Notes |
|------|-----------|-----------|-------|
| `POWERFULMOVES` | `nj48mQncqB21CNTRL` | 288.3 days ago | Old Windows registration; replaced by current fleet nodes |
| `google-pixel-9-pro-xl` | `naSJJXxmmb11CNTRL` | 247.6 days ago | Old phone registration |
| `pmoves-pro` | `n46xjnH3F211CNTRL` | 137.6 days ago | Decommissioned node |
| `pmoves-botz` | `nn26NGQCjU11CNTRL` | 97.5 days ago | Previous BoTZ dev node |
| `2871444ae72428` | `nZFhjMhFcA11CNTRL` | 3.3 days ago | Unknown/temporary Linux registration; confirm before removal |

`pixel-10-pro-xl` was last seen on 2026-03-28 and should not be treated as stale.

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
  -H "Authorization: Bearer $TAILSCALE_API_KEY" \
  "https://api.tailscale.com/api/v2/tailnet/-/devices"

curl -fsS -X DELETE \
  -H "Authorization: Bearer $TAILSCALE_API_KEY" \
  "https://api.tailscale.com/api/v2/device/<deviceId>"
```

Notes:
- `TAILSCALE_API_KEY` is an admin credential. Keep it in GitHub environment secrets, a `*_FILE` secret mount, or a local ignored file only.
- The repo-local API schema for these endpoints lives at `pmoves/docs/API_Docs/tailscale-api.yaml`.

### 3. Verify removal

```bash
tailscale status
# The removed node should no longer appear
```

## Active Nodes (reference)

| Node | Role |
|------|------|
| `pmoves-laptop` | 4090 laptop (mobile workstation) |
| `pmoves-z890` | Z890 (dev/GPU) |
| `pmoves-kvm4-1` | KVM4-1 (API gateway) |
| `pmoves-nano` | Jetson Nano |
| `pmoves-powerfulmoves` | WSL2 on laptop |
| `powerfulmoves-1` | Windows host (laptop alt) |
| `pmoves-tablet` | Android tablet (mobile) |
| `pmoves-phone` | Android phone (mobile) |

## Schedule

Review `tailscale status` monthly. Any node offline > 60 days without a planned return should be investigated for removal.
