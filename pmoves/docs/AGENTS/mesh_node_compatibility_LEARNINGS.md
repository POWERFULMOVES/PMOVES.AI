# mesh_node_compatibility_LEARNINGS.md

**Lane:** the mesh announcement plane ↔ the node registry — the R8 / R8a rows of
`pmoves/docs/AGENTS/PRE_RESTART_PREFLIGHT_2026-08-25.md`, open since 2026-08-25.
**Branch:** `feat/minimax-client-pmoves-parity` (PR #3418).
**Taxonomy:** 4 buckets · 5 classes, as used across the PMOVES lanes.

---

## What was broken

Five defects, all recorded before the fix and all confirmed against source:

| # | Defect | The symptom |
|---|--------|-------------|
| D1 | `pmoves/services/mesh_exposure/tests/test_app.py` asserted `len(reg) == 12` | The curated dir held **13** entries after `crush.yaml` landed on 2026-08-05 (PR #2412). The assertion was **RED for twelve weeks**: a count cannot say *which* entry moved, and a red test in an optional service suite is easy to miss. |
| D2 | `pmoves/services/resource-detector/` was kebab-case while every importer wrote `..resource_detector.*` | `pmoves.services.resource_detector` did not exist. Four services could not be imported at all. |
| D3 | `node-registry/main.py` loaded its own submodules with `spec_from_file_location` and no parent package | `from .config import …` raised "attempted relative import with no known parent package". The service could not start. |
| D4 | `mesh-agent` published `mesh.node.announce.v1`; the registry subscribed to `compute.nodes.announce.v1` | Two finished halves wired to different subject strings. The subject with zero publishers had a subscriber; the subject with every publisher had none. |
| D5 | No JetStream stream named `compute` was ever created | The registry's durable subscribe raised and the service **silently fell back to core NATS**, losing every announcement published while it was down. |

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **reasoning-gap** | A hard-coded **count** cannot say *which* thing moved; name the set. | `assert len(reg) == 12` stayed red for twelve weeks after `crush.yaml` landed (PR #2412). 13 ≠ 12 was never investigated because a count cannot point at the entry. Replaced with the declared slug set, resolved from the real curated directory, so the check is cwd-independent and says which apps the mesh exposes. | Any assertion about "the set has not changed unexpectedly". |
| 2 | **semantic-naming drift** | The **import name** and the **directory name** must be one thing; when they disagree, rename the directory rather than alias it. | `resource-detector/` vs `..resource_detector` made four services unimportable; `node-registry/` vs `pmoves.services.node_registry` broke every relative import. Renaming made the docstrings true instead of maintaining an alias that can drift. The same class was found in `work-marshaling/` and `vllm-orchestrator/`, whose docstrings already promised `from pmoves.services.work_marshaling import …` and `from pmoves.services.vllm_orchestrator import …` — **both were lies**. | A package whose importers, docstrings and directory disagree. |
| 3 | **contract-correctness** | Publisher and subscriber are **one** contract: a subject with no publisher is a silent void, and a subscriber on a subject nobody publishes is a silent deaf ear. | `compute.nodes.announce.v1` (0 publishers) vs `mesh.node.announce.v1` (mesh-agent + the bootstrap scripts + `agent_registry.yaml` + the graphiti subject registry). Fixed on the subscriber side, because that is the side with publishers; the two halves now agree and the ratchet asserts it. | Any NATS/queue/event subject pair. |
| 4 | **defense-in-depth** | A parser that expects one shape silently drops every other shape — normalise dialects at the boundary instead of re-raising. | The registry fed announcements to `NodeCapabilities.from_nats_message()`; all three real dialects (mesh-agent v1/v2, bootstrap scripts) lack `node_id`/`hostname` → `KeyError` → an **empty registry**. `capabilities_from_announcement()` now maps all of them and **refuses to invent capacity** (zero available slots unless the announcement states them). | Any consumer of a shared bus with more than one producer. |
| 5 | **pattern-conformance** | A file-path load is not a package import: register the module in `sys.modules` under its canonical name or its relative imports have no parent. | `spec_from_file_location` without `sys.modules[…] = module` → "attempted relative import with no known parent package". Worse, loading the same package by file path under a second name produced **two module objects** — two `VLLMOrchestrator` classes, two `WorkMarshaling` classes — so every `isinstance` check across the two import paths would silently fail. Fixed by making the directories real packages and importing them canonically: **one** module identity. | Any service whose directory name is not a valid package name. |
| 6 | **reasoning-gap** | **A test that tolerates a vocabulary the product ignores is worse than no test** — it certifies the blind spot. | `crush.yaml` was authored against `layer_1..layer_4` (the CRUSH_IN_PINOKIO_PLAN handoff) while `mesh_exposure/state.py` reads `l1_venv` / `l2_container_same_host` / `l3_mesh` / `l4_public`. The entry **parsed**, so an alias-tolerant layer check was happy — but the planner saw crush as having **no exposure contract at all**: the mesh was blind to a curated app the registry listed. The alias was removed, the entry migrated, and the check is now exact so a future legacy-vocabulary entry fails loudly. | Any tolerance between a checker and the thing that consumes the data: the check must use the **consumer's** vocabulary, not a superset. |
| 7 | **reasoning-gap** | A docstring is a **contract**, not decoration: "Usage: `from pmoves.services.X import …`" is a promise that someone will paste. | `work-marshaling/__init__.py` and `vllm-orchestrator/__init__.py` both documented snake_case imports that could not work, because the directories were kebab-case. The rename made the promise true. An unreachable `Usage:` block is a defect with a future incident attached. | Any `Usage:` / `Examples:` block that names an import path. |
| 8 | **contract-correctness** | A **retention policy** is part of the subscription contract, not a tuning knob. | The `compute` stream is created with `limits` retention, not `interest`. Under `interest` retention a message with no currently bound consumer is accepted and immediately discarded — and the registry's durable consumer is created **lazily** on its first connect, so every announcement published before the registry first ran would have been silently dropped. The same silent-discard hazard the sibling streams document. | Any stream whose consumer is created lazily. |
| 9 | **defense-in-depth** | A **dead** subscription is not a fallback. | The registry's JetStream subscribe passed `durable_name=` — **not a nats-py kwarg** (`js.subscribe(subject, cb, durable, stream, …)`) — so it always raised and silently fell back to core NATS. The service looked alive and was losing data. Fixed to `durable=`, and the ratchet asserts the durable consumer is actually configured. | Any call whose failure is caught and downgraded to a weaker mode. |
| 10 | **semantic-naming drift** | **An API call is a contract with the installed library** — and a permissive stub will agree with it forever. | `node_registry/main.py` configured structlog with `cache_class=structlog.WriteLogFile`. **Neither half has ever existed in a released structlog**: `WriteLogFile` is not exported by 21.5.0, 22.3.0, 24.4.0 (the pinned version) or 26.1.0 (what the unpinned `requirements-tests.txt` resolves to in the merge gate) — the wheels were unpacked and grepped to confirm — and `cache_class` is not in `configure()`'s signature in any of them (`processors`, `wrapper_class`, `context_class`, `logger_factory`, `cache_logger_on_first_use` only). So the module could not be **imported in any environment, ever**. Nothing noticed because nothing imported it until this ratchet did. The local run passed only because this file installs a **permissive structlog stub** when the package is absent, and that stub answers any attribute — CI, with the real package, was the first place the defect could be seen. FIX: the bogus kwarg is gone (`cache_logger_on_first_use=True` is the supported mechanism), and `test_the_entry_points_use_only_structlog_api_that_exists` now checks every `structlog.configure(...)` keyword and every `structlog.<attr>` against the **real** installed package — skipping with a reason when only the stub is present, and the stub now carries a `__pmoves_permissive_stub__` marker so no later check can mistake it for the real thing. | Any call into a third-party API whose signature can change between versions. |
| 11 | **reasoning-gap** | **A ratchet whose verdict depends on the HOST is not load-bearing** — pin the environment the verdict depends on. | `test_the_rendered_roster_is_created_owner_only` asserts the roster file's mode is exactly `0o600`. The defective path (`write_text()`) creates the file with `0o666 & ~umask`, so on a host whose umask is `0o077` the defect produces `0o600` — the same mode the fixed path produces — and the test **passed against the defect it exists to catch**. That is not hypothetical: the mutation-kill case M9 (which reintroduces `write_text()`) **survived** on the CI merge gate, whose container umask is `0o077`, while it died on a developer machine with the usual `0o022`. Measured on a real POSIX filesystem: umask `0o077` → fixed `0600`, mutated `0600` → not killed; umask `0o022` → fixed `0600`, mutated `0644` → killed. FIX: the test pins the umask to `0o022` around the write and restores it in a `finally` (it is process-global). The fixed path still passes because it asks for `0o600` **explicitly**; the defective path then yields `0o644` and the assertion fails **in every environment**. | Any assertion whose outcome depends on umask, locale, TZ, PATH order, hash seed, or filesystem defaults. |

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 4 lessons (#1, #6, #7, #11) — a count cannot name what moved; a tolerant test certifies a blind spot; a `Usage:` block is a contract; a host-dependent verdict is not a verdict.
- **(2) semantic-naming drift** — 2 lessons (#2, #10) — the directory name and the import name must be one thing; an API call is a contract with the installed library.
- **(3) contract-correctness** — 3 lessons (#3, #8, #9) — publisher/subscriber are one contract; retention is part of it; a dead subscription is not a fallback.
- **(4) defense-in-depth** — 2 lessons (#4, #5) — normalise dialects at the boundary; a file-path load is not a package import.
- **(5) pattern-conformance** — 1 lesson (#5's sibling rule, folded into #5) — the canonical import shape.

Pattern: **reasoning-gap and contract-correctness dominate** — 7 of 11 lessons. Every one of them is a case where a thing *parsed* but did not *mean* what it appeared to mean: a count that was merely wrong, a layer name that was merely different, a subscription that was merely alive, a mode that was merely right.

---

## The ratchet

`pmoves/tests/tools/test_mesh_node_compatibility.py` — **hermetic**: no network, no NATS,
no containers. Every assertion is read out of the source tree, and every import happens
**inside** the test that needs it, so a broken import fails *that named test* rather
than collapsing the whole module at collection time.

Every assertion is **positive** — "the bad string is nowhere in the repo" is a statement
about absence, and absence cannot say no. Each test names the thing that must BE true.

`pmoves/tests/tools/test_mesh_node_compatibility_mutation_kill.py` — **the harness must
MUTATE THE PRODUCTION SOURCE and run the real test file.** It never restates the
assertion it expects to fail.

| Mutation | What it breaks | The named test that must go red |
|---|---|---|
| M1 | the registry subscribes to the old, unpublished subject again | `test_the_registry_subscribes_to_the_subjects_the_mesh_publishes` |
| M2 | the package directory goes back to its kebab-case name | `test_the_four_services_import_under_their_canonical_package_names` |
| M3 | work-marshaling stops reaching the canonical `resource_detector` package | `test_the_four_services_import_under_their_canonical_package_names` |
| M4 | the vllm-orchestrator entry point stops importing its canonical package | `test_the_service_entry_points_resolve_their_imports_without_a_package` |
| M5 | the COMPUTE stream stops covering the announce family | `test_the_compute_stream_carries_the_announce_family` |
| M6 | a curated entry disappears | `test_the_curated_registry_set_matches_the_curated_directory` |
| M7 | a curated entry reverts to the legacy layer vocabulary | `test_the_curated_entries_declare_the_canonical_exposure_layers` |

Each case asserts **green-before → red-after (the named test) → green-after-restore**,
and the suite has a baseline case that proves it is green before any mutation — a suite
that is red for an unrelated reason would make every mutation look "killed".

---

## SDK provenance

| File | Change |
|---|---|
| `pmoves/services/node_registry/` (was `node-registry/`) | 5 files renamed; `main.py` loads by canonical package with a script-mode fallback; `registry.py` subscribes to the announce family with `durable=` and parses every published dialect; the structlog `cache_class=structlog.WriteLogFile` call — an API that has never existed — is gone |
| `pmoves/services/resource_detector/` (was `resource-detector/`) | 5 files renamed; `main.py` registers the canonical package; the lazy import is now `from pmoves.services.resource_detector import …` |
| `pmoves/services/work_marshaling/` (was `work-marshaling/`) | 2 files renamed; `main.py` uses the canonical import; `__init__.py` imports the shared models absolutely |
| `pmoves/services/vllm_orchestrator/` (was `vllm-orchestrator/`) | 8 files renamed; `main.py` uses the canonical import and no longer executes `server.py` a second time |
| `pmoves/services/mesh-agent/main.py` | `MESH_ANNOUNCE_SUBJECT_V1/V2` + `MESH_SHAPE_HANDSHAKE_SUBJECT` as named constants; the publish sites use them |
| `pmoves/scripts/nats/init_streams.sh` | the `COMPUTE` stream (`mesh.node.announce.> compute.nodes.>`, `limits`, 7d/1GB) |
| `pmoves/scripts/nats/validate_streams.py` | `EXPECTED_STREAMS` gains the `COMPUTE` row |
| `pmoves/configs/pinokio-apps/curated/crush.yaml` | the exposure layers migrate to the canonical names |
| `pmoves/services/mesh_exposure/tests/test_app.py` | the count becomes the declared slug set; the layer check is alias-free and exact |
| `pmoves/tests/tools/test_mesh_node_compatibility.py` | NEW — the ratchet |
| `pmoves/tests/tools/test_mesh_node_compatibility_mutation_kill.py` | NEW — the mutation-kill harness |
| `README.md`, `pmoves/docs/operations/SCRIPTS_AND_TESTS_GUIDE.md` | the renamed service paths |
| `pmoves/docs/AGENTS/PRE_RESTART_PREFLIGHT_2026-08-25.md` | a resolution log for R8 / R8a — the historical rows above it are unchanged |

## Cross-references

- `pmoves/docs/AGENTS/PRE_RESTART_PREFLIGHT_2026-08-25.md` — rows R8, R8a (the source of this lane) and the resolution log.
- `pmoves/services/mesh_exposure/state.py` — the planner that reads the canonical layer names only.
- `pmoves/services/mesh-agent/main.py` — the deployed publisher.
- `pmoves/config/agent_registry.yaml`, `pmoves/services/graphiti/nats_subject_registry.py` — the other declarers of `mesh.node.announce.v1`.
- `pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py` — the sibling lane's mutation-kill idiom.
- `pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md` — the sibling lane's "a ratchet that can only assert absence cannot say no".

## Deliberately NOT done (operator decisions)

1. **node-registry deployment wiring** — Dockerfile, compose entry, Make target. `pmoves/docker-compose.yml` was not touched.
2. **The port conflict** — `main.py` defaults to 8082; the catalog and the docs say 8115. Resolve before wiring the compose entry.
3. **The service identity strings** stay hyphenated (`"service": "node-registry"`) while the Python packages are snake_case — the name is the wire contract, the package is the import contract.
