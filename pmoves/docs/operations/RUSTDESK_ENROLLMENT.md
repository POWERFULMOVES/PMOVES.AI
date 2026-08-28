# RustDesk enrollment — add a node like Tailscale

The self-hosted RustDesk server (KVM2, `hbbs`/`hbbr`) is the transport layer; see
`RUSTDESK_SELF_HOSTED.md` for server ops and `FLEET_REMOTE_ACCESS_RUNBOOK.md` for the
4-layer model. This doc covers **Layer 3 — enrollment**: onboarding a node in one
command, the RustDesk analogue of `tailscale up --authkey`.

Enrollment is two halves:

| Half | Tool | What it does |
|------|------|--------------|
| **Issue** | `fleet:enroll` → `pmoves/scripts/fleet/generate-enrollment.py` | Mints a CHIT-signed, TTL-bounded `fleet.enrollment.v1` token (role-scoped) + a QR PNG. Already existed. |
| **Apply** | `pmoves/scripts/fleet/rustdesk-enroll.sh` / `.ps1` | Writes the proven `RustDesk2.toml` and restarts the client on the node. **New — this closes the gap.** |

Before this, "apply" existed only for Jetsons (`restart-jetson-rustdesk.sh`). Now every
platform has a one-command apply.

## Owner fleet nodes (the common case)

You already have the server host + key, so skip the token and pass them directly.

Retrieve the server values (from any Tailscale-enrolled box):
```bash
HOST=pmoves-kvm2                                              # Tailscale hostname (fleet)
KEY=$(ssh root@pmoves-kvm2 "cat /root/id_ed25519.pub")       # server public key
```

**Linux / macOS node** (run on the node; use sudo if RustDesk runs as a systemd service):
```bash
pmoves/scripts/fleet/rustdesk-enroll.sh --host "$HOST" --key "$KEY" --dry-run   # preview
pmoves/scripts/fleet/rustdesk-enroll.sh --host "$HOST" --key "$KEY"             # apply
```

**Windows node** (Z890 / 5090 / 4090 — e.g. after a reinstall):
```powershell
powershell -ExecutionPolicy Bypass -File pmoves\scripts\fleet\rustdesk-enroll.ps1 `
  -RdHost pmoves-kvm2 -Key <server_pubkey>
```

**A remote Linux node over SSH** (generalizes the Jetson flow):
```bash
pmoves/scripts/fleet/rustdesk-enroll.sh --host "$HOST" --key "$KEY" --remote pmovesnvme@<lan-ip>
```

## Partner / guest devices (time-bounded, QR)

Use the issuance half for a TTL-scoped token, then apply from it:
```bash
# Issue (needs CHIT_PASSPHRASE + RUSTDESK_RELAY_HOST + RUSTDESK_PUBLIC_KEY):
/fleet:enroll ROLE=partner DEVICE="Partner-Laptop-1" TTL=24h        # → token JSON + QR

# Apply on a desktop from the emitted token:
pmoves/scripts/fleet/rustdesk-enroll.sh --token enrollment.json
```
Mobile devices still scan the QR (RustDesk → Settings → ID/Relay Server → Import Server
Config). The apply scripts warn if a token is past its `expires_at` but still apply
(re-issue for a clean audit trail).

## Verify

Server-side registration confirms the node enrolled:
```bash
/fleet:rustdesk-check                                        # deep diagnostics
# or on the server:
ssh root@pmoves-kvm2 "journalctl -u hbbs --since '1 min ago' | grep update_pk"
```

## Notes

- Both scripts write the **same** `RustDesk2.toml` shape that `restart-jetson-rustdesk.sh`
  proved (rendezvous `:21116`, `custom-rendezvous-server`, `key`, `relay-server`,
  `use-permanent-password`). Config only — they never expose the server key in git.
- Fleet nodes use the **Tailscale hostname** (`pmoves-kvm2`) as ID server (resolves on
  the tailnet, inherits Tailscale ACLs = Layer 1). External/non-tailnet devices use the
  KVM public IP.
- The server key is a shared secret — distribute via SSH/Cipher, never commit it. QR PNGs
  are gitignored.
- Server activation / relay `-r` flag issues: `RUSTDESK_SELF_HOSTED.md` +
  `pmoves/scripts/claws/fix-kvm2-rustdesk-relay.sh`.

## References
- `pmoves/docs/operations/RUSTDESK_SELF_HOSTED.md` — server ops (KVM2 hbbs/hbbr)
- `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md` — 4-layer remote-access model
- `pmoves/scripts/fleet/generate-enrollment.py` — CHIT-signed token issuance
- `pmoves/scripts/claws/restart-jetson-rustdesk.sh` — Jetson-specific precedent this generalizes
- `.claude/commands/fleet/enroll.md`, `.claude/commands/fleet/rustdesk-check.md`
