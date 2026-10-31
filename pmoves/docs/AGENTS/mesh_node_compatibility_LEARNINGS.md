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

### The merge-gate findings (2026-10-31) — F1 … F6

Six further findings, raised by the review of PR #3418. Every one was
confirmed against the source before it was accepted, and two of them are
recorded here **against the finding's own wording**, because the honest
version of a finding is the one that survives measurement.

| # | Defect | The symptom |
|---|--------|-------------|
| F1 | `init_streams.sh` declared the COMPUTE subjects space-separated: `--subjects "mesh.node.announce.> compute.nodes.>"` | **NOT a broken stream** — measured: the pinned CLI's `splitCLISubjects` splits on `,|\t|\s`, so the space-separated form created TWO subjects against nats-box 0.14.5 (nats CLI v0.1.5) and against v0.5.1 alike. What the old form lacked was the **canonical, version-stable list form** — the one the validator reads back out of `nats stream info -j`. |
| F2 | `registry.py` asked for `stream="compute"`; `init_streams.sh` creates `COMPUTE` | JetStream stream names are **case-sensitive**. Every subscribe raised and the registry fell back to core NATS — the same data loss D5 described, one capital letter away. |
| F3 | The registry held a SECOND core-NATS subscription on `mesh.node.announce.v1` ("heartbeat") beside the JetStream family subscription | Every announcement was delivered **twice**, and the JetStream subscription was never appended to `_subscriptions`, so `stop()` left it alive and it **leaked on every restart**. |
| F4 | An ISO-8601 announcement timestamp with an offset produced an **aware** datetime; the store compares `last_heartbeat` against a **naive** clock | `datetime.now() - aware` raises `TypeError: can't subtract offset-naive and offset-aware datetimes` — `list_online()` died and the node record could not be evaluated at all. |
| F5 | `validate_streams.py` parsed a `NAME SUBJECTS RETENTION` table that the nats CLI **never emits** | `stream ls -n` prints NAMES ONLY; `stream ls` has no Subjects column and no Retention column. The guard was reading a format the tool does not produce, so it **could not have passed against a real server** — it was decoration wearing a uniform. |
| F6 | `test_the_rendered_roster_is_created_owner_only` asserted the roster's **FINAL** mode | The generator ALSO `os.chmod`s the file to `0o600` after the write, so the final mode is `0o600` on BOTH the fixed and the defective path. The assertion was structurally blind to the world-readable **WINDOW** — which is why mutation-kill case M9 was **UNKILLABLE**. |


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
| 12 | **contract-correctness** | **The producer and the reader of a LIST must agree on the list form** — and a finding must not claim a defect the measurements do not show. | The COMPUTE stream declares two subject families. The old `--subjects "mesh.node.announce.> compute.nodes.>"` was NOT broken: the nats CLI's `splitCLISubjects` splits on `,|\t|\s`, so the space-separated form created two subjects against the pinned nats-box 0.14.5 (CLI v0.1.5) and against v0.5.1 too — measured, not assumed. What the form lacked was the **canonical list form**: unambiguous, documented, and the one the validator reads back out of `nats stream info -j`. A subject may not contain a space (the server answers `invalid subject (10052)`), so the separator must be one the CLI strips — and a comma is the only separator that is never part of a subject. The lesson is BOTH halves: use the canonical form, and report the finding in the words the measurement supports. | Any producer whose output is parsed by another tool in the same repo. |
| 13 | **semantic-naming drift** | **A stream NAME is data, not a label** — the constant must be the byte-for-byte name the creator makes. | `ANNOUNCE_STREAM = "compute"` against a stream created as `COMPUTE`. JetStream stream names are case-sensitive, so the subscribe raised, the exception was swallowed by the fallback, and the registry quietly ran on core NATS — the same data loss D5 described, one capital letter away. The ratchet now compares the registry's constant, `init_streams.sh`'s `add_stream` name and the validator's expectation **against each other**, so a rename on any one side fails. | Any identifier that crosses a process or a service boundary. |
| 14 | **reasoning-gap** | **A second subscription on the same subject is not redundancy** — it is a second delivery of every message, and it hides the fact that the family subscription already covered it. | The mesh has no separate heartbeat subject: it re-announces every `ANNOUNCE_SEC`, so the announcement IS the heartbeat. The registry nevertheless held a core-NATS subscription on `mesh.node.announce.v1` beside the JetStream family subscription, so every announcement was delivered twice, and the "heartbeat" row in the `SUBJECTS` table kept the fiction alive. Worse, the JetStream subscription was never appended to `_subscriptions`, so `stop()` never tore it down and it leaked on every restart. The ratchet now asserts the EXACT SET of core-NATS subscribed subjects and that the JetStream subscription is tracked and unsubscribed by `stop()`. | Any broker where one family subscription already covers the messages. |
| 15 | **contract-correctness** | **A store's clock and the values it stores must speak the same convention** — naive vs aware is not a detail, it is a `TypeError`. | `datetime.fromisoformat("…+05:00")` returns an AWARE datetime; the store compares `last_heartbeat` against `datetime.now()`, which is NAIVE. `now - aware` raises, so `list_online()` died and the node record could not be evaluated. Every value that ENTERS the store is now converted to UTC and stripped of its tzinfo — at the announcement boundary (`timestamp_from_announcement`), at the HTTP heartbeat boundary (`api.py`) and at the Supabase read boundary (`storage._parse_datetime`, a TIMESTAMPTZ column hands back an offset). A datetime that is already naive is left UNCHANGED: it is already in the store's convention and rewriting it would move a value the publisher meant literally. | Any store that compares a stored value with a clock. |
| 16 | **reasoning-gap** | **A guard that parses a format the tool never emits is not a guard** — it is decoration wearing a uniform. | `validate_streams.py` parsed `NAME SUBJECTS RETENTION` out of `nats stream ls -n`. Measured against nats-box 0.14.5: `stream ls -n` prints **NAMES ONLY**, and `stream ls` prints Name / Description / Created / Messages / Size / Last Message — no Subjects column, no Retention column. The only output that carries both is `nats stream info <NAME> -j`. So the old guard could not have passed against a real server, and nothing noticed because nothing ran it against one. The contract is now the REAL one: the concatenated JSON of one `stream info -j` per stream, walked with `JSONDecoder().raw_decode` (`json.loads` accepts exactly one object per document), with the subjects compared as **SETS** because JetStream promises no order and COMPUTE carries two families. | Any guard whose input is another tool's output. |
| 17 | **reasoning-gap** | **Assert the mode a file was BORN with, not only the mode it ended with** — a final state cannot see a window. | `mcp_config_generator.py` writes the roster with `os.open(…, 0o600)` and THEN runs `os.chmod(output_path, 0o600)`. The trailing chmod makes the FINAL mode `0o600` on the fixed path AND on the defective `write_text()` path, so the final-mode assertion certified the defect and mutation-kill case M9 was **unkillable** — the suite agreed with the code it was supposed to police. FIX: a wrapper around `os.chmod` records the mode the file has at the moment the generator asks to tighten it — the last instant of the window — and the test asserts that BIRTH mode is `0o600`, and that a birth mode was observed at all ("no observation" is a FAILURE, not a pass). Measured on a real POSIX filesystem: fixed `0600`, mutated `0644` → killed, and the kill is the birth-mode assertion, not an error in the hook. | Any assertion about a secret file, and any state that a later step can repair. |

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 7 lessons (#1, #6, #7, #11, #14, #16, #17) — a count cannot name what moved; a tolerant test certifies a blind spot; a `Usage:` block is a contract; a host-dependent verdict is not a verdict; a second subscription is a duplicate delivery; a guard that parses a format the tool never emits is decoration; a final state cannot see a window.
- **(2) semantic-naming drift** — 3 lessons (#2, #10, #13) — the directory name and the import name must be one thing; an API call is a contract with the installed library; a stream name is data, not a label.
- **(3) contract-correctness** — 5 lessons (#3, #8, #9, #12, #15) — publisher/subscriber are one contract; retention is part of it; a dead subscription is not a fallback; producer and reader must agree on a list form; a store's clock and its values must speak one convention.
- **(4) defense-in-depth** — 2 lessons (#4, #5) — normalise dialects at the boundary; a file-path load is not a package import.
- **(5) pattern-conformance** — 1 lesson (#5's sibling rule, folded into #5) — the canonical import shape.

Pattern: **reasoning-gap and contract-correctness dominate** — 12 of 17 lessons. Every one of them is a case where a thing *parsed* but did not *mean* what it appeared to mean: a count that was merely wrong, a layer name that was merely different, a subscription that was merely alive, a mode that was merely right, a guard that was merely green.

---

## What was measured (2026-10-31, not assumed)

Every claim in the F1–F6 findings was measured against a real JetStream
server (`nats:2.11.8-alpine`, container `natsjs-probe`, port 14222) with the
pinned `natsio/nats-box:0.14.5` CLI (nats CLI v0.1.5) and, for the subject
splitter, with nats CLI v0.5.1 as well.

| Question | Measured answer |
|---|---|
| Does `nats stream ls -n` carry subjects or retention? | **No** — names only. |
| Does `nats stream ls` carry subjects or retention? | **No** — Name / Description / Created / Messages / Size / Last Message. |
| What DOES carry both? | `nats stream info <NAME> -j` → `config.subjects` + `config.retention`. |
| Does `nats stream info <MISSING> -j` print anything? | **No** — non-zero exit, EMPTY stdout (the error goes to stderr), so a missing stream contributes no JSON object and the validator reports it MISSING. |
| Does the space-separated `--subjects` form work? | **Yes** — `splitCLISubjects` splits on `,|\t|\s`, so `"a.> b.>"` created TWO subjects (CLI v0.1.5 and v0.5.1). |
| Does a subject containing a literal SPACE work? | **No** — the server answers `invalid subject (10052)`. |
| Does the comma-separated form work? | **Yes** — `stream add --subjects "f1probe.a.>,f1probe.b.>"` produced `subjects: ["f1probe.a.>", "f1probe.b.>"]`. |
| Can one `json.loads` read the concatenated capture? | **No** — one object per document. `JSONDecoder().raw_decode` in a loop read both objects correctly. |
| What mode is the roster born with? | Fixed path `0600`, mutated (`write_text()`) `0644` under umask `0o022` — measured on a real POSIX filesystem (WSL Ubuntu 22.04). |


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
| M8 | the COMPUTE subject list goes back to the space-separated form | `test_the_compute_stream_declares_its_subjects_as_a_comma_separated_list` |
| M9 | the registry asks for the lowercase stream name again | `test_the_registry_and_the_stream_script_name_the_same_stream` |
| M10 | the JetStream subscription is never tracked, so `stop()` leaks it | `test_the_registry_tears_down_its_jetstream_subscription` |
| M11 | the registry stops normalising an aware announcement timestamp | `test_every_datetime_that_enters_the_store_is_naive` |
| M12 | the HTTP heartbeat endpoint stops normalising its timestamp | `test_every_datetime_that_enters_the_store_is_naive` |
| M13 | the validator reads only the FIRST JSON object of the capture | `test_the_validator_reads_the_real_stream_info_contract` |
| M14 | the validator compares the subject list as an ORDERED tuple | `test_the_validator_matches_a_two_subject_stream_by_set` |

Each case asserts **green-before → red-after (the named test) → green-after-restore**,
and the suite has a baseline case that proves it is green before any mutation — a suite
that is red for an unrelated reason would make every mutation look "killed".

M5's anchor was re-pointed at the comma-separated subject line when F1 changed it —
an anchor that no longer matches the source would make the harness stale, and a stale
harness silently passes.

### The sibling harness: the roster provisioning lane

`pmoves/tests/tools/test_minimax_roster_provisioning_mutation_kill.py` holds the
**M9** case that the CI merge gate exposed as UNKILLABLE. It is a different file
from the mesh harness above, and it is the one the merge gate flagged:

| Mutation | What it breaks | The named test that must go red |
|---|---|---|
| M9 | the roster is written with `write_text()` and chmod'd afterwards | `test_the_rendered_roster_is_created_owner_only` |

It was unkillable because the test asserted the **FINAL** mode, and the
generator's trailing `os.chmod` makes the final mode `0o600` on both paths.
The test now asserts the **BIRTH** mode, observed through a wrapper around
`os.chmod`. The harness also gained an `EXPECTED_FAILURE_REASON` map: a kill
that is not the expected assertion is a kill by an unrelated error, and proves
nothing about the defect. M9 remains POSIX-only (Windows has no mode bits),
so its kill was verified on a real POSIX filesystem — WSL Ubuntu 22.04, Python
3.10.12, pytest 8.4.2 — not on the Windows host.

---

## SDK provenance

| File | Change |
|---|---|
| `pmoves/services/node_registry/` (was `node-registry/`) | 5 files renamed; `main.py` loads by canonical package with a script-mode fallback; `registry.py` subscribes to the announce family with `durable=` and parses every published dialect; the structlog `cache_class=structlog.WriteLogFile` call — an API that has never existed — is gone |
| `pmoves/services/resource_detector/` (was `resource-detector/`) | 5 files renamed; `main.py` registers the canonical package; the lazy import is now `from pmoves.services.resource_detector import …` |
| `pmoves/services/work_marshaling/` (was `work-marshaling/`) | 2 files renamed; `main.py` uses the canonical import; `__init__.py` imports the shared models absolutely |
| `pmoves/services/vllm_orchestrator/` (was `vllm-orchestrator/`) | 8 files renamed; `main.py` uses the canonical import and no longer executes `server.py` a second time |
| `pmoves/services/mesh-agent/main.py` | `MESH_ANNOUNCE_SUBJECT_V1/V2` + `MESH_SHAPE_HANDSHAKE_SUBJECT` as named constants; the publish sites use them |
| `pmoves/scripts/nats/init_streams.sh` | the `COMPUTE` stream (`mesh.node.announce.>,compute.nodes.>`, `limits`, 7d/1GB) |
| `pmoves/scripts/nats/validate_streams.py` | `EXPECTED_STREAMS` gains the `COMPUTE` row; the input contract is replaced with the real one (concatenated `nats stream info -j` JSON, parsed with `raw_decode`, subjects compared as SETS) |
| `pmoves/Makefile` | `nats-streams-validate` captures `stream info <NAME> -j` per stream inside ONE `docker run` (no `jq`), instead of the fictional `stream ls -n` table |
| `pmoves/services/node_registry/registry.py` | `ANNOUNCE_STREAM` is `COMPUTE`; the duplicate heartbeat subscription is gone; the JetStream subscription is tracked and torn down by `stop()`; `timestamp_from_announcement` normalises to the store's naive convention |
| `pmoves/services/node_registry/storage.py` | `naive_utc()` — the store's convention helper; `_parse_datetime` normalises the Supabase TIMESTAMPTZ read path |
| `pmoves/services/node_registry/api.py` | the HTTP heartbeat timestamp is normalised before it enters the store |
| `pmoves/configs/pinokio-apps/curated/crush.yaml` | the exposure layers migrate to the canonical names |
| `pmoves/services/mesh_exposure/tests/test_app.py` | the count becomes the declared slug set; the layer check is alias-free and exact |
| `pmoves/tests/tools/test_mesh_node_compatibility.py` | NEW — the ratchet |
| `pmoves/tests/tools/test_mesh_node_compatibility_mutation_kill.py` | NEW — the mutation-kill harness |
| `pmoves/tests/test_minimax_mcp_roster_provisioning.py` | the roster test asserts the BIRTH mode through an `os.chmod` wrapper, not only the final mode |
| `pmoves/tests/tools/test_minimax_roster_provisioning_mutation_kill.py` | `EXPECTED_FAILURE_REASON` — a kill must be the expected assertion, not an unrelated error |
| `pmoves/docs/specs/nats-broker-deploy-slice3-streams-2026-08-01.md` | the `-n` capture contract is corrected to the real `stream info -j` one |
| `README.md`, `pmoves/docs/operations/SCRIPTS_AND_TESTS_GUIDE.md` | the renamed service paths |
| `pmoves/docs/AGENTS/PRE_RESTART_PREFLIGHT_2026-08-25.md` | a resolution log for R8 / R8a — the historical rows above it are unchanged |

## Cross-references

- `pmoves/docs/AGENTS/PRE_RESTART_PREFLIGHT_2026-08-25.md` — rows R8, R8a (the source of this lane) and the resolution log.
- `pmoves/services/mesh_exposure/state.py` — the planner that reads the canonical layer names only.
- `pmoves/services/mesh-agent/main.py` — the deployed publisher.
- `pmoves/config/agent_registry.yaml`, `pmoves/services/graphiti/nats_subject_registry.py` — the other declarers of `mesh.node.announce.v1`.
- `pmoves/tests/tools/test_mcp_inventory_endpoint_mutation_kill.py` — the sibling lane's mutation-kill idiom.
- `pmoves/docs/AGENTS/test_gap_ratchet_LEARNINGS.md` — the sibling lane's "a ratchet that can only assert absence cannot say no".
- `pmoves/docs/specs/nats-broker-deploy-slice3-streams-2026-08-01.md` — the slice-3 spec, with the capture-contract correction.
- `pmoves/tools/mcp_config_generator.py` — the roster writer: `os.open(…, 0o600)` then `os.chmod(…, 0o600)`. The two steps are why the FINAL mode is blind to the window.

## Deliberately NOT done (operator decisions)

1. **node-registry deployment wiring** — Dockerfile, compose entry, Make target. `pmoves/docker-compose.yml` was not touched.
2. **The port conflict** — `main.py` defaults to 8082; the catalog and the docs say 8115. Resolve before wiring the compose entry.
3. **The service identity strings** stay hyphenated (`"service": "node-registry"`) while the Python packages are snake_case — the name is the wire contract, the package is the import contract.
