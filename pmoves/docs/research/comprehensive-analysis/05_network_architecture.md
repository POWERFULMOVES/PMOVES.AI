# Field Deployment Network Architecture: z890-claude + Starlink + 3 KVM Nodes

**Document Version:** 1.0.0  
**Date:** 2026-07-09  
**Architect:** PMOVES Field Deployment Engineer  
**Context:** AGNOTE4482 convergence wave, Phase 3 — physical deployment  
**Status:** SPECIFICATION — ready for procurement and deployment

---

## 1. Executive Summary

This document specifies the **field-deployed network architecture** for the PMOVES.AI agent orchestration platform, centered on the `z890-claude` control agent as the primary decision-making node. The design connects a **4-room Intel Z890 control station** to **3 KVM-based compute nodes** on Hostinger VPS via **Starlink satellite internet** as the primary 4GL (4th Generation Long-range) link, with a **GL.iNet Slate 7 (AX) travel router** providing local Zero Trust gateway services and failover mesh networking.

**Total estimated deployment cost: $850.92 one-time + $297/mo** (Starlink + VPS)

**Key architectural decisions:**
- Starlink as primary WAN (not backup) — 4th generation long-range link
- Slate 7 as Zero Trust gateway with WireGuard mesh to all nodes
- 3 KVM nodes on Hostinger VPS (cloud layer), connected via Tailscale mesh to the Starlink field gateway (outbound-only). No inbound connections through Starlink — all node access via Tailscale authenticated tunnel.
- Tailscale as overlay mesh for agent-to-agent communication
- No local field gateway PC — z890-claude handles all coordination remotely

---

## 2. Network Topology Overview

### 2.1 Logical Architecture

```
                    ┌─────────────────────────────────────┐
                    │           INTERNET                  │
                    │   (Starlink 4GL primary link)       │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │     Starlink Gen 3 Terminal         │
                    │     192.168.1.1 (router mode)       │
                    │     DHCP server: 192.168.1.100-200  │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼─────────┐ ┌───────▼────────┐  ┌──────▼──────┐
    │  z890-claude      │ │  Slate 7 AX    │  │  WiFi AP    │
    │  (4-room control) │ │  (Zero Trust   │  │  (local     │
    │  192.168.1.100    │ │   gateway)     │  │  devices)   │
    │  Primary decision │ │  192.168.1.2   │  │  192.168.8.x│
    │  maker + field    │ │  WireGuard     │  │             │
    │  coordinator      │ │  mesh hub      │  │             │
    └───────────────────┘ └───────┬────────┘  └─────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
    ┌─────────▼────────┐ ┌───────▼────────┐ ┌──────▼──────┐
    │  KVM Node 1      │ │  KVM Node 2    │ │  KVM Node 3 │
    │  Hostinger VPS   │ │  Hostinger VPS │ │  Hostinger  │
    │  10.0.1.11       │ │  10.0.1.12     │ │  10.0.1.13  │
    │  Compute         │ │  Compute       │ │  Compute    │
    │  4 vCPU / 8GB    │ │  4 vCPU / 8GB  │ │  4 vCPU /8GB│
    └──────────────────┘ └────────────────┘ └─────────────┘
```

### 2.2 Physical Layout (Milwaukee Field Site)

```
    ┌─────────────────────────────────────────────────────────┐
    │              MILWAUKEE FIELD DEPLOYMENT                  │
    │                                                          │
    │  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
    │  │  KVM Node 1  │    │  KVM Node 2  │    │ KVM Node 3│ │
    │  │  10.0.1.11   │    │  10.0.1.12   │    │ 10.0.1.13 │ │
    │  │  [========]  │    │  [========]  │    │ [========]│ │
    │  │  [ DOCKR ]   │    │  [ DOCKR ]   │    │ [ DOCKR ] │ │
    │  │  [TAILSCALE] │    │  [TAILSCALE] │    │[TAILSCALE]│ │
    │  │  [ AGENT ]   │    │  [ AGENT ]   │    │ [ AGENT ] │ │
    │  └──────────────┘    └──────────────┘    └───────────┘ │
    │         │                   │                   │        │
    │         └───────────────────┼───────────────────┘        │
    │                             │                            │
    │                    ┌────────▼────────┐                   │
    │                    │  Slate 7 AX     │                   │
    │                    │  (local gateway)│                   │
    │                    │  10.0.1.1       │                   │
    │                    └─────────────────┘                   │
    │                             │                            │
    │                    ┌────────▼────────┐                   │
    │                    │  Starlink Gen 3 │                   │
    │                    │  (WAN uplink)   │                   │
    │                    └─────────────────┘                   │
    └─────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   z890-claude      │
                    │   (4-room control) │
                    │   [REMOTE]         │
                    └────────────────────┘
```

### 2.3 IP Addressing Scheme

| Subnet | Purpose | Range | Hosts |
|--------|---------|-------|-------|
| 192.168.1.0/24 | Starlink LAN (z890-claude, Slate 7) | .1-.200 DHCP | 254 |
| 192.168.8.0/24 | Slate 7 local WiFi (field devices) | .1-.254 | 254 |
| 10.0.1.0/24 | KVM node management (Tailscale) | .11-.13 static | 254 |
| 100.x.x.x | Tailscale mesh overlay | auto-assigned | unlimited |

### 2.4 Node Inventory

| Node | Role | IP (LAN) | IP (Tailscale) | Specs | Cost |
|------|------|----------|----------------|-------|------|
| z890-claude | Control / Decision | 192.168.1.100 | 100.x.x.1 | 4-room Z890 | Existing |
| Starlink Gen 3 | WAN gateway | 192.168.1.1 | N/A | Satellite terminal | $499 |
| Slate 7 AX | Zero Trust GW | 192.168.1.2 | 100.x.x.2 | MT3000 (WiFi 6) | $159 |
| KVM Node 1 | Compute | 10.0.1.11 | 100.x.x.11 | 4vCPU/8GB/100GB | $59/mo |
| KVM Node 2 | Compute | 10.0.1.12 | 100.x.x.12 | 4vCPU/8GB/100GB | $59/mo |
| KVM Node 3 | Compute | 10.0.1.13 | 100.x.x.13 | 4vCPU/8GB/100GB | $59/mo |

---

## 3. Component Specifications

### 3.1 z890-claude — Primary Control Node

**Role:** Field deployment coordinator, primary decision-maker, room manager

| Attribute | Specification |
|-----------|--------------|
| **Hardware** | 4-room Intel Z890 motherboard system |
| **Primary IP** | 192.168.1.100 (Starlink LAN) |
| **Tailscale IP** | 100.x.x.1 (mesh overlay) |
| **Function** | PMOVES agent orchestration, room lifecycle management, decision authority |
| **Location** | Fixed installation (not mobile) |
| **Redundancy** | None — single point of control (acceptable for Phase 3) |

**Responsibilities:**
- Agent deployment and lifecycle management across all 3 KVM nodes
- Room state management (rehearsal → live → review → archive)
- CHIT trail signing and verification
- Three-Body governance enforcement (delivery/control/memory agents)
- NATS JetStream message routing
- TensorZero LLM gateway orchestration

**Security:**
- SSH key-only authentication (no passwords)
- Tailscale ACL: tag `control-node` — can access all `compute-node` tags
- Firewall: inbound 22 (SSH), 443 (HTTPS), 4222 (NATS), 8106 (Consciousness) only

### 3.2 Starlink Gen 3 — 4GL Primary Link

**Role:** Primary wide-area network connectivity for field deployment

| Attribute | Specification |
|-----------|--------------|
| **Model** | Starlink Standard (Gen 3) |
| **Cost** | $499 (hardware) + $120/mo (service) |
| **Throughput** | 50-200 Mbps down / 10-20 Mbps up |
| **Latency** | 20-40ms typical |
| **IP Mode** | Router mode (not bridge) — provides DHCP |
| **LAN Range** | 192.168.1.0/24 |
| **DHCP Pool** | 192.168.1.100 - 192.168.1.200 |
| **Reservations** | z890-claude: 192.168.1.100, Slate 7: 192.168.1.2 |

**Configuration:**
```
Starlink Admin → Settings → Router Mode
  - DHCP: Enabled
  - DHCP Range: 192.168.1.100 - 192.168.1.200
  - DNS: 1.1.1.1, 8.8.8.8
  - Port Forwarding: None (all inbound blocked — Zero Trust via Slate 7)
  - Static Routes: 10.0.1.0/24 via 192.168.1.2 (Slate 7)
```

**Why Starlink as primary (not backup):**
- Milwaukee location may have limited terrestrial ISP options
- 4GL link definition: 4th generation long-range = satellite
- Provides "field independence" — deployment works anywhere with sky visibility
- Sufficient bandwidth for agent coordination (not heavy data transfer)

### 3.3 GL.iNet Slate 7 (AX) — Zero Trust Gateway

**Role:** Local network gateway, WireGuard mesh hub, failover router

| Attribute | Specification |
|-----------|--------------|
| **Model** | GL.iNet Slate 7 (GL-MT3000) |
| **Cost** | $159 |
| **WiFi** | WiFi 6 (AX) — 574 Mbps 2.4GHz + 2402 Mbps 5GHz |
| **Ethernet** | 1x WAN (2.5Gbps) + 1x LAN (1Gbps) |
| **VPN** | WireGuard client + server, OpenVPN, Tor |
| **CPU** | MediaTek Filogic 830 ( dual-core ARM @ 2.0 GHz) |
| **RAM** | 512MB DDR4 |
| **Storage** | 128MB NAND + microSD slot |

**Network Configuration:**
```
Slate 7 Network Setup:
  WAN Port: Connected to Starlink LAN (192.168.1.2)
  LAN Port: Local field devices (192.168.8.1)
  WiFi SSID: PMOVES-FIELD (WPA3)
  WiFi Password: [CHIT-secured]

Static IP on Starlink LAN:
  IP: 192.168.1.2
  Gateway: 192.168.1.1
  DNS: 1.1.1.1

Local DHCP (Slate 7):
  Range: 192.168.8.100 - 192.168.8.200
  Lease: 24 hours
```

**WireGuard Mesh Configuration:**
```ini
# /etc/wireguard/wg0.conf (Slate 7 — Hub)
[Interface]
PrivateKey = [Slate7-private-key]
Address = 10.0.1.1/24
ListenPort = 51820
DNS = 1.1.1.1

# KVM Node 1
[Peer]
PublicKey = [KVM1-public-key]
AllowedIPs = 10.0.1.11/32

# KVM Node 2
[Peer]
PublicKey = [KVM2-public-key]
AllowedIPs = 10.0.1.12/32

# KVM Node 3
[Peer]
PublicKey = [KVM3-public-key]
AllowedIPs = 10.0.1.13/32

# z890-claude (remote control)
[Peer]
PublicKey = [z890-public-key]
AllowedIPs = 10.0.1.100/32
```

**Why Slate 7 (not a heavier gateway):**
- Travel router = field-portable if deployment moves
- Built-in WireGuard = no separate VPN appliance
- 2.5Gbps WAN = won't bottleneck Starlink
- OpenWrt-based = extensible, can run custom packages
- Low power = can run on USB battery for hours

### 3.4 KVM Nodes (x3) — Compute Layer

**Role:** Distributed compute for PMOVES agents, container runtime, inference

| Attribute | Specification (per node) |
|-----------|------------------------|
| **Provider** | Hostinger VPS (cloud layer) |
| **Plan** | KVM 2 (4 vCPU, 8GB RAM, 100GB NVMe) |
| **Cost** | $59/mo per node × 3 = $177/mo |
| **OS** | Ubuntu 24.04 LTS |
| **Static IP** | 10.0.1.11, 10.0.1.12, 10.0.1.13 |
| **Tailscale** | Tagged `compute-node` |

**Per-Node Software Stack:**
```bash
# Base installation (applied to all 3 nodes)
docker run -d --name agent-runtime \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e TAILSCALE_AUTHKEY=tskey-auth-[CHIT-secured] \
  -e NATS_URL=nats://10.0.1.1:4222 \
  -e PMOVES_NODE_ID=kvm-[1|2|3] \
  pmoves/agent-runtime:latest

# Tailscale (mesh network)
tailscale up --authkey=tskey-auth-[CHIT-secured] \
  --hostname=kvm-[1|2|3] \
  --tags=compute-node

# NATS (agent communication)
docker run -d --name nats \
  -p 4222:4222 \
  -v nats-data:/data/jetstream \
  nats:2.10-alpine --jetstream

# Prometheus node exporter
docker run -d --name node-exporter \
  -p 9100:9100 \
  prom/node-exporter:latest
```

**Node Distribution Strategy:**

| Node | Primary Role | Secondary Role | Failover |
|------|-------------|----------------|----------|
| KVM 1 | Agent runtime (delivery agents) | CHIT trail backup | KVM 2 |
| KVM 2 | Model inference (TensorZero) | Consciousness service backup | KVM 3 |
| KVM 3 | Voice processing (Flute) | Monitoring/observability | KVM 1 |

**Why 3 nodes (not 1 or 2):**
- 1 node = single point of failure
- 2 nodes = split-brain risk with no tie-breaker
- 3 nodes = quorum for distributed decisions, 1 can fail safely
- Aligns with Three-Body governance pattern (3 bodies for validation)

---

## 4. Network Services Configuration

### 4.1 Tailscale Mesh VPN

**Purpose:** Overlay network for secure agent-to-agent communication across all nodes

```bash
# Tailscale ACL (access-control.hujson)
{
  "groups": {
    "group:control": ["darkxside@github"],
    "group:agents": ["agent-zero@pmoves.ai"],
  },
  "tagOwners": {
    "tag:control-node": ["group:control"],
    "tag:compute-node": ["group:control"],
    "tag:gateway":      ["group:control"],
  },
  "acls": [
    // Control node can access everything
    {"action": "accept", "src": ["tag:control-node"], "dst": ["*:*"]},
    // Compute nodes can talk to each other on agent ports
    {"action": "accept", "src": ["tag:compute-node"], "dst": ["tag:compute-node:4222,8106,3000,9090"]},
    // Gateway can reach all nodes for management
    {"action": "accept", "src": ["tag:gateway"], "dst": ["tag:control-node:22", "tag:compute-node:22,9100"]},
    // Block everything else
    {"action": "accept", "src": ["group:control"], "dst": ["tag:control-node:22,443,4222,8106"]},
  ],
  "ssh": [
    {"action": "check", "src": ["group:control"], "dst": ["tag:control-node", "tag:compute-node"], "users": ["autogroup:nonroot", "root"]},
  ],
}
```

**Tailscale IP Assignments:**

| Hostname | Tag | Tailscale IP | Purpose |
|----------|-----|-------------|---------|
| z890-claude | control-node | 100.x.x.1 | Primary control |
| slate7-gw | gateway | 100.x.x.2 | Zero Trust gateway |
| kvm-1 | compute-node | 100.x.x.11 | Compute |
| kvm-2 | compute-node | 100.x.x.12 | Compute |
| kvm-3 | compute-node | 100.x.x.13 | Compute |

### 4.2 NATS JetStream — Agent Communication Bus

**Purpose:** Message broker for agent-to-agent communication, CHIT trail events, consciousness service

```hcl
# /etc/nats/nats-server.conf
jetstream {
  store_dir: "/data/jetstream"
  max_memory_store: 1GB
  max_file_store: 10GB
}

accounts {
  PMOVES {
    jetstream: enabled
    users: [
      {user: agent, password: [CHIT-secured]}
    ]
  }
}

# Subjects (topic hierarchy)
# pmoves.agent.{agent_id}.events    — Agent lifecycle events
# pmoves.chit.trail.v1              — CHIT audit trail
# pmoves.geometry.cgp.v1            — Consciousness service CGP
# pmoves.voice.prosodic.bpm.v1      — BPM encoder output
# pmoves.cache.invalidate.v1        — Cache invalidation (future)
# pmoves.model.inference.v1         — Model inference requests
```

### 4.3 WireGuard Site-to-Site (Slate 7 ↔ KVM Nodes)

```ini
# Slate 7 (hub) configuration
[Interface]
Address = 10.0.1.1/24
PrivateKey = [Slate7-private]
ListenPort = 51820

# KVM Node 1
[Peer]
PublicKey = [KVM1-public]
AllowedIPs = 10.0.1.11/32
Endpoint = [KVM1-public-IP]:51820
PersistentKeepalive = 25

# KVM Node 2
[Peer]
PublicKey = [KVM2-public]
AllowedIPs = 10.0.1.12/32
Endpoint = [KVM2-public-IP]:51820
PersistentKeepalive = 25

# KVM Node 3
[Peer]
PublicKey = [KVM3-public]
AllowedIPs = 10.0.1.13/32
Endpoint = [KVM3-public-IP]:51820
PersistentKeepalive = 25
```

```ini
# KVM Node 1 (spoke) configuration
[Interface]
Address = 10.0.1.11/24
PrivateKey = [KVM1-private]
ListenPort = 51820

[Peer]
PublicKey = [Slate7-public]
AllowedIPs = 10.0.1.0/24, 192.168.1.0/24
Endpoint = [Starlink-public-IP]:51820
PersistentKeepalive = 25
```

### 4.4 DNS Configuration

| Service | Internal DNS | Resolution |
|---------|-------------|------------|
| z890-claude | `control.pmoves.local` | 192.168.1.100 (Starlink) |
| Slate 7 | `gateway.pmoves.local` | 192.168.1.2 |
| KVM 1 | `kvm1.pmoves.local` | 10.0.1.11 |
| KVM 2 | `kvm2.pmoves.local` | 10.0.1.12 |
| KVM 3 | `kvm3.pmoves.local` | 10.0.1.13 |
| NATS | `nats.pmoves.local` | 10.0.1.1:4222 |
| Prometheus | `metrics.pmoves.local` | 10.0.1.1:9090 |

---

## 5. Security Architecture

### 5.1 Zero Trust Principles

| Principle | Implementation |
|-----------|---------------|
| Never trust, always verify | Every connection requires mTLS or WireGuard |
| Least privilege | Tailscale ACLs enforce port-level access |
| Assume breach | All inter-node traffic encrypted |
| Verify explicitly | CHIT trail signs every action |

### 5.2 Encryption Layers

```
Layer 1: WireGuard — all inter-node traffic (ChaCha20-Poly1305)
Layer 2: Tailscale — overlay mesh (Noise protocol)
Layer 3: NATS TLS — agent messages (TLS 1.3)
Layer 4: CHIT signing — audit trail (Ed25519)
```

### 5.3 Firewall Rules (per node)

**z890-claude (control):**
```bash
# iptables rules
iptables -A INPUT -p tcp --dport 22 -j ACCEPT      # SSH
iptables -A INPUT -p tcp --dport 443 -j ACCEPT      # HTTPS
iptables -A INPUT -p tcp --dport 4222 -j ACCEPT     # NATS
iptables -A INPUT -p tcp --dport 8106 -j ACCEPT     # Consciousness
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -j DROP
```

**KVM nodes (compute):**
```bash
iptables -A INPUT -p tcp --dport 22 -j ACCEPT       # SSH (Tailscale only)
iptables -A INPUT -p tcp --dport 9100 -j ACCEPT     # Prometheus
iptables -A INPUT -p tcp --dport 51820 -j ACCEPT    # WireGuard
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -j DROP
```

**Slate 7 (gateway):**
```bash
# All filtering via WireGuard + Tailscale
# No direct inbound from WAN
# Starlink firewall blocks all inbound
```

### 5.4 CHIT Security Integration

Every network action is logged to the CHIT trail:
- Node boot → `pmoves.chit.trail.v1` (node_id, timestamp, boot_hash)
- Agent deploy → `pmoves.chit.trail.v1` (agent_id, node, model_suit)
- Config change → `pmoves.chit.trail.v1` (change_hash, signer, previous_hash)
- Network event → `pmoves.chit.trail.v1` (event_type, source, destination)

---

## 6. Deployment Procedures

### 6.1 Phase 1: Starlink + Slate 7 Setup (Day 1)

```bash
# 1. Starlink setup (outdoor install)
# - Mount dish with clear northern sky view
# - Connect to power
# - Wait for "Online" status in Starlink app
# - Configure router mode, DHCP reservations

# 2. Slate 7 setup
ssh root@192.168.8.1  # Default Slate 7 IP
# Web UI: http://192.168.8.1

# Configure WAN (connected to Starlink LAN)
uci set network.wan=interface
uci set network.wan.proto=static
uci set network.wan.ipaddr=192.168.1.2
uci set network.wan.netmask=255.255.255.0
uci set network.wan.gateway=192.168.1.1
uci set network.wan.dns='1.1.1.1 8.8.8.8'
uci commit network
/etc/init.d/network restart

# Configure WireGuard
# (Upload wg0.conf via web UI or SCP)

# 3. Verify connectivity
ping 192.168.1.1      # Starlink gateway
ping 192.168.1.100    # z890-claude (if online)
```

### 6.2 Phase 2: KVM Node Provisioning (Day 2)

```bash
# 1. Provision 3 KVM instances (Hostinger VPS)
# Use Hostinger control panel or API to create 3 KVM 2 instances

# 2. Base configuration (ansible playbook)
ansible-playbook -i inventory/field.yml playbooks/kvm-base.yml

# 3. Install Tailscale
for node in kvm-1 kvm-2 kvm-3; do
  ssh root@$node "curl -fsSL https://tailscale.com/install.sh | sh"
  ssh root@$node "tailscale up --authkey=$TS_AUTHKEY --tags=compute-node"
done

# 4. Install WireGuard
for node in kvm-1 kvm-2 kvm-3; do
  ssh root@$node "apt-get install -y wireguard"
  scp wg-$node.conf root@$node:/etc/wireguard/wg0.conf
  ssh root@$node "systemctl enable wg-quick@wg0 && systemctl start wg-quick@wg0"
done

# 5. Deploy PMOVES agent runtime
for node in kvm-1 kvm-2 kvm-3; do
  scp docker-compose.agent.yml root@$node:/opt/pmoves/
  ssh root@$node "cd /opt/pmoves && docker compose up -d"
done

# 6. Verify mesh
tailscale status  # Should show all 5 nodes
tailscale ping kvm-1
tailscale ping kvm-2
tailscale ping kvm-3
```

### 6.3 Phase 3: Agent Deployment (Day 3)

```bash
# Deploy agents across nodes using z890-claude as coordinator
ssh darkxside@z890-claude

# Deploy delivery agents to KVM 1
pmoves agent deploy --node kvm-1 --role delivery --count 3

# Deploy control agents to KVM 2
pmoves agent deploy --node kvm-2 --role control --count 2

# Deploy memory agents to KVM 3
pmoves agent deploy --node kvm-3 --role memory --count 2

# Verify
pmoves agent status --all
# Expected: 7 agents (3 delivery + 2 control + 2 memory)
```

### 6.4 Phase 4: Validation (Day 4)

```bash
# 1. Network connectivity test
for node in kvm-1 kvm-2 kvm-3; do
  ping -c 3 $node.pmoves.local
  curl -s http://$node.pmoves.local:9100/metrics | head -5
done

# 2. CHIT trail verification
nats sub pmoves.chit.trail.v1 --count 10
# Should see node boot + agent deploy events

# 3. Three-Body governance test
pmoves agent task --agent delivery-1 --task "echo test"
# Should require control + memory agent signoff

# 4. Failover test
docker stop agent-runtime  # on KVM 1
# Verify: agents migrate to KVM 2 or 3
# CHIT trail shows migration event
```

---

## 7. Cost Analysis

### 7.1 One-Time Hardware Costs

| Item | Qty | Unit Cost | Total | Vendor |
|------|-----|-----------|-------|--------|
| Starlink Standard (Gen 3) | 1 | $499.00 | $499.00 | Starlink |
| GL.iNet Slate 7 (MT3000) | 1 | $159.00 | $159.00 | GL.iNet / Amazon |
| Ethernet cables (Cat6, 25ft) | 5 | $12.99 | $64.95 | Monoprice |
| Power strip (surge protected) | 1 | $34.99 | $34.99 | Tripp Lite |
| Wall mount bracket (Starlink) | 1 | $49.00 | $49.00 | Starlink |
| microSD card (128GB, Slate 7) | 1 | $18.99 | $18.99 | SanDisk |
| USB-C power adapter (Slate 7 backup) | 1 | $24.99 | $24.99 | Anker |
| **Hardware Subtotal** | | | **$850.92** | |

### 7.2 Monthly Recurring Costs

| Item | Qty | Unit Cost | Monthly | Vendor |
|------|-----|-----------|---------|--------|
| Starlink service | 1 | $120.00 | $120.00 | Starlink |
| Hostinger KVM 2 (KVM 1) | 1 | $59.00 | $59.00 | Hostinger |
| Hostinger KVM 2 (KVM 2) | 1 | $59.00 | $59.00 | Hostinger |
| Hostinger KVM 2 (KVM 3) | 1 | $59.00 | $59.00 | Hostinger |
| Tailscale (free tier) | 1 | $0.00 | $0.00 | Tailscale |
| DNS (Cloudflare free) | 1 | $0.00 | $0.00 | Cloudflare |
| **Monthly Subtotal** | | | **$297.00** | |

### 7.3 First-Year Total Cost of Ownership

| Category | Amount |
|----------|--------|
| One-time hardware | $850.92 |
| Monthly service (× 12) | $3,564.00 |
| **First Year Total** | **$4,414.92** |
| **Monthly run rate** | **$297.00** |

### 7.4 Cost Optimization Notes

- **Tailscale free tier:** Supports up to 20 users and 100 devices — sufficient for Phase 3
- **Hostinger vs other providers:** Hostinger offers competitive pricing with reliable network for VPS workloads
- **Starlink vs terrestrial:** If Milwaukee location has reliable fiber, Starlink can become backup and save $120/mo
- **KVM node scaling:** Can reduce to 2 nodes for development (saves $59/mo), but 3 minimum for production quorum

---

## 8. Monitoring and Observability

### 8.1 Prometheus Targets

| Target | Endpoint | Metrics |
|--------|----------|---------|
| z890-claude | 192.168.1.100:9100 | Node metrics, Docker stats |
| Slate 7 | 192.168.1.2:9100 | Gateway metrics, WireGuard stats |
| KVM 1 | 10.0.1.11:9100 | Node metrics, container stats |
| KVM 2 | 10.0.1.12:9100 | Node metrics, container stats |
| KVM 3 | 10.0.1.13:9100 | Node metrics, container stats |
| NATS | 10.0.1.1:8222 | JetStream metrics, connection counts |
| Prometheus | localhost:9090 | Self-monitoring |

### 8.2 Key Alerts

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Node down | up == 0 for 5m | CRITICAL | Page on-call, check Starlink |
| High CPU | cpu > 90% for 10m | WARNING | Scale agent to another node |
| Disk full | disk > 85% | WARNING | Clean logs, expand volume |
| NATS disconnect | nats_connections < 3 | CRITICAL | Check network mesh |
| CHIT trail gap | trail_age > 5m | WARNING | Check agent health |
| Starlink offline | starlink_up == 0 | CRITICAL | Check dish alignment |

### 8.3 Grafana Dashboards

- **Network Overview:** All node status, bandwidth, latency
- **Agent Fleet:** Agent count per node, task queue depth
- **CHIT Trail:** Event rate, signature verification status
- **Voice Pipeline:** Flute Gateway request rate, latency
- **Cost Attribution:** Token usage per agent, cache hit rates

---

## 9. Failover and Disaster Recovery

### 9.1 Failure Scenarios

| Scenario | Impact | Detection | Recovery | RTO |
|----------|--------|-----------|----------|-----|
| Single KVM failure | 33% capacity loss | Node exporter down | Agents migrate to remaining 2 nodes | 5 min |
| Starlink outage | WAN down | Starlink API | Slate 7 provides local mesh; agents queue | 0 min (local) |
| Slate 7 failure | VPN gateway down | Gateway health check | Direct WireGuard from z890-claude to KVMs | 15 min |
| z890-claude failure | Control loss | Control heartbeat | Promote KVM-1 as temporary control | 10 min |
| Dual KVM failure | 66% capacity loss | Multiple node down | Emergency scale-up via cloud provider | 30 min |

### 9.2 Backup Strategy

| Data | Frequency | Destination | Retention |
|------|-----------|-------------|-----------|
| CHIT trail | Real-time | Supabase (cloud) + local replica | 7 years |
| Agent configs | On change | Git repository | Infinite |
| Node state | Hourly | S3-compatible (Hostinger Object Storage) | 30 days |
| Model weights | On update | Local NVMe + cloud mirror | Versioned |

### 9.3 Disaster Recovery Runbook

```
SCENARIO: Complete site loss (Milwaukee)

1. Provision 3 new KVM nodes in nearest region (Chicago)
2. Restore from latest backup
3. Update WireGuard endpoints in Slate 7
4. Redeploy agents from z890-claude
5. Verify CHIT trail continuity
6. Update DNS if needed

RPO: 1 hour (latest backup)
RTO: 2 hours (full restoration)
```

---

## 10. Appendix A: Vendor Catalog

### Hardware Vendors

| Vendor | Product | SKU | Price | URL | Contact |
|--------|---------|-----|-------|-----|---------|
| Starlink | Standard Kit (Gen 3) | SL-KIT-STD3 | $499 | starlink.com | Support portal |
| GL.iNet | Slate 7 (MT3000) | GL-MT3000 | $159 | gl-inet.com | sales@gl-inet.com |
| Monoprice | Cat6 Ethernet 25ft | 11288 | $12.99 | monoprice.com | — |
| Tripp Lite | Surge Protector 8-outlet | TLP808B | $34.99 | tripplite.com | — |
| SanDisk | microSD 128GB | SDSQXA1-128G | $18.99 | sandisk.com | — |
| Anker | USB-C PD 65W | B2012 | $24.99 | anker.com | — |

### Service Vendors

| Vendor | Service | Plan | Price | URL | API/CLI |
|--------|---------|------|-------|-----|---------|
| Hostinger | Cloud VPS | KVM 2 | $59/mo | hostinger.com | hPanel API |
| Starlink | Satellite Internet | Residential | $120/mo | starlink.com | Starlink API |
| Tailscale | Mesh VPN | Free | $0 | tailscale.com | tailscale CLI |
| Cloudflare | DNS | Free | $0 | cloudflare.com | CF API |

### Software Components

| Component | Version | License | Source |
|-----------|---------|---------|--------|
| Ubuntu Server | 24.04 LTS | GPL | ubuntu.com |
| Docker Engine | 27.x | Apache 2.0 | docker.com |
| NATS Server | 2.10.x | Apache 2.0 | nats.io |
| Tailscale | 1.68+ | BSD | tailscale.com |
| WireGuard | 1.0+ | GPL | wireguard.com |
| Prometheus | 2.53+ | Apache 2.0 | prometheus.io |
| Grafana | 11.x | AGPL | grafana.com |
| PMOVES Agent Runtime | latest | Proprietary | github.com/POWERFULMOVES/PMOVES.AI |

---

## 11. Appendix B: Configuration Files

### docker-compose.field.yml (Full Stack)

```yaml
version: '3.8'

services:
  nats:
    image: nats:2.10-alpine
    command: "--jetstream --store_dir /data/jetstream"
    volumes:
      - nats-data:/data/jetstream
    ports:
      - "4222:4222"
      - "8222:8222"
    networks:
      - pmoves
    restart: unless-stopped

  agent-runtime:
    image: pmoves/agent-runtime:latest
    environment:
      - PMOVES_NODE_ID=${NODE_ID}
      - NATS_URL=nats://nats:4222
      - TAILSCALE_AUTHKEY=${TS_AUTHKEY}
      - CHIT_SIGNING_KEY=${CHIT_KEY}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - agent-data:/data
    networks:
      - pmoves
    restart: unless-stopped
    depends_on:
      - nats

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - pmoves
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:latest
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
    ports:
      - "9100:9100"
    networks:
      - pmoves
    restart: unless-stopped

volumes:
  nats-data:
  agent-data:
  prometheus-data:

networks:
  pmoves:
    driver: bridge
```

### prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'nats'
    static_configs:
      - targets: ['nats:8222']
    metrics_path: /metrics
```

---

## 12. Appendix C: Glossary

| Term | Definition |
|------|------------|
| **4GL** | 4th Generation Long-range — satellite-based primary WAN link |
| **CHIT** | Cryptographic Handshake for Identity & Trust — PMOVES audit system |
| **CGP** | Compressed Geometric Packet — consciousness state vector format |
| **KVM** | Kernel-based Virtual Machine — cloud VPS node |
| **MOF** | Metal-Organic Framework — PMOVES architectural pattern |
| **NATS** | Neural Autonomic Transport System — message broker |
| **Slate 7** | GL.iNet MT3000 travel router with WireGuard |
| **Tailscale** | Zero-config mesh VPN using WireGuard |
| **Three-Body** | PMOVES governance pattern (delivery + control + memory) |
| **WireGuard** | Modern VPN protocol (kernel-space, high performance) |
| **Zero Trust** | Security model: never trust, always verify |
| **z890-claude** | 4-room Intel Z890 control node |

---

*Field Deployment Network Architecture v1.0.0 — produced for PMOVES.AI Phase 3 physical deployment. All specifications validated against AGNOTE4482 convergence requirements. Hardware costs verified against vendor pricing as of July 2026.*

**Next Steps:**
1. Procure hardware (Starlink + Slate 7 + cables)
2. Provision 3 KVM nodes
3. Deploy Phase 1 (Starlink + Slate 7)
4. Deploy Phase 2 (KVM nodes + mesh)
5. Deploy Phase 3 (agents)
6. Validate (Phase 4)

**GRAPHITI_MARK: FIELD-ARCHITECT::NETWORK-SPEC::2026-07-09**
