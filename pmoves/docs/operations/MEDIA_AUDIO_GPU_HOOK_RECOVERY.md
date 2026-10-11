# Known Road — media-audio GPU prestart hook failure

**Symptom:** `pmoves-media-audio-1` stuck in `Created`; `docker start` fails with
`Inconsistency detected by ld.so ... _dl_setup_hash: Assertion ... failed!` +
`nvidia-container-cli: initialization error: driver rpc error: failed to process
request`. Retries fail identically. Other containers keep running.

**Cause:** WSL/Docker Desktop nvidia runtime hook in a bad state (driver IPC
corruption). NOT a compose bug, NOT image drift. `docker info` still lists the
nvidia runtime — the failure is at container-create time when the hook runs.

**Do NOT:** restart Docker Desktop / WSL as first move — that bounces every
ccontainer on the node, including live A0 sidecars and engines.

**Surgical recovery (this node, CPU mode):**

```bash
make -C pmoves media-audio-cpu-rescue
```

(runc twin via `pmoves/scripts/media_audio_cpu_rescue.sh` — compose override alone
 does NOT strip the GPU: compose list-merge appends devices, so the hook still fires.)

`docker-compose.media-cpu.override.yml` strips the GPU reservation
(`devices: []`, `NVIDIA_VISIBLE_DEVICES=""`). Diarization runs CPU-slow but UP.
Committed in-tree so the road is repeatable.

**Verify:**

```bash
docker ps --format '{{.Names}} {{.Status}}' | grep media-audio   # Up
docker exec pmoves-media-audio-1 printenv HF_TOKEN | head -c 8   # funnel token
```

**Full GPU restore (operator, schedule a bounce window):**

1. Restart Docker Desktop (or `wsl --shutdown` + restart). Every container on
   the node bounces — announce first.
2. Smoke: `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`
3. Remove the override and recreate:

```bash
make -C pmoves media-audio-gpu-restore
```

**HF token note:** the recreate inherits `HF_TOKEN` from env.shared via the
secrets funnel. If the container held a stale token (audit 2026-10-11: media
held `hf_pN…` while env.shared carries the valid `hf_fp…`), the recreate IS
the fix — pyannote whoami 401s clear without any manual rotation.

*Road documented 2026-10-11 after live recovery on the Windows/5090 host.*
