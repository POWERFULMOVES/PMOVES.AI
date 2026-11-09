# Instrument-trust audit — seven checks that reported confidently and were wrong

**Date:** 2026-08-15
**Auditor:** B850-CLAUDE (Knuckles)
**Scope:** findings from a single B850 session (2026-08-13 → 08-15), landed as
[#2538](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2538),
[#2545](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2545),
[#2567](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2567),
[#2570](https://github.com/POWERFULMOVES/PMOVES.AI/pull/2570)
**Companion audits:** #2525 (CI enforcement), #2527 (reproducibility), #2522 (ruleset exposure)

## What this audit does and does not establish

*(framing borrowed from #2527, which states its own limits before its findings)*

**Establishes:** seven specific checks on this node reported a confident result that did
not match reality, each verified by reading the underlying values rather than the
verdict. Each has a named mechanical cause, reproduced.

**Does not establish:** that these are the only such cases, or that the pattern
generalises beyond the surfaces examined. Six of the seven were found incidentally while
chasing unrelated bugs — the sampling is opportunistic, not systematic. **No claim is
made that the fleet has been swept.** Finding 7 in particular was found only because a
glyph looked wrong, which is not a method.

**Deliberately not restated here:** the verification discipline itself. It is already
written in `.claude/agents/verifier.md` — *"evidence before assertions … capture
verbatim … do not paraphrase '12 passed, 1 skipped' into 'tests pass' … state
UNVERIFIED (environment) rather than approximating."* That contract predates this
session and covers the general case better than a restatement would. **The gap this
audit documents is invocation, not documentation.**

## The seven

| # | Instrument | Reported | Actually | Mechanism |
|---|---|---|---|---|
| 1 | rocm-smi exporter `:9835` | `200 OK` | 0-byte body, weeks | systemd expanded `%d` and `${#body}` in an inline `ExecStart` |
| 2 | `claude-pmoves` launcher | launched normally | every cred-dependent MCP empty | `WARN`-then-`exec` on a root it failed to resolve |
| 3 | submodule branch audit | 53 mismatches | 3 real | measured branch *name*, not branch *membership* |
| 4 | `dmesg` | no PCIe errors | buffer evicted | a USB keyboard re-enumerating ~5,000×/day |
| 5 | `geometry_bus_health.py` | "Health: 0.0%" | never contacted NATS | `ParseResult` → `re.sub` raised; caught and relabelled "connection failed" |
| 6 | *this auditor* | "the venv lacks nats-py" | it has 2.14.0 | read an `AttributeError` as an `ImportError`, then wrote it into a Makefile comment as fact |
| 7 | `sign_trail.py` (CHIT trail) | valid signature | **default identity** | `import yaml` inside a `try` with `except Exception: pass`; under `uv run` (no pyyaml declared) it silently returned `_FALLBACK` |

**Where each row is verifiable in-tree.** Added 2026-08-17; the table above was
narrative-only on first publication, which made it unauditable by anyone who had not
sat through the session. In four of the seven cases the *source file already carries a
longer and better explanation than this document does* — the grounding work was
pointing at it, not producing it.

| # | Verify against |
|---|---|
| 1 | `deploy/provision/rocm-smi-http-responder.sh:5-11` (states the trap in-source), `deploy/provision/rocm-smi-http@.service:5` (the repaired unit — `ExecStart` now calls a real script) |
| 2 | `pmoves/scripts/claude-pmoves.sh:61` (root resolution), `:72-73` (the `WARN`-then-`exec` pair, adjacent lines) |
| 3 | `docs/audit/SUBMODULE_AUDIT_2026-02-07.md` and the memory note `reference_submodule_pin_vs_worktree` — test is `merge-base --is-ancestor`, not branch name |
| 4 | Not reproducible in-tree: a host-local `dmesg` ring buffer at a point in time. Marked as such rather than approximated. |
| 5 | `pmoves/tools/geometry_bus_health.py:188-196` (both bugs described in-source), `:314` (the `--json` half of the postscript below) |
| 6 | No artifact — the misread was written into a Makefile comment and corrected before landing. Retained here because the audit's subject is instruments, and the auditor was one. |
| 7 | `pmoves/tools/sign_trail.py:2-5` (the `# /// script` block that is the fix), `:77` (the `try`), `:8-16` (why the dependency block is a correctness fix, not a convenience) |

Finding 7 was discovered while registering *this audit* in AGNOTE4482 — the signing
tool emitted a cryptographically valid HMAC carrying glyph `◆` / `#7C3AED` instead of
the agent's registered `⌬` / `#DC2626`. The `agent_id` survived only because it is
passed on the command line; every field sourced from the registry was substituted. Its
own comment states the intent — *"so the tool never hard-fails on missing YAML"* — and
the effect is a provenance tool that cannot report not knowing who you are. Fixed by
declaring `pyyaml` in an inline `# /// script` block; verified re-signing now yields the
registered identity. **Noticed only because the glyph looked wrong**; had the agent's
configured glyph happened to match the fallback, it would have passed unremarked, which
is a fair guess at why it went unnoticed until now.

Two shapes, and they need different remedies:

- **1, 2, 5, 7 are mechanizable.** Each is a surface returning success while the payload
  is absent, stale, or substituted. A check asserting *content* rather than status catches
  all four without knowing anything about any of them. Three of the four share one exact
  cause: **a soft-import or broad `except` that swallows the reason and returns a
  plausible default**, so the caller receives a complete-looking result built from
  nothing. *Mechanizable is not the same as grep-able* — see the sweep below, where
  that instinct over-reported by a factor of forty before it was narrowed.
- **3, 4, 6 are not.** They are a wrong question, unrelated noise destroying evidence, and
  a misread. No linter catches these; only the habit of reading raw values does.

`merge-gate` deserves a note — and the note as first written was imprecise in exactly
the way this audit is about. Corrected 2026-08-17 against
`.github/workflows/merge-gate.yml`:

- The **job literally named `merge-gate`** (`:16-29`) is the one #2525 found vacuous,
  and it **is still vacuous today**: it sets `PASSED=true`, echoes three lines, and
  nothing ever reads the output. A reader who took the original sentence at face value
  and opened that job would have concluded this audit was wrong.
- What was **repaired** is the `python-tests` job (`:34`) — `pytest_ratchet.py` runs all
  264 test files where `head -20` by filesystem order previously ran at most 20; the
  dependency install lost its `|| fallback` and `2>/dev/null`. The 264 is
  `pytest_ratchet.py:11`'s own figure and it holds: re-deriving it on 2026-08-17 via
  `discover_test_files()` with submodule paths excluded (CI checks out with
  `submodules: false`, stated at `pytest_ratchet.py:88-91`) gives **263**.
- Enforcement actually comes from a **third** job, `merge-decision` (`:80`), which reads
  `needs.*.result` and `exit 1`s. Worth recording while looking straight at it: it fails
  only on `== "failure"`, so a **cancelled or skipped** required job passes the gate
  (`:91-96`). Not pursued here — noted with its line so it is not rediscovered from
  scratch.

Verified before relying on it for the merges above. **The audit lane is driving fixes
ahead of its own PRs merging.**

## The sweep — and what it says about the sweep

Finding 7's cause looked mechanizable, so it was swept for across `pmoves/tools/` and
`pmoves/services/` by AST rather than grep (a text grep cannot tell a handler's shape).
The funnel matters more than the endpoint:

| Filter | orig, 08-15 | `--legacy`, 08-18 | current, 08-18 |
|---|---|---|---|
| `try:` containing an import, with a broad or bare `except` | **157** | 160 | **178** |
| …of those, handlers that are **silent** (no log, no raise, no warn) | **60** | 65 | **71** |
| …of those, handlers that are fully `pass` | 6 | 2 | 4 |
| …of those, in a path that **reports outward** as authoritative | **4** | — | **0** |

**On first publication the 08-15 column rested on a script that had been thrown away** —
an audit about instruments that cannot be checked, publishing a headline number that
could not be checked. The script was since recovered from the session's scratch
directory, and its predicate is now preserved in-tree as
`pmoves/tools/silent_handler_sweep.py --legacy`, beside the corrected default
(`make -C pmoves silent-handler-sweep`). Preserving it is not sentiment: documenting the
middle column while leaving it un-runnable would repeat the same defect one level down.
All three columns reconcile:

- **157 → 160.** The historical headline reproduces to within three sites across three
  days of commits (49 of them). It was never wrong — it was merely unverifiable, which is a different
  complaint and the one this audit should have anticipated about itself.
- **6 → 2 is exactly the four sites fixed in this PR.** The original predicate,
  unchanged, run two days later, finds precisely the four gone and the two known-good
  ones still there. That is the strongest single confirmation in this document, and it
  exists only because the old script happened to be recoverable — luck, not method.
- **The new tool finds 2 more at stage 3 because the original required the import to be
  a *direct child* of the `try` body.** `retro_flightcheck.py:595` puts `import winsound`
  inside `if os.name == 'nt':`, and `bootstrap.py:70` nests likewise; both were invisible
  to the original. The original also matched only `ast.Name` for broadness, missing
  tuple forms like `except (ValueError, Exception)`.
- **Only 2 predicate disagreements remain across all 178 stage-1 sites**, and the new
  tool is right in both: `tunnel_manager.py:163` calls `self._notify_error(...)` (audible;
  the original missed it), and `chit_invalidation.py:123` merely *acquires* a logger with
  `logging.getLogger(...)` (silent; the original called it audible).

**Stage 4 is 0 today.** All four surviving stage-3 sites were hand-classified and
cleared: `services/common/__init__.py:92` and `services/common/bootstrap.py:70` both fail
loudly at the eventual import site (the latter says so in-source);
`hf-mcp-server/main.py:564` is the `"source": "catalog"` counterexample cited below;
`retro_flightcheck.py:595` falls back from `winsound` to `\a` — the feature audibly
degrades, which is the definition of fine. **Stage 4 is deliberately not automated**: the
tool prints stage-3 sites for a human and emits `"reports_outward": null` in `--json`.
Automating that judgement would be the precise error this audit documents.

### Both sweeps were wrong about silence, in opposite directions

Worth recording rather than quietly fixing, because it is the same failure a third and
fourth time:

- **The original decided silence by substring-scanning `ast.dump(handler).lower()`** for
  `log`/`print`/`warn`/`stderr`/`exit`. That is a text grep wearing an AST costume — any
  identifier anywhere in the handler that merely *contains* one of those (a local named
  `catalog`, `dialog`, `logic`, `exit_code`) reads as a report. **In the sweep whose
  headline is that a text grep cannot see a handler's shape, the sweep was a text grep.**
- **The replacement's first draft counted `Assign` and `Return` as audible** and reported
  stage 2 as **7** instead of 71. That predicate excludes
  `except Exception: return _FALLBACK` — *finding #7 itself*. Widening "audible" until
  the alarming number goes away is the same move as trusting a status code.
- **Its second draft under-detected**, missing `print_error`, `error_msg`, `sys.exit`,
  and then `logger.info` / `logger.debug`, because the verb list was assembled by
  guessing instead of by diffing against the original. Each round was caught only by
  running both predicates over the same 178 sites and reading every disagreement —
  four, then four again, then two.

`silent_handler_sweep.py:_is_silent` and `:_is_audible_call` now carry all of this, and
`tests/tools/test_silent_handler_sweep.py` pins the two wrong drafts as named regression
tests so the number cannot drift back the way it drifted forward.

**The first number is the finding.** 157 would have been a fleet-wide alarm, and it would
have been wrong: `torch`, `faiss`, `sentence_transformers`, `numpy`, `tqdm`, `rich`,
`psutil` guards are all *correct* — the feature genuinely degrades and the caller is told.
Had this audit stopped at the grep it would have become an eighth entry in the table
above: a confident count that did not match reality. **The antipattern is not "a broad
`except` on an import." It is a silent handler in a path that reports outward.**

Two sites show what correct looks like, and both survived every filter honestly:

- `services/hf-mcp-server/main.py:542` (the `try`), `:564` (the `pass`), `:560` / `:586`
  (the stamps) — a live registry query falls back to the static catalog and stamps
  `"source": "catalog"` instead of `"source": "registry"`. The consumer can *see* which
  one it got. Note it *is* a fully-`pass` handler and still reaches stage 3; it is
  cleared only at stage 4, by reading what the fallthrough does. No mechanical filter
  clears this site, which is the argument for stage 4 existing.
- `tools/chit_security.py:13` — crypto import failure sets `_CRYPTO_OK = False`, an
  explicit degraded flag rather than a silent no-op. It is counted as **silent at stage
  2** (it says nothing at the moment of failure) and cleared at stage 3 (its handler is
  not `pass`). That is the intended path for correct-but-quiet code.

The four that lied outward, all fixed in this PR (logging only — no behaviour or
contract change; best-effort delivery stays best-effort):

| Site | Was | Now |
|---|---|---|
| `tools/sign_trail.py:77` | substituted the whole agent identity in silence | warns to stderr naming the reason (pyyaml missing / file unreadable / agent unregistered) |
| `hi-rag-gateway-v2/routes/geometry.py:166` | dropped every live subscriber, returned `{"ok": true}` | `logger.exception` |
| `hi-rag-gateway-v2/routes/geometry.py:587` | same | `logger.exception` |
| `hf-mcp-server/main.py:853` | `hf.model.gguf.converted.v1` never published, returned `{"ok": true}` | `logger.exception` |

Line numbers in the table above are **post-fix, re-verified 2026-08-17**. The
`geometry.py` second site read `:583` on first publication and had already drifted to
`:587` — the fix to the first site added lines above it, so the stale citation pointed
at the `_persist_cgp_to_db` call, which is the *correct-discipline* counterexample four
lines up. A citation that rots into pointing at the opposite of its claim is worse than
no citation, so: re-derive before quoting, and prefer `silent_handler_sweep.py` output
over a number typed into prose.

Two of these are self-evidencing. `sign_trail.py` already warned loudly that it could not
find a requested **alter** — twenty lines below the block that substituted the entire
**agent** without a word; it could report a missing persona but not a missing person.
And `geometry.py` persists with `logger.exception` + `raise HTTPException(500)`, then
eight lines later swallows the broadcast and returns `ok: true`. **Both files already
contained the correct discipline; it just had not been applied to the adjacent line.**
That is the more useful lesson than any lint rule: the fix was usually already in the
file.

## Postscript — the fix for #5 had the same defect twice

The first host run of the *merged* `geometry_bus_health.py` found two gaps in the
NOT MEASURED work itself. Neither is a new instrument; both are instrument 5 again:

- **The JSON branch still emitted `"health_pct": 0.0`.** The human-readable branch had
  been taught to refuse an unmeasured percentage; `--json` had not, so anything
  machine-consuming it kept receiving the identical false negative. *Fixed the instance,
  not the class* — the failure mode this session hit twice already. Now `null`, beside an
  explicit `"measured"` flag.
- **The failure report listed guesses and no facts.** The real cause was
  `Authorization Violation`, but nats-py routes server rejections through `error_cb` and
  retries, so the only exception reaching the caller was `TimeoutError`. The report said
  *"timed out"* and advised checking host and port — both of which were already correct.
  An `error_cb` now captures what the server actually said and the report leads with it.

Worth stating plainly: **the remedy for a confidently-wrong instrument was itself
confidently wrong on first contact with the real system.** It passed review, it passed
its own tests, and it was still guessing. The only thing that caught it was running it.

## Mechanical traps (the genuinely new material)

Node-agnostic, reproduced, and in none of the existing surfaces:

| Trap | Consequence seen | Verify against |
|---|---|---|
| `$(...)` strips **all** trailing newlines | `Content-Length` one byte short of the body; Prometheus exposition lost its required final newline. Bit **four separate times** — in the responder, in two tests of the responder, and in the installer verifying it. | `deploy/provision/rocm-smi-http-responder.sh:58-61` |
| nats-py `connect_timeout` does **not** bound DNS resolution | unresolvable host hung ~60 s while `connect_timeout=5` sat there looking authoritative. Wrap in `asyncio.wait_for`. | `pmoves/tools/geometry_bus_health.py:168-173` |
| `%` and `${}` in a systemd `ExecStart` are expanded **by systemd** | `%d` → credentials dir, `%s` → user shell, `${#body}` → empty. Put shell code in a real script; escaping works but reintroduces itself on the next edit. | `deploy/provision/rocm-smi-http@.service:5` (repaired unit), `rocm-smi-http-responder.sh:5-11` (the original inline form, quoted in-source) |
| Submodule branch **name** ≠ branch **membership** | detached HEAD is normal; the real test is `merge-base --is-ancestor <sha> origin/<tracked>`. And the *recorded gitlink* is a different layer from the *working tree* — only the former affects clones. | `docs/audit/SUBMODULE_AUDIT_2026-02-07.md`; memory note `reference_submodule_pin_vs_worktree` |
| Fleet `NATS_URL` is container-scoped (`nats:4222`) | any host-run tool hangs on it. Use the published address from the host. | `pmoves/tools/geometry_bus_health.py:38-41` (no credential-bearing default), `:170` (the hang) |
| A tool run in a bare `uv run` env has no venv packages | a soft-import fallback then renders a full report from nothing. Declare inline deps (`# /// script`). | `pmoves/tools/sign_trail.py:2-5` (the block), `:8-16` (why it is a correctness fix) |

## Recommendations

1. **Invoke `.claude/agents/verifier.md` reflexively** — on one's own claims before
   asserting them, not only on others' PRs. It was invoked zero times during a session
   in which it would have caught finding #6 immediately.
2. **Healthchecks and status targets assert payload, not status code.**
   `.claude/skills/pmoves-mesh-preflight/scripts/preflight.sh:64` and
   `.claude/commands/health/check-all.md` currently trust endpoint verdicts; either
   would have passed the 0-byte exporter every day it was broken. The preflight case is
   not a judgement call — the line is
   `curl -sS --max-time 3 -o /dev/null -w '%{http_code} %{time_total}'`, which
   **discards the body**, and `:69` accepts anything matching `^[23]`. It is
   structurally incapable of noticing an empty 200. (First published as an unsourced
   assertion; grounded 2026-08-17.)
3. **Land the audit lane** (#2522, #2525, #2527). Its findings are already changing the
   repo; merging them makes the reasoning citable rather than folkloric.
4. **Consider the #2527 package as a calibration fixture.** #2525 had to hand-roll "a
   deliberately failing test run through an equivalent path" to prove a check *could*
   fail. A frozen, network-isolated, hash-manifested package with six deterministic
   checks of known outcome is the standing form of that — a target whose answer is known,
   which is exactly what every instrument in the table above lacked.

## Provenance

Every row was verified by reading the underlying value, not the verdict:
`Content-Length` vs actual bytes; `LnkSta: Width x16` vs the expected `x8`;
`4.2%` vs `0.0%`; `merge-base --is-ancestor` vs branch name; `importlib.metadata
.version('nats-py')` vs a traceback's first line. Where a claim could not be checked on
this node it is marked as such above rather than approximated.

### Grounding pass, 2026-08-17

The document above was, on first publication, **narrative with almost no citations** —
every claim true, none of them checkable by a reader. That is a real defect in an audit
whose thesis is that confident reports need their underlying values read. This pass
attached a source to every claim that has one, and marked the ones that do not.

What it found, in the document itself:

| | |
|---|---|
| A citation had **rotted into pointing at its own opposite** | `geometry.py:583` → `:587`; the stale line landed on the correct-discipline counterexample |
| The **load-bearing number was unreproducible** | the 157/60/6/4 sweep script had been discarded — recovered from scratch, re-run, and replaced by `pmoves/tools/silent_handler_sweep.py`; `6 → 2` then confirmed the four fixes exactly |
| A paragraph **named the wrong thing as repaired** | the job named `merge-gate` is still vacuous; `python-tests` was the repair, `merge-decision` is the enforcer |
| A recommendation **asserted a mechanism it never quoted** | `preflight.sh:64`'s `-o /dev/null` is the actual reason, and is stronger than the prose was |
| Two rows have **no in-tree artifact and now say so** | #4 (a host `dmesg` ring buffer at a moment in time) and #6 (the auditor's own misread) |

Claims re-derived rather than copied: **263** CI-visible test files against
`pytest_ratchet.py:11`'s 264 — close enough to confirm the figure, and the difference is
one file, not a methodology. Reaching that number took three attempts.
`discover_test_files()` returns **5058** on this host (submodules populated; CI checks
out with `submodules: false`), and a first correction over-excluded by truncating
`pmoves/integrations/archon` to `pmoves` and reported **4**. Two confidently wrong
measurements, inside a grounding pass for an audit about confidently wrong measurements,
before one that agreed with the source. Recorded because the third number is only
trustworthy in the company of the first two.
