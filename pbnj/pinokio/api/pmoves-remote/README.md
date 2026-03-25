# PMOVES Remote

Headscale VPN mesh + RustDesk remote desktop for multi-node PMOVES.AI deployment. Connects your local dev machine, AI Lab, and KVM4 production nodes into a secure private network.

## Quick Start

1. Click **Install** to pull Docker images and initialize `env.tier-vpn`
2. Edit `env.tier-vpn` with your Headscale and RustDesk credentials
3. Click **Start** to bring up the VPN mesh + remote desktop server
4. Open the **Headscale Admin** UI at `http://localhost:8096`

## Architecture

```
Z890 (dev) ──┐
5090 (GPU) ──┤── Headscale VPN ──┬── KVM4-1 (API gateway)
             │    (WireGuard)    ├── KVM4-2 (data/storage)
             └───────────────────└── KVM2 (exit proxy)

RustDesk relay enables remote desktop to any mesh node.
```

## Scripts

| Script | Purpose |
|--------|---------|
| `install.js` | Pull Docker images, create `env.tier-vpn` from template |
| `start.js` | Start Headscale + RustDesk via `docker-compose.remote.yml` |
| `status.js` | Show container status + Tailscale mesh peers |

## API Reference

### Headscale Admin — Port 8096

**Curl**

```bash
# List nodes
curl -H "Authorization: Bearer $HEADSCALE_API_KEY" \
  http://localhost:8096/api/v1/node

# Get node by ID
curl -H "Authorization: Bearer $HEADSCALE_API_KEY" \
  http://localhost:8096/api/v1/node/1

# List users
curl -H "Authorization: Bearer $HEADSCALE_API_KEY" \
  http://localhost:8096/api/v1/user
```

**Python**

```python
import requests
import os

api_key = os.environ["HEADSCALE_API_KEY"]
headers = {"Authorization": f"Bearer {api_key}"}

# List nodes
r = requests.get("http://localhost:8096/api/v1/node", headers=headers)
for node in r.json().get("nodes", []):
    print(f"{node['name']}: {node['ipAddresses']}")
```

**JavaScript**

```javascript
const apiKey = process.env.HEADSCALE_API_KEY;

const nodes = await fetch("http://localhost:8096/api/v1/node", {
  headers: { Authorization: `Bearer ${apiKey}` }
}).then(r => r.json());

nodes.nodes?.forEach(n => console.log(`${n.name}: ${n.ipAddresses}`));
```

### Tailscale CLI (Local Machine)

```bash
# Check mesh status
tailscale status

# Ping a node
tailscale ping pmoves-kvm4-1

# SSH to a mesh node
ssh root@pmoves-kvm4-1
```

### RustDesk

RustDesk provides remote desktop access to mesh nodes. Connection details are configured in `env.tier-vpn`:

```bash
# Key environment variables
RUSTDESK_RELAY=your-relay-server
RUSTDESK_KEY=your-public-key
```

## Agent Hints

AI agents can use this launcher to:

- **Check VPN status** — Run `status.js` to see which nodes are online
- **Connect to remote node** — Use Tailscale SSH via `ssh root@pmoves-kvm4-1`
- **List mesh peers** — Run `tailscale status` to see all connected nodes
- **Verify connectivity** — Ping nodes with `tailscale ping <hostname>`
