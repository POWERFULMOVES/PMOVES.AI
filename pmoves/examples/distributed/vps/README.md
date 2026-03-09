# VPS Distributed Deployment

Example configuration for deploying PMOVES submodules with a hybrid VPS and home network setup.

## Scenario

**Hostinger VPS Cluster:**
- **KVM4-1** - API Gateway (BoTZ MCP Gateway, reverse proxy)
- **KVM4-2** - Data Services (DoX Backend, NATS)
- **KVM2** - Exit Node (Tailscale exit node)

**Home Network:**
- **GPU Workstations** - Tokenism, local inference, development

## Network Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          Hostinger KVM Cluster                              │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐      ┌─────────────────┐     ┌──────────────────┐    │
│   │ KVM4-1          │      │ KVM4-2          │     │ KVM2             │    │
│   │ vps1.pmoves.io  │      │ vps2.pmoves.io  │     │ exit.pmoves.io   │    │
│   │ ┌─────────────┐ │      │ ┌─────────────┐ │     │ ┌──────────────┐ │    │
│   │ │ BoTZ Gateway│ │      │ │ DoX Backend │ │     │ │ Tailscale    │ │    │
│   │ │   :2091     │ │      │ │   :8484     │ │     │ │ Exit Node    │ │    │
│   │ ├─────────────┤ │      │ ├─────────────┤ │     │ └──────────────┘ │    │
│   │ │ Nginx Proxy │ │      │ │ NATS + TLS  │ │     │                  │    │
│   │ │   :443      │ │      │ │   :4222     │ │     │                  │    │
│   │ └─────────────┘ │      │ └─────────────┘ │     │                  │    │
│   │  4 vCPU / 8GB   │      │  4 vCPU / 8GB   │     │  2 vCPU / 4GB    │    │
│   └────────┬────────┘      └────────┬────────┘     └────────┬─────────┘    │
│            │                        │                       │               │
│            └────────────────────────┼───────────────────────┘               │
│                                     │                                       │
│                              Tailscale Mesh                                │
│                                     │                                       │
├─────────────────────────────────────┼───────────────────────────────────────┤
│                              Home Network                                   │
│                                     │                                       │
│   ┌─────────────────────────────────▼───────────────────────────────────┐  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │  │
│   │  │ RTX 5090     │  │ RTX 4090     │  │ Jetson Orin  │               │  │
│   │  │ Tokenism     │  │ Dev/Testing  │  │ Edge Infer.  │               │  │
│   │  │   :5000      │  │   :8484      │  │   :8484      │               │  │
│   │  └──────────────┘  └──────────────┘  └──────────────┘               │  │
│   │              GPU Workstations (192.168.1.0/24)                       │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

## VPS Specifications (Hostinger KVM)

| Server | vCPU | RAM | Storage | Purpose |
|--------|------|-----|---------|---------|
| KVM4-1 | 4 | 8GB | 100GB | API Gateway |
| KVM4-2 | 4 | 8GB | 200GB | Data Services |
| KVM2 | 2 | 4GB | 50GB | Exit Node |

## Prerequisites

### 1. VPS Initial Setup

On each VPS:

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Install Docker Compose v2
apt install docker-compose-plugin

# Configure firewall
ufw allow 22/tcp    # SSH
ufw allow 443/tcp   # HTTPS
ufw allow 4222/tcp  # NATS (restrict to home IP)
ufw enable
```

### 2. Tailscale Mesh Setup

On KVM4-1 and KVM4-2:

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Join mesh with tagged auth key (tagged keys auto-disable key expiry)
# Generate at https://login.tailscale.com/admin/settings/keys
tailscale up --auth-key tskey-xxx --hostname <pmoves-kvm4-1|pmoves-kvm4-2> --accept-routes --accept-dns
```

On KVM2 (exit node), also enable IP forwarding and advertise:

```bash
# Enable IP forwarding
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1
cat > /etc/sysctl.d/99-tailscale-exit-node.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF

# Advertise as exit node
tailscale up --auth-key tskey-xxx --hostname pmoves-kvm2 --advertise-exit-node --accept-routes --accept-dns

# Approve exit node in admin console: https://login.tailscale.com/admin/machines
```

### 3. Let's Encrypt Certificates

On KVM4-1 (API Gateway):

```bash
apt install certbot

# Get certificates
certbot certonly --standalone -d api.pmoves.io
certbot certonly --standalone -d dox.pmoves.io
```

## Deployment

### KVM4-1 - API Gateway

```bash
cd /opt/pmoves
git clone https://github.com/POWERFULMOVES/PMOVES-BoTZ.git
cd PMOVES-BoTZ

cp /path/to/examples/vps/kvm4-1.env .env
cp /path/to/examples/vps/nginx-reverse-proxy.conf /etc/nginx/sites-available/pmoves

docker compose -f docker-compose.yml -f docker-compose.distributed.yml up -d
```

### KVM4-2 - Data Services

```bash
cd /opt/pmoves
git clone https://github.com/POWERFULMOVES/PMOVES-DoX.git
cd PMOVES-DoX

cp /path/to/examples/vps/kvm4-2.env .env.distributed

# Generate TLS certificates for NATS
./backend/nats-config/generate-certs.sh

docker compose -f docker-compose.yml -f docker-compose.distributed.yml \
  --env-file .env.distributed up -d
```

### Home Network - Tokenism

```bash
cd ~/PMOVES-ToKenism-Multi
cp /path/to/examples/vps/home-tokenism.env .env

# Verify Tailscale mesh connectivity
tailscale status
tailscale ping pmoves-kvm4-2

docker compose up -d
```

## Nginx Reverse Proxy Configuration

On KVM4-1, configure Nginx as API gateway:

```nginx
# /etc/nginx/sites-available/pmoves

upstream botz_gateway {
    server 127.0.0.1:2091;
}

upstream dox_backend {
    server kvm4-2.internal:8484;  # Internal VPS network
}

server {
    listen 443 ssl http2;
    server_name api.pmoves.io;

    ssl_certificate /etc/letsencrypt/live/api.pmoves.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.pmoves.io/privkey.pem;

    # BoTZ MCP Gateway
    location /mcp {
        proxy_pass http://botz_gateway;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /call {
        proxy_pass http://botz_gateway;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://botz_gateway;
    }
}

server {
    listen 443 ssl http2;
    server_name dox.pmoves.io;

    ssl_certificate /etc/letsencrypt/live/dox.pmoves.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dox.pmoves.io/privkey.pem;

    # DoX Backend API
    location / {
        proxy_pass http://dox_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;  # Long timeout for PDF processing
    }
}
```

## Security Considerations

### 1. Firewall Rules

```bash
# KVM4-1 (API Gateway)
ufw allow from 192.168.1.0/24 to any port 2091  # BoTZ from home
ufw allow 443/tcp                                 # Public HTTPS

# KVM4-2 (Data Services) — allow traffic from Tailscale interface
ufw allow in on tailscale0 to any port 8484       # DoX from Tailscale mesh
ufw allow in on tailscale0 to any port 4222       # NATS from Tailscale mesh
```

### 2. Rate Limiting

Add to Nginx:

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

location /call {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://botz_gateway;
}
```

### 3. JWT Authentication

All VPS deployments require JWT authentication:

```bash
# Generate strong secret
openssl rand -hex 32 > jwt_secret.txt

# Set in all .env files
SUPABASE_JWT_SECRET=$(cat jwt_secret.txt)
```

## Monitoring

### Health Check Script

```bash
#!/bin/bash
# /opt/pmoves/healthcheck.sh

check_service() {
    curl -sf "$1" > /dev/null && echo "✓ $2" || echo "✗ $2"
}

echo "=== PMOVES Health Check ==="
check_service "http://localhost:2091/health" "BoTZ Gateway"
check_service "http://kvm4-2.internal:8484/healthz" "DoX Backend"
check_service "http://kvm4-2.internal:8223/healthz" "NATS"
```

### Prometheus Metrics

Configure Prometheus to scrape all services:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'botz'
    static_configs:
      - targets: ['kvm4-1.internal:2091']
  - job_name: 'dox'
    static_configs:
      - targets: ['kvm4-2.internal:8484']
```

## Troubleshooting

### VPS Cannot Reach Home Network

1. Check Tailscale status: `tailscale status`
2. Ping the target node: `tailscale ping pmoves-kvm4-2`
3. Check key expiry: `tailscale debug key-expiry`
4. Verify routing: `ip route show`

### SSL Certificate Issues

```bash
# Renew certificates
certbot renew

# Verify certificate
openssl s_client -connect api.pmoves.io:443
```

### High Latency

1. Check VPS network: `mtr home-ip`
2. Consider moving services closer together
3. Enable HTTP/2 in Nginx

## Cost Optimization

- **KVM4 servers**: €9.99/month each
- **KVM2 server**: €5.99/month
- **Total**: ~€26/month

Consider:
- Use spot/preemptible instances for non-critical workloads
- Scale down KVM2 if exit node not needed
- Use Cloudflare for SSL termination (free tier)
