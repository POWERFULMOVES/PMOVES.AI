# skills-agents-md-foldin-refactor

Field brief for **any implementation agent** — two corpus-consistent refactors
left open by the 6-repo fold-in slice (PR1 skills / PR2 model-cascade / PR3
agents.md, merged 2026-08-17..20).

**A.** Retire the stray untracked `skills/Pmoves-skills` clone and route the
Anthropic skill library through the package's `sources/` overlay instead.
**B.** Give the root format/taxonomy pointer a progressive-disclosure link path
into the AGNOTE4482 corpus, so an agent that starts at `AGENTS.md` reaches the
Signoff Rule and the ACK convention instead of dead-ending.

Both are documentation + submodule-topology work. Neither touches a service.

## Arguments

- `workstream` (enum `A` | `B` | `both`, default `both`): A retires the stray
  clone; B wires the corpus link path. They share no files and can land as two
  PRs or one.
- `delete_stray` (bool, default **false**): whether to actually remove
  `skills/Pmoves-skills/` from disk. **Leave false.** The deletion is
  OPERATOR-GATED — see `## Notes`. With `false`, the run does everything except
  the removal and leaves the directory in place for an operator to handle.
- `populate_sources` (bool, default true): run
  `git submodule update --init --recursive skills/PMOVES-skills` so the
  `sources/` overlay stops being an unpopulated pointer.
- `branch` (string, default `docs/skills-agents-md-foldin-refactor`): work
  branch off `origin/main`. Use a git worktree; do not work in a dirty main tree.

## Implementation

### Workstream A — retire the stray `skills/Pmoves-skills`

#### A0. Confirm the measured state before changing anything

Re-run these on `origin/main`. If any answer differs, stop and report — the
premise below is what makes the fix safe.

```bash
git status --porcelain skills/Pmoves-skills     # expect: ?? skills/Pmoves-skills/
git check-ignore -v skills/Pmoves-skills        # expect: no output, exit 1 (NOT ignored)
cat skills/Pmoves-skills/.git                   # expect: gitdir: ../../.git/modules/skills/Pmoves-skills
git -C skills/Pmoves-skills rev-parse --short HEAD    # expect: 69c0b1a
git -C skills/Pmoves-skills remote get-url origin     # expect: .../POWERFULMOVES/Pmoves-skills.git
grep -n 'skills/Pmoves-skills' .gitmodules      # expect: NO match — no declaration
git add -A -n skills/Pmoves-skills              # expect: "warning: adding embedded git repository"
```

That last line is the hazard. The path is a real clone with a valid gitdir
pointer, is not gitignored, and has no `.gitmodules` entry — so a careless
`git add -A` anywhere in the repo stages it as a bare `160000` gitlink behind a
*warning*, not an error. The result is an **orphan gitlink**: a commit pointer
with no declared URL, which no clone can resolve. That is strictly worse than
bug #2654, where the drifting entry was at least declared.

Second, independent hazard: `skills/Pmoves-skills` and the tracked
`skills/PMOVES-skills` differ only in case. On Windows and macOS those are the
same path. Z890 is the Windows/WSL node.

#### A1. The corpus already adjudicates this — do not re-derive it

`skills_foldin_pr1_LEARNINGS.md` §2.2 states the rule: *"when an upstream
recenters, the canonical fork follows; deprecated URLs are documented in the
existing module's README, not added as separate submodules."*

Read the **CORRECTION banner at the top of that same file (2026-08-20)** before
you cite §2.2 anywhere. The banner retracts §2.2's *premise* — `MiniMax-AI/skills`
never moved to `vercel-labs/skills`; both are alive and share no history. The
*rule* survives, and `skills/README.md:33-60` records the actual reason this
directory should not exist:

> `Pmoves-skills` was the **Anthropic** fork's old name, renamed to
> `Pmoves-Claude-skills`. GitHub repo names are case-insensitive, so the vacated
> name was immediately taken by `PMOVES-skills`, and the old
> `skills/Pmoves-skills` submodule silently began resolving to the vercel-labs
> CLI instead of the Anthropic library. That duplicate entry is removed; the
> Anthropic fork is tracked under `sources/`.

So: the entry was already removed from `.gitmodules` on purpose. What survives
on this node is a working-tree leftover of the pre-removal checkout, pinned at
`69c0b1a` — the last gitlink the parent repo ever recorded for it.

#### A2. Populate the canonical home instead

The Anthropic library's canonical home is
`skills/PMOVES-skills/sources/Pmoves-Claude-skills/`, declared in the package
fork's **own** `.gitmodules` (`skills/PMOVES-skills/.gitmodules`, entry
`sources/Pmoves-Claude-skills`, url `POWERFULMOVES/Pmoves-Claude-skills.git`,
branch `PMOVES.AI-Edition-Hardened`).

It is currently **uninitialized**. `git -C skills/PMOVES-skills submodule status`
prints a leading `-` on all six `sources/*` entries:

```
-f6656c1256d5a8adfa37db9110046ef20bac644c sources/Pmoves-Claude-skills
-60aaae52bb2af8162732751a4332f62a5fef518b sources/Pmoves-Minimax-skills
```

Populate it:

```bash
git submodule update --init --recursive skills/PMOVES-skills
git -C skills/PMOVES-skills submodule status   # leading '-' must be gone
```

Then use the package rather than maintaining a parallel clone. The vercel
package format is what `skills/PMOVES-skills` *is* — `npx skills add <owner>/<repo>`
installs a source's skills into whichever harness directory is in play
(`.claude/skills/`, `.agents/skills/`, `.minimax/skills/`, …). Record the exact
invocation you used in the PR body. Do **not** copy skill directories by hand
from `skills/Pmoves-skills/` into the tree; that recreates the same duplicate in
a new location.

#### A3. Update all four constellation touch points

Per PR1 §2.3, any constellation change updates **all four**. Name each one in
the PR body with the line you changed:

| # | File | What to change |
|---|------|----------------|
| 1 | `skills/README.md` — constellation table (lines ~11-17) | Confirm no row names `skills/Pmoves-skills`. Add a short "retired path" line under the § Correction block (lines 33-60) recording that the working-tree leftover was removed and why, so the next clone that finds one knows it is not a submodule. |
| 2 | `skills/README.md` — § Activation paths (lines ~71-81) | The `PMOVES-skills/sources/Pmoves-Claude-skills/` bullet (line ~76) currently describes the fork as a reference. Add the concrete populate command from A2 so the activation path is executable, not descriptive. |
| 3 | `.claude/context/submodules.md` — § `skills/ — Skills Constellation` table (lines ~118-128) | Row for `skills/PMOVES-skills/` (line ~124) already names both sources. Add the `git submodule update --init --recursive` note; confirm no row for the lowercase path. |
| 4 | `pmoves/configs/submodule_skill_registry.json` — key `"skills/PMOVES-skills"` (line ~1118) | The `$note` already carries the 2026-08-20 correction. Extend it with the retired working-tree path so the context-tag injector's note matches the README. Do not add a key for `skills/Pmoves-skills`. |

Validate the JSON after editing:

```bash
python3 -c "import json; d=json.load(open('pmoves/configs/submodule_skill_registry.json')); print(len(d['submodules']))"
```

#### A4. The deletion itself — OPERATOR-GATED, do not script

**Stop here.** Two steps are destructive and require explicit operator approval
before anyone performs them. This brief deliberately does **not** spell them as
runnable command lines, so they cannot be pasted through by an agent skimming
for a code block:

1. Delete the working-tree directory `skills/Pmoves-skills/` (recursive). It is
   a real clone and it is untracked, so nothing in git recovers it and any
   uncommitted work inside it is gone.
2. Delete its backing gitdir, `.git/modules/skills/Pmoves-skills/` — the target
   the `.git` pointer file resolves to. Removing the worktree without this
   leaves a stale module dir; removing this without the worktree leaves a broken
   pointer. Approve and perform both together, step 1 then step 2.

Emit both as an operator checklist in the PR body. Do not put either in a
Makefile target, a script, or a hook. Do not run `git add -A` at repo root at
any point in this workstream — stage explicit paths only
(`git add skills/README.md`, etc.), or you create the orphan gitlink A0 measured.

### Workstream B — link the root format pointer INTO the AGNOTE4482 corpus

#### B1. The dead end, stated precisely

Two true statements combine into a hole:

1. `agents_md_foldin_pr3_LEARNINGS.md` §2.4 placed `PMOVES-agents.md/` at the
   **repo root** deliberately: root is for format/spec/taxonomy references that
   agents *load*; `skills/` is for runtime-invokable skills that agents *run*.
   **That placement is correct. Do not move the submodule.**
2. Its pinned tree carries zero PMOVES taxonomy — 61 blobs, all Next.js; its own
   `AGENTS.md` documents how to run that website ("always use `npm run dev`, do
   not run `npm run build`"). Measured 2026-08-30 and written up in
   `AGENTS.md:255-284` and `.claude/CLAUDE.md:39-47`.

Because (2) is true, `.claude/CLAUDE.md:39` now tells agents the submodule is
"the agents.md **website** fork, nothing more." So the designated pointer to
agent-corpus material contains none, and the correction routes agents *away*
from the pointer — and **nothing on either path forwards a reader to
`pmoves/docs/AGENTS/AGNOTE4482.md`**, which is where the Three-Body pattern, the
Village Rule, the Signoff Rule and the ACK convention actually live.

#### B2. The motivating incident — cite it, it is measured

On 2026-09-03 the B850 node filed **six** `RELEASE` rows through
`register-release` — `AGNOTE4482PHI.t1.md` lines **2754-2759**, timestamps
`2026-09-03T20:58:59Z` through `2026-09-03T21:03:10Z` — carrying **no
`agent_signature` and no `GRAPHITI_MARK`**, while neighbouring rows carry both
(`<!-- GRAPHITI_MARK: … -->` appears 297 times in that file). Root cause is
recorded in the CLAIM at line 2760: the steward read the SITREP and the register
and never reached AGNOTE4482.md, whose line 21 says to read the gateway *first*
and then claim. Orientation, not tooling.

#### B3. Add the bridge in PMOVES-owned files only

Respect the upstream-fork boundary. `PMOVES-agents.md/` tracks upstream `main`
with no PMOVES overlay branch (PR2 §2.3: fresh forks track `main` until they
need one), and the constellation's branch contract keeps vendored trees
byte-identical so fork-sync stays a fast-forward (`skills/README.md:30-31`).
Editing a vendored Next.js file to insert a PMOVES pointer converts every future
sync from a fast-forward into a merge, for a link that belongs in our own docs
anyway. **Put every edit in a PMOVES-owned file. Say so in the PR body with this
reasoning.**

Three edits, forming one progressive-disclosure chain — each hop discloses only
the next hop, per the operator's "CHIT progressive" framing:

**Hop 1 — root `AGENTS.md`, § "AGENTS.md Format Reference" (lines 255-284).**
That section already carries a "Where the taxonomy actually lives" table
(`agent_registry.yaml`, the prose hub, class taxonomy + topology). Add one row
to that same table:

| you want | load |
|---|---|
| the coordination corpus — Three-Body, Village Rule, Signoff Rule, the ACK + GRAPHITI_MARK convention | `pmoves/docs/AGENTS/AGNOTE4482.md` (gateway — read before claiming), then `AGNOTE4482PHI.t1.md` (active claims) |

One row. Do not restate the corpus contents here; that is hop 2's job.

**Hop 2 — `.claude/CLAUDE.md`, Tier-2 block (lines 39-47) and the table row at
line 25.** Both currently end at "the taxonomy lives in
`pmoves/config/agent_registry.yaml` + `pmoves/docs/AGENTS/`." Extend each by one
sentence naming `AGNOTE4482.md` specifically as the gateway and stating that
agents entering a PMOVES lane read it before claiming. `pmoves/docs/AGENTS/` as
a bare directory is not a pointer — it is 40+ files with no reading order, which
is how the corpus stayed unread.

**Hop 3 — `.claude/context/submodules.md`, § `PMOVES-agents.md` (lines 104-116).**
The `**Cross-refs:**` bullet (line ~110) names the root `AGENTS.md` and two
taxonomy docs. Add `pmoves/docs/AGENTS/AGNOTE4482.md` to that bullet, described
as the coordination gateway. Leave the one-row table at line 116 alone.

#### B4. What the corpus gateway must be described as carrying

When you write the hop-1 and hop-2 sentences, name these four by their actual
headings in `pmoves/docs/AGENTS/AGNOTE4482.md` so a reader knows what they are
being sent to:

- `## Canonical Pointer` (lines 5-21) — the ordered read list, ending in
  *"All agents entering PMOVES lanes should read that file first, then claim
  work before edits."*
- `## Signoff Rule` (lines 24-30) — `AGNOTE4482_SIGNOFF_CHECKLIST.md`; each
  agent signs only for the sections it actually reviewed or executed.
- `## Village Rule` (lines 52-64) — execution / control / memory bodies; derived
  from `THREE_BODY_DOCTRINE.md`.
- `## Agent ACK (Gateway)` (lines 65-68) — the `ACK::<AGENT>::<MARK>` signature
  form, paired with the `GRAPHITI_MARK` declared at line 3
  (`PHI-4482-GATEWAY::PMOVES`). This is the convention the six rows in B2 missed.

#### B5. Registry entries stay distinct

Per PR3 §2.5, distinct upstreams get distinct registry entries. Do **not** merge
`"PMOVES-agents.md"` (line ~1181) and `"skills/PMOVES-skills"` (line ~1118) in
`pmoves/configs/submodule_skill_registry.json`, and do not cross-populate their
`domain_tags`. If you touch the `PMOVES-agents.md` entry at all, the only
correct change is extending its `$note` to mention the corpus link path.

## Related

- `skills_foldin_pr1_LEARNINGS.md` — §2.2 (deprecated URLs live in the README,
  not as submodules — **read the 2026-08-20 CORRECTION banner first**), §2.3
  (the four constellation touch points), §2.4 (`skills/<fork>/` path convention)
- `agents_md_foldin_pr3_LEARNINGS.md` — §2.4 (root vs `skills/` placement),
  §2.5 (distinct upstreams, distinct registry entries)
- `mcpcli_foldin_pr2_LEARNINGS.md` — §2.2 (root placement for non-constellation
  forks), §2.3 (`main` vs `PMOVES.AI-Edition-Hardened` branch contract)
- `skills/README.md` — canonical constellation doc: table L11-17, sources
  overlay L19-31, § Correction L33-60, adding-forks procedure L62-69,
  activation paths L71-81
- `pmoves/docs/AGENTS/AGNOTE4482.md` — the corpus gateway workstream B links to
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` L2754-2759 — the six unsigned RELEASE
  rows; L2760 — the CLAIM recording the root cause
- `AGENTS.md:255-284` — § AGENTS.md Format Reference (hop 1); `AGENTS.md:363-365`
  — § Skills Constellation, the workstream-A prose
- `.claude/CLAUDE.md:25`, `:39-47` — the two places that route agents away from
  the fork (hop 2)
- `.claude/context/submodules.md:104-116` (agents.md), `:118-128` (skills table)
- `pmoves/configs/submodule_skill_registry.json` — `"skills/PMOVES-skills"`
  L1118, `"PMOVES-agents.md"` L1181
- `.claude/hooks/damage-control/patterns.yaml` — authoritative zero-access path
  list and blocked-command globs

## Notes

- **OPERATOR-GATED, do not perform without explicit approval:** (1) deleting the
  working-tree directory `skills/Pmoves-skills/`, (2) deleting its backing gitdir
  `.git/modules/skills/Pmoves-skills/`. Approve and perform both together, in
  that order. Emit them as a checklist in the PR body; never script them, never
  put them in a Make target or hook. They are stated as prose in A4 rather than
  as a runnable code block on purpose.
- **Never `git add -A` at repo root while `skills/Pmoves-skills/` exists.** It
  stages a `160000` orphan gitlink behind a warning, not an error. Stage explicit
  paths.
- **Do not move `PMOVES-agents.md/`.** Its root placement is the adjudicated
  outcome of PR3 §2.4, not an accident. Workstream B changes what points *at* it,
  never where it lives.
- **Do not edit vendored files inside `PMOVES-agents.md/`.** The fork tracks
  upstream `main`; a PMOVES edit there turns every fork-sync into a merge.
- **Do not touch `.gitmodules` in either workstream.** Workstream A's entry was
  already removed on purpose; workstream B adds no submodule.
- **Zero-access material.** Neither workstream needs a secret. The tier env files
  and the CHIT secrets manifest are on the damage-control zero-access list — no
  read, write, grep, or diff, and several command globs around them are blocked
  outright. `.claude/hooks/damage-control/patterns.yaml` is the authoritative
  list; consult it rather than restating paths, and never route around a block.
- No LAN or raw Tailscale IPs in any file or commit message — hostnames only.
- Never `git stash` in this repo (~10 pre-existing stashes; a bare `pop` restores
  another agent's WIP). Use a worktree, or `git archive` into a temp tree.
- Claim the lane in `AGNOTE4482PHI.t1.md` before editing, and sign the RELEASE
  with both `agent_signature: ACK::<AGENT>::<MARK>` and
  `<!-- GRAPHITI_MARK: … -->`. Omitting them is the exact defect workstream B
  exists to prevent — a run that fixes the signpost while repeating the miss is
  not a fix.
- Scope discipline (PR3 §2.3): `.claude/context/submodules.md:11` still says
  "Total submodules: 54" and the real count is higher. It is stale. Leave it —
  a count audit is its own slice.

### Handoff Target

The operator named the implementer for this brief: **PMOVESxDARKXSIDExKiLO-KlAW**.
Everything below is what an agent needs to pick the brief up, plus the one thing
about that handoff that is *not* settled.

#### Which profile — an operator decision, not resolved here

The name maps onto two different profiles, and the corpus says they are not
interchangeable:

| profile | what the corpus says it is |
|---|---|
| `pmoves/configs/agent-profiles/kiloclaw.yaml` | the **node-agnostic harness target** — "the fleet-wide KiloClaw identity behind the bootstrap routing entry (`pmoves-bootstrap/v1` CGP: `routing.kiloclaw`, wire target `glm-5.1`)" (header, L4-5). Model `glm-5.1`, control agent `mavis`. |
| `pmoves/configs/agent-profiles/kilocode_glm.yaml` | the **5090 DARKXSIDE co-creation edition** — and `kiloclaw.yaml`'s own header (L8-9) says it is "**not** the harness target." Model `glm-5-turbo`, control agent `darkxside`, `cocreator: darkxside`. |

`PMOVESxDARKXSIDExKiLO-KlAW` reads like the DARKXSIDE edition — which is the one
the corpus explicitly excludes from harness dispatch. Both readings are live:

- **Reading 1 (harness).** The operator means the dispatchable claw, and
  DARKXSIDE is attribution: DARKXSIDE witnesses all three 5090 agent interfaces
  per `KRISS_KROSS_ACK.md` § "KiloCode GLM — Third Agent on 5090", so the name
  can carry the witness without naming a different profile. Target is
  `kiloclaw.yaml` and the subjects below apply as written.
- **Reading 2 (co-creation edition).** The operator means `kilocode_glm.yaml`
  literally. Then this is a **5090-local, operator-driven** handoff and not a bus
  dispatch at all: that profile does not subscribe to `pmoves.agent.task.v1` —
  only `claw.task.assign.v1`, `botz.workitem.claimed.v1`, and
  `mesh.gpu.model.loaded.v1`.

**Do not pick one silently.** The readings differ in model, in control agent, and
in whether a harness dispatch is even possible. The operator decides. Record the
choice in the CLAIM row so the next agent inherits the answer instead of this
paragraph.

#### Dispatch subjects

Per `kiloclaw.yaml` § `nats` (L52-60), cross-checked against
`pmoves/tools/agent_task_subscriber.py:70-71`:

| direction | subject | note |
|---|---|---|
| in | `pmoves.agent.task.v1` | harness dispatch; match `target=glm-5.1` / alias `kiloclaw` |
| in | `claw.task.assign.v1` | direct claw lane — the only inbound lane both profiles share |
| out | `pmoves.agent.result.v1` | harness result return |
| out | `claw.task.complete.v1` | claw completion |
| out | `agent.graphiti.signed.v1` | signed-trail emission |

Node-side worker: `pmoves/tools/agent_task_subscriber.py --agent glm-5.1 --alias kiloclaw`.

#### Node affinity — this handoff leaves B850

`kiloclaw.yaml` § `node_affinity` (L21-24): **5090** (primary), **laptop-4090**
(portable), **z890** (fallback). `kilocode_glm.yaml` lists the same three.
**B850 (Knuckles) is on neither list.** This brief was written on B850; the
implementation is expected to run elsewhere. An implementer that finds itself on
B850 should read that as a signal it picked up the wrong lane, not as a fallback
to improvise around.

#### The dispatch surface is UNVERIFIED

`kiloclaw.yaml`'s own header (L14-15) states the precondition: *"Until that
subscriber runs on a node, the routing entry is a hint, not a dispatch surface."*

What was measured, on B850, 2026-09-03:

- `agent_task_subscriber.py` is **not running on B850** — `pgrep -af
  agent_task_subscriber` with the self-match excluded returns no match, exit 1.
- Whether *any* consumer is attached to `pmoves.agent.task.v1` **fleet-wide**
  **could not be measured from this node.** The NATS containers publish no
  host-mapped monitoring port, and `/varz` + `/subsz` on both 8222 and 9223
  return HTTP 000 / URLError from here.

Under the exit-code doctrine — `0 clean · 1 findings · 3 could not measure` —
**could-not-measure is not a pass.** So the dispatch surface is UNVERIFIED:
nobody has shown that publishing to `pmoves.agent.task.v1` reaches KiloClaw. A
publish that succeeds proves the broker accepted the message, not that anything
is listening.

Exactly two things would settle it. Either is sufficient:

1. **A reachable NATS monitoring endpoint.** Query `/subsz` and `/varz` on a node
   where the monitoring port is actually mapped, and show a subscriber on
   `pmoves.agent.task.v1`. Refer to that node by hostname.
2. **Confirmation from a node with affinity** (5090, laptop-4090, or z890) that
   `agent_task_subscriber.py --agent glm-5.1 --alias kiloclaw` is running there —
   either a process listing, or a round trip: publish a no-op task and observe
   the matching `pmoves.agent.result.v1`.

Until one of those lands, hand the brief over out-of-band — operator, or the
AGNOTE lane board per `mavis_inter_agent_handoff_LEARNINGS.md` Lesson 6 — and say
in the CLAIM that the bus path is unverified. Do not report a bus dispatch as
delivered on the strength of a successful publish.

#### Closing the loop

On completion the implementer signs a trail: `kiloclaw` carries capability
`trail_signing` (`kiloclaw.yaml` L49) and publishes `agent.graphiti.signed.v1`.
The registered signing identity is **`kilocode`** in
`pmoves/config/agent_signatures.yaml` (glyph U+25B2, emerald `#059669`, voice
*architectural*), with alter **`kilocode-glm`** for the GLM / 5090 / DARKXSIDE
mode.

Then file a register row in `AGNOTE4482PHI.t1.md` carrying **both**:

- `agent_signature: ACK::<AGENT>::<MARK>`
- `<!-- GRAPHITI_MARK: … -->`

That pairing is not optional decoration. The marker appears **307 times** in that
file at this branch's tip (measured 2026-09-03; the count tracks the register, so
re-measure rather than quoting this number). Six rows filed on B850 on 2026-09-03
omitted both — the motivating incident recorded in PR #2915 and in B2 above. A
handoff that lands the work and then files a bare row repeats the exact defect
this brief exists to close.
