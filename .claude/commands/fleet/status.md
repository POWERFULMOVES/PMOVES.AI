Show fleet status: Tailscale nodes and RustDesk relay health.

## Usage

Run this command to:
- See all Tailscale nodes (online, offline, stale)
- Check KVM2 RustDesk relay health (hbbs/hbbr)
- Verify RustDesk client is running on the current machine
- Get a fleet-wide overview before remote access operations

## Implementation

Execute the following steps:

1. **Tailscale node status (hostnames only — NEVER output raw IPs):**
   ```bash
   tailscale status | awk '{print $2, $4, $5, $6, $7}'
   ```

   Parse the output and report:
   - Online nodes (no "offline" marker)
   - Offline nodes with last-seen duration
   - Flag any node offline > 60 days as STALE (per `pmoves/docs/TAILSCALE_NODE_HYGIENE.md`)

2. **RustDesk relay health (via Tailscale hostname):**
   ```bash
   # Test hbbs rendezvous port via Tailscale hostname
   timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21116' 2>&1 && echo "hbbs: REACHABLE" || echo "hbbs: UNREACHABLE"

   # Test hbbr relay port
   timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21117' 2>&1 && echo "hbbr: REACHABLE" || echo "hbbr: UNREACHABLE"
   ```

3. **Local RustDesk client check:**
   ```bash
   # Windows
   tasklist 2>/dev/null | grep -i rustdesk && echo "RustDesk: RUNNING" || echo "RustDesk: NOT RUNNING"

   # Check config exists
   [ -f "$APPDATA/RustDesk/config/RustDesk2.toml" ] && echo "Config: found" || echo "Config: MISSING"
   ```

4. **Store snapshot in Cipher (if available):**
   ```bash
   curl -sf --max-time 3 http://localhost:8096/health > /dev/null 2>&1 && \
     curl -s -X POST http://localhost:8096/api/memory \
       -H "Content-Type: application/json" \
       -d "{\"content\": \"Fleet status snapshot: $(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"category\": \"agent_checkpoint\", \"source\": \"fleet-status\"}" \
     || true
   ```

5. **Report to user:**
   - Table of nodes: hostname, OS, status (online/offline/stale)
   - RustDesk relay: reachable/unreachable
   - Local RustDesk: running/not running + config status
   - Actionable recommendations (start RustDesk, clean stale nodes, etc.)

## Security

- **NEVER** output raw Tailscale IPs (100.x.x.x) — use hostnames only
- The topology leakage hook will block commands containing real IPs
- Use `tailscale status` hostname column, not the IP column
- RustDesk server key must never appear in output — reference only as "configured" or "missing"

## Known Road

```
make -C pmoves fleet-status
```

## Related

- `/fleet:rustdesk-check` — Deep RustDesk diagnostics
- `/fleet:stale-nodes` — Clean up stale Tailscale nodes
- `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md` — Full runbook
- `pmoves/docs/TAILSCALE_NODE_HYGIENE.md` — Stale node criteria
