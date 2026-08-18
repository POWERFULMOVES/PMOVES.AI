# Handoff — Skill-check Danger Room, verifiable artifacts → SPARK

**Date:** 2026-08-08
**From:** 4090-claude (field)
**To:** SPARK — named owner
**Substrate:** `PMOVES-E2B-Danger-Room` (E2B fork, submodule, populated)
**Coordination:** Village Rule — CLAIM in `AGNOTE4482PHI.t1.md` before starting.

---

## Why this exists

Today's work made every *named* thing in this repo checkable. It made nothing *worked* checkable.

`make -C pmoves validate-command-anchors` (#2488, #2494) proves a skill's commands resolve — the target exists, the path exists, the host is in the topology, the guard's road isn't a dead end. It cannot prove the skill **does what it says**. A skill can be perfectly anchored and completely wrong.

That is the next rung, and it needs somewhere safe to fail.

### The ladder, named

| Tier | Question | Mechanism | Status |
|---|---|---|---|
| **1 — anchored** | Does everything it names exist? | `validate-command-anchors` | **shipped** #2488 / #2494 |
| **2 — exercised** | Does it do what it claims, on a real node? | **Danger Room** | **this handoff** |
| **3 — receipted** | Can any node verify that without re-running it? | CHIT-signed artifact + NATS | designed here, follows T2 |

Each tier is useless alone and compounding together. T1 without T2 is a spell-checked lie. T2 without T3 is a result only the node that ran it can trust.

---

## Why SPARK

Not availability — capability.

- **DGX GB10 Grace-Blackwell, 128 GB unified** (`configs/claws/scopes/spark.json`: `role: gpu-inference`, `hostname: pmoves-spark`). A skill that says *"route through TensorZero to a local model"* can be **actually exercised** there. On a CPU node the same run is a mock, and a mock receipt is worse than none.
- **`sign_trail: true` and `damage_control_hooks: true`** are already set in its claw scope. T3 needs no new trust wiring — the signing identity is live.
- **Unlimited quarters.** A sandbox resets free. The whole point of a Danger Room is that failure costs nothing, so a skill can be run against its *worst* fixture rather than its friendliest.

---

## The stage I need

I am not asking for the Danger Room to be designed around me. I am naming the smallest set of artifacts that lets me observe a result and believe it, at my own pace, without being present for the run.

### 1. A `pmoves-skill-check` sandbox template

Sibling to the existing `templates/base`. Must contain the repo checkout **with submodules populated** — the gap documented in `pmoves/docs/operations/SUBMODULE_BUILD_AND_MOUNT_GAP.md` applies here directly, and a Danger Room whose sandbox has empty submodule dirs will produce confident false negatives.

Note the gitlink is currently drifted (`git submodule status PMOVES-E2B-Danger-Room` shows `+`). Sync before building the template.

### 2. A skill verification contract, declared in the skill itself

Skills today carry only `name` and `description`. Nothing declares scope, node affinity, or what success looks like. Proposed frontmatter extension — **additive, so an undeclared skill is simply "unverified" rather than broken**:

```yaml
---
name: ci-expedition
description: ...
# --- verification contract (new, optional) ---
scope: [docker, remote]        # command domains; same vocabulary validate_command_anchors
                               # already classifies targets by (docker/remote/python/
                               # git/systemd/nats/secrets/meta)
nodes: [any]                   # affinity, NOT a lane. [spark] only when the skill
                               # genuinely needs that hardware.
danger_room:
  fixture: ci-red-startup-failure
  artifacts:
    - kind: exit_code
      expect: 0
    - kind: file
      path: triage.json
      must_contain: ["signature", "fix"]
    - kind: assertion
      that: "classified signature equals the fixture's planted signature"
  budget:
    wall_s: 120
    quarters: unlimited
---
```

`scope` deliberately reuses the classifier that already exists rather than inventing a second vocabulary — a skill's declared scope and its commands' actual scope should agree, and disagreement is itself a finding.

### 3. A fixture is a planted failure, not a happy path

The fixture's job is to make the skill's claim falsifiable. `ci-expedition` claims it can tell a `startup_failure` caused by broken YAML from one caused by an Actions allowlist block. A fixture plants **one** of those and asserts the skill names it. A fixture that plants nothing verifies nothing.

Fixtures live beside the skill, versioned with it. When a skill's claim changes, its fixture must change — that coupling is the point.

### 4. The artifact contract — what makes it *verifiable* rather than merely *reported*

An artifact I can trust without having watched the run:

- **deterministic** — same fixture, same skill version → same verdict. Non-determinism is a defect in the fixture, not an acceptable variance.
- **self-describing** — carries skill name, skill content hash, fixture id, node, wall time, verdict, and the artifact hashes. A verdict without a content hash cannot be tied to the thing it judged.
- **signed** — CHIT, `kid` present. Unsigned is fine for local iteration and must be *labelled* unsigned, never silently equivalent.
- **addressable** — a path any node can fetch. A verdict on Spark's local disk is a rumour everywhere else.

### 5. The CHIT reflection — native to each, reflected in all

This is the part I care most about, and it's where the design earns the "unlimited quarters" framing.

Each node runs the skills its `scope`/`nodes` declaration matches. Native. Different nodes will legitimately produce different results for the same skill — that is information, not inconsistency.

Each run emits one receipt:

```
skill.verified.v1
  { skill, skill_sha, fixture, node, verdict, artifacts[], wall_s, ts, sig, kid }
```

Published to NATS, accumulated into every node's CHIT map. The effect: **"works on spark, untested on 4090, failed on knuckles at fixture X"** becomes a fact any agent can *read* rather than folklore it has to *discover*.

Subject naming and closed-schema registration should follow the existing convention — see `.claude/context/nats-subjects.md`. Register before publishing; the `archon.crawl.*` family is the cautionary tale of a subject registered against an operation that was never built.

---

## What this gives a small model — the actual payoff

A 1B-parameter agent cannot judge whether a skill will work. It can *read a receipt*.

That inverts where the competence lives. The heavy model runs the Danger Room, hits the failure modes, and pays the cost once. The receipt it leaves is pre-digested context: *this skill, this fixture, this node, this verdict.* A small model downstream doesn't reason about it — it selects on it.

That is the bridge. Bigger models building sensing surfaces that smaller models can stand on, and the smaller model's constrained choice feeding back richer signal about which skills actually get reached for. Learning on both sides, and neither side has to hold the whole system.

It is also the same principle already proven in `patterns.yaml`: the guard doesn't ask the model to know PMOVES, it *hands over* the correct path, valid parameters, and how to verify. Capability living in the field rather than the model. The Danger Room extends that from "what to do when blocked" to "what actually works."

---

## Boundaries

**Not in this handoff:**
- Deploying `e2b-mcp-server`. Agent Zero registers `e2b.sandbox.*` / `e2b.spell.execute` / `e2b.surf.scrape` pointing at `e2b-mcp-server:7073`, which is not a compose service, is not running, and — for `surf` — has no route in the fork at all. That is a real and separate lane; do not let it block this one, and do not assume those MCP commands work because they are registered.
- Retrofitting all 31 skills. The contract is additive. Two or three skills with real fixtures beat thirty with aspirational ones.
- T3 wiring itself. Design it now so T2's artifacts are shaped to carry it; build it after T2 produces something worth signing.

**Owned elsewhere:** `pmoves/mk/infra.mk` (z890, #2480), WS4-B living-docs mesh (recommended to Mavis-5090).

---

## Acceptance — how I will observe, at my pace

I do not need to watch a run. I need to be able to answer these from artifacts alone:

1. `templates/pmoves-skill-check` exists, and a sandbox built from it has **populated submodules** (`git submodule status` shows no leading `-`).
2. At least one skill declares the contract, and at least one fixture plants a falsifiable failure.
3. A run against that fixture emits a self-describing artifact carrying the skill content hash.
4. Re-running the same fixture against the same skill sha yields the same verdict.
5. **A deliberately broken skill fails.** This is the acceptance test that matters — a harness that only ever passes has verified nothing. Break `ci-expedition`'s signature table on a branch, run it, and show me a red artifact.
6. The receipt shape is registered before it is published.

(5) is the one I would cut last. Every gate I shipped today was weaker than advertised until something proved it could say no.

---

## Trail

Three-body: delivery=SPARK, control=DARKXSIDE, memory=this doc + the AGNOTE row + the receipts themselves once T3 lands.

---

## Re-scope check — 2026-08-16 (4090, before assignment)

Eight days on, re-measured against `origin/main` @ `017de5369` before handing this to SPARK.
**The scope holds.** Nothing below replaces the text above; it records what is still true, what
is newly available, and one thing that got sharper.

### Still true, verified not assumed

| Claim in this handoff | Checked | State |
|---|---|---|
| E2B gitlink drifted, sync before building | `git submodule status PMOVES-E2B-Danger-Room` | **still drifted.** Working copy `7a38b33b`, `origin/main` records `78f7c5d8`. The pre-req is unresolved — it is the first thing to do, not a footnote. |
| 31 skills, retrofitting all of them is out of scope | count of `.claude/skills/*/SKILL.md` | **still 31.** Unchanged. |
| No skill declares the verification contract | grep for `danger_room` / `scope:` in skill frontmatter | **still none.** Piece 2 is untouched. |

### Newly available — acceptance criterion 1 can now be a command

Acceptance 1 asks that a sandbox built from the template have populated submodules. When this
was written that was an eyeball check. Since then:

- `pmoves/docs/operations/SUBMODULE_BUILD_AND_MOUNT_GAP.md` merged (#2485) — the failure is now
  documented, including that Docker **creates** a missing bind source as a directory rather than
  erroring, which is exactly how a sandbox produces a confident false negative.
- `make -C pmoves bind-sources-check` (#2581) asserts every submodule-backed compose bind source
  exists and is the right kind, and distinguishes *missing* from *directory-where-file-expected*.

So acceptance 1 should be stated as two commands rather than an inspection:

```bash
git submodule status | grep '^-' && echo "UNPOPULATED" || echo "populated"
make -C pmoves bind-sources-check
```

A sandbox that passes both cannot silently be the empty-submodule case.

### Sharper — the `archon.crawl.*` cautionary tale is worse than this doc says

Piece 5 cites `archon.crawl.*` as the reason to register `skill.verified.v1` **before** first
publish: "a subject registered against an operation nobody built." That description was too kind,
and the real version matters for the artifact contract.

`archon.crawl.*` has a handler. `ArchonOrchestrator._process_crawl` takes the `metadata` dict
**from the request message** and republishes it unchanged as `extracted_text` and `fragments`,
stamped `"status": "completed"`. Nothing fetches the URL. Its tests assert dispatch *routing*
and never that a crawl occurred. (Documented 2026-08-16, PR #2582.)

**A subject that is never implemented times out and you notice. This one reports success.** For
`skill.verified.v1` that is the precise failure to design against: a receipt reading PASS because
the harness echoed back what the request handed it. Which means the artifact must carry the
**skill content hash** — already required by piece 4 — *and* something the harness could only
know by actually running: exit codes, wall time, emitted paths. A receipt derivable from the
request alone is `archon.crawl.result.v1` wearing a different name.

This also raises acceptance (5) from "the one I would cut last" to **the one that defines the
lane**. A Danger Room that cannot emit RED is a publish→echo circuit.

### Unchanged and still correct

The boundaries hold: `e2b-mcp-server` stays out of scope (still not a compose service), and
retrofitting all 31 skills stays out of scope. Two or three real fixtures still beat thirty
aspirational ones.

**Not claimed by 4090.** SPARK remains the named owner; this row refreshes the lane, it does not
take it.
