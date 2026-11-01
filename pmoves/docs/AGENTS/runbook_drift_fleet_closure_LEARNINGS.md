# runbook_drift_fleet_closure_LEARNINGS.md

**Lane:** the runbook-drift auditor's own defect class (F1) plus the four items the
operator's fleet-review queue had left open — node-registry deployment wiring (F2),
the two unregistered pipecat forks (F3), the Windows POSIX-only blast radius (F4),
and the fleet-wide image-staleness ratchet (F5).
**Branch:** `feat/runbook-drift-open-items`.
**Taxonomy:** 4 buckets · 5 classes, as used across the PMOVES lanes.
**Tooling:** `scripts/runbook_drift.py` (the zero-LLM drift auditor added by PR #3375)
is the instrument this lane was measured with. It found its own defect first.

---

## What was broken

The lane started from a review question — *"the runbook drift tooling around PR
#3375 should help address the open items"* — and the honest answer turned out to be
that **the tooling could not see any of the open items, and was itself lying about
what it had seen.**

### The measurement that started it

A fresh run of the auditor against a clean worktree at `origin/main`
(`f202064a6758`), scope `plans/*.md`:

```
run_digest f90d93a4d5ab…   160 claims / 7 files
VERIFIED 99   UNDECIDED 59   DRIFTED 2
```

**59 of 160 claims could not be decided.** The 2 DRIFTED were real (two endpoints
answering HTTP 404). The 59 UNDECIDED were not: **47 of them had a file with that
EXACT NAME sitting in the tree**, and in every one of those 47 the auditor's own
evidence string named a file that merely *mentioned* the name.

### F1 — the file probe grepped CONTENT and called it a NAME

`scripts/runbook_drift.py::probe_file` resolved a missing path with:

```python
git grep -l --fixed-strings '<basename>' origin/main -- | head -3
```

`git grep -l` returns files whose **TEXT** contains the string. The probe then
reported `basename found on origin/main at: <that file>` — a claim of existence
backed by a document that only talked about the artefact. Measured examples:

| Claim | Evidence the auditor cited | The file that actually exists |
|---|---|---|
| `agent_registry.yaml` | `.claude/CLAUDE.md` | `pmoves/config/agent_registry.yaml` |
| `beats_to_voice.py` | `.claude/hooks/shift-crew-trail.sh` | `pmoves/tools/beats_to_voice.py` |
| `validate_room_manifests.py` | `.claude/commands/p7/room.md` | `pmoves/scripts/validate_room_manifests.py` |
| `PERSONAS.md` | `.claude/context/documentation-index.md` | `pmoves/docs/AGENTS/PERSONAS.md` |
| `signing_identity_cards.yaml` | `.claude/CLAUDE.md` | `pmoves/config/signing_identity_cards.yaml` |

A **content grep is not a filename search**. The evidence named an artefact the
claim never named — and because the verdict was UNDECIDED rather than DRIFTED, the
failure was invisible: the report still said "we could not decide", so nobody
looked.

The fix resolves by NAME over `git ls-tree -r --name-only origin/main` (plus a
bounded working-tree walk for non-git checkouts), and the evidence names the file
that actually matched.

**But the first fix was still wrong, and only measurement caught it.** Resolving
every claim by basename produced 146 VERIFIED — and **24 of those were FALSE**:
a PATH claim (`PMOVES-Archon/README.md`) was satisfied by any of the **210**
unrelated `README.md` files in the tree, and `.kilocode/mcp.json` (a git-ignored
local path) was satisfied by `.claude/mcp.json`. The auditor was citing artefacts
the claim never named — the same lie, one layer down. The refined rule:

- a **bare basename** (`agent_registry.yaml`) may match any file of that name;
- a **PATH claim** (`PMOVES-Archon/README.md`) may only match a path ENDING that
  way, on a directory boundary;
- a path claim that points **into a submodule** is UNDECIDED — the parent tree
  records a gitlink, not the submodule's files, so absence proves nothing;
- a **git-ignored** path is UNDECIDED — it is a local artefact, absent by design.

Measured on the same tree and scope, before → after:

| | VERIFIED | UNDECIDED | DRIFTED |
|---|---|---|---|
| baseline (content grep) | 99 | 59 | 2 |
| name-only fix | 146 | 2 | 12 |
| **shape-aware fix (shipped)** | **122** | **27** | **11** |

Of the 27 remaining UNDECIDED: **22 submodule**, **3 git-ignored**, **2 stale
checkout**. All 11 DRIFTED are genuine drift — every one was re-checked against
the whole tree and has **zero** name matches anywhere.

### F2 — node-registry: a complete service with no way to run

`pmoves/services/node_registry/` is a finished five-module service (subscriber,
storage, HTTP API) with **no Dockerfile, no compose service entry and no Make
target**. It therefore never starts in normal bring-up — the R8a row of
`pmoves/docs/AGENTS/PRE_RESTART_PREFLIGHT_2026-08-25.md`, open since 2026-08-25.

The preflight log said "resolve the port conflict first" and left the port as an
operator decision. **Measurement resolved it**: `pmoves/docker-compose.yml:2672`
binds media-audio to host `${MEDIA_AUDIO_PORT:-8082}:8082` and its healthcheck
curls `http://localhost:8082/healthz` — **8082 is already owned by another
service**. 8115 is what **both** `pmoves/tests/utils/service_catalog.py:266-275`
(`NODE_REGISTRY = ServiceDefinition(name="node-registry", port=8115, …,
profile="distributed,orchestration", dependencies=["nats","postgres"])`) and
`pmoves/docs/infrastructure/DISTRIBUTED_COMPUTE_SERVICES.md:47` ("### 1. Node
Registry [Port 8115]") already said, as does
`.claude/context/runner-topology.md:6,46`. The code said 8082 in six places
(`main.py:96`, `api.py:35`, `api.py:526`, `registry.py:616`, `__init__.py:19`,
`__init__.py:32`). The code was the outlier, not the docs.

**But "8115 is free" was itself too narrow a claim, and the narrowness was
found by sweeping every compose file instead of one.** `pmoves/docker-compose.yml`
is not the only compose file in `pmoves/`:
`pmoves/docker-compose.yt-cookies.yml:46` binds
`"${YT_COOKIE_REFRESHER_BIND:-127.0.0.1}:8115:8115"` for `yt-cookie-refresher`
— a **second claimant of the canonical node-registry port**. It is not a
default-stack collision (`docker-compose.yt-cookies.yml` is not in `STACK_FILES`
— see `pmoves/Makefile:2907` — and the service is gated behind the
`yt-cookies` profile), but it is a latent one, and it is reported to the
operator as a separate pre-existing defect rather than silently ignored.

The collision assertion in the shipped ratchet is therefore scoped to the
**default stack** — the set that is actually brought up together — not to
every compose file in the tree. A ratchet that is red on arrival teaches the
fleet to ignore it. `pmoves/tests/smoke/test_compose_structure.py::test_cross_compose_port_conflicts`
cannot be relied on to catch this: it resolves a host port only when the
left-of-colon side is a bare number, so a `${VAR:-127.0.0.1}` binding is
skipped entirely and the yt-cookies entry is invisible to it.

**And F2 repaired five defects it did not set out to touch.**
`pmoves/tools/validate_command_anchors.py` keeps a baseline of findings it
cannot yet resolve. Among them were **five** `GHOST_ENDPOINT` entries in
`pmoves/docs/infrastructure/DISTRIBUTED_COMPUTE_SERVICES.md` — the
node-registry documentation's own endpoints, attributed to
`yt-cookie-refresher`. They were ghosts because node-registry was **not a
deployable service**: the validator could not attribute `/api/v1/nodes` to a
service that had no image and no compose entry, so the routes resolved
elsewhere. Giving node-registry a Dockerfile, a compose entry and a Make
target made the attribution resolvable, and the five findings stopped
occurring. The gate then reported them as **STALE BASELINE** entries —
"these were fixed; drop them so the same defect cannot return silently" —
and `make -C pmoves validate-command-anchors-baseline` dropped exactly
those five. A deployability fix that repairs a documentation ratchet's
backlog is the same fix showing up in a second instrument.

**The split overlays are GENERATED, and adding a service to the compose
source regenerates them.** `pmoves/docker-compose.{base,core,agents,media,
ui,workers,apps,juicefs}.yml` are produced from `pmoves/docker-compose.yml`
by `pmoves/scripts/split_compose.py` — never hand-edited — and the
`compose-split-drift-check` job in `.github/workflows/merge-gate.yml`
regenerates them and fails on `git status --porcelain`. Measured: the
overlays were in sync on `origin/main` (the gate is green there), and
adding one service desynchronised exactly one of them:
`docker-compose.core.yml`, because an ungrouped service lands in the
`core` overlay. The regeneration is safe **because** main was clean: the
gate's own warning — "`compose-split` would make this green by DELETING the
hand-edits that were never ported into the source" — is a warning about
*unported* edits, and there were none outstanding. The diff was 51
insertions of the node-registry block and **zero** deletions of live
config. The gate compares against COMMITTED state, so the regenerated
overlay has to be committed before the check passes — a regenerated-but-
uncommitted overlay is still drift.

### F3 — two pipecat forks in no registry, and six registry claims with no mechanism

`pmoves/config/fork_registry.json` and `.github/workflows/fork-sync.yml` are two
independent hand-maintained lists. Measured: registry **84** forks / **33**
`sync: true`; the workflow's `FORKS` block **31**; the GH App `repositories:`
scope **31**; the two workflow lists had identical membership. **Six registry
forks claimed `sync: true` while appearing in neither workflow list** —
`Pmoves-pipecat-context-hub`, `PMOVES-KeYlOkODe`, `PMOVES-ScaleTail`,
`PMOVES-natscli-CHIT-EeZz`, `Pmoves-Glancer`, `Pmoves-nats.net`. Two more pipecat
forks — `Pmoves-pipecat-client-web-transports` and `Pmoves-pipecat-mcp-server` —
were in **no** registry entry, **no** workflow entry, **no** token scope and **no**
submodule: prose-only. Measured drift vs upstream: context-hub **463** ahead,
client-web-transports **117** ahead, mcp-server **0/0** (upstream dormant since
2026-02-12).

A `sync: true` with no mechanism behind it is a claim with nothing implementing
it — and the existing ratchet could not see it, because it cross-checked
`.gitmodules` → registry and never registry → workflow.

### F4 — a POSIX-only call at module scope is a collection bomb

`pmoves/tests/tools/test_env_local_key.py:360` read
`@pytest.mark.skipif(os.geteuid() == 0, …)`. A decorator argument is evaluated at
**import** time, and `os.geteuid` does not exist on Windows — so the whole file
failed collection and **0 tests ran**. Reproduced on the operator's host:

```
AttributeError: module 'os' has no attribute 'geteuid'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

An AST sweep over `pmoves/**/*.py` found **5 module-scope POSIX-only `os.*`
calls across 4 test files**; **2** of the 4 actually broke collection, hiding
**71 tests** (69 in `test_env_local_key.py`, 2 in
`test_secrets_audit_unreadable.py`). The other two files already used the house
pattern — `hasattr(os, "geteuid") and os.geteuid() == 0`, which short-circuits —
so the fix was to apply an existing convention, not to invent one.

The **tool** was broken too, and worse: `pmoves/tools/env_local_key.py` raised a
**raw traceback** on Windows, because `os.fchmod` (audit log), `os.fchown` and
`os.getegid`/`os.geteuid` do not exist there and only `PermissionError` was
caught. An operator tool that stack-traces on the operator's own platform is not
a tool with a POSIX-only mode — it is a tool that is broken there.

### F5 — nothing rebuilt the fleet's images

`pmoves/images.yaml` declares **30** images. `.github/workflows/build-images.yml`
reads that matrix, but its `on:` block was `workflow_dispatch:` **only** — no
`push:`, no `schedule:`, no `repository_dispatch:`. The `push: true` at line ~116
is the **buildx `--push` flag**, not a workflow trigger, and it is an easy misread.
`integrations-ghcr.yml` has a `push:` trigger but its `schedule:` is **commented
out** and its matrix does not include flute-gateway. So the flute image went
**65 days stale** because nothing rebuilds it automatically: the GH App is scoped
to FORKS, and image publishing uses separate `GHCR_USERNAME`/`GHCR_PASSWORD`
secrets.

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **reasoning-gap** | **A content grep is not a filename search** — and an evidence string must name the artefact it actually observed. | `probe_file` resolved a missing path with `git grep -l --fixed-strings <basename>`, which returns files whose TEXT mentions the name. It then reported `basename found on origin/main at: <that file>`. Measured: **47 of 57** UNDECIDED file_path claims had a file of that exact name in the tree, and in **every one** the cited evidence was a file that only mentioned the string (`agent_registry.yaml` → `.claude/CLAUDE.md`). Because the verdict stayed UNDECIDED rather than becoming wrong, the failure was invisible — the report still said "could not decide". FIX: resolve by NAME over `git ls-tree -r --name-only origin/main`, and let the evidence name the file that matched. | Any drift, liveness or inventory probe that must decide "does this path exist". |
| 2 | **reasoning-gap** | **The SHAPE of a claim decides how it may be matched** — a path claim matched on its basename cites an artefact the claim never named. | Fixing lesson 1 by basename alone turned 146 VERIFIED, of which **24 were FALSE**: `PMOVES-Archon/README.md` was satisfied by any of the **210** unrelated `README.md` files in the tree; `.kilocode/mcp.json` (git-ignored) was satisfied by `.claude/mcp.json`. A bare basename (`agent_registry.yaml`) may match any file of that name; a PATH claim may only match a path ENDING that way, on a directory boundary. Measured: shape-aware 122 VERIFIED / 27 UNDECIDED / 11 DRIFTED, and all 11 DRIFTED re-checked to have zero name matches anywhere. | Any matcher that keys on one component of a multi-component identifier. |
| 3 | **reasoning-gap** | **Absence is only evidence when absence means something** — a submodule or a git-ignored path is UNDECIDED, not DRIFTED. | A claim pointing into a submodule (`PMOVES-Archon/README.md`) names a file in ANOTHER repository; the parent tree records a gitlink, so its absence proves nothing. A git-ignored path (`.kilocode/*`, per `.gitignore:301`) is a local artefact, absent by design. Both are now UNDECIDED with the reason named — 22 submodule + 3 git-ignored of the 27 remaining. Without this, "could not check" and "it is broken" collapse into one wrong answer. | Any absence-based verdict over a tree with submodules or ignore rules. |
| 4 | **reasoning-gap** | **A module-scope POSIX call is a COLLECTION bomb, not a test failure** — and a platform-blind test suite is blind in exactly one direction. | `os.geteuid()` inside a `skipif` decorator argument is evaluated at IMPORT time. On Windows the attribute does not exist, so the whole file failed collection and **0 tests ran** — 71 tests across 2 files. The other 2 of the 4 affected files already used `hasattr(os, "geteuid") and os.geteuid() == 0`, so the fix was an existing convention, not a new one. The same class hid in `pmoves/tests/test_runbook_drift_root.py`, which passed `env={"PATH": "/usr/bin:/bin"}` and thereby stripped `%ComSpec%`/`%SystemRoot%`: `subprocess` could not spawn a shell ("shell not found"). CI runs ubuntu-only, so **neither defect could ever show up in the merge gate** — they only bite the operator on Windows. | Any test or tool that must run on both POSIX and Windows. |
| 5 | **contract-correctness** | **A tool that stack-traces on the operator's platform is broken there, not POSIX-only** — degrade or refuse, in the tool's own language. | `pmoves/tools/env_local_key.py` raised a raw `AttributeError` traceback on Windows: `os.fchmod` (audit-log open), `os.fchown` (owner preservation) and `os.getegid`/`os.geteuid` do not exist, and only `PermissionError` was caught. The tool's contract is POSIX-centric, but its FAILURE MODE was not: it printed a traceback instead of its own `result=refused … reason=…` line. | Any operator-run tool with a platform-specific syscall. |
| 6 | **contract-correctness** | **A declared capability with no mechanism behind it is a claim, not a feature** — the two lists must be cross-checked. | `fork_registry.json` said `sync: true` for 33 forks; `fork-sync.yml`'s `FORKS` block and the GH App `repositories:` scope each said 31. **Six registry forks were in neither workflow list**, and two pipecat forks were in no list at all — prose-only, 463 and 117 commits ahead of upstream respectively. The existing ratchet proved every fork was DECIDED (`sync` + `reason`) and cross-checked `.gitmodules` → registry; it never cross-checked registry → workflow, so it reported full coverage over a gap. Shipped: the registry is **86** forks / **35** `sync: true`, both workflow lists are **39** with identical membership, and `_validate_workflow_coverage()` checks registry → workflow with stdlib text parsers (no YAML import), scoped the same way as `_validate_coverage`. | Any registry of intended state paired with a separate executor. |
| 7 | **contract-correctness** | **A service that no bring-up path starts is not deployed** — a Dockerfile, a compose entry and a Make target are three separate obligations. | `pmoves/services/node_registry/` was a complete service (subscriber + storage + HTTP API) with none of the three. The R8/R8a rows of the 2026-08-25 preflight have been open since that date. The port was the stated blocker, and measurement resolved it: 8082 is media-audio's host binding (`docker-compose.yml:2672`), and 8115 is what the catalog and the docs already said. The service also imports `..resource_detector.models` / `..resource_detector.hardware`, so its image must carry `pmoves/services/resource_detector/` and `pmoves/services/common/` as well as its own package — an image that carries only the service's own files imports fine on the host and dies in the container. | Any service directory in `pmoves/services/`. |
| 8 | **reasoning-gap** | **Manual-only is not automatic** — a build pipeline whose only trigger is `workflow_dispatch:` is a pipeline that goes stale on a human's schedule. | `build-images.yml`'s `on:` block was `workflow_dispatch:` alone; the `push: true` nearby is the buildx `--push` flag, not a trigger. The flute image went **65 days stale** because nothing rebuilt it — the GH App is scoped to FORKS, and image publishing uses separate GHCR secrets. `integrations-ghcr.yml`'s `schedule:` is commented out and its matrix omits flute-gateway. A staleness ratchet that can only say "this image is old" without a non-manual trigger leaves the clock running. Shipped: a `schedule:` trigger was added to `build-images.yml` and `pmoves/tools/image_staleness_ratchet.py` now asserts, per image in `pmoves/images.yaml`, that the builder fields exist, that the build inputs resolve, and that the build path needs no human click — while keeping **UNDECIDED** (a submodule that is not checked out) distinct from **DRIFTED** (genuinely broken). The job's display name changed from `Manual Image Build` to `Image Build`; measured first — that literal string appeared in exactly one file, and main's required contexts are `python-tests`, `hardening-validation`, `verify` and `submodule-gitlink-gate`, so it was never a required context. | Any build/publish pipeline. |
| 9 | **pattern-conformance** | **A mutation must revert the WIRING, not perturb a neighbouring condition** — and a surviving mutation means the test does not guard what you think it guards. | While hardening lesson 2 I mutated the bare-basename branch's entry condition (`if not claim or "/" not in claim:` → `if not claim:`) to prove the rule load-bearing. **All 15 tests still passed** — the mutation never touched the path branch, so it never restored the defective behaviour. The mutation that actually bites reverts the path branch's matcher (`_paths_ending` → `_paths_named`) and puts **3 named tests** red. The first hypothesis for a surviving mutation is that the mutation is wrong, not that the test is weak. | Every mutation-kill harness. |
| 10 | **reasoning-gap** | **A port sweep that reads one file is not a port sweep** — and a ratchet that is red on arrival teaches the fleet to ignore it. | "8115 is free" was MEASURED against `pmoves/docker-compose.yml` alone. `pmoves/` holds many compose files, and `pmoves/docker-compose.yt-cookies.yml:46` binds `127.0.0.1:8115` for `yt-cookie-refresher`. The conclusion happened to survive (8115 is right — the catalog, the service doc and the runner topology all say so), but the *method* would have shipped a collision without noticing. The same narrowness exists in the existing gate: `test_cross_compose_port_conflicts` resolves a host port only when the left-of-colon side is a bare number, so every `${VAR:-127.0.0.1}` binding is skipped — the yt-cookies entry is invisible to it. The shipped ratchet therefore asserts the collision over the **default stack** (`STACK_FILES`, `pmoves/Makefile:2907`), which is the set actually brought up together, and names the exclusion rule instead of pretending the port is unclaimed. | Any "is this port free" claim, and any ratchet whose verdict must be true on the day it lands. |
| 11 | **reasoning-gap** | **Moving a service's port is not a one-file change — and the consumers' old default is ANOTHER service's port, so the failure is silent.** | Moving node-registry off 8082 would have left **six** consumer defaults still naming 8082: `pmoves/services/work_marshaling/__init__.py` (4 sites — the module docstring, the `WorkMarshaling.__init__` default, the `run_marshaling` default and the `NODE_REGISTRY_URL` env default) and `pmoves/services/work_marshaling/main.py:68` (the `NODE_REGISTRY_URL` env default), plus `pmoves/services/vllm_orchestrator/tensorzero.py:381` (`node_registry_url`). Both services declare `node-registry` in their catalog `dependencies`. Leaving them would not have produced a connection error — 8082 answers — it would have pointed them at **media-audio**, so a node query would have been answered by the wrong service. The catalog was the only place that said 8115; the consumers carried 8082 because 8082 was what the code had always claimed. | Any change to a service's host port, and any default that names another service's port. |
| 12 | **reasoning-gap** | **A dot is TRUTHY in a GitHub Actions expression** — so a fallback that looks guarded can be dead code, and the ratchet that mirrors it inherits the blindness. | `build-images.yml` resolved the build context with `matrix.context \|\| format('{0}/{1}', github.workspace, matrix.repo)`. A NON-EMPTY `context` always won: MEASURED, **18 of the 19** repo-backed entries in `pmoves/images.yaml` set `context: .`, and the one exception (`pmoves-tokenism-ui`) sets `context: pmoves-nextjs`. A dot is truthy, so `matrix.context` always won and the `github.workspace/matrix.repo` branch never ran: **18** images were built against the WORKSPACE ROOT and one against `github.workspace/pmoves-nextjs` — in every case a directory that does not hold that image's Dockerfile. The evidence that this never worked: the last **7** runs of the workflow ALL failed. The ratchet mirrored the same expression, so it verified submodule Dockerfiles the build never opened. FIX: `matrix.repo && format(...) \|\| matrix.context` — the discriminator FIRST — and the ratchet now mirrors the workflow LITERALLY with **one** candidate path, because a ratchet that tries several readings and accepts whichever matches can verify a file the build would never open. The now-dead `context` on `pmoves-tokenism-ui` is flagged rather than left in the matrix as a contradiction nobody would look for. | Any workflow expression with a fallback, and any ratchet that mirrors a workflow. |
| 13 | **pattern-conformance** | **A mutation kill must be PLATFORM-INDEPENDENT** — a kill that only bites on one OS reports a live defect as a passing lane. | The F4 mutation reverted the tool's guard to an unconditional `os.fchmod`, and the kill signal was the behavioural test `test_env_local_key_never_emits_a_raw_traceback`. On POSIX `os.fchmod` **EXISTS**, so the mutated tool behaves correctly and the mutation **SURVIVED**. The ubuntu `python-tests` job went red with exactly that message — the harness reporting its own blind spot. FIX: the kill signal is the STRUCTURAL test (`test_env_local_key_has_no_unguarded_posix_only_os_reference`), because "an unguarded POSIX-only syscall is reachable" is true on EVERY platform; the behavioural test is kept as a separate WINDOWS-only case, because on POSIX the defective code is CORRECT code and there is nothing to kill. | Every mutation-kill harness, and every cross-platform test. |
| 14 | **pattern-conformance** | **A hand-rolled re-implementation of a guarded contract fails on the platform its author is not on** — use the sanctioned helper. | The node-registry deployment test built its own stub tool dir for the docker guard: a marker file plus one recorder per tool, each written with Python's default 0644. The guard's `_is_recorder()` requires `os.access(path, os.X_OK)`. On WINDOWS `X_OK` is a no-op on a regular file, so the stub was accepted and the test ran; on LINUX the same file is not executable, `is_stub_dir()` returned False, and the guard raised `DestructiveDockerCallBlocked` — the test failed on CI for a reason that had nothing to do with node-registry. FIX: the sanctioned `build_stub_env()` from `pmoves/tests/_destructive_docker_guard.py`, which chmods 0755 and is therefore correct on both platforms. | Any test that satisfies a guard, a fixture, or an environment contract. |
| 15 | **contract-correctness** | **A pinned upstream TAG has no remote-tracking ref** — merge `FETCH_HEAD`, not `upstream/<tag>`. | `fork-sync.yml` merged `upstream/$ub`, which works only because a BRANCH fetch opportunistically updates `refs/remotes/upstream/<branch>`. MEASURED against the real upstream, both shapes: `git fetch --no-tags upstream v4.5.8` sets FETCH_HEAD and creates NO remote-tracking ref, so `git merge upstream/v4.5.8` fails with "not something we can merge"; fetching `develop` sets FETCH_HEAD **and** creates `refs/remotes/upstream/develop`. The hardened Glancer branch tracks a RELEASE TAG, so the old merge would have failed for exactly the fork the pin exists for. FIX: resolve `git rev-parse --verify --quiet 'FETCH_HEAD^{commit}'` after the fetch and merge that SHA — FETCH_HEAD is the one ref both shapes set. Proven end-to-end against the real fork: the old command failed, the new one fast-forwarded `026175c0..c2788e66`. | Any workflow that fetches a ref other than the upstream's default branch. |
| 16 | **contract-correctness** | **Under `bash -e`, a bare failing command aborts the WHOLE loop** — `cmd; if [ $? -ne 0 ]` never reaches the check. | GitHub runs `run:` steps under `bash -e`. `fork-sync.yml` merged with `git -C "$d" merge --no-edit "upstream/$ub"` followed by `if [ $? -ne 0 ]; then … skip … fi`. A merge conflict would have ABORTED THE STEP: the conflict would read as a workflow failure, and every fork after it in the list would never be synced — the opposite of the "skip this fork, carry on" the comment promised. FIX: `if ! git -C "$d" merge --no-edit "$merge_ref"; then … fi`. | Any GitHub Actions `run:` block, and any `set -e` shell loop meant to continue past a failure. |
| 17 | **contract-correctness** | **A gate that cannot read its input must FAIL, not pass** — UNDECIDED is right for an uninitialised SUBMODULE, and wrong for the gate's own probe gagging. | Two fail-open holes in the image ratchet, both found by review. (a) `parse_images_matrix` returns `[]` for any shape it does not recognise (a flow-style `- {name: ...}` entry, a re-indented `images:` key), and `main()` then tallied zero claims, zero problems and **exited 0** — a green hard gate that verifies nothing, so a matrix reformat would have sailed straight through the gate built to catch the 65-day staleness bug. (b) When `parse_workflow_triggers` could not read the `on:` block, the `build_path` claim became UNDECIDED, and UNDECIDED **passes** — so the check whose entire origin story is "the trigger silently disappeared and nobody noticed" also went green when the trigger silently became unparseable. The distinction: an uninitialised submodule is an ENVIRONMENTAL condition (the subject is fine, the checkout is not); a probe that cannot read its own subject is the INSTRUMENT failing. Both now fail closed, and the matrix-empty case has a negative-control test. | Any gate whose input it might fail to parse. |
| 18 | **reasoning-gap** | **A guard counts only if an ancestor can actually PROTECT the reference** — walking to the top of the file is not a guard check. | The F4 ratchet's `_guard_kind` walked the ancestor chain all the way up to `ast.Module`, and `_hasattr_guard` then `ast.walk`ed that Module — i.e. the ENTIRE FILE. Net effect: an unguarded module-scope `os.geteuid()` anywhere in the file was stamped `guard="hasattr"` if an UNRELATED `hasattr(os, "geteuid")` existed anywhere else in the same file. That is not a guard check, it is a "has this file ever heard of hasattr" check — the ratchet that exists to catch the collection bomb issued the bomb a hall pass whenever a legitimate guard lived somewhere else in the building. The same walk-to-Module logic meant any `sys.platform` compare anywhere guarded everything. FIX: credit a guard only from an ancestor that can protect the reference — stop the walk BEFORE `ast.Module`. An `if hasattr(os, "fchmod"):` node IS such an ancestor, because an `If` node's subtree includes its own `test`. | Any AST scope/guard analysis that walks to the module root. |
| 19 | **reasoning-gap** | **Eager is not lazy** — a comprehension that runs at import is MODULE scope, however it is written. | `ListComp`/`SetComp`/`DictComp` bodies were classified as "function" scope, but a module-level `[os.geteuid() for _ in range(1)]` runs EAGERLY at import time — precisely the collection bomb this ratchet exists to catch — while `module_scope_hits` filtered on `scope == "module"` and never saw it. `GeneratorExp` is lazy, so its body being function scope is defensible, but a generator expression's FIRST iterable IS evaluated eagerly in the enclosing scope, so that part had to keep the enclosing scope. FIX: the elements/keys of EAGER comprehensions are classified at the comprehension's OWN scope; function scope is kept only for `GeneratorExp` bodies. | Any static analysis that classifies a scope by syntax rather than by when it runs. |
| 20 | **contract-correctness** | **An audit and the thing it audits must measure the SAME thing** — a report that contradicts the fix is a broken signal. | `fork-sync.yml` had two definitions of "behind": the audit loop compared every fork against its upstream's DEFAULT branch, while the sync loop merged a PINNED policy ref. So the audit printed "STALE 614 behind" for Pmoves-Glancer against upstream develop — a ref the policy says is NOT the source — on every single run, and would eventually scream CRITICAL about a fork the policy says is CURRENT. FIX: ONE definition of the fork list (a "Prepare the fork policy" step that exports it to `$GITHUB_ENV`) and ONE resolver (a file both steps source) that decides the fork branch and the upstream ref, so the two cannot drift apart again. MEASURED locally with a mocked `gh`: 39 entries exported, Glancer resolves to `PMOVES.AI-Edition-Hardened\|v4.5.8`, a branch override resolves to the override, a gitlink branch resolves from `.gitmodules`, and a fork outside the list falls back to the defaults. The literal `FORKS="..."` shape was KEPT because the registry ratchet parses that block as text out of the workflow file — the shape is an interface between the workflow and the gate. | Any report that measures the same subject as an action. |
| 21 | **reasoning-gap** | **An unmeasured universal quantifier is a defect in a lane whose brand is MEASURED claims** — and the good number was available for free. | The build-context comment said "and EVERY repo-backed entry sets `context: .`". MEASURED: **18 of the 19** do; the exception is `pmoves-tokenism-ui`, which sets `context: pmoves-nextjs`. The corollary "all 19 resolved against the WORKSPACE ROOT" was wrong for that one — it resolved against `github.workspace/pmoves-nextjs`, its own flavour of the wrong place, but not the workspace root. In a lane whose entire brand is measured claims, an unmeasured "EVERY" in the comment explaining WHY measurement mattered was the exact defect the lane exists to catch. The same pass found a comment citing `integrations-ghcr.yml`'s `'17 7 * * *'` as a live schedule when that file's `schedule:` is COMMENTED OUT (lines 97-98) — a dead code block cited as fleet-wide load-balancing evidence. FIX: the quantifier now states 18 of 19 and names the exception; the schedule neighbour now cites the LIVE ones (measured across `.github/workflows`); and the dead `context` is flagged by the ratchet rather than left in the matrix where nobody would look for it. | Any claim of universality in a comment, a docstring, or a register row. |
| 22 | **contract-correctness** | **A one-directional baseline check leaves the direction nobody thinks about uncovered** — and an absent entry produces no claim at all. | The stale-gap check catches a gap that gets FIXED: its `build_inputs` claim becomes VERIFIED, so the baselined gap is stale and fails until it is dropped. Good contract — and one-directional. A `known_gaps` name whose image was REMOVED from or RENAMED in `pmoves/images.yaml` produces NO claims, matches nothing, and haunts the baseline forever: `stale_gaps` requires a VERIFIED `build_inputs` claim, so an absent image fails nothing and reports nothing. The baseline validated "broken -> fixed" but not "gone from the matrix entirely" — the one direction where nothing else will ever remind anyone the entry exists. FIX: an ORPHAN check — a baseline name with NO `build_inputs` claim AT ALL (not DRIFTED, not VERIFIED, not even UNDECIDED) is reported and failed, so the baseline cannot outlive the matrix entry it describes. | Any baseline, allowlist, or known-gap file. |
| 23 | **reasoning-gap** | **A docstring that describes the state of the tree is a CLAIM, not a caption** — and the lane that changes the tree must change the description in the SAME commit. | The `probe_dead_context` docstring said "The lane's own matrix has exactly one such entry: `pmoves-tokenism-ui` declares `context: pmoves-nextjs` ... and that declaration is ignored" — in the PRESENT tense. The SAME lane DROPPED that declaration from `pmoves/images.yaml` (MEASURED at the pinned gitlink `04285b813f`: the submodule holds both `Dockerfile` and `pmoves-nextjs/Dockerfile`, and the latter is what the entry wants). So the gate's own docstring described a tree state that stopped existing in the same PR: a present-tense claim falsified by the change sitting next to it, and a reader cannot tell which half to believe — the code or the prose about the code. FIX: past tense ("used to declare ... until the dead declaration was dropped"), and the probe now fails any entry that declares one again. The general shape: prose about the tree decays at exactly the rate the tree moves, so prose about the tree is a claim and carries the same standard as a claim. | Any docstring, comment or register row that describes the state of the tree it governs. |
| 24 | **reasoning-gap** | **An argument that cites a measurement can be FALSE, not merely unmeasured** — and the honest reason is usually better than the invented one. | The ratchet justified `REQUIRED_FIELDS = ("name", "dockerfile")` by saying requiring `image` "would put a FALSE RED on the lane's own matrix". MEASURED: **all 30** entries in `pmoves/images.yaml` DO declare `image:`, so requiring it would put exactly **ZERO** reds on the lane's own matrix. The conclusion was right for a fabricated reason. The same clause was half-true for `context`: requiring it would red exactly **one** entry — the now-contextless `pmoves-tokenism-ui`. FIX: the rationale is now the reason that survives measurement — `image` is DEAD BUILD INPUT (the tag comes from `${{ matrix.name }}`), and a dead field should not be law; requiring it would make the gate assert something the build does not do, and the thing a dead `context` actually breaks has its own probe (`dead_context`). Lesson 21 caught an unmeasured UNIVERSAL; this caught a measured-but-false NUMBER — a stronger claim, and the same failure mode wearing a lab coat. | Any rationale that cites a count, a rate or a comparison to justify a rule. |
| 25 | **defense-in-depth** | **A measurement script that silently skips what it cannot read reports a population it never counted** — and a lane whose brand is measured claims must measure its own evidence fail-closed, IN THE TREE. | The script that backs the schedule-contention comment did `continue` on a YAML parse exception, so a workflow file it could not parse was dropped from the population **silently** and the script still exited 0. "18 live scheduled workflows" was therefore a population that could shrink between runs without anyone noticing — the same fail-open shape as lesson 17, in the lane's own evidence-gathering rather than in a shipped gate. And the instrument was worse than fail-open: it lived in a developer's TEMP DIRECTORY, so the claim survived in the prose while the measurement itself did not exist in the tree — a reader hunting for the script that produced the numbers found nothing, and the lane's own lesson 25 was the thing that had to be applied to it. FIX: the measurement is now `pmoves/tools/measure_schedule_contention.py`, IN THE TREE and cited by the comment it backs. It counts the files it scanned, names every parse failure by file, and exits non-zero if any file failed — MEASURED: 74 files scanned, 74 parsed, 0 dropped, 18 live schedules. That rewrite also CAUGHT the quantifier error the comment was hiding: the "06:00 cluster" is **7** schedules, not 6, because `review-collect.yml` (`0 */2 * * *`) fires at 06:00 as well as at 04:00. The tool COMPUTES each schedule's weekly frequency from the parsed cron fields rather than being handed a ratio, which is how the hand-written "365x" was caught and corrected to 84. | Any script whose output is quoted as a number, a count, or a "nearest neighbour" — and any instrument cited by a comment that is not itself in the repository. |
| 26 | **reasoning-gap** | **A shorthand in a comment is a CLAIM — eliding the expression you measured is the same failure as asserting a number you did not.** | The contention comment wrote the 03:00 workflow's runner as `[self-hosted, Linux, X64, ...]`. The claim was TRUE, and the ellipsis hid the one detail that made it matter: the fourth element is `"${{ matrix.runner_label }}"`, so the workflow runs once per target host on this pool, and it is the same pool the build pushes images to. An ellipsis standing in for a matrix expression is "probably absent" in the same way a commented-out `schedule:` is "probably absent" — and the very comment that elided it criticises exactly that shape two dozen lines later, on the commented-out `integrations-ghcr.yml` cron. The lesson is not "ellipses are forbidden"; it is that a SHORTHAND is a claim, so it carries the same obligation to be exact as the number it stands in for. FIX: the exact `runs-on` expressions are now quoted, and the one schedule that could actually race the build (`docker builder prune -af` / `docker image prune -a -f` on the same pool) is named rather than left as "both are self-hosted, 83 minutes earlier". | Any comment that abbreviates an expression it measured. |
| 27 | **defense-in-depth** | **A summary that claims to BE a measurement needs a gate of its own** — otherwise it is the one number in the file nobody re-derives. | The bucket summary ("13 reasoning-gap / 0 semantic-naming drift / 8 contract-correctness / 1 defense-in-depth / 3 pattern-conformance = 25") is a MEASUREMENT of the lesson table sitting directly above it. It was written by hand, like every other number in this lane's prose, and hand-written numbers are the thing this lane exists to catch. The reviewer checked the arithmetic by hand — a good check ONCE, not a check that survives the next lesson. FIX: `pmoves/tests/tools/test_runbook_drift_learnings_taxonomy.py` RECOMPUTES the per-class counts and the total from the lesson table, asserts the summary's numbers agree, asserts the summary's lesson LISTS agree (a count that is right while the list is wrong is still a wrong summary), asserts every class present in the table appears in the summary (an absent class reads as an oversight rather than a measurement), and asserts the lesson numbers are contiguous from 1. The summary is now a CHECKED number rather than a claimed one. | Any aggregate, tally, or count published in a document that also contains the items it aggregates. |

**Bucket summary** (27 lessons) — (1) **reasoning-gap** 14 lessons (#1, #2, #3, #4, #8,
#10, #11, #12, #18, #19, #21, **#23, #24, #26**) · (2) **semantic-naming drift** 0 ·
(3) **contract-correctness** 8 lessons (#5, #6, #7, #15, #16, #17, #20, #22) ·
(4) **defense-in-depth** 2 lessons (**#25, #27**) · (5) **pattern-conformance** 3
lessons (#9, #13, #14).

A summary that claims to BE a measurement, in the file where lesson 24 finishes
explaining that citing a count without measuring it is a failure mode, needs a
gate of its own — otherwise the summary is the one number in the file nobody
re-derives. `pmoves/tests/tools/test_runbook_drift_learnings_taxonomy.py`
RECOMPUTES these counts from the lesson table above and asserts they agree, so
the summary cannot drift away from the thing it summarises. (MEASURED here, by
that test: 14 + 0 + 8 + 2 + 3 = 27 = the number of lesson rows.)

---

## Three review rounds, and what they changed

The lane was reviewed three times before it merged, and **every round found real
defects in the lane's own work** — which is the point of running the review before
the merge rather than after it. The third round is the one that makes the first two
look lucky: its findings were all about PROSE, and prose was where two of the three
were hiding.

**Round 1 — four P2 findings** (codex connector), all fixed: a claim inside a
NESTED submodule was reported DRIFTED rather than UNDECIDED; the image ratchet
never checked out its submodules, so 19 of 30 entries were UNDECIDED and the gate
was VACUOUS; the ratchet mirrored the build workflow's context expression
INEXACTLY, and the expression itself was dead code (lesson 12); and the hardened
Glancer branch had no upstream-ref pin, so the sync would have proposed a
614-commit development merge (lesson 15).

**Round 1 also produced three CI failures**, each a real defect rather than a
flaky test: the committed `docker_matrix.yaml` was stale after node-registry was
added; the node-registry make test hand-rolled a stub tool dir whose 0644
recorders are executable to `os.access(X_OK)` on Windows but NOT on Linux, so the
docker guard refused the spawn on CI (lesson 14); and the F4 mutation kill was
PLATFORM-DEPENDENT, so it reported a live defect as a passing lane on ubuntu
(lesson 13).

**Round 2 — ten further findings** (the second review bot), all fixed: the image
ratchet was FAIL-OPEN on an unparsable matrix and on its own gagged trigger probe
(lesson 17); `REQUIRED_FIELDS` demanded fields the builder never reads; the F4
ratchet credited a guard from ANYWHERE in the file, and misclassified eager
comprehensions (lessons 18 and 19); the fork-sync AUDIT and the fork-sync SYNC
measured different things (lesson 20); a comment claimed "EVERY repo-backed
entry" where the measured truth was 18 of 19, and cited a COMMENTED-OUT schedule
as a live neighbour (lesson 21); and the known-gaps baseline only checked one
direction (lesson 22).

**Round 3 — three further findings** (the third review bot), all fixed: the
schedule-contention comment cited `branch-protection-ruleset-sync.yml` as "the
nearest live neighbour" while `review-collect.yml`'s `0 */2 * * *` fires at the same
clock time — and **84x** more often, not the 365x this lane first wrote down
(lesson 21 AGAIN, in the very comment that exists because of lesson 21; the
ratio is now COMPUTED from the cron fields, and the first hand-written figure
was wrong); the "06:00 cluster" roll call omitted three live schedules; the
`dead_context` docstring described a matrix state the same lane had already
changed (lesson 23); and the `REQUIRED_FIELDS` rationale cited a "FALSE RED on
the lane's own matrix" that MEASUREMENT shows would be **ZERO** reds (lesson 24).

The third round also exposed a defect in the lane's own EVIDENCE-GATHERING: the
script that measured the schedule contention silently skipped any workflow file it
could not parse and still exited 0, so the population it reported could shrink
between runs without anyone noticing (lesson 25). Rewriting it fail-closed — **74
files scanned, 74 parsed, 0 dropped, 18 live schedules** — is what caught the
missing member of the "06:00 cluster" (`review-collect.yml`), and turned a citation
into a measurement: the comment now names the exact count at each clock time, the
runner class (hosted vs self-hosted) and the day-of-week restriction, so the
contention argument now stands on the build job's actual runner
(`[self-hosted, Linux, X64]`) rather than on a hand-picked neighbour.

**Round 4 — four further findings** (the fourth review bot), all fixed, and the
first round whose findings were all about the lane's own PROVENANCE rather than
about a behaviour: the fail-closed measurement was not in the TREE at all — it
lived in a temp directory, so the claim survived in the prose and the instrument
did not, and a reader hunting for the script that produced the numbers found
nothing (lesson 25's own lesson, applied to lesson 25); the **365x** ratio was
hand-written and WRONG — `0 */2 * * *` is 12 times a day (**84/week**) against
`0 4 * * 0`'s once a week, so the ratio is 84 (lesson 24, one paragraph after
the lane mocked itself for the same class of error); the bucket summary claimed
to be a measurement of the lesson table while the lesson table was the thing
being measured, so the summary now carries a test that recomputes it; and the
comment elided a `runs-on` expression into `...`, which is the "probably
absent" shape the same comment criticises two dozen lines later.

The instrument is now `pmoves/tools/measure_schedule_contention.py`, in the tree,
cited by the comment it backs. It is fail-closed (an unreadable workflow file is
a NAMED failure and a non-zero exit, never a silent drop), it COMPUTES each
schedule's weekly frequency from the parsed cron fields rather than being handed
a ratio, and it excludes the slot owner from its own contention check. Its
21 tests include a LIVE rot gate: on every PR the fleet is re-read and the
04:23 slot is re-checked against every self-hosted schedule, so the comment's
claim cannot rot into a falsehood unnoticed.

The four rounds are also the lane's own measure of its lessons: every finding that
was fixed was fixed at the ROOT, with a test that fails without the fix. Fourteen
of them are negative controls -- a gate that cannot read its input, a gate that
cannot check its subject, a gate that cannot see a baseline entry that no longer
exists, and a guard check that could be borrowed from across the room. The third
round adds a category the first two missed: a defect can live in the PROSE that
explains the fix, and a lane that measures everything else must measure its own
explanations too.

---


| Finding | Code | Tests | Gate |
|---|---|---|---|
| **F1** the probe grepped content | `scripts/runbook_drift.py` — `_origin_main_paths()`, `_working_tree_paths()`, `_paths_named()`, `_paths_ending()`, `_submodule_paths()`, `_is_gitignored()` | `pmoves/tests/test_runbook_drift_probe.py` (16) | the auditor itself; `pmoves/tests/test_runbook_drift_root.py` (8) |
| **F2** node-registry could not run | `pmoves/services/node_registry/{__init__,api,main,registry}.py` (port), `Dockerfile`, `requirements.txt`, `pmoves/docker-compose.yml` (service block), `pmoves/mk/node-registry.mk`, `pmoves/Makefile` (include) | `pmoves/tests/tools/test_node_registry_deployment.py` (6) | `make -C pmoves compose-provenance-audit`; `docker compose config` in `hardening-validation.yml`; `make -C pmoves validate-command-anchors` (5 stale ghost findings dropped) |
| **F2b** the consumers of the moved port | `pmoves/services/work_marshaling/{__init__,main}.py` (5), `pmoves/services/vllm_orchestrator/tensorzero.py` (1) | covered by the F2 sweep's `>= 6` non-vacuity assertion plus the F2 test | — |
| **F3** six claimed forks, no mechanism | `pmoves/config/fork_registry.json`, `.github/workflows/fork-sync.yml` (both lists + the GH App `repositories:` scope) | `pmoves/tools/tests/test_fork_registry_ratchet.py` (17) | `.github/workflows/fork-registry-ratchet.yml` |
| **F4** a module-scope POSIX call | `pmoves/tools/env_local_key.py`, `pmoves/tests/tools/test_env_local_key.py`, `pmoves/tests/test_secrets_audit_unreadable.py` | `pmoves/tests/tools/test_windows_posix_ratchet.py` (18) | the AST ratchet itself |
| **F5** nothing rebuilt the images | `.github/workflows/build-images.yml` (`schedule:` trigger, job renamed `Manual Image Build` -> `Image Build`) | `pmoves/tools/tests/test_image_staleness_ratchet.py` (33) | `.github/workflows/image-staleness-ratchet.yml` |
| **F5b** the build context was resolved against the WORKSPACE ROOT | `.github/workflows/build-images.yml` (`matrix.repo && format(...) \|\| matrix.context`), `pmoves/tools/image_staleness_ratchet.py` (one literal candidate path), `pmoves/configs/image_staleness/_known_gaps.yaml` (8 baselined gaps) | `pmoves/tools/tests/test_image_staleness_ratchet.py` (33) | `.github/workflows/image-staleness-ratchet.yml` — checks out submodules recursively and asserts **0 UNDECIDED** |
| **F5c** the image ratchet could go GREEN while measuring NOTHING | `pmoves/tools/image_staleness_ratchet.py` (`MatrixParseError` on an unparsable matrix, the `INSTRUMENT_ERROR` verdict, the `dead_context` probe, the `orphan_gaps` check), `pmoves/images.yaml` (the dead `context` dropped) | `pmoves/tools/tests/test_image_staleness_ratchet.py` (33, 14 of them new) | the ratchet's own exit code, plus the workflow's 0-UNDECIDED assertion |
| **F4b** the ratchet that catches the collection bombs had two holes of its own | `pmoves/tests/tools/test_windows_posix_ratchet.py` (`_guard_kind` stops BEFORE `ast.Module`; eager comprehensions classified at their own scope) | same file (18, 4 of them new) | the AST ratchet itself |
| **F3b** the Glancer release-tag pin | `.github/workflows/fork-sync.yml` (4th `FORKS` column `upstream_ref`, the `release` keyword, the FETCH_HEAD merge, the `bash -e`-safe conflict skip, ONE shared policy for the audit and the sync) | — | `.github/workflows/fork-registry-ratchet.yml` (the coverage re-check still passes) |
| **F1b** nested submodule claims | `scripts/runbook_drift.py` (`_owning_submodule()`, longest match wins) | `pmoves/tests/test_runbook_drift_probe.py` (16) | the auditor itself |
| **F5d** the schedule-contention measurement was cited but not in the TREE | `pmoves/tools/measure_schedule_contention.py` (fail-closed scan; COMPUTES each cron's weekly frequency; excludes the slot owner from its own contention check) | `pmoves/tests/tools/test_measure_schedule_contention.py` (21, incl. a LIVE rot gate that re-reads the real fleet and re-checks the 04:23 slot on every PR) | the tool's own `--check` exit code |
| **P1** the bucket summary was a number nobody re-derived | `pmoves/docs/AGENTS/runbook_drift_fleet_closure_LEARNINGS.md` (the **Bucket summary** line) | `pmoves/tests/tools/test_runbook_drift_learnings_taxonomy.py` (5 — RECOMPUTES the summary from the lesson table and asserts they agree) | the test itself |

**The mutation-kill harness** — `pmoves/tests/tools/test_runbook_drift_fleet_closure_mutation_kill.py`
— is the lane's own proof. **Seven** mutations, each reverting the WIRING rather than
a neighbouring condition, each required to put a NAMED test red, with the
restore byte-exact and asserted, all under a two-layer mutation lock:

| Mutation | Reverts | Named test that must go red |
|---|---|---|
| F1 | the path branch's matcher (`_paths_ending` -> `_paths_named`) | `test_a_path_claim_is_not_satisfied_by_an_unrelated_file_of_the_same_name` |
| F2 | `api.py`'s own default (`port: int = 8115` -> `8082`) | `test_node_registry_code_default_and_compose_binding_match_catalog_port` |
| F2 | the compose host binding (`:8115:8115` -> `:8082:8082`) | the same test — one named test, two wirings, two mutations |
| F3 | a claimed fork out of the workflow's `FORKS` list | `test_every_sync_true_registry_fork_is_in_the_workflow_forks_block` |
| F4 | the unconditional `os.fchmod` | `test_env_local_key_has_no_unguarded_posix_only_os_reference` — the STRUCTURAL kill, which bites on every platform (lesson 13) |
| F4 | the same mutation, seen from the operator's platform | `test_env_local_key_never_emits_a_raw_traceback` — WINDOWS-ONLY, because on POSIX the defective code is correct code |
| F5 | the `schedule:` rebuild trigger | `test_real_workflow_has_a_non_manual_trigger` |

**Measurements, before -> after**

| | before | after |
|---|---|---|
| drift auditor (7 files, 160 claims) | 99 VERIFIED / 59 UNDECIDED / 2 DRIFTED | 122 VERIFIED / 27 UNDECIDED / 11 DRIFTED (all 11 re-verified genuine) |
| Windows-collectable tests | 71 hidden behind 2 collection errors | 71 collect; 76 passed / 9 skipped on the operator's host |
| fork registry | 84 forks / 33 `sync: true`; 31 in each workflow list | 86 forks / 35 `sync: true`; 39 in each list, membership-identical |
| node-registry deployability | no Dockerfile, no compose entry, no Make target | all three, plus the port agreement across source + compose + catalogue |
| image build context | the workspace root for 18 of the 19 repo-backed images, and `github.workspace/pmoves-nextjs` for the 19th (a dot is truthy) | `github.workspace/<repo>` for every repo-backed image; the last 7 workflow runs had all failed |
| repo-backed images with a resolvable Dockerfile | — (the gate was vacuous: 19 of 30 UNDECIDED) | **11 of 19** resolve at the pinned gitlink; the other **8** are baselined as KNOWN-GAP, and a NEW gap fails while a FIXED gap is stale and fails |

---

## Cross-references

- `pmoves/docs/AGENTS/PRE_RESTART_PREFLIGHT_2026-08-25.md` — rows R8 / R8a and the
  "Still open (operator decisions)" section that F2 closes.
- `pmoves/docs/services/PIPECAT_FORK_PROVENANCE_AUDIT_2026-10-30.md` — "Gap 1"
  (registry → workflow), "Gap 2" (the two unregistered forks), "Gap 3" (the
  manual-only image build) — the provenance F3 and F5 answer.
- `pmoves/docs/AGENTS/AGNOTE4482_FLEET_FORK_REVIEW_2026-09-15.md` — the lane that
  registered `Pmoves-pipecat-context-hub`.
- `pmoves/docs/AGENTS/mesh_node_compatibility_LEARNINGS.md` — the sibling lane's
  lesson 17 (assert the mode a file was BORN with) and lesson 11 (a ratchet whose
  verdict depends on the HOST is not load-bearing), the same shape as lessons 4
  and 9 here.
- `pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md` — the sibling lane's
  "a ratchet that can only assert absence cannot say no".
- `pmoves/tests/tools/test_mesh_node_compatibility.py` — the house ratchet shape:
  hermetic, every assertion positive, each import inside the test that needs it.
- `pmoves/tools/fork_registry_ratchet.py` — the tool F3 extends; its
  `_validate_coverage` (`.gitmodules` → registry) is the shape
  `_validate_workflow_coverage` (registry → workflow) follows.
- `scripts/runbook_drift.py` — the instrument, and the artefact F1 fixes.
- `pmoves/tests/tools/test_runbook_drift_fleet_closure_mutation_kill.py` — this
  lane's mutation-kill harness. **Seven** mutations — one per finding, plus the
  F4 pair (a platform-independent structural kill and a Windows-only
  behavioural one) — each of which
  must revert the **wiring** and put a **named** test red, with the restore
  byte-exact and asserted. It is modelled on
  `pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py`, and it inherits that
  harness's hard-won rules: the mutation window is held under a two-layer lock
  (threading + advisory file lock) because a mutation that is not exclusive is a
  self-healing grenade; the pytest child gets its own process group so a timeout
  can kill the whole tree; the kill signal is a **test name read from pytest's
  own short summary**, never a substring, so a collection error or a timeout
  cannot masquerade as a kill; and a PARAMETRIZED test's name is stripped of its
  parameter id before matching, or every parametrized case would be unkillable.
- `pmoves/tools/image_staleness_ratchet.py` — the F5 ratchet: per image, the
  builder fields, the build inputs and a build path that needs no human click.
- `pmoves/tools/measure_schedule_contention.py` — the instrument behind the
  schedule-contention comment in `.github/workflows/build-images.yml`. It is
  IN THE TREE because a measurement that survives only in prose is a claim
  (lesson 25), it fails CLOSED on an unreadable workflow file rather than
  dropping it silently, and it COMPUTES each schedule's weekly frequency from
  the parsed cron fields rather than being handed a ratio — which is how a
  hand-written "365x" was caught and corrected to 84.
- `pmoves/tests/tools/test_measure_schedule_contention.py` — the gate for that
  instrument, including the LIVE rot gate: the real fleet is re-read and the
  04:23 slot is re-checked against every self-hosted schedule on every PR, so
  the comment's claim cannot rot into a falsehood unnoticed.
- `pmoves/tests/tools/test_runbook_drift_learnings_taxonomy.py` — the gate for
  THIS file's bucket summary: it recomputes the per-class counts from the
  lesson table and asserts they agree, so the one number in the file nobody
  re-derives is derived.
- `pmoves/tests/tools/test_windows_posix_ratchet.py` — the F4 ratchet: an AST
  sweep for module-scope POSIX-only `os.*` calls across `pmoves/**/*.py`, with
  the house guard pattern (`hasattr(os, "geteuid") and os.geteuid() == 0`) as its
  accepted shape and a `sys.platform == "win32"` guard as the other.
