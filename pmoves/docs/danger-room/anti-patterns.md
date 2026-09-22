# Danger Room — Anti-Pattern Catalog

**Status:** living catalog · **Doctrine:** registry-first (skill `pmoves-registry-first`)
**Rule:** load the dice first — anchor constellations → harvest the shape → hand-roll only the
delta, with provenance. Tests belong here (Danger Room / E2B sandbox E2E), not `bash -n`.

Each room: **Trap** (what it is) · **Live** (where it bit us, real refs) · **Signal** (how to
recognize it before it bites) · **Harvest** (the correct pre-existing tool/procedure).

---

### `hand-rolled-launch-verify`
- **Trap:** writing bespoke subprocess-launch + JSON-RPC + env-sanitize code for agent CLIs.
- **Live:** three lanes in one week duplicated PMOVES-Registry tooling — #3093 (cipher CLI
  dispatcher), #3097 (ACP launcher probe), `acp_registry_map.py` consumption — while
  `PMOVES-registry/.github/workflows/` already ships `verify_agents.py` (1,156 lines:
  sandbox launch per agent, platform detection, auth-check), `client.py` (ACP JSON-RPC:
  initialize → session/new → auth probe), `registry_utils.py` (sanitize_agent_env,
  process-group kill, npm/pypi parse, quarantine), `protocol_matrix.py` (daily
  capability snapshots), across 42 registered agents.
- **Signal:** about to `import subprocess` to launch an agent CLI; about to hand-write an
  `initialize` handshake.
- **Harvest:** consume the registry harness. PMOVES layers only identity (node pins, CHIT),
  env (env.shared + model-suit selection), fleet routing (tailnet serve URLs).

### `hardcoded-compose-urls`
- **Trap:** compose `environment:` entries pinning `host.docker.internal:<port>` for optional
  backends — invisible until a node lacks the local service.
- **Live:** cipher-api `OLLAMA_URL` hardcoded in BOTH the split file
  (`docker-compose.agents.yml:928`) and the monolith (`docker-compose.yml:4077`). #3082
  fixed only the split; monolith nodes (elder-melchor) stayed dark — cipher embed leg dead
  for weeks while `/healthz` stayed green. #3101 fixed the monolith; healing verified live
  (`OLLAMA_URL=http://pmoves-z890:11434`, donor `qwen3-embedding:4b` answering, store→search
  round-trip).
- **Signal:** env default pointing at `host.docker.internal`; "works on GPU nodes."
- **Harvest:** interpolate `${VAR:-same-default}` at every layer (split AND monolith —
  compose-split regenerates one from the other, fix both or neither); node selects donor via
  `.env.local` + Known Road recreate.

### `unquoted-heredoc-args`
- **Trap:** `"$@"` inside an unquoted heredoc expands at GENERATION/install time, not call time.
- **Live:** #3092 — rc function template emitted `{name}() { "$launcher" "$@"; }` via
  `cat <<EOF`; the installer's own args were baked in — running the installer with `--force`
  hardcoded `--force` into every future invocation.
- **Signal:** emitted shell containing a heredoc AND `"$@"`.
- **Harvest:** escape to `\"\$@\"` (keep `$launcher` expanding) or quote the heredoc and
  inject the path by substitution.

### `template-brace-double-escape`
- **Trap:** regex authored inside a format-template inside a string literal — three escaping
  layers multiply until the pattern matches only garbage.
- **Live:** #3092 — the PS1 `${VAR}` resolver regex was double-escaped twice over
  (`'\\$\\{{...\\}}'` in template → emitted PS never matched `${NAME}`), so env.shared alias
  lines like `KEY=${OTHER}` loaded VERBATIM into process env (the #1987 placeholder-leak
  class). Same class: #3093's install script emitted `${{BASH_SOURCE[0]}}` and `{{` function
  braces — syntactically broken bash.
- **Signal:** backslash runs in generated code; "regex works in isolation, never in output."
- **Harvest:** compose patterns with `[char]123` / `[char]125` (no literal braces in the
  template), or move the regex out of the template entirely. Then parse-test every emitted
  file (`test_every_emitted_ps1_parses` exists for this).

### `ps-trailing-comma`
- **Trap:** PowerShell array literals reject trailing commas — bash/JSON habits leak in.
- **Live:** #3092 — blocklist entries each emitted with a trailing `,` →
  `Missing expression after ','` at parse time; surfaced only after fix #1 made blocklists
  non-empty (empty lists skipped the code path — a bug hiding behind a bug).
- **Signal:** string-joined PS/JSON-ish arrays built item-by-item with `f"'{entry}',"`.
- **Harvest:** separator-join (`sep = "," if i < n-1 else ""`) and keep the parse gate.

### `exec-bit-drift`
- **Trap:** files generated on Windows commit `100644` regardless of intended mode; the
  executable bit is unrepresentable on the generating platform.
- **Live:** #3092 — 42 generated `.sh` committed non-executable while the manifest claimed
  `"executable": true`; fresh clones hit permission-denied on the rc `$launcher` call and
  `~/.local/bin` symlinks. The manifest-vs-disk drift check compared bytes only, so it stayed
  green over the broken bit.
- **Signal:** generated scripts + Windows dev seat + `git ls-files -s` showing 100644.
- **Harvest:** `git update-index --chmod=+x <files>` in the generator's own lane; assert mode
  bits in the manifest test, not just content hashes.

### `eol-blind-byte-tests`
- **Trap:** byte-stability tests hashing worktree files while ignoring `.gitattributes` eol
  conversion — the comparison is CRLF (checkout) vs LF (regen) on every platform.
- **Live:** #3092 — `*.ps1 text eol=crlf` converted the LF blob at checkout; the test failed
  everywhere with `f60746ec != cc4af8cb`. Also latent: `*.cmd` had NO attributes rule
  (platform-unstable by default).
- **Signal:** hashes differ only after checkout; "works on the machine that generated it."
- **Harvest:** emit per-policy endings (ps1/bat/cmd → CRLF, rest → LF); add the missing
  `.gitattributes` rules; keep the parse test alongside the hash test.

### `green-healthz-dead-deps`
- **Trap:** healthchecks that probe the service itself — structurally cannot report the death
  of the dependencies behind it.
- **Live:** cipher-api `/healthz` green for weeks while its logs showed Neo4j absent,
  Ollama unreachable, HiRAG fetch-failing. Same family: the nats-event-bus facade probing its
  own `/healthz` for 9 days while fronting no broker (register row 2954), the GEOMETRY BUS
  checker reporting a confident zero percent without ever contacting NATS, the Archon
  healthcheck polling a different port.
- **Signal:** "healthy" + any dependency leg untested; healthcheck URL equals the service's
  own loopback.
- **Harvest:** probes that can fail — client round-trip (NATS pub/sub, bolt connect, one real
  embed call), stated denominators, per-dependency status in the body (flute's `/healthz`
  with its `providers:{}` map is the in-repo model).

### `stale-checkout-heal`
- **Trap:** node-side operational fixes run from a checkout that is days/commits behind
  origin/main — the fix being applied is already on main, or the defect being fixed is
  already fixed.
- **Live:** the cipher heal lost ~an hour: the main checkout sat 157 commits stale on a
  pre-merge branch, so #3082's interpolation was invisible to every recreate; the monolith vs
  split file ambiguity compounded it. Three bg compose runs died on required-var
  interpolation before the checkout was reconciled.
- **Signal:** "let me just recreate the container" on a checkout whose last fetch predates
  the relevant merge.
- **Harvest:** reconcile FIRST — `git fetch && git log origin/main -1 && git status` (and
  `git merge --ff-only origin/main` when clean) — then the Known Road
  (`INCLUDE_ENV_LOCAL_IN_COMPOSE=1 make recreate-svc SVC=<svc>`).

### `placeholder-env-credentials`
- **Trap:** enabled provider/platform whose credential is still the `YOUR_*_HERE` template.
- **Live:** 2026-09-20 TTS 401 — config had flipped to `provider: openai` with the
  `YOUR_OPENAI...` placeholder; earlier the gateway crash-looped exit 78 for a week on
  Discord/Telegram `YOUR_*_TOKEN` placeholders.
- **Signal:** any `YOUR_`/`CHANGE_ME` value behind an enabled flag.
- **Harvest:** enabled ⇒ real credential; placeholders ⇒ platform disabled. Local working
  chains (kokoro floor → flute gateway) stay the default.

### `exit-code-contract-drift`
- **Trap:** docstring documents one exit-code contract, the switch statement implements
  another; tests assert a third.
- **Live:** #3093 — docstring: "2 … missing tool"; code remaps every non-zero to 3;
  LEARNINGS claims `bundle` exits 1 on the chit `ModuleNotFoundError`, code returns 3; and
  `test_failed_subprocess_does_not_append` asserts the OPPOSITE of its name (the append did
  happen) — an invitation for a future "fix" to delete an audit write.
- **Signal:** exit codes appear in more than one place; test names contain "does_not".
- **Harvest:** single enum/source of truth for codes; tests named for verified behavior
  (`test_failed_subprocess_still_appends`).

### `premature-audit-write`
- **Trap:** an audit/ledger row recording success before the operation it audits has run or
  passed.
- **Live:** #3093 — `cipher_cli.py:788` set `manifest_check: True` before the manifest check
  executed, so failed/pending checks were recorded as passed.
- **Signal:** audit state initialized `True`/`ok` at declaration.
- **Harvest:** write the row after the operation, carrying the actual result; initialize
  `None`/`pending`.

### `phantom-deliverable`
- **Trap:** post-interruption (or post-compaction) work claimed as done that was never
  durably created — files written to scratch that never got committed, PRs "opened" whose
  branch was never pushed, skills "saved" that the index doesn't list.
- **Live:** 2026-09-20 session — the previous pass reported a danger-room doc pushed, a PR
  open, and dispositions posted; fresh verification showed the branch never pushed (empty
  `ls-remote`), the doc 404 on main, the disposition absent, and the cited PR number was an
  unrelated lane.
- **Signal:** any completion claim resting on the same context that produced it; memory of
  writing instead of a fresh read.
- **Harvest:** verification-first — every deliverable gets a fresh independent read
  (`skill_view`, `git ls-remote`, `gh pr view`, file re-read) before it enters a report or a
  close. Claim = receipt.

---

## Matching index (signal → room)

| Signal | Room |
|---|---|
| `import subprocess` to launch an agent | `hand-rolled-launch-verify` |
| `host.docker.internal` in compose env | `hardcoded-compose-urls` |
| heredoc + `"$@"` in emitted shell | `unquoted-heredoc-args` |
| backslash runs / `{{` in generated code | `template-brace-double-escape` |
| PS arrays built by string append | `ps-trailing-comma` |
| generated scripts from Windows | `exec-bit-drift` |
| hash tests over checked-out files | `eol-blind-byte-tests` |
| healthcheck = own loopback | `green-healthz-dead-deps` |
| ops run without `git fetch` | `stale-checkout-heal` |
| `YOUR_`/`CHANGE_ME` behind enabled flag | `placeholder-env-credentials` |
| exit codes in docstring + switch + test | `exit-code-contract-drift` |
| audit row initialized `True` | `premature-audit-write` |
| completion claim without a fresh receipt | `phantom-deliverable` |

## Provenance

Compiled 2026-09-20 by HERMES-AGENT (elder-melchor) from live session evidence:
PRs #3082, #3092, #3093, #3097, #3101; register rows 2954/2956 (B850 bus restore);
PMOVES-Registry tooling survey (42 agents, `verify_agents.py`/`client.py`/
`registry_utils.py`/`protocol_matrix.py`); the 2026-09-20 cipher heal and TTS 401.
Doctrine owner: DARKXSIDE. Catalog home: this file; matching signals feed Danger Room
room-generation (E2B E2E per `pmoves-e2b-danger-room`).
