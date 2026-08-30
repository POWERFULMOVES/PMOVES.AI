# HERMES Agent Node Profiles

Per-node Hermes Agent (`~/.hermes/config.yaml`) profile definitions for the PMOVES.AI fleet.

## How to use

1. Install Hermes Agent:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
   ```

2. Create the shared base profile:
   ```bash
   hermes profile create pmoves-hermes
   ```

3. Copy the node-specific YAML into your profile config:
   ```bash
   # Example for Z890 (THIS NODE)
   cp pmoves/config/profiles/hermes/z890.yaml ~/.hermes/profiles/pmoves-hermes/config.yaml
   hermes profile use pmoves-hermes
   ```

4. Populate secrets:
   ```bash
   make -C pmoves secrets-funnel
   # Copy relevant env vars into ~/.hermes/profiles/pmoves-hermes/.env
   ```

## Profile Matrix

| File | Node | GPU | Primary Local Model | Gateway | Key Notes |
|------|------|-----|---------------------|---------|-----------|
| `elder-melchor.yaml` | **Elder-Melchor (THIS NODE)** | GTX 1650 4GB + UHD 630 | `hermes3:8b` (Q4/CPU) | 7700 | **You are here**. Laptop, Win10, i7-9750H, 32GB RAM |
| `z890.yaml` | Z890 | RTX 3090 Ti 24GB | `hermes3:8b` | 7700 | Windows 11 desktop, bash via git-bash, Ctrl+Enter newline |
| `5090.yaml` | pmoves-5090 | RTX 5090 32GB | `hermes3:8b` (+70b staging) | 7700 | Primary GPU workhorse, +rl/+moa/video |
| `4090.yaml` | pmoves-4090 | RTX 4090 Mobile 16GB | `hermes3:8b` | 7700 | Mobile, battery-saver disable gateway |
| `spark.yaml` | pmoves-spark | GB10 128GB unified | `hermes3:70b` | 7700 | **70B PRIMARY**, NeMo Omni, large inference events |
| `b850.yaml` | pmoves-b850 / rdna4 | Dual AMD R9700 64GB | `hermes3:8b` (ROCm) | 7700 | ROCm 7.1, dual-GPU row-split, NOT CUDA |
| `kvm4-1.yaml` | kvm4-1 | None | openrouter remote | 7700 | Headless, no TTS/STT, NATS leaf |

## Model Size Routing Rules

- **8B models** (`hermes3:8b`, Unsloth 8B): Any node with Ollama (Z890, 5090, 4090, B850)
- **70B models** (`hermes3:70b`, Unsloth 70B): **Spark ONLY** (GB10 128GB unified)
- **Embedding** (Gemma4): Z890, 5090, Spark, B850 via HF
- **NeMo Omni** (72B VL): **Spark ONLY** (requires NeMo >= 2.1)

## ROCm Notes (B850 / RDNA4)

- Ollama must be built with ROCm support (`OLLAMA_BACKEND=rocm`)
- `HIP_VISIBLE_DEVICES=0,1` required for dual-GPU visibility
- GGUF row-split via llama.cpp with ROCm backend
- Hermes 70B GGUF untested on ROCm -- assume Spark-only for 70B

## Windows Notes (Z890)

- Config must be UTF-8 **without BOM** (re-save if `hermes doctor` throws HTTP 400)
- Use **Ctrl+Enter** for newline in Hermes CLI (Alt+Enter trapped by Windows Terminal)
- Forward-slash paths preferred: `C:/Users/...`
- `WinError 10106` in sandbox = missing `SYSTEMROOT` (allowlisted in modern Hermes)

## See also

- `pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md` -- full integration spec
- `pmoves/configs/tac_trees/node-hermes-agent.tac.yaml` -- integration roadmap
- `.claude/skills/hermes-agent-integration/SKILL.md` -- operator skill
