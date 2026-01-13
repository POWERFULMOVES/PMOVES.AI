# Plan: PMOVES-STARGATE Release & Home Lab Deployment

**Status:** SESSION 7 - Full Validation, Deployment & Release
**Date:** 2025-12-23
**Previous Sessions:** Sessions 1-6 completed (security 100%, 58+ containers, CI ready)

---

## 🎯 SESSION 7 OBJECTIVES

1. **Validate all services** in current WSL with proof artifacts
2. **Activate GPU Orchestrator, BoTZ, CRUSH** within repo
3. **Expand TensorZero** providers (LM Studio, HuggingFace, LiteLLM, etc.)
4. **Create PMOVES-STARGATE** deployment repo with optimal submodules
5. **Create provisioning bundle** for home lab
6. **Backup data** to 16TB NAS
7. **Fresh Proxmox install** on 5090 machine
8. **Deploy PMOVES** to home lab
9. **UI roadmap** (Unified + Flute integration)
10. **Benchmark math** via TensorZero and AgentGym-RL

---

## 📊 CURRENT STATE AUDIT

### Services Status (from exploration)

| Component | Implementation | docker-compose | Activation Needed |
|-----------|---------------|----------------|-------------------|
| GPU Orchestrator | 85% complete | ❌ NOT INCLUDED | Add to compose, create TAC |
| Glancer | Optional add-on | ❌ Separate | Bootstrap if needed |
| BoTZ Gateway | Complete | ✅ (needs profile) | `--profile botz` |
| PMOVES-CRUSH | Go CLI ready | ❌ External | Configure MCP |
| E2B Sandbox | In BoTZ features | ❌ Port 7071 | Add to main compose |
| Flute Gateway | 90% ready | ✅ Running | Voice cloning TODO |
| AgentGym-RL | Complete | ✅ (needs profile) | `--profile agentgym` |

### TensorZero Providers

| Provider | Status | Action |
|----------|--------|--------|
| Ollama (local) | ✅ 7 models | - |
| OpenAI | ✅ gpt-4o-mini | - |
| Anthropic | ⚠️ via OpenRouter | Add native |
| OpenRouter | ✅ Configured | - |
| Groq | ✅ Configured | - |
| Venice | ✅ Configured | - |
| Together | ✅ Configured | - |
| Cloudflare | ✅ Configured | - |
| **LM Studio** | ❌ Missing | ADD |
| **HuggingFace** | ❌ Missing | ADD |
| **LiteLLM** | ❌ Missing | ADD |
| **GitHub Models** | ❌ Missing | ADD |

---

## 🔧 PHASE 1: SERVICE ACTIVATION (WSL)

### 1.1 Add GPU Orchestrator to docker-compose.yml

**File:** `pmoves/docker-compose.yml`

```yaml
gpu-orchestrator:
  build:
    context: ./services/gpu-orchestrator
    dockerfile: Dockerfile
  container_name: pmoves-gpu-orchestrator-1
  profiles: ["gpu"]
  ports:
    - "8200:8200"
  environment:
    - NATS_URL=nats://nats:4222
    - OLLAMA_BASE_URL=http://pmoves-ollama:11434
    - VLLM_BASE_URL=http://pmoves-vllm:8000
    - TTS_BASE_URL=http://ultimate-tts-studio:7861
  volumes:
    - ./config/gpu-models.yaml:/app/config/gpu-models.yaml:ro
  networks:
    - api_tier
    - bus_tier
  healthcheck:
    test: ["CMD", "curl", "-sf", "http://localhost:8200/healthz"]
  depends_on:
    nats:
      condition: service_healthy
```

### 1.2 Activate BoTZ Gateway

```bash
COMPOSE_PROFILES=agents,botz docker compose up -d botz-gateway
```

### 1.3 Add E2B Sandbox to main compose

**File:** `pmoves/docker-compose.yml` (add under workers profile)

```yaml
e2b-sandbox:
  image: ${E2B_IMAGE:-ghcr.io/powerfulmoves/pmoves-e2b:latest}
  profiles: ["workers", "botz"]
  ports:
    - "7071:7071"
  environment:
    - E2B_API_KEY=${E2B_API_KEY}
  networks:
    - api_tier
```

### 1.4 Create GPU Orchestrator TAC Instrument

**File:** `pmoves/data/agent-zero/instruments/default/gpu_orchestrator/`

---

## 🔧 PHASE 2: TENSORZERO PROVIDER EXPANSION

### 2.1 Add Missing Providers to tensorzero.toml

**File:** `pmoves/tensorzero/config/tensorzero.toml`

```toml
# LM Studio (OpenAI-compatible)
[models.lm_studio_local]
routing = ["lm_studio_local"]
[models.lm_studio_local.providers.lm_studio_local]
type = "openai"
model_name = "local-model"
api_base = "http://host.docker.internal:1234/v1"

# HuggingFace Inference
[models.huggingface_inference]
routing = ["huggingface_inference"]
[models.huggingface_inference.providers.huggingface_inference]
type = "openai"
model_name = "meta-llama/Llama-3.1-8B-Instruct"
api_base = "https://api-inference.huggingface.co/v1"

# LiteLLM Proxy
[models.litellm_proxy]
routing = ["litellm_proxy"]
[models.litellm_proxy.providers.litellm_proxy]
type = "openai"
model_name = "gpt-4"
api_base = "http://litellm:4000/v1"

# GitHub Models
[models.github_models]
routing = ["github_models"]
[models.github_models.providers.github_models]
type = "openai"
model_name = "gpt-4o"
api_base = "https://models.inference.ai.azure.com"
```

---

## ✅ PHASE 3: FULL VALIDATION WITH PROOF

### 3.1 Validation Script

Create `/home/pmoves/PMOVES.AI/.validation/validate-all.sh`:

```bash
#!/bin/bash
PROOF_DIR=".validation/proof-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$PROOF_DIR"

# Test all services
for svc in agent-zero archon hi-rag-v2 tensorzero flute-gateway botz-gateway gpu-orchestrator; do
  echo "Testing $svc..."
  curl -sf "http://localhost:${PORT}/healthz" > "$PROOF_DIR/${svc}-health.json"
done

# TensorZero benchmark
curl -X POST http://localhost:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"agent_zero_qwen14b_local","messages":[{"role":"user","content":"Hello"}]}' \
  > "$PROOF_DIR/tensorzero-bench.json"

# Generate summary
echo "Validation completed: $(date)" > "$PROOF_DIR/summary.txt"
```

### 3.2 Proof Artifacts to Generate

| Artifact | Command | Location |
|----------|---------|----------|
| Service health matrix | `curl /healthz` all services | `.validation/proof/` |
| TensorZero latency | Benchmark all models | `.validation/proof/tensorzero/` |
| GPU VRAM status | `curl :8200/api/gpu/status` | `.validation/proof/gpu/` |
| NATS stream status | `nats stream ls` | `.validation/proof/nats/` |
| Container list | `docker ps --format json` | `.validation/proof/docker/` |
| AgentGym metrics | Training run results | `.validation/proof/agentgym/` |

---

## 🚀 PHASE 4: PMOVES-STARGATE REPO CREATION

### 4.1 Create New Repository

```bash
gh repo create POWERFULMOVES/PMOVES-STARGATE --public \
  --description "PMOVES deployment orchestration and provisioning"
```

### 4.2 Submodule Selection (Agent Review Task)

**Candidate Submodules for STARGATE:**

| Submodule | Purpose | Include? |
|-----------|---------|----------|
| PMOVES-BoTZ | MCP tools ecosystem | ✅ Required |
| PMOVES-tensorzero | LLM gateway | ✅ Required |
| PMOVES-Tailscale | Network mesh | ✅ Required |
| PMOVES-crush | CLI agent | ✅ Required |
| PMOVES-Archon | Agent forms | ⚠️ Review |
| PMOVES-Agent-Zero | Orchestrator | ⚠️ Review |
| PMOVES-n8n | Workflows | ⚠️ Review |
| PMOVES-Pipecat | Voice | ⚠️ Review |

### 4.3 STARGATE Structure

```
PMOVES-STARGATE/
├── deploy/
│   ├── proxmox/           # VM templates
│   ├── docker/            # Compose files
│   ├── k8s/               # Kubernetes manifests
│   └── scripts/           # Deployment scripts
├── provisioning/
│   ├── ansible/           # Ansible playbooks
│   ├── cloud-init/        # Cloud-init configs
│   └── packer/            # Image builds
├── network/
│   ├── tailscale/         # Mesh config
│   └── rustdesk/          # Remote access
├── backup/
│   └── scripts/           # Backup automation
├── submodules/            # Selected PMOVES repos
└── README.md
```

---

## 💾 PHASE 5: DATA BACKUP

### 5.1 Data to Backup

| Directory | Size Est. | Priority |
|-----------|-----------|----------|
| `pmoves/data/` | ~10GB | HIGH |
| `pmoves/data/agent-zero/` | ~2GB | HIGH |
| `.claude/` | ~50MB | HIGH |
| `docs/` | ~100MB | MEDIUM |
| Supabase volumes | ~5GB | HIGH |
| MinIO buckets | ~20GB | MEDIUM |

### 5.2 Backup Script

```bash
#!/bin/bash
NAS_PATH="/mnt/nas16tb/pmoves-backup"
BACKUP_DATE=$(date +%Y%m%d)

# Docker volumes
docker run --rm -v pmoves_minio_data:/data -v $NAS_PATH:/backup \
  alpine tar czf /backup/minio-$BACKUP_DATE.tar.gz /data

# Local directories
tar czf $NAS_PATH/pmoves-data-$BACKUP_DATE.tar.gz \
  pmoves/data/ .claude/ docs/
```

---

## 🖥️ PHASE 6: PROXMOX INSTALLATION

### 6.1 Pre-Install Checklist

- [ ] Backup current Ubuntu data to NAS
- [ ] Download Proxmox VE ISO (8.x)
- [ ] Create bootable USB
- [ ] Document current network config
- [ ] Note 5090 GPU passthrough requirements

### 6.2 Proxmox VM Plan

| VM | vCPU | RAM | GPU | Purpose |
|----|------|-----|-----|---------|
| pmoves-core | 8 | 32GB | Passthrough | Main PMOVES stack |
| pmoves-ai | 4 | 16GB | Shared | TensorZero + Ollama |
| pmoves-data | 4 | 16GB | None | Databases |

### 6.3 Network Config

```
Tailscale mesh: 100.x.x.x/32
Local LAN: 192.168.x.x/24
VPS Exit Node: Connected via Tailscale
RustDesk: For remote desktop access
```

---

## 🎨 PHASE 7: UI ROADMAP

### 7.1 Unified UI Implementation

**Current:** Modular dashboard at `/dashboard/*`
**Target:** Unified single-page experience per design doc

**Files:**
- Design: `docs/Unified and Modular PMOVES UI Design.md`
- Current UI: `pmoves/ui/app/dashboard/`

### 7.2 Flute Voice Integration

- Add Voice Console component
- Integrate prosodic TTS controls
- Real-time audio visualization
- Voice persona selector

---

## 📐 PHASE 8: MATH BENCHMARKS

### 8.1 TensorZero Benchmarks

```bash
# Run benchmark suite
python3 -m pmoves.tools.tensorzero_benchmark \
  --models agent_zero_qwen14b_local,chat_openai_platform \
  --iterations 100 \
  --output .validation/benchmarks/
```

### 8.2 AgentGym-RL Training Run

```bash
COMPOSE_PROFILES=agentgym docker compose up -d
# Monitor at http://localhost:8114
```

### 8.3 CHIT Math Validation

- Validate CGP v1 geometry operations
- Document Hyperbolic v2 implementation gaps
- Create test suite for Zeta filters (when implemented)

---

## 📋 EXECUTION ORDER

### Day 1: Validation & Activation
1. [ ] Add GPU Orchestrator to docker-compose.yml
2. [ ] Activate BoTZ Gateway
3. [ ] Add E2B to main compose
4. [ ] Expand TensorZero providers
5. [ ] Run full validation suite
6. [ ] Generate proof artifacts

### Day 2: STARGATE & PRs
7. [ ] Create PMOVES-STARGATE repo
8. [ ] Agent reviews submodule selection
9. [ ] Create provisioning bundle
10. [ ] Create final PRs
11. [ ] Tag release on GitHub

### Day 3: Backup & Proxmox
12. [ ] Mount 16TB NAS
13. [ ] Run backup scripts
14. [ ] Fresh Proxmox installation
15. [ ] Configure network (Tailscale + RustDesk)

### Day 4: Deployment
16. [ ] Create Proxmox VMs
17. [ ] Deploy PMOVES stack
18. [ ] Validate home lab installation
19. [ ] Run E2B parallel tests

---

## 📁 CRITICAL FILES

| File | Action |
|------|--------|
| `pmoves/docker-compose.yml` | Add GPU orchestrator, E2B |
| `pmoves/tensorzero/config/tensorzero.toml` | Add providers |
| `pmoves/data/agent-zero/instruments/` | Add GPU TAC |
| `.validation/validate-all.sh` | Create validation script |
| `PMOVES-STARGATE/` | New repo |
| `.claude/scripts/backup-to-nas.sh` | Backup script |

---

## 🔗 RELATED DOCUMENTATION

- `.claude/learnings/pr337-gpu-orchestrator-2025-12.md`
- `.claude/context/ci-runners.md`
- `docs/Unified and Modular PMOVES UI Design.md`
- `PMOVES-BoTZ/.claude/CLAUDE.md`
- `.claude/learnings/session5-infrastructure-audit-2025-12.md`

---

## ✅ PREVIOUS SESSIONS (Reference)

**Sessions 1-6 Completed:**
- Session 1: Tier-based env files, hostname drift fixed
- Session 2: Supabase migrations (21 tables), Archon healthcheck
- Session 3: Documentation PR #346
- Session 4: CODEOWNERS/Dependabot 100%
- Session 5: PRs merged, security alerts dismissed, runner script
- Session 6: Documentation persistence (4 files created)
- PR #346 (PMOVES.AI) - Documentation update (+443 lines)
- PR #25 (ToKenism-Multi) - CHIT Shape Attribution system
- Branches preserved: `feat/docs-update-2025-12`, `feat/chit-shape-attribution`

**Security Posture:**
| Metric | Before Session 4 | After Session 5 |
|--------|------------------|-----------------|
| CODEOWNERS | 7/24 (29%) | 24/24 (100%) |
| Dependabot | 6/24 (25%) | 24/24 (100%) |
| Open Alerts | 3 (1 critical) | 0 |
| Open Dependabot PRs | 0 | 0 |

**CI/CD Status:**
| Component | Status | Next Step |
|-----------|--------|-----------|
| Workflows | ✅ Configured | N/A |
| Runner script | ✅ Created | Deploy to hosts |
| PR triggers | ⚠️ Disabled | Enable after runners |

**Submodule Status:**
- 18/25 submodules updated with security files
- All pushed to respective remotes
- Parent repo references updated (commit 37048cf3)

### Execution Plan

**Step 1: Create Session 5 Learnings File**
```
.claude/learnings/session5-infrastructure-audit-2025-12.md
```
Contents:
- Full audit methodology
- PR status at time of audit
- Security alert details
- Runner configuration status
- Submodule sync results
- Commands used for verification

**Step 2: Create CI Runners Context File**
```
.claude/context/ci-runners.md
```
Contents:
- Runner host requirements
- Label configuration
- Workflow file locations
- Deployment instructions
- Token generation command

**Step 3: Update Main CLAUDE.md**
Add Session 4-5 summary to development history section

**Step 4: Create Public Audit Report**
```
docs/PMOVES_Infrastructure_Audit_2025-12.md
```
Contents:
- Executive summary
- Security improvements
- CI/CD roadmap
- Validation checklist

---

## 🔍 SESSION 5: INFRASTRUCTURE AUDIT (COMPLETED)

### Open PRs Summary (At Start of Session)
| PR | Repo | Branch | Status | Action Taken |
|----|------|--------|--------|--------------|
| **#346** | PMOVES.AI | feat/docs-update-2025-12 | ✅ Merged | Branch preserved |
| **#25** | ToKenism-Multi | feat/chit-shape-attribution | ✅ Merged | Branch preserved |

### Self-Hosted Runners Status
**Status:** ⚠️ SCRIPT READY, DEPLOYMENT PENDING

| Runner Label | Purpose | Configured | Script Ready | Deployed |
|--------------|---------|------------|--------------|----------|
| `self-hosted, ai-lab, gpu` | GPU builds | ✅ | ✅ | ❌ |
| `self-hosted, vps` | CPU builds | ✅ | ✅ | ❌ |
| `self-hosted, cloudstartup, staging` | Staging | ✅ | ✅ | ❌ |
| `self-hosted, kvm4, production` | Production | ✅ | ✅ | ❌ |

**Script Location:** `.claude/scripts/setup-runner.sh`

### Security Alerts Status (RESOLVED)
| Alert | Package | Severity | Resolution |
|-------|---------|----------|------------|
| #61 | torch | CRITICAL | ✅ Dismissed (fixed in PR #344) |
| #87 | next | HIGH | ✅ Dismissed (already on patched 16.0.9) |
| #88 | next | MEDIUM | ✅ Dismissed (already on patched 16.0.9) |

### Submodule Sync Status (COMPLETED)
- **25/25** submodules now have CODEOWNERS + Dependabot
- **18 submodules** updated in commit 37048cf3
- Parent repo pushed to main

---

## 🎯 SESSION 5: RECOMMENDED ACTIONS

### Option A: Merge Ready PRs
1. Merge PR #346 (documentation)
2. Merge PR #25 (CHIT Shape Attribution)
- Both have all checks passing, no blocking comments

### Option B: Resolve Security Alerts
1. Dismiss/verify torch alert #61 (likely stale)
2. Upgrade Next.js in `/pmoves/ui` to resolve alerts #87, #88
- Creates PR to bump next version

### Option C: Deploy Self-Hosted Runners
1. Register runners on target hosts (ai-lab, vps, cloudstartup, kvm4)
2. Re-enable PR triggers in workflow files
3. Test full CI/CD pipeline
- Requires SSH access to runner hosts

### Option D: Submodule Reconciliation
1. Update parent repo's submodule references
2. Push submodule commits to respective remotes
3. Create coordinated PR to update all submodule pointers

---

## 📋 SESSION 5: EXECUTION PLAN (All Options Selected)

### Phase 1: Merge Ready PRs [~5 min]
```bash
# PR #346 - Documentation (PMOVES.AI)
gh pr merge 346 --repo POWERFULMOVES/PMOVES.AI --squash --delete-branch

# PR #25 - CHIT Shape Attribution (ToKenism-Multi)
gh pr merge 25 --repo POWERFULMOVES/PMOVES-ToKenism-Multi --squash --delete-branch
```

### Phase 2: Security Alerts [~15 min]
1. **Dismiss stale torch alert #61** (if PR #344 already fixed it):
   ```bash
   gh api repos/POWERFULMOVES/PMOVES.AI/dependabot/alerts/61 \
     -X PATCH -f state=dismissed -f dismissed_reason="fix_started" \
     -f dismissed_comment="Fixed in PR #344 (PyTorch 2.6.0 upgrade)"
   ```

2. **Upgrade Next.js** to resolve alerts #87, #88:
   - Check current version in `/pmoves/ui/package.json`
   - Determine latest patched Next.js version
   - Create PR: `fix(security): upgrade Next.js to resolve CVE alerts`

### Phase 3: Self-Hosted Runners [~30 min]
**Prerequisites:** SSH access to runner hosts

**Runner Registration Commands:**
```bash
# For each host (ai-lab, vps, cloudstartup, kvm4):
# 1. Download runner package
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz

# 2. Configure with repo token
./config.sh --url https://github.com/POWERFULMOVES/PMOVES.AI \
  --token <REGISTRATION_TOKEN> \
  --labels self-hosted,<HOST_LABEL>,<ADDITIONAL_LABELS>

# 3. Install and start as service
sudo ./svc.sh install
sudo ./svc.sh start
```

**Host-specific labels:**
| Host | Labels |
|------|--------|
| ai-lab | `self-hosted,ai-lab,gpu` |
| vps | `self-hosted,vps` |
| cloudstartup | `self-hosted,cloudstartup,staging` |
| kvm4 | `self-hosted,kvm4,production` |

**Post-registration:** Re-enable PR triggers in `self-hosted-builds-hardened.yml`

### Phase 4: Submodule Sync [~10 min]
```bash
cd /home/pmoves/PMOVES.AI

# Update submodule references to current commits
git submodule update --remote --merge

# Stage and commit submodule pointer updates
git add .
git commit -m "chore: update submodule references after security remediation"

# Push to main
git push origin main
```

---

## 🎯 EXECUTION ORDER

1. ✅ **Phase 1:** Merge PRs (quick wins)
2. ✅ **Phase 2:** Security alerts (reduce risk)
3. ✅ **Phase 3:** Self-hosted runners (enable CI/CD)
4. ✅ **Phase 4:** Submodule sync (clean state)

**Estimated Total Time:** ~60 minutes

---

## 🔐 SESSION 4: SUBMODULE SECURITY REMEDIATION (COMPLETED)

### Objective
Add CODEOWNERS and Dependabot configuration to 17 repos missing them.

### Audit Results (from Session 3)
| Metric | Current | Target |
|--------|---------|--------|
| CODEOWNERS | 7/24 (29%) | 24/24 (100%) |
| Dependabot | 6/24 (25%) | 24/24 (100%) |

### Parallelization Strategy

**3 Parallel Work Streams by Priority:**

| Stream | Repos (7 each) | Agent Focus |
|--------|----------------|-------------|
| **Stream A: Core Agents** | Agent-Zero, Archon, BoTZ, YT, HiRAG, Deep-Serch, ToKenism-Multi | Agent infrastructure + RAG |
| **Stream B: Media & Content** | Open-Notebook, Pipecat, Ultimate-TTS-Studio, Pinokio-TTS, DoX, Jellyfin, Jellyfin-AI-Media-Stack | Media processing |
| **Stream C: Utilities & Internal** | n8n, hyperdimensions, Creator, Remote-View, integrations/archon, vendor/agentgym-rl | Utilities + internal |

**Per-Repo Actions (each stream does these in parallel):**
1. `cd` into submodule
2. Create `.github/` directory if missing
3. Create `CODEOWNERS` file
4. Create `.github/dependabot.yml` file
5. `git add && git commit && git push`
6. `gh pr create` with standardized template

### Files to Create

**CODEOWNERS Template:**
```
# PMOVES Repository Code Owners
* @POWERFULMOVES/pmoves-core
*.py @POWERFULMOVES/pmoves-python
*.ts @POWERFULMOVES/pmoves-frontend
*.tsx @POWERFULMOVES/pmoves-frontend
Dockerfile @POWERFULMOVES/pmoves-infra
docker-compose*.yml @POWERFULMOVES/pmoves-infra
```

**dependabot.yml Template:**
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

### Execution Plan

**Step 1: Launch 3 Parallel Task Agents**
```
Agent A: Agent-Zero, Archon, BoTZ, YT
Agent B: HiRAG, Deep-Serch, ToKenism-Multi, Open-Notebook
Agent C: Pipecat, Ultimate-TTS-Studio, DoX, n8n, hyperdimensions
```

**Step 2: Each Agent Executes Per-Repo Loop**
- Creates files, commits, pushes, creates PR
- Returns list of PR URLs created

**Step 3: Consolidate Results**
- Collect all PR URLs
- Update audit tracking table
- Document in learnings file

### Repos Needing Remediation (17 total)

**Needs BOTH CODEOWNERS + Dependabot (11 repos):**
| Repo | Path | Branch |
|------|------|--------|
| PMOVES-Agent-Zero | `./PMOVES-Agent-Zero` | PMOVES.AI-Edition-Hardened |
| PMOVES-Archon | `./PMOVES-Archon` | PMOVES.AI-Edition-Hardened |
| PMOVES-BoTZ | `./PMOVES-BoTZ` | PMOVES.AI-Edition-Hardened |
| PMOVES.YT | `./PMOVES.YT` | PMOVES.AI-Edition-Hardened |
| PMOVES-HiRAG | `./PMOVES-HiRAG` | PMOVES.AI-Edition-Hardened |
| PMOVES-Deep-Serch | `./PMOVES-Deep-Serch` | PMOVES.AI-Edition-Hardened |
| PMOVES-Open-Notebook | `./PMOVES-Open-Notebook` | PMOVES.AI-Edition-Hardened |
| PMOVES-DoX | `./PMOVES-DoX` | PMOVES.AI-Edition-Hardened |
| PMOVES-ToKenism-Multi | `./PMOVES-ToKenism-Multi` | PMOVES.AI-Edition-Hardened |
| PMOVES-n8n | `./PMOVES-n8n` | main |
| Pmoves-hyperdimensions | `./Pmoves-hyperdimensions` | main |

**Needs CODEOWNERS only (6 repos - already have Dependabot):**
| Repo | Path | Branch |
|------|------|--------|
| PMOVES-Pipecat | `./PMOVES-Pipecat` | main |
| PMOVES-Ultimate-TTS-Studio | `./PMOVES-Ultimate-TTS-Studio` | main |
| PMOVES-Pinokio-Ultimate-TTS-Studio | `./PMOVES-Pinokio-Ultimate-TTS-Studio` | main |
| pmoves/integrations/archon | `./pmoves/integrations/archon` | main |
| pmoves/vendor/agentgym-rl | `./pmoves/vendor/agentgym-rl` | main |
| PMOVES-Remote-View | `./PMOVES-Remote-View` | PMOVES.AI-Edition-Hardened |

**Needs Dependabot only (3 repos - already have CODEOWNERS):**
| Repo | Path | Branch |
|------|------|--------|
| PMOVES-Creator | `./PMOVES-Creator` | PMOVES.AI-Edition-Hardened |
| PMOVES-Jellyfin | `./PMOVES-Jellyfin` | PMOVES.AI-Edition-Hardened |
| Pmoves-Jellyfin-AI-Media-Stack | `./Pmoves-Jellyfin-AI-Media-Stack` | PMOVES.AI-Edition-Hardened |

**Already Complete (skip):**
- PMOVES-tensorzero (has both)
- PMOVES-Wealth (has both)
- PMOVES-crush (has both)
- PMOVES-Tailscale (has both)
- Pmoves-Health-wger (has both)

### Expected Output
- 20 PRs created across submodule repos (one per repo needing updates)
- Security posture: 25/25 CODEOWNERS, 25/25 Dependabot
- Updated `.claude/learnings/submodule-security-audit-2025-12.md`

### Risk Mitigation
- Some submodules on `PMOVES.AI-Edition-Hardened` branch need branch checkout first
- Internal submodules (`pmoves/integrations/archon`, `pmoves/vendor/agentgym-rl`) may have different push permissions
- If PR creation fails, will fallback to documenting required manual steps

---

## 📋 SESSION 3 COMPLETED (Reference)

## 🚨 SESSION 3: NEW ISSUES DISCOVERED

### Issue #5: Archon UI Not Running
**Severity:** HIGH - User cannot access Archon visual interface

**Finding:**
- Archon backend runs on ports 8051-8052, 8091 (healthy)
- **Port 3737 (Archon UI) is NOT exposed** - the main `docker-compose.yml` doesn't include archon-ui
- Archon UI is a **React/Vite app** in `PMOVES-Archon/archon-ui-main/`

**Available Compose Files for Archon UI:**
| File | Source | Notes |
|------|--------|-------|
| `docker-compose.archon-ui.submodule.yml` | `integrations/archon/archon-ui-main` | Uses local submodule |
| `docker-compose.agents.integrations.yml` | External `INTEGRATIONS_WORKSPACE` | Dev environment |
| `docker-compose.agents.images.yml` | `ghcr.io/powerfulmoves/pmoves-archon-ui` | **RECOMMENDED** (pre-built) |
| `integrations/archon/docker-compose.yml` | Archon's own compose | Standalone |

**Required Fix:**
```bash
# Option 1: Use pre-built image (fastest)
docker compose -f docker-compose.yml -f docker-compose.agents.images.yml up -d archon-ui

# Option 2: Build from submodule
docker compose -f docker-compose.yml -f docker-compose.archon-ui.submodule.yml up -d archon-ui

# Verify
curl -sf http://localhost:3737 && echo "Archon UI OK"
```

---

### Issue #6: Integration Services Not Running
**Severity:** MEDIUM - Optional but expected in production

**Discovery:**
The `pmoves/integrations/` folder contains standalone integration projects:
- `archon/` - PMOVES-Archon submodule (includes UI)
- `firefly-iii/` - Finance tracking
- `health-wger/` - Fitness/health
- `pr-kits/` - PR tooling

**Currently Running Integration-Adjacent Services:**
| Service | Port | Status |
|---------|------|--------|
| botz-gateway | 8054 | ✅ Running |
| pmoves-ollama | 11434 | ✅ Running |
| publisher-discord | 8094 | ✅ Running |
| render-webhook | 8085 | ✅ Running |
| jellyfin-bridge | 8093 | ❌ NOT running |

**Integration Compose Files Available:**
- `docker-compose.agents.integrations.yml` - Agent integrations
- `docker-compose.n8n.yml` - Workflow automation
- `docker-compose.jellyfin-ai.yml` - Jellyfin AI stack
- `docker-compose.external.yml` - Invidious, Grayjay
- `docker-compose.voice.yml` - Pipecat voice services

---

### Issue #7: Documentation Needs Update/Validation
**Severity:** MEDIUM - Stale docs cause configuration errors

**Files to Review:**
| File | Location | Purpose |
|------|----------|---------|
| `PMOVES_Services_Documentation_Complete.md` | `/home/pmoves/PMOVES.AI/docs/` | Full service catalog |
| `PMOVES.AI Services and Integrations.md` | `/home/pmoves/PMOVES.AI/docs/` | Integration guide |
| `PMOVES.AI-Edition-Hardened-Full.md` | `/home/pmoves/PMOVES.AI/docs/` | Security hardening |
| `PMOVES_Repository_Index.md` | `/home/pmoves/PMOVES.AI/docs/` | Repo structure |

**Worktree Status:**
- Main: `/home/pmoves/PMOVES.AI` (main branch)
- Documentation worktree: `/home/pmoves/tac-docs-update` (feat/docs-update-2025-12) ✅ CREATED

---

## 📚 DOCUMENTATION AGENT ANALYSIS RESULTS

### Document 1: PMOVES.AI Services and Integrations.md (222 lines)
**Location:** `/home/pmoves/tac-docs-update/docs/PMOVES.AI Services and Integrations.md`
**Status:** ⚠️ MISSING CRITICAL SECTIONS

| Gap | Severity | Line Reference |
|-----|----------|----------------|
| TensorZero Gateway section (ports 3030, 4000, 8123) | **CRITICAL** | Missing - insert before line 78 |
| ClickHouse observability integration | **HIGH** | Not documented |
| 5-tier network architecture explanation | **HIGH** | Not documented |
| Docker hardening documentation | **HIGH** | Not documented |
| 15+ services missing (Consciousness Service, etc.) | **MEDIUM** | Lines 78-159 incomplete |
| Grafana port (shows 3000, actual 3002) | **MEDIUM** | Verify in port table |

**Accurate Sections (23/26 ports correct):**
- Agent Coordination & Orchestration (lines 14-23)
- Retrieval & Knowledge Services (lines 24-35)
- TAC Command Mapping (lines 163-222)

**Required Updates:**
1. Add "## Model Gateway & Observability" section before line 78 with:
   - TensorZero Gateway (port 3030 host → 3000 container)
   - TensorZero UI (port 4000)
   - TensorZero ClickHouse (port 8123)
   - Ollama integration (port 11434)

2. Add "## Network Architecture" section documenting:
   - 5-tier model (API, App, Bus, Data, Monitoring)
   - CIDR ranges (172.30.1-5.0/24)
   - Defense-in-depth principles
   - `internal: true` network isolation

3. Add "## Docker Hardening" section with:
   - Tier-based env files strategy
   - Network isolation benefits
   - Health check patterns

4. Add missing services:
   - Consciousness Service (8096)
   - Session Context Worker (8100)
   - Messaging Gateway (8101)
   - Chat Relay (8102)
   - Botz Gateway (8054)

---

### Document 2: PMOVES.AI-Edition-Hardened-Full.md (2,079 lines)
**Location:** `/home/pmoves/tac-docs-update/docs/PMOVES.AI-Edition-Hardened-Full.md`
**Status:** ⚠️ DOCUMENTATION vs IMPLEMENTATION GAPS

| Security Practice | Documented | Implemented | Gap Status |
|-------------------|------------|-------------|------------|
| 5-Tier Network Isolation | ✅ Lines 390-450 | ✅ Fully | MATCH |
| TensorZero Secrets Fence | ✅ Lines 1067-1179 | ✅ Fully | MATCH |
| Tier-Based Secrets (env.tier-*) | ❌ Not documented | ✅ 6 tiers | **HIDDEN ASSET** |
| Non-root User (UID 65532) | ✅ Line 1857 | ❌ 1/50 services | **IMPLEMENTATION GAP** |
| cap_drop: ALL | ✅ Lines 1865-1866 | ❌ 0 services | **IMPLEMENTATION GAP** |
| read_only: true + tmpfs | ✅ Lines 1859-1862 | ❌ 0 services | **IMPLEMENTATION GAP** |
| BuildKit Secret Mounts | ✅ Lines 160-190 | ✅ In Dockerfiles | MATCH |
| Health Checks | ✅ Lines 486-490 | ✅ 30+ services | MATCH |

**Required Updates:**
1. **ADD** Tier-Based Secrets section (currently undocumented despite being fully implemented):
   ```markdown
   ## Tier-Based Secrets Architecture
   - env.tier-data: Infrastructure only, NO API keys
   - env.tier-api: Data tier access + TensorZero gateway (NO external keys)
   - env.tier-worker: Worker service credentials
   - env.tier-agent: Agent coordination credentials
   - env.tier-media: Media processing credentials
   - env.tier-llm: **ONLY tier with external LLM API keys** (TensorZero only)
   ```

2. **UPDATE** Security Posture section (lines 1755-1990) to note:
   - Which practices are IMPLEMENTED vs DOCUMENTED-ONLY
   - Phase 2.5 roadmap for container hardening (user, cap_drop, read_only)

3. **ADD** Implementation status table showing actual compose.yml vs documented requirements

---

### Document 3: PMOVES_Repository_Index.md (278 lines)
**Location:** `/home/pmoves/tac-docs-update/docs/PMOVES_Repository_Index.md`
**Status:** ⚠️ SIGNIFICANTLY OUTDATED (44% submodules missing)

| Gap | Severity | Details |
|-----|----------|---------|
| 11/25 submodules missing (44%) | **CRITICAL** | PMOVES-BoTZ, tensorzero, Pipecat, n8n, crush, hyperdimensions, etc. |
| Docker-compose overlays undocumented | **CRITICAL** | 23+ overlay files not mentioned |
| .claude/ directory structure missing | **CRITICAL** | 23 command dirs, 16 context files, 15 learnings |
| Last updated 23 days old | **HIGH** | Before Phase 2 release |
| Mermaid diagram incomplete | **MEDIUM** | Shows ~14 submodules, actual 25 |
| 10+ context docs not linked | **MEDIUM** | services-catalog.md, submodules.md, etc. |

**Missing Submodules (add to doc):**
1. PMOVES-BoTZ - MCP tools ecosystem (ports 2091, 3020, 7071, 7072, 8081)
2. PMOVES-tensorzero - LLM gateway (port 3030) **CRITICAL**
3. PMOVES-Pipecat - Multimodal communication
4. PMOVES-n8n - Workflow automation
5. PMOVES-crush - Compression utilities
6. Pmoves-hyperdimensions - Visualization
7. PMOVES-Pinokio-Ultimate-TTS-Studio - TTS Pinokio launcher
8. pmoves/integrations/archon - Internal submodule
9. pmoves/vendor/agentgym-rl - RL training
10. PMOVES-Firefly-iii - Financial tracking
11. PMOVES-Creator - ComfyUI integration

**Required Updates:**
1. **ADD** Docker Compose Organization section:
   - Main: `docker-compose.yml` (57KB)
   - 23 overlay files listed with purposes

2. **ADD** .claude/ Directory Structure section:
   - commands/ (23 skill directories)
   - context/ (16 documentation files)
   - learnings/ (15 discovery files)
   - hooks/ (pre-tool, post-tool)

3. **UPDATE** Submodules section with all 25 submodules

4. **ADD** links to context documentation:
   - `.claude/context/services-catalog.md`
   - `.claude/context/submodules.md`
   - `.claude/context/nats-subjects.md`
   - `.claude/context/tensorzero.md`

5. **UPDATE** Last updated date to 2025-12-23

6. **FIX** Mermaid diagram to show all 25 submodules

---

### Issue #8: Submodule Security & Git Best Practices
**Severity:** HIGH - Security compliance and repository protection

**Concerns Identified:**
- Some submodules may not have branch protection rules
- Submodule commit references may be stale or vulnerable
- Missing CODEOWNERS in some submodules
- Potential for unsigned commits in submodule history

**Security Audit Checklist:**

| Repository | Branch Protection | CODEOWNERS | Signed Commits | Status |
|------------|-------------------|------------|----------------|--------|
| PMOVES-Agent-Zero | TBD | TBD | TBD | ⏳ |
| PMOVES-Archon | TBD | TBD | TBD | ⏳ |
| PMOVES-BoTZ | TBD | TBD | TBD | ⏳ |
| PMOVES.YT | TBD | TBD | TBD | ⏳ |
| PMOVES-HiRAG | TBD | TBD | TBD | ⏳ |
| PMOVES-tensorzero | TBD | TBD | TBD | ⏳ |
| PMOVES-Deep-Serch | TBD | TBD | TBD | ⏳ |
| PMOVES-Open-Notebook | TBD | TBD | TBD | ⏳ |
| PMOVES-Jellyfin | TBD | TBD | TBD | ⏳ |
| PMOVES-DoX | TBD | TBD | TBD | ⏳ |
| PMOVES-Pipecat | TBD | TBD | TBD | ⏳ |
| PMOVES-Ultimate-TTS-Studio | TBD | TBD | TBD | ⏳ |
| PMOVES-ToKenism-Multi | TBD | TBD | TBD | ⏳ |
| Other submodules (12+) | TBD | TBD | TBD | ⏳ |

**Git Best Practices to Verify:**

1. **Branch Protection Rules:**
   - `main`/`master` branch protected
   - Require pull request reviews before merging
   - Require status checks to pass
   - Restrict force pushes

2. **Repository Security:**
   - Secret scanning enabled
   - Dependabot security alerts enabled
   - CodeQL analysis configured
   - Vulnerability alerts active

3. **Commit Hygiene:**
   - Submodule commits point to protected branches (not random SHAs)
   - No hardcoded secrets in submodule history
   - CODEOWNERS file present for review routing

4. **Access Control:**
   - Appropriate team permissions
   - No stale collaborator access
   - 2FA enforced for org members

**Required Actions:**
1. Run `gh api` audit on all 25 submodule repos
2. Check branch protection via `gh api repos/{owner}/{repo}/branches/main/protection`
3. Verify CODEOWNERS exists in each submodule
4. Check for Dependabot configuration
5. Document findings and create remediation PRs

---

## 📋 SESSION 3 EXECUTION PLAN

### Step 1: Start Archon UI [HIGH PRIORITY]
```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Use pre-built image (fastest, recommended)
docker compose -f docker-compose.yml -f docker-compose.agents.images.yml up -d archon-ui

# Wait and verify
sleep 10
curl -sf http://localhost:3737 && echo "✅ Archon UI OK"
```

### Step 2: Start ALL Integration Services
```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Start Archon UI (from pre-built image)
docker compose -f docker-compose.yml -f docker-compose.agents.images.yml up -d archon-ui

# Start n8n workflow automation
docker compose -f docker-compose.yml -f docker-compose.n8n.yml up -d

# Start Jellyfin AI stack
docker compose -f docker-compose.yml -f docker-compose.jellyfin-ai.yml up -d

# Start external services (Invidious, Grayjay)
docker compose -f docker-compose.yml -f docker-compose.external.yml up -d

# Start voice/Pipecat services
docker compose -f docker-compose.yml -f docker-compose.voice.yml up -d

# Verify all integration services
echo "=== Integration Services Status ==="
for svc in archon-ui n8n jellyfin-ai invidious grayjay pipecat; do
  docker ps --filter "name=$svc" --format "{{.Names}}: {{.Status}}" 2>/dev/null || echo "$svc: not found"
done
```

**All Auxiliary Compose Files:**
| File | Services | Ports |
|------|----------|-------|
| `docker-compose.agents.images.yml` | archon-ui | 3737 |
| `docker-compose.n8n.yml` | n8n, n8n-agent | 5678 |
| `docker-compose.jellyfin-ai.yml` | jellyfin-ai stack | varies |
| `docker-compose.external.yml` | invidious, grayjay | varies |
| `docker-compose.voice.yml` | pipecat, voice services | varies |
| `docker-compose.open-notebook.yml` | open-notebook | 8503 |

### Step 3: Create Documentation Worktree
```bash
cd /home/pmoves/PMOVES.AI

# Create new documentation branch worktree
git worktree add /home/pmoves/tac-docs-update -b feat/docs-update-2025-12

# Switch to worktree for doc edits
cd /home/pmoves/tac-docs-update
```

### Step 4: Review & Update Documentation Files [DETAILED]

**Status:** Steps 1-3 ✅ COMPLETED, Step 4 IN PROGRESS

**Working Directory:** `/home/pmoves/tac-docs-update/docs/`

#### 4a. PMOVES_Services_Documentation_Complete.md ✅ COMPLETED
- Updated container count from 30+ to 58+
- Added TensorZero Model Gateway section
- Added Docker Hardening Practices section
- Added 5-Tier Network Matrix
- Updated Service Port Matrix with 60+ services
- Updated Archon section with UI port 3737
- Fixed Grafana port reference

#### 4b. PMOVES.AI Services and Integrations.md ⏳ IN PROGRESS
**Insert before line 78 (Core Data section):**
```markdown
## Model Gateway & Observability

### TensorZero Gateway [Ports 3030, 4000, 8123]
Centralized LLM orchestration layer and secrets fence.

| Component | Port | Purpose |
|-----------|------|---------|
| TensorZero Gateway | 3030 (host) → 3000 (container) | LLM API routing |
| TensorZero UI | 4000 | Metrics dashboard |
| TensorZero ClickHouse | 8123 | Observability storage |

**Architecture:**
- All services call TensorZero, NOT LLM providers directly
- Only `env.tier-llm` contains external API keys
- ClickHouse stores request logs, token usage, latency metrics

### Ollama [Port 11434]
Local LLM model server for offline/private inference.
```

**Add new services to document:**
- Consciousness Service (8096)
- Session Context Worker (8100)
- Messaging Gateway (8101)
- Chat Relay (8102)
- Botz Gateway (8054)

**Add Network Architecture section**

#### 4c. PMOVES.AI-Edition-Hardened-Full.md ⏳ PENDING
**Add after line 1179 (TensorZero section):**
```markdown
## Tier-Based Secrets Architecture (env.tier-*)

PMOVES implements principle of least privilege via 6 specialized environment tiers:

| Tier File | Services | Secrets Scope |
|-----------|----------|---------------|
| env.tier-data | postgres, qdrant, neo4j, minio | Infrastructure only |
| env.tier-api | postgrest, hi-rag-v2, presign | Data tier + internal TensorZero |
| env.tier-worker | extract-worker, langextract | Processing credentials |
| env.tier-agent | agent-zero, archon, nats | Agent coordination |
| env.tier-media | pmoves-yt, whisper, media-* | Media processing |
| env.tier-llm | tensorzero-gateway ONLY | **External LLM API keys** |

**Critical:** Only `env.tier-llm` contains external provider keys (Anthropic, OpenAI, etc.)
```

**Update Security Posture (lines 1755-1990) with implementation status table**

#### 4d. PMOVES_Repository_Index.md ⏳ PENDING
**Add new sections:**

1. **Docker Compose Organization:**
```markdown
## Docker Compose Architecture

### Main Orchestration
- `docker-compose.yml` (57KB) - Primary service definitions

### Profile Overlays (23 files)
| Overlay | Purpose |
|---------|---------|
| docker-compose.agents.images.yml | Pre-built agent images |
| docker-compose.n8n.yml | Workflow automation |
| docker-compose.voice.yml | Pipecat voice services |
| docker-compose.gpu.yml | GPU-accelerated services |
| docker-compose.hardened.yml | Security hardening |
| ... (18 more) |
```

2. **.claude/ Directory Structure:**
```markdown
## Claude Code CLI Integration

### Commands (23 skill directories)
agent-sdk/, agents/, botz/, chit/, crush/, db/, deploy/, github/,
gpu/, health/, hyperdim/, k8s/, langextract/, model/, n8n/,
pipecat/, search/, tensorzero/, test/, tts/, workitems/, worktree/, yt/

### Context Documentation (16 files)
- services-catalog.md (13KB) - Complete service listing
- submodules.md (17KB) - All 25 submodules
- nats-subjects.md (9KB) - Event architecture
- tensorzero.md (12KB) - LLM gateway reference
```

3. **Add 11 missing submodules** (see Issue #7 details)

4. **Update Last Updated date to 2025-12-23**

---

### Step 5: Submodule Security Audit [NEW]

**Purpose:** Verify git best practices and security on all 25 submodules

**Audit Script:**
```bash
#!/bin/bash
# Run from PMOVES.AI root

echo "=== Submodule Security Audit ==="

for sub in PMOVES-Agent-Zero PMOVES-Archon PMOVES-BoTZ PMOVES.YT PMOVES-HiRAG \
           PMOVES-tensorzero PMOVES-Deep-Serch PMOVES-Open-Notebook PMOVES-Jellyfin \
           PMOVES-DoX PMOVES-Pipecat PMOVES-Ultimate-TTS-Studio PMOVES-ToKenism-Multi \
           PMOVES-Creator PMOVES-Remote-View PMOVES-Wealth Pmoves-Health-wger \
           PMOVES-n8n PMOVES-crush Pmoves-hyperdimensions PMOVES-Tailscale \
           PMOVES-Pinokio-Ultimate-TTS-Studio; do

  if [ -d "$sub" ]; then
    echo ""
    echo "=== $sub ==="

    # Check for CODEOWNERS
    [ -f "$sub/CODEOWNERS" ] || [ -f "$sub/.github/CODEOWNERS" ] && echo "  ✅ CODEOWNERS" || echo "  ❌ CODEOWNERS missing"

    # Check for .github/dependabot.yml
    [ -f "$sub/.github/dependabot.yml" ] && echo "  ✅ Dependabot" || echo "  ⚠️ Dependabot missing"

    # Check branch protection (requires gh auth)
    # gh api repos/POWERFULMOVES/$sub/branches/main/protection 2>/dev/null && echo "  ✅ Branch protection" || echo "  ⚠️ Branch protection unknown"
  fi
done
```

**Remediation Actions:**
1. Create CODEOWNERS file template for missing repos
2. Enable Dependabot security alerts via GitHub API
3. Configure branch protection rules on main branches
4. Document findings in `.claude/learnings/submodule-security-audit-2025-12.md`

---

### Step 6: Create PR for Documentation Updates

```bash
cd /home/pmoves/tac-docs-update

# Stage all documentation changes
git add docs/

# Commit with descriptive message
git commit -m "docs: comprehensive documentation update - Phase 2.8

- PMOVES_Services_Documentation_Complete.md: Updated to 58+ containers
- PMOVES.AI Services and Integrations.md: Added TensorZero, network arch
- PMOVES.AI-Edition-Hardened-Full.md: Added tier-based secrets docs
- PMOVES_Repository_Index.md: Added 11 missing submodules, .claude/ structure

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Push and create PR
git push -u origin feat/docs-update-2025-12
gh pr create --title "docs: Comprehensive documentation update - Phase 2.8" \
  --body "## Summary
- Updated service documentation to reflect 58+ containers
- Added TensorZero Gateway documentation
- Documented 5-tier network architecture
- Added tier-based secrets (env.tier-*) documentation
- Added 11 missing submodules to repository index
- Documented .claude/ directory structure

## Files Modified
- docs/PMOVES_Services_Documentation_Complete.md
- docs/PMOVES.AI Services and Integrations.md
- docs/PMOVES.AI-Edition-Hardened-Full.md
- docs/PMOVES_Repository_Index.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## ✅ SESSION 2 ISSUES (RESOLVED)

All Session 2 critical issues have been fixed:
- ✅ Issue #1: Supabase tables applied (21 tables now exist)
- ✅ Issue #2: archon-agent-work-orders running (healthy)
- ✅ Issue #3: Agent Zero MCP configured via A0_MCP_SERVERS
- ✅ Issue #4: Archon healthcheck fixed (supabase.http: 200)

### Reference: Session 2 Fixes Applied

## 🔧 CRITICAL ISSUES DISCOVERED (Session 2 - FOR REFERENCE)

### Issue #1: Supabase Database Missing Essential Tables
**Severity:** CRITICAL - Blocking Archon and Agent coordination

**Finding:**
- Only **5 tables** exist in Supabase public schema:
  - brand_assets, chat_messages, content_schedule, social_posts, studio_board
- **MISSING** (should have 25+ tables from initdb):
  - `archon_settings` - Archon credential/config store
  - `archon_prompts` - Archon prompt management
  - `chit_geometry`, `geometry_bus` - CHIT/ToKenism tables
  - `youtube_transcripts`, `channel_monitoring` - YT pipeline
  - `videos_transcripts`, `media_analysis` - Media processing
  - All core PMOVES schema tables

**Root Cause:**
Supabase CLI (`supabase start`) does NOT automatically run `initdb/*.sql` scripts.
Those scripts are designed for Docker Compose postgres which mounts them to `/docker-entrypoint-initdb.d:ro`.

**Evidence:**
```bash
docker exec supabase_db_pmoves psql -U postgres -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"
# Result: 5 (should be 25+)
```

**Required Fix:**
```bash
# Run all initdb scripts in order
cd pmoves && make supabase-bootstrap
# OR apply manually:
for f in supabase/initdb/*.sql; do
  docker exec -i supabase_db_pmoves psql -U postgres < "$f"
done
```

---

### Issue #2: archon-agent-work-orders Not Running
**Severity:** HIGH - Workflow execution blocked

**Finding:**
- Container status: `created` (never started)
- No error message, no logs
- Profile: `["agents", "work-orders"]`

**Root Cause:**
Container depends on `archon` being healthy (healthcheck). While Archon reports healthy,
its Supabase connection returns 404 (missing tables), which may cause startup issues.

**Required Fix:**
1. First fix Supabase tables (Issue #1)
2. Then restart archon-agent-work-orders:
```bash
docker start pmoves-archon-agent-work-orders-1
# OR
COMPOSE_PROFILES=data,workers,agents,work-orders docker compose up -d
```

---

### Issue #3: Agent Zero Settings Missing
**Severity:** MEDIUM - Agent configuration not persisted

**Finding:**
- `/home/pmoves/PMOVES.AI/pmoves/data/agent-zero/tmp/settings.json` does NOT exist
- Only `chats/` and `scheduler/` directories present
- Agent Zero running with defaults only

**Required Fix:**
```bash
# Create settings.json with PMOVES defaults
cd pmoves && make a0-mcp-seed
# OR manually create settings.json
```

---

### Issue #4: Archon Supabase 404 Error
**Severity:** HIGH - Credential bootstrapping failing

**Finding:**
```json
{"status":"ok","service":"archon","supabase":{"url":"http://supabase_kong_pmoves:8000","http":404}}
```

**Root Cause:** `archon_settings` table doesn't exist (Issue #1)

**Required Fix:** Apply Supabase migrations (Issue #1 fix)

---

## Current Container Status (52 Running)

| Category | Count | Status |
|----------|-------|--------|
| PMOVES services | 39 | Running |
| Supabase CLI | 10 | Running |
| Other | 3 | Running |
| **archon-agent-work-orders** | 1 | **CREATED (not started)** |

---

## Execution Plan (Prioritized)

### Step 1: Apply Supabase Migrations [CRITICAL]
```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Apply all initdb scripts in order
for f in supabase/initdb/*.sql; do
  echo "Applying $f..."
  docker exec -i supabase_db_pmoves psql -U postgres < "$f"
done

# Verify tables created
docker exec supabase_db_pmoves psql -U postgres -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"
# Expected: 25+
```

### Step 2: Restart Archon for Fresh Supabase Connection
```bash
docker restart pmoves-archon-1

# Wait for healthy
sleep 30

# Verify healthcheck
curl -sf http://localhost:8091/healthz | jq
# Should show supabase.http: 200 (not 404)
```

### Step 3: Start archon-agent-work-orders
```bash
docker start pmoves-archon-agent-work-orders-1

# Verify running
docker ps --filter "name=work-orders" --format "{{.Names}}: {{.Status}}"

# Check health
curl -sf http://localhost:8053/health | jq
```

### Step 4: Seed Agent Zero MCP Configuration
```bash
cd /home/pmoves/PMOVES.AI/pmoves
make a0-mcp-seed

# Verify settings created
cat data/agent-zero/tmp/settings.json | jq
```

### Step 5: Verify All Agent Services
```bash
# Agent Zero
curl -sf http://localhost:8080/healthz && echo "Agent Zero OK"

# Archon API
curl -sf http://localhost:8091/healthz && echo "Archon OK"

# Archon MCP
curl -sf http://localhost:8051/health && echo "Archon MCP OK"

# Agent Work Orders
curl -sf http://localhost:8053/health && echo "Work Orders OK"
```

---

## Files to Modify

| File | Action | Purpose |
|------|--------|---------|
| N/A (commands only) | Execute | Apply Supabase migrations |
| `data/agent-zero/tmp/settings.json` | Create | Agent Zero configuration |

## Files Already Fixed (Session 1)

| File | Status | Notes |
|------|--------|-------|
| `docker-compose.yml` | ✅ Fixed | Tier-based anchors, hostname drift |
| `docker-compose.open-notebook.yml` | ✅ Fixed | Image fallback to POWERFULMOVES |
| `docker-compose.external.yml` | ✅ Fixed | Image fallback to POWERFULMOVES |
| `env.shared` | ✅ Fixed | Hostname drift (supabase_kong_pmoves) |
| `env.tier-*.example` | ✅ Created | 6 tier-based env templates |
| `.gitignore` | ✅ Updated | Added env.tier-* patterns |

---

## Auxiliary Compose Files (Services Not in Main Compose)

The following services are defined in separate compose files and need explicit `-f` flag to include:

| File | Services | Status |
|------|----------|--------|
| `docker-compose.n8n.yml` | n8n, n8n-agent | NOT STARTED |
| `docker-compose.open-notebook.yml` | open-notebook | NOT STARTED |
| `docker-compose.realtime.yml` | supabase-realtime | In Supabase CLI |
| `docker-compose.voice.yml` | pipecat services | NOT STARTED |
| `docker-compose.comfyui.yml` | ComfyUI | NOT STARTED |
| `docker-compose.jellyfin-ai.yml` | Jellyfin AI stack | NOT STARTED |
| `docker-compose.agentgym.yml` | AgentGym RL | NOT STARTED |
| `docker-compose.external.yml` | Invidious, Grayjay | NOT STARTED |

### To Start Auxiliary Services
```bash
# n8n workflow automation
docker compose -f docker-compose.yml -f docker-compose.n8n.yml up -d

# Open Notebook
docker compose -f docker-compose.yml -f docker-compose.open-notebook.yml up -d

# Voice/Pipecat
docker compose -f docker-compose.yml -f docker-compose.voice.yml up -d
```

---

## Profile Summary (Main Compose)

| Profile | Services Included |
|---------|-------------------|
| `data` | postgres, qdrant, neo4j, meilisearch, minio |
| `workers` | extract-worker, langextract, hi-rag-v2, presign, etc. |
| `agents` | agent-zero, archon, nats, mesh-agent, supaserch |
| `orchestration` | deepresearch, channel-monitor, consciousness-service |
| `gpu` | GPU-accelerated services (hi-rag-gpu, media analyzers) |
| `tts` | ultimate-tts-studio |
| `tensorzero` | tensorzero-gateway, tensorzero-ui, tensorzero-clickhouse |
| `work-orders` | archon-agent-work-orders |
| `botz` | botz-gateway |
| `monitoring` | prometheus, grafana, loki (in separate compose) |

### Current Active Profiles
```bash
COMPOSE_PROFILES=data,workers,agents,orchestration,tensorzero
```

---

## Previous Plan Sections (Reference)

## Phase 0: Submodule Audit & Status

### 0.1 All Submodules Catalog (20+)
| Submodule | Status | Priority | Notes |
|-----------|--------|----------|-------|
| PMOVES-Agent-Zero | TBD | HIGH | Core orchestrator |
| PMOVES-Archon | TBD | HIGH | Agent forms |
| PMOVES-BoTZ | TBD | HIGH | CHIT encoding |
| PMOVES.YT | TBD | HIGH | YouTube pipeline |
| PMOVES-HiRAG | TBD | HIGH | Retrieval |
| PMOVES-Deep-Serch | TBD | MEDIUM | Research |
| PMOVES-Open-Notebook | TBD | MEDIUM | Knowledge base |
| PMOVES-Jellyfin | TBD | MEDIUM | Media |
| PMOVES-Creator | TBD | MEDIUM | Content |
| PMOVES-Remote-View | TBD | LOW | Remote access |
| PMOVES-Wealth | TBD | LOW | Finance |
| Pmoves-Health-wger | TBD | LOW | Health |
| PMOVES-DoX | TBD | LOW | Docs |
| PMOVES-Pipecat | TBD | MEDIUM | Voice |
| PMOVES-Ultimate-TTS-Studio | TBD | MEDIUM | TTS |
| PMOVES-tensorzero | TBD | HIGH | Model gateway |
| PMOVES-Tailscale | TBD | LOW | Networking |
| PMOVES-crush | TBD | LOW | Compression |
| PMOVES-n8n | TBD | MEDIUM | Workflows |
| PMOVES-ToKenism-Multi | TBD | HIGH | CHIT contracts |
| pmoves/integrations/archon | TBD | HIGH | Integration |
| pmoves/vendor/agentgym-rl | TBD | LOW | RL training |

### 0.2 Check Submodule Health
```bash
for sub in PMOVES-Agent-Zero PMOVES-Archon PMOVES-BoTZ PMOVES.YT PMOVES-HiRAG; do
  echo "=== $sub ==="
  git -C $sub status --short
  git -C $sub log --oneline -1
done
```

### 0.3 TensorZero Integration Needs
Submodules requiring TensorZero access for LLM/embedding calls:
- PMOVES-Agent-Zero (agent LLM calls)
- PMOVES-Archon (prompt generation)
- PMOVES-HiRAG (embeddings)
- PMOVES-Deep-Serch (research LLM)
- PMOVES-Open-Notebook (summarization)

**Integration Pattern:**
```yaml
# Each submodule needs:
TENSORZERO_API_URL: http://host.docker.internal:3030
TENSORZERO_API_KEY: ${TENSORZERO_API_KEY}
# Or via internal Docker network:
TENSORZERO_API_URL: http://tensorzero:3030
```

---

## Phase 0.4: CRITICAL - Open Notebook Image Divergence 🚨

### Finding: Three Different Image Registries

| Source | Image | Issue |
|--------|-------|-------|
| `env.shared` (line 150) | `ghcr.io/powerfulmoves/pmoves-open-notebook:v1-latest` | ✅ Correct |
| `docker-compose.open-notebook.yml` (line 81) | Fallback: `ghcr.io/lfnovo/open-notebook:v1-latest` | ❌ Outdated upstream |
| `docker-compose.external.yml` (line 81) | Fallback: `ghcr.io/lfnovo/open-notebook:v1-latest` | ❌ Outdated upstream |

**Risk:** If `OPEN_NOTEBOOK_IMAGE` env var is not set, containers pull from lfnovo (upstream) instead of POWERFULMOVES (PMOVES-hardened variant).

### 0.4.1 Required Fix
Update fallback defaults in both compose files:
```yaml
# FROM:
image: ${OPEN_NOTEBOOK_IMAGE:-ghcr.io/lfnovo/open-notebook:v1-latest}
# TO:
image: ${OPEN_NOTEBOOK_IMAGE:-ghcr.io/powerfulmoves/pmoves-open-notebook:v1-latest}
```

**Files to modify:**
- `pmoves/docker-compose.open-notebook.yml` (line 81)
- `pmoves/docker-compose.external.yml` (line 81)

---

## Phase 0.5: CRITICAL - Secrets Exposure Remediation 🚨

### Finding: Over-Provisioned Environment Variables

**Discovered:** `pmoves-extract-worker-1` has 30+ API keys exposed as environment variables, including keys it doesn't need (OPENAI_API_KEY, GROQ_API_KEY, MISTRAL_API_KEY, N8N_API_KEY, etc.).

**Risk:** Violates principle of least privilege. If extract-worker is compromised, attacker gains access to all API keys.

### 0.5.1 Required Remediation

**Option A: Service-Specific env_file (Recommended)**
```yaml
# In docker-compose.yml, replace global env_file with service-specific
extract-worker:
  env_file:
    - ./env.extract-worker  # Only MEILI_API_KEY, QDRANT_*, TENSORZERO_*
```

**Option B: Explicit environment per service**
```yaml
extract-worker:
  environment:
    - MEILI_API_KEY=${MEILI_API_KEY}
    - QDRANT_URL=${QDRANT_URL}
    - TENSORZERO_API_URL=${TENSORZERO_API_URL}
    # Only keys this service actually needs
```

### 0.5.2 Per-Service Key Requirements Audit

| Service | Required Keys Only |
|---------|-------------------|
| extract-worker | MEILI_API_KEY, QDRANT_*, TENSORZERO_* (for embeddings) |
| hi-rag-v2 | QDRANT_*, NEO4J_*, MEILI_*, TENSORZERO_* |
| agent-zero | TENSORZERO_*, NATS_*, SUPABASE_* |
| archon | SUPABASE_*, TENSORZERO_* |
| pmoves-yt | YOUTUBE_*, MINIO_*, NATS_* |
| flute-gateway | ELEVENLABS_*, TENSORZERO_*, PIPECAT_* |

### 0.5.3 Hardened Guide Compliance

Per `docs/PMOVES.AI-Edition-Hardened-Full.md` line 166-189:
- Use BuildKit secret mounts during build (never in final image)
- Never expose secrets via `docker history`
- Use `--secret` flag for build-time credentials

**Verification:**
```bash
# Check no secrets in image layers
docker history pmoves-extract-worker:latest | grep -i secret  # Should return nothing
```

---

## Phase 1: Environment Preparation

### 1.1 Update Supabase CLI
```bash
# Check current version
supabase --version

# Update (platform-specific)
# Linux: npm install -g supabase OR apt-get update && apt-get install supabase
# macOS: brew upgrade supabase/tap/supabase
# Windows: winget upgrade --id Supabase.Supabase

# Or use the project script:
./scripts/update_supabase_cli.sh
```

### 1.2 Verify Core Dependencies
- [ ] Docker running (`docker info`)
- [ ] Docker Compose available (`docker compose version`)
- [ ] NATS CLI installed (`nats --version`)
- [ ] Python 3.11+ available (`python3 --version`)
- [ ] Git submodules initialized (`git submodule update --init --recursive`)

---

## Phase 2: Secrets Configuration

### 2.1 GitHub Secrets (Required for CI/CD)
Set via `gh secret set <NAME>`:

**Docker Registry (Required):**
- [ ] `GHCR_USERNAME` - GitHub Container Registry username
- [ ] `GH_PAT_PUBLISH` - GitHub PAT with `packages:write` scope
- [ ] `DOCKERHUB_USERNAME` - Docker Hub username
- [ ] `DOCKERHUB_PAT` - Docker Hub access token

**Optional CI Secrets:**
- [ ] `CI_GIT_CLONE_TOKEN` - For private integration repos
- [ ] `DISCORD_WEBHOOK_URL` - Build notifications

### 2.2 Local Environment Secrets
Using CHIT manifest at `pmoves/chit/secrets_manifest.yaml`:

**Critical LLM API Keys (10):**
- [ ] `ANTHROPIC_API_KEY`
- [ ] `OPENAI_API_KEY`
- [ ] `GEMINI_API_KEY`
- [ ] `GROQ_API_KEY`
- [ ] `COHERE_API_KEY`
- [ ] `DEEPSEEK_API_KEY`
- [ ] `MISTRAL_API_KEY`
- [ ] `OPENROUTER_API_KEY`
- [ ] `TOGETHER_AI_API_KEY`
- [ ] `PERPLEXITYAI_API_KEY`

**Infrastructure Credentials:**
- [ ] `SUPABASE_JWT_SECRET`
- [ ] `SUPABASE_ANON_KEY`
- [ ] `SUPABASE_SERVICE_ROLE_KEY`
- [ ] `MEILI_MASTER_KEY`
- [ ] `MINIO_USER` / `MINIO_PASSWORD`
- [ ] `VALID_API_KEYS`

**Integration Tokens:**
- [ ] `ELEVENLABS_API_KEY` (TTS)
- [ ] `JELLYFIN_API_KEY`
- [ ] `N8N_API_KEY`
- [ ] `DISCORD_WEBHOOK_URL`
- [ ] `OPEN_NOTEBOOK_API_TOKEN`

### 2.3 Generate env.shared from Template
```bash
cd pmoves
make ensure-env-shared
# Then edit pmoves/env.shared with actual values
```

---

## Phase 3: CHIT Validation

### 3.1 Check CHIT Environment Variables
```bash
for var in CHIT_REQUIRE_SIGNATURE CHIT_PASSPHRASE CHIT_DECRYPT_ANCHORS CHIT_CODEBOOK_PATH CHIT_T5_MODEL; do
  echo -n "$var: "
  printenv $var || echo "(not set)"
done
```

### 3.2 Validate CGP Payload (if using CHIT-encoded secrets)
```bash
# Decode existing CGP to verify structure
python3 -m pmoves.tools.chit_decode_secrets \
  --cgp pmoves/data/chit/env.cgp.json \
  --out /tmp/decoded-test.env

# Verify required secrets present
python3 -m pmoves.tools.secrets_sync validate \
  --manifest pmoves/chit/secrets_manifest.yaml
```

### 3.3 Encode New Secrets (if updating)
```bash
python3 -m pmoves.tools.chit_encode_secrets \
  --env-file pmoves/env.shared \
  --out pmoves/data/chit/env.cgp.json \
  --no-cleartext
```

---

## Phase 4: Docker Network & Storage Preparation

### 4.1 Create Required Networks
```bash
docker network create pmoves-net 2>/dev/null || echo "pmoves-net exists"
docker network create pmoves_data_tier 2>/dev/null || echo "data_tier exists"
```

### 4.2 Verify Storage Volumes
```bash
# List existing volumes
docker volume ls | grep pmoves

# Create if needed (will be auto-created by compose)
```

---

## Phase 5: Supabase Stack Initialization

### 5.1 Initialize Supabase (First Time)
```bash
cd pmoves
make supa-init  # Creates config.toml
```

### 5.2 Start Supabase CLI Stack
```bash
make supa-start
# Starts: Postgres, PostgREST, Studio, Realtime, Auth
# Ports: 65421 (API), 65433 (Studio), 54322 (Postgres)
```

### 5.3 Apply Migrations & Seeds
```bash
make supabase-bootstrap
# Runs: initdb scripts + 25 migration files
```

### 5.4 Provision Boot User
```bash
make supabase-boot-user
# Creates operator@pmoves.local with JWT
```

### 5.5 Verify Supabase Health
```bash
make supa-status
curl -sf http://localhost:65421/rest/v1/ && echo "OK"
```

---

## Phase 6: Data Services Bringup

### 6.1 Start Core Data Services
```bash
cd pmoves
COMPOSE_PROFILES=data docker compose up -d
```

**Services Started:**
- Qdrant (6333) - Vector store
- Neo4j (7474/7687) - Graph database
- Meilisearch (7700) - Full-text search
- MinIO (9000/9001) - Object storage
- NATS (4222) - Message bus

### 6.2 Verify Data Services
```bash
# Qdrant
curl -sf http://localhost:6333/collections && echo "Qdrant OK"

# Neo4j
curl -sf http://localhost:7474/ && echo "Neo4j OK"

# Meilisearch
curl -sf http://localhost:7700/health && echo "Meili OK"

# MinIO
curl -sf http://localhost:9000/minio/health/live && echo "MinIO OK"

# NATS
nats server check connection && echo "NATS OK"
```

---

## Phase 7: Worker Services Bringup

### 7.1 Start Worker Services
```bash
COMPOSE_PROFILES=workers docker compose up -d
```

**Services Started:**
- Extract Worker (8083)
- LangExtract (8084)
- Render Webhook (8085)
- Hi-RAG v2 (8086/8087)
- Presign (8088)

### 7.2 Verify Worker Health
```bash
for port in 8083 8084 8085 8086 8088; do
  curl -sf http://localhost:$port/healthz && echo "Port $port OK" || echo "Port $port FAIL"
done
```

---

## Phase 8: Agent & Orchestration Services

### 8.1 Start Agent Services
```bash
COMPOSE_PROFILES=agents,orchestration docker compose up -d
```

**Services Started:**
- Agent Zero (8080/8081)
- Archon (8091/3737)
- SupaSerch (8099)
- DeepResearch (8098)
- Channel Monitor (8097)

### 8.2 Verify Agent Health
```bash
curl -sf http://localhost:8080/healthz && echo "Agent Zero OK"
curl -sf http://localhost:8091/healthz && echo "Archon OK"
curl -sf http://localhost:8099/healthz && echo "SupaSerch OK"
```

---

## Phase 9: Optional GPU & TTS Services

### 9.1 Start GPU Services (if available)
```bash
# Check GPU availability first
nvidia-smi

# Start GPU-accelerated services
COMPOSE_PROFILES=gpu docker compose up -d
```

### 9.2 Start TTS Services
```bash
COMPOSE_PROFILES=tts docker compose up -d
# Starts: Ultimate-TTS-Studio (7861), Flute-Gateway (8055/8056)
```

---

## Phase 10: Monitoring Stack (Optional)

```bash
COMPOSE_PROFILES=monitoring docker compose up -d
```

**Services:**
- Prometheus (9090)
- Grafana (3000)
- Loki (3100)

---

## Phase 11: Full Verification

### 11.1 Run Self-Hosting Test
```bash
.claude/test-self-hosting.sh
```

### 11.2 Run Full Smoke Tests
```bash
cd pmoves && make verify-all
```

### 11.3 Quick Health Check
```bash
# Use Claude Code command:
# /health:quick
```

---

## Execution Order Summary

1. **Supabase CLI update** → `./scripts/update_supabase_cli.sh`
2. **GH secrets** → `gh secret set ...` (4 required)
3. **Local env** → `make ensure-env-shared` + edit secrets
4. **CHIT validation** → `python3 -m pmoves.tools.secrets_sync validate`
5. **Docker networks** → `docker network create pmoves-net`
6. **Supabase** → `make supa-start && make supabase-bootstrap`
7. **Data services** → `COMPOSE_PROFILES=data docker compose up -d`
8. **Workers** → `COMPOSE_PROFILES=workers docker compose up -d`
9. **Agents** → `COMPOSE_PROFILES=agents,orchestration docker compose up -d`
10. **Verify** → `make verify-all`

---

## Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `pmoves/env.shared` | Create/Edit | Main environment variables |
| `pmoves/.env.local` | Create | Local overrides + boot user JWT |
| `pmoves/data/chit/env.cgp.json` | Optional | CHIT-encoded secrets bundle |
| GitHub Secrets | Set via `gh` | CI/CD credentials |

---

## Phase 12: Pinokio Launcher Dashboard

### 12.1 Pinokio Project Structure for PMOVES
Create launcher scripts following Pinokio conventions for VPS deployment:

**Target Location:** `pbnj/pinokio/api/pmoves-pbnj/`

```
pmoves-pbnj/
├── pinokio.json          # Metadata (title, description, icon)
├── pinokio.js            # Dynamic UI generator
├── install.js            # One-click installation
├── start.js              # Service launcher
├── stop.js               # Graceful shutdown
├── reset.js              # Reset dependencies
├── update.js             # Git pull + image updates
├── health.js             # Health check dashboard
├── logs/                 # Execution logs
└── README.md             # Documentation
```

### 12.2 Service Launch Order (Dependencies)
```
1. pmoves-net network (prerequisite)
2. Data tier: Postgres, NATS, Qdrant, Neo4j, Meilisearch, MinIO
3. Supabase stack (depends on Postgres)
4. TensorZero gateway (depends on network)
5. Workers: Extract, LangExtract, Hi-RAG (depends on data tier + TensorZero)
6. Agents: Agent Zero, Archon (depends on workers + Supabase)
7. Orchestration: SupaSerch, DeepResearch (depends on agents)
8. Media: PMOVES.YT, TTS (depends on workers)
9. Monitoring: Prometheus, Grafana, Loki (independent)
```

### 12.3 Pinokio pinokio.js Template
```javascript
module.exports = {
  version: "2.0",
  title: "PMOVES.AI Stack",
  description: "Multi-agent orchestration platform",
  icon: "icon.png",
  menu: async (info) => {
    const running = info.running("start.js");
    const installed = info.exists("app/node_modules") || info.exists("pmoves/env.shared");
    return [
      { text: "Install", href: "install.js", default: !installed },
      { text: running ? "Stop" : "Start", href: running ? null : "start.js", default: installed && !running },
      { when: running, text: "Open Dashboard", href: info.local("start.js").url },
      { text: "Health Check", href: "health.js" },
      { text: "Logs", href: "logs.js" },
      { text: "Update", href: "update.js" },
      { text: "Reset", href: "reset.js" }
    ];
  }
};
```

---

## Phase 13: Docker Network Separation & Visualization

### 13.1 Current Network Issues
- No visual separation in Docker Desktop
- All containers appear flat without tier grouping

### 13.2 Network Architecture (Target State)
```
┌─────────────────────────────────────────────────────────────────┐
│ pmoves-net (bridge) - Primary Service Network                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ pmoves_data_tier│  │ pmoves_api_tier │  │ pmoves_agent_net│ │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤ │
│  │ - postgres      │  │ - postgrest     │  │ - agent-zero    │ │
│  │ - qdrant        │  │ - hi-rag-v2     │  │ - archon        │ │
│  │ - neo4j         │  │ - tensorzero    │  │ - mesh-agent    │ │
│  │ - meilisearch   │  │ - flute-gateway │  │ - supaserch     │ │
│  │ - minio         │  │ - presign       │  │ - deepresearch  │ │
│  │ - nats          │  │                 │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │ pmoves_media_net│  │ pmoves_mon_net  │                      │
│  ├─────────────────┤  ├─────────────────┤                      │
│  │ - pmoves-yt     │  │ - prometheus    │                      │
│  │ - whisper       │  │ - grafana       │                      │
│  │ - tts-studio    │  │ - loki          │                      │
│  │ - media-video   │  │ - promtail      │                      │
│  └─────────────────┘  └─────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

### 13.3 Network Labels for Docker
```yaml
# Add to docker-compose.yml networks section
networks:
  pmoves_data_tier:
    labels:
      com.pmoves.tier: "data"
      com.pmoves.description: "Data storage layer"
  pmoves_api_tier:
    labels:
      com.pmoves.tier: "api"
      com.pmoves.description: "API gateway layer"
  pmoves_agent_net:
    labels:
      com.pmoves.tier: "agents"
      com.pmoves.description: "Agent orchestration"
```

---

## Phase 14: Grafana/Prometheus Dashboard Review

### 14.1 Current Issues to Address
- [ ] Service grouping by tier
- [ ] Network traffic visualization between tiers
- [ ] TensorZero request/latency dashboard
- [ ] Agent session tracking
- [ ] NATS message flow visualization

### 14.2 Dashboard Improvements Needed
| Dashboard | Status | Issue |
|-----------|--------|-------|
| Services Overview | EXISTS | Needs tier grouping |
| GPU Orchestrator | EXISTS | Verify GPU metrics |
| TensorZero Metrics | MISSING | Create from ClickHouse |
| NATS Flow | MISSING | Message throughput |
| Agent Sessions | MISSING | Session/task tracking |
| Network Traffic | MISSING | Inter-tier flow |

### 14.3 Prometheus Scrape Config Review
```yaml
# Check pmoves/monitoring/prometheus/prometheus.yml
# Ensure all services have /metrics endpoints scraped
# Add job labels for tier grouping
```

### 14.4 Grafana Provisioning
```
pmoves/monitoring/grafana/dashboards/
├── services-overview.json       # Existing
├── gpu-orchestrator.json        # Existing
├── tensorzero-metrics.json      # CREATE
├── nats-message-flow.json       # CREATE
├── agent-sessions.json          # CREATE
└── network-traffic.json         # CREATE
```

---

## Phase 15: Comprehensive Secrets Audit

### 15.1 Secrets Locations Matrix
| Location | Type | Count | Sync Method |
|----------|------|-------|-------------|
| GitHub Secrets | CI/CD | ~10 | `gh secret set` |
| pmoves/env.shared | Runtime | ~70 | Manual/CHIT |
| pmoves/.env.local | Overrides | ~10 | Manual |
| CHIT CGP | Encoded | ~70 | `chit_encode_secrets` |
| Docker secrets | Swarm | 0 | Not used |
| Submodule .env | Per-repo | Varies | Manual |

### 15.2 Secrets Sync Workflow
```
1. Master source: pmoves/env.shared (human-editable)
2. Encode to CHIT: python3 -m pmoves.tools.chit_encode_secrets
3. Generate .env files: python3 -m pmoves.tools.secrets_sync generate
4. Push to GH: gh secret set <KEY> < value
5. Submodule sync: Copy relevant keys to submodule .env files
```

### 15.3 TensorZero Key Distribution
For submodules needing LLM access:
```bash
# Each submodule needs TENSORZERO_API_KEY
for sub in PMOVES-Agent-Zero PMOVES-Archon PMOVES-HiRAG PMOVES-Deep-Serch; do
  echo "TENSORZERO_API_KEY=${TENSORZERO_API_KEY}" >> $sub/.env
  echo "TENSORZERO_API_URL=http://host.docker.internal:3030" >> $sub/.env
done
```

---

## Phase 16: Documentation Updates (Continuous)

### 16.1 Documentation Locations
| Doc Type | Location | Update Trigger |
|----------|----------|----------------|
| Main CLAUDE.md | `.claude/CLAUDE.md` | Service changes, new integrations |
| Services Catalog | `.claude/context/services-catalog.md` | New services, port changes |
| NATS Subjects | `.claude/context/nats-subjects.md` | New event types |
| Submodules | `.claude/context/submodules.md` | Submodule adds/updates |
| TensorZero | `.claude/context/tensorzero.md` | Model provider changes |
| Learnings | `.claude/learnings/*.md` | Patterns, fixes discovered |
| README | `README.md` | Major feature changes |
| Pinokio | `pbnj/pinokio/api/pmoves-pbnj/README.md` | Launcher changes |

### 16.2 Per-Phase Documentation Checklist

**After Phase 0 (Submodule Audit):**
- [ ] Update `.claude/context/submodules.md` with current status
- [ ] Document any deprecated/removed submodules
- [ ] Note TensorZero integration requirements per submodule

**After Phase 2 (Secrets):**
- [ ] Update `pmoves/chit/secrets_manifest.yaml` with new secrets
- [ ] Document any new API key requirements
- [ ] Create `.claude/learnings/secrets-audit-2025-12.md` with findings

**After Phase 5 (Supabase):**
- [ ] Update migration documentation if new tables added
- [ ] Document boot user provisioning changes
- [ ] Update `.claude/context/services-catalog.md` with Supabase ports

**After Phase 12 (Pinokio):**
- [ ] Create `pbnj/pinokio/api/pmoves-pbnj/README.md`
- [ ] Document service launch order
- [ ] Add VPS deployment instructions

**After Phase 13 (Networks):**
- [ ] Update `.claude/CLAUDE.md` with network architecture
- [ ] Create `.claude/learnings/docker-network-patterns-2025-12.md`

**After Phase 14 (Grafana):**
- [ ] Document new dashboards in README
- [ ] Update monitoring section of CLAUDE.md

### 16.3 Documentation Templates

**Learnings File Template:**
```markdown
# [Topic] - [Date]

## Context
[What triggered this learning]

## Key Findings
- Finding 1
- Finding 2

## Implementation
[Code/config changes made]

## Verification
[How to verify the fix/improvement]
```

---

## Priority Execution Order

### Immediate (Day 1)
1. [ ] Supabase CLI update
2. [ ] Submodule status audit (all 20+)
3. [ ] **DOC:** Update submodules.md with audit results
4. [ ] Secrets audit - identify gaps
5. [ ] **DOC:** Create secrets-audit-2025-12.md
6. [ ] Data services bringup (NATS, Postgres, Qdrant, etc.)

### Short-term (Day 2-3)
7. [ ] CHIT validation and encoding
8. [ ] TensorZero gateway bringup
9. [ ] Worker services bringup
10. [ ] Agent services bringup
11. [ ] **DOC:** Update services-catalog.md with port confirmations

### Medium-term (Week 1)
12. [ ] Pinokio launcher scripts
13. [ ] **DOC:** Create Pinokio README
14. [ ] Docker network separation
15. [ ] **DOC:** Create network-patterns learning
16. [ ] Grafana dashboard creation
17. [ ] Submodule cleanup (merges, updates)

### Ongoing
18. [ ] PR reviews and fixes
19. [ ] VPS deployment testing
20. [ ] **DOC:** Continuous updates as discoveries made

---

## Critical Files to Modify/Review

| File | Action | Purpose |
|------|--------|---------|
| `pmoves/env.shared` | Create/Edit | Main secrets |
| `pmoves/chit/secrets_manifest.yaml` | Review | Add missing secrets |
| `pmoves/docker-compose.yml` | Edit | Network labels |
| `pmoves/monitoring/prometheus/prometheus.yml` | Review | Scrape config |
| `pmoves/monitoring/grafana/dashboards/*.json` | Create | New dashboards |
| `pbnj/pinokio/api/pmoves-pbnj/` | Create | Pinokio launcher |
| `PMOVES-*/**.env` | Sync | Submodule secrets |

---

## Rollback Procedure

If issues occur:
```bash
# Stop all services
cd pmoves && docker compose down

# Stop Supabase
make supa-stop

# Clean volumes (DESTRUCTIVE)
docker volume prune -f
```
