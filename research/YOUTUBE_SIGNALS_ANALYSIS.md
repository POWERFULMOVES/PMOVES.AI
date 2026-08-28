# YouTube Signals Analysis — PMOVES.AI Model Integration Framework

**Date:** 2026-04-19
**Source:** Playlist PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8 (80 videos, 5 high-signal analyzed)
**Transcripts:** Not included in repo (full transcripts available from YouTube playlist, analyzed locally)

---

## 1. Executive Summary

Five high-signal videos reveal a rapidly shifting agent landscape directly impacting PMOVES.AI:

1. **NemoClaw is NVIDIA's official agent framework for DGX Spark** — not a competitor to ClaWZ, but a reference architecture. Uses Nemotron-3 Super as default model via Ollama. First-class NIM Cloud citizen on Spark.
2. **Hermes Agent replaces OpenClaw for many users** — local-first, home-folder config, skills system, MCP support, GLM-5.1 integration confirmed. ClaWZ fork being 1092 commits behind upstream is an industry-wide pattern.
3. **Qwen3.6 vs Gemma4 benchmarks provide concrete model suit data** — Qwen3.6 excels at speed (3262 tok/s at 2K), Gemma4 dense excels at throughput (10,000 tok/s at 8K on dual 4090). Both fit in 16GB VRAM at Q4.
4. **Harness pattern is the emerging architecture** — Cole Medin's Archon guide (2hr45m) defines coding harnesses as the next evolution beyond raw agent frameworks.
5. **DGX Spark confirmed as GB10 Grace-Blackwell** — NVIDIA presenters explicitly name it, describe as "GPU in a box, tons of unified memory."

---

## 2. Per-Video Analysis

### 2.1 Hermes Agent + GLM-5.1 (AICodeKing, 12:29)

**Architecture:**
- Open-source agent by Nouse Research
- Terminal-based, uses tools, browses, executes code, messaging apps, memory, skills, MCP servers
- Config lives in `~/` home folder with: config file, memories folder, skills folder, cron folder, .o file
- Skills ≠ MCP — skills are reusable procedures, MCP is external tool integration
- Work trees support for multi-branch coding

**GLM-5.1 Integration:**
- Cloud access via NVIDIA API: base URL `integrate.api.nvidia.com/v1`
- Set model to any hosted model (GLM-5.1, etc.)
- Free tier available for decent cloud models without paying
- Local model support: can pull GLM4, Qwen, Llama via Ollama
- For coding/research/larger tasks: recommends cloud model (GLM-5.1) over local

**Why Hermes over OpenClaw:**
- More polished, more practical, easier daily use
- Local-first design (config in home folder, not project-locked)
- Better MCP integration (install `mcp` extra)
- Can turn tools/databases into skills
- Telegram integration built-in
- Lower API bills

**PMOVES Integration Points:**
- GLM-5.1 cloud config pattern (NVIDIA API endpoint) can inform A0_SET_ variables
- Skills folder pattern maps to PMOVES skills/ directory
- Memory pattern (facts + procedures) maps to PMOVESCHIT Distillation config_tuning layer
- Hermes as potential ClaWZ replacement evaluation target

---

### 2.2 NemoClaw on DGX Spark (NVIDIA Developer, 52:34)

**DGX Spark Hardware (confirmed by NVIDIA presenters):**
- GB10 Grace-Blackwell chip inside
- "GPU in a box, tons of unified memory"
- Local development platform
- Can run models and agents locally
- Also used for custom neural net training (data science)

**NemoClaw Architecture:**
- NVIDIA's official agent framework for DGX Spark
- Uses Ollama for local model serving
- NIM Cloud is "first-class citizen for Spark" — tested and optimized
- Can run multiple claws on the same DGX Spark
- JSON configuration (model can modify its own config — guardrail concern raised)

**Recommended Model: Nemotron-3 Super**
- "Super efficient" for single-use-case agents on Spark
- Leaves 20-25-28GB for KV cache after model load
- Conversations won't be huge at that KV cache size — task-dependent
- Deploy configs available in `nvidia/NeMo/NeMoTron` repo
- Learning paths available for tool calling, memory, and Spark deployment

**Memory Math on DGX Spark (128GB unified):**
- Nemotron-3 Super model weights: ~100GB estimated
- Remaining for KV cache: 20-28GB
- Implication: longer conversations need smaller models or quantization

**Guardrails:**
- Question raised: how to prevent model from changing its own JSON config
- No clear answer provided — acknowledged as open problem

**PMOVES Integration Points:**
- **Nemotron-3 Super as DGX Spark local model** — add to model suit profiles
- NemoClaw as reference architecture for ClaWZ on Spark
- NVIDIA API endpoint `integrate.api.nvidia.com/v1` for cloud fallback
- NIM Cloud first-class support means Nemotron models work seamlessly
- Multiple claws on same Spark = multi-agent pattern validation
- Guardrail gap: PMOVESCHIT CHIT signatures could solve the config-modification problem

---

### 2.3 AI Coding Harnesses (Cole Medin, 30:48)

**Harness Concept:**
- Next evolution beyond raw agent frameworks (Claude Code, Cursor, etc.)
- A harness wraps the coding agent with: structured workflows, memory, error recovery, multi-step task management
- Different from simple agent — harness provides the scaffolding, agent provides the intelligence

**Key Patterns:**
- Harness manages the agent's context window (preventing overflow)
- Structured task decomposition before agent execution
- Error handling and retry loops built into harness, not agent prompts
- Memory persistence across sessions
- Tool orchestration managed by harness layer

**PMOVES Integration Points:**
- Harness pattern maps directly to PMOVESCHIT Distillation pipeline
- config_tuning = harness model config
- context_priming = harness prompt management + memory
- The "suit" concept in PMOVES = harness configuration per model
- ClaWZ could be restructured as a harness rather than a fork

---

### 2.4 Qwen3.6 vs Gemma4 Benchmarking (Digital Spaceport, 31:44)

**Test Configuration:**
- Ollama with NGL=999 (offload all layers to GPU)
- num_batch=4096, ubatch=1024
- Q4 quantization for all models
- Tested at 2K, 4K, 8K, 16K, 32K context windows
- Hardware: dual RTX 3060 (12GB each), dual RTX 4090 (24GB each)

**Qwen3.6 Results (dual 3060, Q4):**
- VRAM demand: 15.9GB
- Prompt processing: 713 tok/s (2K) → 2,279 tok/s (8K) → 2,241 tok/s (16K)
- Text generation: 3,262 tok/s at 2K context
- Good at deeper agentic workflows (4K+ context where inbatch kicks in)

**Gemma4 Dense Results (dual 4090, Q4):**
- Prompt processing: 10,000 tok/s at 8K, 9,500 tok/s at 16K
- Text generation: 8,526 tok/s at 32K context
- "Insane" performance — best numbers of entire benchmark
- Still strong at 32K context

**Gemma4 MoE Results (dual 3060, Q4):**
- 830 tok/s at 2K context
- Significant performance hit when sharding to system RAM
- "Name of the game is fitting everything into VRAM"

**Key Insight:**
- Dense models >> MoE models when VRAM is constrained
- Dual 3060 (24GB total) can run Qwen3.6 Q4 fully in VRAM
- Dual 4090 (48GB total) runs Gemma4 dense Q4 with massive headroom
- DGX Spark (128GB unified) should run ANY of these with room to spare

**PMOVES Integration Points:**
- Qwen3.6 Q4: excellent for Agent Zero utility tasks (fast, fits small GPU)
- Gemma4 dense Q4: excellent for DGX Spark local model (massive throughput)
- Ollama config: NGL=999, num_batch=4096, ubatch=1024 are proven optimal
- VRAM math: Qwen3.6 Q4 ≈ 16GB, Gemma4 dense Q4 ≈ 20-24GB
- For DGX Spark: can run both simultaneously with 128GB unified memory

---

### 2.5 Full Archon Guide (Cole Medin, 2:45:31)

**Note:** 120K-word transcript. Key architecture concepts extracted via targeted scan.

**Archon Definition:**
- A coding harness framework — not an agent itself, but scaffolding around coding agents
- Built by Cole Medin as open-source project
- Designed to make coding agents (Claude Code, etc.) actually ship production code

**Architecture Components:**
- Task decomposition layer (break work into manageable chunks)
- Context window management (prevent overflow, smart truncation)
- Memory system (cross-session persistence)
- Error recovery (retry loops, fallback strategies)
- Multi-agent orchestration (delegate subtasks)
- Tool management (which tools available, when to use)

**Relationship to PMOVES Archon:**
- PMOVES Archon is the crawl/knowledge agent — different purpose
- Cole Medin's Archon is a coding harness — could inform how PMOVES structures agent workflows
- The "harness" pattern is applicable regardless of naming

---

## 3. Model Suit Profiles (Extracted)

### GLM-5.1 (Cloud via Z.AI / NVIDIA)

| Parameter | Value | Source |
|-----------|-------|--------|
| Provider | Z.AI MAX plan / NVIDIA integrate API | Hermes video |
| Base URL | `integrate.api.nvidia.com/v1` | Hermes video |
| Context Window | Large (specific number not stated) | — |
| Temperature | Not specified in transcripts | — |
| Prompt Style | Not specified — needs Z.AI docs check | — |
| Strengths | Free tier available, coding + research tasks | Hermes video |
| Weaknesses | Cloud-only (no local weights mentioned) | Hermes video |
| Local Fallback | None — use Qwen3.6 or Gemma4 locally | Inferred |

### Qwen3.6 (Local via Ollama)

| Parameter | Value | Source |
|-----------|-------|--------|
| Quantization | Q4_K_M (recommended) | Benchmark video |
| VRAM Required | ~15.9GB | Benchmark video |
| NGL | 999 (all layers GPU) | Benchmark video |
| num_batch | 4096 | Benchmark video |
| ubatch | 1024 | Benchmark video |
| Prompt Processing | 2,279 tok/s at 8K (dual 3060) | Benchmark video |
| Text Generation | 3,262 tok/s at 2K | Benchmark video |
| Strengths | Fast agentic workflows, fits 24GB GPU, good at 4K+ context | Benchmark video |
| Weaknesses | Slower than Gemma4 dense on equivalent hardware | Benchmark video |
| DGX Spark Estimate | Should exceed 5,000+ tok/s with 128GB unified | Inferred |

### Gemma4 Dense (Local via Ollama)

| Parameter | Value | Source |
|-----------|-------|--------|
| Quantization | Q4 (dense, not MoE) | Benchmark video |
| VRAM Required | ~20-24GB (dual 4090) | Benchmark video |
| Prompt Processing | 10,000 tok/s at 8K (dual 4090) | Benchmark video |
| Text Generation | 8,526 tok/s at 32K | Benchmark video |
| Strengths | Best throughput of all tested, maintains speed at 32K context | Benchmark video |
| Weaknesses | Larger VRAM footprint than Qwen3.6 | Benchmark video |
| DGX Spark Estimate | Should exceed 15,000+ tok/s — best local model for Spark | Inferred |
| Note | **Dense >> MoE** when VRAM is available | Benchmark video |

### Nemotron-3 Super (Local via Ollama on DGX Spark)

| Parameter | Value | Source |
|-----------|-------|--------|
| Target Platform | DGX Spark (GB10 Grace-Blackwell) | NVIDIA video |
| VRAM for Model | ~100GB (leaves 20-28GB KV cache) | NVIDIA video |
| Strengths | First-class NIM Cloud citizen, super efficient, NVIDIA-optimized | NVIDIA video |
| Weaknesses | Large model limits KV cache on 128GB Spark | NVIDIA video |
| Deploy Configs | `nvidia/NeMo/NeMoTron` repo | NVIDIA video |
| Use Case | Single-purpose agents (coding, retrieval) | NVIDIA video |

---

## 4. Harness Architecture Patterns

| Pattern | Source | PMOVES Application |
|---------|--------|-------------------|
| Home-folder config with memories/skills/cron | Hermes | Sidecar env template already does this — validate parity |
| Skills as reusable procedures (not MCP) | Hermes | PMOVES skills/ directory — confirm skills vs MCP distinction in docs |
| Harness wraps agent with scaffolding | Cole Medin | ClaWZ could be restructured as harness around Claude Code/GLM |
| Context window management layer | Cole Medin | Agent Zero already does this — document the pattern |
| Error recovery in harness, not prompts | Cole Medin | PMOVESCHIT CHIT signatures provide this at crypto level |
| Multi-agent delegation from harness | Cole Medin | Agent Zero subordinates already do this — formalize as pattern |
| Model modifies own config (guardrail problem) | NemoClaw | CHIT signed configs solve this — key differentiator |

---

## 5. ClaWZ Transition Signals

| Signal | Implication |
|--------|------------|
| Hermes Agent: "RIP OpenClaw" (video title) | OpenClaw ecosystem fracturing — multiple replacements emerging |
| NemoClaw: NVIDIA's official agent for DGX Spark | Vendor-backed alternative to OpenClaw — will get ongoing support |
| ClaWZ fork 1092 commits behind upstream | Maintenance burden growing — consider if fork is still worth it |
| Paperclip: zero-human company framework | Another OpenClaw alternative gaining traction |
| Meta Harness: MIT/Stanford academic backing | Harness pattern has institutional validation |

**Recommendation:** Rather than continuing to fork OpenClaw, evaluate NemoClaw (for DGX Spark) and Hermes (for terminal agents) as potential replacements. The harness pattern (wrap any coding agent) may be more sustainable than maintaining a fork.

---

## 6. DGX Spark Deployment Notes

- Confirmed GB10 Grace-Blackwell by NVIDIA presenters
- 128GB unified memory — can run Nemotron-3 Super (~100GB) + 20-28GB KV cache
- Ollama is the recommended local model server
- NIM Cloud is first-class (tested, optimized for Spark)
- Multiple agent instances ("claws") can run simultaneously
- cuTile kernels available for Spark-to-Cloud pipeline (video #22 in playlist)
- Can also run custom neural networks for training

**Recommended DGX Spark Model Stack:**
1. **Nemotron-3 Super** via Ollama — primary local agent model (NVIDIA-optimized)
2. **Gemma4 Dense Q4** via Ollama — high-throughput utility model (10K+ tok/s)
3. **Qwen3.6 Q4** via Ollama — fast agentic tasks (5K+ tok/s estimated)
4. **GLM-5.1** via NVIDIA API / Z.AI — cloud coding model with free tier
5. **Claude Sonnet** via OpenRouter — fallback coding model

All 5 can coexist: 3 local (Ollama) + 2 cloud (API). 128GB unified memory handles all local models simultaneously.

---

## 7. Priority Action Items

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | **Create model suit YAML profiles** for GLM-5.1, Qwen3.6, Gemma4, Nemotron-3 with extracted configs | 2hr | Foundation for entire framework |
| 2 | **Configure Ollama on DGX Spark** with proven settings: NGL=999, num_batch=4096, ubatch=1024 | 30min | Immediate performance gain |
| 3 | **Pull Nemotron-3 Super** via Ollama on DGX Spark, validate it fits with KV cache room | 1hr | NVIDIA-optimized local model |
| 4 | **Test Gemma4 Dense Q4** on DGX Spark — expect 15,000+ tok/s | 30min | Best throughput model validation |
| 5 | **Wire NVIDIA API endpoint** (`integrate.api.nvidia.com/v1`) as cloud fallback in Agent Zero | 30min | GLM-5.1 + Nemotron cloud access |
| 6 | **Evaluate NemoClaw** as ClaWZ replacement on DGX Spark — download and test | 2hr | Potential ClaWZ migration path |
| 7 | **Document harness pattern** in AGENTS/ — map Cole Medin's architecture to PMOVES agent taxonomy | 1hr | Architecture clarity |
| 8 | **Check Z.AI docs** for GLM-5.1 recommended temperature, context, prompt style | 30min | Complete GLM suit profile |
| 9 | **Update FLEET_INFRASTRUCTURE_ENHANCEMENT_REPORT** with NemoClaw as Spark agent framework | 30min | Doc accuracy |
| 10 | **Draft PMOVES_MODEL_INTEGRATION_FRAMEWORK.md** canonical reference | 2hr | Ties everything together |

---

## Appendix: Video Metadata

| # | ID | Title | Channel | Duration |
|---|----|-------|---------|----------|
| 4 | xS5wao4H4u4 | Local AI Qwen3.6 vs Gemma4 Benchmarking | Digital Spaceport | 31:44 |
| 11 | qMnClynCAmM | AI Coding Is Harnesses | Cole Medin | 30:48 |
| 12 | srx9iwnjK2M | Full Archon Guide | Cole Medin | 2:45:31 |
| 24 | N2LHg2-J3p8 | Build a Claw: NemoClaw on DGX Spark | NVIDIA Developer | 52:34 |

---

## Creator Pipeline Deep Dives (2026-04-24)

**Search window**: March 25 – April 24, 2026
**Method**: Fresh YouTube API searches via researcher subordinate. No prior analysis relied upon.
**Correction (2026-04-24)**: Prior note incorrectly claimed video srx9iwnjK2M was unverifiable/removed. yt-dlp confirmed it exists at playlist position 37 (2:45:31, 'Full Archon Guide - Build AI Coding Harnesses That Actually Ship (LIVE)' by Cole Medin). The original claim was a YouTube search indexing failure incorrectly encoded as fact. See `research/FRESH_VIDEO_ANALYSIS.md` for full transcript-grounded analysis.

---

### Harness Engineering (High Relevance Cluster)

| Priority | Title | Channel | Date | URL | Key Takeaway |
|----------|-------|---------|------|-----|-------------|
| 1 | Rethinking AI Agents: The Rise of Harness Engineering | PY | Apr 14 | https://www.youtube.com/watch?v=Xxuxg8PcBvc | "Same model. Same benchmark. 6x the performance difference." Harness as primary performance differentiator, not model. |
| 2 | Harness Engineering: Why AI Agents Fail Without It | Devsplainers | Apr 8 | https://www.youtube.com/watch?v=f2oP5mpluQg | Positions harness engineering as #1 skill for reliable AI coding agents in 2026. References OpenAI's bet on harness patterns. |
| 3 | Agent Zero x Paperclip: Governed Autonomous AI Operations | dumbfoundry | Apr 17 | https://www.youtube.com/watch?v=WNrBKq8DmlA | Combines Agent Zero (intelligence) with Paperclip (governance). Directly applicable to CHIT-as-governance-layer. |
| 4 | One Million Lines of Code. Zero Keystrokes | AI-plus-plus | Mar 19 | https://www.youtube.com/watch?v=nQqKP6liaF4 | OpenAI Codex case study shipping 1M lines via harness engineering. Scale validation. |
| 5 | Paradigm Shift: Harnesses to Protection Layers | htekdev | Mar 23 | https://www.youtube.com/watch?v=PcaccHNqfhI | Harnesses evolving into protection layers. Maps to CHIT fail-closed design. |

All five flagged as potential timeline accelerators. Harness engineering directly validates the CHIT-as-harness-layer thesis from Grand Convergence L2.

---

### Security

| Title | Channel | Date | URL | Relevance |
|-------|---------|------|-----|----------|
| CVE-2026-4308: SSRF Vulnerability in Agent-Zero AI Framework | infotech409 | Mar 17 | https://www.youtube.com/watch?v=96860FVjYIs | Moderate — security awareness for PMOVES hardening, not actionable how-to |

---

### Gaps Found

| Topic | Status |
|-------|--------|
| Archon + Agent Zero integration guides | **FOUND** — srx9iwnjK2M (Full Archon Guide, 2:45:31), DMXyDpnzNpY (Official Guide, 23:18), qMnClynCAmM (AI Coding Is Harnesses, 30:48), plus V3 explainers. Prior 'NO content found' was a search failure. |
| ComfyUI + Agent Zero (last 30 days) | NO content found (3 videos from Feb, all outside window) |
| PMOVES creator pipeline | NO content found (expected — niche) |
| coleam00 original content (last 30 days) | **ACTIVE** — 3 videos in user's playlist (positions 6, 35, 37), 8+ Archon-specific videos on channel. Prior claim of inactivity was false. |
| Playlist PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8 | **ACCESSIBLE** — 1,589 videos verified via yt-dlp --flat-playlist. Prior 'inaccessible' was a tool limitation, not a data limitation. |

---

### Assessment

The harness engineering space is active with 5 highly relevant videos in 30 days. These validate the PMOVES thesis that orchestration code (the harness) matters more than model selection. The dumbfoundry Agent Zero + Paperclip video is the most directly composable — it demonstrates governance wrapping around Agent Zero, which is architecturally identical to CHIT wrapping Agent Zero in PMOVES.

Archon-specific content is **abundant** on YouTube. Cole Medin has 8+ Archon-specific videos including a 2:45 live guide, an official guide, and multiple V3 explainers. The prior claim of absence was a search indexing failure incorrectly generalized. See `FRESH_VIDEO_ANALYSIS.md` Task 2 for full transcript-grounded analysis with fair comparison to PMOVES.

**Recommendation**: Transcribe the dumbfoundry (Agent Zero x Paperclip) and PY (Harness Engineering 6x) videos. Both are directly applicable to PMOVES architecture decisions and likely contain patterns that can be extracted and implemented within days.
| 62 | VBV4sxUBdsE | Hermes Agent + GLM-5.1: RIP OpenClaw | AICodeKing | 12:29 |
