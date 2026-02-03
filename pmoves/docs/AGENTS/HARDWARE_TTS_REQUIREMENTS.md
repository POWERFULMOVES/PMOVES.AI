# PMOVES.AI Hardware & TTS Requirements

Actionable specifications extracted from the PMOVES.AI Agentic Architecture documentation.

---

## Table of Contents

1. [Hardware Specifications](#hardware-specifications)
   - [Central Core (Heavy Compute Tier)](#central-core-heavy-compute-tier)
   - [Edge Compute (Jetson Orin Nano)](#edge-compute-jetson-orin-nano)
   - [Venice.ai Integration](#veniceai-integration)
2. [Required Models](#required-models)
3. [TTS Engine Templates](#tts-engine-templates)
   - [KOKORO TTS](#1-kokoro-tts-the-host)
   - [Fish Speech](#2-fish-speech-the-architect)
   - [IndexTTS2](#3-indextts2-the-opsengineer)
   - [VibeVoice](#4-vibevoice-the-podcast-mode)
4. [Punctuation Engineering Patterns](#punctuation-engineering-patterns)
5. [Reference Audio Requirements](#reference-audio-requirements)

---

## Hardware Specifications

### Central Core (Heavy Compute Tier)

| Specification | Requirement |
|---------------|-------------|
| **GPU** | NVIDIA RTX 3090 Ti / RTX 5090 |
| **VRAM** | 24GB - 32GB+ |
| **Role** | Deep Reasoning, Orchestration, Training, hosting "Brain" models |
| **Backend** | vLLM (mandatory for inference) |

**Primary Functions:**
- Agent Zero orchestration
- Hi-RAG reasoning
- Model training and fine-tuning
- High-throughput inference via continuous batching

### Edge Compute (Jetson Orin Nano)

| Specification | Requirement |
|---------------|-------------|
| **Hardware** | Jetson Orin Nano Super |
| **RAM** | 8GB |
| **Role** | Real-time perception, "Reflective" intelligence, local tool use, "Glance" operations |

**Configuration Requirements:**

1. **Phi-3-Mini (3.8B)**
   - Purpose: Local brain for command-and-control logic
   - Constraint: Must fit within 8GB memory envelope
   - Use Case: "Small Language Model" (SLM) for edge inference

2. **Qwen-2.5-Omni (Quantized)**
   - Format: 4-bit quantized (GGUF/INT4)
   - Purpose: Multi-modal interaction (text, audio, image)
   - Use Case: Unified perception stream without cloud latency

3. **YOLOv8**
   - Optimization: Compiled with TensorRT
   - Latency: Millisecond-level object detection
   - Use Case: "Glance" phase of Reflective GoG pipeline

**Jetson Bootstrap Checklist:**
- [ ] Install JetPack SDK
- [ ] Configure TensorRT for YOLOv8
- [ ] Deploy GGUF-quantized models
- [ ] Set up Docker stacks from `Cataclysm Studios Inc` directory
- [ ] Configure `host.docker.internal` networking

### Venice.ai Integration

| Configuration | Value |
|---------------|-------|
| **API Type** | OpenAI-compatible |
| **Access Models** | Qwen-235B, Llama-405B |
| **Purpose** | "Superintelligence as a Service" bridge |
| **Auth Mechanism** | VVV token staking (optional) |

**Integration Points:**
- Offload tasks exceeding local reasoning capacity
- Handle "Big Thread" architectural design tasks
- Provide frontier model capabilities without H100 clusters
- Privacy-focused, uncensored access

**Environment Variables:**
```bash
VENICE_API_KEY=<your-api-key>
VENICE_BASE_URL=https://api.venice.ai/v1
```

---

## Required Models

### Model Matrix

| Model | Parameters | Deployment | Purpose |
|-------|------------|------------|---------|
| **Qwen-2.5-14B** | 14B | Central Core | Agent Zero orchestration |
| **Phi-3-Medium** | 14B | Central Core | Alternative to Qwen for Agent Zero |
| **Phi-3-Mini** | 3.8B | Edge (Jetson) | Local command-and-control |
| **Qwen-2.5-Omni** | Variable (4-bit) | Edge (Jetson) | Multi-modal perception |
| **YOLOv8** | - | Edge (Jetson) | Real-time object detection |
| **DeepSeek-V3.1** | 70B (distilled) | Central Core | Complex multi-hop reasoning |
| **BGE-M3-Large** | - | Central Core | Embedding generation for Hi-RAG |

### Quantization Requirements

| Model | Quantization | Format | Target Hardware |
|-------|--------------|--------|-----------------|
| Qwen-2.5-Omni | INT4 | GGUF | Jetson Orin Nano |
| Phi-3-Mini | INT4/INT8 | GGUF | Jetson Orin Nano |
| DeepSeek-V3.1 | INT4 | GGUF | Dual RTX 3090 / RTX 5090 |

---

## TTS Engine Templates

### 1. KOKORO TTS (The "Host")

**Best For:** Natural flow, long introductions, warm narration

**Technique:** Punctuation Engineering

| Symbol | Effect | Duration |
|--------|--------|----------|
| `...` | Long Pause | ~600ms |
| `--` | Sharp break/Tone shift | Variable |
| `,` | Short breath | ~150ms |

**Example Script:**
```
Imagine a world where your local hardware isn't just a server... but a living organism.
We are looking at the P-MOVES dot A-I orchestration mesh. It's a distributed architecture--one that mirrors high-end production environments--but it lives entirely on your local metal.

No cloud... No leaks... Just raw, autonomous power.
```

**Voice Characteristics:**
- Warm, conversational tone
- Suitable for introductions and explanations
- Natural pacing with strategic pauses

---

### 2. Fish Speech (The "Architect")

**Best For:** High-speed technical jargon, excitement, manic energy

**Technique:** Reference Audio Cloning

**Reference Audio Requirements:**
| Parameter | Specification |
|-----------|---------------|
| Duration | 10 seconds |
| Style | Fast-talking tech reviewer |
| Examples | Linus Tech Tips, rapid tutorial style |

**Reference Text Example:**
```
"This is the fastest CPU we have ever tested and it is absolutely mind blowing."
```

**Target Text Examples:**

**Block A - Infrastructure:**
```
Correct. And this is not just storage... this is Local Inference!
We utilize Tensor-Zero to host Qwen models--ranging from four billion to thirty-two billion parameters--right on the edge. This ensures that the agent's intelligence remains on-site.
```

**Block B - Logic:**
```
Precisely! The mesh is bifurcated.
First, the Decision Engine--Agent Zero. It acts as an M-C-P bridge. It ingests events, processes context, and triggers the muscles.
Then... you have Archon, the Knowledge Manager. It coordinates with NATS and Supabase Realtime to maintain state stability across the entire mesh.
```

**Block C - Mesh:**
```
We call it the Unified Communication Mesh.
Agents coordinate via NATS messaging. We can actually observe the system "thinking" through events like claude.code.tool.executed.v1.
But the real breakthrough? Contextual Geometry Packets--or CGPs.
```

---

### 3. IndexTTS2 (The "Ops/Engineer")

**Best For:** Texture, grit, specific emotional control (whispers, authority)

**Technique:** Natural Language Style Prompts

**Style Prompt Matrix:**

| Block | Pitch | Speed | Voice | Tone |
|-------|-------|-------|-------|------|
| Hardware | Low | Slow | Gravelly | Serious |
| Muscles | Normal | Slightly faster | Clear | Authoritative |
| Self-Improvement | Deep | Slow | Whisper | Intense |

**Target Text by Block:**

**Block A - Hardware:**
Style Prompt: `Low pitch, slow speed, gravelly voice, serious`
```
It starts with the Local-First Infrastructure. We aren't renting power. We are provisioning it.
Inside the Cataclysm Studios Inc directory, you find the blueprint. We have automated OS installs, Jetson bootstrap scripts, and Docker stacks.
This allows edge hardware to mirror the production topology... exactly.
```

**Block B - Muscles:**
Style Prompt: `Normal pitch, authoritative, slightly faster`
```
And then... the muscles do the heavy lifting.
Services like P-Moves-Y-T for media ingestion, Deep-Research for data loops, and N-eight-N for workflow orchestration. They are autonomous services, feeding data back into the core.
```

**Block C - Self-Improvement:**
Style Prompt: `Deep voice, whisper, intense`
```
And it learns.
The Evo-Controller reads those packets and emits "tuning capsules" back into the bus.
It creates a self-improving loop. We even run a full smoke-test harness--make verify-all--to validate every agent locally before we commit a single line of code.
```

---

### 4. VibeVoice (The "Podcast" Mode)

**Best For:** Multi-speaker conversations, podcast-style content

**Technique:** Speaker Labeling

**Supported Mode:** Multi-Speaker Inference

**Speaker Configuration:**

| Speaker ID | Role | Voice Character |
|------------|------|-----------------|
| Speaker 1 | Host | Warm, conversational |
| Speaker 2 | Ops | Technical, authoritative |
| Speaker 3 | Architect | Fast, excited |

**Multi-Speaker Script Format:**
```
**Speaker 1 (Host):** Imagine a world where your local hardware isn't just a server, but a living organism. We are looking at the P-MOVES dot A-I orchestration mesh.

**Speaker 2 (Ops):** It starts with the Local-First Infrastructure. We aren't renting power; we are provisioning it. Inside the directory, you find the blueprint. Automated OS installs. Jetson bootstrap scripts.

**Speaker 3 (Architect):** Correct! And this is not just storage. This is Local Inference. We utilize Tensor-Zero to host Qwen models right on the edge.

**Speaker 2 (Ops):** Plus, with "Single-User Mode" and boot-J-W-T auto-authentication, the system operates offline. No external login prompts.

**Speaker 1 (Host):** So, how does it actually think?

**Speaker 3 (Architect):** Precisely. The mesh is bifurcated. First, the Decision Engine--Agent Zero. It acts as an M-C-P bridge. Then, you have Archon, the Knowledge Manager.

**Speaker 2 (Ops):** And then the muscles do the heavy lifting. Services like Deep-Research and N-eight-N.

**Speaker 3 (Architect):** We call it the Unified Communication Mesh. Agents coordinate via NATS messaging. But the real breakthrough? Contextual Geometry Packets.

**Speaker 1 (Host):** This is the future of the fully automated industrial substrate. Welcome to PMOVES.AI.
```

---

## Punctuation Engineering Patterns

### Universal Pause Markers

| Symbol | Duration | Use Case |
|--------|----------|----------|
| `...` | ~600ms | Dramatic pause, thought transition |
| `--` | ~300ms | Sharp break, topic shift |
| `,` | ~150ms | Natural breath, list item |
| `.` | ~400ms | Sentence end, full stop |

### Acronym Pronunciation

| Written | Spoken |
|---------|--------|
| PMOVES.AI | P-MOVES dot A-I |
| MCP | M-C-P |
| NATS | NATS (as word) |
| JWT | J-W-T |
| N8N | N-eight-N |
| YT | Y-T |
| CGP | C-G-P |

### Emphasis Patterns

| Pattern | Effect | Example |
|---------|--------|---------|
| `ALL CAPS` | Strong emphasis | "This is LOCAL Inference!" |
| `word!` | Excitement | "Correct!" |
| `word?` | Questioning tone | "How does it think?" |
| `word...` | Trailing thought | "No cloud... No leaks..." |

---

## Reference Audio Requirements

### Fish Speech Cloning

| Requirement | Specification |
|-------------|---------------|
| **Duration** | 10-15 seconds optimal |
| **Quality** | Clear, minimal background noise |
| **Format** | WAV or MP3, 44.1kHz |
| **Content** | Representative of target speaking style |

### Recommended Reference Sources

1. **Tech Reviewer Style**
   - Fast-paced product reviews
   - Enthusiastic, energetic delivery
   - Example: Linus Tech Tips, MKBHD rapid segments

2. **Documentary Narrator Style**
   - Measured, authoritative tone
   - Clear enunciation
   - Example: David Attenborough, Morgan Freeman

3. **Podcast Host Style**
   - Conversational warmth
   - Natural cadence
   - Example: NPR hosts, popular podcast intros

### Reference Text Guidelines

- Match the energy and style of the reference audio
- Keep reference text 15-30 words
- Include natural speech patterns (pauses, emphases)
- Avoid complex technical terms in reference text

---

## Quick Start Checklist

### Hardware Setup
- [ ] Central Core: RTX 3090 Ti or RTX 5090 with 24GB+ VRAM
- [ ] Edge Device: Jetson Orin Nano Super (8GB)
- [ ] Install vLLM on central core
- [ ] Configure TensorRT on Jetson

### Model Deployment
- [ ] Deploy Qwen-2.5-14B or Phi-3-Medium on central core
- [ ] Deploy Phi-3-Mini (GGUF) on Jetson
- [ ] Deploy Qwen-2.5-Omni (INT4) on Jetson
- [ ] Compile YOLOv8 with TensorRT on Jetson

### Venice.ai Integration
- [ ] Obtain Venice API key
- [ ] Configure environment variables
- [ ] Test API connectivity
- [ ] Set up fallback routing for Big Threads

### TTS Setup
- [ ] Choose primary TTS engine based on use case
- [ ] Prepare reference audio for Fish Speech (if using)
- [ ] Configure style prompts for IndexTTS2 (if using)
- [ ] Set up speaker profiles for VibeVoice (if using)
- [ ] Test punctuation engineering patterns

---

## Related Documentation

- [PMOVES.AI Agentic Architecture Deep Dive](./PMOVES.AI%20Agentic%20Architecture%20Deep%20Dive.md)
- [PMOVES Engine Templates](./PMOVES_Engine_Templates.md)
- [CLAUDE.md](../../.claude/CLAUDE.md) - Developer context for PMOVES-BoTZ
