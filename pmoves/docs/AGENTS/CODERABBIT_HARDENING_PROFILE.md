# CodeRabbit Hardening Profile (PMOVES)
_Last updated: 2026-02-14_

This guide documents how PMOVES configures CodeRabbit to support production hardening review.

## Source of truth

- Config file: `.coderabbit.yaml`
- Branch focus: hardened branches and active feature/fix prefixes.
- Review focus: workflows, compose/runtime security, secrets handling, CHIT correctness, and docs accuracy.

## Trigger behavior

- Auto review is enabled for non-draft PR updates.
- Manual rerun from PR comments:
  - `@coderabbitai review`

## PMOVES hardening review lanes

1. `.github/workflows/**`
   - Verify CodeQL + Trivy gates stay enforced.
   - Validate GHCR/token logic and StepSecurity constraints.
2. `pmoves/docker-compose*.yml`
   - Flag in-container loopback binds on exposed ports.
   - Flag hardcoded credentials/default insecure values.
3. `pmoves/services/**`
   - Enforce PMOVES secret conventions (`*_FILE`, shared env helpers).
4. `pmoves/chit/**`
   - Check crypto claims against implementation reality.
5. `pmoves/docs/**`
   - Keep status claims aligned with reproducible evidence.

## Practical limit

CodeRabbit may skip large PRs (for example, >150 changed files). When that happens:

1. Split the change into smaller PR slices (recommended).
2. Keep security/runtime changes in a dedicated PR for focused review.
3. Re-trigger review after split (`@coderabbitai review`).

