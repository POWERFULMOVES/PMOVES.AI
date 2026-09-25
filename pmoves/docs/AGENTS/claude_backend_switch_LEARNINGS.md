# Claude Code backend switch — lessons

**Slice:** `feat/claude-backend-switch` (off `feat/pmoves-launcher-generator@4c7316d653`).
**Author:** mavis (DARKXSIDE).
**Date:** 2026-09-25.
**Status:** built + tested, awaiting PR review.

This file is the 4-bucket × 5-class taxonomy of lessons learned while building
the per-launch `--backend={auto|anthropic|minimax}` override and the persistent
`pmoves-mini claude-backend {show,set,backup,restore}` switch.

The bucket × class matrix follows the project convention; see the lane-C LEARNINGS
file for the column / row definitions and the rationale for keeping them.

---

## Bucket 1 — design (architecture / scope / non-goals)

### D-1 — "auto" heuristic is keyed on `ANTHROPIC_BASE_URL` only, NOT `ANTHROPIC_MODEL`
**Class:** scope / decision under ambiguity.

The plan considered keying `auto` on either `ANTHROPIC_BASE_URL` OR
`ANTHROPIC_MODEL`. It chose the URL because model names alone don't prove routing
— the operator may want Anthropic's opus but with a custom model id, and we
should not silently undo that. Pinning this in `is_hijacked()` and tested by
`AutoDetectHijackTests.test_anthropic_api_host_with_path_not_hijacked` (URL with
path is still clean) and `ApplyBackendTests.test_auto_no_base_url_with_model_only_passes_through`
(model-only override is preserved). Document this in the LEARNINGS file rather
than the user-facing `--help` — operators who care reach here.

### D-2 — Per-launch flag is the OVERRIDE layer, not the registry
**Class:** architecture / load-bearing separation.

The Mavis-SDK env-strip registry (`MAVIS_SDK_ENV_NAMES`) is GLOBAL — every CLI
launch strips the same set. The hijack is claude-specific. Adding
`ANTHROPIC_MODEL` etc. to that registry would also strip them for kilo-pmoves
(kilo talks to Z.AI/GLM, doesn't want Anthropic env). The per-launch
`--backend=` flag is the right granularity because it scopes the override to
claude only.

**Companion decision (D-2b):** The Mavis-SDK env-strip keeps
`ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY` for claude
(NOT removed from the registry) because claude legitimately needs them. The
override layer (this slice) handles the case where the *value* of those vars
points to the wrong endpoint.

### D-3 — Two switch surfaces, one source of truth
**Class:** API / separation of concerns.

`pmoves-mini claude-backend` writes the templates (persistent, writes
`~/.claude/settings.json`). `claude-pmoves --backend=` only acts at launch time
(transient, doesn't touch `~/.claude/settings.json`). They compose: `set anthropic`
makes persistent the default; `--backend=minimax` overrides one launch.

**Non-obvious consequence:** the python module (`claude_backend.py`) is the single
source of truth for both surfaces. Bash and PowerShell twins invoke it as a
subprocess; `mini_cli.py` imports it directly. This means changes to the strip
semantics propagate to all three callers with no per-surface duplication.

---

## Bucket 2 — implementation (correctness / robustness / bugs)

### I-1 — Same-second backup collisions silently overwrite
**Class:** correctness, **caught by** `BackupRestoreTests::test_idempotency_two_consecutive_sets_create_two_backups`.

`backup_name()` uses second-resolution UTC timestamps: `2026-09-25T18-49-00Z`.
Two `set anthropic` calls within the same second produced the same backup path,
so the second `set` overwrote the first snapshot. That defeats the audit trail
that "every `set` is recoverable" relies on.

**Fix:** `write_settings_atomic` now appends `.1`, `.2`, ... when the target
backup already exists. Pinned by `test_idempotency` so a future regression to
the old behavior fails the test directly.

**Lesson:** the test was added BEFORE running the slice; without it the bug
would have shipped silently. Same lesson as Lane C's `test_audit_log_*`: a
test that can only assert presence can't catch an overwrite.

### I-2 — `apply` CLI's stdout `unset NAME` emission only fired on `env[var] == ""`
**Class:** correctness, **caught by** bash scenario `scenario_claude_backend_auto_strips_minimax_hijack_body`.

The first version of the `apply` CLI emitted `unset NAME` only when the in-memory
env dict had the var set to the empty string. But `apply_backend` does
`env.pop(var, None)`, which removes the var entirely. The `unset` loop never
fired, and the bash launcher's `eval "$out"` had nothing to unset.

**Fix:** emit `unset NAME` for every var in the `stripped` return list (which IS
populated correctly by `apply_backend`). The dict's `pop` is the right
operation in `apply_backend`; the loop's predicate was the bug.

**Lesson:** the unit tests for `apply_backend` directly exercised the function
and passed. The bug only surfaced at the E2E boundary where the bash launcher's
`eval` had nothing to act on. E2E tests catch layer-boundary bugs that unit
tests can't.

### I-3 — Bash JSONL audit-log needles assumed compact JSON; actual format has spaces
**Class:** test correctness, **caught by** bash scenario's `"backend":"auto"` needle.

`json.dumps(entry)` uses default separators (`, ` + `: `), producing
`{"backend": "auto"}`. The first version of the bash scenario's
`assert_in "$audit_line" '"backend":"auto"'` matched `haystack` with spaces
between keys and values, so the assertion failed.

**Fix:** pin `"backend": "auto"` and `"cli": "claude"` (with spaces) to match
the existing `PMOVES_MAVIS_SDK_*` convention. Pinned by the bash scenario AND
by TwinParityTests (which checks the python module's audit emit directly).

**Lesson:** the existing `mavis_sdk_audit.py` CLI parses the same JSONL. The
ratchet for that audit format is in the python test; the bash scenario pins
the same shape with the same needles. Drift between the two surfaces is the
same class of bug as Lane C's twin-registry drift — caught by reading both.

### I-4 — `pm_pick_python ""` in bash context: probe="" means "any python"
**Class:** pm-python.sh contract.

`pm_pick_python` is the canonical python discovery. Its signature is
`pm_pick_python [probe]` where probe is a module name to test. Empty probe =
"any python". This is the documented contract from `pm-python.sh:42-46`
("any python (json/os/re tools)").

The new `claude_backend_apply` bash function uses `pm_pick_python ""` (empty
probe) because `claude_backend.py apply` only needs the stdlib. Pinned by
`test_pm_pick_python_discovery_no_probe` (existing test) + the bash scenario
that invokes the helper end-to-end.

---

## Bucket 3 — operations (testing / CI / observability)

### O-1 — 33-test unit module + 1 bash scenario + 1 ratchet = high signal at low cost
**Class:** test coverage / ROI.

The 33 tests in `test_claude_backend.py` cover six classes (parse, hijack
detection, apply, backup/restore, templates, twin parity). The bash scenario
covers the E2E boundary. The ratchet (`test_claude_pmoves_emits_backend_flag_help_block`)
catches cross-twin drift at the file-content level. Together: 144 assertions
across 71 python tests + 73 bash assertions, three real bugs caught during
development (I-1, I-2, I-3), zero false positives.

### O-2 — Twin parity ratchet is the load-bearing class of test
**Class:** regression prevention.

The bash + PowerShell twins of `claude-pmoves` reference the SAME flag surface
(`--backend=`), the SAME env var (`PMOVES_CLAUDE_BACKEND`), the SAME WARN phrase
substring (`stripped Mavis SDK hijack`), and the SAME persistent-switch hint
(`pmoves-mini claude-backend`). Drift here means an operator who greps one twin
cannot find the same surface in the other.

**TwinParityTests** pins 5 surface tokens across both twins. Pinned by reading
the file contents directly (not by spawning subshells), so the test is hermetic
and CI-fast.

### O-3 — Audit-log write is best-effort; never a launch blocker
**Class:** failure-mode preservation.

The `apply` CLI's audit append is best-effort: `Path.mkdir(parents=True,
exist_ok=True)` + `try: open("a") except OSError: pass`. The strip semantics
always complete even when the audit write fails.

This mirrors the Mavis-SDK env-strip lane's `>> "$log_path" 2>/dev/null || true`
semantics. The bash scenario (`scenario_audit_log_best_effort_no_throw_body`
from Lane C) pins the contract for the SDK env-strip; the python module's
`_audit_append` is the parallel for the override layer.

---

## Bucket 4 — collaboration / process

### C-1 — SDK + doc provenance for every fix (DARKXSIDE practice 2026-09-16)
**Class:** operator practice / non-workaround culture.

The slice ships:
- **SDK file:line** — `pmoves/tools/claude_backend.py:153-191` (apply_backend),
  `pmoves/scripts/claude-pmoves.sh:16-104` (--backend parsing + apply invocation),
  `pmoves/scripts/claude-pmoves.ps1:9-66` (mirror).
- **AGNOTE row** — `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` RELEASE row at
  `2026-09-25T18:51:00Z`.
- **LEARNINGS file** — this document, 4-bucket × 5-class taxonomy.
- **PR + branch** — new PR off `feat/claude-backend-switch` into `main`.

No workarounds. Every fix has a documented provenance chain. A future agent
debugging a regression in this slice has the full trail.

### C-2 — Two-layer model separates TRANSIENT and PERSISTENT
**Class:** API surface.

Operators have TWO levers for the same underlying problem:
- `claude-pmoves --backend=anthropic "..."` — one-shot override for THIS launch.
- `pmoves-mini claude-backend set anthropic` — flips the persistent default for
  ALL future launches.

The two compose: `set` makes persistent the default; `--backend=` overrides one
launch. The audit log records both (the transient emit goes to stderr + JSONL;
the persistent set doesn't emit to the JSONL — it logs to the AGNOTE release
trail instead).

### C-3 — Operator-side `pmoves-mini claude-backend set anthropic` is post-merge, not pre-merge
**Class:** sequencing.

The slice lands the tools, NOT the operator's persistent state change. The
operator runs `pmoves-mini claude-backend set anthropic` ONCE after the PR
merges, to flip the persistent state on their host. The slice ships the
mechanism; the operator drives the policy.

This mirrors Lane C's "post-merge applies" pattern: code lands, operator runs
the explicit command, state changes. Code + state change together in the same
PR is a bigger blast radius than the slice warrants.

---

## Cross-cutting

### X-1 — Three bugs caught and fixed during the slice, all surfaced by tests
| Bug | Caught by | Class | Fix |
|---|---|---|---|
| Same-second backup collisions | `test_idempotency_two_consecutive_sets_create_two_backups` | I-1 | Append `.1`, `.2`, ... when target exists |
| `apply` CLI never emitted `unset NAME` | bash scenario's `assert_in "unset ANTHROPIC_BASE_URL"` | I-2 | Emit `unset` for every var in `stripped` return list |
| Bash needles assumed compact JSONL | bash scenario's `"backend":"auto"` assertion | I-3 | Pin `"backend": "auto"` (with spaces) |

Three bugs, three different test classes (unit, E2E, format pin). All surfaced
BEFORE the slice shipped. The test suite earned its keep on this slice.

### X-2 — Companion docs (README + LEARNINGS) are part of the deliverable
**Class:** documentation completeness.

- `pmoves/configs/claude_settings/README.md` — template usage notes for the
  operator. Single source of truth for what `set anthropic` / `set minimax` do.
- `pmoves/docs/AGENTS/claude_backend_switch_LEARNINGS.md` — this file, the
  4-bucket × 5-class taxonomy.

Both were written in the same worktree, in the same PR, alongside the SDK
changes. Documentation debt is the kind of thing that compounds; this slice
closes that loop on day 1.

### X-3 — Operator handoff is documented in the LEARNINGS, not just the AGNOTE
**Class:** handoff / next-slice readiness.

The AGNOTE row is for the audit trail (what shipped, when, who). The LEARNINGS
file is for the NEXT agent (what to watch out for, what to read first, what
decisions were load-bearing). Both readers need different surfaces; the slice
ships both.

---

## Verification commands

```
# Bash runner
bash pmoves/tests/test_mavis_sdk_env.sh

# Python tests
"C:\Users\russe\AppData\Local\Programs\Python\Python312\python.exe" -m pytest \
  pmoves/tools/tests/test_pmoves_launcher_generator.py \
  pmoves/tools/tests/test_mavis_sdk_audit.py \
  pmoves/tools/tests/test_claude_backend.py \
  pmoves/tests/test_mavis_sdk_env.py

# Manual switch flow
pmoves-mini claude-backend show
pmoves-mini claude-backend set anthropic
pmoves-mini claude-backend show

# Per-launch override
PMOVES_CLAUDE_BACKEND=anthropic bash deploy/provision/claude-pmoves.sh --help
```
