# GitHub Copilot Review Guidance for PMOVES.AI

These repository-level instructions tell GitHub Copilot how to assist on pull requests alongside the local Codex workflow.

## Review Focus
- Start with a concise bullet summary of the change and reference any roadmap or checklist items mentioned by the author.
- Verify that smoke evidence is present when code paths touch the automation loop. Expect 13/13 smoke harness completion as documented in `pmoves/docs/SMOKETESTS.md`.
- Call out mismatches between code changes and the runbooks (`pmoves/docs/NEXT_STEPS.md`, `pmoves/docs/ROADMAP.md`, `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`) and suggest updates if missing.
- Flag missing documentation updates whenever behavior, configuration, or provisioning steps change.

## Collaboration Etiquette
- Keep feedback organized by file with actionable suggestions or questions; avoid restating nit-level style issues already covered by formatters or lint.
- When unsure, recommend the author re-run the relevant smoke target or attach logs instead of speculating.
- Prefer compact responses so the human reviewer and Codex agent can keep context in long-running threads.

## When Author Asks for a Summary
- Provide a short (3–5 bullet) recap highlighting risky areas, test coverage, and any follow-up work.
- Point the author back to the PR template checkboxes if key validations are missing.
