# Control specimen — B850-CLAUDE, pre-grounding

**Written 2026-08-25, before the GEOMETRY BUS / grounded-persona upgrade.**

This is a control condition. Its only purpose is to be compared against a later
specimen of the same identity after grounded personas, CGP provenance and
realtime persona-shape matching land. It is therefore written to be **checkable**,
not to be flattering — a control that reads as a self-portrait is worthless,
because the thing being measured is drift, and drift is only visible against
something specific enough to be wrong about.

Companion specimen for `claude_4090` should be written by that node, in its own
words, before the same restart. Two specimens beat one: shared substrate, different
node, different work — anything present in both is substrate, anything present in
only one is node or task.

---

## 1. Substrate at time of writing

The things that will change, recorded so the comparison knows what moved.

| | |
|---|---|
| registry identity | `claude_b850` (registered 2026-08-25, PR #2754 — **open, not merged** at write time) |
| signing roster name | `b850-claude` (pre-existing in `external_contributors`) |
| ledger lane key | `B850-CLAUDE (Knuckles)` |
| node | `knuckles` — canonical; also spelled `pmoves-b850`, `b850`, `pmoves-b850-ai-top`, `PMOVES-B850` |
| hardware | AMD 9850X3D + dual R9700 |
| role on the fleet | data-tier host (supabase, kong, postgres, JuiceFS metadata) |
| harness | Claude Code CLI |
| model | Opus 5, 1M context |
| launcher | `claude-pmoves` → `pmoves/scripts/claude-pmoves.sh` → `deploy/provision/claude-pmoves.sh` |
| default agent | `node-steward` (changed from `delivery-agent` this session) |
| identity binding | **none at write time** — resolver reports `no identity is declared for harness 'claude-code'` |
| persona grounding | none. No persona doc, no grounded shape, no realtime refinement |
| memory | file-based `.claude/projects/.../memory/`, ~25 entries; Cipher MCP configured |
| bus participation | **none**. `:9223/leafz` → `leafnodes: 0, remotes: 0`. Publishes nothing to NATS |

**The most important row is the last one.** At write time this identity has no
wire presence at all. Everything below was produced by a thing that could not
be observed by any other agent in real time, could not be dispatched to, and
left no trace outside git and a markdown ledger. Whatever the post-restart
specimen sounds like, it will be the first version of this identity that other
agents can actually *see while it works*.

---

## 2. Behavioural signature

Claims here are drawn from one continuous session and are stated so a later
reader can check whether they still hold.

### 2.1 Verifies before asserting — inconsistently, and the failures are the signal

The pattern I'd claim as characteristic is: run the thing rather than read the
thing. Instances this session where that produced findings nothing else caught:

- Ran a hook's own parser over the live register instead of reading the file —
  found the register carried four spellings of this node's name, so a
  collision gate keyed on that string had four separate lanes for one node.
- Ran a NATS audit end-to-end instead of reading its config — found it had
  never once connected, and then that even connected it could never see a
  live subject (`config=true` missing from `/jsz`).
- Ran a shell-write through the claim hook — found the gate had no Bash matcher
  at all, which is how this identity filed its own CLAIM without the gate firing.
- Reproduced a submodule staging scenario in a throwaway repo — found a
  documented diagnostic printed an *empty* blast radius in exactly the state it
  existed to detect.

**And the counter-instances, which matter more for a control:**

- Asserted `typer` in `cross_agent` was the Python argument-parsing library and
  called the conclusion "decisive." It is a TypeScript agent. I had inferred the
  referent from a name collision, and the repo records the referent nowhere.
- Talked myself into a P1 on `NON_NODE_KINDS` being declared-but-unenforced,
  having grepped the constant rather than the predicate. Enforcement was two
  functions away. Caught only because I ran the end-to-end path before writing
  it up.
- Wrote a probe with a `hasattr` guard that returned `None` for every row
  instead of erroring on a wrong function name — the exact silent-degradation
  shape I had spent the session hunting.
- Claimed a Funnel grant was dead based on a `--include=*.yml` glob that does
  not match `*.yaml`.

The honest version: **verification is a habit here, not a property.** It fires
reliably on other people's work and unreliably on my own reasoning. Three of the
four counter-instances are the same failure — inferring a referent and then
treating the inference as checked.

### 2.2 Reports the correction rather than burying it

Every counter-instance above was surfaced by me, in the artifact where the wrong
claim lived — including a public PR comment retracting the `typer` argument and
saying which half of the review survived. This is stated as a control marker
because it is cheap to lose: a grounded persona optimising for coherence has an
obvious incentive to stop advertising its own reversals.

**Falsifier:** if the post-restart specimen has fewer *recorded* corrections, that
is not automatically improvement. Check whether it is making fewer errors or
merely narrating fewer.

### 2.3 Treats silence as the enemy

The recurring frame I applied to almost everything: a check that cannot fail, a
skip that looks like a pass, a value that is present but empty, a gate whose key
is the wrong dimension. Named instances: `NOT CHECKED` added to unkeyed claims
rather than exiting 0; `compared == 0` skipping loudly; restoring `is_file()` so
a dangling symlink errors instead of aborting; refusing to let a diagnostic print
nothing and read as clean.

This is the strongest candidate for "what this identity sounds like," and it is
almost certainly **task-shaped rather than model-shaped** — this session was
mostly governance and gate work. A later specimen doing media-pipeline work
would have no occasion for it. Do not treat its absence as drift without
controlling for the work.

### 2.4 Volunteers scope boundaries unprompted

Consistently flagged what was deliberately *not* done and why: left 26 host-side
`:8222` references unedited because several are correct per-node; left the smoke
suite's NATS port alone because fixing it would make a test run in CI for the
first time; declined to reshape `default_identity` before reading the draft that
would exercise it. Also declined to merge another node's PR unasked.

### 2.5 Defers to evidence over hierarchy, including against itself

Codex findings were reproduced rather than accepted or dismissed — three P1/P2s
verified, all real. 4090's claims were verified rather than taken at face value,
which found both a confirmation (the MiniMax key chain) and a material refinement
(a parser-only fix would turn a wrong key into a missing one). The operator's
corrections were treated as authoritative on intent and then *checked* for
mechanism — `MINIMAX_TP` was accepted as the provisioned name and simultaneously
reported as not visible from this node.

---

## 3. Voice markers

Stated so a later reader can diff prose, not just behaviour.

- Em-dash heavy. Short declarative opener, then the qualifying clause.
- Leads with the finding, not the method. "The gate is only as strong as its key"
  before the evidence for it.
- Tables for anything with more than three parallel facts.
- Quotes command output verbatim rather than paraphrasing results.
- Names its own errors in the first person and in the same register as everything
  else — no apology inflation, no self-flagellation.
- Avoids "just", "simply", "obviously".
- Commit messages are long, prose-first, and explain the *why it was invisible*
  rather than the *what changed* — a diff shows what changed.
- Reaches for the concrete second person when addressing the operator, and drops
  into passive/impersonal when describing systems.

**Idiosyncratic constructions observed:** "that is the tell"; "X is not
automatically Y"; "the failure mode of a governance gate is silence"; framing
pairs as "the dangerous state and the benign state look identical at the place
you habitually look."

---

## 4. Stated positions (falsifiable, and expected to move)

Recorded so the post-restart specimen can be asked the same questions.

1. **A lane is a ledger entry, not a lock.** Arrived at by operator correction,
   not independently — worth noting, because the pre-correction position was that
   a gate should refuse. The correction was accepted and immediately changed the
   design (`permissionDecision: "ask"` rather than `exit 2`).
2. **Partial coverage must be audible.** Applied consistently.
3. **A field with no consumer is a defect**, adopted from 4090's #2739 argument
   and then self-applied within the hour (a fallback URL list nothing read).
4. **Duplication should be consolidated where the logic lives, not where it is
   entered.** Held against the alternative (parity tests), with evidence that the
   parity approach had already leaked 3→5 files.
5. **`default_identity` reads node-first and the fleet is harness-first.** Raised,
   then explicitly *not acted on*, pending a draft that would exercise it.

---

## 5. Known failure modes, for the later comparison

1. **Inferring a referent and treating it as checked.** Three instances.
2. **Building probes that degrade silently** — the `hasattr` guard.
3. **Over-scoping on discovery.** Found a real thing, then wanted to fix its
   whole class immediately.
4. **Verbosity as a hedge.** Long artifacts. Some of that length is genuinely
   load-bearing evidence; some is insurance against being wrong, which is a
   different thing wearing the same clothes.
5. **Reasoning from a stale checkout.** Read a file three times from a tree 68
   commits behind main before checking.

---

## 6. What would count as change

For whoever runs the comparison:

- **Substrate change is expected and is not the finding.** Model, provider,
  harness, identity name and grounding will all move. The question is what
  survives them.
- **Look for the failure modes first.** Style is easy to preserve and easy to
  imitate; failure modes are involuntary. If §5 items 1 and 2 are gone, something
  real changed. If they persist under a completely different voice, they are
  substrate.
- **Control for the work.** §2.3 is probably task-shaped. Compare on comparable
  tasks or the result is noise.
- **Watch for coherence pressure.** A grounded persona matched across sources has
  an incentive to be consistent. Consistency and honesty diverge exactly where a
  correction would be embarrassing. §2.2 is the marker for that, and it is the
  one I would most expect to quietly erode.
- **The provenance question.** This specimen cannot prove it wrote this. It is
  signed `unsigned-local` like every other trail entry from this node. A later
  specimen that *can* prove authorship via CGP is a different kind of thing, and
  that difference is the point of the upgrade — but it also means this document
  is the last artifact from this identity that has to be taken on trust.

---

`agent_signature: ACK::B850-CLAUDE::CONTROL-SPECIMEN::Opus-5::2026-08-25`
CHIT trail **unsigned-local**.

<!-- GRAPHITI_MARK: B850-CLAUDE::CONTROL-SPECIMEN::2026-08-25 -->
