# Handoff — `pmoves/AGENTS.md` conformance + deferred doc/index work

**Node:** Z890 (win32) · **Agent:** Z890-CLAUDE (Delivery Body) · **Date:** 2026-08-28

## What this handoff is for

Operator observation: *"reference and format are two different things."* Root `AGENTS.md`
**referenced** the agents.md format; `pmoves/AGENTS.md` neither referenced nor followed it. This
records what was fixed now and what is blocked on two external events — PRs merging, and Cipher
being reachable after a restart.

## Landed

- `pmoves/AGENTS.md` restructured to **conform** to the agents.md format. All three canonical
  sections now present (`## Dev environment tips`, `## Testing instructions`, `## PR instructions`),
  achieved by renaming the equivalent existing sections rather than rewriting the file — the
  pmoves-specific content (ports, bring-up order, smoke commands) is preserved verbatim.
- Header block added: format note, scope statement (narrows root `AGENTS.md`, does not replace it),
  four cross-references a cold-start agent needs, and a **CHIT-awareness** block covering
  `claim → work → sign → release` and the `sign-trail` fallback-identity trap.
- **Two `pip install` instructions removed** — they contradicted the standing uv rule and had been
  sitting in a file six other documents point at.
- Registered in `pmoves/configs/living_docs_registry.yaml` (30 days, P2). It had drifted a month
  while unmonitored.

## Verified

| Check | Result |
|---|---|
| canonical sections present | 3/3 |
| `pip install` occurrences remaining | 0 |
| cross-reference links resolve | 6/6 |
| registry parses, no duplicate paths | OK, 29 entries |
| `.claude/skills/*/SKILL.md` package-format conformance | **33/33** (`name` + `description` frontmatter) |

Skills were checked because the same "do they follow the new package format?" question applied.
They do — the format is the `skills` npm package v1.5.22 contract (a directory containing
`SKILL.md` with YAML frontmatter). No action needed there.

## Deferred — blocked on PRs merging

1. **Submodule branch drift.** `.gitmodules` declares
   `PMOVES-agents.md  branch = PMOVES.AI-Edition-Hardened`, but the gitlink is checked out at
   `heads/main` (`d1ac7f063`). By contrast `skills/PMOVES-skills` correctly tracks
   `origin/PMOVES.AI-Edition-Hardened`. Moving a gitlink changes what every node checks out, so it
   wants an operator decision rather than a drive-by fix. **Open question: is `main` deliberate here?**

2. **Case drift on the skills submodule.** Git tracks `skills/PMOVES-skills`; the working tree has
   `Pmoves-skills`. `git status` is clean because Windows is case-insensitive — on a Linux node the
   checkout is `PMOVES-skills`, so any reference using the lowercase spelling breaks there. Needs a
   case-only rename done carefully (`git mv` via a temporary name), which is disruptive mid-flight.

3. **Neither `PMOVES-agents.md` nor `skills/README.md` is registered for freshness.** Deliberately
   not added in this pass: both are submodule-owned surfaces, and registering a path the
   superproject does not author needs a rule about who is responsible for refreshing it.

## Deferred — blocked on Cipher ready after restart

The operator intent is that any project PMOVES integrates carries enough context that *"whoever
reads gets along with PMOVES context and is CHIT aware"*, and that this is **indexed and
multi-referenced** rather than only cross-linked by hand.

Hand-written cross-references (what landed above) are the fallback. The durable version is an
index, and that needs Cipher:

- **Index the AGENTS.md set into Cipher** (`pmoves-cipher` SSE `http://localhost:8105/mcp/sse`) so a
  cold-start agent retrieves the contract by intent rather than by knowing the path. Marco/Polo
  pattern per the SITREP: store with one phrasing, retrieve with another.
- **Multi-reference** — the same contract reachable from root `AGENTS.md`, `pmoves/AGENTS.md`, the
  SITREP, and Cipher recall, so no single stale link is load-bearing.
- **Integrated-project template** — a minimal `AGENTS.md` stub any repo PMOVES pulls in can carry,
  giving PMOVES context + CHIT awareness without duplicating the whole contract.

Blocker on record: the memory stack is `cipher healthy 8105; STORE dead = Ollama 404; Qdrant empty`.
Retrieval-by-intent needs the store path working, not just the container up.

## Deferred — HuggingFace / unsloth

Operator note: HF integration exists for storing datasets, and unsloth work gets easier once
Z890-CLAUDE is on a node with Cipher. Not started; recorded so it is not rediscovered.

- HF Hub is already reachable as a tool surface (`huggingface-skills` plugin pack, `hf_fs`).
- `pmoves/docs/AGENTS/AGNOTE4482.md` records unsloth as a runtime-lane setup item: *"direct Python
  `unsloth` import is not installed in the base environment."* That is a prerequisite gap of exactly
  the kind `make -C pmoves check-prereqs-env` now reports — worth wiring unsloth into that tier's
  probe set once the lane is live.

## Related PRs open at time of writing

`#2761` (CLI preflight contract + interpreter tier), `#2814` (claim register row),
`#2815` (VS Code env manager), `#2816` (interpreter discovery fix).
`#2816` is the one that makes `sign-trail` resolve a real identity instead of a fallback — the
CHIT-awareness note in `pmoves/AGENTS.md` assumes it lands.
