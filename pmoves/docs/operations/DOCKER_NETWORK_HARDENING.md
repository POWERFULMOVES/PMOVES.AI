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

**Rule 1 — All internal networks air-gap from internet.** Only `pmoves_external`
carries outbound internet access. Services not needing LLM API calls or pip installs
must never appear in `pmoves_external`.

**Rule 2 — Subnets are permanent.** Never renumber them; NATS auth, TLS SANs, and
firewall rules are baked against these CIDRs.

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
2. Host-side `netstat`/`Get-NetTCPConnection` confirms listener
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

## Pending: Network-Tier Hardening Anchors (PR-A)

PR-A (pending operator action — requires `COMPOSE_EDIT=1` override on
damage-control hook) will add four YAML anchors mirroring the existing 11
service-tier-hardened anchors:

| Anchor | Purpose | Key settings |
|--------|---------|-------------|
| `x-network-internal-only` | Air-gapped internal bridge | `internal: true`, explicit subnet, no DNS servers |
| `x-network-bus-internal-dns` | NATS bus — internal but with external DNS if needed | `internal: true` + `dns: [127.0.0.11]` explicit |
| `x-network-external-bridged` | Internet-capable tier | `internal: false`, explicit subnet |
| `x-network-tailnet-published` | Tailnet-reachable with per-OS portforward notes | `internal: false` + Windows bind caveat |

Until PR-A lands, the network definitions in compose are functional but undocumented
as anchors. The rules in this doc apply regardless.

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
