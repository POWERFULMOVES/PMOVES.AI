Generate a CHIT-signed enrollment token for a new fleet device.

## Usage

Run this command to:
- Enroll a new phone, tablet, laptop, or partner device
- Generate time-limited, role-based access tokens
- Create QR codes for mobile device enrollment

## Arguments

- `ROLE` — Required. One of: `owner`, `unfcu`, `guest`
- `DEVICE` — Required. Device name (e.g., "Pixel 10", "UNFCU-Laptop-1")
- `TTL` — Optional. Token lifetime (default: `5m` for owner, `24h` for unfcu, `1h` for guest)

## Roles

| Role | Tailscale Tag | Allowed Nodes | Allowed Ports |
|------|--------------|--------------|--------------|
| `owner` | `tag:pmoves` | All | All |
| `unfcu` | `tag:unfcu` | See ACL policy | See ACL policy |
| `guest` | `tag:guest` | See ACL policy | See ACL policy |

## Implementation

### Step 1: Verify prerequisites

```bash
# Check CHIT_PASSPHRASE is available (do NOT print it)
[ -n "$CHIT_PASSPHRASE" ] && echo "CHIT_PASSPHRASE: set" || echo "ERROR: CHIT_PASSPHRASE not set — run: make -C pmoves secrets-funnel"

# Check enrollment script exists
[ -f "pmoves/scripts/fleet/generate-enrollment.py" ] && echo "Enrollment script: found" || echo "ERROR: Enrollment script missing"
```

### Step 2: Generate enrollment token

```bash
RUSTDESK_RELAY_HOST=$(tailscale ip -4 pmoves-kvm2 2>/dev/null || echo "UNKNOWN") \
RUSTDESK_PUBLIC_KEY="${RUSTDESK_PUBLIC_KEY}" \
CHIT_PASSPHRASE="${CHIT_PASSPHRASE}" \
  python pmoves/scripts/fleet/generate-enrollment.py generate \
    --role <ROLE> \
    --ttl <TTL> \
    --device "<DEVICE>"
```

**NOTE:** The script generates a QR code PNG at `pmoves/docs/operations/rustdesk-kvm2-qr.png` (gitignored).

### Step 3: Guide user

For mobile devices:
1. Open RustDesk app → Settings → ID/Relay Server
2. Tap Import Server Config (QR icon)
3. Scan the generated QR code

For desktop devices:
1. Open RustDesk → Settings → Network
2. Set ID Server from enrollment output
3. Set Key from enrollment output
4. Leave Relay Server blank (auto-relayed via `-r` flag)

### Step 4: Verify registration

After device scans QR / enters config:
```bash
# Check KVM2 server logs for registration (via SSH through Tailscale)
# The fleet-audit-watcher on KVM2 logs registrations to /var/log/pmoves/fleet-audit.jsonl
```

## Security

- Enrollment tokens are CHIT-signed (HMAC-SHA256) with TTL expiry
- Expired tokens fail validation even if HMAC is correct (fail-closed)
- NEVER commit QR codes or tokens to git (gitignored)
- NEVER output CHIT_PASSPHRASE or RUSTDESK_PUBLIC_KEY values
- Token generation is logged to local ledger (`fleet/.enrollment-ledger.jsonl`, gitignored)

## Known Road

```
make -C pmoves fleet-enroll ROLE=owner DEVICE="Device Name"
```

## Related

- `/fleet:status` — Check current fleet state before enrolling
- `/fleet:rustdesk-check` — Verify relay is healthy before enrolling
- `pmoves/scripts/fleet/generate-enrollment.py` — Enrollment script
- `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md` — Full runbook
