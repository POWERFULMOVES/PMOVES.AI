---
name: pmoves-chit-sign
description: Sign a CHIT trail payload, append a CLAIM-or-RELEASE entry to AGNOTE4482PHI.t1.md, and stage a NATS publish to chit.signed.v1 (via pmoves-nats-mcp when wired). Use when committing CHIT-aware service changes.
disable-model-invocation: false
user-invocable: false
---

# pmoves-chit-sign

Composable procedural skill that ties three existing surfaces together:

1. `/chit:sign-trail` slash command (CHIT signature emission)
2. `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` Active Claim Register (CLAIM / RELEASE bookkeeping)
3. `chit.signed.v1` NATS subject (downstream observers — Consciousness :8105, Tokenism :8103, Evo Controller :8113)

The NATS leg is **staged but not auto-published** until the `pmoves-nats-mcp` server is wired into `.claude/mcp.json`. Until then, this skill emits a structured message body the operator (or a future hook) can publish.

## When to invoke

- Committing a change to a CHIT-aware service (see `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`: Tokenism Simulator, Hi-RAG v2, Gateway, Consciousness, Evo Controller, A2UI NATS Bridge, AgentGym RL Coordinator)
- Closing out a claim that involved CHIT payload handling
- Anytime a PR description references `chit.signed.v1`

## Procedural steps (Claude follows this in order)

1. **Gather the payload.** Identify the artifact being signed: PR number, commit SHA, branch, file paths touched, summary one-liner. Confirm no plaintext secrets are inside the payload — only references (paths, IDs).
2. **Call `/chit:sign-trail`.** Pass the payload object as the slash command's input. Capture the returned signature, trail-id, and timestamp.
3. **Capture the signature.** Record `signature`, `trail_id`, and `signed_at` in your working notes so the next steps can reference them verbatim.
4. **Append to AGNOTE4482PHI.t1.md.** Open `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`, locate the Active Claim Register, and append a row of the form:
   ```
   | <agent> | <branch> | <CLAIM|RELEASE> | <timestamp> | trail=<trail_id> sig=<sig-prefix> |
   ```
   If RELEASING, also mark the matching CLAIM row as resolved.
5. **Prepare the NATS message body.** Construct a JSON object:
   ```json
   {
     "schema": "chit.signed.v1",
     "trail_id": "<trail_id>",
     "signature": "<signature>",
     "signed_at": "<iso8601>",
     "artifact": {
       "pr": <pr_num_or_null>,
       "commit": "<sha>",
       "branch": "<branch>",
       "paths": ["..."]
     },
     "agent": "<agent_name>",
     "tier": "<service_tier_from_CHIT_INTEGRATION_STATUS>"
   }
   ```
6. **Note NATS-publish gating.** Publishing to `chit.signed.v1` requires the `pmoves-nats-mcp` server to be active in `.claude/mcp.json`. If not present, save the prepared message under your working notes and surface it in the PR description under a `## Pending NATS Publish` heading so the operator (or a future hook) can dispatch it.
7. **Cross-reference CHIT integration tier.** Open `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`, locate the affected service, and confirm its tier (Full / Partial / None). Include this `tier` in the NATS body (step 5). If `None`, raise a warning in the PR — CHIT-aware behavior should not regress to None.
8. **Update LIVING_DOCS_INDEX if needed.** If the signed change touches a living-doc-tracked artifact, run `pmoves-living-docs-refresh` to confirm the relevant doc has been regenerated; otherwise the signature claims freshness that doesn't exist.
9. **Smoke-test the consumer side (optional).** If the affected service is `Consciousness :8105` or `Tokenism :8103`, hit its `/healthz` and tail recent logs to confirm it would have consumed `chit.signed.v1` once published. Reuse `pmoves-mesh-preflight` for this check.
10. **Record completion.** Append a final RELEASE row in AGNOTE4482PHI.t1.md (if you previously held a CLAIM), and link the trail-id in the PR body so reviewers can chain the audit.

## Inputs expected at invocation time

- `agent_name` — your declared persona (Delivery Body / Control Body / Memory Body)
- `branch` — the working branch
- `pr_number` (optional) — when invoked mid-PR
- `paths[]` — files touched in this signing scope

## Outputs

- A signed CHIT trail entry (via `/chit:sign-trail`)
- An updated AGNOTE4482PHI.t1.md row
- A prepared `chit.signed.v1` JSON body (published when NATS MCP is wired; otherwise surfaced in PR body)
- Optional preflight + living-docs refresh side-checks

## Citations

- `.claude/commands/chit/sign-trail.md` (the slash command this skill composes over)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — Active Claim Register
- `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md` — service tier matrix
- `.claude/context/nats-subjects.md` — `chit.signed.v1` schema
- Sibling skills: `pmoves-mesh-preflight`, `pmoves-living-docs-refresh`, `pmoves-nats-subject-audit`
