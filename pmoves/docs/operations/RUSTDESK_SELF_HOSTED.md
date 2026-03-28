# RustDesk Self-Hosted Relay — KVM2

> Remote desktop access for the PMOVES fleet via self-hosted RustDesk server.
>
> Last updated: 2026-03-28

Canonical operator runbook: `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md`

---

## Server Architecture

**Host:** KVM2 (<KVM2_IP>) — Hostinger VPS, 4C/8GB, Ubuntu
**Transport:** Bare-metal systemd services (not Docker)

| Service | Unit | Port(s) | Purpose |
|---------|------|---------|---------|
| hbbs | `hbbs.service` | 21115, 21116, 21118 | Rendezvous (ID registration + NAT traversal + WebSocket) |
| hbbr | `hbbr.service` | 21117, 21119 | Relay (encrypted traffic forwarding + QUIC) |

**Key:** `<RUSTDESK_KEY>`

### hbbs Configuration

The hbbs service MUST include the `-r` relay flag pointing to the server's own public IP:

```
ExecStart=/opt/rustdesk-server/hbbs -r <KVM2_IP>
```

Without `-r`, clients behind NAT will fail to relay through the server.

### Firewall (UFW)

```
22/tcp    SSH (key-only)
21115/tcp hbbs
21116/tcp hbbs
21117/tcp hbbr
21118/tcp hbbs (WebSocket)
21119/tcp hbbr (QUIC)
```

All other ports are denied by default.

---

## Fleet Registration Status

| Node | Config Method | Registered | Verified |
|------|--------------|------------|----------|
| Z890 | RustDesk GUI | Yes | Bidirectional with 5090+4090 |
| 5090 | RustDesk GUI | Yes | Bidirectional |
| 4090 Laptop | RustDesk GUI | Yes | Bidirectional |
| Jetson #1 | `restart-jetson-rustdesk.sh` | Yes | Via relay (stabilizing) |
| Jetson #2 | `restart-jetson-rustdesk.sh` | Yes | Via relay (stabilizing) |
| Phone (Pixel) | QR code pending | No | — |
| Tablet (S8 Ultra) | QR code pending | No | — |

---

## Client Configuration

### Windows / macOS / Linux Desktop

1. Open RustDesk → Settings → Network
2. Set **ID Server:** `<KVM2_IP>`
3. Set **Key:** `<RUSTDESK_KEY>`
4. Leave Relay Server blank (server auto-relays via `-r` flag)

### Jetson (Linux, systemd service)

RustDesk runs as a systemd service under root on Jetsons. Config must be written to BOTH:
- `/root/.config/rustdesk/RustDesk2.toml` (root service reads this)
- `/home/pmovesnvme/.config/rustdesk/RustDesk2.toml` (user session)

Use `restart-jetson-rustdesk.sh` to deploy config to both paths:

```bash
bash pmoves/scripts/claws/restart-jetson-rustdesk.sh
```

This script:
1. Writes `RustDesk2.toml` with KVM2 as rendezvous + relay server
2. Copies to both root and user config paths
3. Injects the `pmoves-claw` SSH key into root's authorized_keys
4. Restarts the RustDesk service
5. Verifies KVM2 registration via `update_pk` in server logs

### Android / iOS (Mobile)

1. Open RustDesk app → Settings (gear icon) → ID/Relay Server
2. Tap **Import Server Config** (QR icon)
3. Scan the QR code (generated locally, NOT committed to repo — gitignored)

To regenerate the QR locally:
```bash
python -c "
import qrcode, json
config = json.dumps({'host':'<KVM2_IP>','key':'<RUSTDESK_KEY>','api':'','relay':'<KVM2_IP>'}, separators=(',',':'))
qrcode.make(config).save('pmoves/docs/operations/rustdesk-kvm2-qr.png')
"
```

**Manual fallback** (if QR not available):
- Open RustDesk → Settings → ID/Relay Server
- Set **ID Server**, **Relay Server**, and **Key** from the values in KVM2 server config

---

## Scripts

| Script | Location | Purpose |
|--------|----------|---------|
| `fix-kvm2-rustdesk-relay.sh` | `pmoves/scripts/claws/` | Add `-r` relay flag to KVM2 hbbs and restart |
| `restart-jetson-rustdesk.sh` | `pmoves/scripts/claws/` | Full Jetson config deploy (root+user, SSH key, verify) |
| `generate-enrollment.py` | `pmoves/scripts/fleet/` | Time-limited, role-based enrollment QR + token generation |
| `fleet-audit-watcher.sh` | `pmoves/scripts/fleet/` | KVM2 journal watcher → NATS event publisher |
| `fleet-audit-watcher.service` | `pmoves/scripts/fleet/` | systemd unit file for the watcher |

Claws scripts SSH via key at `$LOCALAPPDATA/Temp/hostinger_vps`.

---

## Enrollment System

### Generating Enrollment Tokens

```bash
# Owner device (full access, 5-minute window)
RUSTDESK_RELAY_HOST=<KVM2_IP> RUSTDESK_PUBLIC_KEY=<KEY> CHIT_PASSPHRASE=<secret> \
  python pmoves/scripts/fleet/generate-enrollment.py generate --role owner --ttl 5m --device "Pixel 10"

# UNFCU partner (limited access, 24-hour window)
... generate --role unfcu --ttl 24h --device "UNFCU-Laptop-1"

# Guest demo (Agent Zero UI only, 1-hour window)
... generate --role guest --ttl 1h
```

### Roles

| Role | Tailscale Tag | Allowed Nodes | Allowed Ports |
|------|--------------|--------------|--------------|
| `owner` | `tag:pmoves` | All | All |
| `unfcu` | `tag:unfcu` | 5090, Z890 | 3030, 8080, 8081 |
| `guest` | `tag:guest` | Z890 | 8081 |

### Security Layers

```
Layer 1: Tailscale ACL (network) — tag-based port access control
Layer 2: RustDesk key (transport) — only fleet members connect
Layer 3: Per-client password (session) — device-to-device auth
Layer 4: Audit trail (NATS) — all events logged
```

- Enrollment tokens are CHIT-signed (HMAC-SHA256) with TTL expiry
- Expired tokens fail validation even if HMAC is correct (fail-closed)
- Tokens are logged to local ledger (`fleet/.enrollment-ledger.jsonl`, gitignored)

### Verifying Tokens

```bash
CHIT_PASSPHRASE=<secret> python pmoves/scripts/fleet/generate-enrollment.py verify '<token-json>'
```

### NATS Subjects

| Subject | Publisher | Purpose |
|---------|-----------|---------|
| `fleet.device.registered.v1` | fleet-audit-watcher | New RustDesk client registered |
| `fleet.device.approved.v1` | admin | Device approved |
| `fleet.device.blocked.v1` | admin | Device blocked |
| `fleet.enrollment.created.v1` | generate-enrollment.py | Token generated |
| `fleet.audit.connection.v1` | fleet-audit-watcher | Connection/disconnection events |
| `fleet.audit.heartbeat.v1` | fleet-audit-watcher | Watcher liveness (every 5m) |

### Installing the Audit Watcher on KVM2

```bash
ssh root@<KVM2_IP> "curl -fsSL -o /tmp/nats-amd64.deb \
  https://github.com/nats-io/natscli/releases/download/v0.3.2/nats-0.3.2-amd64.deb && \
  dpkg -i /tmp/nats-amd64.deb"
scp pmoves/scripts/fleet/fleet-audit-watcher.sh root@<KVM2_IP>:/opt/pmoves/
scp pmoves/scripts/fleet/fleet-audit-watcher.service root@<KVM2_IP>:/etc/systemd/system/
ssh root@<KVM2_IP> "mkdir -p /opt/pmoves /var/log/pmoves && \
  chmod +x /opt/pmoves/fleet-audit-watcher.sh && \
  systemctl daemon-reload && systemctl enable --now fleet-audit-watcher"
```

Requires: `nats` CLI installed on KVM2 for NATS publishing.

Operational notes:
- Create `/var/log/pmoves` before starting the service. The systemd unit uses `ReadWritePaths=/var/log/pmoves`, and the service will fail early if the directory does not exist.
- Set `Environment=NATS_URL=...` in `fleet-audit-watcher.service` to a broker reachable from KVM2.
- The repo default NATS config binds port `4222` to localhost only, so the watcher cannot publish remotely until one PMOVES node exposes NATS on a Tailscale-reachable interface.
- Local audit logging still works even when NATS is not reachable; inspect `/var/log/pmoves/fleet-audit.jsonl`.

---

## Troubleshooting

### Connection drops / intermittent

1. Verify relay flag is set: `ssh root@<KVM2_IP> "grep ExecStart /etc/systemd/system/hbbs.service"`
   - Must show `-r <KVM2_IP>`
2. Check server logs: `ssh root@<KVM2_IP> "journalctl -u hbbs -n 20 --no-pager"`
3. On Jetson: verify root config has correct server: `sudo cat /root/.config/rustdesk/RustDesk2.toml`

### Client not registering

1. Check `update_pk` entries in hbbs logs (indicates client registration)
2. Verify UFW allows ports 21115-21119
3. Ensure client key matches server key exactly

### Relay vs Direct

- **Direct:** Both peers on same LAN with no NAT → fastest, no relay
- **Relay:** At least one peer behind NAT → routed through KVM2 hbbr
- Relay mode is expected for Jetsons and mobile devices

---

## Architecture Decision

**Why self-hosted?**
- Full control over relay infrastructure
- No dependency on public RustDesk servers
- Key pinning prevents unauthorized connections
- Consistent with PMOVES principle: self-host everything, trust nothing external

**Why bare-metal (not Docker)?**
- KVM2 is a lightweight exit node — Docker overhead not justified
- systemd services are simpler to manage on a VPS
- Direct network access without Docker bridge complexity
