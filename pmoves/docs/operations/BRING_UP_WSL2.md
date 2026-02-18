# PMOVES.AI WSL2 Bring-Up Guide

**Last Updated:** 2026-02-07
**Target Environment:** Windows Subsystem for Linux 2 (WSL2) with Docker Desktop
**Branch:** PMOVES.AI-Edition-Hardened

## Prerequisites

### Required Software

| Software | Version | Notes |
|----------|---------|-------|
| **WSL2** | Latest | Install via \`wsl --install\` |
| **Docker Desktop** | Latest | Enable WSL2 integration |
| **Git** | 2.40+ | For large file support |
| **Python** | 3.11+ | For CLI tools and scripts |

### Docker Desktop Configuration

**Critical WSL2 Settings:**

1. **Enable WSL2 Integration**
   - Docker Desktop → Settings → Resources → WSL Integration
   - Enable your WSL2 distribution (e.g., Ubuntu-22.04)

2. **Expose Daemon on TCP**
   - Docker Desktop → Settings → Advanced
   - Expose daemon on tcp://localhost:2375 without TLS (optional, for some tools)

3. **Resource Allocation**
   - RAM: 8GB+ minimum, 16GB+ recommended
   - CPUs: 4+ minimum, 8+ recommended
   - Disk: 100GB+ for containers and images

## Known WSL2 Issues and Solutions

### Issue 1: "not a directory" Bind Mount Errors

**Symptom:**
```
Error: not a directory: Are you trying to mount a directory onto a file
```

**Root Cause:** Docker Desktop on WSL2 requires explicit \`--project-directory\` for relative path resolution.

**Solution:** All \`docker compose\` invocations must include \`--project-directory\`:
```bash
docker compose -p pmoves --project-directory $(pwd) up -d
```

This is now handled automatically in the Makefile via the \`$(DC)\` variable.

### Issue 2: Network "Incorrect Label" Errors

**Symptom:**
```
Error: network pmoves_api declared as external, but could not be found
network pmoves_api has incorrect label
```

**Root Cause:** Networks created manually with \`docker network create\` lack Docker Compose labels.

**Solution:** Run \`make clean-networks\` to remove stale networks:
```bash
cd pmoves
make clean-networks
```

This is now automatically run as part of \`make up\`.

### Issue 3: Environment Variable Expansion

**Symptom:** Port mappings or environment variables not expanding correctly.

**Solution:**
- Use \`\${VAR:-default}\` syntax in docker-compose.yml
- For \`docker compose\`, Docker Compose natively handles this expansion
- Don't rely on shell expansion in WSL2

### Issue 4: File System Performance

**Symptom:** Slow operations on bind mounts.

**Solutions:**
1. Place PMOVES.AI in WSL2 filesystem (not \`/mnt/c\`)
2. Use \`wsl2\\localhost\\` from Windows (not \`\\\\wsl$\``)
3. Enable WSL2 metadata caching:
   ```bash
   sudo sh -c 'echo "[experimental]" >> /etc/wsl2.conf'
   sudo sh -c 'echo "metadata=true" >> /etc/wsl2.conf'
   ```

## Bring-Up Procedure

### Step 1: Clone Repository

```bash
# In WSL2 terminal
cd ~
git clone https://github.com/POWERFULMOVES/PMOVES.AI.git
cd PMOVES.AI
git checkout PMOVES.AI-Edition-Hardened
```

### Step 2: Install Dependencies

```bash
cd pmoves
make first-run
```

This will:
- Check required tools (Docker, Python)
- Setup environment files interactively
- Create tier environment files
- Start core services

### Step 3: Configure Provider Keys

At minimum one LLM provider is required:

```bash
# Edit pmoves/env.shared
nano pmoves/env.shared
```

Add at least one:
```bash
OPENAI_API_KEY=sk-...
# OR
GROQ_API_KEY=gsk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 4: Verify Configuration

```bash
cd pmoves
make env-check
```

This will show:
- Supabase key sync status
- Provider API keys configured
- Empty/placeholder value warnings

### Step 5: Start Services

```bash
cd pmoves
make up
```

First run includes automatic network cleanup.

### Step 6: Verify Services

```bash
cd pmoves
make verify-all
```

## Service URLs (WSL2)

| Service | URL | Notes |
|---------|-----|-------|
| **TensorZero UI** | http://localhost:4000 | Model gateway dashboard |
| **TensorZero API** | http://localhost:3030 | Gateway for LLM requests |
| **Grafana** | http://localhost:3000 | Metrics dashboards |
| **Prometheus** | http://localhost:9090 | Metrics query |
| **Hi-RAG v2** | http://localhost:8086 | CPU RAG gateway |
| **Hi-RAG v2 GPU** | http://localhost:8087 | GPU RAG gateway |
| **Agent Zero** | http://localhost:8080 | Agent orchestrator |
| **Supabase Studio** | http://localhost:54323 | Database UI |

## Troubleshooting

### Docker Daemon Not Responding

```bash
# From Windows PowerShell
wsl --shutdown
# Then restart WSL2
```

### Port Already in Use

```bash
# Check what's using the port
netstat -ano | findstr :3030

# Or from WSL2
sudo ss -tulpn | grep 3030
```

### Container Exit Codes

```bash
# Check container logs
docker compose logs tensorzero-gateway
docker compose logs agent-zero
```

### Reset Everything

```bash
cd pmoves
make down          # Stop all services
make clean-networks # Remove networks
docker system prune -a --volumes  # Clean Docker (careful!)
make first-run     # Start fresh
```

## WSL2-Specific Considerations

### Path Mapping

| From Windows | From WSL2 | Notes |
|--------------|-----------|-------|
| \`\\\\wsl$\\Ubuntu\\home\\user\\PMOVES.AI\` | \`~/PMOVES.AI\` | Use WSL2 path for better performance |
| \`http://localhost:3030\` | \`http://localhost:3030\` | Localhost works both ways |
| \`http://172.x.x.x:3030\` | \`http://172.x.x.x:3030\` | WSL2 bridge IP |

### Firewall

Windows Firewall may block inter-container communication. Add rules for:
- Docker Desktop networks
- WSL2 subnet (172.x.x.x)

### GPU Passthrough

For NVIDIA GPU in WSL2:
```powershell
# Install NVIDIA WSL2 drivers
# Download from https://developer.nvidia.com/cuda/wsl
```

Verify GPU access:
```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu nvidia-smi
```

## Additional Resources

- **Main Bring-Up Guide:** \`BRING_UP_GUIDE.md\`
- **Cross-Platform Tasks:** \`CROSS_PLATFORM_TASKS.md\`
- **Tier Architecture:** \`.claude/context/tier-architecture.md\`

## Getting Help

If you encounter issues not covered here:

1. Check \`CROSS_PLATFORM_TASKS.md\` for known issues
2. Run \`make env-check\` to validate configuration
3. Check logs: \`docker compose logs <service>\`
4. Open an issue with:
   - WSL2 version: \`wsl --version\`
   - Docker Desktop version
   - Error message and reproduction steps
