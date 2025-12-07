Start PMOVES services using docker compose.

This command brings up the PMOVES stack with appropriate profiles based on your environment.

## Usage

Run this command to:
- Start core data services (Supabase, Qdrant, Neo4j, Meilisearch, MinIO)
- Bring up workers (extract, langextract, media analyzers)
- Start Hi-RAG gateways (v2 CPU and GPU)
- Launch orchestration services (SupaSerch, DeepResearch, Agent Zero)

## Implementation

Execute the following steps:

1. **Start core services:**
   ```bash
   cd pmoves && make up
   ```

   This brings up:
   - Data layer: Supabase, Qdrant, Neo4j, Meilisearch, MinIO, NATS
   - Workers: Extract, LangExtract
   - Hi-RAG v2 gateways (both CPU and GPU)

2. **Start with GPU acceleration (if available):**
   ```bash
   cd pmoves && make up-gpu
   ```

   Adds GPU-accelerated services:
   - Hi-RAG v2 GPU (port 8087)
   - FFmpeg-Whisper
   - Media-Video Analyzer
   - Media-Audio Analyzer

3. **Comprehensive bring-up with UI:**
   ```bash
   cd pmoves && make bringup-with-ui
   ```

   Full stack including:
   - Supabase, core, agents, externals
   - Monitoring (Prometheus, Grafana, Loki)
   - UI development mode
   - Auto-captures evidence after bring-up

4. **Verify services started successfully:**
   ```bash
   cd pmoves && docker compose ps
   ```

   Check that services show "running" status.

## Common Profiles

PMOVES uses docker compose profiles to group services:

```bash
# Start specific profiles
cd pmoves && COMPOSE_PROFILES=data,workers docker compose up -d

# Available profiles:
# - data: Core data services
# - workers: Processing services
# - gateway: API gateways
# - agents: Agent Zero, Archon, Mesh Agent
# - orchestration: SupaSerch, DeepResearch
# - monitoring: Prometheus, Grafana, Loki
# - gpu: GPU-accelerated services
```

## Configuration

**Environment setup:**

1. Ensure `pmoves/env.shared` exists (created automatically from `env.shared.example`)
2. Set external service flags if using managed services:
   ```bash
   export EXTERNAL_SUPABASE=true  # Skip local Supabase
   export EXTERNAL_NEO4J=true     # Skip local Neo4j
   export EXTERNAL_QDRANT=true    # Skip local Qdrant
   export EXTERNAL_MEILI=true     # Skip local Meilisearch
   ```

**Check environment:**
```bash
cd pmoves && make ensure-env-shared
```

## Troubleshooting

**Services fail to start:**
- Check logs: `cd pmoves && docker compose logs <service-name>`
- Verify ports not in use: `netstat -tlnp | grep <port>`
- Check environment: `cat pmoves/env.shared`

**Out of memory:**
- Reduce services: Start only needed profiles
- Increase Docker memory limit
- Check: `docker stats`

**GPU services fail:**
- Verify NVIDIA drivers: `nvidia-smi`
- Check Docker GPU runtime: `docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi`

## Post-Startup Verification

After bringing up services, always verify health:

```bash
# Quick health check
cd pmoves && make verify-all

# Check individual service
curl http://localhost:8080/healthz  # Agent Zero
curl http://localhost:8086/healthz  # Hi-RAG v2
```

## Notes

- First startup may take several minutes (image pulls, database init)
- Supabase initialization can take 30-60 seconds
- GPU services require NVIDIA runtime and drivers
- Monitoring stack adds overhead, disable if not needed
- Use `make down` to stop all services
- Logs available via: `docker compose logs -f <service>`
