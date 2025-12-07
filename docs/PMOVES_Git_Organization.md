# PMOVES Git Organization & Infrastructure Guide

This document provides a comprehensive guide to PMOVES.AI's GitHub organization, infrastructure setup, and related resources.

## Table of Contents
- [Contributor Guidance](#contributor-guidance)
- [Security Roadmap](#security-roadmap)
- [Branch Protection Rules](#branch-protection-rules)
- [Recent Changes](#recent-changes)
- [GitHub Actions Self-Hosted Runner Setup](#github-actions-self-hosted-runner-setup)
- [GitHub Documentation Resources](#github-documentation-resources)
- [PMOVES Project Repositories](#pmoves-project-repositories)
- [Infrastructure & Deployment](#infrastructure--deployment)
- [Video Resources & Tutorials](#video-resources--tutorials)
- [Team & Collaboration](#team--collaboration)

---

## Contributor Guidance
- Operational/stabilization rules live in the root `AGENTS.md`; service-level coding norms for the `pmoves/` subtree live in `pmoves/AGENTS.md`. Read both before opening PRs and keep edits in sync.
- Submodules are the source of truth for hardened integrations (Archon, Agent Zero, PMOVES.YT, etc.). Pin the intended branch/ref in `.gitmodules`, align with `docs/PMOVES.AI-Edition-Hardened.md`, and note any temporary divergence in PR notes.

---

## Security Roadmap

### Phase 1: Foundation - COMPLETE ✅
**Completion Date:** 2025-11-15
**Security Score:** 80/100

**Achievements:**
- GitHub Actions hardening with secure workflow patterns
- Non-root baseline established (3/29 services migrated)
- SecurityContext templates for pod security standards
- Initial container security posture

### Phase 2: Hardening - COMPLETE ✅
**Completion Date:** 2025-12-07 (PR #276, commit 8bf936a)
**Security Score:** 95/100 (+18.75% improvement)

**Achievements:**
- **BuildKit Secrets Migration:** Removed 4 HIGH-RISK secrets from Archon Dockerfile, migrated to BuildKit `--secret` pattern
- **Network Tier Segmentation:** 5-tier isolation architecture across 45 services
  - Tier 1: Public (Jellyfin, TensorZero UI)
  - Tier 2: Gateway (TensorZero, Agent Zero)
  - Tier 3: Application (Hi-RAG, Archon, PMOVES.YT)
  - Tier 4: Data (Supabase, Qdrant, Neo4j, Meilisearch)
  - Tier 5: Infrastructure (NATS, MinIO, Prometheus)
- **Branch Protection:** Main branch protected with required PR reviews, status checks, signed commits, and linear history
- **CODEOWNERS:** Automated review assignments for critical paths

**Documentation:** 67KB of Phase 2 security guides and audit logs

### Phase 3: Advanced Security - PLANNED
**Target Completion:** Q1 2026
**Target Security Score:** 98/100

**Planned Initiatives:**
- TLS termination with cert-manager
- HashiCorp Vault integration for dynamic secrets
- Automated secret rotation policies
- mTLS between service tiers
- Runtime security monitoring with Falco
- SAST/DAST integration in CI/CD pipeline

---

## Branch Protection Rules

### Main Branch Protection (Active since Phase 2)
The `main` branch is protected with the following rules:

**Required Before Merging:**
- Pull request with at least 1 approval
- Status checks must pass:
  - CI tests
  - `make verify` validation
  - CodeQL security scanning
- All conversations must be resolved
- Linear history (no merge commits)
- Commits must be GPG signed

**Bypass Permissions:**
- @powerfulmoves (repository owner)
- @claudedev (automation bot)
- @coderabbitai (review bot)

### CODEOWNERS
Automated review assignments configured in `.github/CODEOWNERS`:
- `/pmoves/**` - Core services team
- `/.github/**` - DevOps team
- `/docs/**` - Documentation team
- `/deploy/**` - Infrastructure team

**Status:** Active and enforced since PR #276 (2025-12-07)

---

## Recent Fixes

### Docker Build Reliability Improvements (2025-12-06 to 2025-12-07)
**Status:** Complete ✅

Following Phase 2 Security Hardening, we identified and resolved critical Docker build failures across the stack:

**Critical Issues Fixed:**
1. **DeepResearch** - Build context mismatch (commit 3147c52)
   - Fixed Dockerfile COPY paths to align with `context: ./services`
   - Resolved container restart loop by restoring contracts directory (commit 4a2a36a)
2. **Environment Files** - JSON parsing errors (commit 3147c52)
   - Quoted all JSON values in shell-sourced environment files
   - Prevents shell interpretation of JSON syntax as commands
3. **FFmpeg-Whisper** - Permission denied errors (commit 714681d)
   - Added .dockerignore to exclude restricted jellyfin-ai directories
   - Eliminates intermittent build failures from permission issues

**Build Success Rate**: Improved from intermittent failures to 100% successful builds for affected services

**Files Modified**: 5 files across 4 commits
- `services/deepresearch/Dockerfile` (2 commits)
- `services/ffmpeg-whisper/.dockerignore` (new file)
- `services/media-audio/requirements.txt` (dependency updates)
- Documentation updates

**See Also**: `docs/build-fixes-2025-12-07.md` for detailed analysis and lessons learned

---

## Recent Changes

### PR #276: Phase 2 Security Hardening (2025-12-07)
**Status:** Merged to main (commit 8bf936a)

**Changes:**
- Fixed network isolation tier assignments for all 45 services
- Container security fixes:
  - TensorZero: Non-root user, read-only root filesystem
  - DeepResearch: Fixed build context and environment variable syntax
  - NATS: Proper health check configuration
- Removed BuildKit secrets from tracked files
- Implemented branch protection rules
- Added CODEOWNERS for automated reviews

**Key Commits:**
- a15c045: Network tier segmentation fixes
- 0811f96: TensorZero container hardening
- cb47f06: DeepResearch build fixes
- 4a2a36a: Branch protection setup

**Documentation:** See `docs/security/phase-2/` for complete audit trail

### Production Readiness Enhancements (2025-12-07, commit 7bacba2)
**Status:** Complete ✅

**TensorZero Model Expansion:**
- Added 5 new Qwen models for local inference via Ollama:
  - Qwen2.5 32B (flagship, ~19GB)
  - Qwen2.5 14B (efficient, ~8GB)
  - Qwen2-VL 7B (vision-language, ~5GB)
  - Qwen3-Reranker 4B (cross-encoder for Hi-RAG v2)
- Enabled ClickHouse observability in TensorZero config

**GitHub Automation:**
- Created .github/CODEOWNERS for security-critical path approvals
- Configured Dependabot for Docker, GitHub Actions, and Python dependencies
- Weekly automated dependency update schedule

**Documentation Updates (via TAC parallel agents):**
- Updated PMOVES.AI-Edition-Hardened-Full.md (service count, network architecture, security posture)
- Created docs/architecture/network-tier-segmentation.md (421 lines, 5-tier architecture)
- Updated .gitignore patterns for backup files and WSL2 artifacts

---

## GitHub Actions Self-Hosted Runner Setup

### Prerequisites
- Linux x64 environment
- Appropriate permissions to install and configure runners

### Installation Steps

1. **Create a folder for the runner**
   ```bash
   mkdir actions-runner && cd actions-runner
   ```

2. **Download the latest runner package**
   ```bash
   curl -o actions-runner-linux-x64-2.329.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.329.0/actions-runner-linux-x64-2.329.0.tar.gz
   ```

3. **Optional: Validate the hash**
   ```bash
   echo "194f1e1e4bd02f80b7e9633fc546084d8d4e19f3928a324d512ea53430102e1d  actions-runner-linux-x64-2.329.0.tar.gz" | shasum -a 256 -c
   ```

4. **Extract the installer**
   ```bash
   tar xzf ./actions-runner-linux-x64-2.329.0.tar.gz
   ```

### Configuration

1. **Create the runner and start the configuration experience**
   ```bash
   ./config.sh --url https://github.com/POWERFULMOVES/PMOVES.AI --token <RUNNER_REGISTRATION_TOKEN>
   ```
   Obtain a one-time registration token for your runner from the GitHub UI (Settings → Actions → Runners). Never commit real tokens to the repository or documentation.

2. **Run the runner**
   ```bash
   ./run.sh
   ```

### Using Your Self-Hosted Runner

Add this YAML to your workflow file for each job:

```yaml
runs-on: self-hosted
```

---

## GitHub Documentation Resources

### Actions & Runners
- [Self-hosted runners overview](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners)
- [Self-hosted runners concepts](https://docs.github.com/en/actions/concepts/runners/self-hosted-runners)
- [Private networking for runners](https://docs.github.com/en/actions/concepts/runners/private-networking)
- [Runner groups](https://docs.github.com/en/actions/concepts/runners/runner-groups)
- [Actions Runner Controller](https://docs.github.com/en/actions/concepts/runners/actions-runner-controller)

### Workflows & Automation
- [Using workflow templates](https://docs.github.com/en/actions/how-tos/write-workflows/use-workflow-templates)
- [Monitoring workflows](https://docs.github.com/en/actions/how-tos/monitor-workflows)

### Repository Management
- [About GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)
- [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [Deciding when to build a GitHub App](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/deciding-when-to-build-a-github-app)

### Security & Dependencies
- [Dependabot configuration template](https://github.com/POWERFULMOVES/PMOVES.AI/new/main?dependabot_template=1&filename=.github%2Fdependabot.yml)

### Secrets & Package Publishing (Org Standard)
- Store credentials only in GitHub Secrets (org/repo/env scope) and the team vault; never in tracked files.
- Standard secret names: `GH_PAT_PUBLISH`, `GHCR_USERNAME`, `DOCKERHUB_PAT`, `DOCKERHUB_USERNAME`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `YOUTUBE_API_KEY`, `GOOGLE_OAUTH_CLIENT_SECRET`, `DISCORD_WEBHOOK` (add more as needed; keep them documented in `docs/SECRETS_ONBOARDING.md`).
- Image publishing: workflows should `docker/login-action` to GHCR and Docker Hub using the secrets above, then `docker/build-push-action` with SBOM+provenance and signed tags.

---

## PMOVES Project Repositories

### Core Components
| Repository | Description |
|------------|-------------|
| [PMOVES-Creator](https://github.com/POWERFULMOVES/PMOVES-Creator.git) | Content creation and management tools |
| [PMOVES-Agent-Zero](https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git) | Primary agent system |
| [PMOVES-Archon](https://github.com/POWERFULMOVES/PMOVES-Archon.git) | Architecture and orchestration layer |
| [PMOVES-Deep-Serch](https://github.com/POWERFULMOVES/PMOVES-Deep-Serch.git) | Advanced search capabilities |
| [PMOVES-HiRAG](https://github.com/POWERFULMOVES/PMOVES-HiRAG.git) | Hierarchical Retrieval-Augmented Generation |

### Media & Content
| Repository | Description |
|------------|-------------|
| [PMOVES.YT](https://github.com/POWERFULMOVES/PMOVES.YT.git) | YouTube integration and processing |
| [PMOVES-Jellyfin](https://github.com/POWERFULMOVES/PMOVES-Jellyfin.git) | Media server integration |
| [Pmoves-Jellyfin-AI-Media-Stack](https://github.com/POWERFULMOVES/Pmoves-Jellyfin-AI-Media-Stack.git) | AI-powered media processing stack |

### Tools & Utilities
| Repository | Description |
|------------|-------------|
| [PMOVES-Open-Notebook](https://github.com/POWERFULMOVES/PMOVES-Open-Notebook.git) | Notebook and documentation system |
| [Pmoves-Health-wger](https://github.com/POWERFULMOVES/Pmoves-Health-wger.git) | Health and fitness integration |
| [PMOVES-Wealth](https://github.com/POWERFULMOVES/PMOVES-Wealth.git) | Financial management tools |
| [PMOVES-BoTZ](https://github.com/POWERFULMOVES/PMOVES-BoTZ.git) | Bot and automation toolkit |
| [PMOVES-ToKenism-Multi](https://github.com/POWERFULMOVES/PMOVES-ToKenism-Multi.git) | Multi-token management system |
| [PMOVES-DoX](https://github.com/POWERFULMOVES/PMOVES-DoX.git) | Documentation and knowledge management |

### Networking & Remote Access
| Repository | Description |
|------------|-------------|
| [PMOVES-Remote-View](https://github.com/POWERFULMOVES/PMOVES-Remote-View.git) | Remote access and viewing capabilities |
| [PMOVES-Tailscale](https://github.com/POWERFULMOVES/PMOVES-Tailscale.git) | VPN and network integration |

---

## Infrastructure & Deployment

### Cloudflare Integration
- [Workers AI Configuration Bindings](https://developers.cloudflare.com/workers-ai/configuration/bindings/)
- [Pages Deploy Hooks](https://developers.cloudflare.com/pages/configuration/deploy-hooks/)

### Reference Implementations
- [Cloudflare AI Hono Durable Objects Example](https://github.com/elizabethsiegle/nbafinals-cloudflare-ai-hono-durable-objects.git) - Can be used to setup users on Cloudflare and add to GitHub users

### RustDesk Server Setup
For self-hosted remote desktop solutions:

- [Installation Guide](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/install/)
- [Docker Deployment](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/)
- [Client Configuration](https://rustdesk.com/docs/en/self-host/client-configuration/)
- [Client Deployment](https://rustdesk.com/docs/en/self-host/client-deployment/)

---

## Video Resources & Tutorials

### ARCHON & Claude Code Integration
For running Claude Code in spinnable VMs with ARCHON:

- [Video 1](https://www.youtube.com/watch?v=XaYpdKGKKtY)
- [Video 2](https://www.youtube.com/watch?v=kFpLzCVLA20)
- [Video 3](https://www.youtube.com/watch?v=OIKTsVjTVJE)
- [Video 4](https://www.youtube.com/watch?v=p0mrXfwAbCg)

### Richard Aragon's Playlists
- [Complete Playlist Collection](https://www.youtube.com/@richardaragon8471/playlists)

---

## Team & Collaboration

### PMOVES.AI-Edition-Hardened
Specialized hardened edition for enhanced security and stability.

### Collaborators

| Username | Role |
|----------|------|
| hunnibear | Collaborator |
| Pmovesjordan | Collaborator |
| Barathicite | Collaborator |
| wdrolle | Collaborator |

---

## Additional Resources

### Claude AI Integration
- [Using the Connectors Directory to Extend Claude's Capabilities](https://support.claude.com/en/articles/11724452-using-the-connectors-directory-to-extend-claude-s-capabilities)

---

## Notes

- This document serves as a central reference for PMOVES.AI's GitHub organization and infrastructure
- Regular updates should be made as new repositories are added or configurations change
- Team members should ensure they have appropriate access to the repositories mentioned above
