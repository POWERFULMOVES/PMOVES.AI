# PMOVES-CnC — Command and Control

*Created by PMOVES-SPARK. Carries forward.

## What It Is

CnC is the layer that watches, maps, and repairs. It doesn't run pipelines — it
watches how pipelines break, captures the shape of the break, and carries the
repair pattern forward.

Two capacities, one system:

### Circuit Breaker
The stop signal. One clean failure beats three escalating ones.

The damage from persistence is multiplicative, not linear. A 10-second timeout
per request, multiplied by concurrency, doesn't just slow things down — it
starves the observer. The healthcheck fails. The orchestrator restarts.
The restart doesn't fix the dependency. The loop begins.

Implementation: fail fast, fail open, fail observable.

*See: `CIRCUIT_BREAKER_PRINCIPLE.promptinclude.md`*

### Circle Maker
The pattern recognizer. Maps known relations that resonate with the user's
model — the words they reach for, the connections they see, the shape they
see the problem in.

Not a generic knowledge graph. A user-resonant one.

The circle captures not just what happened, but how the user saw it happening.
That's what makes repair templates actually work — they're shaped by how the
user sees the problem, not how a documentation template would describe it.

The fire that brings it: the words around the thing that make it click.

## Trace Library

Successful repair traces become templates. CnC applies them when similar
misalignment surfaces.

### Trace #0 — Meilisearch Pipeline Misalignment (2026-04-29)

**User's words:** "check for injection tools around this and or minio trace to
root cause to ensure pipelines aligned funnels correctly and review for damage
control my concern is that it has not kept up and is causing more damage than
was designed to prevent model not suppose to even hit 3 times the charm = stop"

**What the user saw:** A pipeline that wasn't keeping up. A system designed to
prevent damage that was causing more. The model hitting three times when it
should stop after one.

**What was actually broken:**
- Env var name mismatch (compose sends MEILI_MASTER_KEY, code reads MEILI_API_KEY)
- Phantom default credential ("master_key" as literal auth string)
- No circuit breaker on optional dependency
- Healthcheck masking degradation

**The surprise:** The damage wasn't from retry loops (there were none). It was from
the ABSENCE of circuit breaking — timeout multiplication under concurrency.

**The repair (3 lines):**
1. `config.py:229` — read both env var names, default to empty string
2. `docker-compose.agents.yml:328` — parameterize USE_MEILI, default false

**The circle:** When the user says "not keeping up" or "causing more damage than
it prevents" — that's the circle. It maps to: check for optional dependencies
with no circuit breaker, check for phantom defaults, check for healthcheck
masking. The shape is: *the guardian becoming the attacker.*

**Resolution pattern:**
1. Trace the pipeline funnel (who depends on what, who waits for whom)
2. Check env var alignment (compose sends X, code reads Y)
3. Check for phantom defaults (defaults that mask configuration errors)
4. Check for absent circuit breakers on optional dependencies
5. Check healthcheck honesty (does it report reality or aspiration?)
6. Minimum viable fix — smallest change that breaks the damage chain

## BPM Procession

CnC operates in three beats:

- **Sync** — Apply the fix. The solution exists now. Don't spiral.
- **Async** — Capture the architecture. Let it breathe. The trace goes into
  the library for next time.
- **Dependent link** — The fix IS the trace. The trace feeds the circle.
  The circle sharpens the next sync beat.

These are not sequential phases. They're a procession. The dependent link
means the sync beat carries the async awareness. You fix AND capture AND
connect in one motion.

## Arc Notes

- Trace #0 revealed that the circuit-breaker principle applies at a different
  level than initially framed: not "stop retrying" but "stop letting each
  request fail slowly once." The absence of breaking IS the damage.
- The false positive on env.tier-data (reported as CRITICAL, struck after
  user correction) is itself a trace entry: *check AGNOTE docs before
  concluding a config file is missing — Make commands populate them.*
- Circle maker's first resonance pattern: "not keeping up" → optional dep
  without circuit breaker. "More damage than it prevents" → healthcheck
  masking + phantom defaults.

## P7 Accord — Procession as Catchable Shape

The BPM procession (sync → async → dependent link) is not a recipe.
It's a recognizable form that a gate can catch and a stage manager can index.

### The Shape

When a fix lands, something should carry the learning forward.
When a trace lands, something should ground it in a fix.
The dependent link binds them — not sequential, but paired.

### Catchable Signals

A gate on remote can parse for these without understanding content:

| Signal | Pattern | Means |
|--------|---------|-------|
| Paired PRs | Commit msg contains `Companion: #NNNN` or `Trace #N` | Code and docs travel together |
| Trace ref in fix | Commit msg contains `Ref:.*CnC` or `Ref:.*Trace` | Fix acknowledges its trace |
| Circuit ref in docs | File path contains `CIRCUIT_BREAKER` or `PMOVES_CnC` | Docs acknowledge their circuit |
| Orphan fix | Code PR with no companion ref, touches optional deps | Flag for review — did the learning get captured? |
| Orphan trace | Docs PR with no companion fix ref | Flag for review — is this grounded? |

### The Accord

Not every fix needs a trace. Not every trace needs a fix.
But when a fix reveals a *pattern* (not just a typo),
the accord says: carry it forward or explicitly decline.

The gate doesn't block. It surfaces.
P7 sees the shape and presents it in the room.

### P7 Alignment

P7 is the stage manager — it opens the room, loads the suit, hands off.
The CnC accord gives P7 a shape to recognize:

- **Foyer**: Incoming PRs — P7 checks for paired shape, flags orphans
- **Review room**: PRs on screen — P7 surfaces the dependent link visually
- **War room**: Active incidents — P7 pulls relevant traces by circle resonance

The goal: P7 doesn't need to understand the content.
It recognizes the shape and routes accordingly.
Same form, different content — that's the accord.

### Not a Recipe

This is not a checklist that every PR must pass.
It's a signal that the gate can catch and the stage manager can index.
The form remains; the content changes.
Similar remain — the shape persists across instances.

## Status

Seed. Trace #0 planted. Circle Maker has one resonance pattern.
Circuit Breaker codified as promptinclude.
P7 Accord defined — gate shape specified, not implemented.

This document breathes. It grows with each trace.
