Check Docker Compose service deployment status.

This command shows which PMOVES services are currently running, their status, and resource usage.

## Usage

Run this command to:
- See which services are deployed and running
- Check container health and status
- Identify stopped or failed services
- View resource usage (ports, CPU, memory)

## Implementation

Execute the following steps:

1. **Check running services:**
   ```bash
   docker compose ps
   ```

   This shows all services defined in docker-compose.yml with their status.

2. **Get detailed status with resources:**
   ```bash
   docker compose ps --format json | jq '.'
   ```

   Or for human-readable format:
   ```bash
   docker compose ps -a
   ```

3. **Check service logs** for any unhealthy services:
   ```bash
   docker compose logs --tail=50 <service-name>
   ```

4. **Report to user:**
   - Total services defined
   - Services running (✓)
   - Services stopped/failed (✗)
   - Services in unhealthy state
   - Port mappings for running services

## Useful Variations

**List only running services:**
```bash
docker compose ps --filter status=running
```

**Show resource usage:**
```bash
docker stats --no-stream $(docker compose ps -q)
```

**Check specific profile:**
```bash
docker compose --profile agents ps
docker compose --profile workers ps
docker compose --profile monitoring ps
```

## Docker Compose Profiles

PMOVES uses profiles to group services:
- `agents` - Agent Zero, Archon, Mesh Agent
- `workers` - Extract, LangExtract, media analyzers
- `orchestration` - SupaSerch, DeepResearch
- `yt` - PMOVES.YT ingestion pipeline
- `gpu` - GPU-accelerated services
- `monitoring` - Prometheus, Grafana, Loki
- `health` - Wger fitness tracker
- `wealth` - Firefly III finance manager

**Start services by profile:**
```bash
docker compose --profile agents --profile workers up -d
```

## Notes

- Services without a profile run by default
- Use `docker compose logs -f <service>` to follow logs in real-time
- Check individual service health: `curl http://localhost:<port>/healthz`
- Restart unhealthy service: `docker compose restart <service-name>`
- View full docker compose config: `docker compose config`
