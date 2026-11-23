# silent_bind_ratchet_LEARNINGS.md

**Lane:** silent-bind ratchet — the static twin of `make -C pmoves net-reality`, plus the smoke-suite wiring that makes a refused HTTP connection distinguishable from a refused *published* port
**Author:** Mavis (mvs_ce8c1e6e34434db1ba42d3b822ecbd15) · **Operator:** DARKXSIDE
**Active:** 2026-11-22 · **Companion CLAIM row:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (branch `fix/silent-bind-declared-host-ports-2026-11-22`)
**Branch:** `fix/silent-bind-declared-host-ports-2026-11-22`

**Remediation lane:** `fix/silent-bind-remediate-tier-2026-11-22` — the operator's
2026-11-23 tier decision landed here: attach `pmoves_public` to every measured
gap, and rebind every wide host bind to `127.0.0.1`. Lessons 14-19 belong to
that lane; the baseline is now EMPTY and the gate fails on any new gap.

---

## Operator direction (verbatim)

> "hhmm sounds like handrolled without loading the dice first lets get doc provenance on to ensure tools scripts work"

> "I also meant check the tools themselves against the relevant latest source docs"

Those two sentences are the load-bearing inputs to this slice, and they are
the reason the lane's first commit is **instruments, not remediation**. The
operator did not ask for another gate; they asked for the tools to be
*right* — sourced from the house's own instruments and checked against the
upstream source docs — before anything was changed in production compose.

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **pattern-conformance** | **The house already owns the instrument.** A hand-rolled compose transform was written first and then deleted in the same session: it edited the generated split overlays by hand and wrote `PMOVES_NETWORKS=` by hand. Both are owned by the house — `scripts/split_compose.py` GENERATES the overlays and the Makefile says "Never hand-edit them (damage-control blocks it)"; `scripts/inject_pmoves_networks.py` MIRRORS each service's `networks:` into `PMOVES_NETWORKS=` and is drift-gated by `make -C pmoves compose-networks-check`. The hand-rolled transform would have been undone by both. | `pmoves/Makefile:6001-6035` (`compose-split` / `compose-split-check` / `compose-networks` / `compose-networks-check`); `pmoves/scripts/inject_pmoves_networks.py` docstring ("The SOURCE file is mutated … both must agree"); `pmoves/scripts/split_compose.py`. The flow that is correct is: edit `networks:` in `pmoves/docker-compose.yml` → `make -C pmoves compose-networks` → commit the regenerated overlays. | Any change to a compose file's `networks:` or `ports:` block in this repo. |
| 2 | **reasoning-gap** | **A "first declaration wins" network map silently degrades to UNKNOWN.** Ten files in the house scope re-declare `pmoves_api` / `pmoves_app` / `pmoves_bus` WITHOUT an `internal:` key, and `pmoves_app`/`pmoves_bus` are declared with a YAML **anchor** (`<<: *network-internal-only`). A global map built by "first file that mentions it wins" therefore resolved `pmoves_app` to UNKNOWN instead of `internal: true`, and the gate went blind to the split overlays. The resolution order must be explicit: the file's own `external: true` → UNKNOWN; the file's own `internal:` → that value; otherwise INHERIT from the canonical declarations in `docker-compose.yml` + `docker-compose.base.yml`; otherwise UNKNOWN. | Measured in this lane: the first-wins map reported `pmoves_app: internal=None` while the canonical file says `internal: true`, and 10 conflicting-flag messages fired across `docker-compose.jellyfin-ai.yml`, `.mcp-gateway.yml`, `.open-notebook.yml`, `.remote.yml`, `.rocm.override.yml`, `.sso.yml`, `.vps.override.yml`. With the canonical-inheritance rule the count is 73 (file, service) pairs across 39 services, and the tool and an INDEPENDENT measurement script agree on that number. | Any tool that resolves a named resource's property across a set of files that redeclare it. |
| 3 | **defense-in-depth** | **`all()` over an EMPTY set is True.** A service with no `networks:` key joins the file's DEFAULT network — a normal bridge — so its published port DOES bind. Scoring the empty set as "every network is internal" reports dozens of phantom gaps. The empty case is only a gap when the file declares its `default:` network with `internal: true`. | `pmoves/tools/silent_bind_ratchet.py::scan_file` (the `default_internal` guard) + mutation **M3** in `pmoves/tools/tests/test_silent_bind_ratchet_mutation_kill.py`, which removes the guard and MUST kill `test_service_without_networks_key_is_not_a_gap`. The vacuous-truth bug was found by MEASUREMENT, not by reading: the first measurement pass reported `activepieces-app` and `nginx` as gaps with an EMPTY network set. | Any tool that asks "are all of these X?" where the list may be empty. |
| 4 | **reasoning-gap** | **Detection must compare the REQUESTED binding to the ACTIVATED map PER KEY.** A text search for `"HostPort": null` catches only one of the two shapes Docker emits: `Ports["8084/tcp"] == null` (the whole entry null) and `Ports["8084/tcp"][0].HostPort == null` (the slot null). The grep misses the first entirely. This is the same class of measurement error the house's own `audit_network_reality.sh` had. | moby/moby#36174's own `docker container inspect` output — `HostConfig.PortBindings` holds the REQUESTED binding while `NetworkSettings.Ports` is `{}` — which is the authoritative shape for the comparison. Measured on the b850 runner: a text-grep detector reported 0 silent binds where a per-key JSON detector reported 15 containers / 16 ports. | Any Docker port-binding audit. |
| 5 | **contract-correctness** | **Upstream provenance AND house provenance are both required, and they say different things.** The upstream tracker (moby/moby#36174, OPEN) carries the mechanism and the maintainer's position — "As far as I'm aware, this is by design, and `--internal` networks should not be reachable, even with `-p` being used". The house doc carries the TIER and the remedy — `pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md` Rule 5, "There is no 'publish without egress.' Front it with a gateway", and the network table naming `pmoves_public` as the "Host-reachable + egress-capable" bridge. Citing only the tracker leaves the operator with a defect and no remedy; citing only the house doc leaves the claim unverifiable upstream. | `pmoves/tools/silent_bind_ratchet.py` docstring cites both, plus compose-spec `13-merge.md` for the merge semantics (mappings merge, so a service's network set across files is the UNION) and the sibling ratchet's "as deployed" model. | Any claim that a runtime platform behaves in a specific way. |
| 6 | **pattern-conformance** | **The house's own precedent on this class is to fix the AUDITORS first.** PMOVES's history on silent binds is three commits that repaired the DETECTION, not the compose files: `6baaaa1` and `fec0a97` ("the auditor that exists to catch silent binds was reporting…"), `de27bdb` ("three silent binds were passing as 'expected if you haven't run make up'"). The compose remediation was a separate decision. So the lane's first PR lands the instruments + the baseline that records the gaps; the remediation PR retires them and the baseline shrinks. | `git log` on the POWERFULMOVES/PMOVES.AI commits that reference moby/moby#36174 (visible on the upstream issue page itself). | When a lane's remediation changes production posture and the instruments are missing. |
| 7 | **contract-correctness** | **A baseline entry whose reason is a placeholder is not a decision.** The ratchet's generator writes `"REVIEW THIS"` for every measured gap; a baseline of placeholders reads exactly like a baseline of reviewed decisions. The gate therefore fails a recorded gap whose reason is empty or is still the placeholder, and the baseline may only SHRINK — a gap that was fixed but left listed fails as `STALE_GAP`. | `pmoves/tools/silent_bind_ratchet.py::run_check` (`STALE_GAP` + the placeholder rule) + mutations **M5** and **M6**; the house's own precedent is `pmoves/configs/hardening_ratchet/_compose_known_gaps.yaml` ("They are NOT approved, and none of them is 'expected'"). | Any recorded-exceptions list. |
| 8 | **defense-in-depth** | **A gate that cannot read its input must FAIL CLOSED, and "could not measure" must be its own exit code.** Three files in the house scope carry Compose's `!reset` / `!override` tags, which PyYAML rejects outright; and an unreadable compose file must be an `INSTRUMENT_ERROR`, not a skip. The house convention is exit 3 = COULD NOT MEASURE, which is NOT a pass — `make` collapses 1 and 3 to 2, so the tool is called directly when the distinction matters. | `pmoves/tools/silent_bind_ratchet.py::ComposeLoader` (`!reset` / `!override` constructors) + exit code 3 + mutation **M7**; the sibling `pmoves/tools/compose_hardening_ratchet.py` and the Makefile's note "(exit 1 = new/stale finding, exit 3 = COULD NOT MEASURE … call the tool directly when the distinction matters)". | Any gate that parses files it does not control. |
| 9 | **reasoning-gap** | **A URL port parser must not split on the colon INSIDE a substitution.** The smoke suite's URLs carry `"${VAR:-default}"`, and `##*:` cuts at the LAST colon — which is the one inside the substitution — yielding `":-default}"` instead of the port. The parser therefore matches the three authority shapes explicitly (host + substitution / bare substitution / host + digits) instead of splitting. The bug was found by the test, not by reading the code. | `pmoves/scripts/smoke-tests.sh::_http_port` + `pmoves/tools/tests/test_smoke_http_port_parser.py`, which EXTRACTS the function from the house script rather than copying it, so the test cannot drift from the code. 12/12 cases pass, including `${VAR:-default}` with and without the variable set. | Any parser that consumes compose-style substitutions. |
| 10 | **defense-in-depth** | **A gate that cannot detect is indistinguishable from a clean tree.** Every rule the ratchet depends on is pinned by a mutation that must kill a NAMED test, with the three-phase GREEN→RED→GREEN contract and a byte-exact restore in a `finally`. The kill signal is the test NAME in pytest's own short summary — not "pytest exited non-zero", which a collection error or a timeout also satisfies. | `pmoves/tools/tests/test_silent_bind_ratchet_mutation_kill.py` — 9 mutations, 10/10 pass, measured **55.46s and 62.44s** on two consecutive runs (the earlier 38.45s figure was the 7-mutation harness, before M8 and M9); the crash-safe backup is `pmoves/tests/mutation_backup.py`, and the file is declared slow with its measured basis in `pmoves/configs/pytest_ratchet/_slow_files.yaml`. | Every new ratchet in this repo. |
| 11 | **pattern-conformance** | **The house already ships the platform shim.** The new shell test resolved bash by hand -- `shutil.which("bash")` with a Git-Bash fallback -- and the house ratchet `pmoves/tests/test_no_bare_bash_argv.py` failed it on CI as the **one** new failure in the run: on Windows a bare `bash` resolves to `C:\\Windows\\System32\\bash.exe` (the WSL launcher) before PATH is consulted, so the child silently runs a different OS. The house ships `pmoves/tools/bash_resolver.py` for exactly this: `resolve_bash()` for callers that must have bash, `find_bash()` for "skip if no bash" callers. The hand-rolled version was not merely non-conforming -- it had already bitten me once, when `shutil.which` returned the WSL stub and my probe reported "No such file or directory" for a file that plainly existed. | `pmoves/tools/bash_resolver.py` (the module docstring carries the Z890 measurement); `pmoves/tests/test_no_bare_bash_argv.py::test_no_repo_python_spawns_a_bare_bash` (the ratchet that caught it -- 26/26 pass after the fix); the fix is `from pmoves.tools.bash_resolver import find_bash` in `pmoves/tools/tests/test_smoke_http_port_parser.py`. | Any Python in this repo that spawns `bash` or `sh`. |
| 12 | **contract-correctness** | **"The baseline may only SHRINK" is not enforceable by comparing the baseline with the gaps measured in the SAME checkout.** A change that introduces a new internal-only published port AND adds the matching baseline entry compares CLEAN, because the entry and the gap arrive together -- the tool's docstring claimed an invariant its mechanism could not enforce. The fix is to measure the BASE revision too, so the comparison is between two MEASUREMENTS rather than two intentions: the base revision's compose files are materialized into a temporary tree and scanned with the SAME code, and a baseline entry whose (file, service) pair is not a gap AT THE BASE is a `BASELINE_ADDITION`. | The house already had this shape and the lane did not use it: `.claude/hooks/damage-control/sweep_differential.py` materializes the BASE version of the guard under test and diffs the two verdicts, and `.github/workflows/guard-proportionality-tests.yml` resolves the base SHA from `github.event.pull_request.base.sha` over a `fetch-depth: 0` checkout. The gate now follows that shape (`--base-ref`), the workflow passes the base SHA, and the blobs are read with `git cat-file blob` rather than `git show` so the measurement sees the COMMITTED bytes rather than the repo's end-of-line conversion. Pinned by mutation **M8** (removing the rule must kill `test_baseline_addition_relative_to_the_base_is_rejected`). Measured against `origin/main` on 2026-11-22: the base revision measures 73 gaps, the baseline holds 73 entries, and the rule reports 0 additions -- so all 73 recorded gaps PRE-DATE this lane. | Any allowlist / recorded-exception list whose stated rule is "this may only shrink". |
| 13 | **defense-in-depth** | **A cache built inside a command substitution is rebuilt on every use.** The smoke suite's silent-bind map was built inside `_silent_bind_owner`, and the callers read it as `_owner="$(_silent_bind_owner "$_port")"` -- command substitution runs in a SUBSHELL, so the assignment to `_SILENT_BIND_MAP` was discarded when the substitution ended and the next refused probe paid the whole cost again: `docker ps` plus a batched `docker inspect` over every container in the project. The FIRST version of this map inspected every container per failed probe (63 exec calls per test on this node), which is what pushed the suite past its timeout; the cache that replaced it did not actually hold. The build and the lookup are now separate functions: `_silent_bind_map_init` fills the variable in the PARENT shell, `_silent_bind_owner` only reads it, and both call sites initialise before the substitution. | `pmoves/scripts/smoke-tests.sh` (`_silent_bind_map_init` / `_silent_bind_owner`) + `pmoves/tools/tests/test_smoke_silent_bind_cache.py`, which measures the docker invocation count with a fake `docker` on PATH: with the init called first, N lookups cost exactly 2 calls (one `ps`, one `inspect`); without it, 2 lookups cost 4. The test pins BOTH halves -- the runtime count AND a structural check that every call site initialises before the substitution, because a runtime test of the functions alone would still pass if the script stopped calling the init. Pinned by mutation **M9** (removing the init at a call site must kill `test_every_call_site_initializes_the_map_before_the_substitution`). | Any shell code that caches into a variable and reads it through `$(...)`. |
| 14 | **reasoning-gap** | **A tier split must be counted in ONE unit, and it must be counted by RUNTIME behaviour rather than by the TEXT.** The prior lane's register rows and PR body said "the 73 measured gaps, 37 of them bound to 0.0.0.0". That number was wrong twice over. It conflated gap ENTRIES (73 `(file, service)` pairs) with SERVICES (39), and it counted only the mappings whose text names `0.0.0.0` -- missing the seven published ports whose mapping carries NO host address at all, which Docker publishes on `0.0.0.0` because that is its default. MEASURED by the ratchet's own `--bind-shape` report: 80 port slots = 34 explicit `0.0.0.0` + 7 implicit + 39 loopback; 37 ENTRIES across 20 SERVICES are wide-or-implicit; 19 SERVICES are loopback-only. The OPERATOR's DECISION was taken against the wrong number, so the count is now an instrument output rather than a sentence anyone typed. | `pmoves/tools/silent_bind_ratchet.py` (`bind_shape`, `classify_port`, `split_port_spec`, `service_bind_class`) + `--bind-shape`, which prints the shape of the tree being measured AND of the base revision, so the pre-remediation split stays reproducible after the baseline empties. Pinned by mutation **M11** (an implicit bind must not be classed loopback) and **M12** (the service tally must not collapse onto the entry tally). Both mutations were written AFTER the instrument caught the same two defects in my own first draft -- the service count came back as 73 instead of 39, and the seven implicit ports came back as "other" -- which is the house's own lesson 3 and 4 turning around. | Any count that mixes units, or that reads a configuration file's TEXT where the question is about RUNTIME behaviour. |
| 15 | **reasoning-gap** | **Attaching the publishing tier CREATES the exposure unless the bind is made explicit at the same time.** A mapping with no host address binds `0.0.0.0` the moment its container joins a non-internal network. So the remediation had to be two changes in one: attach `pmoves_public` (so the binding can activate at all) AND give every wide-or-implicit mapping an explicit `127.0.0.1` (so activating it does not publish on every interface). Doing only the first would have created seven brand-new wide listeners -- the exact defect the lane exists to remove. | The seven implicit mappings, all found by the bind-shape report and not by reading the compose files: jaeger's 14268 / 14250 / 4317, otel-collector's 4327 / 4318 / 8889, and semantic-cache's 8100. The three jaeger ports and the three collector ports now reuse the service's own bind var (`JAEGER_BIND`, and a new `OTEL_BIND`); semantic-cache gains `SEMANTIC_CACHE_BIND`. `JAEGER_BIND` is set nowhere in the house, so widening its reach to the three collector ports cannot change a deployed bind. The registry records all seven: `pmoves/configs/ports.yaml`. | Any change that makes a stored binding live for the first time. |
| 16 | **contract-correctness** | **A base file that cannot be READ is not the tree being MEASURED.** The gate failed the whole run when the BASE revision carried an unparseable compose file -- which made the gate unpassable for the very change that REPAIRED that file: the repair would be compared against the breakage it fixed. The tree being measured must still fail closed (exit 3, an unreadable file there is an instrument error), but a base file that will not parse contributes ZERO gaps at the base, which is the CONSERVATIVE direction -- it cannot have carried a measurable gap, so a baseline entry naming it is reported as an ADDITION rather than quietly accepted. The run says how many base files could not be read. | Pinned by mutation **M10**, which turns a base instrument error back into a hard failure and MUST kill `test_a_base_file_that_cannot_be_read_does_not_fail_the_run`. The situation was not hypothetical: `origin/main` carried PR #3519's mangled `networks:` line until this lane repaired it. | Any gate that compares a working tree against a base revision. |
| 17 | **contract-correctness** | **Egress granted by a network attachment has to be accepted IN WRITING, with the tier and the set named.** `pmoves_public` is `internal: false`, so attaching it to 39 services grants those services outbound internet -- Rule 5's second option ("accept egress, deliberately and in writing, for that specific service"), not its preferred gateway-fronting option, which does not apply to most of these because they publish raw TCP ports (NATS 8131, PostgreSQL 54329/6543) rather than HTTP behind Kong. The acceptance is recorded in the register CLAIM and RELEASE rows and here, not left to be inferred from a compose diff. | `pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md` Rule 5 and the network table ("pmoves_public | bridge | internal: no | Host-reachable + egress-capable"); the anchor's own comment in `docker-compose.yml` ("the services still default to 127.0.0.1 host binds for safer standalone operation"), which is why the wide binds had to become loopback in the same change. | Any change that moves a service onto an egress-capable network. |
| 18 | **pattern-conformance** | **A file that cannot be PARSED is invisible to every gate that would have caught the next defect.** PR #3519 landed with two failing checks, and the mangled `networks:` line it introduced was not the only problem: the miSSingLinc instance it added publishes host port 60939 and was never added to `pmoves/configs/ports.yaml`. The port-registry ratchet could not report it, because the file did not parse. The first repair made the file parse; the SECOND defect then surfaced immediately. One broken line was hiding an unregistered published port. | `pmoves/tools/port_registry_ratchet.py --check` on the repaired tree: "1 UNKNOWN SLOT(s) -- service not in registry: docker-compose.agent-zero-instances.yml:agent-zero-miSSinglinc-inst". The registry now carries the slot (`A0MISS_PORT`, host 60939, bind `A0MISS_BIND`), and the ratchet reports 266 published port slots with exit 0. The sibling instance `agent-zero-darkxside-inst` was the precedent for the entry's shape. | Any file whose parse failure can mask a second defect. |
| 19 | **reasoning-gap** | **A compose `networks:` block has THREE shapes in this house, and appending to the wrong one creates a different thing.** The scope contains block lists at the key's own indent (`networks:` then `- pmoves_app` at the same indent), FLOW lists (`networks: [pmoves_app, pmoves_bus]`), and a MAPPING form (`networks:` then `pmoves_api:` with an `aliases:` key). The mapping form is the trap: its LAST content line is a list item -- an ALIAS inside `pmoves_api` -- so appending a list item there adds `pmoves_public` as an alias of `pmoves_api`, a network that does not exist, and attaches the service to nothing. The form has to be decided by the FIRST content line, and the value has to be bounded, because an unbounded scan runs past the networks value into the `healthcheck:` block's own list. | Both defects were found by the edit script's own parse-and-compare verification, which failed with "while parsing a block mapping ... expected <block end>, but found '-'" and then with the alias case caught by the parse of the result. The remediation edits are TEXTUAL -- the compose files are never YAML-round-tripped -- and every file is parsed before and after, with every non-target service asserted byte-identical and every target service asserted to have exactly the intended networks and ports. | Any tool that edits YAML structurally rather than textually. |
| 20 | **pattern-conformance** | **The house already ships a gate that reads this lane's OWN prose back and checks it.** The lane rewrote the slow-file allowance's WHY block to explain the new measurement, and the block kept a historical sentence -- *"the harness carried 9 mutations"* -- for the pre-M10 set. `pmoves/tests/tools/test_pytest_ratchet.py::test_a_declared_mutation_count_is_the_measured_one` scans every declared entry's reason for a mutation count and asserts it against the harness's actual `Mutation(...)` count **by AST**. It failed with *"9 != 12"*. The house instrument was already there, already reading the config this lane was editing, and it caught the lane's own drift without being asked. The fix was to reword the history so it cannot be read as the live figure (*"the 9-mutation set (M1..M9)"*), not to weaken the check. | MEASURED: the test failed on the local tree with `AssertionError: 9 != 12 : pmoves/tools/tests/test_silent_bind_ratchet_mutation_kill.py's config reason claims 9 mutations; the file defines 12`, and passed (43/43) after the reword. The same file also holds `test_the_lane_harnesses_are_declared_with_their_measured_allowances` and `test_the_lane_allowances_widen_the_chunk_that_holds_each_harness`, so the allowance is checked from three sides: the committed value, the chunk budget, and the mutation count in the prose. | Any lane that edits a config whose WHY block a house test reads back as a claim. |

---

## Review findings accepted

The Codex review bot reviewed this PR against commit `d05f45e` and raised two
findings. Both were **verified against the code**, both were **real**, and both
are fixed in this branch:

| # | Finding | Verdict | Fix |
|---|---------|---------|-----|
| P1 | *"Reject baseline additions relative to the base revision"* -- the gate compared the baseline with the gaps measured in the same checkout, so a PR could add a new gap AND its baseline entry and still pass. | **Accepted.** The invariant was stated in the docstring and the workflow comment, and the mechanism did not enforce it. | Lesson 12. `--base-ref` measures the base revision with the same code; `BASELINE_ADDITION` is a new finding kind; the workflow resolves the base SHA the way `guard-proportionality-tests.yml` does. |
| P2 | *"Preserve the silent-bind cache across HTTP probes"* -- the map was built inside a command substitution, so the assignment was discarded and every refused probe rebuilt it. | **Accepted.** The HTTP path I had just wired in inherited the TCP path's latent defect. | Lesson 13. `_silent_bind_map_init` builds the map in the parent shell; both call sites initialise first. |

The P1 finding also exposed a second defect while it was being fixed: the
baseline was keyed on the bare FILENAME, and two files in the house scope
share the name `docker-compose.core.yml` (`pmoves/docker-compose.core.yml`, the
main stack's core overlay, and `pmoves/compose/docker-compose.core.yml`, the
separate n8n stack). The key now carries the path relative to `pmoves/`. The
73 recorded gaps are all in top-level files, so the committed baseline is
byte-identical -- the change removes the collision instead of adding churn.

---

## 4-bucket · 5-class cross-check

- **(1) reasoning-gap** — 6 lessons (#2, #4, #9, #14, #15, #19) — the first-wins network map, the per-key requested-vs-activated comparison, the colon inside a substitution, the tier split counted in the wrong unit, the exposure created by activating a stored binding, and the three shapes of a compose `networks:` block.
- **(2) semantic-naming drift** — 0 lessons.
- **(3) contract-correctness** — 5 lessons (#5, #7, #12, #16, #17) — upstream AND house provenance together, a recorded exception is not a decision, a stated invariant is not an enforced one, an unreadable base is not the tree being measured, and granted egress must be accepted in writing.
- **(4) defense-in-depth** — 4 lessons (#3, #8, #10, #13) — the vacuous-truth empty set, fail-closed on unreadable input, the mutation-kill net, and a cache that did not survive the subshell it was built in.
- **(5) pattern-conformance** — 5 lessons (#1, #6, #11, #18, #20) — the house already owns the instrument, the house's precedent sets the order of work, the house already ships the platform shim for bash, a file that will not parse hides the next defect, and the house's own gate reads this lane's prose back and checks it.

Pattern: **the lane's centre of gravity is conformance to instruments that already
existed.** Three of the thirteen lessons are the same lesson seen from opposite ends
(#1, #6 and #11: find the house's instrument -- the compose pipeline, the precedent
for what to fix first, the platform shim -- instead of hand-rolling one), and the
two that changed the CODE most (#2 canonical inheritance, #3 the empty-set guard)
were both found by MEASUREMENT rather than by reading the source -- which is the
point the operator made about "loading the dice first".

The remediation lane keeps that shape and adds one more turn to it. Lesson 14 is
the same lesson the lane already knew, arriving from a new direction: the tier
split was a NUMBER IN PROSE, it was wrong, and the operator decided against it.
The fix is not a better sentence -- it is an instrument (`--bind-shape`) that
prints the split, plus two mutations that kill the two ways the split can be
miscounted. And lesson 18 is the sharpest instance of the lane's own recurring
theme: the house's gate could not report the unregistered port because the file
would not parse, so the instrument was not wrong and still could not see.

**Outcome of the remediation lane (2026-11-23).** 39 services across 10 compose
files now attach `pmoves_public`; 34 published host ports were rebound from
`0.0.0.0` to `127.0.0.1` and 7 more were given an explicit loopback bind they
did not have. The gate measures **0 gaps** and the baseline is **empty**, so the
gate now fails on ANY new gap -- the recorded exceptions are retired, not
carried forward.

The third of those three (#11) was caught by the HOUSE's own ratchet, on CI, on the
first push of this lane: `pmoves/tests/test_no_bare_bash_argv.py` failed the new
shell test as the single new failure in the run, because the test resolved bash by
hand instead of through `pmoves/tools/bash_resolver.py`. A house instrument found a
defect in a lane whose subject was itself a house instrument. That is the correct
division of labour, and it is the cheapest possible audit.

The two review findings (#12, #13) are the same shape one level up: the HOUSE's own
`git show <ref>:<path>` differential pattern was the answer to a defect the lane's
own docstring had claimed to prevent, and the second finding was a defect the lane
had just WIRES IN rather than merely inherited. The lesson generalises: a lane that
touches a house instrument inherits that instrument's unexamined assumptions, and
the review that catches them is not a formality.

---

## What is measured, and where

| Instrument | Measures | Scope |
|---|---|---|
| `pmoves/tools/silent_bind_ratchet.py` | STATIC: can a published host port activate? (compose files only — no daemon, so it runs on every PR) | 63 compose files in the house scope; 25 out of scope, printed on every run; 73 (file, service) pairs across 39 services |
| `make -C pmoves net-reality` (`pmoves/scripts/audit_network_reality.sh`) | RUNTIME: what did each container REQUEST vs what the daemon ACTIVATED | needs a running daemon; cannot run on a GitHub-hosted runner |
| `pmoves/scripts/smoke-tests.sh::_silent_bind_owner` | RUNTIME: the same class, from the smoke suite's own probes | was wired into `test_tcp_connectivity()` only; `test_http_endpoint()` collapsed a refusal into a WARNING — a gate that cannot see the class it owns |

The three are one subject seen from three vantage points. The static one is
new; the other two were already in the house, and one of them was already
half-wired.

---

## Reproducing the numbers in this file

```
python pmoves/tools/silent_bind_ratchet.py --check          # the gate
python pmoves/tools/silent_bind_ratchet.py --check --json   # the same, machine-readable
python pmoves/tools/silent_bind_ratchet.py --check --base-ref origin/main   # with the
                                                       # baseline-addition rule
python -m pytest pmoves/tools/tests/test_silent_bind_ratchet.py -v
python -m pytest pmoves/tools/tests/test_silent_bind_ratchet_mutation_kill.py -v
python -m pytest pmoves/tools/tests/test_smoke_http_port_parser.py -v
python -m pytest pmoves/tools/tests/test_smoke_silent_bind_cache.py -v
```

Run the mutation-kill harness ALONE: a mutation harness holds the tree
MUTATED by design (house lesson 34), so nothing may read or write the tree
while one runs.

---

## Regenerate the baseline

```
python pmoves/tools/silent_bind_ratchet.py --write-baseline --yes
```

Every reason the generator writes is a PLACEHOLDER (`REVIEW THIS`). The
generator cannot write a reason because a reason is a decision, and a
decision is the operator's. The committed baseline's reasons are written by
hand and state what each gap is waiting on.
