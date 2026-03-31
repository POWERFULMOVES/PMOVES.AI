---
name: minimax-multimodal
description: Verify tool execution using text, audio, and VLM checks across PMOVES services. This skill should be used when validating multimodal outputs, capturing verification evidence, or binding verification to task/run IDs.
keywords: [multimodal, verify, VLM, audio, video, evidence, validation]
version: 1.0.0
category: PMOVES/MiniMax
---

# MiniMax Multimodal Verifier

Verify tool execution using text + audio + VLM checks with evidence capture bound to task/run IDs.

## Purpose

Execute multimodal verification of PMOVES service outputs using text analysis, audio processing, and Vision Language Model (VLM) checks. Capture verification evidence for audit and bind results to task/run identifiers.

## Capabilities

- 👁️ VLM-based visual verification (screenshots, video frames)
- 🔊 Audio verification for TTS/transcription outputs
- 📝 Text/log analysis for structured validation
- 📊 Metrics verification against baselines
- 🔗 Evidence binding to task/run IDs
- ⚡ Fast verification via MiniMax inference

## Integration Points

- **VLM**: MiniMax VL models for image/video analysis
- **Audio**: PMOVES-TensorZero transcription pipeline
- **Jellyfin**: Video frame extraction for verification
- **Logs**: `docker compose logs -f <service>`
- **Metrics**: Prometheus endpoint `:9090`
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

# VLM verification
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
| Visual | UI state | VLM prompt | Confidence > 0.8 |
| Audio | Duration | ffmpeg | Within ±5% |
| Metrics | Latency | Prometheus | p99 < threshold |

## Example Usage

```
User: "Verify Jellyfin playback start for task abc-123"

Agent:
1. Extracts frame at t=0 from Jellyfin stream
2. Runs VLM check for player UI visibility
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
