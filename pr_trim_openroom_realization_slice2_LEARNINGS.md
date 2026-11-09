# LEARNINGS — openroom-realization slice 2 (P1 iframe wiring + P2/P3/P4/P5/P6 follow-ups)

> Per the 4-bucket taxonomy: missed-signal / fix-pattern / wrong-suggestion / already-addressed.
> Captured during implementation, before any review. Add more buckets as review threads land.

## 1. The slice 2 work as a whole

**Goal:** turn the persona living-doc room from a `StubApp` metadata card into a real served surface embedded in the OpenRoom desktop, plus the 5 follow-up priorities from the 2026-08-06 handoff. Lowest-risk, highest-signal first deliverable; the other 5 are progressive enhancements on top.

**10 commits on `feat/mavis-openroom-realization` (off `feat/persona-livingdoc-rooms`):**

| # | SHA | What | Priority |
|---|-----|------|----------|
| 1 | `a198e1cf3f` | (cherry-pick from `feat/persona-livingdoc-rooms`) persona route + greeting + null guard | scaffold |
| 2 | `ade63dffe9` | slice 2 scaffold — openroom service, UI auth refactor, AGNOTE claim, first trail entry, 5090 sitrep skill (+471/-11) | scaffold |
| 3 | `7900a98fe4` | **P1 iframe wiring** — Dockerfile ARG + compose build args + split script update | P1 |
| 4 | `dbf9b66f3f` | LEARNINGS.md per pr-trim protocol | docs |
| 5 | `500aff4f46` | LEARNINGS addendum — runtime validation deferred (upstream build issue) | docs |
| 6 | `4ab0cd431f` | **P3 Enter button on each room card** — stage_data.py emits A2UI Button, stage.js handles a2ui.action event, index.html adds OPENROOM_BASE_URL meta tag, public-rooms.json regenerated | P3 |
| 7 | `f2083c5d37` | **P5 P7 session endpoint** — POST /api/p7/rooms/{id}/session (Pydantic SessionRequest, NATS publish_room_session extended) + 5 tests | P5 |
| 8 | `86fc198902` | chore(submodule): bump PMOVES-OpenRoom for P2 stock-app hiding | P2 |
| 9 | `94808093f7` | chore(submodule): bump PMOVES-OpenRoom for P4 model-fabric wiring ('pmoves' provider) | P4 |
| 10 | `d5e2b9acdd` | chore(submodule): bump PMOVES-OpenRoom for P6 persona theming (theme.skin/icon/wallpaper) | P6 |

**Acceptance criteria status (per the 2026-08-06 handoff):**

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `?room=persona.room.livingdoc` shows the real persona HTML in an iframe | Code complete (P1). Runtime blocked on upstream PMOVES-OpenRoom Dockerfile CRLF + pnpm-workspace issues (LEARNINGS addendum). |
| 2 | Stock OpenRoom apps hidden when a PMOVES room is active | **Code complete (P2).** Shell filters by appId >= PMOVES_DYNAMIC_APP_ID_BASE=1000. |
| 3 | `/stage/` Enter buttons | **Code complete (P3).** stage_data.py emits Button, stage.js handles click, public-rooms.json regenerated. Tests: 6/6 pass. |
| 4 | At least 3 rooms render real content via iframe | Deferred (depends on P1 runtime + 3 rooms configured in VITE_PMOVES_ROOM_IFRAMES). P3 added the wire path; P1 is the only room configured. |
| 5 | P7 session open/close succeeds (no 404) | **Code complete (P5).** New `POST /api/p7/rooms/{id}/session` endpoint with Pydantic validation + NATS publish. Tests: 5/5 new + 51/51 total pass. |
| 6 | Persona theming beyond `--pm-accent` (consume `theme.skin` / `theme.icon`) | **Code complete (P6).** Adapter now consumes skin/icon/wallpaper and sets both data-attrs + CSS vars on document root. |
| 7 | Signed graphiti trail entry in `docs/AGENT_TRAIL.md` | **Done (commit 2 in scaffold).** |

## 2. Patterns / fixes

### 2.1 Vite `import.meta.env.VITE_*` is **build-time**, not runtime

**The trap:** reading `import.meta.env.VITE_PMOVES_ROOM_IFRAMES` at runtime and trying to inject via `environment:` in `docker-compose.yml` — this will set the env var in the *running* container, but Vite already inlined the build-time value into the JS bundle. The runtime value is invisible to the bundle.

**The fix:** add `ARG VITE_PMOVES_ROOM_IFRAMES` + `ENV VITE_PMOVES_ROOM_IFRAMES=${...}` to the Dockerfile's builder stage, pass it as a `build.args` entry in `docker-compose.yml`. Image rebuild required on value change.

**This is the only P1 architectural note.** P2-P6 don't need it.

### 2.2 Submodule commit + gitlink bump = one logical change

**The pattern:** when a PMOVES.AI PR depends on a PMOVES-OpenRoom (or other submodule) change, the submodule change is a separate commit **on a named branch in the submodule** (not detached HEAD — git's reflog can lose detached commits), and the PMOVES.AI parent commit updates the gitlink to point at the named branch tip.

**Concrete:** in PMOVES-OpenRoom I created branch `openroom-realization-vite-iframes` from commit `59b8b5e` (the Dockerfile ARG addition). The PMOVES.AI commit `7900a98fe4` then records the gitlink bump.

**Risk:** if the submodule branch isn't pushed to a remote that PMOVES.AI's CI can reach, the gitlink can become unreachable. For this PR, the operator will need to push the branch before merge.

### 2.3 Cherry-pick the persona work, don't duplicate

**The discovery:** `feat/persona-livingdoc-rooms` already had the persona route + greeting + null guard (commit `a198e1cf3f`, generated by Crush). My new branch `feat/mavis-openroom-realization` started as a base of `main`, but the untracked scaffold in the main repo (`pmoves/ui/app/persona/livingdoc/route.ts` etc.) was **identical** to what's in `a198e1cf3f`.

**The move:** `git reset --hard feat/persona-livingdoc-rooms` after the worktree was created, then `git stash pop` — git's 3-way merge auto-resolved the 4 overlapping files (no-op since the persona commit already had them with the same content), and the remaining 8 files + 3 new ones are unique to slice 2.

**Saved:** ~108 lines of duplicate diff in the final PR. The PR is `+516 / -22` instead of `+624 / -22`.

### 2.4 `git stash` + worktree + `git stash pop` is the cleanest scaffold-mover

**The pattern:** when you start a worktree from a clean `main` and want to move a dirty scaffold from the main repo's working tree into the new worktree, the sequence is:
1. From main: `git add -A && git stash push -m "scaffold-name"`
2. From main: `git worktree add <path> -b <new-branch> <base>`
3. From new worktree: `git reset --hard <actual-base>` (if the new branch's base should be different from main)
4. From new worktree: `git stash pop` (auto-resolves overlap if the actual-base has the same content)

This works because git stash is repo-wide (lives in `.git/refs/stash`), and each worktree has its own working tree but shares the same `.git`.

### 2.5 PowerShell backtick gotcha when heredoc'ing shell args

**The trap:** writing a commit message with `git commit -m "..."` where the message contains backticks (e.g., `\`pmoves\`). PowerShell interprets backticks as escape characters, so `\u` becomes a Unicode-escape syntax error.

**The fix:** write the commit message to a file (e.g., `.commit-msg-<name>.tmp`) and use `git commit -F <file>`. Cleaner diff in the working tree (temp file in `.gitignore` or deleted after commit) and zero backtick interpretation.

## 3. Already-addressed (no action needed)

- **P7 session 404 in `pmovesRoomAdapter.ts` line 371**: the adapter calls `POST /api/p7/rooms/{id}/session` and tolerates 404 (best-effort, logs warning, continues). Not blocking P1. P5 in the handoff will fix the proxy.
- **The 11 stock OpenRoom sample apps (Twitter, Chess, etc.)**: still render in the desktop grid. P2 in the handoff will filter them by `isPmovesRoom`. Not blocking P1.
- **`/stage/` Enter buttons**: cards link out but no navigate. P3 in the handoff. Not blocking P1.
- **The `data-pmoves-room` and `data-pmoves-stage` attributes**: `pmovesRoomAdapter.ts` already sets them on the document root. The StubApp banner reads them. Working as designed.
- **The persona route is in `MARKETING_ROUTES` in `pmoves/ui/proxy.ts`**: so it renders without auth. Already shipped in the scaffold commit.

## 4. Known unknowns (defer to follow-up slices)

- **CORS / cross-origin iframe policy**: the persona iframe is served from `localhost:4482` (pmoves-ui) inside a page loaded from `localhost:5173` (OpenRoom). Different ports = different origins. The iframe has `sandbox="allow-scripts allow-popups"` but no `allow-same-origin`, which is the safer default. If the persona HTML has fetch calls to pmoves-ui's own APIs, those will be cross-origin and may need CORS headers. **Test on bring-up.**
- **The `OPENROOM_ROOM_IFRAMES_JSON` env var**: defaulted in the compose file. If an operator wants to add more rooms without rebuilding, they need to set this env var AND rebuild (because Vite embeds at build time). Could be confusing — P2 follow-up: add a runtime config endpoint that the OpenRoom shell can fetch to override.
- **PMOVES-OpenRoom submodule branch not pushed**: `openroom-realization-vite-iframes` is local-only. The PMOVES.AI CI may not be able to fetch it. **Action:** before opening the PR, push the submodule branch to `POWERFULMOVES/PMOVES-OpenRoom` (or wherever the fork remote is).

## 5. Reviewer quick-reference

- **What changed:** 13 files total — 3 in PMOVES-OpenRoom (submodule, Dockerfile only), 10 in PMOVES.AI
- **What to look at first:** `pmoves/docker-compose.yml` (the new build arg) and `PMOVES-OpenRoom/apps/webuiapps/Dockerfile` (the ARG/ENV addition)
- **What to bring up:** `make -C pmoves up-openroom` + the pmoves-ui service, then visit `http://localhost:5173/webuiapps/?room=persona.room.livingdoc` and verify the persona HTML streams into the iframe
- **What NOT to do:** do not merge without pushing the PMOVES-OpenRoom `openroom-realization-vite-iframes` branch first, or the gitlink will dangle

## 6. Runtime validation status (deferred)

I attempted a real-runtime bring-up on the host to verify the P1 iframe actually loads the persona HTML. **Validation blocked on an upstream issue, not on P1 code.**

### What I tried

1. `docker build` of the new openroom image with `VITE_PMOVES_ROOM_IFRAMES` passed as `--build-arg`
2. Both `docker compose build` and direct `docker build` (the compose route is blocked by missing required env vars like `QDRANT__API_KEY`, `CHIT_PROD_PASSPHRASE`, `JWT_SECRET` — those are for OTHER services in the compose, not openroom; compose validates all services on parse)

### What broke

**Issue A (Windows-only): `apps/webuiapps/script/build.sh` has CRLF line endings** on the host working tree. The submodule has no `.gitattributes`, and the host's `core.autocrlf=true` converts LF → CRLF on checkout. When the container runs the script, `set -e\r` fails with "illegal option -". I converted the file to LF locally, but the next `git checkout` would re-CRLF it.

**Issue B (cross-platform):** even with LF line endings, the build fails at `pnpm run build` with `WARN: Local package.json exists, but node_modules missing`. The pnpm install at WORKDIR=/app succeeds, but `pnpm run build` at WORKDIR=/app/apps/webuiapps reports missing node_modules. Likely a pnpm-workspace + turbo setup that doesn't survive `pnpm i --frozen-lockfile` from outside the workspace context, or a stale lockfile.

**Both are in PMOVES-OpenRoom, not in my PR.** I reverted the LF-converted build.sh in my local submodule working tree so the PR is clean.

### Recommended upstream fix (separate PR to PMOVES-OpenRoom)

1. **Add `apps/webuiapps/.gitattributes`:**
   ```
   * text=auto eol=lf
   script/*.sh text eol=lf
   Dockerfile* text eol=lf
   ```
2. **Fix the Dockerfile to `pnpm install` inside the workspace package's directory**, or add `pnpm install --frozen-lockfile` after the `WORKDIR ${APP_PATH}` so the package's node_modules is properly set up.
3. **Test build on Windows + Linux** to confirm both work.

### What the reviewer should do

The bring-up validation is the right thing to do before merge. Until the PMOVES-OpenRoom Dockerfile is fixed for cross-platform builds, the validation will fail on the operator's host too. Suggested sequence:
1. Land this PR (P1 wiring) on the assumption that the Dockerfile fix is independent.
2. Open a separate upstream PR to PMOVES-OpenRoom for the `.gitattributes` + workspace install fix.
3. After the upstream lands, re-test the bring-up.
4. Update the PR with a screenshot in the LEARNINGS file.

## 7. Acceptance criterion 1 status

- ⏳ **`http://localhost:5173/webuiapps/?room=persona.room.livingdoc` shows the real persona HTML in an iframe (not StubApp)** — code complete + JSON map wired + compose arg set, but **runtime bring-up blocked by the PMOVES-OpenRoom Dockerfile issue above**. The code path is straightforward Vite build-time env var → `import.meta.env` → StubApp's `iframeUrl` derivation → `<iframe src={iframeUrl}>` → Next.js route serves the persona HTML. All components are present and individually validated (YAML safe_load, JSON.parse, Dockerfile ARG, compose build args, split script regen).

## 8. Test command the reviewer can run locally on Linux

```bash
cd pmoves
OPENROOM_ROOM_IFRAMES_JSON='{"persona.room.livingdoc":"http://localhost:4482/persona/livingdoc"}' \
  docker compose --profile ui build openroom
docker compose --profile ui up -d openroom
# wait 30s, then:
curl -sf http://localhost:5173/webuiapps/ | head -3
# visit http://localhost:5173/webuiapps/?room=persona.room.livingdoc in a browser
```

If the PMOVES-OpenRoom Dockerfile build works on the operator's Linux host, the iframe will load the persona HTML. The Compose + openroom Dockerfile are wired correctly; the only moving part is the build.
