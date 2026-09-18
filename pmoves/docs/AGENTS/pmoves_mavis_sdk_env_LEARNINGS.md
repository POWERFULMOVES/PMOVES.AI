# pmoves_mavis_sdk_env_LEARNINGS.md

**Lane:** Mavis SDK env-strip for ALL PMOVES launchers — single-helper parity across bash + PowerShell + per-CLI needs registry
**Author:** 5090-CLAUDE · **Operator:** DARKXSIDE
**Active:** 2026-09-17 · **Companion CLAIM row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` 2026-09-17T... (TBD at commit)
**PR:** (pending — see `feat/pmoves-mavis-sdk-env` worktree)

---

## Operator direction (verbatim)

> "i need claude-pmoves to load the claude-code settings as it is being overidden by your settings. since you and glm both have helpers for claude code ensure parrity along that surface for the registry. Mavis providers has model provider verifier and cascade and that helps other models jump in the harness"

Two named bugs + one named architecture:

1. **Override bug**: `claude-pmoves` is being overridden by "your settings" (Mavis SDK env block in `~/.claude/settings.json`).
2. **Parity gap**: `claude-pmoves` (Mavis's helper) and GLM's helper (`kilo-pmoves`) must be at parity — both must scrub the Mavis SDK env before exec'ing the downstream CLI.
3. **Provider verifier + cascade**: existing PMOVES architecture (`pmoves/tools/provider_verifier_gate.py` + `pmoves/tools/provider_cascade.py`) — once launchers stop clobbering the provider config, other models can "jump in" (claude, GLM, Kimi, Hermes, etc., all use the same harness).

Operator follow-up (interview answer to my "A: strip + preserve + WARN" option):

> "claude-pmoves.sh + claude-pmoves.ps1 (hand-written): add a top-of-file need check against sdk as well as check PMOVES-Registry for existing tooling we need to check that for tooling as we dont want to duplicate however we want our tools to evolve"

Two refinements from the follow-up:

1. **Need check against SDK** (not a blanket blocklist) — for each Mavis SDK var in the SHELL env, ask "does this CLI consume it?". Per-CLI registry decides what's preserved vs stripped.
2. **PMOVES-Registry parity** — `pmoves/configs/cli_tools.yaml` is the source of truth for CLI identity. Helper registry keys MUST match the registry's CLI names; new CLIs absent from the helper's registry fall through to the safe default (strip everything, never inherit).

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **contract-correctness** | The Mavis SDK env block (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`, `MCP_TIMEOUT`, `API_TIMEOUT_MS`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `CLAUDE_CODE_*`, `CLAUDE_SESSION_*`) is inherited by every PMOVES launcher that runs in a Mavis shell. Without scrubbing, downstream CLIs get Mavis's provider config baked in — claude talks to `api.minimax.io` instead of the operator's intended Anthropic endpoint, kilo gets an `ANTHROPIC_BASE_URL` it doesn't understand. | `pmoves/scripts/mavis_sdk_env.sh:84-101` (registry), `pmoves/scripts/mavis_sdk_env.sh:226-279` (strip); `pmoves/scripts/mavis_sdk_env.ps1` (PowerShell twin, same registry). | Every CLI helper that runs in a shell session whose env was set by an upstream SDK. |
| 2 | **defense-in-depth** | Per-CLI NEEDS list, not a blanket blocklist. claude keeps `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_API_KEY` (it IS the Anthropic consumer); kilo/codex/kimi/hermes strip every Mavis SDK var (they don't consume any); `pmoves-mini` keeps ALL via the `["*"]` wildcard (it IS the Mavis agent). Adding a new Mavis SDK var to the registry forces an explicit "needs this CLI? y/n" decision. | `pmoves/scripts/mavis_sdk_env.sh:131-141` (per-CLI arrays); `mavis_sdk_needs_for` case statement at `pmoves/scripts/mavis_sdk_env.sh:158-167`; tests at `pmoves/tests/test_mavis_sdk_env.sh:99-104` (`pmoves-mini consumes everything via *`). | Any "env policy must differ per consumer" pattern. |
| 3 | **defense-in-depth** | Two layers of env hygiene: the **shell env** is stripped via `mavis_sdk_strip_env_for` (this PR); the **env.shared file** is filtered via the per-CLI blocklist in `claude-pmoves.sh`/`claude-pmoves.ps1` (existing). The two layers are INDEPENDENT — a Mavis SDK var can come from the parent process (shell env) AND from `env.shared` (PMOVES fleet creds). The strip handles the shell env; the blocklist handles env.shared. | `claude-pmoves.sh:42-66` (shell env strip) and `claude-pmoves.sh:74-89` (env.shared blocklist); the two sections are explicitly labeled as covering independent layers in the header comments. | Any "two surfaces share a backend" pattern where one is config-driven (file) and the other is process-driven (shell env). |
| 4 | **semantic-naming drift** | The bash and PowerShell twins MUST encode the same registry. The pre-existing bug: the bash blocklist had `CLAUDE_CODE_` (anchored literal — matches only a var literally named `CLAUDE_CODE_`, not `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`) while the PowerShell blocklist had `CLAUDE_CODE_*` (regex via `-replace '\*', '.*'`, matches anything with the prefix). One platform stripped vars the other did not. Fix: bash uses `CLAUDE_CODE_.+` (regex, require at least one char), PowerShell keeps `CLAUDE_CODE_*`. The two are now equivalent. | Drift diagnostic: `grep 'CLAUDE_CODE_' deploy/provision/claude-pmoves.{sh,ps1}` showed different patterns; fix recorded in `claude-pmoves.sh:75-83` (DRIFT FIX 2026-09-17 comment) and `claude-pmoves.ps1:13-29`. | Every shared semantic (blocklist, registry key, env var name) that has both bash and PowerShell implementations. |
| 5 | **reasoning-gap** | The strip call uses `{tool.family}` (e.g., `kilo`), NOT `{tool.binary}` (which substitutes to `kilo-pmoves` because of a pre-existing lookup bug in `BINARY_BY_TOOL.get(name, name)` that misses the family keying). The strip call must look up the needs registry by FAMILY name — that's how `pmoves/configs/cli_tools.yaml` and `MAVIS_SDK_NEEDS_BY_TOOL` agree. A regression that uses `{tool.binary}` (the launcher name) hits the "unknown CLI" branch and strips everything (the safe default), which would break `claude-pmoves` (loses `ANTHROPIC_BASE_URL` that claude actually needs). | `pmoves/tools/pmoves_launcher_generator.py:431` (bash template uses `{tool.family}`); `pmoves/tools/pmoves_launcher_generator.py:584` (ps1 template uses `{tool.family}`); regression test at `pmoves/tools/tests/test_pmoves_launcher_generator.py:158-189` asserts `cli_arg` does NOT end with `-pmoves`. | Every "registry lookup" pattern where the registry key is the FAMILY, not the LAUNCHER name. |
| 6 | **contract-correctness** | Unknown CLI name → safe default (strip everything). The registry has an explicit `*) return 0` branch in `mavis_sdk_needs_for` that returns an empty needs list for any CLI not in `MAVIS_SDK_NEEDS_BY_TOOL`. Stripping everything is the SAFE default because the alternative (silently inheriting Mavis config) is the bug this file exists to prevent. | `pmoves/scripts/mavis_sdk_env.sh:158-167` (case statement's `*)` branch); `pmoves/scripts/mavis_sdk_env.ps1` (`Get-MavisSdkNeedsFor` `else` branch); test at `pmoves/tests/test_mavis_sdk_env.sh:182-194` (unknown CLI strips everything). | Any "registry lookup with safe fallback" pattern. |
| 7 | **defense-in-depth** | Glob pattern support: `CLAUDE_CODE_*` and `CLAUDE_SESSION_*` match live env vars matching that prefix (e.g., `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, which is NOT literally in the registry but IS caught via the glob). Bash uses `[[ "$name" == $pat ]]` (bash glob); PowerShell uses `-like $pat` (PowerShell -like). The two operators are equivalent for the patterns used. | `pmoves/scripts/mavis_sdk_env.sh:201-205` (bash glob match); `pmoves/scripts/mavis_sdk_env.ps1` (PowerShell -like); test at `pmoves/tests/test_mavis_sdk_env.sh:166-180` (CLAUDE_CODE_AUTO_COMPACT_WINDOW glob match). | Every registry-of-prefixes pattern where new live vars appear after the registry is written. |
| 8 | **contract-correctness** | Strip semantics: for each Mavis SDK var in the SHELL env, preserve the value under `PMOVES_MAVIS_SDK_<NAME>` (so the operator can inspect later), unset the original (so the launched CLI doesn't see it), record the stripped names in `PMOVES_MAVIS_SDK_STRIPPED` (newline-separated), set `PMOVES_MAVIS_SDK_CLI` (the CLI name passed in), emit ONE WARN line on stderr with the count + names. The audit trail (prefixed copies + STRIPPED list + CLI marker) is what makes the operation reversible. | `pmoves/scripts/mavis_sdk_env.sh:218-274` (preservation + unset + WARN); `pmoves/scripts/mavis_sdk_env.ps1` (same contract in PowerShell); tests at `pmoves/tests/test_mavis_sdk_env.sh:99-156` (the kilo + claude scenarios assert the prefixed copies are set with the original values). | Every "env mutation" pattern where the operator needs to verify what was actually stripped. |

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 1 lesson (#5) — registry key vs launcher name distinction is the load-bearing one; easy to regress.
- **(2) semantic-naming drift** — 1 lesson (#4) — bash/ps1 twins must encode the same registry; the CLAUDE_CODE_ vs CLAUDE_CODE_* drift was a real production bug.
- **(3) contract-correctness** — 3 lessons (#1, #6, #8) — env block contents, unknown CLI fallback, strip audit trail are the load-bearing contracts.
- **(4) defense-in-depth** — 3 lessons (#2, #3, #7) — per-CLI needs list, two-layer env hygiene, glob pattern support are the defense layers.

Pattern: **defense-in-depth + contract-correctness dominate** — 6 of 8 lessons. This is a "thin wrapper that surfaces policy" slice; the contracts (registry keys, exit semantics, audit trail) and defense (per-CLI needs, two layers, glob fall-through) ARE the value.

---

## Test inventory

| File | Lines | Tests | What it pins |
|---|---|---|---|
| `pmoves/scripts/mavis_sdk_env.sh` | 280 | — | The helper itself: `MAVIS_SDK_ENV_NAMES` registry (15 vars + 2 globs), `MAVIS_SDK_NEEDS_BY_TOOL_<cli>` per-CLI arrays, `mavis_sdk_needs_for` lookup, `mavis_sdk_strip_env_for` strip function. |
| `pmoves/scripts/mavis_sdk_env.ps1` | 220 | — | PowerShell twin: identical registry + per-CLI needs dict (`$MAVIS_SDK_NEEDS_BY_TOOL`), `Get-MavisSdkNeedsFor`, `Strip-MavisSdkEnvFor`. |
| `pmoves/tests/test_mavis_sdk_env.sh` | 244 | 5 scenarios / 34 assertions | kilo strips everything; claude keeps ANTHROPIC_*; pmoves-mini consumes via `*`; `CLAUDE_CODE_*` glob matches; unknown CLI falls back to safe default. Subprocess-via-file pattern (PowerShell quoting kills `bash -c`). |
| `pmoves/tests/test_mavis_sdk_env.py` | 60 | 1 | Python wrapper that invokes the bash runner; prints the runner's stdout/stderr so the operator sees the per-scenario PASS/FAIL when CI runs. |
| `pmoves/tools/tests/test_pmoves_launcher_generator.py:158-189` | +30 | 3 new | (a) every generator-managed bash LAUNCHER (excludes install + pin) contains `mavis_sdk_strip_env_for` + uses family name not launcher name; (b) every ps1 LAUNCHER contains `Strip-MavisSdkEnvFor`; (c) hand-written `claude-pmoves.{sh,ps1}` carry the strip step. |

---

## SDK provenance

- **Helper (bash)**: `pmoves/scripts/mavis_sdk_env.sh` (280 lines, new)
- **Helper (PowerShell twin)**: `pmoves/scripts/mavis_sdk_env.ps1` (220 lines, new)
- **Tests (bash runner)**: `pmoves/tests/test_mavis_sdk_env.sh` (244 lines, new)
- **Tests (Python wrapper)**: `pmoves/tests/test_mavis_sdk_env.py` (60 lines, new)
- **Generator template updates**: `pmoves/tools/pmoves_launcher_generator.py` (+~50 lines for the Mavis SDK env strip section in both bash + ps1 templates, +1 line for the `BINARY_BY_TOOL.get(_family_of(name), _family_of(name))` bug fix)
- **Generator tests**: `pmoves/tools/tests/test_pmoves_launcher_generator.py` (+~50 lines, 3 new tests)
- **Hand-written edits**: `deploy/provision/claude-pmoves.sh` (+24 lines for strip section, +DRIFT FIX comment) and `deploy/provision/claude-pmoves.ps1` (+24 lines for the PowerShell twin's strip section)
- **Regenerated launchers**: 49 files under `deploy/provision/` (per `python pmoves/tools/pmoves_launcher_generator.py` plan)

---

## Bug discovered during this slice

**Pre-existing bug in `pmoves/tools/pmoves_launcher_generator.py:276`** (now line 276):
```python
binary=BINARY_BY_TOOL.get(name, name),
```
`name` is the LAUNCHER name (e.g., `kilo-pmoves`); `BINARY_BY_TOOL` is keyed by FAMILY (e.g., `kilo`). The lookup always misses, falls back to the launcher name, and the template's `exec {tool.binary}` line ends up calling the launcher itself (infinite loop / wrong exec target).

**Fix**: `binary=BINARY_BY_TOOL.get(_family_of(name), _family_of(name))`. The family of `kilo-pmoves` is `kilo`, which IS in `BINARY_BY_TOOL`. Generated launchers now correctly `exec kilo "$@"`.

This is a load-bearing bug fix bundled with this slice because:
1. It was discovered during verification of the new strip section (the strip call uses family, the exec line uses binary — the inconsistency surfaced as `mavis_sdk_strip_env_for "kilo"` paired with `exec kilo-pmoves "$@"`).
2. Fixing the strip without fixing the exec would ship launchers that never actually exec the right binary.
3. The fix is 1 line in the generator, mechanical, has no behavioral risk for currently-working paths (the wrong-exec path was always broken — no operator depends on the buggy behavior).

---

## Open follow-ups

1. **`crush-pmoves.{sh,ps1}` hand-edit** — currently excluded from the strip step in the test (`test_hand_written_launchers_have_strip_step` checks only `claude-pmoves`). The operator's "parity along that surface" directive implies crush-pmoves should also get the strip; can be a follow-up slice if the operator wants.
2. **Mavis SDK env drift notification** — when the operator adds a new var to `MAVIS_SDK_ENV_NAMES` in `pmoves/scripts/mavis_sdk_env.sh`, they should ALSO update the PowerShell twin (`pmoves/scripts/mavis_sdk_env.ps1`). Currently no drift check pins the two in step. A `pmoves/tests/test_mavis_sdk_env_drift.py` ratchet that asserts the bash and PowerShell registries have identical contents is a low-cost follow-up.
3. **Registry shape documentation** — `pmoves/configs/cli_tools.yaml` is the PMOVES-Registry the operator referenced. A cross-link section in `pmoves/scripts/mavis_sdk_env.sh` pointing at the registry, plus a note in the registry pointing at the helper, would make the two-way reference explicit. Currently the connection is implicit (both keyed by CLI name).
4. **`PMOVES_MAVIS_SDK_*` expiry** — the prefixed vars persist for the lifetime of the shell session. If the operator runs `unset PMOVES_MAVIS_SDK_*` after the first inspection, the audit trail is gone. A `mavis-sdk-audit.log` (one-line per strip call) would be a more durable trail. Out of scope for this slice — the prefixed copies are sufficient for the operator's "find out what's bleeding" use case.
