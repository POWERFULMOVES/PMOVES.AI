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
