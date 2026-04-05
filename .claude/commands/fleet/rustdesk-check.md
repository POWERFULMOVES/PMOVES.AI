Deep RustDesk diagnostics: relay health, client configs, node visibility.

## Usage

Run this command when:
- Nodes can't see each other in RustDesk
- RustDesk connections are dropping or failing
- After relay restart to verify recovery
- Before enrolling new devices

## Arguments

- `--relay-only` — Only check KVM2 relay, skip client checks
- `--client-only` — Only check local client, skip relay
- No args — Full check (relay + client + visibility)

## Implementation

### Step 1: KVM2 Relay Health

Check relay service status via Tailscale hostname (NEVER raw IP):

```bash
# Port connectivity
timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21115' 2>&1 && echo "21115 (hbbs TCP): OK" || echo "21115: FAIL"
timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21116' 2>&1 && echo "21116 (hbbs rendezvous): OK" || echo "21116: FAIL"
timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21117' 2>&1 && echo "21117 (hbbr relay): OK" || echo "21117: FAIL"
timeout 3 bash -c 'echo "" > /dev/tcp/pmoves-kvm2/21118' 2>&1 && echo "21118 (hbbs WS): OK" || echo "21118: FAIL"
```

If relay is unreachable, suggest: `/fleet:fix-relay`

### Step 2: Local RustDesk Client

```bash
# Is RustDesk running?
tasklist 2>/dev/null | grep -i rustdesk || echo "WARNING: RustDesk is NOT running on this machine"

# Config file
CONFIG="$APPDATA/RustDesk/config/RustDesk2.toml"
if [ -f "$CONFIG" ]; then
  echo "Config found at: $CONFIG"
  # Check server is configured (show status, not values — NEVER output keys or IPs)
  grep -q "rendezvous_server" "$CONFIG" && echo "  rendezvous_server: configured" || echo "  rendezvous_server: MISSING"
  grep -q "custom-rendezvous-server" "$CONFIG" && echo "  custom-rendezvous-server: configured" || echo "  custom-rendezvous-server: MISSING"
  grep -q "key" "$CONFIG" && echo "  key: configured" || echo "  key: MISSING"
  grep -q "relay-server" "$CONFIG" && echo "  relay-server: configured" || echo "  relay-server: MISSING"
else
  echo "ERROR: No RustDesk config found at $CONFIG"
  echo "  -> RustDesk may not be installed, or needs initial configuration"
fi
```

### Step 3: Node Visibility Report

Cross-reference Tailscale online nodes with RustDesk registration table:

```bash
# Get online Tailscale nodes (hostnames only)
tailscale status | awk '!/offline/' | awk '{print $2}'
```

Compare against registered nodes in `pmoves/docs/operations/RUSTDESK_SELF_HOSTED.md` (Fleet Registration Status table):
- Z890: Registered, Verified bidirectional
- 5090: Registered, Verified bidirectional
- 4090 Laptop: Registered, Verified bidirectional
- Jetson #1: Registered, Via relay (stabilizing)
- Jetson #2: Registered, Via relay (stabilizing)
- Phone: QR code pending
- Tablet: QR code pending

### Step 4: Report

Output a table:

| Node | Tailscale | RustDesk Config | RustDesk Running | Notes |
|------|-----------|-----------------|------------------|-------|
| (hostname) | online/offline | yes/no/unknown | yes/no/unknown | (actionable note) |

Include actionable recommendations:
- "Start RustDesk on Z890" if not running
- "Run /fleet:fix-relay" if relay unreachable
- "Configure RustDesk client" if config missing
- "Enroll via /fleet:enroll" for unregistered devices (phone, tablet)

## Security

- NEVER output raw Tailscale IPs, RustDesk server key, or SSH credentials
- Config checks report "configured" / "MISSING" — not actual values
- Use Tailscale hostnames for all connectivity checks

## Known Road

```
make -C pmoves fleet-status     # Quick overview
/fleet:fix-relay                # If relay is down
```

## Related

- `/fleet:status` — Quick fleet overview
- `/fleet:fix-relay` — Fix KVM2 relay configuration
- `/fleet:enroll` — Enroll new devices
- `pmoves/docs/operations/RUSTDESK_SELF_HOSTED.md` — Server architecture
- `pmoves/scripts/claws/fix-kvm2-rustdesk-relay.sh` — Relay fix script
