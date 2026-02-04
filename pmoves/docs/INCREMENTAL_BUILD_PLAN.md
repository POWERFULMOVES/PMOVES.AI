# Incremental Build Plan - Container Hardening Deployment

**Date:** 2026-02-04
**Purpose:** Build and deploy hardened services incrementally to avoid Docker resource exhaustion

## Overview

After applying container hardening templates (PR #570), **29 services use custom builds** that may need image rebuilds. Building all images simultaneously will crash Docker due to memory/CPU constraints.

## Services with Custom Builds (29 total)

### Priority 1: Core Infrastructure (Build First)
| Service | Purpose | Dependencies |
|---------|---------|--------------|
| nats | Message bus | None |
| supabase-gotrue | Auth | supabase-db |
| supabase-postgrest | API gateway | supabase-db |
| supabase-realtime | Realtime | supabase-db |
| supabase-storage | Storage | supabase-db |
| supabase-studio | UI | supabase-db |
| qdrant | Vector DB | None |
| neo4j | Graph DB | None |
| meilisearch | Search | None |
| minio | Object storage | None |

### Priority 2: Data Processing Workers
| Service | Purpose | Dependencies |
|---------|---------|--------------|
| extract-worker | Embedding indexer | Qdrant, Meilisearch |
| langextract | NLP preprocessing | None |
| pdf-ingest | PDF processing | extract-worker |
| notebook-sync | Note sync | langextract, extract-worker |
| ffmpeg-whisper | Transcription | None |
| media-video | Video analysis | None |
| media-audio | Audio analysis | None |

### Priority 3: Knowledge & Search Services
| Service | Purpose | Dependencies |
|---------|---------|--------------|
| hi-rag-gateway | v1 RAG API | Qdrant, Neo4j, Meilisearch |
| hi-rag-gateway-v2 | v2 RAG API | Qdrant, Neo4j, Meilisearch |
| hi-rag-gateway-gpu | GPU RAG | NVIDIA GPU |
| hi-rag-gateway-v2-gpu | GPU RAG v2 | NVIDIA GPU |
| retrieval-eval | RAG evaluation | Qdrant |

### Priority 4: Agent & Integration Services
| Service | Purpose | Dependencies |
|---------|---------|--------------|
| agent-zero | Agent orchestrator | NATS |
| archon | Supabase agent service | agent-zero, Supabase |
| mesh-agent | Multi-host announcer | NATS |
| botz-gateway | BoTZ gateway | None |
| a2ui-nats-bridge | NATS bridge | NATS |

### Priority 5: Media & Ingestion Services
| Service | Purpose | Dependencies |
|---------|---------|--------------|
| pmoves-yt | YouTube ingestion | FFmpeg-Whisper |
| channel-monitor | YouTube monitoring | pmoves-yt |
| presign | MinIO presigner | MinIO |
| render-webhook | ComfyUI webhook | None |
| model-registry | Model catalog | None |

### Priority 6: Specialized Services
| Service | Purpose | Dependencies |
|---------|---------|--------------|
| deepresearch | Research planner | None |
| supaserch | Multimodal search | deepresearch |
| nats-echo-req | Echo testing | NATS |
| nats-echo-res | Echo testing | NATS |
| publisher-discord | Discord bot | NATS |
| jellyfin-bridge | Jellyfin integration | None |
| gpu-orchestrator | GPU allocation | None |
| evo-controller | Evolution controller | None |

## Incremental Build Commands

### Wave 1: Core Infrastructure (5 images)
```bash
# Build message bus and databases
cd pmoves
docker compose build nats qdrant neo4j meilisearch
```

### Wave 2: Supabase Stack (6 images)
```bash
# Build Supabase services after data tier is up
docker compose build supabase-gotrue supabase-postgrest supabase-realtime supabase-storage supabase-studio
```

### Wave 3: Core Workers (5 images)
```bash
# Build core data processing workers
docker compose build extract-worker langextract pdf-ingest notebook-sync ffmpeg-whisper
```

### Wave 4: Media Workers (2 images)
```bash
# Build media analysis workers
docker compose build media-video media-audio
```

### Wave 5: RAG Services (5 images)
```bash
# Build RAG gateway services
docker compose build hi-rag-gateway hi-rag-gateway-v2 retrieval-eval
```

### Wave 6: Agent Services (4 images)
```bash
# Build agent services
docker compose build agent-zero archon mesh-agent botz-gateway a2ui-nats-bridge
```

### Wave 7: Ingestion & Integration (7 images)
```bash
# Build ingestion and integration services
docker compose build pmoves-yt channel-monitor presign render-webhook model-registry
```

### Wave 8: Specialized Services (7 images)
```bash
# Build specialized services
docker compose build deepresearch supaserch nats-echo-req nats-echo-res publisher-discord jellyfin-bridge
```

### Wave 9: GPU Services (3 images)
```bash
# Build GPU services (only if NVIDIA GPU available)
docker compose build hi-rag-gateway-gpu hi-rag-gateway-v2-gpu gpu-orchestrator
```

## Deployment Strategy

### Local AI Stack (Single Host)
```bash
# 1. Start observability first
make up-obs

# 2. Build and start data tier
docker compose build qdrant neo4j meilisearch
docker compose up -d qdrant neo4j meilisearch

# 3. Build and start message bus
docker compose build nats
docker compose up -d nats

# 4. Build and start workers incrementally
docker compose build extract-worker langextract
docker compose up -d extract-worker langextract

# 5. Build and start services
docker compose build agent-zero archon
docker compose up -d agent-zero archon
```

### Hostinger VPS Deployment
```bash
# 1. Use VPS-optimized compose override
export COMPOSE_FILE=docker-compose.yml:docker-compose.vps.override.yml

# 2. Build on local machine then push to registry
# See: deploy/runners/vps/README.md

# 3. Deploy to VPS via SSH
# See: deploy/scripts/deploy-compose.sh
```

## Resource Management

### Build Resource Limits
```bash
# Limit concurrent builds to avoid OOM
export DOCKER_BUILDKIT=1
export BUILDKIT_STEP_LOG_MAX_SIZE=10485760

# Set memory limits for build
docker buildx build --memory=4g ...
```

### Clean Build Cache Between Waves
```bash
# Optional: Clean build cache between waves if disk space is low
docker builder prune -f
```

## Validation

After each wave, validate:
```bash
# Check services are running
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Run health checks
make verify-all

# Check logs for errors
docker compose logs --tail=50
```

## Troubleshooting

### Docker Build Crash Symptoms
- Build hangs indefinitely
- "no space left on device" errors
- OOM killer messages in dmesg
- Docker daemon becomes unresponsive

### Recovery
```bash
# Stop all builds
docker compose down

# Clean build cache
docker builder prune -a -f

# Restart Docker daemon
sudo systemctl restart docker

# Resume with next wave
```

## Notes

- **29 custom build services** identified
- **Pre-built images** (GHCR, Docker Hub) don't need rebuild
- **GPU services** only build if NVIDIA GPU available
- **VPS builds** should happen locally then push images
- **Observability stack** has its own compose file

## Next Steps

1. Update CI/CD to build in waves
2. Add build status tracking
3. Create smoke tests for each wave
4. Document build times for each wave
