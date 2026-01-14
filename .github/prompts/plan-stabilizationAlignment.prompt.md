You are drafting a plan. Ensure every task aligns with current stabilization goals and roadmap.

Context anchors:
- Read pmoves/docs/ROADMAP.md and pmoves/docs/NEXT_STEPS.md first.
- Respect the stabilization snapshot and next actions in AGENTS.md and pmoves/AGENTS.md.
- Keep single-environment, branded defaults, and secrets handling as documented in docs/SECRETS.md and docs/SECRETS_ONBOARDING.md.

Plan requirements:
- State the objective and scope clearly.
- Include dependencies on Supabase, Hi-RAG, Invidious, and monitoring when relevant.
- Call out required secrets or env updates and reference the secrets push helper (pmoves/tools/push-gh-secrets.sh).
- For CI/image work, mention GHCR/Docker Hub signing (Cosign) and SBOM/Trivy steps.
- Be explicit about validation: which make targets or smokes will be run.

Output a concise list of steps (3-7), each with owner/role and expected evidence.
