# Hi-RAG Gateway pmoves.tools Namespace Dockerfile Packaging — LEARNINGS

**Date:** 2026-10-17
**Author:** mavis (claude M3, worktree `pmoves-wt-hirag-cgp`)
**Branch:** `fix/hi-rag-cgp-geometry-event-handler`
**Follow-up to:** PR #3382, commit `e38c3a1` (`fix(hirag): Dockerfile.gpu packages the pmoves.chit namespace`)

## TL;DR

PR #3382 closed the `pmoves.chit` namespace gap in `Dockerfile.gpu` but missed
a *second* namespace gap: `pmoves.tools`. Both the CPU `Dockerfile` AND the GPU
`Dockerfile.gpu` were missing the `pmoves.tools` packaging, so
`/geometry/event` kept returning 500 with `ModuleNotFoundError: No module
named 'pmoves.tools'`. The 2026-10-17 verification (rebuild + `POST /yt/emit`)
exposed this. The follow-up commit extends BOTH Dockerfiles with the
`pmoves.tools` namespace and updates the static ratchet to pin both
namespaces.

## What PR #3382 actually fixed

- The GPU image's `Dockerfile.gpu` now creates `/app/pmoves/__init__.py` and
  copies `chit/` into `/app/pmoves/chit/`. Verified: `ShapeStore initialized
  (v2)` in the rebuilt container logs (no more `ModuleNotFoundError:
  No module named 'pmoves'`).

## What PR #3382 missed

`tools/chit_security.py` is one of the modules the geometry/event path
imports (specifically: `from tools.chit_security import verify_cgp,
decrypt_anchors`). At module load, `chit_security.py:25` executes:

```python
from pmoves.tools.chit_common import canon as _canon  # noqa: F401 - re-export for backward compat
```

That import fails because neither Dockerfile copies `tools/chit_common.py`
into `/app/pmoves/tools/`. Result: every `POST /geometry/event` returns
500 → `pmoves-yt /yt/emit` degrades to `cgp_ok: false`.

The same `pmoves.tools` import shows up in:
- `services/common/geometry_decoder.py:75-76`
- `services/common/branch_trail.py:146-147`
- `services/common/model_fitness.py:22`

So the bug is not a one-off — `pmoves.tools` is a structural dependency of
the geometry/event path, and it was silently broken across both Dockerfiles.

## Why the CPU `Dockerfile` did not surface the bug earlier

The CPU container (`pmoves-hi-rag-gateway-v2-1`) has been up for 3+ days
and *also* logs `ERROR:hirag.gateway.v2:security module import failed`. But
the CPU service is primarily a re-ranker (`HIRAG_V1_HOST_PORT=8089`,
`USE_CUDA=false`), not the geometry bus. The geometry/event HTTP endpoint
on the CPU container is exercised only by `pmoves-yt /yt/emit`, which goes
to the GPU sibling by default (`HIRAG_URL=http://hi-rag-gateway-v2-gpu:8086`).
So the CPU container's bug was invisible until the GPU container started
returning 500s on /geometry/event.

## Why the integration test did not catch this

`pmoves/tests/test_yt_emit_cgp_ok.py` is a runtime test that calls
`POST /yt/emit` on a fresh video and asserts `cgp_ok: true`. It SKIPs on
this host because:
- `0p_1QSUsbsM` (the probe video) is already in the yt-dlp download archive
- The archive has 183 youtube entries; finding a non-archived stable video
  is hit-or-miss

When the test *does* run, it would have failed with the exact symptom we
saw in the runtime logs. The fix is to make the static ratchet (which DOES
run in CI) catch this — which the follow-up commit does.

## What the follow-up commit changes

### `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu`

Replaces the single-namespace block (4 lines) with a two-namespace block
(13 lines). Adds:

```dockerfile
RUN mkdir -p /app/pmoves \
    && printf '"""Minimal pmoves namespace for Docker."""\n' > /app/pmoves/__init__.py \
    && mkdir -p /app/pmoves/tools \
    && printf '"""pmoves.tools namespace for Docker."""\n' > /app/pmoves/tools/__init__.py
COPY chit /app/pmoves/chit
COPY tools/__init__.py /app/pmoves/tools/__init__.py
COPY tools/chit_common.py /app/pmoves/tools/chit_common.py
COPY tools/chit_security.py /app/pmoves/tools/chit_security.py
COPY tools/sign_trail.py /app/pmoves/tools/sign_trail.py
```

The GPU Dockerfile's existing `tools/chit_security.py` COPY to
`/app/tools/chit_security.py` is preserved (no harm in having both
`pmoves.tools.chit_security` and `tools.chit_security` available).

### `pmoves/services/hi-rag-gateway-v2/Dockerfile`

Mirrors the same block. The CPU Dockerfile had `tools/chit_security.py`
COPY at `/app/tools/chit_security.py` since 30efedfb77f but never had
the `pmoves.tools` namespace packaging. Same fix.

### `pmoves/tests/test_dockerfile_packages_pmoves_chit.py`

Adds `test_dockerfile_packages_pmoves_tools` parameterized over every
`Dockerfile*` in the service directory. Asserts:
1. `mkdir -p /app/pmoves/tools` + `/app/pmoves/tools/__init__.py`
2. COPY of `tools/chit_common.py`, `tools/chit_security.py`,
   `tools/sign_trail.py` into `/app/pmoves/tools/`

Also extends `test_pmoves_chit_in_cpu_dockerfile_unchanged` to also pin
`/app/pmoves/tools` in the CPU sibling.

Test result on this host: `5 passed in 0.19s` (3 new tests).

## 4-bucket + 5-class taxonomy

### Bucket: SDK provenance
- **class: code/SDK** — Dockerfile.gpu:52-69, Dockerfile:18-30,
  test_dockerfile_packages_pmoves_chit.py:84-127
- **class: doc** — this LEARNINGS file + AGNOTE4482PHI.t1.md:3400
- **class: agent memory** — none yet (this finding is project-specific)

### Bucket: operational
- **class: lane/PR** — supersedes the incomplete PR #3382 fix; the
  follow-up commit lands on the same branch (`fix/hi-rag-cgp-geometry-
  event-handler`) and PR #3382 will be amended/extended rather than
  closed and re-opened.
- **class: env/ops** — none (no env var changes)

### Bucket: provenance chain
- **class: trace/ID** — `4adad305ca6` (previous HEAD) → this commit on
  `fix/hi-rag-cgp-geometry-event-handler`
- **class: SDK+test contract** — `5 passed in 0.19s` ratchet result;
  full E2E verification (`cgp_ok: true`) is the integration test
  `test_yt_emit_cgp_ok.py` once the integration test can run (probe
  video in archive blocks it on this host)

### Bucket: decision narrative
- **class: SDK+doc vs workaround** — chose to extend both Dockerfiles
  (NOT to remove the `pmoves.tools` re-export from chit_security.py)
  because the `pmoves.tools` namespace is referenced from multiple
  files (4 files; see "What PR #3382 missed" above), and removing the
  re-export would be a behavior change rather than a packaging fix.
- **class: scope discipline** — limited the ratchet to the three
  modules actually needed (`chit_common.py`, `chit_security.py`,
  `sign_trail.py`). Did NOT broaden it to "COPY tools/*.py" because the
  intent is to flag namespace drift, not to mirror the entire tools/
  directory (which has 200+ files, most of which are not runtime deps).

## Follow-up recommendations (for the operator's review)

1. **Audit `pmoves.services.common.*` namespace usage.** Several files
   do `from pmoves.services.common.{env,geometry_models,geometry_decoder,
   nats_client} import ...` (see branch_trail.py:34, chit_lanes.py:42-45,
   geometry_decoder.py:65-75). The CPU Dockerfile copies
   `services/common` to `/app/services/common/` so the non-namespaced
   paths work, but the `pmoves.services.common.*` paths would fail if
   triggered. This is a separate audit; the immediate cgp_ok blocker
   does NOT depend on it.

2. **Make the ratchet self-updating.** The current ratchet requires
   editing the test whenever a new `pmoves.*` namespace is added.
   A more durable approach is a `grep`-based "every `from pmoves.X`
   import in `services/hi-rag-gateway-v2/` must have an X namespace
   packaged" test. Filed as a separate lane.

3. **Move the probe video out of the archive.** The integration test
   `test_yt_emit_cgp_ok.py` SKIPs on this host because `0p_1QSUsbsM`
   is in the download archive. Operator decision: either delete the
   archive entry (`yt_archive_purge.py`) or pick a different probe.
   Filed as a separate lane.

4. **Container restart recipe (env vars).** This runbook pulled env
   vars from the running container via `docker inspect --format '{{range
   .Config.Env}}{{println .}}{{end}}'` and passed them via `--env-file`.
   The compose file's `env_file: pmoves/env.shared` directive fails
   in worktrees that don't carry the gitignored `env.shared`. The
   `--env-file` workaround is documented inline here as the canonical
   bring-up path. Not in scope for the follow-up commit.