# Review: PR #1279 — feat(services): GRAPHITI pipeline stubs, voice relay NATS, DGX Spark + Cataclysm TAC trees

**Reviewer:** Agent Zero Code Reviewer
**Date:** 2026-04-18
**Branch:** feat/phi-4482-services-nats-tac → main
**Files:** 13 changed, +997/-0

---

## Review Summary

**Verdict:** REQUEST CHANGES

**Overview:** Adds GRAPHITI pipeline stubs (3 stages), two NATS subject registries (97 + 8 entries), two TAC trees (DGX Spark 278-line operational checklist, Cataclysm 105-line creative pipeline), NATS JetStream stream definitions, an n8n workflow stub, and two media service stubs. The infrastructure intent is sound but contains a deploy-blocking NATS config bug, a cross-reference path error, a TAC schema inconsistency, and a subject namespace mismatch between streams and TAC trees. No tests.

---

## Critical Issues

### C1. NATS stream `max_bytes` uses invalid format — will fail on deploy
**File:** `pmoves/nats/mesh_gpu_streams.yaml:11`

```yaml
max_bytes: 256MB
```

JetStream stream configs require integer bytes. `256MB` is a human-readable alias not accepted by `nats stream add --config`. This will produce a parse error at deploy time.

**Fix:** `max_bytes: 268435456` (or remove the field to use server default).

### C2. NATS stream subjects don't cover TAC tree subjects — messages will be lost
**File:** `pmoves/nats/mesh_gpu_streams.yaml` vs `pmoves/configs/tac_trees/dgx-spark.tac.yaml`

Stream subjects defined:
- `mesh.gpu.inference.>`
- `mesh.gpu.health.>`
- `mesh.gpu.models.>`
- `mesh.gpu.training.>`
- `mesh.gpu.metrics.>`

TAC tree references:
- `mesh.gpu.command.v1`
- `mesh.gpu.status.v1`
- `mesh.gpu.model.loaded.v1`
- `mesh.gpu.model.unloaded.v1`
- `mesh.gpu.command.result.v1`

**None** of the TAC tree subjects fall under any stream wildcard. `mesh.gpu.status.v1` does not match `mesh.gpu.health.>`. `mesh.gpu.command.v1` does not match `mesh.gpu.inference.>`. Messages published to these subjects will not be persisted by JetStream.

**Fix:** Align stream subjects with actual usage. E.g., `mesh.gpu.status.>` or `mesh.gpu.>` as a catch-all, or add specific subjects to the streams.

---

## Important Issues

### I1. sign_trail.py path wrong in NATS subject registry
**File:** `pmoves/services/graphiti/nats_subject_registry.py:42`

```python
subscriber_file: "pmoves/services/gateway/scripts/sign_trail.py",
```

Actual location: `pmoves/tools/sign_trail.py`. Any tooling that resolves subscriber files from this registry will hit a dead path.

### I2. TAC tree schema inconsistency — cataclysm-studios breaks convention
**File:** `pmoves/configs/tac_trees/cataclysm-studios.tac.yaml:7-9`

Uses `tac_tree:` top-level key with `phases:` list structure. Every other TAC tree in the codebase (26 files) uses `name:` + `root:` with nested `children:`. This means any TAC tree parser/runner that works with the other 26 trees will fail on this one.

**Fix:** Either (a) restructure cataclysm to use `name:` + `root:` + `children:` like all others, or (b) document why this is a deliberate second schema and update parsers accordingly.

### I3. media-audio and media-video `__init__.py` crash on import
**Files:** `pmoves/services/media-audio/__init__.py:6`, `pmoves/services/media-video/__init__.py:6`

```python
raise NotImplementedError("Media audio service not yet implemented")
```

Module-level `raise` means `import pmoves.services.media_audio` crashes. This breaks IDE tooling, linters, test discovery (`pytest --collect-only`), and any code that tries to inspect the service registry. No other service stub in the codebase uses this pattern — existing stubs use docstring-only modules.

**Fix:** Remove the raise. Use a docstring-only `__init__.py` like every other stub service.

### I4. Duplicate `SubjectEntry` dataclass with different fields
**Files:** `pmoves/services/graphiti/nats_subject_registry.py:13-19`, `pmoves/services/voice-relay/nats_subject_registry.py:12-16`

Graphiti version: 6 fields (`subject, status, stage, subscriber_file, publisher, notes`).
Voice version: 4 fields (`subject, status, subscriber_file, notes`).

Same name, different shape. If any code imports both, it will silently shadow one definition.

**Fix:** Extract a shared `SubjectEntry` into `pmoves/services/common/` (which already exists) and import from there. Add `publisher` and `stage` to the voice version or make them optional.

### I5. No tests for any of the 997 lines added

Zero test files. At minimum:
- `test_nats_subject_registry.py` — verify assertion passes, status counts are correct, filters work
- `test_graphiti_stubs.py` — verify each stage raises `NotImplementedError` with the correct NATS subject in the message

Even stubs deserve tests — they encode contracts (function signatures, error messages, subject names).

---

## Suggestions

### S1. Capital-D `Discord.messages.fetched.v1` breaks lowercase convention
**File:** `pmoves/services/graphiti/nats_subject_registry.py:281`

All 96 other subjects use lowercase. `Discord.messages.fetched.v1` should be `discord.messages.fetched.v1`.

### S2. Stale docstring count
**File:** `pmoves/services/graphiti/nats_subject_registry.py:4`

Docstring says "Tracks all 88 GRAPHITI-related NATS subjects" but assert on line 327 says 97. Update the docstring.

### S3. Unused `logger` in all three GRAPHITI stage files
**Files:** `stage1_pr_monitor.py:21`, `stage2_pr_trim.py:19`, `stage3_chit_encode.py:19`

`logger = logging.getLogger(__name__)` is defined but never called. Either use it (e.g., log the NotImplementedError before raising) or remove it.

### S4. Unused `json` import in stage1
**File:** `pmoves/services/graphiti/stage1_pr_monitor.py:16`

`import json` — not used anywhere in the file.

### S5. Wildcard subject `skills.pipeline.*.v1` mixed with concrete entries
**File:** `pmoves/services/graphiti/nats_subject_registry.py:96`

A wildcard monitoring subject listed alongside 96 concrete subjects is semantically different. Add a comment or separate section explaining this is a catch-all monitor, not a publish target.

### S6. PR should be split

997 lines across 4 distinct concerns:
1. GRAPHITI pipeline stubs + registry (5 files)
2. Voice relay NATS registry (1 file)
3. DGX Spark TAC tree + NATS streams (2 files)
4. Cataclysm TAC tree + n8n workflow (2 files)
5. Media service stubs (2 files)

Stacking 3-4 smaller PRs would let domain experts review their area without context-switching.

### S7. n8n workflow has no configured URL
**File:** `pmoves/n8n-workflows/cataclysm-creative-pipeline.json:16-22`

The `httpRequest` node has `parameters: {"topic": "..."}` but no `url` field. It won't do anything even if imported into n8n. Mark it more explicitly or add a placeholder URL.

### S8. `spark_claw.yaml` cross-reference path incomplete
**File:** `pmoves/configs/tac_trees/dgx-spark.tac.yaml:11`

Header says `pmoves/prompts/spark_claw.yaml` but actual path is `pmoves/configs/agent-profiles/spark_claw.yaml`.

### S9. `.a0proj/plugins/_model_config/config.yaml` reference doesn't exist
**File:** `pmoves/configs/tac_trees/dgx-spark.tac.yaml:72`

Cross-ref to a file that doesn't exist in the repo. Remove or correct.

---

## What's Done Well

- **GRAPHITI stub pattern is excellent.** Each stage file has a clear docstring with NATS consume/publish subjects, dependency notes, status, and a structured TODO list. The `NotImplementedError` messages include the target NATS subject — this is a strong contract-encoding pattern that will guide implementation.
- **DGX Spark TAC tree is thorough.** 6 phases, actionable check steps with specific commands, expect clauses, and cross-references. The `status: future` tagging on not-yet-deployed items is a good practice.
- **Subject registry is well-organized.** Grouped by team/stage with clear section headers, status tracking, and filter functions. The assertion guard catches drift.
- **Cataclysm TAC tree phase dependency chain is clean.** `depends_on` creates a clear linear pipeline with matching entry/exit conditions.

---

## Verification Story

- **Tests reviewed:** No — zero test files in the diff
- **Build verified:** Partially — `python -c "from pmoves.services.graphiti.nats_subject_registry import get_status_summary; print(get_status_summary())"` would verify the registry loads, but media-audio/media-video `__init__.py` would crash any broad import
- **Security checked:** Yes — no secrets, no user input handling, no auth logic in this PR. NATS subjects are internal-only. The mesh GPU command subjects (`mesh.gpu.command.v1`) have no auth layer defined but that's expected for stub stage — flag for when implementation ships
- **Cross-references verified:** 3 of 5 cross-ref paths in DGX Spark TAC tree are invalid (sign_trail.py, spark_claw.yaml, model_config)

---

## Required Before Merge

| # | Issue | Severity |
|---|-------|----------|
| C1 | Fix `max_bytes: 256MB` → integer | Critical |
| C2 | Align NATS stream subjects with TAC tree subjects | Critical |
| I1 | Fix sign_trail.py path in registry | Important |
| I2 | Align cataclysm TAC schema with codebase convention | Important |
| I3 | Remove module-level raise from media stubs | Important |
| I4 | Deduplicate SubjectEntry dataclass | Important |
| I5 | Add minimum tests for registry + stub contracts | Important |

## Optional Improvements

| # | Issue |
|---|-------|
| S1 | Lowercase `discord.messages.fetched.v1` |
| S2 | Fix stale "88 subjects" docstring |
| S3-S4 | Remove unused logger/json imports |
| S5 | Comment the wildcard subject |
| S6 | Consider splitting into smaller PRs |
| S7 | Add placeholder URL to n8n workflow |
| S8-S9 | Fix cross-ref paths in DGX Spark TAC tree |
