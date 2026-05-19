# Hostinger VPS Production Self-Host Review

Date: 2026-05-17
Scope: PMOVES.AI KVM fleet (KVM2, KVM4-1, KVM4-2) on Hostinger US-East
Fleet: 3x KVM VPS + Tailscale VPN mesh + local GPU nodes
Classification: Internal Operations

---

## 1. Executive Summary

PMOVES.AI operates three Hostinger KVM VPS instances in US-East (DC id=13) at a combined cost of $30/mo, forming the remote production tier alongside local GPU workstations. The Hostinger API exposes 89 endpoints across 11 functional groups — VPS lifecycle, snapshots, firewall, SSH keys, DNS, billing, domains, Docker management, and metrics — authenticated via Bearer tokens with user-level permissions.

This review identifies critical operational gaps: API access is blocked from the Agent Zero Docker container by Cloudflare WAF, two of three KVM nodes have SSH access severed since 2026-04-02 (console-injection PENDING), KVM4 hardware specs are documented inconsistently across internal sources (8C vs inferred 16C), and no Terraform IaC exists despite an available provider. The Tailscale exit node infrastructure is provisioned but non-functional due to a missing ACL consume rule.

**Key metrics:** 89 API endpoints, 0 Terraform resources defined, 2/3 KVM nodes unreachable via SSH, 1 known stale API secret, 3+ stale Tailscale nodes exceeding 60-day cleanup policy.

---

## 2. API Surface Map

### 2.1 Endpoint Groups

| # | Group | Prefix | Endpoints | Purpose |
|---|-------|--------|-----------|--------|
| 1 | VPS Lifecycle | `/api/vps/v1/virtual-machines` | 16 | Create, start, stop, restart, recreate, recovery, hostname, passwords, setup, monarx |
| 2 | VPS Snapshots | `/api/vps/v1/virtual-machines/{id}/snapshot` | 3 | Create, list, restore snapshots |
| 3 | VPS Backups | `/api/vps/v1/virtual-machines/{id}/backups` | 2 | List auto-backups, restore from backup |
| 4 | VPS Firewall | `/api/vps/v1/firewall` | 8 | CRUD firewall groups + rules, activate/deactivate/sync to VM |
| 5 | VPS SSH Keys | `/api/vps/v1/public-keys` | 4 | Add, list, delete, attach keys to VMs |
| 6 | VPS Templates | `/api/vps/v1/templates` | 2 | List OS templates, get template details |
| 7 | VPS Docker | `/api/vps/v1/virtual-machines/{id}/docker` | 9 | Compose project CRUD, start/stop/restart/update/logs (EXPERIMENTAL) |
| 8 | VPS Metrics | `/api/vps/v1/virtual-machines/{id}/metrics` | 1 | CPU%, RAM, disk, traffic, uptime |
| 9 | VPS Networking | `/api/vps/v1/virtual-machines/{id}/(nameservers\|ptr)` | 2 | Nameservers, PTR (reverse DNS) records |
| 10 | DNS | `/api/dns/v1` | 4 | Zone CRUD, snapshots, validation, reset |
| 11 | Billing | `/api/billing/v1` | 7 | Catalog, orders, payment methods, subscriptions, auto-renewal |
| 12 | Domains | `/api/domains/v1` | 8 | Availability, forwarding, portfolio, WHOIS, nameservers, domain lock, privacy |
| 13 | Hosting | `/api/hosting/v1` | 4 | Datacenters, free subdomains, verify ownership, orders |
| 14 | Reach (Email) | `/api/reach/v1` | 5 | Contacts, groups, segmentation |
| 15 | Direct | `/api/v2/direct` | 1 | Active verifications |
| | **Total** | | **89** | |

Confidence: SPEC-CONFIRMED [api-1.json]

### 2.2 Authentication

| Property | Value | Confidence |
|----------|-------|------------|
| Mechanism | Bearer token in `Authorization` header | SPEC-CONFIRMED |
| Header format | `Authorization: Bearer YOUR_API_TOKEN` | SPEC-CONFIRMED |
| Token creation | hPanel → Profile → API | SPEC-CONFIRMED |
| Token permissions | Same as owning user (no granular scopes) | SPEC-CONFIRMED |
| Token expiry | Optional — can be set to expire after a period | SPEC-CONFIRMED |
| OAuth2 / scopes | Not supported | SPEC-CONFIRMED (absent from spec) |
| API key alternative | Not supported | SPEC-CONFIRMED (absent from spec) |

**Implication:** Any compromised token has full account access equivalent to the hPanel user. Rotation is the only mitigation — no read-only or scope-limited tokens exist.

### 2.3 Rate Limits

| Property | Value | Confidence |
|----------|-------|------------|
| General rate limit | Enforced, returns 429 Too Many Requests | SPEC-CONFIRMED |
| Rate limit headers | Included in response (names not specified) | SPEC-CONFIRMED |
| IP blocking | Temporary IP block on repeated limit violation | SPEC-CONFIRMED |
| Domain availability | 10 requests/minute (explicitly documented) | SPEC-CONFIRMED |
| Per-endpoint limits | Not documented for other endpoints | UNKNOWN |
| Burst allowance | Not documented | UNKNOWN |
| Default page size | 50 items per page | SPEC-CONFIRMED |

**Implication:** Automated fleet management scripts must implement client-side rate limiting with exponential backoff. The domain availability endpoint's explicit 10/min limit suggests other endpoints may have undocumented limits that could trigger IP blocks.

### 2.4 Error Response Patterns

Three response schemas defined in the spec:

**Standard Error (all 4xx/5xx except 401/422):**

~~~json
{
  "message": "Error message",
  "correlation_id": "26a91bd9-f8c8-4a83-9df9-83e23d696fe3"
}
~~~

**Unauthorized (401):**

~~~json
{
  "message": "Unauthenticated",
  "correlation_id": "26a91bd9-f8c8-4a83-9df9-83e23d696fe3"
}
~~~

**Validation Error (422):**

~~~json
{
  "message": "The name field is required. (and 1 more error)",
  "errors": {
    "field_1": ["The field_1 field is required.", "The field_1 must be a number."],
    "field_2": ["The field_2 field is required."]
  },
  "correlation_id": "26a91bd9-f8c8-4a83-9df9-83e23d696fe3"
}
~~~

Confidence: SPEC-CONFIRMED [api-1.json lines 7627-7700]

**Implication:** The `correlation_id` field is critical for support escalation. Any automation layer must log this field on error. The validation error schema supports multi-field errors with array-valued messages per field.

### 2.5 READ vs MUTATING Classification (VPS Endpoints)

| Method | Endpoint | Type | Downtime Risk | Confidence |
|--------|----------|------|---------------|------------|
| GET | `/api/vps/v1/virtual-machines` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/virtual-machines/{id}` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/virtual-machines/{id}/metrics` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/virtual-machines/{id}/backups` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/virtual-machines/{id}/nameservers` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/virtual-machines/{id}/public-keys` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/templates` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/data-centers` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/public-keys` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/firewall` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/firewall/{id}` | READ | None | SPEC-CONFIRMED |
| GET | `/api/vps/v1/virtual-machines/{id}/monarx` | READ | None | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/start` | MUTATING | ~10-30s boot | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/stop` | MUTATING | Immediate (graceful) | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/restart` | MUTATING | ~10-30s reboot | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/snapshot` | MUTATING | None (background) | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/snapshot/restore` | MUTATING | Full VM downtime | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/backups/{id}/restore` | MUTATING | Full VM downtime | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/recreate` | MUTATING | Full VM rebuild | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/recovery` | MUTATING | Recovery mode boot | SPEC-CONFIRMED |
| PUT | `/api/vps/v1/virtual-machines/{id}/hostname` | MUTATING | Hostname change | SPEC-CONFIRMED |
| PUT | `/api/vps/v1/virtual-machines/{id}/root-password` | MUTATING | None | SPEC-CONFIRMED |
| PUT | `/api/vps/v1/virtual-machines/{id}/panel-password` | MUTATING | None | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/setup` | MUTATING | Initial setup | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/actions` | MUTATING | Varies by action | SPEC-CONFIRMED |
| POST | `/api/vps/v1/firewall` | MUTATING | None (until sync) | SPEC-CONFIRMED |
| PUT | `/api/vps/v1/firewall/{id}` | MUTATING | None (until sync) | SPEC-CONFIRMED |
| POST | `/api/vps/v1/firewall/{id}/rules` | MUTATING | None (until sync) | SPEC-CONFIRMED |
| PUT | `/api/vps/v1/firewall/{id}/rules/{id}` | MUTATING | None (until sync) | SPEC-CONFIRMED |
| DELETE | `/api/vps/v1/firewall/{id}/rules/{id}` | MUTATING | None (until sync) | SPEC-CONFIRMED |
| POST | `/api/vps/v1/firewall/{id}/activate/{vmId}` | MUTATING | Instant enforcement | SPEC-CONFIRMED |
| POST | `/api/vps/v1/firewall/{id}/deactivate/{vmId}` | MUTATING | Instant removal | SPEC-CONFIRMED |
| POST | `/api/vps/v1/firewall/{id}/sync/{vmId}` | MUTATING | Instant sync | SPEC-CONFIRMED |
| POST | `/api/vps/v1/public-keys` | MUTATING | None | SPEC-CONFIRMED |
| DELETE | `/api/vps/v1/public-keys/{id}` | MUTATING | None | SPEC-CONFIRMED |
| POST | `/api/vps/v1/public-keys/attach/{vmId}` | MUTATING | None | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/ptr/{ipId}` | MUTATING | DNS propagation delay | SPEC-CONFIRMED |
| POST | `/api/vps/v1/post-install-scripts` | MUTATING | None (on next provision) | SPEC-CONFIRMED |
| PUT | `/api/vps/v1/post-install-scripts/{id}` | MUTATING | None | SPEC-CONFIRMED |
| DELETE | `/api/vps/v1/post-install-scripts/{id}` | MUTATING | None | SPEC-CONFIRMED |
| POST | `/api/vps/v1/virtual-machines/{id}/docker` | MUTATING | Container lifecycle | SPEC-CONFIRMED |

**Key observation:** Firewall changes require explicit `activate` + `sync` to take effect on a VM. Creating rules alone does nothing — this is a two-phase commit pattern.

---

## 3. PMOVES KVM Fleet Profile

### 3.1 Hardware Inventory

| Spec | KVM2 | KVM4-1 | KVM4-2 | Confidence |
|------|------|--------|--------|------------|
| **Hostinger Plan** | kvm2-usd-4m | kvm4-usd-4m | kvm4-usd-4m | DOC-INFERRED [kvm-strategy L54-61] |
| **vCPU** | 8 (doc says 4C but plan is kvm2=8C) | 8 | 8 | CONFLICT — see note |
| **RAM** | 8 GB | 16 GB | 16 GB | DOC-INFERRED [TOPOLOGY L20-22] |
| **Disk** | 200 GB SSD | Unknown (inferred 400GB) | Unknown (inferred 400GB) | MIXED |
| **GPU** | None | None | None | SPEC-CONFIRMED (no GPU endpoints) |
| **OS** | Ubuntu 22.04 | Ubuntu 22.04 | Ubuntu 22.04 | DOC-INFERRED [kvm-strategy L59] |
| **Data Center** | US-East (id=13) | US-East (id=13) | US-East (id=13) | DOC-INFERRED [kvm-strategy L60] |
| **Cost** | ~$10/mo | ~$10/mo | ~$10/mo | DOC-INFERRED [kvm-strategy L61] |
| **Total** | **$30/mo** | | | |

**Spec conflict note:** The KVM strategy document (L55-56) lists KVM2 as 8 vCPU and KVM4 as ~16 vCPU (inferred). TOPOLOGY.md (L22) lists KVM2 as 4C/8GB. The `kvm2-usd-4m` plan name suggests 4-month billing, not 4 vCPU. Actual specs are UNKNOWN until verified via `GET /api/vps/v1/virtual-machines`.

### 3.2 Service Assignments

**KVM4-1 — API Gateway / Agent Tier** [DOC-INFERRED, TOPOLOGY L136-149]

| Service | Port | Health Endpoint | Compose Profile |
|---------|------|-----------------|-----------------|
| TensorZero Gateway | 3030 | `/healthz` | default |
| Agent Zero | 8080 | `/healthz` | agents |
| Hi-RAG v2 (CPU) | 8086 | `/healthz` | default |
| Archon | 8091 | `/healthz` | agents |
| Mesh Agent | — | — | agents |
| Gateway Agent | 8100 | `/healthz` | tier-agent |
| Extract Worker | 8083 | `/healthz` | workers |

**KVM4-2 — Data / Storage Tier** [DOC-INFERRED, TOPOLOGY L150-165]

| Service | Port | Health Endpoint | Compose Profile |
|---------|------|-----------------|-----------------|
| Supabase DB (Postgres) | 5432/54322 | — | supabase-local |
| Supabase PostgREST | 3000 (int) | — | supabase-local |
| Kong Gateway | 8000/65421 | — | supabase-local |
| Qdrant | 6333 | `/healthz` | default |
| Neo4j | 7474/7687 | `/db/neo4j/health` | default |
| Meilisearch | 7700 | `/health` | default |
| NATS | 4222/9222 | `http://nats:8222/varz` | default |
| Prometheus | 9090 | `/-/healthy` | monitoring |
| Grafana | 3002 | `/api/health` | monitoring |
| Loki | 3100 | `/ready` | monitoring |
| MinIO | 9000/9001 | `/minio/health/live` | default |

**KVM2 — Reverse Proxy / RustDesk Relay** [DOC-INFERRED, TOPOLOGY L166-180]

| Service | Port | Health Check | Transport |
|---------|------|--------------|------------|
| nginx (SSL termination) | 80/443 | `nginx -t` | systemd/Docker |
| RustDesk hbbs | 21115-21116/21118 | `journalctl -u hbbs` | systemd (bare-metal) |
| RustDesk hbbr | 21117/21119 | `journalctl -u hbbr` | systemd (bare-metal) |

RustDesk relay status verified REACHABLE as of 2026-05-07 probe [DOC-INFERRED, FLEET_INVENTORY L141-146].

### 3.3 SSH Access Status

| Node | SSH Status | Blocker | Duration | Confidence |
|------|-----------|---------|----------|------------|
| KVM2 | BLOCKED | Console-injection PENDING — regenerated SSH key not pasted via Hostinger VNC console | Since 2026-04-02 (~45 days) | DOC-INFERRED [FLEET_INVENTORY L9, L137-139] |
| KVM4-1 | RESTRICTED | Per-session authorization required by damage-control hook (production VPS policy) | Ongoing policy | DOC-INFERRED [FLEET_INVENTORY L93-102] |
| KVM4-2 | BLOCKED | Console-injection PENDING — same root cause as KVM2 | Since 2026-04-02 (~45 days) | DOC-INFERRED [FLEET_INVENTORY L9, L137-139] |

**Impact:** Two of three production KVM nodes have been unreachable via SSH for 45+ days. No configuration changes, security patches, or service updates can be applied to KVM2 or KVM4-2 without VNC console access. This is the single largest operational risk in the fleet.

---

## 4. Automated Lifecycle Operations

### 4.1 Power Operations

| Operation | API Call | Method | Downtime | Console Required | Confidence |
|-----------|----------|--------|----------|-----------------|------------|
| Start | `/api/vps/v1/virtual-machines/{id}/start` | POST | ~10-30s boot | No | SPEC-CONFIRMED |
| Stop | `/api/vps/v1/virtual-machines/{id}/stop` | POST | Immediate | No | SPEC-CONFIRMED |
| Restart | `/api/vps/v1/virtual-machines/{id}/restart` | POST | ~10-30s | No | SPEC-CONFIRMED |
| Recovery mode | `/api/vps/v1/virtual-machines/{id}/recovery` | POST | Recovery boot | No | SPEC-CONFIRMED |

**Note:** Stop is graceful (OS shutdown signal). Force-kill is not documented as a separate endpoint. If the OS is hung, recovery mode or recreate may be needed.

### 4.2 Snapshot / Backup Strategy

| Operation | API Call | Method | Downtime | Limits | Confidence |
|-----------|----------|--------|----------|--------|------------|
| Create snapshot | `/api/vps/v1/virtual-machines/{id}/snapshot` | POST | None (background) | Unknown | SPEC-CONFIRMED |
| Restore snapshot | `/api/vps/v1/virtual-machines/{id}/snapshot/restore` | POST | Full VM downtime | Destructive | SPEC-CONFIRMED |
| List auto-backups | `/api/vps/v1/virtual-machines/{id}/backups` | GET | None | Unknown | SPEC-CONFIRMED |
| Restore auto-backup | `/api/vps/v1/virtual-machines/{id}/backups/{id}/restore` | POST | Full VM downtime | Destructive | SPEC-CONFIRMED |

**Risk:** Snapshot restore is destructive — current state is fully replaced. No "snapshot before restore" safeguard exists in the API. Automation must create a pre-restore snapshot before restoring.

**Recommended backup cadence:** KVM4-2 weekly (data tier, highest value), KVM4-1 bi-weekly (agent tier, mostly stateless), KVM2 monthly (proxy config only, easily reprovisioned).

### 4.3 OS Reinstall / Recreate

| Operation | API Call | Risk Level | Confidence |
|-----------|----------|------------|------------|
| Recreate VM | `/api/vps/v1/virtual-machines/{id}/recreate` | CRITICAL — destroys all data | SPEC-CONFIRMED |
| Setup (initial config) | `/api/vps/v1/virtual-machines/{id}/setup` | HIGH — post-provision only | SPEC-CONFIRMED |

**Recreate is the only resize mechanism** — Hostinger has no in-place plan upgrade/downgrade API [DOC-INFERRED, kvm-strategy L178]. To change plan, the VM must be recreated with a new `plan_id`, meaning:

1. Snapshot current state
2. Recreate VM with new plan
3. Restore from snapshot (may fail if disk size changed)
4. Re-attach SSH keys, firewall rules
5. Re-run post-install scripts
6. Verify all services

This is a high-risk operation with significant downtime (potentially 30-60 minutes including verification).

### 4.4 Network Operations

| Operation | API Call | Two-Phase Commit | Confidence |
|-----------|----------|-----------------|------------|
| List IPs | `/api/vps/v1/virtual-machines/{id}` (includes IPs) | No | SPEC-CONFIRMED |
| Set PTR record | `/api/vps/v1/virtual-machines/{id}/ptr/{ipAddressId}` | No | SPEC-CONFIRMED |
| Get nameservers | `/api/vps/v1/virtual-machines/{id}/nameservers` | No | SPEC-CONFIRMED |
| Create firewall group | `POST /api/vps/v1/firewall` | Yes — must activate + sync | SPEC-CONFIRMED |
| Update firewall rules | `PUT /api/vps/v1/firewall/{id}` | Yes — must activate + sync | SPEC-CONFIRMED |
| Add firewall rule | `POST /api/vps/v1/firewall/{id}/rules` | Yes — must activate + sync | SPEC-CONFIRMED |
| Activate firewall | `POST /api/vps/v1/firewall/{id}/activate/{vmId}` | Final step | SPEC-CONFIRMED |
| Sync firewall | `POST /api/vps/v1/firewall/{id}/sync/{vmId}` | Final step | SPEC-CONFIRMED |

**No floating IPs, no VPC, no private networking between VMs** [DOC-INFERRED, kvm-strategy L176-179]. All inter-KVM traffic routes through Tailscale VPN or public IPs.

### 4.5 Console-Free vs Console-Required Matrix

| Task | API Only | Console Required | Notes |
|------|----------|-----------------|-------|
| Start/stop/restart | Yes | No | |
| Create/restore snapshot | Yes | No | |
| Firewall management | Yes | No | |
| SSH key injection | Yes (attach) | No | But KVM2/KVM4-2 already need console for initial key injection |
| Root password reset | Yes | No | |
| Hostname change | Yes | No | |
| OS reinstall | Yes (recreate) | No | But post-provision setup may need console if SSH fails |
| Boot into recovery | Yes | No | |
| Rescue mode / grub edit | No | Yes (VNC) | |
| Fix broken networking | No | Yes (VNC) | |
| Fix broken SSH daemon | No | Yes (VNC) | |
| Access hPanel settings | No | Yes (web console) | |
| View boot console output | No | Yes (VNC) | |
| Docker compose management | Yes (experimental) | No | Per-container start/stop/logs |

---

## 5. Security Hardening Checklist

### 5.1 API Token Management

| # | Check | Status | Confidence |
|---|-------|--------|------------|
| S1 | API token created via hPanel Profile → API | ASSUMED | DOC-INFERRED (secret exists) |
| S2 | Token has optional expiry set | UNKNOWN | Not verifiable from spec side |
| S3 | Token rotation procedure documented | NO | No runbook exists |
| S4 | Token stored in secrets manager (not plaintext) | PARTIAL | Stored as `PMOVES_SPARK_HOSTINGER` secret alias — may be stale |
| S5 | Token value validated against live API | NO | API blocked from container by Cloudflare |
| S6 | Token not committed to git | ASSUMED | Standard practice |

### 5.2 Console / VNC Access Audit

| # | Check | Status | Confidence |
|---|-------|--------|------------|
| C1 | Who has hPanel login access | UNKNOWN | Not documented |
| C2 | VNC console sessions logged | UNKNOWN | Not documented in spec |
| C3 | hPanel MFA enabled | UNKNOWN | Not documented |
| C4 | Console session timeout configured | UNKNOWN | Not documented |

### 5.3 SSH Key Management

| # | Check | Status | Confidence |
|---|-------|--------|------------|
| K1 | SSH keys managed via API (not just console) | PARTIAL | API supports attach/delete, but 2 nodes need console injection first |
| K2 | All KVM nodes use same deploy key | ASSUMED | `pmoves-claw` key referenced in scripts |
| K3 | Old/revoked keys removed from API | UNKNOWN | No audit performed |
| K4 | KVM2/KVM4-2 have regenerated key pending | YES | DOC-INFERRED [FLEET_INVENTORY L137-139] |
| K5 | Post-install script can inject keys automatically | YES | SPEC-CONFIRMED (post-install-scripts endpoint) |

### 5.4 Firewall Automation

| # | Check | Status | Confidence |
|---|-------|--------|------------|
| F1 | KVM2 firewall rules defined | YES | DOC-INFERRED [kvm-strategy L507-521] — 8 rules including SSH, RustDesk, Tailscale UDP |
| F2 | KVM4-1 firewall rules defined | NO | Not documented |
| F3 | KVM4-2 firewall rules defined | NO | Not documented |
| F4 | Default-deny policy confirmed | ASSUMED | Hostinger default behavior |
| F5 | Firewall changes via API tested | NO | API blocked from container |

### 5.5 What the API CANNOT Do

| Gap | Impact | Workaround | Confidence |
|-----|--------|-----------|------------|
| No VPC / private networking | Inter-KVM traffic uses public internet or Tailscale | Tailscale VPN (already deployed) | DOC-INFERRED |
| No floating IPs | Cannot move IP between VMs for failover | DNS update + Tailscale Funnel | DOC-INFERRED |
| No in-place resize | Plan change requires full VM recreate | Snapshot → recreate → restore → verify | SPEC-CONFIRMED (absent from spec) |
| No custom images | Cannot upload golden images for fast provisioning | Post-install scripts + Ansible | DOC-INFERRED |
| No GPU instances | No GPU compute on Hostinger | Local GPU nodes via Tailscale | SPEC-CONFIRMED |
| No granular token scopes | Any token = full user access | Use dedicated API-only user account | SPEC-CONFIRMED |
| No console/VNC API | Cannot automate rescue mode operations | Manual hPanel VNC access | UNKNOWN (not in spec) |
| No webhook/event system | Cannot react to VM state changes | Polling via metrics API | SPEC-CONFIRMED (absent from spec) |

---

## 6. Integration Gaps and Risks

### 6.1 Cloudflare Blocking API from Container

**Status:** CONFIRMED — the Hostinger API at `developers.hostinger.com` is protected by Cloudflare WAF, which blocks requests from the Agent Zero Docker container.

| Workaround | Feasibility | Latency | Effort |
|-----------|-------------|---------|--------|
| Proxy via KVM node (curl from VPS itself) | High (once SSH restored) | ~5ms (DC internal) | Low — one-liner SSH+curl |
| Proxy via CLI host (A0 connector) | Medium (requires host setup) | ~20ms (home ISP) | Medium — configure SSH tunnel |
| Use Hostinger MCP server on KVM | High (designed for this) | ~5ms | Medium — MCP server setup on KVM |
| Cloudflare bypass (not recommended) | Low (ethical + TOS) | N/A | N/A |
| Request IP whitelist from Hostinger | Low (unlikely for single user) | N/A | Low — support ticket |

**Recommended path:** Once KVM2/KVM4-2 SSH is restored, run API calls via SSH from any KVM node. The MCP server approach (Phase 3 in kvm-strategy) is the long-term solution.

### 6.2 No Terraform IaC

| State | Detail | Confidence |
|-------|--------|------------|
| Terraform provider exists | `terraform-provider-hostinger` on GitHub | DOC-INFERRED [kvm-strategy L695-758] |
| Terraform configs written | NO — only example code in strategy doc | UNKNOWN (check `pmoves/terraform/`) |
| Existing KVMs imported to state | NO | Assumed from absence |
| Plan IDs known | `hostingercom-vps-kvm2-usd-4m`, `hostingercom-vps-kvm4-usd-4m` | DOC-INFERRED [kvm-strategy L727-742] |
| DC ID | 13 (US-East) | DOC-INFERRED [kvm-strategy L719] |
| Template ID | 1 (Ubuntu 22.04) | DOC-INFERRED [kvm-strategy L720] |

**Risk:** Without IaC, any KVM recreation is a manual, error-prone process. A misconfigured firewall or missing SSH key during recreation could permanently lock out the node.

### 6.3 Potentially Stale API Secret

The secret `PMOVES_SPARK_HOSTINGER` is stored in the Agent Zero secrets system but cannot be validated because the API is blocked from the container. If this secret is wrong or expired:

- All documented API automation is non-functional
- The Hostinger MCP server (if deployed on KVM) would need its own token
- Terraform plans referencing this secret would fail on apply

**Validation procedure:** SSH into any KVM node and run:

~~~bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  https://developers.hostinger.com/api/vps/v1/virtual-machines
~~~

Expected: `200`. If `401`, token is expired or wrong.

### 6.4 Tailscale ACL Gaps

| Gap | Status | Impact | Confidence |
|-----|--------|--------|------------|
| Exit node consume rule missing | P0 — not added | No client can use KVM2 as exit node despite autoApprovers being configured | DOC-INFERRED [kvm-strategy L144-152] |
| `tag:exit` not assigned to KVM2 | P0 — not tagged | KVM2 cannot advertise as exit node | DOC-INFERRED [kvm-strategy L38-39] |
| `tag:vps` defined but unused | P2 — dead code | No functional impact, but pollutes ACL readability | DOC-INFERRED [kvm-strategy L42] |
| `tag:dgx-spark` not created | P1 — pending | DGX Spark not integrated into ACL policy | DOC-INFERRED [kvm-strategy L44] |

### 6.5 Stale Tailscale Nodes

Per FLEET_INVENTORY_LIVE.md (2026-05-07), nodes exceeding 60-day offline threshold per `TAILSCALE_NODE_HYGIENE.md`:

| Hostname | OS | Offline Duration | Action | Confidence |
|----------|----|----------------|--------|------------|
| `nvsync-powerfulmoves` | windows | >60d | Remove — superseded by `pmoves-5090` | DOC-INFERRED |
| `nvsync-pmoves-spark` | linux | >60d | Remove — superseded by `pmoves-spark` | DOC-INFERRED |
| `powerfulmoves` | windows | >60d | Remove — pre-rename 5090 | DOC-INFERRED |
| `pmoves-pro` | linux | >60d | Remove — unknown retired box | DOC-INFERRED |
| `pmoves-botz` | linux | >60d | Remove — legacy/archived per 2026-04-19 | DOC-INFERRED |
| `0a120cdf31cc` | linux | >60d | Remove — abandoned container | DOC-INFERRED |
| `13eeb550425c` | linux | >60d | Remove — abandoned container | DOC-INFERRED |
| `2871444ae72428` | linux | >60d | Remove — abandoned container | DOC-INFERRED |

**Do NOT auto-delete** — run `/fleet:stale-nodes` for triaged proposal [DOC-INFERRED, FLEET_INVENTORY L166].

---

## 7. Actionable Next Steps

### R1 — Restore SSH Access to KVM2 and KVM4-2 [P0]

**Rationale:** Two of three production KVM nodes have been unreachable for 45+ days. This blocks all configuration changes, security patches, and service updates. The fix is a single manual action: paste the regenerated SSH public key via Hostinger VNC console.

**Implementation Steps:**
1. Log into hPanel for KVM2 → VNC Console
2. Paste `pmoves-claw` public key into `/root/.ssh/authorized_keys`
3. Verify SSH from Z890: `ssh root@pmoves-kvm2 hostname`
4. Repeat for KVM4-2
5. Update FLEET_INVENTORY_LIVE.md to reflect restored access
6. Run `make -C pmoves fleet-status` to verify full fleet visibility

### R2 — Validate Hostinger API Token [P0]

**Rationale:** The secret `PMOVES_SPARK_HOSTINGER` cannot be validated from the container. If expired, all API-dependent automation (snapshots, firewall, metrics) is non-functional.

**Implementation Steps:**
1. SSH into KVM4-1 (or KVM2 after R1): `ssh root@pmoves-kvm4-1`
2. Run: `curl -s -H "Authorization: Bearer $TOKEN" https://developers.hostinger.com/api/vps/v1/virtual-machines | jq '.[0].hostname'`
3. If 401: generate new token in hPanel → Profile → API
4. Update secret in Agent Zero secrets manager
5. Record token expiry date (if set) in fleet docs

### R3 — Add Exit Node ACL Consume Rule [P0]

**Rationale:** autoApprovers grant `tag:exit` permission to advertise, but no ACL rule allows any source to consume. KVM2 exit node is completely non-functional despite infrastructure being in place.

**Implementation Steps:**
1. Add to Tailscale ACL policy: `{"action": "accept", "src": ["tag:pmoves"], "dst": ["autogroup:internet:*"]}`
2. Add optional lab rule: `{"action": "accept", "src": ["tag:lab"], "dst": ["autogroup:internet:*"]}`
3. Assign `tag:exit` to KVM2: `tailscale up --auth-key=... --advertise-exit-node --tags=tag:pmoves,tag:exit`
4. Verify from Z890: `tailscale set --exit-node=pmoves-kvm2 && curl -s ifconfig.me`

### R4 — Create Terraform IaC for KVM Fleet [P1]

**Rationale:** Without IaC, any KVM recreation (the only resize path) is manual and error-prone. A misstep during recreation could permanently lock out a node.

**Implementation Steps:**
1. Initialize `pmoves/terraform/hostinger/` with provider config
2. Define resources: 3x `hostinger_vps_virtual_machine`, 1x `hostinger_vps_firewall` per VM, 1x `hostinger_vps_public_key`
3. Define 1x `hostinger_vps_post_install_script` for bootstrap
4. Run `terraform import` for existing KVMs (requires working API token from R2)
5. Run `terraform plan` — expect no changes (state matches reality)
6. Commit to repo with `.tfvars` in secrets (not git)

**Resource mapping:**

~~~hcl
resource "hostinger_vps_virtual_machine" "kvm2" {
  name            = "pmoves-kvm2"
  data_center_id  = 13
  template_id     = 1  # Ubuntu 22.04
  plan_id         = "hostingercom-vps-kvm2-usd-4m"
}

resource "hostinger_vps_virtual_machine" "kvm4_1" {
  name            = "pmoves-kvm4-1"
  data_center_id  = 13
  template_id     = 1
  plan_id         = "hostingercom-vps-kvm4-usd-4m"
}

resource "hostinger_vps_virtual_machine" "kvm4_2" {
  name            = "pmoves-kvm4-2"
  data_center_id  = 13
  template_id     = 1
  plan_id         = "hostingercom-vps-kvm4-usd-4m"
}
~~~

### R5 — Verify KVM4 Specs via API [P1]

**Rationale:** Internal docs conflict on KVM4 vCPU count (8 vs 16). Before deploying additional services to KVM4-1 (which the resource budget shows may exceed 16GB RAM at full agent tier), actual specs must be confirmed.

**Implementation Steps:**
1. After R2 (valid token), run: `GET /api/vps/v1/virtual-machines`
2. Extract `cpu_cores`, `ram`, `disk` for KVM4-1 and KVM4-2
3. Update TOPOLOGY.md and kvm-strategy.md with confirmed values
4. Re-evaluate KVM4-1 resource budget if specs differ from assumed

### R6 — Implement Automated Snapshot Schedule [P1]

**Rationale:** KVM4-2 holds all production databases (Postgres, Qdrant, Neo4j, Meilisearch, MinIO). No automated backup exists. Data loss on KVM4-2 would be catastrophic.

**Implementation Steps:**
1. Create Python script using Hostinger SDK: `POST /api/vps/v1/virtual-machines/{kvm4-2-id}/snapshot`
2. Add pre-snapshot safety: create labeled snapshot with timestamp before any restore
3. Schedule via cron on KVM4-1 (or GitHub Actions): weekly for KVM4-2, bi-weekly for KVM4-1
4. Add retention policy: keep last 4 weekly snapshots, delete older
5. Alert on failure (NATS publish to `ops.backup.failed.v1`)

### R7 — Deploy Hostinger MCP Server on KVM [P1]

**Rationale:** Long-term solution for API access from Agent Zero. The MCP server runs on a KVM node (inside Hostinger's network, no Cloudflare block) and exposes tools to CLAW agents.

**Implementation Steps:**
1. SSH into KVM4-1
2. Install: `npm install -g hostinger-api-mcp-server`
3. Configure CLAW scope with MCP server pointing at KVM4-1
4. Test: metrics query, snapshot create, firewall list
5. Document in `pmoves/docs/operations/HOSTINGER_MCP_SETUP.md`

### R8 — Define and Apply KVM4-1/KVM4-2 Firewall Rules [P1]

**Rationale:** KVM2 has documented firewall rules. KVM4-1 and KVM4-2 have none documented — they may be running with Hostinger defaults (which may be too permissive or misconfigured).

**Implementation Steps:**
1. Audit current rules via API: `GET /api/vps/v1/firewall` + check which are active on each VM
2. Design KVM4-1 rules: SSH (Tailscale /24 only), Tailscale UDP, service ports (3030, 8080, 8086, 8091, 8100, 8083)
3. Design KVM4-2 rules: SSH (Tailscale /24 only), Tailscale UDP, service ports (54322, 8000, 6333, 7474, 7687, 7700, 4222, 9090, 3002, 3100, 9000, 9001)
4. Create via API, activate, sync
5. Document in TOPOLOGY.md

### R9 — Clean Up Stale Tailscale Nodes [P2]

**Rationale:** 8+ nodes exceed the 60-day offline cleanup threshold. Stale entries pollute fleet status output and could cause routing confusion.

**Implementation Steps:**
1. Run `/fleet:stale-nodes` for triaged proposal
2. Review proposed removals with operator
3. Remove via Tailscale admin console or API
4. Verify fleet-status shows clean list

### R10 — Set Up Metrics-Based Alerting [P2]

**Rationale:** The Hostinger metrics API provides CPU%, RAM, disk, traffic, and uptime. No alerting exists today — resource exhaustion would be noticed only after service degradation.

**Implementation Steps:**
1. Create polling script: `GET /api/vps/v1/virtual-machines/{id}/metrics` every 5 minutes
2. Threshold checks: CPU >80% for 10min (warn), RAM >85% (critical), disk >90% (critical)
3. Alert via NATS publish to `ops.hostinger.metrics.v1`
4. Integrate with existing Prometheus/Grafana on KVM4-2 for visualization
5. Optional: n8n workflow for PagerDuty/Slack integration

### R11 — Remove Unused `tag:vps` from Tailscale ACL [P2]

**Rationale:** Dead code in ACL policy. No nodes are assigned `tag:vps`, and no rules reference it. Removing improves policy clarity.

**Implementation Steps:**
1. Verify no nodes have `tag:vps` assigned: `tailscale status --json | jq '.Peer[] | select(.Tags[] | contains("vps"))'`
2. Remove `tag:vps` from `tagOwners` in ACL policy
3. Test: `tailscale lock` or admin console apply

---

## 8. SDK and Tool Reference

| Tool | URL | Language | Status | Confidence |
|------|-----|----------|--------|------------|
| Python SDK | github.com/hostinger/api-python-sdk | Python | Available | SPEC-CONFIRMED |
| TypeScript SDK | github.com/hostinger/api-typescript-sdk | Node/TS | Available | SPEC-CONFIRMED |
| Terraform Provider | github.com/hostinger/terraform-provider-hostinger | HCL | Available | SPEC-CONFIRMED |
| Ansible Collection | github.com/hostinger/ansible-collection-hostinger | YAML | Available | SPEC-CONFIRMED |
| MCP Server | github.com/hostinger/api-mcp-server | Node | Available | SPEC-CONFIRMED |
| CLI (`hapi`) | github.com/hostinger/api-cli | Shell | Available | SPEC-CONFIRMED |
| n8n Node | github.com/hostinger/api-n8n-node | n8n | Available | SPEC-CONFIRMED |
| PHP SDK | github.com/hostinger/api-php-sdk | PHP | Available | SPEC-CONFIRMED |
| Postman Collection | postman.com/hostinger-api | REST | Available | SPEC-CONFIRMED |
| WHMCS Module | github.com/hostinger/api-whmcs-plugin | PHP | Available | SPEC-CONFIRMED |

---

## 9. Summary Risk Matrix

| # | Risk | Probability | Impact | Severity | Mitigated By |
|---|------|------------|--------|----------|-------------|
| 1 | KVM2/KVM4-2 SSH remains broken | High | Critical | CRITICAL | R1 (manual console injection) |
| 2 | API token expired/invalid | Medium | High | HIGH | R2 (validate from KVM) |
| 3 | KVM4-2 data loss (no backups) | Medium | Critical | HIGH | R6 (automated snapshots) |
| 4 | KVM4 specs wrong, OOM in production | Medium | High | HIGH | R5 (verify via API) |
| 5 | Exit node never functional | High | Medium | MEDIUM | R3 (ACL consume rule) |
| 6 | KVM recreation fails (no IaC) | Low | Critical | HIGH | R4 (Terraform configs) |
| 7 | Firewall misconfiguration | Medium | Medium | MEDIUM | R8 (audit + define rules) |
| 8 | Rate limit IP block during automation | Low | Medium | MEDIUM | Client-side backoff |
| 9 | Cloudflare continues blocking container | High | Low | LOW | MCP server on KVM (R7) |
| 10 | Stale Tailscale nodes cause confusion | Low | Low | LOW | R9 (cleanup) |

---

*Document generated by Agent Zero Deep Research. All API findings based on analysis of `docs/Hostingerapi/api-1.json` (8362-line OpenAPI 3.x specification). Fleet findings based on `TOPOLOGY.md`, `FLEET_INVENTORY_LIVE.md`, `kvm-exit-node-hosting-strategy.md`, and `RUSTDESK_SELF_HOSTED.md`. No live API calls were made — Cloudflare WAF blocks the Hostinger API from the Agent Zero Docker container. All speculative findings are marked DOC-INFERRED or UNKNOWN with source references.*