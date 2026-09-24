---
name: known-roads
description: Answer what the damage-control guard protects and what the sanctioned route is BEFORE tripping it — protected path classes, Known Road domains, whether a reason is provable, which grant is open right now, and which roads have already been taken. Use when a Bash/Edit/Write call was refused for a protected path, before editing a compose file / contract schema / topics registry / Dockerfile / migration, or when you need to know what is off limits in this repo.
disable-model-invocation: false
user-invocable: true
---

# known-roads — make the protected set a known known

The damage-control guard refuses operations on protected paths. For some of those
paths a **Known Road** exists: a provable, recorded, operator-authorized bypass.

The problem this skill solves is not the refusal. It is that the protected set was
only discoverable **by tripping it**. What is off limits should not be a known
unknown — that spends the fleet's discovery budget on the guard's own
configuration instead of on real unknowns. Ask first; the answers are below.

Companion pieces, all already in the repo:

| Piece | Role |
|---|---|
| `.claude/hooks/damage-control/known_roads.py` | the mechanism: domain predicates, reason provability, trail recording |
| `.claude/hooks/damage-control/patterns.yaml` | the protected path classes |
| `.claude/skills/known-roads/roads.py` | **this skill's query tool** — derives every answer from the two above |
| `.claude/agents/known-roads` agent | advisory navigator for a *specific* edit; never modifies the guard |
| `.claude/PATTERNS.md` § Known Roads | the prose reference |

`roads.py` hardcodes nothing. A domain added to `DOMAIN_PATTERNS`, or a class
added to `patterns.yaml`, shows up on the next run. A catalog that could go stale
would put the protected set straight back into the bucket this skill empties.

## When to use

- A Bash, Edit, or Write call was refused with `SECURITY: Blocked ...`.
- **Before** touching a compose file, a contract schema, `topics.json`, a service
  Dockerfile, or a Supabase migration — the five domains that have roads.
- You are about to claim a lane and want to know what it will collide with.
- A refusal names a road and you need to know whether your reason is provable
  *before* spending a turn on it.
- Someone asks "what is off limits here?"

## Ask, in order

Run from the repo root. `CLAUDE_PROJECT_DIR` is honored; otherwise the tool walks
up to the directory containing `.claude/hooks/damage-control`.

```bash
SK=.claude/skills/known-roads/roads.py

# 1. What classes of path are protected, and how many entries in each?
python3 "$SK" protected

# 2. Which domains have a sanctioned bypass, and what does each open?
python3 "$SK" domains

# 3. Is THIS path protected, by which entry, and which road opens it?
python3 "$SK" check pmoves/docker-compose.yml pmoves/contracts/topics.json README.md

# 4. Is my reason provable? (the guard's own gate answers)
python3 "$SK" reason pr:3011 issue:42 handoff:MY_BRIEF.md

# 5. Is a road already open on this node? (grants outlive the session that set them)
python3 "$SK" status

# 6. Which roads have actually been taken?
python3 "$SK" trail 20
```

Step 5 is not optional housekeeping. A file grant persists on disk, so a road
another session opened is still open for yours. Check before assuming a refusal
is the guard's baseline behaviour — and report an unattended grant rather than
riding it.

## The three protection classes, and what they mean for you

`python3 "$SK" protected` prints live counts. What the classes mean:

| Class | Reads | Writes | Deletes | Road? |
|---|---|---|---|---|
| `zeroAccessPaths` | refused | refused | refused | **never** — credentials and state; there is no sanctioned bypass |
| `readOnlyPaths` | fine | refused | refused | only if the path falls in a Known Road domain |
| `noDeletePaths` | fine | fine | refused | no |
| `repoScopedPaths` | subset of `readOnlyPaths` that applies **inside this repo only** | | | |

Matching is on **resolved paths**, in all three guards. Two consequences worth
knowing before you write a command:

- Prose that merely *names* a protected path is not an operation on it. You can
  document the guard in a register note without the note being refused.
- An entry in `repoScopedPaths` does not reach an identically-named directory
  elsewhere on the host. A host-level interpreter environment outside the repo is
  not this repo's build artifact directory.

## Taking a road

A road needs a **domain** and a **provable reason**. Both are checked, and the
crossing is recorded; a bypass that cannot be recorded is denied (fail-closed).

```bash
# confirm the domain covers your path, and that your reason will pass
python3 "$SK" check <path>
python3 "$SK" reason pr:<n>

# then open it for the operation, one of:
export KNOWN_ROAD=<domain>:<reason>                               # session env
echo '<domain>:<reason>' > .claude/hooks/damage-control/.known-road-active   # file grant
```

Reason forms, exactly three: `pr:<number>`, `issue:<number>`,
`handoff:<filename>` — and for `handoff:`, the brief must actually exist at
`pmoves/docs/handoffs/<filename>` **and be tracked by git** (`git add` is
enough). That is the point: a reason a hook can check.

**A grant expires.** Well-formed is not enough; the guard checks the grant is
still live every time it is used:

| Bound | Rule | Refusal says |
|---|---|---|
| referent | `pr:N` / `issue:N` must be **OPEN** on `POWERFULMOVES/PMOVES.AI` (`gh api`, 8 s timeout, at most one lookup per hook call). Merged or closed → void | `grant VOID: PR #N ... is MERGED at <time>` |
| verifiable | no trusted `gh`, no network, auth failure, timeout, or a malformed API body → **refused**, never assumed open | `grant not verifiable: <cause>` |
| kind | `issue:N` that is really a PR (or `pr:N` that is an issue) → refused | `grant refused: issue #N is a pull request; ... pr:N` |
| age | a **file** grant older than **24 h** is void whatever the PR state; so is a future-dated one | `grant file is N.Nh old (limit 24h)` |
| env grant | has no mtime: it lives as long as the session launched with it. In a settings file's `env` it would ride every session and only the referent bound would limit it — which is why that is forbidden | — |

**Which `gh`.** Never the one on `PATH` (it starts with agent-writable
`~/.local/bin`; a shim there answering "open" revived a merged grant). Only
`/usr/bin`, `/usr/local/bin`, `/opt/homebrew/bin`, `/bin` (Windows:
`%ProgramFiles%\GitHub CLI\gh.exe`), and the binary and its directory must not
be writable by the hook's user. On Homebrew that directory is user-owned, so
grants refuse there; use a root-owned gh or the offline override. An operator can
set `KNOWN_ROAD_GH=/abs/path/gh` in the launching environment; it passes the same
test and replaces the search. The API call runs with a fresh, empty
`GH_CONFIG_DIR` (gh's own config can re-route its HTTP via `http_unix_socket`,
measured), authenticated by a token fetched first with `gh auth token`.

**The hooks fail closed.** Every damage-control hook exits 0 or 2 only
(`fail_closed.py`). For PreToolUse any other code is non-blocking, so a crash used
to let the call through; now an unexpected error prints `SECURITY:
damage-control guard error, refusing: <Type> at <file:line>` and blocks. The
PostToolUse effect check cannot block a command that already ran, so it exits 2
with `EFFECT-CHECK GUARD ERROR ... NOT checked` instead. That is its loudest
channel, and it feeds the model. A corrupt cache or a non-UTF-8 grant file is not
an error: the cache counts as a miss, and the grant grants nothing.

Only a **successful** lookup is cached (120 s, `.grant-state-cache.json`,
git-ignored and readOnly), so a merge takes effect within two minutes and a burst
of edits costs one API call. The lookup runs only when a command actually touches
a path in the grant's domain; ordinary Bash calls pay nothing.

**Offline work.** Append `!offline` to a `pr:`/`issue:` grant
(`compose:pr:3200!offline`). It skips the referent check only — never the age
limit — and every use is recorded as `grant_state: offline-override`. It is a
per-grant suffix, not an env switch, so it cannot become ambient: it is written by
the same act that opens the grant and dies with it.

Close the road when you are done. `roads.py status` is how the next session finds
out you did not — it now shows the grant's source, age and live verdict, and
`roads.py reason pr:<n>` gives the same verdict the guard would.

## Rules

1. **Never edit the guard to permit your own edit.** If damage-control blocks
   work you believe is legitimate, the route is a road, a narrower command, or an
   escalation to the operator — not a change to the thing doing the checking.
2. **Never widen a protection to make a refusal go away.** A permissive
   regression in a security guard costs far more than a false positive.
3. **`known-roads.jsonl` is an audit log of roads TAKEN, not a catalog.** Its
   94-plus lines answer "who crossed, when, why" — never "what is protected".
   For the catalog use `protected` and `domains`. Do not read the log looking for
   the set; that mistake is what made the protected set feel undiscoverable.
4. **`zeroAccessPaths` has no road.** If you need one of those files, you need
   the secrets pipeline (`make -C pmoves secrets-funnel`), not a bypass.
5. **A path with no road gets no road.** When `check` reports a protected path
   with no domain, the sanctioned route is a new domain predicate in
   `known_roads.py`, agreed with the operator — a change to the policy, made
   deliberately and in the open.

## The trail row

Each line of `.claude/hooks/damage-control/known-roads.jsonl` is one JSON object,
written by `known_roads._record()` with sorted keys. There are two row shapes:
rows written before `5bae26814`, and rows written with no hook input, carry only
the always-present fields. A row's `reason` never carries the `!offline` suffix — it is
stripped so rows group by the bare reason; `grant_state` says it was used.

| Field | Present | Meaning |
|---|---|---|
| `ts` `tool` `file` `domain` `reason` | always | when (UTC), which tool, which path, which road, which provable reason |
| `agent` | always | a **registered body** (runtime name, e.g. `delivery-agent`) when one acted; otherwise the **node value** (see below). Mixed by design, so don't group on it alone |
| `node` | only when `agent` is a body | the node value that `agent` would have held without attribution |
| `agent_instance` | when the hook carried `agent_id` | per-instance id of the subagent (≤64 chars). Absent for a main thread, including one started with `--agent` |
| `unregistered_agent_type` | when the hook carried an `agent_type` that is not in the registry | the raw type (≤128 chars). Kept visible, never promoted to `agent` |
| `session` | always | `CLAUDE_SESSION_ID`, else `SESSION_ID`, else the hook's `session_id`, else `unknown` |
| `note` | optional | how the use was observed (e.g. after the fact by the PostToolUse effect check) |
| `grant_state` | rows written after grant expiry landed | how the grant was verified at the moment of use: `open` (PR/issue checked open), `offline-override` (`!offline`, not checked), `handoff-present` (brief exists and is tracked). Refused states (`merged`, `closed`, `stale`, `unverifiable`) never appear: the trail records roads TAKEN, and a refusal is reported in the hook's message instead |
| `grant_source` | with `grant_state` | `env` (KNOWN_ROAD) or `file` (`.known-road-active`) |

**Node value.** It is `AGENT_ID`, else `PMOVES_NODE_ID`, else `unknown`. `AGENT_ID`
is **ambiguous**: every value in the trail so far is a node id, but other tools use
the same variable for an agent name (`pmoves/tools/pr_hedge_trim.py` defaults it to
`claude-code-cli`; `persona-bind/bind.sh` to `4090-claude`). If a harness exports
`AGENT_ID=<agent name>`, that name is recorded as the node. Treat `node` as "the
identity the environment claimed", not as a verified host.

**Grouping.** To group rows by node, use `node if present else agent`. To group
by body, use `agent` only on rows that carry `node`. A row without `node` names
no registered body.

**Attribution, not authentication.** `agent_type` is the definition the harness
loaded. It is not a credential. It is certified as a body only when it exactly
matches an `agent_registry.yaml` `agents:` key under the registry's own rule
(runtime name = key with `_` → `-`). An unreadable registry certifies nothing.
Nothing in the guard reads these fields to allow or deny.

## Verifying a guard change

If you are changing damage-control itself, both directions must be proven, and
the tests are script-style — **not pytest-collectable**. `make` collapses every
nonzero exit to 2, so call them directly:

```bash
cd .claude/hooks/damage-control
for t in test_gitlock_allowlist.py test_interpreter_writes.py test_insight_edits.py \
         test_dockerfile_domain.py test_topic_domain.py test_proportionality.py \
         test_bash_known_roads.py test_grant_expiry.py test_fail_closed.py; do
  python3 "$t" >/dev/null 2>&1; echo "rc=$? $t"
done
```

`test_proportionality.py` is the template for the shape that matters: every ALLOW
case paired with the in-repo form of the same operation, which must still refuse.

**Then run the sweep, because the suite is not enough.** On the change that added
these files the hand-written suite was green while the sweep found 16 permissive
regressions. A suite tests the cases someone thought of; a sweep tests the cases
`patterns.yaml` actually contains.

```bash
# 6548 commands x two guards, ~15 minutes. Exit 0 clean / 1 findings / 3 cannot run.
python3 .claude/hooks/damage-control/sweep_differential.py <base-git-ref>
```

Every verdict change it reports must be a deliberate, named relaxation. If one is
not, that is a permissive regression in a security guard — stop and report it
rather than shipping it.

## What the PreToolUse guard cannot see, and what catches it instead

Every path rule interpolates the protected path into the pattern, so the guard
only sees a write that NAMES a protected path in the command. Applying a diff
from a file, extracting an archive, mirroring a tree, a block copy, an executed
shell or python script, and a build-tool target all write paths the command never
spells. Measured: a diff applied from a file wrote two protected compose files
and the trail read 250 rows before and 250 after.

Two mechanisms, and they are not equivalent:

| | where | what it can do |
|---|---|---|
| `opaqueWriteVerbs` in `patterns.yaml` | PreToolUse | the common shapes, while prevention is still possible. **Deliberately partial.** A grant allows and records; no grant asks. |
| `effect_check.py` | PostToolUse(Bash) | closes the class. Asks whether a protected path is DIFFERENT, which every verb answers the same way. Detection only -- the write already happened. |

```bash
# what state is each historical trail row in? (156 synthetic / 11 genuine / rest current)
python3 .claude/hooks/damage-control/trail_states.py
```

The effect check costs ~60 ms per Bash call (measured, 6 warm rounds, full-size
checkout; the git scan is 4-5 ms of that and interpreter startup is the rest --
the existing PreToolUse guard measured 121-139 ms the same way). What it cannot
see is listed at the top of `effect_check.py` and is not implied away: untracked
and gitignored protected paths, paths outside the repository, a write that leaves
porcelain code, mtime and size unchanged, and attribution finer than "since the
last Bash call in this checkout".

If it alerts, **disclose it and then revert or justify** -- do not silence it, and
do not edit `patterns.yaml` to make your own change fit.

## Related

- `pmoves-chit-sign` — sign the trail after guard-adjacent work
- `pmoves-pair-review` — review anatomy for a guard diff
- `.claude/PATTERNS.md` § Known Roads — Protected-File Edits
