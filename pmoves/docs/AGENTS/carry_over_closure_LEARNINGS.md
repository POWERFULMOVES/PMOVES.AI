# carry_over_closure_LEARNINGS.md

**Lane:** the four carry-over items the operator opened in the post-merge message on
PR #3440 — the 8 unbuildable image-matrix entries (F1), the 25 Windows-only
compose-smoke failures plus the `validate_service_tools_packaging.py` cp1252 defect
(F2), the GH App installation state on the newly-scoped repos (F3), and the latent
second claimant of 8115 (F4) — plus the MiniMax x PMOVES surface parity ask (F5).
**Branch:** `fix/carry-over-closure`.
**Base:** `origin/main` @ `2020a9103a9`.
**Taxonomy:** 4 buckets · 5 classes, as used across the PMOVES lanes.
**Spec:** `pmoves/docs/specs/carry-over-closure-2026-11-01.md`.

---

## What was broken

The operator's post-merge message named four things. Measurement found that **three
of the four were not what their names said**, and that the fourth was much bigger
than its name.

### F2 — the 25 "compose-smoke failures" were not compose-smoke failures

`pmoves/tests/smoke/test_compose_structure.py` and
`pmoves/tests/smoke/test_port_conflicts.py` failed on the operator's Windows host:
**25 failed, 2 passed**.

The obvious theory was that the compose parser was wrong. The theory was wrong, and
the way it was wrong is the lesson.

**The proof.** Re-running the same 27 tests with `PYTHONUTF8=1` — which makes every
`open()`/`read_text()` decode as UTF-8 instead of the locale encoding — gives
**27 passed**. The failures were therefore not logic failures at all. They were
`UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f`, raised while reading
a compose file that contains UTF-8, on a host whose locale encoding is cp1252.

**The rival theory, measured and withdrawn.** An earlier draft of this spec claimed
a second root cause: compose merge tags (`!reset` / `!override`) refused by
`yaml.safe_load`. MEASURED: `yaml.safe_load` on `pmoves/docker-compose.yml`
**succeeds**. The merge tags exist in exactly three optional overlays
(`docker-compose.amd.yml`, `docker-compose.amd-voice.yml`,
`docker-compose.hardened.yml`), none of which the failing tests read. The theory
was withdrawn from the design rather than quietly carried into it.

**The class is much bigger than the symptom.** MEASURED at `origin/main`
(`2020a9103a9`) with the committed instrument
`pmoves/tools/windows_encoding_ratchet.py`: **708** text-mode call sites across
**192** files in `pmoves/` omit an explicit `encoding=`. The lane removes **25**
sites in **9** files, leaving **683** sites in **183** files as the baselined
population that a ratchet holds in place. MEASURED as a per-file diff between
the two populations with the SAME instrument: **0** files added to the
population and **0** files grew — the lane only ever removed gaps.

### F3 — the repo universe was never 39

The prior lane's fork ratchet cross-checks `fork_registry.json` → the workflow's
`FORKS` block → the GH App's `repositories:` scope, and all three agreed on **39**.
That agreement was the bug: **39 is the workflow's SYNC SCOPE, not the universe.**

MEASURED: `pmoves/config/fork_registry.json` holds **86** forks (**35** `sync: true`,
**51** `sync: false`) plus **9** `_first_party` repos (PMOVES-built, no upstream) —
a universe of **95**. `Pmoves-cipher` is held outside `forks` in `_excluded`
because it has no common ancestor with upstream and cannot sync via the merge API.

**New drift found while measuring it:** 4 of the workflow's 39 are marked
`sync: false` in the registry — `PMOVES-Jellyfin`, `PMOVES-crush`,
`PMOVES-headscale`, `PMOVES.YT` — while **0** registry `sync: true` entries are
missing from the workflow. The registry's flag and the workflow's scope disagree
for 4 repos, and the ratchet that cross-checks them cannot see it because it only
checked membership, never the flag.

### F4 — the 8115 collision was one of 71 bare literals

`pmoves/docker-compose.yt-cookies.yml:46` was flagged as a latent second claimant
of 8115. MEASURED across **59** compose files: **262** published-port stanzas —
**191** with a parameterised host port, **71** with a **bare-literal** host port,
and **0** using Docker's dynamic host port (the container-port-only form). The
"docker has dynamic ports" capability is entirely unused in this repo today.

The three 8115 claimants all hard-code the port while parameterising only the bind
address:

| File | Service | Entry |
|---|---|---|
| `pmoves/docker-compose.yml` | `node-registry` | `${NODE_REGISTRY_BIND:-0.0.0.0}:8115:8115` |
| `pmoves/docker-compose.core.yml` | `node-registry` | `${NODE_REGISTRY_BIND:-0.0.0.0}:8115:8115` |
| `pmoves/docker-compose.yt-cookies.yml` | `yt-cookie-refresher` | `${YT_COOKIE_REFRESHER_BIND:-127.0.0.1}:8115:8115` |

And the two "port registries" are neither complete: `service_catalog.py` holds 45
services, `port_allocator.py::DEFAULT_PORTS` holds 40, they agree on every one of
the 32 names they share, and **91 of the 125** compose services that publish a port
appear in **neither**.

---

## 4-bucket · 5-class taxonomy

| # | Class | Observation (rule) | Evidence / Why | Apply when |
|---|-------|---------------------|----------------|------------|
| 1 | **reasoning-gap** | **A text-mode read with no `encoding=` is a PLATFORM-DEPENDENT failure wearing the costume of a logic failure** — and the costume is what makes it survive review. | MEASURED 2026-11-01: 25 of 27 tests in `pmoves/tests/smoke/test_compose_structure.py` + `test_port_conflicts.py` failed on the operator's Windows host with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f`. They were filed as "compose smoke failures" — i.e. as failures of the thing the file is named after. The cause was in the FILE READ, not the compose logic: the compose YAML contains UTF-8 and the host locale encoding is cp1252. The named defect (`pmoves/scripts/validate_service_tools_packaging.py:45`) had the same shape: `COMPOSE_FILE.read_text()` with no `encoding=`, while the file's OTHER three reads already passed `encoding="utf-8"`. FIX: an explicit `encoding="utf-8"` on every text-mode read, plus a ratchet that holds the class in place. | Any test, tool or script that reads a file whose bytes are not guaranteed to be the host's locale encoding. |
| 2 | **reasoning-gap** | **"The failures are decoding" is a CLAIM until a control run proves it — and a rival theory that sounds right must be measured and WITHDRAWN, not carried quietly into the design.** | The single-cause claim was proved by a CONTROL: the same 27 tests with `PYTHONUTF8=1` (which only changes the decode) give **27 passed**. That control is what separates "decoding" from "the compose parser". The rival theory — `!reset`/`!override` merge tags refused by `yaml.safe_load` — was MEASURED and **withdrawn**: `yaml.safe_load` on `docker-compose.yml` succeeds, and the tags live in exactly 3 optional overlays the failing tests never read. An earlier draft of the spec asserted both root causes; the spec now records the withdrawal in place, because a spec that quietly drops a disproved cause teaches the next reader that it was never checked. | Any diagnosis that produces more than one candidate cause. |
| 3 | **contract-correctness** | **An instrument's carve-out must read the argument the carve-out is ABOUT** — and a throwaway counter that gets it wrong poisons the number that goes into the prose. | The class size was first measured by a throwaway script that decided "is this call binary?" by inspecting `node.args[0]` — the FILE argument — against a set of mode strings. That check could never fire, so every binary `open(path, "rb")` was counted as a text-mode gap. It reported **730** sites across **207** files. The committed instrument reads the MODE from the correct slot per signature and reports **708** sites across **192** files at `origin/main`. The 22-site difference is not noise: it is the difference between a number that describes the fleet and one that describes the measuring script. The wrong figure had already been written into the spec's prose before the instrument shipped. | Any measurement whose carve-out inspects a specific argument. |
| 4 | **contract-correctness** | **Two signatures, two slots** — `builtin open(file, mode, …)` takes the mode SECOND, `Path.open(mode, …)` takes it FIRST. | A shared `_mode_argument(node, path_open)` helper exists for exactly this reason, and BOTH slots are mutation-tested (M1, M2 in `pmoves/tests/tools/test_windows_encoding_ratchet_mutation_kill.py`). Reading the wrong slot is silent in the dangerous direction: for `open(path, "rb")` the wrong slot yields the FILENAME, the binary mode is missed, and every binary read in the fleet is flagged as a text-mode gap. For `p.open("rb")` the wrong slot yields nothing, and a binary handle is flagged. The house already writes the correct form in most places (`path.open("r", encoding="utf-8")`), so the detector has to agree with the house, not with a guess. | Any helper that reads a positional argument from a call with an overloaded signature. |
| 5 | **contract-correctness** | **A baseline that CANNOT ROT is not a baseline** — fixing a file must turn the gate RED until its entry is pruned. | The contract has four failure kinds, and they are kept distinct on purpose: a file NOT in the baseline with gaps is a NEW GAP; a count that ROSE is a NEW GAP; a count that FELL is STALE; a file with no gaps left is STALE; a file that no longer exists is ORPHANED. MEASURED in the act: after the lane fixed `services/channel-monitor/channel_monitor/config.py` and `tools/keygen_cards.py`, the gate reported **2 STALE baseline entries** and exited **1** — the fix itself turned the gate red, because leaving the entries would have let the defect be re-introduced silently. That is the intended behaviour, and it is why the STALE half is mutation-tested (M5). | Any gate with a known-bad baseline. |
| 6 | **pattern-conformance** | **A gate's `paths:` filter must cover the WHOLE surface the gate scans** — or the gate has a hole exactly where a new gap would land. | `pmoves/tools/windows_encoding_ratchet.py` scans EVERY `.py` under `pmoves/`, so ANY of them can introduce a gap. The workflow's filter is therefore `pmoves/**/*.py` plus the baseline YAML plus the workflow file itself — a narrower filter would let a gap into the tree without ever waking the gate. The prior lane closed the same hole in `fork-sync.yml` (F3). The companion rule from the prior lane applies here too: the ratchet runs in `merge-gate.yml`'s REQUIRED `python-tests` context via `pmoves/tools/pytest_ratchet.py`, which discovers `test_*.py` across the parent repo with NO paths filter; `python-tests.yml`'s `tests (3.11)` job is a DIFFERENT check that runs only `pmoves/services/*/tests` and is not required. | Any gate whose trigger filter is narrower than its scan surface. |
| 7 | **reasoning-gap** | **A locale-dependent WRITE and a locale-dependent READ agree BY ACCIDENT** — and the fix that makes one of them explicit BREAKS the other, which looks like the fix was wrong. | `pmoves/tools/keygen_cards.py` read its cards file with `read_text()` (locale encoding). `pmoves/tests/tools/test_keygen_cards.py` WROTE that file with `write_text()` (locale encoding). Both were cp1252 on the operator's host, so the round trip worked and the test was green. The lane made the READ explicit (`encoding="utf-8"`) — and the test immediately failed with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97 in position 29`, because the FIXTURE was the cp1252 side of the accident. The byte was the em-dash in `# 5x5 Signing Identity Cards — test fixture`; the real data file `pmoves/config/signing_identity_cards.yaml` was, and remains, valid UTF-8. FIX: the test's four text-mode sites now declare `encoding="utf-8"` too, so the round trip is explicit on BOTH ends and the locale is out of the contract. The lesson is not "be careful when you fix X" — it is that a green test can be evidence of an ACCIDENT rather than of a contract. | Any test that writes a fixture and any code that reads it back — the two must declare the SAME encoding explicitly, or the test is asserting that the host's locale has not changed. |
| 8 | **defense-in-depth** | **A ratchet must be able to catch the AUTHOR** — a gate that is green on arrival teaches the fleet to ignore it, and a gate that goes red on the lane's OWN new file is the proof it is not decorative. | MEASURED IN THE ACT: `pmoves/tools/windows_encoding_ratchet.py` flagged `pmoves/tests/tools/test_windows_encoding_ratchet_mutation_kill.py` as a **NEW GAP** — the harness's own lock-file handle was `path.open("a+")` with no `encoding=`. The lane's own new file was the first thing the new gate turned red on. It was fixed (`path.open("a+", encoding="utf-8")`), and the baseline was NOT widened to absorb it: a NEW gap is a failure, not a baseline entry. The opposite failure is also real and was measured in the prior lane — a ratchet that is green on arrival, because its authors pre-emptively baselined the very thing it should have caught, is a gate the fleet learns to ignore. | Any gate added to a tree that already contains the defect class it measures. |

---

## What shipped

| Item | What | Where |
|---|---|---|
| F2a | 25 text-mode file reads fixed with an explicit `encoding="utf-8"` | `tests/smoke/test_port_conflicts.py` (5), `tests/smoke/test_compose_structure.py` (4), `tests/tools/test_keygen_cards.py` (4), `tools/keygen_cards.py` (4), `services/channel-monitor/channel_monitor/config.py` (3), `scripts/port_allocator.py` (2), `scripts/validate-ollama-inventory.py` (1), `scripts/validate_service_tools_packaging.py` (1), `tools/inject_docker_hub_pat_from_cli.py` (1) |
| F2b | `pmoves/tools/windows_encoding_ratchet.py` — AST detector for text-mode file I/O without `encoding=`; NEW GAP / STALE / ORPHANED / instrument-error all fail the gate; fails closed | `pmoves/tools/windows_encoding_ratchet.py` |
| F2c | `pmoves/configs/encoding_ratchet/_known_gaps.yaml` — the 683-site, 183-file pre-existing population, per file with its count | `pmoves/configs/encoding_ratchet/_known_gaps.yaml` |
| F2d | `.github/workflows/windows-encoding-ratchet.yml` — the gate, with a `paths:` filter covering the whole scanned surface | `.github/workflows/windows-encoding-ratchet.yml` |
| F2e | 35 behavioural tests + 7 mutation kills | `pmoves/tests/tools/test_windows_encoding_ratchet.py`, `pmoves/tests/tools/test_windows_encoding_ratchet_mutation_kill.py` |

---

## Bucket summary

RECOMPUTED, not asserted. `pmoves/tests/tools/test_carry_over_closure_learnings_taxonomy.py`
parses the lesson table above and re-derives every count, the total, and each
class's MEMBER LIST, then compares them with this section. A summary that claims
to be a measurement needs a gate of its own, or it rots silently.

| Class | Lessons | Members |
|-------|---------|---------|
| reasoning-gap | 3 | 1, 2, 7 |
| semantic-naming drift | 0 | — |
| contract-correctness | 3 | 3, 4, 5 |
| defense-in-depth | 1 | 8 |
| pattern-conformance | 1 | 6 |

**Total lessons: 8**

The zero-count classes are DECLARED, not omitted. A summary that lists only the
classes that happen to have members cannot show that a class was considered and
found empty — and an omitted class reads as an oversight rather than a
measurement.

