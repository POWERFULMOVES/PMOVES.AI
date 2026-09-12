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
`pmoves/docs/handoffs/<filename>`. That is the point: a reason a hook can check.

Close the road when you are done. `roads.py status` is how the next session finds
out you did not.

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

## Verifying a guard change

If you are changing damage-control itself, both directions must be proven, and
the tests are script-style — **not pytest-collectable**. `make` collapses every
nonzero exit to 2, so call them directly:

```bash
cd .claude/hooks/damage-control
for t in test_gitlock_allowlist.py test_interpreter_writes.py test_insight_edits.py \
         test_dockerfile_domain.py test_topic_domain.py test_proportionality.py \
         test_bash_known_roads.py; do
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

## Related

- `pmoves-chit-sign` — sign the trail after guard-adjacent work
- `pmoves-pair-review` — review anatomy for a guard diff
- `.claude/PATTERNS.md` § Known Roads — Protected-File Edits
