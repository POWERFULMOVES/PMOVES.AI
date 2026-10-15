# media-audio GPU runtime fix — LEARNINGS

**PR**: #3358 (Mavis, cross-lane inheritance from PR #3197's AGInT lane)
**Branch**: `fix/media-audio-gpu-runtime`
**HEAD at write**: `f9c720e9f15` (test port) ← `812168c2551` (compose fix) ← `aed68d92b8d` (first cut)
**Test contract**: `pmoves/tests/make/test_amd_overlay_reachable.py` 6/6 PASS on Windows + 6/6 PASS on ratchet
**Compose contract**: `media-audio` and `ffmpeg-whisper` both serve NVIDIA via `runtime: nvidia`. The AMD overlay (`pmoves/docker-compose.amd.yml`) currently `!reset`s **only `ffmpeg-whisper`**; `media-audio` is **not yet neutralised** on AMD nodes. The fix is a `media-audio: runtime: !reset null` block plus adding `media-audio` to `AMD_NEUTRALISED_SERVICES` in `pmoves/tests/make/test_amd_overlay_reachable.py`; it is pending a `compose:pr:3358` Known Road grant, because `docker-compose*.yml` is a protected path. No `-amd` Make target brings `media-audio` up yet either (`up-media` does not take `$(WHISPER_NODE_OVERLAY)`)

## 4-bucket × 5-class taxonomy

### 1. Defects

| # | Class | What | Where | Why it hurt |
|---|-------|------|-------|-------------|
| 1.1 | nvidia-prestart-hook | The `deploy.resources.reservations.devices` GPU request fires Docker's nvidia legacy prestart hook, which fails on Docker Desktop / WSL2 (ld.so assertion, driver rpc error) and leaves the container in `Created`. | `pmoves/docker-compose.yml` `media-audio` `deploy.resources.reservations.devices` (pre-812168c) | Live blockage: `media-audio` could not start on PMOVES-5090 2026-10-11 |
| 1.2 | xet-ca-panic | The HuggingFace `xet` downloader panics on slim images ("No CA certificates were loaded from the system"); documented fallback is `HF_HUB_DISABLE_XET=1`. | `pmoves/docker-compose.yml` `media-audio` environment | First-run model download failed TLS verify on the same incident |
| 1.3 | hand-edited-overlay | The first cut (`aed68d9`) hand-edited `docker-compose.media.yml` and placed `runtime: nvidia` / `HF_HUB_DISABLE_XET` at the **document root** (column 0). The overlay no longer parsed; every compose gate failed. | `pmoves/docker-compose.media.yml` (pre-812168c) | Silent breakage caught only by `make compose-split` drift gate and the live test |
| 1.4 | limits-dropped-with-reservation | Removing the device reservation also dropped the cpus/memory limits that lived in the same `deploy.resources` block. | `pmoves/docker-compose.yml` `media-audio` (pre-812168c) | Container ran without limits; potential OOM at high concurrency |
| 1.5 | either-spelling-ratchet-blind | The OLD test `test_base_compose_really_reserves_an_nvidia_device` only checked `deploy.resources.reservations.devices` for `ffmpeg-whisper`. After #3363 moved that service to `runtime: nvidia`, the OLD test would silently start failing on the merged tree. | `pmoves/tests/make/test_amd_overlay_reachable.py` (pre-f9c720e) | The ratchet would report 1 NEW failure on every PR that touched the same shape — silent regression. The test passed on the PR's branch alone but failed on the merged state. |
| 1.6 | non-vacuity-guard-as-fixed-check | The OLD test `test_amd_overlay_file_exists_and_resets_the_reservation` checked a fixed expectation (`devices: !reset []`). When the base moved to `runtime: nvidia`, the overlay that only reset `devices` kept passing the OLD test while doing nothing. | `pmoves/tests/make/test_amd_overlay_reachable.py` (pre-f9c720e) | The AMD overlay became a no-op on the runtime path; AMD nodes failed to schedule ffmpeg-whisper with `could not select device driver "nvidia"` |

### 2. Decisions

| # | Class | What | Why | Alternative considered | Cost of alternative |
|---|-------|------|-----|------------------------|---------------------|
| 2.1 | nvidia-runtime-vs-devices | Use service-level `runtime: nvidia` + `NVIDIA_VISIBLE_DEVICES` env, not the `deploy.resources.reservations.devices` path. | Documented in `docs.nvidia.com/datacenter/cloud-native/container-toolkit` (runtime modes, CDI) and `docs.docker.com/compose` (service `runtime` attribute). Measured working on PMOVES-5090 with driver 610.57.01. | Keep `deploy.resources.reservations.devices` and patch Docker Desktop | Patch the operator's host — not the right scope |
| 2.2 | source-monolith-not-overlay | Apply the change in `docker-compose.yml` (source monolith) and regenerate `docker-compose.media.yml` via `make -C pmoves compose-split`. | `docker-compose.media.yml` is generated; hand-edits get clobbered on next regen. | Edit the overlay directly (what aed68d9 did) | Drift gate failure + opaque YAML parse error |
| 2.3 | either-spelling-ratchet | Pin the test to the SET of NVIDIA request paths the base uses (`_nvidia_paths(service)` returns `{"devices": [...], "runtime": "nvidia"}` keys), and require the overlay to neutralise EVERY path in the set. | The base may legitimately use either spelling depending on host class (NVIDIA runtime vs devices hook). The test is the contract: whatever the base uses, the overlay must neutralise. | Keep the OLD fixed check | Silent no-op on the runtime path |
| 2.4 | test-rename-not-addition | Rename the test rather than adding a parallel one. The OLD test name was a fixed expectation; the NEW test name expresses the intent ("requests", not "reserves"). | A parallel test would diverge; a renamed test is the only test. | Add a NEW test alongside | Two tests, one true, one stale |

### 3. Operations

| # | Class | What | Measured | Repeatability |
|---|-------|------|----------|---------------|
| 3.1 | compose-split-drift-gate | `make -C pmoves compose-split` regenerates overlays from the source monolith. | `compose-split-drift-check` CI check on PR | Every compose change MUST end with the regen + a clean check |
| 3.2 | ratchet-baseline-discipline | `pmoves/tools/pytest_ratchet.py` compares a run to `pmoves/configs/pytest_ratchet/_known_failures.yaml`. A test rename needs no baseline update IF both old and new names pass; the ratchet only flags NEW FAILURES, not NEW PASSES. | Verified: `test_base_compose_really_reserves_an_nvidia_device` (old) was NOT in baseline, and `test_base_compose_really_requests_an_nvidia_gpu` (new) will NOT need to be added | Whenever a test name changes meaning, re-read the ratchet rule |
| 3.3 | windows-yaml-encoding | `pmoves/tests/hardening/test_docker_hardening.py` opens compose files with `open(path, "r")` — the default platform encoding (cp1252 on Windows). Compose files contain UTF-8 multi-byte sequences (`⚠` U+26A0 in headers) that cp1252 cannot decode. | 32/34 `media-*` hardening tests ERROR on Windows with `UnicodeDecodeError`. Pre-existing; NOT introduced by #3358. | Add `encoding="utf-8"` to every `open()` call in the test, or pre-decode the file | Drift across the repo's test suite on Windows hosts |
| 3.4 | crlf-normalisation-on-write | `Add-Content` on PowerShell writes a trailing CRLF. `write` via the harness uses LF. Both end up in git, but git's `.gitattributes` (`*.py text eol=lf`) normalises on `git add`. | The AGNOTE and test file changes both required `Add-Content` → strip CR → `git add` cycles to avoid the CRLF warning. | Write a helper that opens in `LF` mode explicitly | `git diff` noise + future "CRLF will be replaced" warnings on every checkout |

### 4. Cross-references

| # | Class | What | Link | Why it matters |
|---|-------|------|------|----------------|
| 4.1 | either-spelling-shared-with-ffmpeg-whisper | The same fix (runtime: nvidia + env, no devices reservation) was applied to `ffmpeg-whisper` in commit `ee1573f55b1` (#3363) — BEFORE the #3358 cut for `media-audio`. | git log `pmoves/docker-compose.yml` | One pattern, two services; any future GPU service should follow it. The AMD overlay MUST neutralise BOTH paths. |
| 4.2 | amd-overlay-is-the-pattern | `docker-compose.amd.yml` is the documented escape hatch for non-NVIDIA nodes. The pattern is `!reset` to neutralise a base request; the test enforces it. | `pmoves/docker-compose.amd.yml` + `pmoves/tests/make/test_amd_overlay_reachable.py::test_amd_overlay_file_exists_and_neutralises_every_gpu_path_the_base_uses` | Every new NVIDIA-touching service needs an AMD overlay plan BEFORE it merges |
| 4.3 | driver-version-pin | The runtime: nvidia path requires the nvidia container toolkit on the host. The compose validation gate checks this. | `pmoves/tools/check_compose_gate.py` (CI step "validate-compose-files") | If a node's driver is below 525.x, neither devices nor runtime path will work — the gate is the canary |
| 4.4 | lane-AGInT-cross-link | This PR inherited the AGInT lane's `mavis/...` branch convention (the lane summary from 2026-10-12 noted "I have write access to the branch (it's the AGInT lane I previously touched)"). The 5090 host is the agent's primary working dir, so the worktree `C:\Users\russe\pmoves-wt-mediafix` is the right place to land the fix. | operator directive 2026-10-10 "are you offering prose or provenance?" + the inheriting workflow | Lane-inheritance pattern: open a fix branch off the original PR's branch, ship the fix + ratchets, leave a comment attributing the work to mavis. |

## Ratchet pin (the thing that catches the next person)

The new test `_nvidia_paths(service) -> dict[str, object]` returns the SET of NVIDIA request paths the base uses for a service. The non-vacuity guard is:

```python
assert _nvidia_paths(base), (
    "docker-compose.yml no longer requests an NVIDIA GPU for ffmpeg-whisper "
    "(neither `runtime: nvidia` nor an nvidia devices reservation)"
)
```

The overlay test is:

```python
unhandled = []
if "devices" in base_paths and not (_is_reset(devices) and devices.get("value") == []):
    unhandled.append("devices reservation ...")
if "runtime" in base_paths and not (_is_reset(runtime) or (isinstance(runtime, str) and runtime != "nvidia")):
    unhandled.append("runtime ...")
assert not unhandled
```

A future regression where:
- The base drops BOTH NVIDIA paths (no devices, no runtime: nvidia) — caught by `test_base_compose_really_requests_an_nvidia_gpu`
- The base uses runtime: nvidia but the overlay only resets devices — caught by `test_amd_overlay_file_exists_and_neutralises_every_gpu_path_the_base_uses`

Both ratchets land in the same file; the ratchet in `pmoves/tools/pytest_ratchet.py` reports the new test names on the next PR that touches the same shape, and the merged tree will not regress.

## Provenance (DARKXSIDE 2026-09-16: no workarounds; SDK + doc provenance required)

- **SDK file:line** — `pmoves/docker-compose.yml:2648-2680` (media-audio, the runtime: nvidia + HF_HUB_DISABLE_XET + deploy.resources.limits); `pmoves/tests/make/test_amd_overlay_reachable.py:161-183` (`_nvidia_paths` + `_is_reset` helpers).
- **Test contract** — 6/6 PASS on Windows host (this worktree, post-f9c720e); the ratchet will catch any future regression to the OLD test name.
- **AGNOTE** — RELEASE row at `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md:3399` (next to the existing rows).
- **PR + branch** — #3358 on `fix/media-audio-gpu-runtime` (this agent, mvs_5d5493b128b640e9aff8d45adcc77a66).
- **Docs cited** — `docs.nvidia.com/datacenter/cloud-native/container-toolkit` (runtime modes, CDI); `docs.docker.com/compose/compose-file` (service `runtime` attribute).
- **Incident** — PMOVES-5090 2026-10-11: `media-audio` stuck in `Created`; live nvidia-smi worked; driver 610.57.01.
