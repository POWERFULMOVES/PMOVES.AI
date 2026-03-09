# Tailscale Mesh Distributed Deployment

Example configuration for deploying PMOVES submodules across different physical networks connected via Tailscale VPN mesh.

## Scenario

- **DoX** at home office (100.64.1.20) - RTX 4090 GPU
- **BoTZ** at remote office (100.64.1.30) - RTX 5090 GPU
- **Tokenism** at data center (100.64.1.40) - CPU only
- **TensorZero + NATS** at home office (100.64.1.10)
- **Jetson Orin #1** edge device (100.64.1.50) - Edge inference
- **Jetson Orin #2** edge device (100.64.1.60) - Edge inference

## Network Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Tailscale Mesh VPN                                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Home Office Network                    Remote Office Network              │
│   ┌─────────────────┐                    ┌─────────────────┐               │
│   │ 100.64.1.10     │                    │ 100.64.1.30     │               │
│   │ pmoves-primary  │◄──────────────────►│ pmoves-botz     │               │
│   │ TensorZero+NATS │                    │ BoTZ Gateway    │               │
│   └────────┬────────┘                    └─────────────────┘               │
│            │                                                                │
│   ┌────────▼────────┐                                                       │
│   │ 100.64.1.20     │                                                       │
│   │ pmoves-dox      │                                                       │
│   │ DoX Document    │                                                       │
│   └─────────────────┘                                                       │
│                                                                             │
│   Data Center                            Edge Devices                       │
│   ┌─────────────────┐     ┌─────────────────┐  ┌─────────────────┐         │
│   │ 100.64.1.40     │     │ 100.64.1.50     │  │ 100.64.1.60     │         │
│   │ pmoves-tokenism │     │ pmoves-orin-1   │  │ pmoves-orin-2   │         │
│   │ Tokenism        │     │ Jetson Orin     │  │ Jetson Orin     │         │
│   └─────────────────┘     └─────────────────┘  └─────────────────┘         │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. Tailscale Setup

Install Tailscale on each machine:

```bash
# Linux
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Docker (using sidecar)
# Handled by docker-compose with --profile tailscale
```

### 2. Generate Auth Key

**Option A: Managed Tailscale (cloud service)**
1. Go to Tailscale Admin Console
2. Settings → Keys → Generate auth key
3. Enable "Reusable" and "Ephemeral" as needed
4. Save the key as `TAILSCALE_AUTHKEY`

**Option B: Self-Hosted Headscale (PMOVES.AI parent)**

If connecting to the parent PMOVES.AI Headscale control plane:

1. Access the parent Headscale at `https://headscale.pmoves.local:8096`
2. Generate a pre-auth key:
   ```bash
   # On the Headscale server
   headscale preauthkeys create --user pmoves --reusable
   ```
3. Configure your env file:
   ```bash
   TAILSCALE_AUTHKEY=<preauthkey-from-headscale>
   TAILSCALE_LOGIN_SERVER=https://headscale.pmoves.local:8096
   ```
4. The Tailscale sidecar will connect to Headscale instead of the cloud service

### 3. TLS Certificates

Generate certificates with Tailscale hostnames:

```bash
cd PMOVES-DoX/backend/nats-config

# Edit generate-certs.sh to add Tailscale SANs:
# DNS.3 = pmoves-dox.tailnet-name.ts.net
# IP.2 = 100.64.1.20

./generate-certs.sh
```

## Setup

### 1. Home Office - Primary (100.64.1.10)

Deploy TensorZero and NATS:

```bash
cd PMOVES.AI
docker compose up -d tensorzero nats
```

### 2. Home Office - DoX (100.64.1.20)

```bash
cd PMOVES-DoX
cp ../pmoves/examples/distributed/tailscale/dox.env .env.distributed

# Start with Tailscale sidecar
docker compose -f docker-compose.yml -f docker-compose.distributed.yml \
  --profile tailscale --env-file .env.distributed up -d
```

### 3. Remote Office - BoTZ (100.64.1.30)

```bash
cd PMOVES-BoTZ
cp ../pmoves/examples/distributed/tailscale/botz.env .env

docker compose -f docker-compose.yml -f docker-compose.distributed.yml \
  --profile tailscale --profile cipher --profile tools up -d
```

### 4. Data Center - Tokenism (100.64.1.40)

```bash
cd PMOVES-ToKenism-Multi
cp ../pmoves/examples/distributed/tailscale/tokenism.env .env

docker compose --profile tailscale up -d
```

### 5. Edge Devices - Jetson Orin (100.64.1.50, 100.64.1.60)

```bash
# On each Jetson
tailscale up --authkey=$TAILSCALE_AUTHKEY

cd PMOVES-DoX
docker compose -f docker-compose.jetson-orin.yml up -d
```

## Verification

### Check Tailscale Status

```bash
tailscale status
# Should show all nodes connected
```

### Test Connectivity

```bash
# From any node
ping pmoves-dox.tailnet-name.ts.net
ping pmoves-botz.tailnet-name.ts.net

# Test services
curl http://100.64.1.20:8484/healthz
curl http://100.64.1.30:2091/health
curl http://100.64.1.40:5000/health
```

## Tailscale Features

### MagicDNS

Use Tailscale hostnames instead of IPs:

```bash
# Instead of
NATS_HOST=100.64.1.10

# Use
NATS_HOST=pmoves-primary.tailnet-name.ts.net
```

### Subnet Routes

To expose entire Docker networks:

```bash
# On container host
tailscale up --advertise-routes=172.31.0.0/16

# On other hosts
tailscale up --accept-routes
```

### Exit Nodes

Route all traffic through a specific node:

```bash
# On exit node
tailscale up --advertise-exit-node

# On client
tailscale up --exit-node=pmoves-exit
```

## Troubleshooting

### Node Not Visible

```bash
# Check Tailscale is running
systemctl status tailscaled

# Re-authenticate
tailscale up --reset
```

### Connection Timeout

```bash
# Check firewall
sudo ufw allow 41641/udp  # Tailscale port

# Check MTU issues
ping -M do -s 1400 pmoves-dox
```

### Docker Sidecar Issues

```bash
# Check Tailscale container
docker logs pmoves-dox-tailscale

# Verify /dev/net/tun exists
ls -l /dev/net/tun
```
