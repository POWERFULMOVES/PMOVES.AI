# ffmpeg-whisper: the CUDA preinstall is gated on aarch64, so x86_64 cannot build

**Node:** Z890 (`x86_64`) · **Author:** Z890-CLAUDE · **Date:** 2026-09-20
**Service:** `pmoves/services/ffmpeg-whisper` · **Target:** `pmoves/services/ffmpeg-whisper/Dockerfile`

## Symptom

`make -C pmoves up-ffmpeg-whisper` fails on Z890 at the Python install layer:

```
error: Failed to download `torchaudio==2.9.1+cu128`
  cause: Hash mismatch for `torchaudio==2.9.1+cu128`
```

The container is never created, so `ffmpeg-whisper` is unresolvable on the compose
network. Every `/yt/transcript` and `/yt/ingest` call on `pmoves-yt` (:8077) then
returns 502:

```
ffmpeg-whisper unreachable: Failed to resolve 'ffmpeg-whisper'
```

Measured 2026-09-20: nine YouTube ingests, nine 502s.

## Why it works on SPARK and not here

It is an **architecture gate**, not a broken lock. The Dockerfile's Python layer is:

```dockerfile
RUN pip install --no-cache-dir uv && \
    if [ "$(uname -m)" = "aarch64" ]; then \
      uv pip install --system --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cu128 torch==2.9.1 torchaudio==2.9.1; \
    fi && \
    uv pip install --system --no-cache-dir --index-strategy unsafe-best-match \
      --extra-index-url https://download.pytorch.org/whl/cu128 -r requirements.txt
```

`requirements.lock` pins `torchaudio==2.9.1` with **plain-PyPI hashes** (line 3112).
The second command passes `--extra-index-url .../cu128` **unconditionally**, on every
architecture.

- **SPARK is `aarch64`.** The guarded preinstall runs first and satisfies
  `torchaudio` from the cu128 index. A PEP 440 local version (`2.9.1+cu128`)
  satisfies the `==2.9.1` pin, so the locked install never re-downloads it and
  never hash-checks it. The Dockerfile comment says exactly this. Build succeeds.
- **Z890 is `x86_64`.** The preinstall is skipped — but the cu128 extra index is
  still offered. uv resolves `torchaudio` to the cu128 wheel, then verifies it
  against the lock's PyPI hashes. They cannot match. Build fails.

So the working path was written for, and only ever exercised on, one architecture.
The arch condition guards the *fix* while the thing the fix compensates for
(`--extra-index-url`) is ungated.

## Reference implementations already in this repo

Both agree with each other, and neither gates on architecture — they select an
index by **GPU vendor**, install the torch trio **explicitly and first**, then
install everything else:

| Source | Pattern |
|---|---|
| `pmoves/docs/ARTSTUFF/realtime/torch.js` (Pinokio) | `uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128` per `platform`×`gpu` branch — **`--index-url`, single index**, never `--extra-index-url` |
| `pmoves/creator/installers/*-AUTO_INSTALL-RUNPOD.sh` | `TORCH_INDEX="https://download.pytorch.org/whl/${CUDA_TAG}"`, explicit `TORCH_VERSION`/`TORCHVISION_VERSION`/`TORCHAUDIO_VERSION` pins installed ahead of the rest |

The lesson both encode: **when torch comes from the CUDA index, it must be
installed from that index alone and before the locked resolve** — not blended into
a hash-checked resolve via a second index.

## Fix

Run the existing preinstall on every CUDA build rather than only `aarch64`, so
x86_64 takes the same proven road SPARK already takes. Minimal change, no new
mechanism, no lock regeneration, and it matches both reference scripts.

The alternative — dropping `--extra-index-url` on x86_64 so the PyPI lock hashes
are authoritative — also builds, but silently changes which CUDA wheels an x86_64
node gets. Rejected as the larger behavioural change.

## Verification

- [ ] `make -C pmoves up-ffmpeg-whisper` completes on Z890 (`x86_64`)
- [ ] container healthy, `:8078/healthz` 200
- [ ] `getent hosts ffmpeg-whisper` resolves from `pmoves-pmoves-yt-1`
- [ ] one `/yt/transcript` returns text rather than 502
- [ ] SPARK (`aarch64`) still builds — the branch it relies on is unchanged

## Related findings (not fixed here)

- **`/yt/transcript` has no caption fallback.** YouTube already serves captions;
  `yt-dlp --write-auto-sub --skip-download` retrieved all nine transcripts on this
  node with **no GPU and no whisper**. Routing straight to whisper makes a 35 MB
  problem out of a zero-byte one. Worth a follow-up: try captions, fall back to
  whisper.
- **Skill doc drift** (`.claude/skills/pmoves-yt/SKILL.md`): `/yt/transcript`
  takes `video_id`, not `url` as documented; and "egress is clean and there is no
  bot-gate on this node" is stale — Z890 egresses through the `pmoves-kvm4-2`
  exit node, presenting a Hostinger datacenter IP, which YouTube gates.
- **DHI:** this service builds `FROM nvidia/cuda:12.6.2-cudnn-runtime-ubuntu22.04`
  directly. `pmoves/docs/operations/DHI_MIGRATION_MANIFEST.md` is the hardened-base
  track; base migration is out of scope for this fix and should be its own change.
  Note also the base is CUDA **12.6** while the wheels are **cu128** (12.8).
