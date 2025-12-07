# PMOVES.AI Service Hardening Inventory
**Date**: 2025-12-06
**Purpose**: Track Phase 1 security hardening progress across all 29 services

## Service Categories

### Simple Python Services (16 services)
**Effort**: 1-2 hours each | **Total**: 16-32 hours

1. **gateway** (TensorZero) - Port 3030
   - Status: ✅ Running
   - Hardening: ⏳ Pending
   - Dockerfile: `services/gateway/Dockerfile`

2. **hi-rag-gateway-v2** - Port 8086
   - Status: ✅ Running
   - Hardening: ⏳ Pending
   - Dockerfile: `services/hi-rag-gateway-v2/Dockerfile`

3. **hi-rag-gateway** (legacy) - Port 8089
   - Status: ⏳ Not running
   - Hardening: ⏳ Pending
   - Dockerfile: `services/hi-rag-gateway/Dockerfile`

4. **supaserch** - Port 8099
   - Status: ⏳ Not running
   - Hardening: ⏳ Pending
   - Dockerfile: `services/supaserch/Dockerfile`

5. **deepresearch** - NATS worker
   - Status: ⏳ Not running
   - Hardening: ⏳ Pending
   - Dockerfile: `services/deepresearch/Dockerfile`

6. **extract-worker** - Port 8083
   - Status: ✅ Running
   - Hardening: ⏳ Pending
   - Dockerfile: `services/extract-worker/Dockerfile`

7. **langextract** - Port 8084
   - Status: ✅ Running
   - Hardening: ⏳ Pending
   - Dockerfile: `services/langextract/Dockerfile`

8. **presign** - Port 8088
   - Status: ✅ Running
   - Hardening: ⏳ Pending
   - Dockerfile: `services/presign/Dockerfile`

9. **render-webhook** - Port 8085
   - Status: ✅ Running
   - Hardening: ⏳ Pending
   - Dockerfile: `services/render-webhook/Dockerfile`

10. **publisher** - NATS worker
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/publisher/Dockerfile`

11. **publisher-discord** - Port 8094
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/publisher-discord/Dockerfile`

12. **pdf-ingest** - Port 8092
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/pdf-ingest/Dockerfile`

13. **notebook-sync** - Port 8095
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/notebook-sync/Dockerfile`

14. **retrieval-eval** - Port 8091
    - Status: ✅ Running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/retrieval-eval/Dockerfile`

15. **nats-echo** - NATS utility
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/nats-echo/Dockerfile`

16. **analysis-echo** - NATS worker
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/analysis-echo/Dockerfile`

### GPU Services (3 services)
**Effort**: 3-4 hours each | **Total**: 9-12 hours
**Challenge**: Non-root needs /dev/nvidia* access, video group membership

17. **ffmpeg-whisper** - Port 8078
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/ffmpeg-whisper/Dockerfile`
    - Notes: CUDA multi-stage build, requires video group

18. **media-video** - Port 8079
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/media-video/Dockerfile`
    - Notes: PyTorch CUDA, YOLOv8

19. **media-audio** - Port 8082
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/media-audio/Dockerfile`
    - Notes: HuBERT emotion detection

### Complex Services (3 services)
**Effort**: 3-4 hours each | **Total**: 9-12 hours

20. **agent-zero** - Port 8080 API, 8081 UI
    - Status: ✅ Running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/agent-zero/Dockerfile`
    - Notes: Uses upstream `agent0ai/agent-zero:latest`

21. **archon** - Port 8091 API, 3737 UI
    - Status: ✅ Running
    - Hardening: ✅ **Partially hardened** (user 1000:1000 in compose)
    - Dockerfile: `services/archon/Dockerfile`
    - Notes: Playwright browsers, complex build

22. **pmoves-yt** - Port 8077
    - Status: ⏳ Not running
    - Hardening: ✅ **Partially hardened** (user 1000:1000 in compose)
    - Dockerfile: `services/pmoves-yt/Dockerfile`

### Other Services (7 services)
**Effort**: 1-2 hours each | **Total**: 7-14 hours

23. **mesh-agent** - No HTTP interface
    - Status: ✅ Running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/mesh-agent/Dockerfile`

24. **jellyfin-bridge** - Port 8093
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/jellyfin-bridge/Dockerfile`

25. **channel-monitor** - Port 8097
    - Status: ⏳ Not running
    - Hardening: ✅ **Partially hardened** (user 1000:1000 in compose)
    - Dockerfile: `services/channel-monitor/Dockerfile`

26. **invidious-companion-proxy** - Port varies
    - Status: ✅ Running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/invidious-companion-proxy/Dockerfile`

27. **graph-linker** - NATS worker
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/graph-linker/Dockerfile`

28. **comfy-watcher** - ComfyUI integration
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/comfy-watcher/Dockerfile`

29. **grayjay-plugin-host** - Plugin host
    - Status: ⏳ Not running
    - Hardening: ⏳ Pending
    - Dockerfile: `services/grayjay-plugin-host/Dockerfile`

## Hardening Pattern

### Standard Python Services
```dockerfile
# Add before CMD/ENTRYPOINT
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves
```

### GPU Services
```dockerfile
# CUDA containers need video group
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves -G video --uid=65532 pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves
```

### Docker Compose Changes
```yaml
services:
  service-name:
    user: "65532:65532"
    read_only: true  # Phase 1.2
    tmpfs:           # Phase 1.2
      - /tmp:size=100M,mode=1777
    cap_drop: ["ALL"]
    security_opt:
      - no-new-privileges:true
```

## Progress Tracking

### Phase 1.1: Non-Root Users
- **Simple Python**: 0/16 (0%)
- **GPU Services**: 0/3 (0%)
- **Complex Services**: 0/3 (0% - archon/pmoves-yt have compose user but not Dockerfile)
- **Other Services**: 0/7 (0% - channel-monitor has compose user but not Dockerfile)
- **Total**: 0/29 (0%)

### Phase 1.2: Read-Only Filesystems
- **Total**: 0/29 (0%)

### Phase 1.3: Kubernetes SecurityContext
- **Template**: ✅ Complete (`deploy/k8s/base/pmoves-core-deployment.yaml`)
- **Deployments**: 1/1 (100%)

## Estimated Effort

- **Phase 1.1 Total**: 150-200 hours (3-4 weeks with 2 engineers)
- **Phase 1.2 Total**: 90-135 hours (after Phase 1.1 complete)
- **Grand Total**: 240-335 hours

## Next Steps

1. Start with simple Python services (lowest risk, highest volume)
2. Test each service after hardening with `make verify-all`
3. Commit changes incrementally (batches of 3-5 services)
4. Move to GPU services (require special testing)
5. Handle complex services (Agent Zero, Archon, PMOVES.YT)
6. Complete remaining services
7. Implement Phase 1.2 (read-only FS)
