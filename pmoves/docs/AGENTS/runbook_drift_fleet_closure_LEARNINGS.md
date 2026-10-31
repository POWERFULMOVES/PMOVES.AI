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

---

## What shipped, and what proves it

| Finding | Code | Tests | Gate |
|---|---|---|---|
| **F1** the probe grepped content | `scripts/runbook_drift.py` — `_origin_main_paths()`, `_working_tree_paths()`, `_paths_named()`, `_paths_ending()`, `_submodule_paths()`, `_is_gitignored()` | `pmoves/tests/test_runbook_drift_probe.py` (15) | the auditor itself; `pmoves/tests/test_runbook_drift_root.py` (8) |
| **F2** node-registry could not run | `pmoves/services/node_registry/{__init__,api,main,registry}.py` (port), `Dockerfile`, `requirements.txt`, `pmoves/docker-compose.yml` (service block), `pmoves/mk/node-registry.mk`, `pmoves/Makefile` (include) | `pmoves/tests/tools/test_node_registry_deployment.py` (6) | `make -C pmoves compose-provenance-audit`; `docker compose config` in `hardening-validation.yml`; `make -C pmoves validate-command-anchors` (5 stale ghost findings dropped) |
| **F2b** the consumers of the moved port | `pmoves/services/work_marshaling/{__init__,main}.py` (5), `pmoves/services/vllm_orchestrator/tensorzero.py` (1) | covered by the F2 sweep's `>= 6` non-vacuity assertion plus the F2 test | — |
| **F3** six claimed forks, no mechanism | `pmoves/config/fork_registry.json`, `.github/workflows/fork-sync.yml` (both lists + the GH App `repositories:` scope) | `pmoves/tools/tests/test_fork_registry_ratchet.py` (17) | `.github/workflows/fork-registry-ratchet.yml` |
| **F4** a module-scope POSIX call | `pmoves/tools/env_local_key.py`, `pmoves/tests/tools/test_env_local_key.py`, `pmoves/tests/test_secrets_audit_unreadable.py` | `pmoves/tests/tools/test_windows_posix_ratchet.py` (14) | the AST ratchet itself |
| **F5** nothing rebuilt the images | `.github/workflows/build-images.yml` (`schedule:` trigger, job renamed `Manual Image Build` -> `Image Build`) | `pmoves/tools/tests/test_image_staleness_ratchet.py` (14) | `.github/workflows/image-staleness-ratchet.yml` |

**The mutation-kill harness** — `pmoves/tests/tools/test_runbook_drift_fleet_closure_mutation_kill.py`
— is the lane's own proof. Six mutations, each reverting the WIRING rather than
a neighbouring condition, each required to put a NAMED test red, with the
restore byte-exact and asserted, all under a two-layer mutation lock:

| Mutation | Reverts | Named test that must go red |
|---|---|---|
| F1 | the path branch's matcher (`_paths_ending` -> `_paths_named`) | `test_a_path_claim_is_not_satisfied_by_an_unrelated_file_of_the_same_name` |
| F2 | `api.py`'s own default (`port: int = 8115` -> `8082`) | `test_node_registry_code_default_and_compose_binding_match_catalog_port` |
| F2 | the compose host binding (`:8115:8115` -> `:8082:8082`) | the same test — one named test, two wirings, two mutations |
| F3 | a claimed fork out of the workflow's `FORKS` list | `test_every_sync_true_registry_fork_is_in_the_workflow_forks_block` |
| F4 | the unconditional `os.fchmod` | `test_env_local_key_never_emits_a_raw_traceback` |
| F5 | the `schedule:` rebuild trigger | `test_real_workflow_has_a_non_manual_trigger` |

**Measurements, before -> after**

| | before | after |
|---|---|---|
| drift auditor (7 files, 160 claims) | 99 VERIFIED / 59 UNDECIDED / 2 DRIFTED | 122 VERIFIED / 27 UNDECIDED / 11 DRIFTED (all 11 re-verified genuine) |
| Windows-collectable tests | 71 hidden behind 2 collection errors | 71 collect; 76 passed / 9 skipped on the operator's host |
| fork registry | 84 forks / 33 `sync: true`; 31 in each workflow list | 86 forks / 35 `sync: true`; 39 in each list, membership-identical |
| node-registry deployability | no Dockerfile, no compose entry, no Make target | all three, plus the port agreement across source + compose + catalogue |

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
  lane's mutation-kill harness. Five mutations, one per finding, each of which
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
- `pmoves/tests/tools/test_windows_posix_ratchet.py` — the F4 ratchet: an AST
  sweep for module-scope POSIX-only `os.*` calls across `pmoves/**/*.py`, with
  the house guard pattern (`hasattr(os, "geteuid") and os.geteuid() == 0`) as its
  accepted shape and a `sys.platform == "win32"` guard as the other.
