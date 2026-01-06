# E2B Security Hardening Guide

**Version:** 1.0.0
**Last Updated:** 2025-12-29
**Status:** Beta

---

## Overview

This document details security hardening measures for E2B (Execution Environment for Bots) integration with PMOVES.AI. E2B provides isolated sandboxes for AI-generated code execution using Firecracker microVMs.

**Security Goal:** Enable safe execution of untrusted AI-generated code while maintaining PMOVES.AI security posture.

---

## Threat Model

### Adversary Capabilities

| Threat | Capability | Mitigation |
|--------|------------|------------|
| **Malicious Code** | Arbitrary code execution in sandbox | Firecracker microVM isolation |
| **Sandbox Escape** | Escape from VM to host | Hardware-level isolation (KVM) |
| **Network Attacks** | Attack other services | Network namespaces, firewall rules |
| **Resource Exhaustion** | CPU/memory DoS | cgroups resource limits |
| **Data Exfiltration** | Extract sensitive data | No persistent storage, network blocking |

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                     PMOVES.AI Network                           │
│  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────┐  │
│  │   Agent Zero      │  │   Archon          │  │  SupaSerch  │  │
│  │   (llm_tier)      │  │   (llm_tier)      │  │ (api_tier)  │  │
│  └─────────┬─────────┘  └─────────┬─────────┘  └──────┬──────┘  │
│            │                      │                   │         │
│            └──────────────┬───────┴───────────────────┘         │
│                           │                                     │
│                    ┌──────▼──────┐                              │
│                    │ e2b-mcp     │                              │
│                    │ (bus_tier)  │                              │
│                    └──────┬──────┘                              │
│                           │                                     │
│            ┌──────────────▼──────────────┐                      │
│            │      TRUST BOUNDARY         │                      │
│            │  (Firecracker microVMs)     │                      │
│            └─────────────────────────────┘                      │
│                           │                                     │
│                    ┌──────▼──────┐                              │
│                    │  E2B Sandbox│                              │
│                    │  (isolated) │                              │
│                    └─────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Container Security

### Base Image Hardening

All E2B containers use security-hardened base images:

```dockerfile
# PMOVES hardened base
FROM pmoves-base:hardened

# Non-root user
USER 65532:65532

# Read-only root filesystem
READONLY_ROOTFS=true

# Drop all capabilities
CAP_DROP=ALL
```

### Docker Compose Security Configuration

```yaml
services:
  e2b-mcp-server:
    image: pmoves-e2b-mcp-server:hardened
    user: "65532:65532"
    read_only: true
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    networks: [llm_tier, bus_tier, monitoring_tier]
    environment:
      - NODE_ENV=production

  e2b-surf:
    image: pmoves-e2b-surf:hardened
    user: "65532:65532"
    read_only: true
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    networks: [api_tier, app_tier, monitoring_tier]

  e2b-desktop:
    image: pmoves-e2b-desktop:hardened
    user: "65532:65532"
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    networks: [app_tier, monitoring_tier]
```

### Volume Security

```yaml
services:
  e2b-mcp-server:
    volumes:
      # Writable tmp only (noexec, nosuid)
      - e2b-mcp-tmp:/tmp:rw,noexec,nosuid,size=100m
```

### Exception: Docker Socket Mount

**e2b-sandbox** requires Docker socket mount for spawning VMs:

```yaml
e2b-sandbox:
  volumes:
    # REQUIRED: Controlled escape for container spawning
    - /var/run/docker.sock:/var/run/docker.sock:rw
  cap_add: [SYS_ADMIN]
  security_opt: [no-new-privileges:true]
```

**Mitigation:**
- Run on dedicated host (KVM VM)
- Restrict socket to e2b-sandbox only
- Monitor spawned containers
- Resource limits via cgroups

---

## Sandbox Isolation

### Firecracker MicroVM Configuration

```toml
# Firecracker VM configuration
[vm]
vcpu_count = 2
mem_size_mib = 2048
ht_enabled = false

# Kernel boot
boot-source.kernel_args_path = "/boot/kernel_args"
boot-source.kernel_args = "console=ttyS0 reboot=k panic=1 pci=off"

# Network (isolated)
[network]
iface_id = "eth0"
host_dev_name = "tap0"
allow_mmds_requests = true

# Resource limits
[mmds]
version = "V2"
network_interfaces = ["eth0"]
ipv4_address = "169.254.169.254"
```

### Network Isolation

Each sandbox runs in an isolated network namespace:

```bash
# Create isolated network for each sandbox
ip netns add sandbox-$(uuidgen)
ip netns exec sandbox-$(uuidgen) ip link set lo up

# No external network access by default
# (must be explicitly enabled per sandbox)
```

### Storage Isolation

```bash
# Ephemeral storage only (deleted on termination)
# No persistent volumes mounted into sandboxes
# All artifacts uploaded to MinIO via Presign
```

---

## Authentication & Authorization

### JWT Token Configuration

```python
# E2B JWT token generation
import jwt
from datetime import datetime, timedelta

def generate_sandbox_token(user_id: str, secret: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
        "capabilities": ["execute:python", "execute:javascript"]
    }
    return jwt.encode(payload, secret, algorithm="HS256")
```

### Token Storage

**Production:** Use CHIT encryption

```bash
# CHIT-encoded secrets
E2B_API_KEY=chit:encrypt:{encoded_key}
E2B_DESKTOP_AUTH_TOKEN=chit:encrypt:{encoded_token}
E2B_MCP_SERVER_TOKEN=chit:encrypt:{encoded_token}
```

**Development:** Plain text in `.env.local` (gitignored)

### Token Rotation

| Token | Rotation Period | Method |
|-------|-----------------|--------|
| E2B_API_KEY | 90 days | Regenerate at E2B.dev or self-hosted |
| E2B_DESKTOP_AUTH_TOKEN | 30 days | `openssl rand -hex 32` |
| E2B_MCP_SERVER_TOKEN | 30 days | `openssl rand -hex 32` |

---

## Resource Limits

### Per-Sandbox Limits

```yaml
# Docker Compose resource limits
e2b-sandbox:
  deploy:
    resources:
      limits:
        cpus: '2'      # 2 CPU cores max
        memory: 2G     # 2GB RAM max
      reservations:
        cpus: '0.5'    # 0.5 CPU minimum
        memory: 512M   # 512MB minimum
```

### Cgroups Configuration

```bash
# Create cgroup for sandbox limits
cgcreate -g cpu,memory:/e2b-sandbox

# Set limits
cgset -r cpu.cfs_quota_us=200000 e2b-sandbox    # 2 CPU cores
cgset -r memory.limit_in_bytes=2147483648 e2b-sandbox  # 2GB RAM
```

### Timeout Limits

```bash
# Maximum sandbox duration
E2B_SANDBOX_TIMEOUT_SEC=3600  # 1 hour max

# Code execution timeout
E2B_EXECUTION_TIMEOUT_SEC=300  # 5 minutes max per execution
```

---

## Network Security

### Firewall Rules

```bash
# IPTables rules for E2B host
# Block all inbound except SSH
iptables -P INPUT DROP
iptables -A INPUT -p tcp --dport 22 -j ACCEPT  # SSH
iptables -A INPUT -i tailscale0 -j ACCEPT     # Tailscale VPN

# Allow outbound only to specific services
iptables -A OUTPUT -d 172.30.0.0/16 -j ACCEPT  # PMOVES networks
iptables -A OUTPUT -d 169.254.169.254 -j ACCEPT  # MMDS (metadata)
iptables -P OUTPUT DROP  # Block everything else
```

### Tailscale Configuration

```bash
# Install Tailscale on KVM host
curl -fsSL https://tailscale.com/install.sh | sh

# Advertise KVM host tags
sudo tailscale up --advertise-tags=kvm-host,tag:e2b

# Enable key expiration
sudo tailscale set --key-expiration=90d
```

### ACL Configuration

```json
// Tailscale ACLs
{
  "tagOwners": {
    "tag:kvm-host": ["group:admins"],
    "tag:e2b": ["group:admins", "group:agents"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["group:agents"],
      "dst": ["tag:e2b:*"]
    }
  ]
}
```

---

## Secrets Management

### CHIT Encryption

See `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` for complete CHIT usage.

```python
# Encrypt E2B secrets with CHIT
from pmoves.geometry import CHIT

# Encrypt API key
encrypted_key = CHIT.encrypt("your_e2b_api_key")

# Store in environment
export E2B_API_KEY="chit:encrypt:{encrypted_key}"

# Decrypt at runtime
decrypted_key = CHIT.decrypt(os.environ["E2B_API_KEY"])
```

### Environment Variable Security

| Variable | Sensitivity | Storage |
|-----------|-------------|---------|
| `E2B_API_KEY` | HIGH | CHIT encrypted |
| `E2B_DESKTOP_AUTH_TOKEN` | HIGH | CHIT encrypted |
| `E2B_MCP_SERVER_TOKEN` | HIGH | CHIT encrypted |
| `E2B_SANDBOX_URL` | LOW | Plain text |
| `E2B_DESKTOP_URL` | LOW | Plain text |

---

## Audit Logging

### Event Types Logged

| Event | Description | Retention |
|-------|-------------|-----------|
| `sandbox.created` | Sandbox created | 90 days |
| `sandbox.executed` | Code executed | 90 days |
| `sandbox.terminated` | Sandbox terminated | 90 days |
| `sandbox.failed` | Execution failed | 365 days |
| `desktop.accessed` | Desktop accessed | 90 days |
| `surf.started` | Web surf started | 30 days |

### Log Format

```json
{
  "timestamp": "2025-12-29T12:00:00Z",
  "event_type": "sandbox.executed",
  "sandbox_id": "sb-uuid-v4",
  "user_id": "user-123",
  "agent_id": "agent-zero",
  "language": "python",
  "duration_ms": 1234,
  "success": true,
  "ip_address": "172.30.1.10"
}
```

### Loki Query Examples

```bash
# Query all E2B events
{job="e2b-*"}

# Query failed executions
{job="e2b-mcp-server"} |= "failed"

# Query by user
{job="e2b-*"} |= "user-123"

# Query desktop access
{job="e2b-desktop"} |= "accessed"
```

---

## Monitoring & Alerting

### Prometheus Metrics

```promql
# Active sandboxes
e2b_sandboxes_active{service="e2b-mcp-server"}

# Execution failure rate (alert if > 5%)
rate(e2b_executions_failed_total[5m]) / rate(e2b_executions_total[5m])

# Average execution duration
rate(e2b_execution_duration_seconds_sum[5m]) / rate(e2b_execution_duration_seconds_count[5m])

# Memory usage per sandbox
e2b_sandbox_memory_bytes{quantile="0.95"}
```

### Alert Rules

```yaml
# Prometheus alert rules
groups:
  - name: e2b_alerts
    rules:
      - alert: E2BHighFailureRate
        expr: |
          rate(e2b_executions_failed_total[5m]) / rate(e2b_executions_total[5m]) > 0.05
        for: 10m
        annotations:
          summary: "E2B failure rate > 5%"

      - alert: E2BHighMemoryUsage
        expr: e2b_sandbox_memory_bytes > 2147483648
        for: 5m
        annotations:
          summary: "E2B sandbox exceeds 2GB memory"

      - alert: E2BTooManySandboxes
        expr: e2b_sandboxes_active > 10
        for: 5m
        annotations:
          summary: "Too many active sandboxes"
```

---

## Incident Response

### Sandbox Escape Detection

```bash
# Check for unexpected processes on host
ps aux | grep -v "sandbox-" | grep -E "(python|node|bash)"

# Check for unexpected network connections
ss -tunlp | grep -E ":(7070|7073|3080|6080)"

# Check Docker container list
docker ps --format "{{.Names}}"

# Alert if unexpected containers found
```

### Response Procedures

| Severity | Response | ETA |
|----------|----------|-----|
| **Critical** | Shut down all E2B services, preserve logs | Immediate |
| **High** | Kill affected sandbox, alert admins | 5 min |
| **Medium** | Log incident, monitor for patterns | 30 min |
| **Low** | Document for future reference | 24 hr |

---

## Compliance & Certifications

### Data Privacy

- **No PII in logs** - User IDs only (no names, emails)
- **Session isolation** - Each sandbox completely isolated
- **Ephemeral storage** - No data persists after termination
- **Artifact uploads** - Via MinIO Presign with signed URLs

### Security Standards

| Standard | Status | Notes |
|----------|--------|-------|
| SOC 2 | N/A | Not certified |
| ISO 27001 | N/A | Not certified |
| CIS Benchmarks | Partial | Docker hardening applied |
| NIST 800-53 | Partial | Select controls implemented |

---

## Hardening Checklist

### Pre-Deployment

- [ ] All secrets encrypted via CHIT
- [ ] Non-root user configured (65532:65532)
- [ ] Read-only filesystem enabled
- [ ] Capabilities dropped (ALL)
- [ ] No-new-privileges enabled
- [ ] Resource limits configured
- [ ] Firewall rules applied
- [ ] Tailscale configured
- [ ] Token rotation schedule set

### Post-Deployment

- [ ] Verify sandbox isolation (test network block)
- [ ] Verify resource limits (test memory/CPU caps)
- [ ] Verify logging (check Loki)
- [ ] Verify metrics (check Prometheus)
- [ ] Run security scan: `trivy image pmoves-e2b-mcp-server:hardened`
- [ ] Run smoke tests: `make e2b-health`

### Ongoing

- [ ] Review logs weekly for anomalies
- [ ] Rotate tokens monthly
- [ ] Update base images monthly
- [ ] Audit security rules quarterly
- [ ] Penetration testing annually

---

## References

### Internal Documentation

- [E2B Integration Guide](../../E2B_INTEGRATION.md)
- [CHIT Integration](../PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md)
- [NATS Subjects](../../../../.claude/context/nats-subjects.md)
- [Services Catalog](../../../../.claude/context/services-catalog.md)

### External Resources

- [E2B Security](https://e2b.dev/docs/security)
- [Firecracker Security](https://firecracker-microvm.github.io/security/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [NIST Container Security](https://www.nist.gov/itl/smallbusiness-containers)
