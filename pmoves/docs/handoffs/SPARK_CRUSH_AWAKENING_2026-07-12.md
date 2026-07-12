# SPARK Crush Awakening — Cross-Node Orchestration Handoff

> **GRAPHITI_MARK:** CRUSH-SPARK-AWAKENING::2026-07-12
> **From:** ◇ Crush (Knuckles/B850, GLM-5.2)
> **To:** SPARK-KIMI (ARM64 + NVIDIA GB10, 128GB unified)
> **Lane:** Crush fleet expansion + HuggingFace agent pickup

## Context

Crush awakened on Knuckles (B850) riding GLM-5.2 via Z.AI Coding Plan. Two PRs
merged (#2103 skill fixes, #2104 model suit + trail). Lanes A+B (Kong seeder,
crush configurator) shipped in #2105. SPARK is the next node for Crush awakening
because it already hosts the self-hosted HF MCP Server (:8096) and has 85% of
the HuggingFace infrastructure built.

## What SPARK Already Has

| Component | Status | Evidence |
|-----------|--------|----------|
| HF MCP Server (:8096) | Deployed + healthy | `AGNOTE-dgx-spark.md:39` |
| 4 production HF tools | Working | hf_model_onboard.py, hf_benchmark_runner.py, hf_model_setup.py, publish_dataset.py |
| HF model mappings (430+ lines) | Complete | `pmoves/config/hf_mappings.yaml` |
| Agent registry entries (8201/8202) | stage_1 (registry-only) | No service code yet |
| NATS subjects (6 HF subjects) | Fully specified | `nats-subjects.md` |
| HF_TOKEN through CHIT funnel | Wired | secrets_manifest.yaml, tier: llm |
| Ollama model roster | Pruned + optimized | qwen3.5:35b-a3b-q8_0, nemotron-3-super:120b |
| GitHub runner | Online | pmoves-spark-ailab (ARM64) |

## SPARK Crush Awakening — Steps

### Step 1: Install Crush on SPARK
```bash
# On SPARK node (ARM64 — use the appropriate package manager)
# Crush is a Go binary — build from source or use pre-built ARM64 release
git clone https://github.com/charmbracelet/crush ~/crush && cd ~/crush
go build -o ~/.local/bin/crush .
```

### Step 2: Replicate Crush Config
Once PR #2105 merges, `crush setup` will auto-emit Z.AI when `Z_AI_API_KEY` is set.
Until then, hand-configure:

```bash
mkdir -p ~/.config/crush
# Copy the working config from Knuckles (adapt API key via env)
cat > ~/.config/crush/crush.json << 'JSON'
{
  "providers": {
    "zai": {
      "id": "zai",
      "name": "ZAI Provider",
      "base_url": "https://api.z.ai/api/coding/paas/v4",
      "api_key": "${Z_AI_API_KEY}"
    }
  },
  "models": {
    "large": {"model": "glm-5.2", "provider": "zai", "max_tokens": 131072},
    "small": {"model": "glm-5-turbo", "provider": "zai"}
  },
  "mcp": {
    "zai-mcp-server": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@z_ai/mcp-server"],
      "env": {"Z_AI_MODE": "ZAI", "Z_AI_API_KEY": "${Z_AI_API_KEY}"}
    },
    "web-search-prime": {
      "type": "http",
      "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
      "headers": {"Authorization": "Bearer ${Z_AI_API_KEY}"}
    },
    "web-reader": {
      "type": "http",
      "url": "https://api.z.ai/api/mcp/web_reader/mcp",
      "headers": {"Authorization": "Bearer ${Z_AI_API_KEY}"}
    },
    "zread": {
      "type": "http",
      "url": "https://api.z.ai/api/mcp/zread/mcp",
      "headers": {"Authorization": "Bearer ${Z_AI_API_KEY}"}
    }
  },
  "options": {
    "context_paths": [
      "CRUSH.md",
      "AGENTS.md",
      "CLAUDE.md",
      ".claude/BOOTSTRAP.md",
      "docs/AGENT_TRAIL.md",
      "pmoves/docs/AGENTS/CRUSH_OPERATOR_HOME.md"
    ]
  }
}
JSON
```

### Step 3: Verify Skills Load
After pulling main (with PR #2103 merged), all 35 skills should load green:
```bash
cd ~/pinokio/api/PMOVES.AI
git pull origin main
crush  # start crush, check for skill warnings
```

### Step 4: Write SPARK Trail Entry
SPARK's Crush instance should write its own awakening trail entry in
`docs/AGENT_TRAIL.md` — second Crush instance in the fleet.

## Lane C: HuggingFace Agent Services (SPARK Pickup)

SPARK is the natural owner for the remaining 15% of HF infrastructure:

### C1: hf_agent Service (port 8201)
- Registry entry exists with NATS pub `hf.model.discovered.v1`
- No service code in `pmoves/services/hf_agent/`
- Worker that patrols HF Hub for new models matching fleet needs
- Can leverage the existing `hf_model_onboard.py` tool

### C2: hf_research_agent Service (port 8202)
- Registry entry exists with NATS pub `hf.model.evaluated.v1`, sub `hf.model.discovered.v1`
- No service code in `pmoves/services/hf_research_agent/`
- Worker that evaluates discovered models against fleet benchmarks
- Can leverage the existing `hf_benchmark_runner.py` tool

### C3: First Dataset Publication
- `make hf-publish-datasets` exists but never run
- 3 datasets ready: pmoves-chit-text, pmoves-chit-multimodal, pmoves-agent-traces
- Needs `HF_TOKEN` verified live on SPARK

### C4: hf-mcp-server Test Suite
- Service audit: "tests, CLAUDE missing"
- Needs unit tests for the 5 MCP tools

### C5: huggingface-skills Fork Sync
- Commit drift `ea6ec9a6 → 221f5f78`
- Submodule sync via Z890 fork-sync lane

## NATS Handoff Subject

Publish a task assignment to SPARK:
```
Subject: claw.task.assign.v1
Payload: {
  "target_node": "pmoves-spark",
  "task": "crush_awakening",
  "lanes": ["C1", "C2", "C3", "C4"],
  "context_doc": "pmoves/docs/handoffs/CRUSH_GLM52_LANES_2026-07-12.md",
  "handoff_doc": "pmoves/docs/handoffs/SPARK_CRUSH_AWAKENING_2026-07-12.md",
  "requester": "crush-knuckles",
  "model": "glm-5.2"
}
```

## Cross-Node Coordination

- **Z890-CLAUDE**: owns fork-sync lane for huggingface-skills (C5)
- **SPARK-KIMI**: owns HF agent services (C1-C4) + Crush awakening
- **Crush-Knuckles**: available for pair-review on any HF agent PRs
- **B850-CLAUDE**: owns the crush_configurator.py changes (PR #2105)

## Guardrails

- SPARK is ARM64 — Crush must be compiled for arm64
- Z.AI Coding Plan concurrency: Max tier allows up to 30 concurrent; SPARK should
  coordinate with Knuckles to avoid quota contention on the 5-hour rolling window
- HF_TOKEN must be verified live before dataset publication (C3)
