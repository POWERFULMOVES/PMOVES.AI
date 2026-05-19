# Tailscale Production Self-Hosted Research Review — PMOVES.AI Fleet

**Date:** 2026-05-17
**Scope:** 21 official Tailscale documentation sources across 8 research domains
**Fleet:** 26 hosts — KVM VPS nodes (KVM4-1, KVM4-2, KVM2), bare-metal GPU nodes (SPARK, 5090, Z890, Knuckles, 4090 laptop), SIDECAR Docker container

---

## 1. Executive Summary

PMOVES.AI operates a 26-host Tailscale fleet spanning KVM virtualization and bare-metal GPU nodes with a Docker sidecar in userspace-networking mode, but lacks tag-based ACL segmentation, has no documented auth key rotation procedure, and does not use Tailscale SSH — all of which Tailscale explicitly recommends for production deployments [source-2][source-11]. The fleet designates KVM2 as an exit proxy node without high-availability failover, and relies on traditional SSH key distribution rather than leveraging Tailscale's built-in WireGuard-based SSH that provides instant revocation and eliminates manual key management [source-10][source-11]. The SIDECAR container running in userspace-networking mode requires careful SOCKS5/HTTP proxy configuration and state persistence, neither of which has been validated against Tailscale's documented Docker patterns [source-13][source-15]. Immediate priorities should be deploying a tag-based ACL policy with role-specific tags, migrating to Tailscale SSH, and implementing an ephemeral auth key rotation procedure with proper secret management [source-1][source-3][source-6].

---

## 2. Current PMOVES Posture Assessment

### What PMOVES Has

| Area | Current State | Source Reference |
|------|--------------|------------------|
| Tailscale deployment | 26 hosts configured in Tailscale plugin | Fleet context |
| Exit node | KVM2 designated as exit proxy | Fleet context |
| Docker sidecar | Tailscale running with `--tun=userspace-networking` | Fleet context / [source-13] |
| SSH access | Pre-generated ed25519 keys at `/root/.ssh/id_ed25519`, host credentials in plugin config | Fleet context |
| Inter-node communication | Tailscale VPN as primary layer | Fleet context |

### Gaps vs. Tailscale Production Recommendations

**ACL Policy (Critical Gap):** PMOVES has no documented tag-based access control policy. Tailscale recommends tag-based ACLs for all production tailnets, with tags applied via auth keys and access restricted by tag in the policy file [source-1]. The new grants syntax is recommended over legacy ACLs for all new configurations [source-1][source-20]. No evidence of `tagOwners`, `autoApprovers`, or `tests` sections in the policy file.

**Auth Key Management (Critical Gap):** No documented auth key lifecycle exists. Tailscale recommends one-off keys over reusable keys, environment variable passing (not CLI arguments), shell history prevention via `HISTCONTROL`, and immediate revocation after use [source-6]. Reusable keys are explicitly called "dangerous if stolen" and should be kept in key vault products [source-5]. No evidence of ephemeral key usage for the SIDECAR container.

**Key Expiry Posture (Significant Gap):** Default key expiry is 180 days [source-8]. Tagged devices have key expiry disabled by default [source-1][source-8], but without a tag policy, PMOVES nodes are likely subject to default expiry with no reauthentication workflow. When connector keys (exit nodes, subnet routers) expire, routes remain configured but become unreachable — a "fail close" policy that could silently break fleet connectivity [source-8][source-9].

**Tailscale SSH (Significant Gap):** PMOVES uses traditional SSH with distributed ed25519 keys. Tailscale SSH replaces traditional SSH entirely by using WireGuard node keys for authentication, eliminating manual key management, providing instant revocation via policy updates, and supporting both `check` (re-auth required) and `accept` modes [source-11].

**Exit Node Hardening (Moderate Gap):** KVM2 is designated as exit proxy but there is no evidence of IP forwarding configuration (`net.ipv4.ip_forward`), admin console approval of exit node status, or ACL rules permitting exit node usage [source-10]. No high-availability failover configuration exists for the exit node role [source-21].

**Subnet Routing (Moderate Gap):** No evidence of subnet router configuration on any node. GPU nodes with local subnets (e.g., SPARK's inference network) cannot be accessed by other fleet nodes without subnet routers advertising those routes [source-18][source-19].

**DNS Strategy (Minor Gap):** No documented decision between MagicDNS and custom DNS. MagicDNS provides automatic FQDN generation (`machine.tailnet.ts.net`) with search domain support [source-16], while custom DNS with split horizon via restricted nameservers offers more control for complex private DNS scenarios [source-17].

**Docker State Persistence (Minor Gap):** The SIDECAR container runs in userspace-networking mode but there is no documented state volume configuration. Without persistent state, the container receives a new identity on each restart, which is problematic for non-ephemeral workloads [source-4][source-15].

---

## 3. Recommendations

### R1 — Deploy Tag-Based ACL Policy [P0]

**Rationale:** Tailscale requires tag-based access control for production tailnets. Tags applied via auth keys enable automatic policy enforcement without per-device configuration [source-1][source-20]. Without tags, there is no segmentation between VPS nodes, GPU nodes, and the sidecar.

**Implementation Steps:**
1. Define tag hierarchy: `tag:vps`, `tag:gpu`, `tag:exit`, `tag:sidecar`, `tag:runner`
2. Configure `tagOwners` mapping each tag to admin users
3. Create grants restricting inter-tag communication (e.g., sidecar can only reach VPS nodes on specific ports)
4. Add `tests` section to validate policy before applying
5. Apply tags to existing nodes via auth key re-registration or admin console

### R2 — Migrate to Tailscale SSH [P0]

**Rationale:** Tailscale SSH eliminates manual SSH key distribution, provides instant revocation via policy updates (which stop existing connections immediately), and uses WireGuard node keys instead of traditional key pairs [source-11]. The current ed25519 key distribution approach does not scale across 26 hosts.

**Implementation Steps:**
1. Enable Tailscale SSH on all nodes: `tailscale set --ssh`
2. Add SSH section to policy file with `action: "accept"` or `"check"` rules
3. Define which users can SSH to which tagged node groups
4. Test with `check` mode first (requires re-auth per session) before moving to `accept`
5. Retain traditional SSH as fallback for non-Tailscale access paths

### R3 — Implement Auth Key Rotation Procedure [P0]

**Rationale:** Reusable auth keys are explicitly flagged as dangerous if stolen and should be kept in key vault products [source-5]. Keys should be passed via environment variables, never CLI arguments, to prevent shell history leakage [source-6]. No current rotation procedure exists.

**Implementation Steps:**
1. Audit all existing auth keys in the admin console Keys page
2. Revoke any reusable keys not actively needed
3. Create new one-off keys for one-time node registration
4. For the SIDECAR, create an ephemeral tagged key with appropriate expiry
5. Store keys in a secrets manager (not source control) [source-5]
6. Document rotation cadence: quarterly for reusable, immediately if compromised

### R4 — Harden KVM2 Exit Node [P0]

**Rationale:** Exit nodes require IP forwarding enabled, explicit admin console approval, and ACL rules permitting their use [source-10]. Without these, the exit node designation may not be functional or secure.

**Implementation Steps:**
1. Enable IP forwarding on KVM2: `echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf && sudo sysctl -p /etc/sysctl.d/99-tailscale.conf`
2. Advertise as exit node: `sudo tailscale set --advertise-exit-node`
3. Approve in admin console: Machines → KVM2 → Edit route settings → Check "Use as exit node"
4. Add exit node ACL/grant rules to policy file
5. Add `autoApprovers.exitNode` for `tag:exit` in policy file [source-20]

### R5 — Configure Subnet Routers on GPU Nodes [P1]

**Rationale:** GPU nodes with local subnets (inference networks, training networks) are inaccessible to other fleet nodes without subnet routers acting as gateways [source-18]. Subnet routers use SNAT by default and respect Tailscale access control policies [source-18].

**Implementation Steps:**
1. Identify local subnets on SPARK, 5090, Z890, Knuckles
2. Enable IP forwarding on each GPU node
3. Advertise routes: `sudo tailscale set --advertise-routes=<local-subnet>/24`
4. Approve routes in admin console or via `autoApprovers.routes` in policy [source-20]
5. Add grants permitting specific tags to access advertised subnets
6. Do NOT disable SNAT on nodes that also serve as exit nodes [source-18]

### R6 — Disable Key Expiry for Tagged Infrastructure Nodes [P1]

**Rationale:** Key expiry on infrastructure nodes (exit nodes, subnet routers) causes routes to become unreachable with a "fail close" policy, silently breaking fleet connectivity [source-8]. Tagged devices have key expiry disabled by default, but only after a tag is applied [source-1][source-8].

**Implementation Steps:**
1. Ensure all infrastructure nodes have tags applied (via R1)
2. Verify key expiry is disabled on Machines page in admin console
3. Set custom authentication period for user devices (1-180 days) [source-8]
4. Document the 30-minute temporary extension procedure for emergency reauth [source-8]
5. Set up admin passkey login to prevent SSO lockout [source-2]

### R7 — Persist SIDECAR Tailscale State [P1]

**Rationale:** Without persistent state, the SIDECAR container receives a new Tailscale identity on each restart. For a long-running agent container, this breaks ACL policies tied to the node identity and prevents stable MagicDNS resolution [source-4][source-15].

**Implementation Steps:**
1. Mount a Docker volume for Tailscale state (typically `/var/lib/tailscale`)
2. Configure `TS_STATE_DIR` environment variable pointing to the volume
3. Evaluate whether to use ephemeral mode (new IP per restart) vs persistent mode
4. If persistent: use a reusable tagged auth key for initial registration only
5. If ephemeral: use an ephemeral tagged auth key and accept IP changes

### R8 — Configure SOCKS5/HTTP Proxy for SIDECAR [P1]

**Rationale:** In userspace-networking mode, applications cannot transparently use Tailscale — they must explicitly connect through the SOCKS5 or HTTP proxy [source-12][source-13]. Environment variables `ALL_PROXY` and `HTTP_PROXY` must be set for any process that needs tailnet access.

**Implementation Steps:**
1. Verify `tailscaled` is started with `--socks5-server=localhost:1055 --outbound-http-proxy-listen=localhost:1055`
2. Set `ALL_PROXY=socks5://localhost:1055/` for general traffic
3. Set `HTTP_PROXY=http://localhost:1055/` and `http_proxy=http://localhost:1055/` for HTTP clients
4. Document that not all protocols work through SOCKS5 (raw sockets, some UDP) [source-13]
5. Test all inter-node communication paths from within the container

### R9 — Set Up Exit Node High Availability [P2]

**Rationale:** Tailscale supports HA for subnet routers with automatic 15-second failover when multiple routers advertise the same routes [source-21]. The same pattern can provide exit node resilience, though Tailscale does not document specific exit node HA — subnet router HA is the closest analogue.

**Implementation Steps:**
1. Designate a secondary node (KVM4-1 or KVM4-2) as backup exit node
2. Configure both nodes to advertise as exit nodes
3. Test failover by disconnecting KVM2 and verifying traffic routes to backup
4. Note limitation: you cannot restrict use of specific exit nodes via ACLs [source-21]
5. Consider regional routing if fleet becomes globally distributed [source-21]

### R10 — Adopt MagicDNS with Split DNS Fallback [P2]

**Rationale:** MagicDNS automatically generates FQDNs for all tailnet devices (`machine.tailnet.ts.net`) and adds search domains so short names work [source-16]. For complex private DNS needs, restricted nameservers provide split DNS for specific domains [source-17].

**Implementation Steps:**
1. Enable MagicDNS in admin console DNS settings
2. Verify all nodes resolve via short names (e.g., `ping spark`)
3. If private DNS zones exist, configure restricted nameservers for those domains
4. Consider enabling "Override DNS servers" to force tailnet DNS on all nodes [source-17]
5. If using exit nodes, configure "Use with exit node" per nameserver as needed [source-17]

---

## 4. ACL Policy Template

The following tailnet policy file is tailored for the PMOVES fleet. It uses the recommended grants syntax alongside SSH rules and autoApprovers.

```json
{
  "nodeAttrs": [
    {
      "target": ["tag:vps"],
      "attr": ["funnel"],
      "comment": "placeholder — remove if funnel not needed"
    }
  ],

  "tagOwners": {
    "tag:vps":    ["autogroup:admin"],
    "tag:gpu":    ["autogroup:admin"],
    "tag:exit":   ["autogroup:admin"],
    "tag:sidecar": ["autogroup:admin"],
    "tag:runner": ["autogroup:admin"]
  },

  "autoApprovers": {
    "routes": {
      "10.0.0.0/8":    ["tag:gpu"],
      "192.168.0.0/16": ["tag:gpu"],
      "172.16.0.0/12":  ["tag:gpu"]
    },
    "exitNode": ["tag:exit"]
  },

  "grants": [
    {
      "src": ["autogroup:member"],
      "dst": ["autogroup:self"],
      "ip": ["*"]
    },
    {
      "src": ["tag:sidecar"],
      "dst": ["tag:vps"],
      "ip": ["*:*"]
    },
    {
      "src": ["tag:sidecar"],
      "dst": ["tag:gpu"],
      "ip": ["*:*"]
    },
    {
      "src": ["tag:vps"],
      "dst": ["tag:vps"],
      "ip": ["*"]
    },
    {
      "src": ["tag:vps"],
      "dst": ["tag:gpu"],
      "ip": ["*"]
    },
    {
      "src": ["tag:gpu"],
      "dst": ["tag:gpu"],
      "ip": ["*"]
    },
    {
      "src": ["tag:gpu"],
      "dst": ["tag:vps"],
      "ip": ["*"]
    },
    {
      "src": ["autogroup:member"],
      "dst": ["tag:exit"],
      "ip": ["*:*"]
    },
    {
      "src": ["tag:runner"],
      "dst": ["tag:vps"],
      "ip": ["*:22,80,443,8080,8443"]
    }
  ],

  "acls": [
    {
      "action": "accept",
      "src": ["*"],
      "dst": ["*:443"],
      "comment": "allow HTTPS to all nodes"
    }
  ],

  "ssh": [
    {
      "action": "check",
      "src": ["autogroup:admin"],
      "dst": ["tag:vps"],
      "users": ["root", "autogroup:nonroot"]
    },
    {
      "action": "check",
      "src": ["autogroup:admin"],
      "dst": ["tag:gpu"],
      "users": ["root", "autogroup:nonroot"]
    },
    {
      "action": "check",
      "src": ["autogroup:admin"],
      "dst": ["tag:exit"],
      "users": ["root"]
    },
    {
      "action": "check",
      "src": ["autogroup:admin"],
      "dst": ["tag:runner"],
      "users": ["root", "autogroup:nonroot"]
    },
    {
      "action": "accept",
      "src": ["autogroup:member"],
      "dst": ["autogroup:self"],
      "users": ["autogroup:nonroot"]
    }
  ],

  "tests": [
    {
      "src": "tag:sidecar",
      "accept": ["tag:vps:*", "tag:gpu:*"],
      "deny": ["tag:exit:*"]
    },
    {
      "src": "tag:runner",
      "accept": ["tag:vps:22", "tag:vps:443"],
      "deny": ["tag:gpu:22"]
    },
    {
      "src": "autogroup:member",
      "accept": ["*:443", "autogroup:self:22"],
      "deny": ["tag:vps:22"]
    }
  ]
}
```

**Design Notes:**
- Grants use `*:*` (all ports) for inter-infrastructure communication where broad access is needed; restrict per-port where principle of least privilege applies (e.g., runners)
- SSH rules use `check` mode for admin access to infrastructure nodes (requires identity provider re-authentication every 12 hours by default) [source-11]
- `autogroup:self` rule allows any user to SSH to their own devices
- `autoApprovers` automatically approves subnet routes from GPU nodes and exit node status, reducing manual console work [source-20]
- Tests validate the deny-by-default posture — sidecar cannot reach exit nodes, runners cannot SSH to GPU nodes

---

## 5. Auth Key Rotation Procedure

### Prerequisites
- Admin access to Tailscale admin console (Keys page)
- Secrets manager configured (not source control) [source-5]
- `HISTCONTROL=ignorespace` or `ignoreboth` configured on all shells [source-6]

### Step 1: Audit Existing Keys
1. Navigate to admin console → Keys page
2. List all active auth keys with their type, expiry, and usage count
3. Identify any reusable keys — flag for immediate evaluation
4. Document which nodes were registered with which keys

### Step 2: Create Replacement Keys
For each key being rotated:

**Infrastructure nodes (VPS, GPU, exit):**
1. Generate a one-off, tagged, pre-approved auth key
2. Set expiry to 90 days maximum
3. Apply appropriate tag (`tag:vps`, `tag:gpu`, `tag:exit`)
4. Copy key to secrets manager immediately — it is only displayed once [source-5]

**SIDECAR container:**
1. Generate an ephemeral, tagged auth key with `tag:sidecar`
2. Ephemeral nodes auto-remove 30-60 minutes after last activity [source-4]
3. If persistent identity is needed (see R7), use a one-off tagged key instead

**CI/CD runners:**
1. Generate a one-off, tagged auth key with `tag:runner`
2. Never use reusable keys for automated systems — use infrastructure-as-code to generate one-off keys per run [source-3]

### Step 3: Distribute Keys Securely
1. Pass keys via environment variable: `export TS_AUTH_KEY=$(cat)` then paste with Ctrl+v, Ctrl+d [source-6]
2. Alternatively: `tailscale up --auth-key=$TS_AUTH_KEY` (never hardcode in command) [source-6]
3. For Docker: pass via `TS_AUTH_KEY` environment variable in compose/service config
4. Unset variable after use: `unset TS_AUTH_KEY` [source-6]

### Step 4: Re-register Nodes
1. On each node: `tailscale logout` (for ephemeral nodes, this immediately removes them [source-4])
2. Re-authenticate with the new key
3. Verify the node appears in admin console with correct tags
4. Verify connectivity from other nodes

### Step 5: Retire Old Keys
1. Revoke all old auth keys from the Keys page
2. Note: revocation does NOT deauthorize already-registered nodes [source-3]
3. Nodes registered with old keys remain authorized until their node key expires (default 180 days) [source-3][source-7]
4. To force re-registration: remove the node from admin console, which immediately revokes its node key [source-7]

### Ephemeral vs Reusable Decision Matrix

| Scenario | Key Type | Rationale |
|----------|----------|-----------|
| Long-running server (VPS, GPU) | One-off tagged | Registered once, key discarded [source-3] |
| SIDECAR container (restarts often) | Ephemeral tagged OR one-off tagged | Ephemeral if IP changes acceptable; one-off if persistent state [source-4] |
| CI/CD runner (per-job) | One-off tagged | Generated per run via IaC, never reused [source-3] |
| Emergency access | One-off (no tag) | Ad-hoc, single use, auditable [source-6] |
| Bulk provisioning (initial setup) | Reusable tagged — SHORT expiry | Only during initial fleet setup, revoke immediately after [source-3][source-5] |

### Node Key Management
- Machine keys: generated once at install, identify the physical device, cannot be rotated [source-7]
- Node keys: generated per user authentication, tie device to identity, can be rotated via re-authentication [source-7]
- To rotate a node key: remove the device from admin console (immediately revokes node key) then re-register with a new auth key [source-7]
- Tagged devices have key expiry disabled by default — verify this after applying tags [source-1][source-8]

---

## 6. Docker-Specific Hardening Steps

### 6.1 State Persistence

The SIDECAR container runs Tailscale in userspace-networking mode. Without persistent state, the container receives a new Tailscale identity (new IP, new node key) on every restart [source-4][source-15].

**Required configuration:**
- Mount a Docker volume at the Tailscale state directory
- Set `TS_STATE_DIR` environment variable to the mounted path
- Example in Docker Compose:
  ```yaml
  volumes:
    - tailscale-state:/var/lib/tailscale
  environment:
    - TS_STATE_DIR=/var/lib/tailscale
  ```

**Decision point:** If the SIDECAR should maintain a stable identity (required for ACL rules targeting it specifically), use persistent state with a one-off tagged auth key for initial registration. If ephemeral identity is acceptable (ACL targets `tag:sidecar` rather than a specific node), use `--state=mem:` with an ephemeral tagged auth key [source-4].

### 6.2 SOCKS5/HTTP Proxy Configuration

In userspace-networking mode, `tailscaled` does not create a TUN device. Instead, it runs a SOCKS5 proxy (v1.8+) and HTTP proxy (v1.16+) that applications must explicitly use [source-12][source-13].

**Required `tailscaled` flags:**
```
tailscaled --tun=userspace-networking --socks5-server=localhost:1055 --outbound-http-proxy-listen=localhost:1055
```

**Equivalent Docker env vars:**
- `TS_USERSPACE=true` (enables userspace-networking mode) [source-13]
- `TS_SOCKS5_SERVER=localhost:1055`
- `TS_OUTBOUND_HTTP_PROXY_LISTEN=localhost:1055`

**Application environment variables:**
```
ALL_PROXY=socks5://localhost:1055/
HTTP_PROXY=http://localhost:1055/
http_proxy=http://localhost:1055/
```

Note: Some libraries use lowercase `http_proxy` instead of `HTTP_PROXY` — set both [source-13].

### 6.3 Known Limitations and Mitigations

| Limitation | Impact on SIDECAR | Mitigation |
|-----------|-------------------|------------|
| HTTP proxy only handles HTTP/HTTPS, not general TCP [source-13] | Non-HTTP services cannot use HTTP proxy | Use SOCKS5 proxy for non-HTTP traffic |
| Applications must be proxy-aware [source-12] | Applications that don't read proxy env vars cannot reach tailnet | Configure each application's proxy settings individually; test all inter-node paths |
| Raw sockets don't work through SOCKS5 [source-13] | ICMP ping, some UDP protocols fail | Use TCP-based health checks; accept that `ping` won't work from inside container |
| Some UDP protocols unsupported [source-13] | DNS-over-UDP, QUIC may not function | Use TCP-based DNS; test QUIC-dependent services |
| No transparent routing [source-12] | Every process must opt in via proxy env vars | Set proxy vars at container/service level, not per-command |

### 6.4 Security Considerations for Userspace Mode

- **Reduced attack surface:** No TUN device means no kernel-level network stack interaction — the proxy runs entirely in userspace [source-12]
- **No privilege escalation via TUN:** Since `/dev/net/tun` is not used, there is no risk of TUN device misuse within the container
- **Proxy is localhost-only:** The SOCKS5/HTTP proxy binds to localhost inside the container, so it is not exposed to the tailnet or host network [source-13]
- **Auth key exposure:** The auth key is passed as an environment variable — ensure it is not logged, not included in `docker inspect` output visibility, and unset after node registration [source-5][source-6]
- **Ephemeral node cost:** Ephemeral nodes are free up to a monthly limit; nodes present for 4+ hours count as standard tagged devices [source-4] — monitor usage if SIDECAR runs long-lived
- **No Tailscale SSH from within container:** Tailscale SSH requires taking over port 22, which in userspace mode would need the proxy to handle it — test whether Tailscale SSH works correctly in userspace-networking mode before relying on it for SIDECAR access

---

## Source References

| # | URL |
|---|-----|
| 1 | https://tailscale.com/docs/features/access-control/acls |
| 2 | https://tailscale.com/docs/reference/best-practices/production |
| 3 | https://tailscale.com/docs/features/access-control/auth-keys |
| 4 | https://tailscale.com/docs/features/ephemeral-nodes |
| 5 | https://tailscale.com/docs/reference/key-secret-management |
| 6 | https://tailscale.com/docs/features/access-control/auth-keys/how-to/secure-auth-keys |
| 7 | https://tailscale.com/docs/concepts/node-keys |
| 8 | https://tailscale.com/docs/features/access-control/key-expiry |
| 9 | https://tailscale.com/docs/features/exit-nodes |
| 10 | https://tailscale.com/docs/features/exit-nodes/how-to/setup |
| 11 | https://tailscale.com/docs/features/tailscale-ssh |
| 12 | https://tailscale.com/docs/concepts/userspace-networking |
| 13 | https://tailscale.com/kb/1112/userspace-networking |
| 14 | https://tailscale.com/docs/features/containers/docker |
| 15 | https://tailscale.com/kb/1282/docker |
| 16 | https://tailscale.com/docs/features/magicdns |
| 17 | https://tailscale.com/docs/reference/dns-in-tailscale |
| 18 | https://tailscale.com/docs/features/subnet-routers |
| 19 | https://tailscale.com/docs/features/subnet-routers/how-to/setup |
| 20 | https://tailscale.com/docs/reference/syntax/policy-file |
| 21 | https://tailscale.com/docs/how-to/set-up-high-availability |
