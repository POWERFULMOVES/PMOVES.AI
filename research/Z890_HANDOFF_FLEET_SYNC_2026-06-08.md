# Z890 Handoff — Fleet Fork Sync (2026-06-08)

Handoff from 4090-claude. The fork→upstream sync pipeline is **fixed, automated, and
documented**; what remains is the manual-merge tail + a branch-consistency decision.
Run the **`fleet-fork-sync`** skill — it's the step-by-step playbook. Companion:
`pmoves/docs/operations/GITHUB_APP.md`, `research/SUBMODULE_SYNC_AUDIT_2026-06-07.md`,
memory `reference_github_app_fleet_sync`.

## Done (4090)
- fork-sync.yml rebuilt: local-git merge, `.gitmodules`-tracked-branch targeting, App
  token scoped, CRITICAL skip-guard (PRs #1733/#1735/#1736/#1738/#1739/#1741).
- Reusable `_app-token.yml` (#1737); `fleet-fork-sync` skill (#1743).
- Synced + gitlink-promoted (clean FF): **Headscale** (#1740), **a0-plugins, E2b-Spells**
  (#1742), **AgentGym, E2B-DR-Desktop, Archon×2** (#1744, archon Trivy green).
- Manual CRITICAL merges done: **Archon** (PMOVES-Archon#17, merged + gitlink promoted),
  **Open-Notebook** (PMOVES-Open-Notebook#15, open — merge + promote gitlink).

## ⚠️ Decision needed: fork default branch vs gitlink-tracked branch

**The concern:** some forks default to `main`, some to `PMOVES.AI-Edition-Hardened`,
and the PMOVES.AI gitlink (`.gitmodules` `branch`) doesn't always match the fork default.

**Data (2026-06-08):**

| Consistent (default == gitlink-tracked) | Mismatched (default ≠ tracked) |
|---|---|
| ClawZ, headscale, E2B-Danger-Room, BotZ-gateway, e2b-mcp (all main/main); Creator, Wealth, Archon, Open-Notebook, Agent-Zero, Health-wger (all hardened/hardened) | **supabase** (default=`master`, tracked=hardened); **tensorzero, a0-plugins, A2UI, E2b-Spells, E2B-DR-Desktop, hyperdimensions, llama-throughput-lab, Pinokio-TTS, AgentGym** (default=`main`, tracked=hardened) |

**Recommended standard (4090 proposal — review/ratify):**
1. **`.gitmodules` `branch` = the consumed line = source of truth.** Hardened-overlay forks
   track `PMOVES.AI-Edition-Hardened`; pristine-mirror forks track `main`. Do NOT change a
   gitlink branch casually — it changes what PMOVES.AI builds.
2. **Set each fork's GitHub default branch = its gitlink-tracked branch.** Fixes the 10
   mismatches (→ default `PMOVES.AI-Edition-Hardened`) + supabase's odd `master`. Then
   clones, PR bases, fork-sync, and the gitlink all point at the same branch — no more
   `diverged` surprises.
3. **Two-branch model per hardened fork:** `main` = pristine upstream mirror (handy clean
   re-sync base), `PMOVES.AI-Edition-Hardened` = main + PMOVES overlay = consumed + default.

**Why this is safe (the "doesn't break the app" check):** all automation now uses explicit
refs — fork-sync reads `.gitmodules`; GHCR builds clone by gitlink SHA; drift compares
named branches. Changing the GitHub *default* only affects bare `git clone`/new-PR base.
**Audit before flipping:** grep the org for scripts that `git clone` a fork and assume
`main` content (none known in PMOVES.AI CI). Flip via repo Settings → Branches, or
`gh api -X PATCH repos/POWERFULMOVES/<fork> -f default_branch=PMOVES.AI-Edition-Hardened`.

## Z890 work queue

### A. Manual CRITICAL merges (use `fleet-fork-sync` skill § Step 4)
Each: clone tracked branch, merge upstream's **active** branch (check it — not always `main`),
resolve conflicts (lockfiles → regenerate), 2-parent merge, PR. Then promote gitlink (clean
FF after PR merges). Conflicts are usually few (Archon=1, Open-Notebook=5).

| Fork | drift (behind/ahead) | upstream | notes |
|---|---|---|---|
| PMOVES-supabase | 2177 / 9 | supabase/supabase | huge; default is `master` (fix per §2) |
| PMOVES-Creator | 1201 / 12 | Comfy-Org/ComfyUI | huge |
| PMOVES-ClawZ | 7959 / 9 | openclaw/openclaw | huge |
| PMOVES-Wealth | 790 / 28 | firefly-iii/firefly-iii | high-ahead |
| PMOVES-Agent-Zero | 116 / 34 | agent0ai/agent-zero | high-ahead; core service |
| Pmoves-hyperdimensions | 7 / 35 | MaxRobinsonTheGreat/hyperdimensions | very high-ahead |
| PMOVES-tensorzero | 958 / 10 | tensorzero/tensorzero | |
| PMOVES-A2UI | 479 / 8 | google/A2UI | |
| Pmoves-Health-wger | 646 / 9 | wger-project/wger | |
| PMOVES-BotZ-gateway | 7 / 7 | microsoft/mcp-gateway | small but conflicts |
| PMOVES-Pinokio-Ultimate-TTS-Studio | 5 / 7 | pinokiofactory/Ultimate-TTS-Studio | small but conflicts |

After each fork PR merges → promote its PMOVES.AI gitlink (`git update-index --cacheinfo
160000,<sha>,<path>`, FF-check first) → for image-built services (supabase, agent-zero) the
promotion PR's Trivy is the CVE gate.

### B. Open PRs to review/merge
- **PMOVES-Open-Notebook #15** (4090's full sync) — review, merge, promote gitlink. **Close #14** (superseded dep-only sync).
- **PMOVES.AI #1725** (SPARK: track fork registry + archive `fork_sync.py`) — **reconcile with the new `fork-sync.yml`**; ensure the fork registry aligns with `.gitmodules`-driven branch resolution (don't reintroduce the default-branch sync).
- PMOVES.AI #1699, #1696 (dependabot uv/pip bumps) — routine.
- PMOVES.AI #1705 (DARKXSIDE sidecar), #1697 (CHIT visual tour), #1662 (marketing copy) — owner review.

### C. Optional: ratify + apply §2 (set fork defaults = gitlink-tracked)
Once ratified, flip the 10 mismatched fork defaults to `PMOVES.AI-Edition-Hardened` (+ supabase off `master`).
