# Review Dump — POWERFULMOVES/PMOVES.AI#2434

**docs(agents): add Operating-in-This-Repo rules for non-obvious conventions**

- State: `OPEN` | Branch: `docs/agents-md-operating-rules` → `main` | +96/-14 (1 files)
- Author: POWERFULMOVES | Collected: 2026-08-06T17:39:47.919714+00:00

## Summary

| Metric | Count |
|---|---|
| Total threads | 7 |
| Resolved | 7 |
| Open P1/P2 (actionable) | 0 |
| Committable suggestions | 2 |

**Severity breakdown:** P1=1, P2=2, question=1, unclassified=3

## Reviews (2)

- **chatgpt-codex-connector** (COMMENTED) —  ### 💡 Codex Review  Here are some automated review suggestions for this pull request.  **Reviewed commit:** `dfc540939f`       <details> <summary>ℹ️ About Codex in GitHub</summary> <br/>  [Your team 
- **coderabbitai** (COMMENTED) — **Actionable comments posted: 4**  <details> <summary>🧹 Nitpick comments (1)</summary><blockquote>  <details> <summary>AGENTS.md (1)</summary><blockquote>  `178-178`: _📐 Maintainability & Code Quality

## Threads

### 1. ✅ [P1] chatgpt-codex-connector — `AGENTS.md:175`

**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Point secrets at the funnel inputs**

When an operator follows this arrow and places a key in an `env.tier-*` file before running the funnel, the key can be overwritten: `pmoves/mk/codex.mk` defines `env.shared` as `CHIT_EXPORT_ENV`, hydrates `env.shared`, exports it to CHIT, and then materializes the tier files from that bundle. Document `env.shared`/`local.env` (or the production bundle path) as inputs and `env.tier-*` as generated outputs so secret provisioning is not silently lost.

AGENTS.md reference: [AGENTS.md:L178-L178](https://github.com/POWERFULMOVES/PMOVES.AI/blob/dfc540939fa297216a2edf211f006913e08ecfdb/AGENTS.md#L178-L178)

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -72,29 +149,33 @@ All make targets live in `pmoves/Makefile`. Run with `make -C pmoves <target>`.
 - Keep modules small and single-purpose
 
 ## Testing
-- Framework: `pytest` — tests per service in `pmoves/tests/` (unit, smoke, integration, hardening)
+- Framework: `pytest` — tests per service in `pmoves/tests/` (unit, smoke, integration, hardening) and inline `pmoves/services/<svc>/tests/`
 - Mock external systems (NATS, Supabase, Neo4j); validate with sample payloads
-- Run: `pytest -q pmoves/tests/unit/` or per-service paths
-- Local CI checks: `docs/LOCAL_CI_CHECKS.md`
-- Before pushing: run relevant smoke targets and document results in PR
+- Run a single service suite: `pytest -q pmoves/services/<svc>/tests/` — run under env: `bash pmoves/scripts/with-env.sh pytest pmoves/tests/unit/`
+- Full verification: `cd pmoves && make verify-all` (smoke + health). Targeted: `make -C pmoves smoke`, `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`, `make -C pmoves model-readiness`
+- Docstring coverage **≥ 80%** on new Python (CI gate; enforced by CodeRabbit)
+- Local CI mirror: `docs/LOCAL_CI_CHECKS.md`
+- Before pushing: run `/test:pr` (or the smoke targets above) and paste a **Testing** section into the PR description
+- Submodule-pointer changes: always run `make -C pmoves submodule-integrity` before/after
 
 ## Commit & PR Guidelines
 - Conventional Commits: `feat(scope): description`, `fix(scope): description`, `docs(scope): description`
-- PRs: clear description, linked issues, affected services, testing evidence
+- Branch prefixes: `feat/`, `fix/`, `infra/`, `docs/`, `refactor/`. Forbidden: `feature/`, `pr/`, `p1`–`p7` (use workstream id). Worktrees or `feat/w<n>-...` IDs are common.
+- PRs: clear description, linked issues, affected services, **Testing** section with command evidence
 - Keep changes atomic; update docs/schemas when interfaces change
+- Merges are **gated** — not autonomous. The standing closeout flow (`pmoves/docs/operations/PR_CLOSEOUT.md`) requires: rebased on latest main, all review threads resolved, all required CI settled, a passing live-head audit, and (where the lane touches production) a Three-Body ACK (`[ACK: delivery] [ACK: control] [ACK: memory]`) in `AGNOTE4482_SIGNOFF_CHECKLIST.md`. Use the closeout flow; do not shortcut to `gh pr merge`.
+- After merging: `make -C pmoves docs-reconcile` and sign a CHIT trail entry.
+- Auto-review failure signatures + merge hazards (stacked-PR auto-close, squash-merge rebase, submodule-conflict `git update-index --cacheinfo`): see [`.claude/PATTERNS.md`](.claude/PATTERNS.md) §PR Review & Merge Workflow and §Merge Hazards.
 
 ## Secrets
 - Never commit secrets. Copy `pmoves/env.shared.example` → `pmoves/env.shared`
-- Shared defaults in `env.shared`, machine-specific in `.env.local`
+- Shared defaults in `env.shared`, machine-specific in `.env.local` (long-form `path: .env.local / required: false` in compose — the short-form `env_file: .env.local` is REQUIRED by default and hard-fails bring-up on nodes without the file)
 - Production secrets in GitHub Actions secrets and team vault
-- Onboarding: `docs/SECRETS_ONBOARDING.md`
-
-**The canonical secrets pipeline is `make -C pmoves secrets-funnel`.** It is the only
-supported path into CHIT storage, and it is defined in `pmoves/mk/codex.mk` — **not** in
-`pmoves/Makefile`. A grep of the root Makefile alone will not find it. Before adding any
-secrets tooling, run `grep -rn 'secrets-funnel' pmoves/Makefile pmoves/mk/` and
-`make -C pmoves help`. A duplicate funnel has been written twice by agents who checked only
-the root Makefile and concluded the target did not exist.
+- Onboarding: `docs/SECRETS_ONBOARDING.md`. Bootstrap: `make -C pmoves env-setup && make -C pmoves secrets-funnel && make -C pmoves auth-alignment`
+- **Never paste API keys in chat.** Secrets flow through `env.tier-*` → `make -C pmoves secrets-funnel`. The funnel is the only supported path into CHIT storage.
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2434#discussion_r3730014139)

### 2. ✅ [P2] chatgpt-codex-connector — `AGENTS.md:155`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Label verify-all as a full-stack bring-up**

In any environment with an existing stack, this is not merely a smoke-and-health check: `verify-all` first calls `bringup-with-ui`, which starts Supabase, core, published agents, external integrations, media, TensorZero, n8n, Jellyfin, and monitoring; if published Agent Zero readiness fails, the script also stops, removes, and recreates shared agent containers. Describe these mutating side effects or direct routine pre-push checks to the targeted commands so an operator does not disrupt a live stack while expecting read-only verification.

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -72,29 +149,33 @@ All make targets live in `pmoves/Makefile`. Run with `make -C pmoves <target>`.
 - Keep modules small and single-purpose
 
 ## Testing
-- Framework: `pytest` — tests per service in `pmoves/tests/` (unit, smoke, integration, hardening)
+- Framework: `pytest` — tests per service in `pmoves/tests/` (unit, smoke, integration, hardening) and inline `pmoves/services/<svc>/tests/`
 - Mock external systems (NATS, Supabase, Neo4j); validate with sample payloads
-- Run: `pytest -q pmoves/tests/unit/` or per-service paths
-- Local CI checks: `docs/LOCAL_CI_CHECKS.md`
-- Before pushing: run relevant smoke targets and document results in PR
+- Run a single service suite: `pytest -q pmoves/services/<svc>/tests/` — run under env: `bash pmoves/scripts/with-env.sh pytest pmoves/tests/unit/`
+- Full verification: `cd pmoves && make verify-all` (smoke + health). Targeted: `make -C pmoves smoke`, `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`, `make -C pmoves model-readiness`
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2434#discussion_r3730014152)

### 3. ✅ [P2] chatgpt-codex-connector — `AGENTS.md:29`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Map services to their actual bring-up targets**

For services whose canonical road is a grouped target, substituting the service name here fails; for example, Firefly is a Compose service but `make -C pmoves up-firefly` exits with “No rule to make target,” while its actual road is `make -C pmoves up-external`. Point readers to `make -C pmoves help` or provide the real service-to-target mapping instead of implying every Compose service has an `up-<svc>` rule.

AGENTS.md reference: [AGENTS.md:L22-L24](https://github.com/POWERFULMOVES/PMOVES.AI/blob/dfc540939fa297216a2edf211f006913e08ecfdb/AGENTS.md#L22-L24)

Useful? React with 👍 / 👎.

<details><summary>Diff context</summary>

```diff
@@ -15,6 +15,83 @@ PMOVES.AI is a modular AI agent platform organized as a **submodule monorepo**,
 - **`.claude/`** — Claude Code context, commands, hooks, MCP config
 - **Root** — `Makefile` (delegates to pmoves), `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`
 
+## Operating in This Repo (Non-Obvious Rules)
+
+These are the load-bearing conventions that are **not** obvious from reading a single file. Violating them has cost the fleet many hours. Full detail in [`.claude/PATTERNS.md`](.claude/PATTERNS.md) and [`.claude/BOOTSTRAP.md`](.claude/BOOTSTRAP.md).
+
+### Known Roads — dangerous ops go through Make targets
+
+Damage-control hooks block raw `docker`, `netsh`, `tailscale`, and `gh workflow` commands and redirect to an `ask` prompt. Every dangerous-but-necessary operation has a **canonical Make target** that bypasses the hook (it encapsulates the correct stop/restart/env-injection flow). When blocked, read the prompt — it names the target.
+
+| Raw command (blocked) | Known Road |
+|---|---|
+| `docker volume rm <svc>` | `make -C pmoves volume-reset SERVICE=<svc>` |
+| `docker compose up -d <svc>` | `make -C pmoves up-<svc>` |
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2434#discussion_r3730014164)

### 4. ✅ [unclassified] coderabbitai — `AGENTS.md:30`

_🩺 Stability & Availability_ | _🟠 Major_ | _⚡ Quick win_

<details>
<summary>🧩 Analysis chain</summary>

🏁 Script executed:

```shell
#!/usr/bin/env bash
set -euo pipefail

rg -n -C 4 '(^|[[:space:]])(restart|up(-[^:[:space:]]+)?|secrets-funnel):' \
  pmoves/Makefile pmoves/mk || true
rg -n -A12 '^up:' pmoves/Makefile
```

Repository: POWERFULMOVES/PMOVES.AI

Length of output: 50379

---

🏁 Script executed:

```shell
#!/usr/bin/env bash
set -euo pipefail

# Inspect the documented command table and related startup row in AGENTS.md.
sed -n '20,45p' AGENTS.md

# Locate any restart-specific Make targets or usage of compose restart.
rg -n --no-heading '(^|[[:space:]])(restart(:|$)|docker compose restart|compose restart|restart-target|SERVICE|svc)' AGENTS.md pmoves/Makefile
```

Repository: POWERFULMOVES/PMOVES.AI

Length of output: 2462

---

🏁 Script executed:

```shell
#!/usr/bin/env bash
set -euo pipefail

printf '--- PMOVES Makefile up target ---\n'
sed -n '1960,1976p' pmoves/Makefile

printf '\n--- PMOVES Makefile secrets-funnel target ---\n'
rg -n -A8 -B3 '^secrets-funnel:' pmoves/Makefile

printf '\n--- service-scoped up and restart-like targets ---\n'
rg -n '^up-[a-z0-9_-]+:[ ]*##|^restart[^-]|docker compose restart|$(DC) .* up -d' pmoves/Makefile | head -n 220
```

Repository: POWERFULMOVES/PMOVES.AI

Length of output: 252

---

🏁 Script executed:

```shell
#!/usr/bin/env bash
set -euo pipefail

echo '--- PMOVES Makefile up target ---'
sed -n '1960,1976p' pmoves/Makefile

echo
echo '--- PMOVES Makefile secrets-funnel target ---'
rg -n -A8 -B3 '^secrets-funnel:' pmoves/Makefile

echo
echo '--- service-scoped up and restart-like targets ---'
rg -n '^(up-[a-z0-9-]+:[ ]*##|restart[-_][^:]*:|^[^ ]+.*docker compose (restart|.* up -d)|^[^ ]+.*compose restart|DC).*' pmoves/Makefile | head -n 220
```

Repository: POWERFULMOVES/PMOVES.AI

Length of output: 1323

---



</details>

**Use the exact restart target for this raw command.**

`make -C pmoves secrets-funnel && ma

<details><summary>Diff context</summary>

```diff
@@ -15,6 +15,83 @@ PMOVES.AI is a modular AI agent platform organized as a **submodule monorepo**,
 - **`.claude/`** — Claude Code context, commands, hooks, MCP config
 - **Root** — `Makefile` (delegates to pmoves), `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`
 
+## Operating in This Repo (Non-Obvious Rules)
+
+These are the load-bearing conventions that are **not** obvious from reading a single file. Violating them has cost the fleet many hours. Full detail in [`.claude/PATTERNS.md`](.claude/PATTERNS.md) and [`.claude/BOOTSTRAP.md`](.claude/BOOTSTRAP.md).
+
+### Known Roads — dangerous ops go through Make targets
+
+Damage-control hooks block raw `docker`, `netsh`, `tailscale`, and `gh workflow` commands and redirect to an `ask` prompt. Every dangerous-but-necessary operation has a **canonical Make target** that bypasses the hook (it encapsulates the correct stop/restart/env-injection flow). When blocked, read the prompt — it names the target.
+
+| Raw command (blocked) | Known Road |
+|---|---|
+| `docker volume rm <svc>` | `make -C pmoves volume-reset SERVICE=<svc>` |
+| `docker compose up -d <svc>` | `make -C pmoves up-<svc>` |
+| `docker compose restart <svc>` | `make -C pmoves secrets-funnel && make -C pmoves up` |
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2434#discussion_r3730032264)

### 5. ✅ [unclassified] coderabbitai — `AGENTS.md:46`

_🎯 Functional Correctness_ | _🟡 Minor_ | _⚡ Quick win_

**Preserve the complete environment value.**

Line 46 uses `cut -d= -f2`. This truncates values that contain additional `=` characters. It also removes all quote characters. Use the canonical loader instead.

<details>
<summary>Proposed fix</summary>

```diff
-To extract a single variable from a shell snippet: `grep '^MY_VAR=' pmoves/env.shared | cut -d= -f2 | tr -d '"'`.
+To extract a single variable: `bash pmoves/scripts/with-env.sh bash -c 'printf "%s\n" "$MY_VAR"'`.
```

</details>

<!-- suggestion_start -->

<details>
<summary>📝 Committable suggestion</summary>

> ‼️ **IMPORTANT**
> Carefully review the code before committing. Ensure that it accurately replaces the highlighted code, contains no missing lines, and has no issues with indentation. Thoroughly test & benchmark the code to ensure it meets the requirements.

```suggestion
To extract a single variable: `bash pmoves/scripts/with-env.sh bash -c 'printf "%s\n" "$MY_VAR"'`.
```

</details>

<!-- suggestion_end -->

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@AGENTS.md` at line 46, Update the environment-variable extraction guidance
near the shell snippet to use the canonical loader instead of grep/cut/tr,
preserving values containing additional “=” characters and embedded quotes. Keep
the example focused on extracting the complete environment value.
```

</details>

<!-- fingerprinting:phantom:triton:caracal -->

<!-- cr-indicator-types:potential_issue -->

<!-- cr-comment:v1:d61a1da0c389a1d0502ddcc4 -->

<!-- This is an auto-generated comment by CodeRabbit -->

**Committable suggestion(s):**

```suggestion
To extract a single variable: `bash pmoves/scripts/with-env.sh bash -c 'printf "%s\n" "$MY_VAR"'`.
```

<details><summary>Diff context</summary>

```diff
@@ -15,6 +15,83 @@ PMOVES.AI is a modular AI agent platform organized as a **submodule monorepo**,
 - **`.claude/`** — Claude Code context, commands, hooks, MCP config
 - **Root** — `Makefile` (delegates to pmoves), `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`
 
+## Operating in This Repo (Non-Obvious Rules)
+
+These are the load-bearing conventions that are **not** obvious from reading a single file. Violating them has cost the fleet many hours. Full detail in [`.claude/PATTERNS.md`](.claude/PATTERNS.md) and [`.claude/BOOTSTRAP.md`](.claude/BOOTSTRAP.md).
+
+### Known Roads — dangerous ops go through Make targets
+
+Damage-control hooks block raw `docker`, `netsh`, `tailscale`, and `gh workflow` commands and redirect to an `ask` prompt. Every dangerous-but-necessary operation has a **canonical Make target** that bypasses the hook (it encapsulates the correct stop/restart/env-injection flow). When blocked, read the prompt — it names the target.
+
+| Raw command (blocked) | Known Road |
+|---|---|
+| `docker volume rm <svc>` | `make -C pmoves volume-reset SERVICE=<svc>` |
+| `docker compose up -d <svc>` | `make -C pmoves up-<svc>` |
+| `docker compose restart <svc>` | `make -C pmoves secrets-funnel && make -C pmoves up` |
+| `tailscale status` (leaks raw IPs) | `make -C pmoves fleet-status` |
+| `gh workflow run sync-secrets-local` | `make -C pmoves secrets-sync-trigger` |
+| raw `-f docker-compose.<overlay>.yml up` | `make -C pmoves overlay-up-<tier>` (see layering trap below) |
+
+Use raw commands **only** when the user explicitly directs.
+
+### `env.shared` is Docker `env_file` format, NOT bash
+
+Never `source pmoves/env.shared` — Windows paths and section headers will produce "command not found" errors and leave variables unset. Use the canonical loader:
+
+```bash
+bash pmoves/scripts/with-env.sh <command>          # run any command with env.shared loaded
+bash pmoves/scripts/with-env.sh pytest pmoves/tests/...  # pytest with service env
+```
+
+To extract a single variable from a shell snippet: `grep '^MY_VAR=' pmoves/env.shared | cut -d= -f2 | tr -d '"'`.
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2434#discussion_r3730032269)

### 6. ✅ [question] coderabbitai — `AGENTS.md:50`

_🎯 Functional Correctness_ | _🟠 Major_ | _⚡ Quick win_

<details>
<summary>🧩 Analysis chain</summary>

🏁 Script executed:

```shell
#!/usr/bin/env bash
set -euo pipefail

rg -n -C 3 'docker-compose\.base\.yml|overlay-up-' \
  pmoves/Makefile pmoves/mk pmoves/docker-compose*.yml || true
```

Repository: POWERFULMOVES/PMOVES.AI

Length of output: 16299

---

🏁 Script executed:

```shell
#!/usr/bin/env bash
set -euo pipefail

echo "AGENTS.md relevant section:"
sed -n '45,55p' AGENTS.md

echo
echo "Overlay files referencing networks/volumes defined in base:"
python3 - <<'PY'
from pathlib import Path
import re, yaml

base = yaml.safe_load(open("pmoves/docker-compose.base.yml"))
base_net = set(base.get("networks", {}) or {})
base_vol = set(base.get("volumes", {}) or [])
re_vol = re.compile(r"\b([a-zA-Z0-9_./-]+):([a-zA-Z0-9_./-]+)")

for path in sorted(Path("pmoves").glob("docker-compose.*.yml")):
    if path.name in {"docker-compose.base.yml","docker-compose.yml"}:
        continue
    data = yaml.safe_load(path.read_text())
    svc = data.get("services") or {}
    bad_net = []
    bad_vol = []
    for name, conf in svc.items():
        if not isinstance(conf, dict):
            continue
        nets = conf.get("networks") or []
        for n in nets:
            if isinstance(n, dict):
                for k in n:
                    if k not in base_net:
                        bad_net.append((name, k))
            elif n not in base_net:
                bad_net.append((name, n))
        for mount in conf.get("volumes") or []:
            if isinstance(mount, dict):
                vol = mount.get("source") or ""
            else:
                vol = re_vol.match(str(mount)).group(1) if re_vol.match(str(mount)) else ""
            if vol and vol not in base_vol:
                bad_vol.append((name, vol))
    if bad_net or bad_vol:
        print(path.name, "uses networks not in base:", sorted(set(n[1] for n in bad_net)), "uses volumes not in base:", sorted(set(v[1] fo

**Committable suggestion(s):**

```suggestion
The stack is split into `docker-compose.base.yml` (networks + anchors) + 6 tier overlays (`core` / `agents` / `media` / `ui` / `workers` / `apps`). Invoking `docker compose -f docker-compose.<overlay>.yml up -d` raw fails with `service "<svc>" refers to undefined network <name>` because the base layer is missing. Always use `make -C pmoves overlay-up-<tier>` (or `overlay-up-full`). Safe read-only validation: `docker compose -f pmoves/docker-compose.base.yml -f pmoves/docker-compose.<overlay>.yml config`. Full runbook: `pmoves/docs/operations/COMPOSE_LAYERING_RUNBOOK.md`.
```

<details><summary>Diff context</summary>

```diff
@@ -15,6 +15,83 @@ PMOVES.AI is a modular AI agent platform organized as a **submodule monorepo**,
 - **`.claude/`** — Claude Code context, commands, hooks, MCP config
 - **Root** — `Makefile` (delegates to pmoves), `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`
 
+## Operating in This Repo (Non-Obvious Rules)
+
+These are the load-bearing conventions that are **not** obvious from reading a single file. Violating them has cost the fleet many hours. Full detail in [`.claude/PATTERNS.md`](.claude/PATTERNS.md) and [`.claude/BOOTSTRAP.md`](.claude/BOOTSTRAP.md).
+
+### Known Roads — dangerous ops go through Make targets
+
+Damage-control hooks block raw `docker`, `netsh`, `tailscale`, and `gh workflow` commands and redirect to an `ask` prompt. Every dangerous-but-necessary operation has a **canonical Make target** that bypasses the hook (it encapsulates the correct stop/restart/env-injection flow). When blocked, read the prompt — it names the target.
+
+| Raw command (blocked) | Known Road |
+|---|---|
+| `docker volume rm <svc>` | `make -C pmoves volume-reset SERVICE=<svc>` |
+| `docker compose up -d <svc>` | `make -C pmoves up-<svc>` |
+| `docker compose restart <svc>` | `make -C pmoves secrets-funnel && make -C pmoves up` |
+| `tailscale status` (leaks raw IPs) | `make -C pmoves fleet-status` |
+| `gh workflow run sync-secrets-local` | `make -C pmoves secrets-sync-trigger` |
+| raw `-f docker-compose.<overlay>.yml up` | `make -C pmoves overlay-up-<tier>` (see layering trap below) |
+
+Use raw commands **only** when the user explicitly directs.
+
+### `env.shared` is Docker `env_file` format, NOT bash
+
+Never `source pmoves/env.shared` — Windows paths and section headers will produce "command not found" errors and leave variables unset. Use the canonical loader:
+
+```bash
+bash pmoves/scripts/with-env.sh <command>          # run any command with env.shared loaded
+bash pmoves/scripts/with-env.sh pytest pmoves/tests/...  # pytest with service env
+```
+
+To extract a single variable from a shell snippet: `grep '^MY_VAR=' pmoves/env.shared | cut -d= -f2 | tr -d '"'`.
+
+### Compose overlay layering — the single-file trap
+
+The stack is split into `docker-compose.base.yml` (networks + anchors) + 6 tier overlays (`core` / `agents` / `media` / `ui` / `workers` / `apps`). Invoking `docker compose -f docker-compose.<overlay>.yml up -d` raw fails with `service "<svc>" refers to undefined network <name>` because the base layer is missing. Always use `make -C pmoves overlay-up-<tier>` (or `overlay-up-full`). Safe read-only validation: `docker compose -f pmoves/docker-compose.<overlay>.yml config`. Full runbook: `pmoves/docs/operations/COMPOSE_LAYERING_RUNBOOK.md`.
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2434#discussion_r3730032296)

### 7. ✅ [unclassified] coderabbitai — `AGENTS.md:87`

_🗄️ Data Integrity & Integration_ | _🟠 Major_ | _⚡ Quick win_

<details>
<summary>🧩 Analysis chain</summary>

🏁 Script executed:

```shell
#!/usr/bin/env bash
set -euo pipefail

test -f .claude/context/nats-subjects.md
test -f .claude/context/services-catalog.md
rg -n 'agent\.peer\.heartbeat\.v1' .claude/context/nats-subjects.md
rg -n 'port|health|8080' .claude/context/services-catalog.md
```

Repository: POWERFULMOVES/PMOVES.AI

Length of output: 161

---

🏁 Script executed:

```shell
#!/usr/bin/env bash
set -euo pipefail

printf 'candidate files:\n'
git ls-files | rg '(^AGENTS\.md$|^\.claude(/context)?/(nats-subjects|services-catalog|CATALOG)\.md$)' || true

printf '\nAGAENTS excerpt:\n'
if [ -f AGENTS.md ]; then
  sed -n '70,90p' AGENTS.md
fi

printf '\n.search canonical NATS entries:\n'
rg -n 'agent\.peer\.heartbeat\.v1|NATS|nats-subjects|\.claude/context/nats-subjects\.md' . || true

printf '\n.search canonical services/catalog:\n'
rg -n 'services-catalog|CATALOG|8080|health|port' .claude . 2>/dev/null | head -n 120 || true
```

Repository: POWERFULMOVES/PMOVES.AI

Length of output: 50380

---

🏁 Script executed:

```shell
#!/usr/bin/env bash
set -euo pipefail

printf 'tracked relevant markdown files:\n'
git ls-files | rg '(^AGENTS\.md$|^\.claude/context/(nats-subjects|services-catalog)\.md$|^\.claude/CATALOG\.md$)' || true

printf '\nAGENTS.md lines 75-88:\n'
sed -n '75,88p' AGENTS.md

printf '\ncanonical NATS subject entries:\n'
for f in .claude/context/nats-subjects.md .claude/CATALOG.md; do
  if [ -f "$f" ]; then
    printf '%s\n' "$f"
    rg -n 'agent\.peer\.heartbeat\.v1|nats|NATS' "$f" | head -n 40 || true
  else
    printf '%s missing\n' "$f"
  fi
done

printf '\ncanonical services catalog port/health entries:\n'
for f in .claude/context/services-catalog.md .claude/CATALOG.md; do
  if [ -f "$f" ]; then
    printf '%s\n' "$f"
    rg -n 'port|health|8080|mcp|Agent Zero|services-catalog|CATALOG' "$f" | head -n 80 || true
  else
    printf '%s missing\n' "$

<details><summary>Diff context</summary>

```diff
@@ -15,6 +15,83 @@ PMOVES.AI is a modular AI agent platform organized as a **submodule monorepo**,
 - **`.claude/`** — Claude Code context, commands, hooks, MCP config
 - **Root** — `Makefile` (delegates to pmoves), `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`
 
+## Operating in This Repo (Non-Obvious Rules)
+
+These are the load-bearing conventions that are **not** obvious from reading a single file. Violating them has cost the fleet many hours. Full detail in [`.claude/PATTERNS.md`](.claude/PATTERNS.md) and [`.claude/BOOTSTRAP.md`](.claude/BOOTSTRAP.md).
+
+### Known Roads — dangerous ops go through Make targets
+
+Damage-control hooks block raw `docker`, `netsh`, `tailscale`, and `gh workflow` commands and redirect to an `ask` prompt. Every dangerous-but-necessary operation has a **canonical Make target** that bypasses the hook (it encapsulates the correct stop/restart/env-injection flow). When blocked, read the prompt — it names the target.
+
+| Raw command (blocked) | Known Road |
+|---|---|
+| `docker volume rm <svc>` | `make -C pmoves volume-reset SERVICE=<svc>` |
+| `docker compose up -d <svc>` | `make -C pmoves up-<svc>` |
+| `docker compose restart <svc>` | `make -C pmoves secrets-funnel && make -C pmoves up` |
+| `tailscale status` (leaks raw IPs) | `make -C pmoves fleet-status` |
+| `gh workflow run sync-secrets-local` | `make -C pmoves secrets-sync-trigger` |
+| raw `-f docker-compose.<overlay>.yml up` | `make -C pmoves overlay-up-<tier>` (see layering trap below) |
+
+Use raw commands **only** when the user explicitly directs.
+
+### `env.shared` is Docker `env_file` format, NOT bash
+
+Never `source pmoves/env.shared` — Windows paths and section headers will produce "command not found" errors and leave variables unset. Use the canonical loader:
+
+```bash
+bash pmoves/scripts/with-env.sh <command>          # run any command with env.shared loaded
+bash pmoves/scripts/with-env.sh pytest pmoves/tests/...  # pytest with service env
+```
+
+To extract a single variable from a shell snippet: `grep '^MY_VAR=' pmoves/env.shared | cut -d= -f2 | tr -d '"'`.
+
+### Compose overlay layering — the single-file trap
+
+The stack is split into `docker-compose.base.yml` (networks + anchors) + 6 tier overlays (`core` / `agents` / `media` / `ui` / `workers` / `apps`). Invoking `docker compose -f docker-compose.<overlay>.yml up -d` raw fails with `service "<svc>" refers to undefined network <name>` because the base layer is missing. Always use `make -C pmoves overlay-up-<tier>` (or `overlay-up-full`). Safe read-only validation: `docker compose -f pmoves/docker-compose.<overlay>.yml config`. Full runbook: `pmoves/docs/operations/COMPOSE_LAYERING_RUNBOOK.md`.
+
+### `secrets-funnel` is in `pmoves/mk/codex.mk`, not the root Makefile
+
+The canonical secrets pipeline is `make -C pmoves secrets-funnel`. It is defined in `pmoves/mk/codex.mk` (included by `pmoves/Makefile`); a grep of the root `Makefile` alone returns nothing. Before adding any secrets tooling, run `grep -rn 'secrets-funnel' pmoves/Makefile pmoves/mk/`. A duplicate funnel has been written twice by agents who skipped that check.
+
+### Three-Body / Village Rule (governance)
+
+No agent operates alone on production validation. Every lane follows **claim → work → sign → release** in [`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`](pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md) (the active claim register). Three bodies, enforced via Claude Code agent frontmatter in `.claude/agents/`: **Delivery** (edits code, `disallowedTools: EnterPlanMode`), **Control** (read-only review, `disallowedTools: Write, Edit, EnterPlanMode`), **Memory** (Cipher/CHIT only). When claiming a lane, write a `CLAIM` row with branch + scope + TTL; on completion write a `RELEASE` row and a signed ACK block.
+
+### CHIT trail signing
+
+After significant multi-file work, sign a provenance entry: `make -C pmoves sign-trail SUMMARY="..." AGENT=<id> PHASE="..."`. If `$CHIT_PASSPHRASE` is unset (common in dev), the payload emits **unsigned** with a stderr warning — that is expected and acceptable locally; still run it. Never hardcode passphrases.
+
+### Damage-control hook recovery
+
+If `patterns.yaml` ever carries unresolved merge-conflict markers, the Bash hook fails closed and blocks **all** Bash commands (you cannot even run `git status`). Recovery escape hatch: the **Edit tool** routes through a separate hook that does not depend on `patterns.yaml` parsing. Use Read + Edit to resolve the conflict markers; Bash resumes on the next call. `patterns.yaml` is intentionally not in `readOnlyPaths` so this path stays open — do not add it.
+
+### Node identity & cross-node state
+
+This is a multi-node fleet (Z890, 5090, 4090, SPARK, Knuckles, KVM4-1/2, KVM2, Jetsons). Per the MOF invariant (PR #1378), every node is a **pore in the lattice** — capacity-class, not expertise-lane. Always verify state locally before assuming; Claude's context is **not** consistent across nodes (different containers, worktrees, claim-register state may exist).
+
+```bash
+hostname            # which node am I on?
+git branch          # what branch?
+git worktree list   # am I in a worktree?
+make -C pmoves fleet-status   # fleet view (no raw tailscale status — it leaks IPs)
+```
+
+Cross-node delegation: Agent Zero `POST http://localhost:8080/mcp/*` (sync), A2A `/.well-known/agent-card.json` (disabled by default), NATS `agent.peer.heartbeat.v1` (Phase D, pending).
+
+### Progressively-disclosed context
+
+Don't dump everything into AGENTS.md. The tiered context map:
+
+| You want | Load |
+|---|---|
+| Service ports, URLs, health endpoints | [`.claude/CATALOG.md`](.claude/CATALOG.md) |
```

</details>

[→ thread](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2434#discussion_r3730032307)

