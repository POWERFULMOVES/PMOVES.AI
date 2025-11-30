# Repository Collaboration Rules

This repository now includes automation helpers to support collaboration as more contributors join. Follow the steps below to finish the configuration inside GitHub and keep contributions consistent.

## 1. Enforce Branch Protections / Rulesets
1. Navigate to **Settings → Rules → Rulesets** (or **Branches → Branch protection rules** for legacy UI).
2. Target the default branch (usually `main`).
3. Require pull requests before merging and block direct pushes.
4. Require at least one approving review and dismiss stale approvals on new commits.
5. Add the `CHIT Contract Check` workflow as a required status check so it must succeed before merges. (The workflow now triggers automatically when Supabase SQL, init scripts, or geometry service code change. For docs-only PRs, dispatch it manually from the Actions tab if you still need a green check.)
6. (Optional) Restrict who can push to the protected branch to trusted maintainers only.

## 2. Automatic Reviewer Assignment
- The `.github/CODEOWNERS` file assigns maintainers to key areas. Update the GitHub handles to match your actual teams or individuals.
- When someone opens a pull request that touches those paths, GitHub will automatically request reviews from the listed owners.

## 3. Pull Request Template
- The `.github/pull_request_template.md` file prompts authors for a change summary, testing notes, required contract considerations, and follow-up tasks.
- GitHub automatically populates new PR descriptions with this template. Encourage contributors to keep the checklist intact so reviews have the necessary context.

## 4. Onboarding Notes
- Link to this document from your onboarding materials or repository README so new collaborators understand the guardrails.
- Periodically audit CODEOWNERS to ensure coverage stays accurate as the codebase evolves.
- Consider extending branch protection rules with additional checks (linting, tests) as automation coverage grows.

Completing these steps ensures the repository consistently captures testing evidence, routes reviews to the right people, and blocks merges when the CHIT contract validation fails.
