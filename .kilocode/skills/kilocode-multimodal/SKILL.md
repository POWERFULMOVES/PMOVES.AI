---
name: kilocode-multimodal
description: Verify tool execution using text, audio, and VLM checks across PMOVES services on the KiloCode GLM lane. Use when validating multimodal outputs, capturing verification evidence, or binding verification to task/run IDs.
keywords: [multimodal, verify, VLM, audio, video, evidence, validation, kilocode, glm]
version: 1.0.0
category: PMOVES/KiloCode
---

# KiloCode Multimodal Verifier

Verify tool execution using text + audio + VLM checks with evidence capture bound to task/run IDs via KiloCode GLM.

## Purpose

Execute multimodal verification of PMOVES service outputs using text analysis, audio processing, and Vision Language Model (VLM) checks. Capture verification evidence for audit and bind results to task/run identifiers. Route complex verification through TensorZero `coding_glm` / `coding_kilocode`.

## Capabilities

- 👁️ VLM-based visual verification (screenshots, video frames)
- 🔊 Audio verification for TTS/transcription outputs
- 📝 Text/log analysis for structured validation
- 📊 Metrics verification against baselines
- 🔗 Evidence binding to task/run IDs
- 🤖 Fast verification via GLM-5-Turbo

## Integration Points

- **VLM**: GLM-5V-Turbo for image/video analysis via Z.AI
- **Audio**: PMOVES-TensorZero transcription pipeline
- **Jellyfin**: Video frame extraction for verification
- **Logs**: `docker compose logs -f <service>`
- **Metrics**: Prometheus endpoint `:9090`
- **TensorZero Functions**: `coding_glm`, `coding_kilocode`
- **NATS Subject**: `pmoves.verify.multimodal.v1`

## Workflow

### 1. Collect Evidence

```bash
# Screenshot capture
grim -o <output> /tmp/verify_screen.png

# Video frame extraction
ffmpeg -i <video> -vf "select=eq(n\,30)" -vsync 0 /tmp/frame.png

# Service logs
docker compose logs --tail=100 <service> > /tmp/logs.txt
```

### 2. Run Verification Checks

```bash
# Text verification
./scripts/verify-text.py --input /tmp/logs.txt --pattern "<expected>"

# VLM verification via GLM-5V-Turbo
./scripts/verify-vlm.py --image /tmp/verify_screen.png --prompt "<visual check>"

# Audio verification
./scripts/verify-audio.py --file /tmp/output.wav --expected-duration <seconds>
```

### 3. Bind Evidence to Task ID

```bash
# Create verification report
./scripts/bind-evidence.py \
  --run-id <task-id> \
  --evidence-dir /tmp/verify_<timestamp>/ \
  --report /tmp/verification_report.json
```

## Verification Matrix

| Modality | Check | Tool | Pass Criteria |
|----------|-------|------|--------------|
| Text | Log pattern | grep/regex | Match found |
| Visual | UI state | GLM-5V-Turbo | Confidence > 0.8 |
| Audio | Duration | ffmpeg | Within ±5% |
| Metrics | Latency | Prometheus | p99 < threshold |

## Example Usage

```
User: "Verify Jellyfin playback start for task abc-123"

Agent:
1. Extracts frame at t=0 from Jellyfin stream
2. Runs VLM check via GLM-5V-Turbo for player UI visibility
3. Verifies logs show stream URL minted
4. Binds evidence to task abc-123
5. Generates verification_report.json
```

## Trigger Phrases

- "verify multimodal output"
- "run VLM verification"
- "bind evidence to task"
- "verify service output"
- "multimodal smoke test"
- "kilocode multimodal verify"
