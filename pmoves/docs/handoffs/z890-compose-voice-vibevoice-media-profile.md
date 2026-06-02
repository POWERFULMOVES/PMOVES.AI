# Handoff: Add VibeVoice to `media` profile + Remove GPU-only Device Constraint

**For:** Z890-CLAUDE (or SPARK / 5090-CLAUDE)  
**Requires:** `COMPOSE_EDIT=1` (damage-control hook bypass — approved by operator under Known Roads)  
**Branch:** new branch off `main`, e.g. `fix/vibevoice-media-profile`  
**File:** `pmoves/docker-compose.voice.yml`

---

## Context

VibeVoice-Realtime is the CPU fallback TTS backend for nodes without an NVIDIA GPU.
It currently runs only under `profiles: ["voice"]` and has a hard `driver: nvidia` device
reservation that prevents it from starting on CPU-only nodes.

The `VIBEVOICE_DEVICE=auto` env var already handles CPU/GPU selection at runtime —
PyTorch falls back to CPU when no CUDA device is present. The nvidia device reservation
is therefore unnecessary and should be removed.

Additionally, VibeVoice must be included in the `media` profile so that
`make overlay-up-media` (used on GPU nodes) also starts the CPU fallback, and
`make up-voice` (which uses `--profile media --profile voice`) picks it up.

---

## Exact Change

**File:** `pmoves/docker-compose.voice.yml`

Change line 28:
```yaml
    profiles: ["voice"]
```
to:
```yaml
    profiles: ["voice", "media"]
```

Remove lines 29–35 (the entire `deploy:` block):
```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [compute,utility]
              count: ${GPU_COUNT:-all}
```

**Result after change** (lines 26–36 should look like):
```yaml
    ports:
      - "${VIBEVOICE_HOST_PORT:-3000}:3000"
    profiles: ["voice", "media"]
    networks: [api_tier]
```

---

## How to Execute

```bash
# In the z890 worktree for PMOVES.AI:
COMPOSE_EDIT=1 <editor> pmoves/docker-compose.voice.yml
# Apply the two changes above

git add pmoves/docker-compose.voice.yml
git commit -m "fix(voice): add VibeVoice to media profile + remove nvidia device constraint

CPU fallback works via VIBEVOICE_DEVICE=auto; GPU device block is
unnecessary and prevents service from starting on CPU-only nodes.
Adds 'media' profile so overlay-up-media starts VibeVoice alongside GPU stack.
"
git push origin fix/vibevoice-media-profile
# Open PR targeting main
```

---

## Verification

```bash
# On a CPU node (no GPU):
docker compose -f docker-compose.base.yml -f docker-compose.voice.yml \
  --profile media up -d vibevoice
docker logs pmoves-vibevoice --tail 20
# Expected: "VibeVoice API started on 0.0.0.0:3000"

# Health check:
curl http://localhost:3000/health
```

---

## Related

- `pmoves/Makefile` targets: `voice-health`, `up-voice` (already call `--profile media --profile voice`)
- Session 7 plan Lane 0-A: TTS auto-start
- Issue: damage-control hook blocks this on 4090-claude — approved for Z890/SPARK/5090 under Known Roads
