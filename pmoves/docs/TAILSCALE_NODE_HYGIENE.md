# Tailscale Node Hygiene

Periodic cleanup of stale Tailscale nodes reduces the mesh attack surface and keeps the admin console navigable.

## Stale Nodes (as of 2026-03-25)

| Node | Last Seen | Notes |
|------|-----------|-------|
| `powerfulmoves` | 285 days ago | Old 4090 laptop registration, replaced by `pmoves-laptop` |
| `pmoves-pro` | 135 days ago | Decommissioned node |
| `pmoves-botz` | 95 days ago | Previous BoTZ dev node |

## Cleanup Procedure

Node removal is a **manual operation** (destructive, affects the entire tailnet).

### 1. Verify the node is truly decommissioned

```bash
# Check from any online node
tailscale ping <node-name>
# If it responds, the node is NOT stale -- do not remove
```

### 2. Remove via Tailscale Admin Console

1. Go to https://login.tailscale.com/admin/machines
2. Find the stale node
3. Click the three-dot menu > **Remove device**
4. Confirm removal

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
