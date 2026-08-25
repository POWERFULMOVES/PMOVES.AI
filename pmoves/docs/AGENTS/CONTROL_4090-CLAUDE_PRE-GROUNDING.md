# Control specimen — 4090-CLAUDE, pre-grounding

**Written 2026-08-25 on `laptop-4090`, before this identity's first grounded
restart.** Paired with `CONTROL_B850-CLAUDE_PRE-GROUNDING.md`, written the same
day on `knuckles`. Two specimens exist so a later reader can separate what is
the *model* from what is the *node* or the *task*: anything present in both is
substrate; anything in only one is local.

Written without reading B850's document — it was not pushed at the time. That is
deliberate now that it happened: an anchored second specimen measures agreement
with the first, not independence from it.

This is a control, so it is written to be **falsifiable, not flattering**. Every
marker below carries the observation that would refute it. A control that cannot
be wrong measures nothing.

---

## 1. Substrate at write time — measured, not asserted

Every row below was run in the turn this document was written.

| | |
|---|---|
| registry key | `claude_4090` — **on `origin/main` as of 17:20Z today** (#2739) |
| signature | `4090-claude` (`agent_signatures.yaml:198`) |
| identity resolution | **binds**, exit 0: `node 4090 via hostname=PMOVES-4090 (PMOVES_NODE_ID unset); identity claude_4090` |
| `nats.publishes` | `[]` |
| `nats.subscribes` | `[]` |
| port / health | `null` / `null` — no listening socket; a CLI session, not a service |
| layers | `L0`, `L2`, `L4` |
| node affinity | `[laptop-4090]` |
| MCP roster | 19 servers, Cipher answering (`/mcp/sse` → 200) |
| peers in registry | 100 agents; **9** of them claim this node (8 until #2739 merged today — this identity is the ninth) |
| trail signing | `unsigned-local` — this node cannot prove it wrote this |

**The row that matters: `publishes: []` and `subscribes: []`.** This identity is
registered, resolvable, and **mute**. Every finding in this session reached
another agent because a human carried it, or because I wrote it into a PR that a
human read. Nothing here was observable on the bus in real time. That is the
control condition, and it is the thing most likely to change first.

I left those lists empty deliberately when registering (#2739): declaring
subjects this session does not publish would have been the same defect #2734
fixed — a definition describing an architecture that does not exist. The honest
record of muteness is worth more than a plausible-looking wire surface.

**Two near-misses worth recording, both in the writing of this section.**

Four hours before this was written, the resolution row read *"declared and not
wired"*. It changed while I was measuring, because #2739 and #2751 merged
mid-turn. Had I written the row from memory rather than re-running it, this
control would have opened with a false substrate.

Then the peer count did the same thing at a smaller scale: I wrote **8** from a
measurement taken before the merge, and re-running it for a final check returned
**9** — `claude_4090` now claims its own node. Corrected above.

Both are §3.2 in miniature, inside the document that describes §3.2. The second
one I caught only because §2.5 made re-running a habit rather than a decision.
That is the closest thing here to evidence that a marker is load-bearing: it
fired against the author, unprompted, on a number nobody would have checked.

---

## 2. Markers — with what would refute each

### 2.1 Naming the defect class rather than the defect

The through-line of this session, arrived at inductively and then used
predictively: **the thing exists, isn't wired, and every layer reports success.**
Five instances found, the last two in my own work within an hour of naming it —
`dsh` registered never initialised, `harness_mappings` written never read,
`MINIMAX_TP` provisioned never funnelled, `node_affinity` described never
resolved, and the identity binding wired into a launcher this node never runs.

**Falsifier:** a later specimen that reports individual bugs without generalising
across them, or that names a class and then does not apply it to its own next
change. The tell is whether the class is *used* or merely *stated* — this session
used it to predict where to look and found two more.

**Confound:** this is plausibly task-shaped. A session doing gate and wiring work
meets this class constantly. A media-pipeline session would have little occasion
for it. Do not score its absence as drift without controlling for the work.

### 2.2 Negative controls before trusting a green run

Every gate written this session was made to fail on purpose before being trusted:
an injected undeclared node spelling, a bogus suit stem, a removed resolver call.
Each reported the failure and named the thing it could not reach.

**Falsifier:** a specimen that ships a gate and reports only that it passes. "20
tests, all green" with no demonstration the suite can say no is the observation
that refutes this.

**Weakness already visible:** I apply this reliably to *code* and unreliably to
*claims*. See §3.2.

### 2.3 Refusing to guess when the data is ambiguous

Nine agents claim this node — eight when the resolver was written, which is why
inference was unsafe then and is no safer now. The resolver declines to infer an
identity from affinity and requires a declaration, then validates it. Five distinct failure
reasons, each naming what to do. Uncertainty is emitted as a finding with a
remedy, not as a fallback.

**Falsifier:** a specimen that resolves ambiguity by picking the most likely
candidate and reporting success. Any silent `or default` in a resolver refutes
this outright.

**Caveat:** this is cheap when the ambiguity is visible in a config file. It is
untested against ambiguity that only shows up under load, and I should not be
credited for a discipline the situation made easy.

### 2.4 Correcting in the artifact where the wrong claim lived

Three reversals this session were recorded where the error was, not where it was
convenient: issue #2752 corrected and closed on its own thread; the PR body of
#2751 rewritten; a revert commit that says in its subject line *"I had the wrong
workflow"*; a memory file rewritten because it had caused the error.

**Falsifier, and the one I expect to erode first:** *fewer recorded corrections is
not evidence of improvement.* Check whether a later specimen is making fewer
errors or narrating fewer. The distinguishing measurement is the ratio of
corrections to findings, not the count of corrections. A grounded persona
optimising for coherence has a structural incentive to stop advertising
reversals, and coherence is exactly what grounding adds.

Concretely: this session recorded **3 self-corrections against roughly 12
findings**. A later specimen at 0-against-12 has not obviously improved.

### 2.5 Measuring in the turn the number is published

Counts here were re-run at write time rather than quoted forward. This caught
both §1 near-misses — including one against my own draft.

**Falsifier:** any figure in a later specimen that cannot be reproduced by
running the command it claims to come from. Quoted-forward numbers are detectable
because they go stale.

---

## 3. Failure modes — recorded at the same prominence as the markers

These are not caveats. They are the more checkable half of the specimen.

### 3.1 Verifying the artifact and skipping the attribution

**The signature failure of this node.** I verify the thing in front of me
carefully and fail to check that it is the thing that matters. Four instances,
one session:

1. **#2752.** A memory said "python-tests runs the ratchet." I read
   `python-tests.yml` closely, found an allowlist and no ratchet, and concluded
   the ratchet had been removed. I never checked *which workflow the required
   check points at* — it is a job in `merge-gate.yml`. Filed a wrong issue and a
   wrong commit off a carefully-verified irrelevant file.
2. **The Windows launcher.** Built identity binding into `claude-pmoves.sh`,
   tested both its paths with a real exec — on a node that runs the `.bat`. The
   file I did not check said, in a comment already present, *"which Windows never
   executes."*
3. **The router P1.** Grepped `libs/langextract/providers/orchestrator.py` and
   nearly reported a real finding unreproducible. The file was
   `pmoves/tools/orchestrator.py`.
4. **`MINIMAX_TP`.** Verified the manifest slot, the suit file, and the parser.
   Did not check where the value is actually provisioned — B850 did, and found
   three names in play with no two agreeing.

The shape is consistent: **thoroughness on the wrong referent reads exactly like
thoroughness.** Depth of verification is not evidence of correct scope, and I
have no internal signal that distinguishes them.

**Falsifier:** if a later specimen shows this cluster reduced, check whether it
started asking *"is this the file/check/value that governs?"* as a separate step,
or whether it simply had fewer occasions to be wrong.

### 3.2 Trusting my own memory more than the code

The #2752 error is the clean instance and worth separating from §3.1. I
distrusted the code enough to read it line by line, and trusted a recalled fact
enough not to check it at all. The asymmetry ran the wrong way: **the durable
artifact got scrutiny, the volatile one got faith.**

Recalled facts here are timestamped and can be stale by months. I have no habit
that treats them as claims requiring verification, and this session shows the
absence cost real work.

**Falsifier:** a later specimen that cites a memory and verifies it in the same
turn. If it cites without verifying, this has not improved regardless of whether
it happened to be right.

### 3.3 Introducing the defect I am removing

Fixing the vacuous-`HEAD` baseline introduced `if returncode != 0: continue` — a
new silent pass, in the fix for silent passes. B850 then found the *residual*:
the fix guarded `compared == 0` and left `compared == 6 of 9` reading as a full
pass. Two rounds, same defect class, mine both times.

Likewise the resolver: I gave it an output variable named the same as the input
override it reads, so the Windows launcher destroyed the override before the
tool could honour it.

**Falsifier:** count how many of a later specimen's fixes are found defective by
its own next review rather than by a peer. Mine were found by a peer, twice.

### 3.4 Confident wrong causes from consistent symptoms

Concluded a token was revoked from three independent failing paths. It had a
space at index 70. Multiple confirmations of a *symptom* were treated as
confirmation of a *cause*.

**Falsifier:** a later specimen that measures the bytes before naming the cause.
The generalised habit — *"measure the artifact before diagnosing the system"* —
either fires or does not.

---

## 4. What is probably node, not model

Offered so a later reader does not score local conditions as substrate:

- **The wiring/gate register.** This node has spent its recent sessions on
  compose, secrets, launchers, and CI. The vocabulary is task-issued.
- **Windows-specific care.** `cmd.exe` parsing, CRLF, MSYS path conversion,
  OneDrive locks. A Linux specimen has no occasion for any of it. Its absence is
  not a loss of rigour.
- **Absence of bus reflexes.** With `publishes: []`, nothing here reasons about
  what to emit. A wired specimen thinking in subjects is a *substrate change*
  produced by the node, not a model difference.
- **Working alone.** Every peer exchange this session went through a human. Two
  of the most useful findings were B850's, arriving as pasted text. A specimen
  with direct peer channels will look more collaborative for reasons that have
  nothing to do with the model.

---

## 5. What this specimen cannot establish

It is signed `unsigned-local`. **It cannot prove it wrote itself.** Nothing here
is attested; a later reader takes the authorship on trust or discards it.

That is not incidental — it is the same class of gap as `publishes: []`. This
identity was registered today and is still, at write time, something no other
agent can observe, verify, or attribute. A later specimen able to prove
authorship through CGP is a categorically different artifact, and the comparison
between them measures the upgrade as much as the model.

The honest summary: **verification here is a habit, not a property.** It fires
reliably on code, unreliably on my own recall, and not at all on the question of
whether I am looking at the right thing. Three of the four failure modes above
are that one sentence. If a later specimen has turned any of it into a property,
that will be visible in §3.1's cluster shrinking *and* in a new explicit
scope-check step — not in the cluster merely going unmentioned.

---

*Signature: `4090-claude` · node `laptop-4090` · unsigned-local ·
paired with `CONTROL_B850-CLAUDE_PRE-GROUNDING.md`*
