# Cipher Relay Deployment — 2026-09-10

**Status:** LIVE on kvm4-1 + kvm4-2 (cipher=healthy on both gateway-agents)
**Scope:** Unblocks cipher MCP for gateway-agent on VPS nodes without violating the
`internal: true` doctrine on the `pmoves_*` Docker networks.

## Root cause chain (why gateway-agent runs were failing)

1. `deploy-gateway-agent.yml` deployed with `CIPHER_URL=http://cipher-api:8105` —
   a compose service name that only resolves inside a full PMOVES compose stack.
   The KVM nodes run only gateway-agent (+ llama / monitoring / NATS), so the name
   never resolved: `[Errno -3] Temporary failure in name resolution`.
2. Cipher's actual home is the **Z890 GPU node** (`cipher-pmoves-shim v0.1.0`,
   port 8105, auth-gated). It is reachable from *tagged* tailnet nodes
   (kvm4-2 → <Z890-TAILNET-IP>:8105  # resolve via `tailscale status` / ops vault — never hardcode = HTTP 200) but **not** from user-owned nodes
   (kiloclaw direct = timeout; same ACL class as the 2026-09-08 finding).
3. Even with a reachable URL, containers cannot use the tailnet: all `pmoves_*`
   networks are `internal: true` (PMOVES network-hardening doctrine) → no route
   off the bridge (`errno 101 Network is unreachable`).

## The fix (host-level relay)

Containers CAN reach their own bridge gateway. So a host-level socat relay on the
`pmoves_api` gateway IP bridges the two worlds without touching the doctrine:

```
container → <PMOVES_API_GW>:8105 (pmoves_api bridge gw)
          → socat (pmoves-cipher-relay.service, host netns)
          → <Z890-TAILNET-IP>:8105  # resolve via `tailscale status` / ops vault — never hardcode (cipher-pmoves-shim on Z890, via tailnet)
```

### Deployed artifacts

**kvm4-2** (canonical gateway-agent node):
- `/etc/systemd/system/pmoves-cipher-relay.service` — enabled, active
- `pmoves-gateway-agent` container recreated with `CIPHER_URL=http://<PMOVES_API_GW>:8105`
  (all other env faithfully carried over from the previous container, captured via
  `docker inspect` before removal; image `pmoves/gateway-agent:latest` unchanged)
- Verified: `GET /healthz` → `cipher: healthy` (2026-09-10 ~08:01 UTC)

**kvm4-1**:
- Same relay unit, enabled + active
- Image transferred kvm4-2 → kiloclaw → kvm4-1 (`docker save | gzip`, 66 MB
  compressed; kvm4-1 has no registry pull access to the CI-built image)
- `pmoves-gateway-agent` deployed on `pmoves_api` + `pmoves_app` (no `pmoves_bus`
  on this node — NATS integration is optional and degrades gracefully)
- Same env minus the node-specific TAILSCALE_API_KEY (kvm4-2's key was not
  reused; set to empty on kvm4-1 — mint a node-scoped key if Tailscale tooling
  is needed there)
- Verified: `GET /healthz` → `cipher: healthy` (2026-09-10 ~08:06 UTC)

### Remaining degraded (by design, for now)

- `agent_zero` unreachable: kvm2's Agent Zero (mapped `:32768`) is firewalled from
  both KVMs by the tailnet ACL — operator decision needed to open kvm2's A0 port
- `tensorzero` unreachable: no TensorZero instance is running anywhere in the
  fleet right now (probed :3000 on z890 / b850 / spark / kvm4-1). Deploying
  TensorZero on kvm4-1 (it has node + free capacity) is the natural next step.
- `SUPABASE_SERVICE_KEY=ci-deploy-placeholder`: the deploy workflow ships
  placeholders; real key must be injected via GitHub Secrets → env files or a
  runtime secret store before cipher-authenticated MCP calls work end-to-end.

### Durable repo fix

.github/workflows/deploy-gateway-agent.yml` (Deploy to VPS job) exports
`CIPHER_URL=http://<PMOVES_API_GW>:8105` at deploy time after resolving the
bridge gateway dynamically, with guards (fail fast if the pmoves_api network
is missing on the runner or the gateway is not an IPv4 address). Precondition
for CI redeploys: the relay unit must exist on the target node (this doc is
the runbook).

## Security notes

- The relay binds ONLY the `pmoves_api` bridge gateway IP (<PMOVES_API_GW>), not
  0.0.0.0 — nothing outside the docker bridge can use it.
- Cipher remains Bearer-token-gated; the relay adds no auth surface on Z890
  (it forwards to the same auth-gated endpoint).
- No changes to tailnet ACLs, Docker network internals, or cipher itself.

## Operator follow-ups

1. ACL: allow tagged KVMs → kvm2 A0 port (32768) if cross-node Agent Zero is wanted
2. Stand up TensorZero on kvm4-1 (node v20 present, 77 GB free, 12 GB avail RAM)
3. Mint per-agent cipher tokens (Supabase `cipher_agent_tokens`) for real
   authenticated MCP use — the relay is transport-only
4. Consider promoting the socat relay into the compose stack as an official
   `cipher-relay` service (or `network_mode: host` sidecar) once proven stable
