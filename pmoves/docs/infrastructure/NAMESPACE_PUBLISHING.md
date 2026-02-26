# PMOVES.AI Namespace Publishing Standard

**Created:** 2026-02-16
**Status:** Production standard for mesh identity

---

## Overview

Namespace publishing provides runtime identity for PMOVES services. Each service
announces its project, tier, branch, and peer expectations via NATS, enabling:

- **Multi-host discovery** across Tailscale mesh
- **Tier-aware routing** (agent requests go to agent-tier nodes)
- **Branch provenance** (know which branch a running service was built from)
- **Peer health monitoring** (detect missing expected services)

---

## Environment Variable Standard

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SERVICE_SLUG` | Yes | Unique service identifier (DNS-safe) | `agent-zero` |
| `SERVICE_TIER` | Yes | One of: data, api, llm, worker, media, agent, ui | `agent` |
| `SERVICE_MODE` | No | `docked` (in PMOVES.AI) or `standalone` | `docked` |
| `COMPOSE_PROJECT_NAME` | No | Docker Compose project name | `pmoves` |
| `GIT_BRANCH` | No | Git branch for build provenance | `PMOVES.AI-Edition-Hardened` |
| `PEER_EXPECTATIONS` | No | Comma-separated expected peer slugs | `archon,nats,supabase` |
| `NODE_NAME` | No | Host identifier (defaults to hostname) | `vps-01` |
| `NODE_CAPABILITIES` | No | Comma-separated capability tags | `clip,clap,t5,rag,agent` |

---

## v2 Announcement Schema

Published to `mesh.node.announce.v2` every 15 seconds:

```json
{
  "type": "mesh.node.announce.v2",
  "node": "vps-01",
  "caps": {
    "clip": true,
    "clap": true,
    "t5": true,
    "rag": true,
    "agent": true
  },
  "host": "100.64.1.5",
  "tailscale_ip": "100.64.1.5",
  "mode": "docked",
  "ts": 1739750400,
  "namespace": {
    "project": "pmoves",
    "tier": "agent",
    "branch": "PMOVES.AI-Edition-Hardened"
  },
  "slug": "agent-zero",
  "peers": ["archon", "hi-rag-gateway-v2", "nats"],
  "health": {
    "status": "announcing"
  }
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `mesh.node.announce.v2` |
| `node` | string | Host/node name |
| `caps` | object | Capability flags (true/false) |
| `host` | string | Reachable IP (Tailscale preferred, then local) |
| `tailscale_ip` | string | Tailscale IPv4 if available, null otherwise |
| `mode` | string | `docked` or `standalone` |
| `ts` | integer | Unix timestamp of announcement |
| `namespace.project` | string | Compose project name |
| `namespace.tier` | string | Service tier classification |
| `namespace.branch` | string | Git branch for provenance |
| `slug` | string | Unique service identifier |
| `peers` | array | Expected peer service slugs |
| `health.status` | string | Current health state |

---

## Backward Compatibility

The mesh agent publishes to **both** NATS subjects on each cycle:

| Subject | Schema | Purpose |
|---------|--------|---------|
| `mesh.node.announce.v1` | Original (no namespace) | Existing consumers |
| `mesh.node.announce.v2` | Extended (with namespace) | New namespace-aware consumers |

Consumers should subscribe to v2 if they need namespace data, or v1 for basic
node discovery. The v1 schema is a strict subset of v2.

---

## Deployment Modes

### Docked Mode (Production)

Service runs inside the full PMOVES.AI Docker Compose stack:

```yaml
environment:
  SERVICE_SLUG: agent-zero
  SERVICE_TIER: agent
  SERVICE_MODE: docked
  COMPOSE_PROJECT_NAME: pmoves
  GIT_BRANCH: PMOVES.AI-Edition-Hardened
  PEER_EXPECTATIONS: archon,nats,supabase,tensorzero
```

### Standalone Mode (Development)

Service runs independently in its own repository:

```yaml
environment:
  SERVICE_SLUG: agent-zero
  SERVICE_TIER: agent
  SERVICE_MODE: standalone
  COMPOSE_PROJECT_NAME: pmoves-dev
  PEER_EXPECTATIONS: nats
```

### Composable Body Mode

Service runs inside a composed "body" (e.g., PMOVES-DoX):

```yaml
environment:
  SERVICE_SLUG: agent-zero
  SERVICE_TIER: agent
  SERVICE_MODE: docked
  COMPOSE_PROJECT_NAME: pmoves-dox
  GIT_BRANCH: PMOVES.AI-Edition-Hardened
  PEER_EXPECTATIONS: hi-rag-gateway,botz-gateway
```

---

## Subscribing to Announcements

### Python (nats-py)

```python
import json
import nats

async def on_announce(msg):
    data = json.loads(msg.data.decode())
    ns = data.get("namespace", {})
    print(f"Node {data['slug']} | tier={ns.get('tier')} | branch={ns.get('branch')}")

nc = nats.NATS()
await nc.connect("nats://nats:pmoves@nats:4222")
await nc.subscribe("mesh.node.announce.v2", cb=on_announce)
```

### CLI (nats-cli)

```bash
nats sub "mesh.node.announce.v2" --count 5
```

---

## See Also

- `pmoves/services/mesh-agent/main.py` - Mesh agent implementation
- `.claude/context/modular-architecture.md` - Body parts architecture
- `.claude/context/nats-subjects.md` - Full NATS subject catalog
- `pmoves/docs/BRANCH_STRATEGY.md` - Branch model documentation
