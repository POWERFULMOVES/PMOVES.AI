# Repository Guidance for PMOVES.AI

## Documentation Expectations
- Maintain clear, up-to-date documentation for any feature or process change.
- When introducing new behavior, update or create relevant docs under `docs/` or within the component-specific directories. Cross-reference existing guides where appropriate.
- Add rationale and context to complex changes so future contributors understand why decisions were made.
- Ensure configuration or provisioning updates are reflected in the associated bundle documentation.

## Commit & PR Standards
- Keep commits focused and descriptive; group related changes together.
- Reference applicable roadmap or next-step items in commit messages when a change fulfills or advances them.
- Provide context-rich PR descriptions outlining the problem, solution, and testing. Include links to relevant documentation and plans.
- Run all required checks and document results in PR summaries.

## Project Plans & Scope Alignment
- Review project plans stored in `pmoves/docs/ROADMAP.md` and `pmoves/docs/NEXT_STEPS.md` before making significant updates.
- For changes outside the `pmoves/` directory, ensure alignment with the roadmap and note any cross-cutting impacts in documentation and PRs.
- If work deviates from the plans, document the rationale and propose updates to the roadmap files.

## Navigating the Repository
- Core application code resides in `pmoves/`.
- General documentation lives in `docs/`.
- Provisioning bundles and deployment assets are located under the `CATACLYSM_STUDIOS_INC/` hierarchy.
- Use `folders.md` as a quick reference for current structure.

## Maintenance Reminders
- Whenever the repository structure changes, update the root `README.md` and `folders.md` directory map to reflect the latest organization.
- Keep documentation pointers synchronized so new contributors can onboard easily.

## Testing & Validation
- Before running checks, review `pmoves/docs/SMOKETESTS.md` for the current 12-step smoke harness flow and optional follow-on targets.
- Use `pmoves/docs/LOCAL_TOOLING_REFERENCE.md` and `pmoves/docs/LOCAL_DEV.md` to confirm environment scripts, Make targets, and Supabase CLI expectations.
- Log smoke or manual verification evidence back into `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` so roadmaps and next-step trackers stay aligned.

## Local CI Expectations
- Run the CI-equivalent checks documented in `docs/LOCAL_CI_CHECKS.md` (pytest targets, `make chit-contract-check`, `make jellyfin-verify` when the publisher is in scope, SQL policy lint, env preflight) before pushing a branch.
- Capture the commands/output in your PR template “Testing” section and tick the review coordination boxes only after these pass locally.
- If a check is skipped (doc-only change, etc.), note the justification in Reviewer Notes so the automation waiver is explicit.
- If Agent Zero starts logging JetStream subscription errors (`nats: JetStream.Error cannot create queue subscription...`), rebuild the container (`docker compose build agent-zero && docker compose up -d agent-zero`) so the pull-consumer controller changes land and JetStream can recreate its consumers cleanly.

## Agent Communication Practices
- Summarize progress after each major action, compacting details to preserve context window space for upcoming tasks.
- Tie summaries to the active roadmap items or checklists so parallel workstreams stay coherent across longer sessions.
