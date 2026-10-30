# Hi-RAG Gateway pmoves.tools Namespace Dockerfile Packaging — LEARNINGS

**Date:** 2026-10-17
**Author:** mavis (claude M3, worktree `pmoves-wt-hirag-cgp`)
**Branch:** `fix/hi-rag-cgp-geometry-event-handler`
**Follow-up to:** PR #3382, commit `a7bfdd3e410` (`fix(hirag): Dockerfile.gpu packages the pmoves.chit namespace`) — the PR-head sha for the same change was `e38c3a1`; the branch was rebuilt onto `origin/main` after review, so the sha moved with it (match the commit by subject, because a further rebase rewrites the sha).

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
decrypt_anchors`). At module load, the `from pmoves.tools.chit_common
import canon` re-export (currently `chit_security.py:25`) executes:

```python
from pmoves.tools.chit_common import canon as _canon  # noqa: F401 - re-export for backward compat
```

That import fails because neither Dockerfile copies `tools/chit_common.py`
into `/app/pmoves/tools/`. Result: every `POST /geometry/event` returns
500 → `pmoves-yt /yt/emit` degrades to `cgp_ok: false`.

The same `pmoves.tools` import shows up in:
- `services/common/geometry_decoder.py` — `from pmoves.tools.chit_common` /
  `from pmoves.tools.chit_security` (currently `:75-76`)
- `services/common/branch_trail.py` — `from pmoves.tools.sign_trail` /
  `from pmoves.tools.chit_security` (currently `:146-147`)
- `services/common/model_fitness.py` — `from pmoves.tools.chit_security`
  (currently `:22`)

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
`POST /yt/emit` on a fresh video and asserts `cgp_ok: true`. As of this
follow-up (2026-10-17) it SKIPs on this host because:
- `0p_1QSUsbsM` (the probe video) is already in the yt-dlp download archive
- The archive has 183 youtube entries; finding a non-archived stable video
  is hit-or-miss

> **Updated 2026-10-30 (review-fix round).** The archive pre-check itself was
> the defect: it POSTed to `/yt/download` to test "is this video archived?",
> which *downloads* the video when it is not. The skip decision is now taken
> from the **emit response** (`_emit_declined_for_archived_video`), so the
> test no longer mutates the archive it is measuring. On the operator's host
> the probe video was already archived, so the test **RUNS and PASSES** now —
> see `hirag_cgp_geometry_event_dockerfile_packaging_LEARNINGS.md`.

When the test *did* run, it would have failed with the exact symptom we
saw in the runtime logs. The fix is to make the static ratchet (which DOES
run in CI) catch this — which the follow-up commit does.

## What the follow-up commit changes

### `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu`

Replaces the single-namespace block (3 physical lines: 1 `RUN` + 1 `COPY`)
with a two-namespace block (9 physical lines: 1 `RUN` + 5 `COPY`). Adds:

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

Mirrors the same block. The CPU Dockerfile had the `tools/chit_security.py`
COPY to `/app/tools/chit_security.py` since `b51366e432a` (2025-10-11) — it
predates the `pmoves.chit` namespace commit `30efedfb77f` — but never had the
`pmoves.tools` namespace packaging. Same fix.

### `pmoves/tests/test_dockerfile_packages_pmoves_chit.py`

Adds `test_dockerfile_packages_pmoves_tools` parameterized over every
`Dockerfile*` in the service directory. Asserts:
1. `mkdir -p /app/pmoves/tools` + `/app/pmoves/tools/__init__.py`
2. COPY of `tools/chit_common.py`, `tools/chit_security.py`,
   `tools/sign_trail.py` into `/app/pmoves/tools/`

The CPU tools namespace is covered by the parametrized
`test_dockerfile_packages_pmoves_tools`, whose `Dockerfile*` glob already
includes the CPU `Dockerfile` — so no separate CPU assert is needed. (An
earlier draft of this follow-up added a dedicated `"/app/pmoves/tools" in source`
assert to `test_pmoves_chit_in_cpu_dockerfile_unchanged`; it was **removed**
in the 2026-10-30 review-fix round as redundant with — and strictly weaker
than — the parametrized test, since a bare substring match also hits a comment.
The test file now carries an explicit NOTE that the CPU tools namespace is NOT
asserted there, so the next reader does not re-add the weaker check.)

Test result on this host: `5 passed` (3 → 5 test items: the
parametrized `pmoves.tools` test adds 2, one per Dockerfile in the glob).

## 4-bucket + 5-class taxonomy

### Bucket: SDK provenance
- **class: code/SDK** — `pmoves/services/hi-rag-gateway-v2/Dockerfile.gpu`, the
  `pmoves` namespace block (anchor: the `COPY chit /app/pmoves/chit` line,
  currently `:74`; whole block `:70-78`) and `pmoves/services/hi-rag-gateway-v2/Dockerfile`,
  the same anchor (currently `:28`; whole block `:24-32`); plus
  `pmoves/tests/test_dockerfile_packages_pmoves_chit.py` →
  `test_dockerfile_packages_pmoves_tools` (currently `:90-157`). *Anchored on the
  `COPY` line and the test function name rather than bare ranges, because the
  `pmoves.tools` follow-up commit widened all three regions and moved every
  line number inside them.*
- **class: doc** — this LEARNINGS file + the AGNOTE4482PHI.t1.md UPDATE row
  timestamped `2026-10-17T23:35:00Z` (currently `:3535`; the sibling RELEASE
  row is `:3533` and the 2026-10-30 review-fix row `:3536` — the three hirag
  rows sit at the tail of the register). *Anchored on the row's
  TIMESTAMP because the register is append-only — later rows push it down.*
- **class: agent memory** — none yet (this finding is project-specific)

### Bucket: operational
- **class: lane/PR** — supersedes the incomplete PR #3382 fix; the
  follow-up commit lands on the same branch (`fix/hi-rag-cgp-geometry-
  event-handler`) and PR #3382 will be amended/extended rather than
  closed and re-opened.
- **class: env/ops** — none (no env var changes)

### Bucket: provenance chain
- **class: trace/ID** — the follow-up commit `e76036c95aa`
  (`fix(hirag): Dockerfile packages pmoves.tools namespace too`) on
  `fix/hi-rag-cgp-geometry-event-handler`, following the chit-namespace fix
  `a7bfdd3e410` (`fix(hirag): Dockerfile.gpu packages the pmoves.chit
  namespace`) and its docs commit `ca9689c74a4` (`docs(hirag): RELEASE row +
  LEARNINGS …`). *These are the current shas; the branch was rebuilt onto
  `origin/main` after the review, so match the commits by subject, not by
  sha.*
- **class: SDK+test contract** — `5 passed` ratchet result
  (`pmoves/tests/test_dockerfile_packages_pmoves_chit.py`); full E2E
  verification (`cgp_ok: true`) is the integration test
  `test_yt_emit_cgp_ok.py`, which RUNS and PASSES on the operator's host
  since the 2026-10-30 review-fix round

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
   nats_client} import ...` (see `branch_trail.py` `from pmoves.services.common.env
   import get_secret`, currently `:34`; `chit_lanes.py` `from pmoves.services.common.
   {geometry_models,geometry_decoder} import ...`, currently `:42-45`; and
   `geometry_decoder.py` `from pmoves.services.common.geometry_models import (...)`,
   currently `:65-74`). The CPU Dockerfile copies
   `services/common` to `/app/services/common/` so the non-namespaced
   paths work, but the `pmoves.services.common.*` paths would fail if
   triggered. This is a separate audit; the immediate cgp_ok blocker
   does NOT depend on it.

2. **Make the ratchet self-updating.** The current ratchet requires
   editing the test whenever a new `pmoves.*` namespace is added.
   A more durable approach is a `grep`-based "every `from pmoves.X`
   import in `services/hi-rag-gateway-v2/` must have an X namespace
   packaged" test. Filed as a separate lane.

3. **Move the probe video out of the archive.** *(superseded 2026-10-30 —
   resolved.)* The integration test `test_yt_emit_cgp_ok.py` SKIPped on this
   host because `0p_1QSUsbsM` was in the download archive; operator decision
   was to either delete the archive entry (`pmoves/tools/yt_archive_purge.py`)
   or pick a different probe. The 2026-10-30 review-fix round took the third
   option and removed the mutating archive pre-check entirely — the skip is
   now decided from the emit response, so the probe video no longer has to
   leave the archive for the test to exercise the CGP path.

4. **Container restart recipe (env vars).** This runbook pulled env
   vars from the running container via `docker inspect --format '{{range
   .Config.Env}}{{println .}}{{end}}'` and passed them via `--env-file`.
   The compose file's `env_file: pmoves/env.shared` directive fails
   in worktrees that don't carry the gitignored `env.shared`. The
   `--env-file` workaround is documented inline here as the canonical
   bring-up path. Not in scope for the follow-up commit.