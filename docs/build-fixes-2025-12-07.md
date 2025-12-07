# Docker Build Fixes - December 6-7, 2025

## Summary

Following Phase 2 Security Hardening completion, we identified and resolved critical Docker build failures across the PMOVES.AI stack. Using a systematic debugging approach, we fixed 3 critical issues that were preventing successful deployment, improving build reliability and service startup success rates.

## Critical Fixes

### 1. DeepResearch - Dockerfile Build Context Mismatch

**Problem**: Build failed with "services: not found" and "contracts: not found" errors during image construction.

**Root Cause**:
- docker-compose.yml configured `context: ./services` for the DeepResearch service
- Dockerfile used absolute paths `COPY services/deepresearch/...` which looked for `services/services/deepresearch/...`
- Unnecessary `COPY contracts` directive for module not imported by DeepResearch

**Fix Applied** (commit 3147c52):
```diff
# In services/deepresearch/Dockerfile
- COPY services/deepresearch/requirements.txt /tmp/deepresearch-requirements.txt
+ COPY deepresearch/requirements.txt /tmp/deepresearch-requirements.txt

- COPY services /app/services
- COPY contracts /app/contracts
+ COPY deepresearch /app/services/deepresearch
```

**Files Modified**: `pmoves/services/deepresearch/Dockerfile`

**Impact**: DeepResearch container now builds successfully and can be deployed alongside other orchestration services.

### 2. Environment File - JSON Value Shell Parsing Error

**Problem**: Shell error `.env.local: line 11: 0.3,: command not found` when loading environment files.

**Root Cause**:
- Unquoted JSON object in environment variable
- Shell interpreted `{"temperature":` as a command to execute

**Before**:
```bash
AGENT_ZERO_DECODING={"temperature": 0.3, "top_p": 0.8}
```

**After**:
```bash
AGENT_ZERO_DECODING='{"temperature": 0.3, "top_p": 0.8}'
```

**Fix Applied** (commit 3147c52):
- Quote all JSON values in `.env.local` and environment templates
- Added documentation reminder that `.env.local` is gitignored and users must apply this pattern

**Files Modified**: Documentation updated; `.env.local` is gitignored (users apply locally)

**Impact**: Environment loading now works correctly for all shell contexts (bash, zsh, sh).

### 3. Container Restart Loop - Missing Contracts Directory

**Problem**: DeepResearch container entered restart loop after successful build, with logs showing "contracts directory not found" errors.

**Root Cause**:
- Application code expected `contracts/` directory to exist at runtime
- Previous fix removed `COPY contracts` but didn't address runtime dependency

**Fix Applied** (commit 4a2a36a):
```diff
# In services/deepresearch/Dockerfile
+ COPY contracts /app/contracts
```

**Files Modified**: `pmoves/services/deepresearch/Dockerfile`

**Impact**: DeepResearch now runs successfully without restart loops.

## Additional Context Issues Resolved

### FFmpeg-Whisper - Permission Denied on Build Context

**Problem**: Build occasionally failed with "permission denied" errors when accessing restricted directories.

**Root Cause**:
- Build context included `jellyfin-ai/redis/appendonlydir` and `jellyfin-ai/neo4j/import` directories with restricted permissions
- Docker build process couldn't read these directories

**Fix Applied** (commit 714681d):
```dockerignore
# In services/ffmpeg-whisper/.dockerignore
jellyfin-ai/
neo4j/
redis/
```

**Files Modified**: Created `pmoves/services/ffmpeg-whisper/.dockerignore`

**Impact**: FFmpeg-Whisper builds now complete reliably without permission errors.

### Media-Audio - Torch/Torchaudio Version Conflicts

**Problem**: Historical dependency conflicts between torch 2.8.0 and torchaudio 2.3.1 causing build failures.

**Root Cause**:
- Incompatible version constraints in requirements.txt
- Newer PyTorch versions require compatible torchaudio versions

**Fix Applied** (Earlier, documented for completeness):
```diff
# In services/media-audio/requirements.txt
-torch==2.3.1
-torchaudio==2.3.1
+torch>=2.5.1
+torchaudio>=2.5.1
```

**Files Modified**: `pmoves/services/media-audio/requirements.txt`

**Impact**: Media-audio service now builds with compatible PyTorch ecosystem versions.

## Debugging Approach

The fixes were applied using a systematic approach:

1. **Build Verification**: Identified services failing to build via docker compose logs
2. **Context Analysis**: Examined docker-compose.yml context settings vs Dockerfile COPY paths
3. **Incremental Testing**: Applied fixes one at a time, verifying each before proceeding
4. **Runtime Validation**: Monitored container logs to catch post-build runtime issues
5. **Documentation**: Captured each fix in git commits and documentation

## Results

### Build Success Metrics

**Before Fixes**:
- DeepResearch: Build failed (context mismatch)
- FFmpeg-Whisper: Intermittent failures (permission errors)
- Media-Audio: Build failed (dependency conflicts)
- Environment loading: Shell parsing errors

**After Fixes**:
- DeepResearch: Builds successfully, runs without restart loops
- FFmpeg-Whisper: Reliable builds with proper .dockerignore
- Media-Audio: Compatible dependency versions
- Environment loading: All JSON values properly quoted

**Files Modified**: 5 total
- `pmoves/services/deepresearch/Dockerfile` (2 commits: context fix, then contracts restoration)
- `pmoves/services/media-audio/requirements.txt` (dependency versions)
- `pmoves/services/ffmpeg-whisper/.dockerignore` (new file)
- Documentation updates (build-fixes-2025-12-06.md)

**Commits**:
- 3147c52: DeepResearch Dockerfile build context and env syntax
- 4a2a36a: DeepResearch container restart loop fix
- 714681d: FFmpeg-Whisper build context scoping
- 65f68f1: Documentation of fixes

## Testing & Validation

### Smoke Tests Available

The PMOVES.AI stack includes comprehensive smoke tests via `make verify-all`:

- **Core Services**: Qdrant, Meilisearch, Neo4j, Presign, Render Webhook
- **Hi-RAG v2**: Hybrid retrieval, reranking, geometry queries
- **Agents**: Agent Zero, Archon (API + UI), headless services
- **Orchestration**: DeepResearch, SupaSerch
- **Monitoring**: Prometheus, Grafana, Loki
- **External**: PMOVES.YT, Channel Monitor, Open Notebook

See `pmoves/docs/SMOKETESTS.md` for complete testing documentation.

### Validation Commands

```bash
# Full stack verification (recommended after fixes)
cd pmoves
make verify-all

# Individual service health checks
curl http://localhost:8098/healthz  # DeepResearch
curl http://localhost:8078/healthz  # FFmpeg-Whisper
curl http://localhost:8082/healthz  # Media-Audio

# Container status
docker ps --filter "name=deepresearch"
docker logs deepresearch --tail 50
```

## Next Steps

1. **Continuous Integration**: Ensure CI/CD pipelines catch build context mismatches early
2. **Documentation Standards**: Establish patterns for JSON environment variables in shell contexts
3. **Build Testing**: Add pre-commit hooks to validate Dockerfile COPY paths match docker-compose contexts
4. **Dependency Management**: Consider Dependabot or Renovate for automated dependency updates (already configured in commit 7bacba2)

## Related Documentation

- **Phase 2 Security**: `docs/phase2-security-hardening-plan.md`
- **Smoke Tests**: `pmoves/docs/SMOKETESTS.md`
- **Service Catalog**: `.claude/context/services-catalog.md`
- **Network Segmentation**: `docs/architecture/network-tier-segmentation.md`
- **Git Organization**: `docs/PMOVES_Git_Organization.md`

## Lessons Learned

### Build Context Awareness
Always align Dockerfile COPY paths with docker-compose context settings:
- `context: .` → Use relative paths from repo root
- `context: ./services` → Use paths relative to services/ directory

### Environment File Quoting
Quote all complex values in shell-sourced environment files:
- JSON objects: Use single quotes `'{"key": "value"}'`
- Arrays: Use single quotes `'["item1", "item2"]'`
- Strings with spaces: Use double quotes `"value with spaces"`

### Incremental Deployment
When fixing build issues:
1. Fix build errors first (COPY paths, dependencies)
2. Then address runtime errors (missing directories, permissions)
3. Validate each fix independently before moving to next issue
4. Document each fix in git commit messages for future reference

---

**Document Version**: 1.0
**Last Updated**: 2025-12-07
**Maintainer**: PMOVES.AI Team
