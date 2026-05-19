# RustDesk Production Self-Host Review

> Comprehensive assessment of the PMOVES self-hosted RustDesk relay deployment on KVM2.
>
> Review date: 2026-05-17
> Reviewer: Agent Zero Researcher
> Sources: 8 project documentation files + agent memory

---

## 1. Architecture Overview

### 1.1 Deployment Model

| Attribute | Value | Confidence |
|-----------|-------|------------|
| Host | KVM2 (Hostinger VPS, US-East DC id=13) | DOC-CONFIRMED |
| Specs | 4 vCPU / 8 GB RAM | DOC-CONFIRMED |
| Cost | $10/mo | DOC-CONFIRMED |
| Transport | Bare-metal systemd (not Docker) | DOC-CONFIRMED |
| OS | Ubuntu 22.04 | DOC-CONFIRMED |
| Activation | Active since 2026-05-16 (re-activated; paused 2026-04-04 for Tailscale-direct experiment) | DOC-CONFIRMED |
| Initial deploy | 2026-03-28 | DOC-CONFIRMED |

### 1.2 Service Architecture

| Service | systemd Unit | Port(s) | Purpose |
|---------|--------------|---------|---------|
| hbbs | `hbbs.service` | 21115 (TCP), 21116 (TCP), 21118 (TCP/WS) | Rendezvous: ID registration, NAT traversal, WebSocket |
| hbbr | `hbbr.service` | 21117 (TCP), 21119 (UDP/QUIC) | Relay: encrypted traffic forwarding |

hbbs MUST include `-r <KVM2_PUBLIC_IP>` to advertise the relay address to clients behind NAT. Without this flag, NAT-traversed clients cannot relay through the server. [DOC-CONFIRMED]

### 1.3 Firewall (UFW)

| Port | Protocol | Service | Confidence |
|------|----------|---------|------------|
| 22/tcp | TCP | SSH (key-only) | DOC-CONFIRMED |
| 21115/tcp | TCP | hbbs | DOC-CONFIRMED |
| 21116/tcp | TCP | hbbs | DOC-CONFIRMED |
| 21117/tcp | TCP | hbbr | DOC-CONFIRMED |
| 21118/tcp | TCP | hbbs (WebSocket) | DOC-CONFIRMED |
| 21119/tcp | UDP | hbbr (QUIC) | DOC-CONFIRMED |

All other ports denied by default. [DOC-CONFIRMED]

### 1.4 RustDesk in the PMOVES Remote Access Stack

The PMOVES fleet uses a layered remote access model. RustDesk is explicitly the transport and operator-UX layer, not the authorization boundary:

| Layer | System | Role | When Used |
|-------|--------|------|-----------|
| 1 (Enforcement) | Tailscale ACLs + tags | Network-level access control | All remote access inherits this |
| 2 (Transport) | RustDesk hbbs/hbbr | Remote desktop GUI path | When graphical access needed |
| 3 (Issuance) | CHIT-signed enrollment | Time-bounded onboarding | Partner/guest device enrollment |
| 4 (Continuity) | Cipher Memory + AGNOTE4482 | Audit trail + drift prevention | Cross-session infra work |

**Decision matrix: RustDesk vs Tailscale SSH:**

| Scenario | Tool | Rationale |
|----------|------|----------|
| CLI shell access to node | Tailscale SSH | Lower latency, no relay hop, scriptable |
| GUI desktop access to Jetson | RustDesk | Only option for graphical interface on headless edge nodes |
| GUI desktop access to Windows (Z890, 5090, 4090) | RustDesk | Full desktop remoting with clipboard, file transfer |
| Emergency recovery when Tailscale down | RustDesk | Independent transport — does not depend on tailnet |
| Partner/guest demo access | RustDesk + CHIT enrollment | Time-bounded, role-scoped GUI access |

---

## 2. Security Assessment

### 2.1 Authentication Model

RustDesk uses its own Ed25519 keypair for server authentication:

| Aspect | Detail | Confidence |
|--------|--------|------------|
| Server key location | `/root/id_ed25519.pub` on KVM2 | DOC-CONFIRMED |
| Key distribution | Retrieved via `ssh root@pmoves-kvm2 "cat /root/id_ed25519.pub"` | DOC-CONFIRMED |
| Client config | Key entered in RustDesk Settings → Network → Key field | DOC-CONFIRMED |
| Key storage on clients | `RustDesk2.toml` under `key = '...'` | SCRIPT-INFERRED |

Clients verify the server by comparing the server's presented key against the configured key. If keys mismatch, connection is refused. [DOC-CONFIRMED]

### 2.2 Encryption

| Aspect | Detail | Confidence |
|--------|--------|------------|
| Relay traffic encryption | E2E encrypted via RustDesk's built-in key exchange | SCRIPT-INFERRED (standard RustDesk behavior, not explicitly documented in PMOVES docs) |
| Key protection | The server's Ed25519 key authenticates the relay; session keys are negotiated per-connection | SCRIPT-INFERRED |
| QUIC (port 21119) | Uses TLS 1.3 internally | SCRIPT-INFERRED (QUIC spec requirement) |

### 2.3 Security Layers (Documented)

The ops doc describes a 4-layer security model:

```
Layer 1: Tailscale ACL (network) — tag-based port access control
Layer 2: RustDesk key (transport) — only fleet members connect
Layer 3: Per-client password (session) — device-to-device auth
Layer 4: Audit trail (NATS) — all events logged
```

[DOC-CONFIRMED]

### 2.4 Identified Security Weaknesses

| Finding | Severity | Confidence | Detail |
|---------|----------|------------|--------|
| Jetson `verification-method = 'use-permanent-password'` | **High** | SCRIPT-INFERRED | Weakens the key-only model. Permanent passwords can be brute-forced, phished, or leaked. The key pair should be the sole authentication factor. |
| Jetson `allow-remote-config-modification = 'Y'` | **High** | SCRIPT-INFERRED | Allows any authenticated client to modify the RustDesk config on the Jetson. An attacker who obtains a session could change the relay server or key, redirecting future connections. |
| KVM2 SSH blocked 45+ days | **Critical** | DOC-CONFIRMED + memory | Cannot manage, update, or audit the RustDesk server. The relay key cannot be rotated. No incident response possible without Hostinger VNC console access. |
| No RustDesk version documented | **Medium** | UNKNOWN | Cannot assess CVE exposure without knowing the deployed server version. No update procedure documented. |
| Interactive sudo password in Jetson script | **Medium** | SCRIPT-INFERRED | `restart-jetson-rustdesk.sh` prompts for sudo password interactively — cannot be automated safely, password may be logged in shell history. |
| Enrollment QR contains key in plaintext JSON | **Low** | SCRIPT-INFERRED | The QR code encodes `{'host':ip,'key':key,...}` as JSON. Anyone who photographs the QR can extract the server key. QR is gitignored but physical security of the image is not addressed. |

### 2.5 Public Relay vs Self-Hosted Relay

| Factor | Public RustDesk Relay | PMOVES Self-Hosted (KVM2) |
|--------|----------------------|---------------------------|
| Attack surface | Shared infrastructure, unknown co-tenants | Private VPS, only PMOVES fleet connects |
| Key control | Trusts RustDesk project's key management | Full control of `/root/id_ed25519` |
| Traffic visibility | Zero visibility into relay traffic | Can inspect journalctl logs for connections |
| Availability | RustDesk project's uptime | PMOVES's KVM2 uptime (currently healthy but SPOF) |
| Bandwidth limits | Potentially throttled at high usage | Limited by KVM2's VPS bandwidth cap |

Self-hosting is the correct choice for PMOVES. [DOC-CONFIRMED — docs explicitly state this rationale]

---

## 3. Fleet Registration Status

### 3.1 Current Registration Table

| Node | Config Method | Registered | Verified | Confidence |
|------|--------------|------------|----------|------------|
| Z890 | RustDesk GUI | Yes | Bidirectional with 5090+4090 | DOC-CONFIRMED |
| 5090 (POWERFULMOVES) | RustDesk GUI | Yes | Bidirectional | DOC-CONFIRMED |
| 4090 Laptop | RustDesk GUI | Yes | Bidirectional | DOC-CONFIRMED |
| Jetson Orin #1 | `restart-jetson-rustdesk.sh` | Yes | Via relay (stabilizing) | DOC-CONFIRMED |
| Jetson Orin #2 | `restart-jetson-rustdesk.sh` | Yes | Via relay (stabilizing) | DOC-CONFIRMED |
| Pixel 10 Pro XL | QR code | **No** | Pending | DOC-CONFIRMED |
| Galaxy S8 Ultra | QR code | **No** | Pending | DOC-CONFIRMED |

### 3.2 Jetson Config Deployment Details

The `restart-jetson-rustdesk.sh` script performs the following operations on each Jetson: [SCRIPT-INFERRED]

| Step | Action | Detail |
|------|--------|--------|
| 1 | Write temp config | `RustDesk2.toml` written to `/tmp/` as unprivileged user |
| 2 | Stop service | `systemctl stop rustdesk` via sudo |
| 3 | Deploy root config | Copy to `/root/.config/rustdesk/RustDesk2.toml` |
| 4 | Deploy user config | Copy to `/home/pmovesnvme/.config/rustdesk/RustDesk2.toml` + chown |
| 5 | Inject SSH key | Append `pmoves-claw` ed25519 pubkey to `/root/.ssh/authorized_keys` (idempotent via grep) |
| 6 | Start service | `systemctl start rustdesk` |
| 7 | Verify | grep rendezvous from root config + check KVM2 hbbs logs for `update_pk` after 10s delay |

### 3.3 Stale or Problematic Registrations

| Node | Issue | Confidence |
|------|-------|------------|
| Jetson #2 | Tailscale not yet active (pending Phase B reflash) — can only reach via LAN IP, not tailnet | DOC-CONFIRMED |
| Jetson #1 | Tailscale hostname rename pending (`pmoves-nano` → `pmoves-nemotron-1`) | DOC-CONFIRMED |
| All nodes | Cannot verify live registration health — KVM2 SSH blocked, no API to query registered peers | UNKNOWN |

---

## 4. Reliability & Performance

### 4.1 Single Point of Failure Analysis

| Component | SPOF? | Impact if Down | Mitigation Present |
|-----------|-------|----------------|-------------------|
| KVM2 hbbs | **Yes** | No new connections, no ID resolution, no NAT traversal | None |
| KVM2 hbbr | **Yes** | No relay for NAT-traversed clients | None |
| KVM2 entire host | **Yes** | Complete loss of remote desktop for all fleet nodes | None |

There is no HA/failover for the RustDesk relay. If KVM2 goes down, all remote desktop access is lost until the VPS is restored. Tailscale SSH remains available as a CLI fallback for nodes on the tailnet, but GUI access is fully dependent on KVM2. [DOC-CONFIRMED]

### 4.2 Latency Assessment

| Path | Route | Latency Impact |
|------|-------|----------------|
| LAN node → LAN node (same subnet) | Should negotiate direct P2P | Minimal — RustDesk attempts direct connection before relaying |
| LAN node → LAN node (cross-subnet / NAT) | Via KVM2 relay (US-East) | ~20-50ms RTT added for relay hop |
| External client → LAN node | Via KVM2 relay | Dependent on client location to US-East |

RustDesk supports direct P2P connection when both peers are on the same subnet and can reach each other without NAT traversal. In this case, traffic does not go through the relay. [SCRIPT-INFERRED — standard RustDesk behavior, not explicitly tested in docs]

### 4.3 Resource Contention on KVM2

KVM2 (4C/8GB) runs multiple services simultaneously: [DOC-CONFIRMED]

| Service | Resource Demand | Notes |
|---------|----------------|-------|
| nginx (SSL termination) | Low-Medium | Handles reverse proxy for public endpoints |
| cloudflared | Low | Cloudflare tunnel (if active) |
| RustDesk hbbs | Low | Signaling server, minimal CPU/RAM |
| RustDesk hbbr | **Medium-High** | Relay traffic — CPU scales with concurrent sessions, RAM for connection buffers |
| fleet-audit-watcher | Negligible | Journal watcher + NATS publish |

Under concurrent RustDesk sessions (e.g., two operators remoting into Jetsons simultaneously), hbbr CPU usage becomes non-trivial on a 4-core VPS. No resource limits or cgroups are documented. [SCRIPT-INFERRED]

### 4.4 Bandwidth and Session Limits

| Parameter | Documented Value | Confidence |
|-----------|-----------------|------------|
| Max concurrent relay sessions | Not documented | UNKNOWN |
| Per-session bandwidth cap | Not documented | UNKNOWN |
| VPS total bandwidth cap | Not documented (Hostinger plan default) | UNKNOWN |
| QUIC vs TCP preference | Both available (21117 TCP, 21119 UDP) | DOC-CONFIRMED |

---

## 5. Operational Gaps

### 5.1 Gap Inventory

| # | Gap | Severity | Confidence | Detail |
|---|-----|----------|------------|--------|
| G1 | KVM2 SSH access blocked 45+ days | **Critical** | DOC-CONFIRMED | Console-injection PENDING — `pmoves-claw` deploy key never pasted via Hostinger VNC. Cannot SSH to manage hbbs/hbbr, rotate keys, update server, or respond to incidents. This is the fleet's single largest operational risk per agent memory. |
| G2 | No monitoring/alerting for hbbs/hbbr | **High** | DOC-CONFIRMED | No Prometheus metrics, no health check endpoint, no alerting. The only health signal is `fleet-status` probing ports 21116/21117 from Z890 — no automated detection of service crashes. |
| G3 | No automated restart/recovery | **High** | SCRIPT-INFERRED | If hbbs or hbbr crashes, they stay down until manual intervention. No systemd watchdog, no external health-checker restarter documented. |
| G4 | fleet-audit-watcher NATS publish blocked | **Medium** | DOC-CONFIRMED | Watcher exists and is designed to publish RustDesk events to NATS, but the target NATS broker is unreachable from KVM2. Only local evidence at `/var/log/pmoves/fleet-audit.jsonl` is available. |
| G5 | No logging aggregation | **Medium** | SCRIPT-INFERRED | hbbs/hbbr logs exist in journalctl on KVM2 but are not shipped to centralized logging (Loki on KVM4-2). No log retention policy documented. |
| G6 | No version management procedure | **Medium** | UNKNOWN | No documented RustDesk server version. No procedure for atomic updates of server + all fleet clients. Risk of version skew breaking connectivity. |
| G7 | Mobile enrollment incomplete | **Low** | DOC-CONFIRMED | Pixel 10 and S8 Ultra QR enrollment pending. QR generation script exists but has not been executed. |
| G8 | Jetson script not automatable | **Low** | SCRIPT-INFERRED | Interactive sudo password prompt prevents CI/CD integration. |

### 5.2 Impact of G1 (KVM2 SSH Blocked)

Since 2026-04-02 (~45 days), the following operations are impossible without Hostinger VNC console:

- Rotating the RustDesk server key (`/root/id_ed25519`)
- Updating hbbs/hbbr to a new version
- Inspecting journalctl logs for connection errors or anomalies
- Restarting services after crashes
- Modifying the `-r` relay flag if KVM2 public IP changes
- Deploying the `fleet-audit-watcher` or fixing its NATS connectivity
- Any incident response on the relay

The relay continues to function (confirmed healthy as of 2026-05-07 fleet probe), but the inability to manage it represents an uncontrolled risk surface. [DOC-CONFIRMED]

---

## 6. Integration with PMOVES Stack

### 6.1 RustDesk API Availability

| Question | Answer | Confidence |
|----------|--------|------------|
| Does RustDesk server expose a management API? | Not documented in PMOVES ops docs | UNKNOWN |
| Can sessions be launched programmatically? | Not documented | UNKNOWN |
| Is there a CLI for server management? | Not documented | UNKNOWN |

The open-source RustDesk server (hbbs/hbbr) has limited API surface compared to the RustDesk Pro server. The PMOVES deployment uses the open-source version. No programmatic session management capability is documented. [SCRIPT-INFERRED]

### 6.2 Agent Zero Integration

| Question | Answer | Confidence |
|----------|--------|------------|
| Can Agent Zero launch RustDesk sessions? | No documented integration | UNKNOWN |
| Can Agent Zero check RustDesk health? | Indirectly via `fleet-status` make target | DOC-CONFIRMED |
| Can Agent Zero deploy RustDesk config? | Via `restart-jetson-rustdesk.sh` for Jetsons only | DOC-CONFIRMED |

### 6.3 KVM2 Service Coexistence

| Service | Relationship to RustDesk | Risk |
|---------|------------------------|------|
| nginx (80/443) | Independent — different ports | Low |
| cloudflared | Independent — different ports | Low |
| fleet-audit-watcher | Depends on hbbs/hbbr logs via journalctl | Medium — if RustDesk logs rotate before watcher processes them, events are lost |

No documented port conflicts or resource contention beyond the general 4C/8GB constraint (see Section 4.3).

---

## 7. Comparison with Alternatives

### 7.1 Feature Comparison Matrix

| Feature | RustDesk (current) | Tailscale SSH | DWService | MeshCentral |
|---------|-------------------|--------------|-----------|-------------|
| GUI remote desktop | Yes | No | Yes | Yes |
| Self-hosted | Yes | Yes (relay) | No (cloud) | Yes |
| Free / open-source | Yes (AGPL) | Yes (free tier) | Freemium | Yes (Apache 2.0) |
| CLI/terminal access | No (GUI only) | Yes | Limited | Yes |
| File transfer | Yes (built-in) | Via scp/rsync | Yes | Yes |
| NAT traversal | Yes (relay) | Yes (DERP) | N/A (cloud) | Yes (relay) |
| Multi-user/session | Yes | Yes | Yes | Yes |
| Mobile client | Yes (Android/iOS) | Yes | Yes | Yes |
| Programmatic API | Limited (OSS) | Yes (API + SSH) | Yes | Yes |
| Audit logging | Manual (journalctl) | Admin API logs | Cloud-managed | Built-in |

### 7.2 Why RustDesk Was Chosen

1. GUI access required for Jetson edge nodes (no physical display) [DOC-CONFIRMED]
2. Self-hosted — no dependency on third-party relay infrastructure [DOC-CONFIRMED]
3. Free and open-source — fits PMOVES cost model ($0 software cost on existing $10/mo VPS) [DOC-CONFIRMED]
4. Works alongside Tailscale as transport layer (not replacement) [DOC-CONFIRMED]

### 7.3 Where Alternatives Would Be Better

| Scenario | Better Alternative | Why |
|----------|-------------------|-----|
| Need programmatic session management + API | MeshCentral | Rich REST API, built-in user management, command execution |
| Want single-tool remote access (CLI + GUI) | Tailscale SSH + RustDesk combo (current) | No single tool covers both well |
| Need enterprise-grade audit compliance | DWService (cloud) or MeshCentral | Centralized logging, user management, compliance features |
| Want zero-maintenance relay | Tailscale SSH only | DERP relays are managed by Tailscale; no self-hosted relay to maintain |

---

## 8. Actionable Next Steps

### P0 — Critical (Resolve Immediately)

| ID | Action | Rationale | Effort |
|----|--------|-----------|--------|
| R1 | Paste `pmoves-claw` deploy key into KVM2 via Hostinger VNC console | Unblocks all KVM2 management including RustDesk server updates, key rotation, log inspection, incident response. This is the fleet's largest operational risk. | 5 min (operator action) |
| R2 | Disable `allow-remote-config-modification` on Jetson RustDesk configs | Prevents authenticated clients from modifying relay server or key settings. Set to `N` in `RustDesk2.toml` and redeploy via `restart-jetson-rustdesk.sh`. | 15 min |
| R3 | Change Jetson `verification-method` from `use-permanent-password` to `use-key-only` or `use-both` (password as secondary) | Eliminates the permanent-password attack surface. Key-only is strongest; `use-both` adds a second factor if password rotation is implemented. | 15 min |

### P1 — High (This Sprint)

| ID | Action | Rationale | Effort |
|----|--------|-----------|--------|
| R4 | Add systemd watchdog to hbbs/hbbr services | Enables automatic restart on crash. Add `WatchdogSec=30` to both `.service` files and configure `ExecStart` to notify watchdog. | 30 min |
| R5 | Create simple health check script + cron on Z890 | 5-minute cron that probes KVM2 ports 21116/21117 and sends alert (e.g., `notify_user`) on failure. | 1 hr |
| R6 | Document current RustDesk server version | SSH to KVM2 (after R1), run `hbbs --version` and `hbbr --version`, record in ops doc. | 5 min (after R1) |
| R7 | Complete mobile QR enrollment for Pixel 10 and S8 Ultra | Run the documented QR generation script, scan with mobile RustDesk clients. | 15 min |
| R8 | Remove interactive sudo from `restart-jetson-rustdesk.sh` | Replace `read -s SUDO_PW` with SSH key-based sudo (NOPASSWD for specific commands) or use `ssh -t` with a pre-configured sudoers entry. | 1 hr |

### P2 — Medium (Next Sprint)

| ID | Action | Rationale | Effort |
|----|--------|-----------|--------|
| R9 | Ship hbbs/hbbr logs to Loki (KVM4-2) | Add journalctl → Loki pipeline (via promtail or Vector). Enables centralized log search and alerting on RustDesk events. | 2-3 hr |
| R10 | Fix fleet-audit-watcher NATS connectivity | Ensure the NATS broker on KVM4-2 is reachable from KVM2 over Tailscale. This unblocks the Layer 4 audit trail. | 1-2 hr |
| R11 | Evaluate HA relay options (or formally accept SPOF) | Options: (a) second relay on KVM4-1, (b) documented recovery runbook with RTO target, (c) accept SPOF with Tailscale SSH as CLI fallback. Document the decision. | 2-4 hr (analysis) |
| R12 | Create RustDesk server update procedure | Document steps for: download new version → stop services → replace binaries → restart → verify fleet re-registration → update Jetson configs if needed. | 1-2 hr |
| R13 | Investigate RustDesk Pro API for Agent Zero integration | Evaluate whether the Pro server's API surface justifies the license cost for programmatic session launching and health monitoring. | 2-3 hr (research) |

---

## Appendix A: Source References

| # | Source | Path |
|---|--------|------|
| S1 | RustDesk Self-Hosted Ops Doc | `pmoves/docs/operations/RUSTDESK_SELF_HOSTED.md` |
| S2 | Jetson RustDesk Deploy Script | `pmoves/scripts/claws/restart-jetson-rustdesk.sh` |
| S3 | KVM2 Relay Fix Script | `pmoves/scripts/claws/fix-kvm2-rustdesk-relay.sh` |
| S4 | Fleet Topology | `pmoves/docs/operations/TOPOLOGY.md` |
| S5 | Fleet Inventory Live | `pmoves/docs/operations/FLEET_INVENTORY_LIVE.md` |
| S6 | Remote Access Runbook | `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md` |
| S7 | Tailscale Companion Review | `research/TAILSCALE_PRODUCTION_SELFHOST_REVIEW.md` |
| S8 | Hostinger Companion Review | `research/HOSTINGER_VPS_PRODUCTION_SELFHOST_REVIEW.md` |
| S9 | Agent Memory — KVM2 SSH Status | `memory_load` (KVM2/KVM4-2 SSH blocked 45+ days) |

## Appendix B: Confidence Legend

| Marker | Meaning |
|--------|---------|
| DOC-CONFIRMED | Explicitly stated in project documentation or scripts |
| SCRIPT-INFERRED | Derived from script behavior, standard tool defaults, or architectural patterns not explicitly documented |
| UNKNOWN | Not documented and cannot be inferred from available sources; requires live verification |

## Appendix C: Enrollment Token Security Model

CHIT-signed enrollment tokens use HMAC-SHA256 with a passphrase and include TTL expiry: [DOC-CONFIRMED]

```
Token validation: HMAC correct AND TTL not expired → ALLOW
Token validation: HMAC correct BUT TTL expired → DENY (fail-closed)
Token validation: HMAC incorrect → DENY
```

Roles map to Tailscale tags for network enforcement:

| Role | Tailscale Tag | Allowed Nodes | Allowed Ports |
|------|--------------|--------------|--------------|
| owner | `tag:pmoves` | All | All |
| partner | `tag:partner` | 5090, Z890 | 3030, 8080, 8081 |
| guest | `tag:guest` | Z890 | 8081 |

Tokens are logged to a local ledger (`fleet/.enrollment-ledger.jsonl`, gitignored). [DOC-CONFIRMED]
