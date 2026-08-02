# Pinokio PBNJ Installation Runbook

## Overview
Install Pinokio browser-based automation platform and configure PBNJ (PMOVES Batch Node Jobs) launchers for one-click service deployment.

## Prerequisites

- Hostinger VPS or local machine with Docker running
- PMOVES.AI repo cloned with submodules initialized
- Desktop environment or VNC access (Pinokio runs as a desktop app)

## Steps

### 1. Install Pinokio

Pinokio is a browser-based automation platform. Install on the target machine:

```bash
# Download Pinokio
wget -qO- https://github.com/pinokio-computer/pinokio/releases/latest/download/pinokio-linux-amd64.tar.gz | tar xz

# Or via the Pinokio website for GUI install
# https://pinokio.computer/
```

For headless VPS, use VNC:
```bash
apt-get install -y tigervnc-standalone-server
vncserver :1 -geometry 1920x1080 -depth 24
# Connect via VNC client, then install Pinokio through the browser
```

### 2. Configure PBNJ Launchers

PBNJ launcher configs are at `pbnj/api/pmoves-services/`.

If the submodule is populated:
```bash
cd pbnj/api/pmoves-services/
# Each service has a pinokio.js launcher file
ls *.js
```

Import launchers into Pinokio:
1. Open Pinokio in the browser
2. Navigate to the API scripts directory
3. Pinokio auto-discovers `.js` launcher files
4. Click "Install" on each PMOVES service launcher

### 3. Register PMOVES Services

Each PBNJ launcher should configure:
- Docker container image and compose file
- Environment variables from tier configs
- NATS connection details
- Health check endpoints
- Service dependencies

Example launcher pattern:
```javascript
module.exports = {
  name: "PMOVES Gateway",
  description: "API Gateway with CHIT signing",
  run: async function() {
    // Pull image
    // Configure env from tier files
    // docker compose up -d gateway
    // Verify healthz
  }
}
```

### 4. Test Service Launch

```bash
# Via Pinokio UI: click "Run" on the PMOVES Gateway launcher
# Or verify manually:
curl http://localhost:8080/healthz
```

### 5. Configure Service Dependencies

PMOVES services have a dependency chain:
1. **Tier Data**: Postgres, MinIO, Neo4j (must start first)
2. **Tier LLM**: Ollama or remote model endpoints
3. **Tier API**: Gateway, auth, services
4. **Tier UI**: Next.js frontend

Configure launcher startup order in Pinokio or use Docker Compose `depends_on`.

## Service Launcher Status

| Service | Launcher | Status | Notes |
|---------|----------|--------|-------|
| Gateway | pbnj/api/pmoves-services/ | Check submodule | CHIT signing enabled |
| Postgres | docker-compose | Existing | Tier data |
| MinIO | docker-compose | Existing | Tier data |
| NATS | docker-compose | Existing | Message bus |
| Voice Relay | pmoves/services/voice-relay/ | Needs launcher | JetStream enabled |
| PMOVES-Creator | ComfyUI fork | Needs launcher | 685+ files |

## TODO

- [ ] Verify PBNJ launcher configs are complete in submodule
- [ ] Test end-to-end service launch via Pinokio
- [ ] Document service dependency order
- [ ] Create VNC setup guide for headless VPS
- [ ] Add auto-restart policies to launchers

## References

- Pinokio: https://pinokio.computer/
- PBNJ configs: `pbnj/api/pmoves-services/`
- Docker Compose: `pmoves/docker/docker-compose.yml`
- Tier configs: `pmoves/env.tier-*.example`

Added: 2026-04-17
