Verify health status of all PMOVES production services.

This command checks the `/healthz` endpoints for all deployed services to ensure the system is operational.

## Usage

Run this command when:
- Starting development to verify infrastructure is running
- Debugging issues to identify failing services
- Before deploying changes to validate system health
- After bringing up services with docker compose

## Implementation

Execute the following steps:

1. **Run the verification script:**
   ```bash
   cd pmoves && make verify-all
   ```

   This executes comprehensive health checks for all services (located in `pmoves/Makefile`).

2. **Alternative: Manual checks** (if make target not available):
   ```bash
   # Agent Coordination
   curl -f http://localhost:8080/healthz  # Agent Zero
   curl -f http://localhost:8091/healthz  # Archon
   curl -f http://localhost:8097/healthz  # Channel Monitor

   # Retrieval & Knowledge
   curl -f http://localhost:8086/healthz  # Hi-RAG v2 CPU
   curl -f http://localhost:8087/healthz  # Hi-RAG v2 GPU
   curl -f http://localhost:8099/healthz  # SupaSerch
   curl -f http://localhost:8098/healthz  # DeepResearch

   # Media Processing
   curl -f http://localhost:8077/healthz  # PMOVES.YT
   curl -f http://localhost:8078/healthz  # FFmpeg-Whisper
   curl -f http://localhost:8079/healthz  # Media-Video Analyzer
   curl -f http://localhost:8082/healthz  # Media-Audio Analyzer
   curl -f http://localhost:8083/healthz  # Extract Worker
   curl -f http://localhost:8084/healthz  # LangExtract
   curl -f http://localhost:8092/healthz  # PDF Ingest
   curl -f http://localhost:8095/healthz  # Notebook Sync

   # Utilities
   curl -f http://localhost:8088/healthz  # Presign
   curl -f http://localhost:8085/healthz  # Render Webhook
   curl -f http://localhost:8093/healthz  # Jellyfin Bridge
   curl -f http://localhost:8094/healthz  # Publisher-Discord
   ```

3. **Report results:**
   - List all healthy services (✓)
   - Highlight any failing services (✗) with service name and port
   - Suggest remediation (check logs, restart service)

## Notes

- Health endpoints check service status + dependency connectivity (NATS, Supabase, etc.)
- Use `-f` flag with curl to fail on non-200 responses
- If services are down, check docker compose: `docker compose ps`
- View logs: `docker compose logs <service-name>`
- Most services are in specific compose profiles (agents, workers, orchestration, etc.)
