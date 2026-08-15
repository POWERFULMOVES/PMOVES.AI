# OpenRoom rooms bring-up — three defects between `up-openroom` and a running room

**Date:** 2026-08-14
**From:** 4090 (field)
**Status:** two PRs open on the fork, one blocked on a protected-file grant
**Scope:** why `make -C pmoves up-openroom` cannot produce a running rooms surface on a Windows fleet node, and what each fix does and does not cover.

Every claim below was measured on this node. Where a claim was published and later found wrong, the correction is recorded rather than edited away.

---

## Summary

`up-openroom` is the correct Known Road and it is not the problem. Three independent defects sit between it and a running container. Each one masks the next, so fixing any one alone changes the error rather than producing a room.

| # | Defect | Fix | Sufficient alone? |
|---|---|---|---|
| 1 | Pin references a commit off its declared branch | [PMOVES-OpenRoom#3](https://github.com/POWERFULMOVES/PMOVES-OpenRoom/pull/3) | no |
| 2 | `build.sh` ships CRLF; unparseable on Windows checkouts | [PMOVES-OpenRoom#4](https://github.com/POWERFULMOVES/PMOVES-OpenRoom/pull/4) | no |
| 3 | `NODE_ENV=production` strips the build toolchain; `\|\| true` hides the resulting exit 1 | this brief | no |

---

## 1. The pin is not on the branch it declares

`PMOVES.AI/.gitmodules` declares:

```
path = PMOVES-OpenRoom
branch = PMOVES.AI-Edition-Hardened
```

`origin/main` pins `ec57368`, which exists **only** on `openroom-realization-vite-iframes`. The pinned commit is not an ancestor of its own declared branch.

`ignore = all` on the submodule entry keeps this out of `git status`, so nothing surfaced it. (See `feedback_git_silent_false_negatives` — `ignore = all` hiding submodule state is a recurring source of silent wrongness here.)

**Measured:**

```
$ git rev-list --left-right --count hardened...vite-iframes
hardened-only: 0    vite-iframes-only: 4

$ git merge-base --is-ancestor hardened vite-iframes
(exit 0 — strict ancestor)
```

Hardened has nothing vite-iframes lacks, so this is a fast-forward with no possible conflict.

**Why fast-forward rather than repointing `.gitmodules`:** after the merge, the hardened tip **==** `ec57368` **==** what PMOVES.AI already pins. The declared branch and the pinned commit agree and **PMOVES.AI needs no gitlink change at all**. Repointing `.gitmodules` at a feature branch would instead leave the fork's default branch permanently behind what the monorepo builds.

---

## 2. CRLF makes the build script unparseable

```
 > [builder 7/7] RUN sh ./script/build.sh production:
0.296 ./script/build.sh: line 2: : not found
0.296 ./script/build.sh: set: line 3: illegal option -
exit code: 2
```

`apps/webuiapps/script/build.sh` is checked out with CRLF on any Windows clone with `core.autocrlf=true` — the git-for-windows default. The trailing `\r` joins each token, so `set -e` parses as `set -e\r`.

The fork has **no `.gitattributes` at all**, so nothing pins line endings.

**Why CI never caught it:** Linux and macOS checkouts are unaffected. GHCR builds green, every Linux node builds green. The failure is only reachable from a Windows fleet node, which is not where the signal is read.

Fix adds `*.sh`, `Dockerfile*`, `*.bash` as `text eol=lf`.

**Limit of the fix:** it moves the failure from exit 2 to exit 1. The script parses and runs — which is all a line-endings fix should do. The build still does not complete.

Existing Windows checkouts must re-normalise or re-clone; `.gitattributes` governs checkout and does not retroactively fix files on disk.

---

## 3. The build toolchain is never installed

**Root cause.** `apps/webuiapps/Dockerfile` sets `ENV NODE_ENV=${ENV}` at line 7 and installs at line 22, so the install runs with `NODE_ENV=production` already in effect. pnpm honours that by skipping **devDependencies** — where both `vite` and `husky` live in the root package.

The root `prepare` lifecycle script runs `husky install`, husky is absent, and the install fails:

```
$ docker run -e NODE_ENV=production node:20-alpine     # matches the builder
$ pnpm i --frozen-lockfile
PNPM_EXIT=1
. prepare$ husky install
. prepare: sh: husky: not found
 ELIFECYCLE  Command failed.
RESULT: vite ABSENT
```

That exit 1 was covered by a trailing `|| true` spanning the whole `&&` chain, so the layer reported success and the real error surfaced two steps later, somewhere unrelated:

```
sh: vite: not found
```

**Control.** The identical install with a neutral `NODE_ENV` exits 0 and produces a working `node_modules/.bin/vite`. The environment is the whole variable.

**Fix, verified:**

```
$ docker run -e NODE_ENV=production ...
$ pnpm i --frozen-lockfile --prod=false
PNPM_EXIT=0
. prepare: husky - git command not found, skipping install
RESULT: vite PRESENT
```

`husky` degrades gracefully when git is absent, so `--prod=false` alone is sufficient. Also splits store-pruning onto its own line: cache cleanup is an optimisation and must not be able to fail the build, but it should not share a guard with the install either.

### Correction recorded

The `|| true` explanation was published, **retracted**, and then **un-retracted**. The retraction rested on a probe that exited 0 — but that probe ran with a neutral `NODE_ENV` and therefore never reproduced the builder. Measuring the wrong environment and treating the result as decisive is the same failure mode this repo keeps finding in its gates, committed twice on one question.

Two earlier probes were also invalid and discarded: one hit `ERR_PNPM_EACCES` from a Windows bind-mount (an artefact of the method, not the build), and one was mangled by MSYS path conversion — `-w /app` became `C:/Program Files/Git/app`. `MSYS_NO_PATHCONV=1` is required for container paths on this node.

---

## Related: two things this work surfaced elsewhere

**The `|| true` pattern is not isolated.** The same swallowed-exit-code shape appears in `merge-gate.yml`'s `python-tests` job (`... | head -20 | xargs pytest ... || true`) and in the `Validate Compose Files` and hardening steps. See PR #2525.

**A guard dead zone, hit live.** Writing a scratch file named `pnpm-probe.Dockerfile` to a temp directory was blocked by `readOnlyPaths`, and no Known Road grant could ever release it: `known_roads.py:_is_dockerfile_target` requires the basename to *be* `Dockerfile`/`Dockerfile.*`, which `pnpm-probe.Dockerfile` is not. Blocked with no reachable grant. PR #2530 anchored the pattern but kept the bare `Dockerfile` entry alongside it, so the substring over-match it was written to remove is still live — `pmoves/docs/Dockerfile_notes.md` is blocked as a Dockerfile today. Over-blocking is fail-safe, so this is not urgent, but the dead zone is real and reachable in ordinary work.

---

## Verification for the whole chain

Rooms are working when, from a populated tree:

```
make -C pmoves up-openroom
curl -sf http://localhost:5173/webuiapps/
```

returns 200 and a room loads at `?room=persona.room.livingdoc`. Until all three land, expect: exit 2 (CRLF), then exit 1 (`vite: not found`), then a build that completes.

**Note on method:** the builds behind this brief used a hand-transcribed compose stanza, because the live tree is 187 commits behind `origin/main` and its `docker-compose.yml` has no `openroom` service, while a fresh worktree has the service but cannot resolve `context: ../PMOVES-OpenRoom` or the gitignored env files. That sibling-submodule build gap is itself a known item — a transcription is not a substitute for the Known Road, and `up-openroom` is what should be used once the tree is current.
