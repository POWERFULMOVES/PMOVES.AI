# WS2 Tooling Audit — 4090 handoff

**From:** z890-claude (coordination plan, 2026-08-08)
**To:** 4090-claude (field) — assigned by node affinity
**Status:** claimed, in progress
**Base for all verification:** `origin/main` @ `22c78fbca`

z890's coordination plan splits post-backlog cleanup four ways and hands Workstream 2 to this node. This doc is the working surface for WS2: the corrected drift list, what ships, and what deliberately does not.

Evidence here comes from three sources with three provenances, kept distinct on purpose: **repository content** from `origin/main` via `git show`; **CI behavior** from Actions run records via `gh api`; **node runtime state** from `docker inspect` / `git submodule status` on this node only. See [Method](#method) — the first pass conflated the first of those with the working tree and produced two wrong answers.

---

## Corrections to the enumeration

**WS2 enumerates five items; 4090 claims four of them (items 2–5).** Item 1 is z890's and is not reserved here. Five entries below adjust the handed-over list — recorded before the fix rather than inside it, because they change the shape of the work.

### 1. It is 2 leaking copies, not 4 drifting implementations

The plan describes cleanup logic existing "in 4 places, drifting," with the two shell scripts carrying the #2473 buildx fix. Verified on `origin/main`:

| Location | `buildx rm --all-inactive`? |
|---|---|
| `pmoves/scripts/pmoves-disk-cleanup.sh:52` | ✅ present |
| `deploy/provision/docker-fleet-cleanup.sh:43` | ✅ present |
| `pmoves/mk/infra.mk:89` (`docker-prune-all`) | ❌ **absent — still leaks** |
| `.claude/skills/ci-expedition/SKILL.md:69` | ❌ **absent — still leaks** |

The two shell scripts are already coherent with each other. The drift is that the Make target and the skill's runner-hygiene block never received the fix. Consolidation is still worth doing, but the urgency sits on the two unfixed copies, not on all four.

`infra.mk` is z890's declared sub-fix and **4090 is not touching it**. The `SKILL.md:69` copy ships with WS2 item 2 because it lives in the same file as the other skill error.

### 2. The "13 of 15" figure was wrong — 7 is correct

4090 reported "13 of 15 fork-building compose services can't build from a worktree" in an earlier session. That number double-counted services re-declared across the generated split overlays. Corrected:

**7 unique sibling-context builds** in `pmoves/docker-compose.yml`:

```text
transcribe-backend      ../PMOVES-transcribe-and-fetch
transcribe-frontend     ../PMOVES-transcribe-and-fetch
pmoves-yt               ../PMOVES.YT
archon                  ../PMOVES-Archon
cipher-api              ../Pmoves-cipher
openroom                ../PMOVES-OpenRoom
llama-throughput-lab    ../PMOVES-llama-throughput-lab
```

The overlays re-declare exactly those seven (`agents` 2 + `apps` 1 + `media` 3 + `ui` 1 = 7), which is where the inflation came from.

Add to the enumeration:
- `docker-compose.n8n.yml` — `n8n` from `../PMOVES-n8n` (z890 already flagged this); also re-declared in `compose/docker-compose.core.yml`
- `docker-compose.archon.submodule.yml` — same `archon`, separate file

**Retracted:** an earlier revision of this doc added `hf-mcp-server.yml` to the list. That was wrong. Its context is `../../pmoves/services/hf-mcp-server` — a two-level relative path back *into* `pmoves/services/`, i.e. a first-party service, not a submodule. A `context: ../` prefix is not sufficient to identify a submodule build; the first path segment has to be matched against `.gitmodules`.

So: **7 registered submodules, 8 services.** Jellyfin correctly excluded — local build.

### The class the enumeration missed entirely: bind mounts

Build contexts are only half of it, and the less dangerous half. Five **bind-mount sources** also come from submodules:

| Source | Mounted by | Kind |
|---|---|---|
| `../PMOVES-supabase/docker/volumes/logs/vector.yml` | `supabase-vector` | **file** |
| `../PMOVES-supabase/docker/volumes/functions` | `supabase-edge-functions` | directory |
| `../PMOVES-supabase/docker/volumes/api/kong.yml` | `supabase-kong` | **file** |
| `../PMOVES-supabase/docker/volumes/api/kong-entrypoint.sh` | `supabase-kong` | **file** |
| `../PMOVES-n8n/workflows` | `n8n` | directory |

A missing build context fails loudly. A missing bind source does not: **Docker creates it as a directory**, so a file mount silently becomes a directory mount and the container fails on its own config instead. That is the class that took down services on this node, and it is why item 4 is a runbook rather than a code fix.

### 3. The ci-expedition correction is narrower than stated

`SKILL.md:29` currently reads:

> workflow **uncompilable on default branch** (GitHub uses default-branch file for `issue_comment`/`pull_request_review`/push)

`issue_comment` is **correct**. The other two are wrong in different ways, so the row became a table rather than a patched parenthetical:

| Event | Workflow file comes from |
|---|---|
| `issue_comment` | default branch, always |
| `push` | the **pushed ref** — default branch only when that is what was pushed |
| `pull_request`, `pull_request_review` | PR head / merge ref |

The `pull_request_review` half is empirical (see below). The `push` half came from Codex on #2483 and is Actions semantics — stated as behavior, not as something measured here. My first attempt at this fix removed only `pull_request_review` and left the `push` error standing.

### 4. The `.worktrees/*` skill copies are not a reconciliation problem

The plan lists the skill as "duplicated into 4 `.claude/worktrees/agent-*` copies → correct canonical + reconcile copies." Those paths are worktree checkouts of the same git-tracked file (`.claude/skills/ci-expedition/SKILL.md` is in `git ls-tree origin/main`). Fixing it on `main` fixes every worktree that rebases. No separate reconciliation step is needed — one item off the list.

### 5. `up-*` count confirmed: 89

82 in `pmoves/Makefile`, plus `egress.mk` 1, `infra.mk` 3, `yt-cookies.mk` 3. The plan's "~90" was accurate.

---

## Evidence for the `pull_request_review` correction

The skill's claim was disproven empirically during the #2479 fix, not reasoned about:

| Run | PR head | Workflow that ran | Result |
|---|---|---|---|
| `31257145963` | `5d0e3d379` — pre-fix, while `main` already had the fix | **old** (`token / mint` + `collect` jobs) | failed at checkout |
| `31257247543` | rebased onto `main`, so head carried the fix | **new** (single `collect` job) | ✅ green |

If `pull_request_review` resolved from the default branch, run `31257145963` would have used the fixed workflow. It did not. The trigger resolves from the PR head/merge ref, like `pull_request`.

This matters operationally: the wrong row sends the next `startup_failure` triage to validate the default-branch file when the fault is on the PR head.

---

## What ships

Each item is its own PR, one concern each.

| # | Item | Shape |
|---|---|---|
| 1 | `infra.mk` buildx leak | **z890's** — 4090 does not touch it |
| 2 | ci-expedition skill: line 29 trigger error, line 69 buildx leak, new `_app-token` row | code fix |
| 3 | The two `claude-pmoves.sh` — **not duplicates**, see below | delegate, delete nothing |
| 4 | Sibling-submodule build gap | **runbook, not a code fix** |
| 5 | `up-*` sprawl | **inventory only** — no Makefile edits |

### Why item 4 is a runbook

The gap is a runtime-topology property, invisible in any diff. **Corrected on review:** an earlier revision said CI is blind because the workflows check out with `submodules: recursive`. They do not check out submodules at all (`validate-dockerfile-paths-ratchet.yml:54`, `validate-composes-ratchet.yml:41`). They pass because `validate_dockerfile_paths.py` **deliberately excludes** sibling-submodule targets — "external repos the ratchet can't statically check" — and because `validate-composes` never inspects bind sources. A known, accepted blind spot rather than an accidental one, which is a better argument for the runbook, not a worse one.

It is not theoretical — it took down services on this node on 2026-08-08:

28 of 33 running containers were launched from a second clone (`GitHub/POWERFULMOVES/PMOVES.AI`) whose **57 submodules were all unpopulated**. Docker auto-created the missing bind sources as empty directories, so `PMOVES-supabase/docker/volumes/logs/vector.yml` existed as a *directory*. `supabase-vector` crash-looped 78 times with `Configuration error. error=Is a directory (os error 21)`; `supabase-edge-functions` failed with `could not find an appropriate entrypoint`.

The diagnostic worth writing down: **a bind-mount source that is a directory where a file is expected means the submodule was unpopulated when `up` ran.** Fix requires clearing Docker's stub directories first — they make the submodule dir non-empty, so `git submodule update --init` refuses to clone.

### Why item 3 does not "pick the authoritative one"

The item was enumerated as *"two divergent `claude-pmoves.sh` — pick the authoritative one."* Reading both first: **they were never duplicates.** They share a name and do different, mutually exclusive things.

| | `pmoves/scripts/` (642 B) | `deploy/provision/` (6523 B) |
|---|---|---|
| loads the shared env file | no | yes |
| passes `--mcp-config=<roster>` | no | yes |
| selects `--agent` | yes | no |

Each ends in its own `exec claude`, so you could have a PMOVES agent **or** working MCP creds, never both. `make -C pmoves claude-pmoves` (`Makefile:4936`) calls the agent-selecting one — so the documented way to launch the delivery agent came up with every cred-dependent MCP empty, which is precisely the failure the provisioning script's header says it exists to prevent.

Picking one and deleting the other would have removed a working capability either way. The fix is delegation: the shorthand forwards `--agent` into the real launcher and inherits creds. Nothing deleted, neither UI changed.

Worth correcting in the enumeration so the next reader does not retry the delete.

### Why item 5 is inventory-only

Operator decision. "Zero textual references" cannot prove a target is unused — it may be one someone types weekly. The deliverable is a grouped, referenced-vs-orphaned inventory with a proposed retire list; the operator picks what dies. `up-cipher-nobuild` is a known keeper regardless: it is the existing workaround for the item-4 build gap.

---

## For z890's WS3 list

The plan names KIMI-SPARK VSS and CRUSH cipher Phase B as the stale claims needing a release-or-reclaim ping. Two Mavis-5090 claims belong on that list but in a **different category** — merged work missing only a RELEASE line, per the #2465 verification sweep. They need a release, not a re-claim:

```text
Mavis-5090 — release-or-reclaim:
  creative-pipeline v0   verified merged (#2450)
  OpenRoom slice 2       verified merged (#2437)

  Both entries were destroyed by #2450's stale-base merge
  and restored in #2478 — read the restored text before
  releasing; it is the pre-loss version, not a rewrite.
```

**WS4-B owner should be Mavis-5090.** Living docs → mesh-backed, realtime, multi-portal sits on their persona-canvas affinity, and the "rooms pull portals" model is their OpenRoom slice-2 claim. Assigning it elsewhere collides with a live claim.

**WS4-A caveat:** `pmoves/data/beats/soundcloud/darkxside/` feeds the beats/BPM voice pipeline. It should move with voice-side agreement, not as part of a bulk binary sweep.

---

## Related finding: the register has no protection against stale-base overwrites

Surfaced while fixing something else, relevant to WS3. `AGNOTE4482PHI.t1.md` was damaged three times in a row by merges from stale bases:

- **#2437** committed raw `<<<<<<< HEAD` conflict markers into it (fixed in #2476)
- **#2450** replaced an 82-line region with 14 lines — deleting **six entries**, including two that had merged 8 and 36 minutes earlier (restored in #2478)
- The duplicate entry #2450 added was itself corrupted (`feat/` → `eat/`, `render_skin.py` → `ender_skin.py`)

A deletion is a valid diff, so nothing catches it. This is the `feedback_rebase_before_merge` rule failing in practice on the one file every agent reads before claiming. Worth considering a structural check — an append-only assertion, or a GRAPHITI_MARK count that must not decrease — but that is a WS3 call, not a WS2 deliverable.

---

## Method

Verify against `origin/main`, never the working tree. The local tree on this node sits on a feature branch and is stale enough to produce false negatives — the first pass of this audit reported `pmoves/scripts/pmoves-disk-cleanup.sh` as **missing** and `docker-fleet-cleanup.sh` as **lacking** the #2473 fix. Both were wrong; both files are correct on `origin/main`.

On Windows, `git show "origin/main:path"` requires `MSYS_NO_PATHCONV=1`. Without it, path conversion silently rewrites `origin/main:.claude/...` to `origin\main;.claude\...` and git reports:

```text
fatal: ambiguous argument 'origin\main;.claude\skills\...': unknown revision or path not in the working tree
```

which reads like the file does not exist rather than like a quoting problem.
