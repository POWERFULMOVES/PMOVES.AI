# Docker Network Hardening Doctrine

> Peer to `DOCKER_DAEMON_HARDENING.md` (digest/cosign, daemon-level).
> This doc covers container-network topology — the layer above the daemon.
>
> Supersedes scattered notes in `FIX_GOTRUE_NETWORK_ISOLATION.md` and the
> `docker-compose.base.yml` HOST ENVIRONMENT LEAK GUARD comments.
> Those remain as incident records; this doc is the forward-facing rule set.

## Network Inventory

Six Docker networks are defined across the compose stack:

| Network | Driver | `internal` | Subnet | Role |
|---------|--------|-----------|--------|------|
| `pmoves_data` | bridge | **yes** | 172.30.4.0/24 | Data stores — NATS, Qdrant, Neo4j, Meilisearch, MinIO, Supabase-DB, ClickHouse |
| `pmoves_api` | bridge | **yes** | 172.30.1.0/24 | API gateway tier — Kong, PostgREST, GoTrue, imgproxy, Realtime |
| `pmoves_app` | bridge | **yes** | 172.30.2.0/24 | App dashboards — TensorZero UI, agent UIs |
| `pmoves_bus` | bridge | **yes** | 172.30.3.0/24 | Message bus — NATS only; high-trust, no internet |
| `pmoves_monitoring` | bridge | **yes** | 172.30.5.0/24 | Observability — Prometheus, Grafana, Loki, cAdvisor |
| `pmoves_external` | bridge | **no** | 172.30.6.0/24 | Internet-capable — TensorZero-gateway, Agent Zero, Archon, Hi-RAG |
| `pmoves_public` | bridge | **no** | 172.30.7.0/24 | Host-reachable + egress-capable — Kong, PostgREST, edge-functions |

> **`pmoves_public` was missing from this table until 2026-09-03** while being
> live with three attached containers and referenced nine times in compose. An
> agent reading only this table to choose a network for a host-unreachable
> service will reach for `pmoves_external` and violate Rule 1 — which is exactly
> what happened. It is documented here now.

**Rule 1 — Internal networks air-gap from the internet.** **TWO** networks are
`internal: false` and therefore carry outbound access: `pmoves_external` and
`pmoves_public`. Services not needing LLM API calls or pip installs
must never appear in `pmoves_external`.

**Rule 2 — Subnets are permanent.** Never renumber them; NATS auth, TLS SANs, and
firewall rules are baked against these CIDRs.

**Rule 5 — There is no "publish without egress." Front it with a gateway.**

Docker offers no network primitive that publishes a host port while blocking
outbound. Measured on the 4090, 2026-09-03:

| network config | host port published | outbound egress |
|---|---|---|
| `internal: true` | **no** (binding stored, never activated) | blocked |
| `internal: false` | yes | **yes** |
| bridge + `enable_ip_masquerade: false` | yes | **yes, on Docker Desktop** |

The third row is the workaround recommended in
[moby/moby#36174](https://github.com/moby/moby/issues/36174) (open since 2018,
filed on native Linux Engine — the ingress behaviour is documented in **no**
official Docker page). It works on Linux, and does **not** isolate here:
Docker Desktop runs a second NAT layer inside its WSL2 VM, so removing the
bridge masquerade leaves egress intact. Re-measure per platform before adopting.

So a service that must be reachable from the host has exactly two honest
options, and "attach it to an egress-capable network" is the one to avoid:

1. **Gateway-front it (preferred).** The gateway is the only published service;
   backends stay `internal: true` behind it. This is already the load-bearing
   pattern here — `kong`, `postgrest` and `edge-functions` are the three
   containers on `pmoves_public`, and Kong is the published door at `:8000`.
2. **Accept egress**, deliberately and in writing, for that specific service.

Verify either with `make -C pmoves net-reality`, which compares what each
container **requested** against what the daemon **activated** (exit 0 clean /
1 drift / 2 docker unavailable / 3 measured nothing).

---

## The Dual-Attach Pattern

When a service needs **both** an air-gapped internal network (for data access or
NATS bus) **and** internet (for LLM API calls), attach it to both:

```yaml
services:
  agent-zero:
    networks:
      - pmoves_bus       # NATS message bus (internal, air-gapped)
      - pmoves_external  # LLM API calls (internet-capable)
```

Docker Compose creates a separate network interface per network. The service name
(e.g. `agent-zero`) is resolvable via Docker's embedded DNS on EACH attached network.

### Precedent

`FIX_GOTRUE_NETWORK_ISOLATION.md` documents the first production incident from
violating this rule: GoTrue on `pmoves_api` couldn't reach `supabase-db` on
`pmoves_data` because the DB was single-attached. Fix: attach DB to both.
Generalizing: **any service that resolves cross-tier hostnames must dual-attach.**

### Current dual-attach services

| Service | Networks | Why |
|---------|----------|-----|
| `supabase-db` | `pmoves_data`, `pmoves_api` | All Supabase services (GoTrue, PostgREST) need DB |
| `agent-zero` | `pmoves_bus`, `pmoves_external` | Needs NATS + LLM APIs |
| `archon` | `pmoves_app`, `pmoves_bus`, `pmoves_external` | Dashboard + NATS + LLM |
| `hi-rag-gateway-v2` | `pmoves_data`, `pmoves_external` | Qdrant + LLM reranker |
| `flute-gateway` | `pmoves_app`, `pmoves_api`, `pmoves_bus`, `pmoves_external` | Voice + NATS + TTS APIs |

---

## Docker Compose vs `docker run` — The Alias Gap

Docker Compose **auto-creates service-name aliases** on every network a service
joins. A container named `nats` joined to `pmoves_bus` is automatically reachable
as `nats:4222` from any other container on `pmoves_bus`.

`docker run --network pmoves_bus ...` does **NOT** create these aliases unless you
explicitly pass `--network-alias nats`. This means:

- Claw scripts, bootstrap tools, and ad-hoc containers that join a `pmoves_*`
  network via `docker run` **lose DNS resolution** from sibling compose services.
- Use `pmoves/scripts/claws/with-pmoves-network.sh` (see PR-D) as the canonical
  wrapper for any `docker run` that needs to participate in compose DNS.

**Rule 3 — Never use bare `docker run --network pmoves_*` for containers that
peer services will resolve by name.** Always wrap with `with-pmoves-network.sh`
or ensure the container is launched via compose.

---

## Windows Docker Desktop — Bind Reality

Docker Desktop on Windows has a known bind-reporting gap: a container can claim
a port is bound (visible in `docker inspect`) while no host listener exists.
This is most common with non-loopback bind addresses (e.g. `NATS_BIND=<tailscale-ip>`).

**Root cause:** Docker Desktop on Windows routes all bind requests through a WSL2
NAT layer. A container bind to a non-loopback address is silently accepted by the
Docker daemon but the host-side proxy only forwards localhost traffic.

### Detection

Run `pmoves/scripts/audit_network_reality.sh` (see PR-B). It cross-checks:
1. `docker inspect` reports binding
2. Host-side PowerShell `TcpClient` probe (with `netstat` fallback) confirms listener
3. Subnet-internal connect from sibling container succeeds

### Workaround pattern

For services needing Tailscale-IP binding on Windows:
```bash
# In docker-compose, set bind to 0.0.0.0 and control access via Tailscale ACLs
# instead of binding to the specific Tailscale IP.
NATS_BIND=0.0.0.0
# ACL-restrict at tailscale layer (pmoves/configs/tailscale-acl-policy.json)
```

For Docker Desktop Windows userspace Tailscale (no TUN device), use
`docker-compose.tailscale.yml` which runs Tailscale in userspace mode
(`--tun=userspace-networking`). This is the authoritative pattern; `extra_hosts:
host.docker.internal:host-gateway` in compose covers Windows/macOS loopback.

**Rule 4 — On Docker Desktop Windows, bind to `0.0.0.0` and ACL-restrict at
the Tailscale layer. Never rely on IP-specific binds on Windows hosts.**

---

## Network-Tier Hardening Anchors (PR-A — LANDED 2026-09-03)

PR-A adds four YAML anchors mirroring the existing service-tier-hardened
anchors. It landed 2026-09-03 under a Known Road grant
(`compose:handoff:network-planes-and-package-sharing-2026-09-03.md`, recorded
in `known-roads.jsonl`) — the `COMPOSE_EDIT=1` override this line used to name
is not the current mechanism; protected-path edits go through Known Roads:

| Anchor | Purpose | Key settings |
|--------|---------|-------------|
| `x-network-internal-only` | Air-gapped internal bridge | `internal: true`, explicit subnet, no DNS servers |
| `x-network-bus-internal-dns` | NATS bus — internal but with external DNS if needed | `internal: true` + `dns: [127.0.0.11]` explicit |
| `x-network-external-bridged` | Internet-capable tier | `internal: false`, explicit subnet |
| `x-network-tailnet-published` | Tailnet-reachable with per-OS portforward notes | `internal: false` + Windows bind caveat |

All four are defined in `docker-compose.yml` and applied to the six
compose-defined networks. `pmoves_external` and `pmoves_db_egress` are
`external: true` — compose adopts them and does not own their `driver`/
`internal`, so they carry no anchor.

Landing it was a pure refactor, verified rather than asserted: `docker compose
--profile "*" config` before and after produced an IDENTICAL networks section
(71 lines both) and an IDENTICAL services section; the only whole-file
difference was the four anchor definitions echoed back as `x-` extension keys.

---

## Service-Tier + Network-Tier Pairing Table

| Service tier anchor | Required networks | Rationale |
|---------------------|-------------------|-----------|
| `tier-data-hardened` | `pmoves_data` | Data stores stay in data tier |
| `tier-api-hardened` | `pmoves_api` | API services stay in API tier |
| `tier-agent-hardened` | `pmoves_bus` + `pmoves_external` | Agents need NATS + LLM |
| `tier-worker-hardened` | `pmoves_data` + `pmoves_bus` | Workers consume data + events |
| `tier-media-hardened` | `pmoves_app` + `pmoves_bus` + `pmoves_external` | Media needs storage + events + model APIs |
| `tier-llm-hardened` | `pmoves_external` only | TensorZero gateway owns all external LLM calls |
| `tier-ui-hardened` | `pmoves_app` | Dashboards in app tier only |

---

## Health & Verification

```bash
# Verify voice stack (includes NATS, Flute, TTS backends):
make -C pmoves voice-health

# Audit port binding reality (PR-B script):
bash pmoves/scripts/audit_network_reality.sh

# Verify NATS bus is accessible from sibling container:
docker run --rm --network pmoves_bus appropriate/nc -zv nats 4222

# Check all network definitions:
docker network ls --filter name=pmoves
```

---

## Related

- `pmoves/docs/operations/FIX_GOTRUE_NETWORK_ISOLATION.md` — incident record (dual-attach precedent)
- `pmoves/docs/DOCKER_DAEMON_HARDENING.md` — daemon level (digest, cosign)
- `pmoves/configs/tailscale-acl-policy.json` — Tailscale ACL rules
- `pmoves/docs/security/PORT_BINDING_MODEL.md` — port binding (localhost-only → mesh-eligible)
- `pmoves/scripts/audit_network_reality.sh` — reality assertion tool (PR-B)
- `pmoves/scripts/claws/with-pmoves-network.sh` — docker run alias enforcement (PR-D)
- Issue #1465 — this audit lane
- Issue #1463 — node provisioning (sequences after this audit)
