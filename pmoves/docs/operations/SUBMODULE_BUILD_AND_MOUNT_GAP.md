# Submodule build & mount gap — why a correct compose still fails

**Applies to:** any checkout where `git submodule update --init` has not run — most commonly a **git worktree**, or a second clone of the repo.

**Why this is a runbook and not a ratchet:** the gap is a property of the *checkout*, not of any file. It cannot appear in a diff, and both relevant CI gates decline to check it — one by explicit design, one because it asks a different question (see [Why CI never sees it](#why-ci-never-sees-it)). The compose files are correct. The fork repos are correct. It still fails.

Verified against `origin/main` @ `22c78fbca`.

---

## The two failure classes

### Class A — build contexts (fails loudly)

Eight services build from seven registered submodules:

| Service | Submodule | Declared in |
|---|---|---|
| `archon` | `PMOVES-Archon` | `docker-compose.yml`, `.agents.yml`, `.archon.submodule.yml` |
| `cipher-api` | `Pmoves-cipher` | `docker-compose.yml`, `.agents.yml` |
| `pmoves-yt` | `PMOVES.YT` | `docker-compose.yml`, `.apps.yml` |
| `openroom` | `PMOVES-OpenRoom` | `docker-compose.yml`, `.ui.yml` |
| `llama-throughput-lab` | `PMOVES-llama-throughput-lab` | `docker-compose.yml`, `.media.yml` |
| `transcribe-backend` | `PMOVES-transcribe-and-fetch` | `docker-compose.yml`, `.media.yml` |
| `transcribe-frontend` | `PMOVES-transcribe-and-fetch` | `docker-compose.yml`, `.media.yml` |
| `n8n` | `PMOVES-n8n` | `docker-compose.n8n.yml`, and `compose/docker-compose.core.yml` as `../../PMOVES-n8n` |

The split overlays re-declare the same contexts as `docker-compose.yml`; they are not additional services. Jellyfin is **not** in this list — it builds locally.

Note the second n8n path: `pmoves/compose/docker-compose.core.yml` sits one directory deeper, so its context is `../../PMOVES-n8n`. It is live — `pmoves/.github/workflows/pmoves-integrations-ci.yml:73` invokes it. Scanning for a single `../` prefix misses it, and matching on the prefix *shape* rather than resolving the first segment against `.gitmodules` produces false positives in the other direction (`pmoves/docker-compose/hf-mcp-server.yml` uses `../../pmoves/services/hf-mcp-server`, which resolves back *inside* this repo and is not a submodule at all).

Class A fails at build time with a missing context or Dockerfile. Annoying, but visible.

### Class B — bind-mount sources (fails *silently*, then crash-loops)

This is the dangerous one. Two submodules supply bind-mount sources:

| Source | Mounted by | Kind |
|---|---|---|
| `../PMOVES-supabase/docker/volumes/logs/vector.yml` | `supabase-vector` | **file** |
| `../PMOVES-supabase/docker/volumes/functions` | `supabase-edge-functions` | directory |
| `../PMOVES-supabase/docker/volumes/api/kong.yml` | `supabase-kong` | **file** |
| `../PMOVES-supabase/docker/volumes/api/kong-entrypoint.sh` | `supabase-kong` | **file** |
| `../PMOVES-n8n/workflows` | `n8n` | directory |

**Docker does not error when a bind source is missing — it creates it, as a directory.** So a file mount silently becomes a directory mount, and the container fails on its own config rather than on the mount.

---

## The diagnostic

> **A bind-mount source that is a *directory* where a file is expected means the submodule was unpopulated when `up` ran.**

Nothing in the error message says "submodule". The messages look like application bugs:

| Container | Error | Actual cause |
|---|---|---|
| `supabase-vector` | `Configuration error. error=Is a directory (os error 21)` | `vector.yml` created as a directory |
| `supabase-edge-functions` | `could not find an appropriate entrypoint` | `functions/` created empty, no `main/index.ts` |

Confirm in one command — compare where the container is actually reading from:

```bash
docker inspect <container> --format '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
docker inspect <container> --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
```

If `working_dir` is not the checkout you think you are running, that is the whole answer. A container reports `Mounts` even when the source is a stub directory, so the mount list alone will not tell you.

---

## Fix

Docker's auto-created stubs make the submodule directory **non-empty**, so `git submodule update --init` refuses to clone into it:

```
fatal: destination path '.../PMOVES-supabase' already exists and is not an empty directory.
```

Clear the stubs first. They contain zero files by construction — verify that before deleting:

```bash
SUB=<repo>/PMOVES-supabase

# 1. Prove the stub holds nothing real. Expect files=0.
find "$SUB" -type f | wc -l
find "$SUB" -type d | wc -l

# 2. Stop only the affected containers (they are crash-looping; they serve nothing).
docker stop pmoves-supabase-vector-1 pmoves-supabase-edge-functions-1

# 3. Remove the empty stub tree. -empty is the guard: it cannot touch a real file.
find "$SUB" -depth -type d -empty -delete

# 4. Populate for real.
git -C <repo> submodule update --init PMOVES-supabase

# 5. Confirm the bind sources are FILES, not directories.
test -f "$SUB/docker/volumes/logs/vector.yml" && echo OK
test -f "$SUB/docker/volumes/functions/main/index.ts" && echo OK
```

### 6. Bring both services back

Step 2 stopped two containers; both need starting, and they need **different** commands.

```bash
# FILE mount — must be RECREATED, a plain start still fails (see below)
make -C pmoves supa-recreate-svc SVC=supabase-vector

# DIRECTORY mount — a plain start is enough
docker start pmoves-supabase-edge-functions-1

# confirm
docker ps --filter name=supabase-vector --filter name=supabase-edge-functions \
  --format '{{.Names}}\t{{.Status}}'
docker ps --filter status=restarting -q | wc -l    # expect 0
```

**Why the two differ.** Docker records the mount *type* in the container spec at creation. A container created against a directory keeps failing after the source becomes a file:

```
error mounting ".../vector.yml" to rootfs at "/etc/vector/vector.yml":
not a directory: Are you trying to mount a directory onto a file (or vice-versa)?
```

So a **file** mount needs `supa-recreate-svc`. A **directory** mount (`functions/`, `workflows/`) recovers on a plain `docker start`, because the recorded type already matches. Getting this backwards costs a confusing round — `edge-functions` came straight back while `vector` refused, from the same fix.

For a non-Supabase service, `supa-recreate-svc` is Supabase-scoped; use `recreate-svc SVC=<name>` (`Makefile:553`) — e.g. `n8n`, whose `workflows/` bind comes from `PMOVES-n8n`.

---

## Worked example (2026-08-08, 4090)

Two containers had been crash-looping since 2026-08-05 — `supabase-vector` **78 restarts**.

Root cause: **28 of 33 running containers** were launched from a second clone at `GitHub/POWERFULMOVES/PMOVES.AI`, where **all 57 submodules were unpopulated** (`git submodule status` showed `-` on every line). The clone was only 5 commits behind `main` — not abandoned, just never `--init`ed. Docker had created `vector.yml` as a directory on Aug 5 at 18:34.

Fix took the five steps above. Both containers healthy; `docker ps --filter status=restarting` returned zero.

Two things worth carrying forward:

- **`supabase-kong` was fine** despite declaring two file mounts from the same submodule. Its running container had `HostConfig.Binds: null` and its Kong config inlined into the entrypoint, so it never touched those paths. Check the container, not the compose file, before assuming a service is affected.
- **`git submodule status` is the fast triage.** A leading `-` means unpopulated; a leading `+` means populated but at a different commit than the gitlink. The second is drift, not this bug.

---

## Working from a worktree

Worktrees do not inherit submodules. Every Class A and Class B service above is unbuildable and unrunnable from a fresh worktree until you populate them there too.

Options, cheapest first:

1. **Don't build from the worktree.** Use the main checkout for `up`/`build`, and the worktree for source edits only. This is the normal split and needs no setup.
2. **Populate just what you need:** `git submodule update --init PMOVES-Archon` inside the worktree. Cheaper than all 65.
3. **`up-cipher-nobuild` — but read what it actually does.** Its recipe is `$(DC) --profile agents up -d --no-build --force-recreate cipher-api`, and `cipher-api` declares **only** a `build:` stanza — no `image:`. So `--no-build` reuses the image Compose *already built locally* under its default tag. It is a **gitlink-drift** workaround (its own help text says so: "applies env/port changes when the `Pmoves-cipher` submodule build is unavailable"), **not** a fresh-checkout escape hatch. On a node or worktree where that image was never built, it cannot start Cipher.

   Still worth keeping in a target-consolidation pass — it solves a real problem — but do not reach for it expecting it to work from a cold worktree.

---

## Why CI never sees it

Not because the runners have the submodules — they do not. Neither validator checks them out:

```
.github/workflows/validate-dockerfile-paths-ratchet.yml:54   actions/checkout   (no `with: submodules`)
.github/workflows/validate-composes-ratchet.yml:41           actions/checkout   (no `with: submodules`)
```

They pass for two different, deliberate reasons:

**`validate-dockerfile-paths` excludes these targets by design.** `pmoves/tools/validate_dockerfile_paths.py` skips any build target failing `_is_in_scope_build_target()`, with the reasoning in the source:

> `BROKEN_BUILD`: a compose build target that doesn't exist on disk **AND is in-scope for the ratchet** (not a sibling submodule / vendor / provisions path — those are external repos the ratchet can't statically check). […] the operator keeps them synced via `make submodules`.

So Class A is a **known, accepted** blind spot, not an oversight. The ratchet is answering "is the declared path right", and it is.

**`validate-composes` never looks at bind sources at all.** It validates compose structure, not filesystem state. Class B is outside its question.

The gap is therefore between a correct declaration and a checkout that cannot satisfy it — and both gates deliberately decline to close it. That is a defensible split (a static ratchet genuinely cannot reason about an external repo's contents), but it means **the only thing standing between this and a silent production failure is a human knowing about it.** Hence this document.

If a check is ever wanted, the useful one is **runtime, not build time**: on `up`, assert that every declared bind source of file kind is a file on disk. That catches Class B at the moment it matters, needs no submodule checkout in CI, and is a handful of `test -f` calls rather than a new workflow.
