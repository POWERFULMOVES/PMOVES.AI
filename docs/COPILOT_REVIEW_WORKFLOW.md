# Codex + Copilot Review Workflow

This guide explains how to pair the local Codex agent with GitHub Copilot PR reviews so every change lands with consistent automation evidence and actionable feedback.

## Prerequisites

- GitHub Copilot for Individuals (Pro) enabled on the account that opens pull requests.
- GitHub CLI (`gh`) ≥ 2.57 installed locally. Install the Copilot extension with `gh extension install github/gh-copilot` if you want to trigger Copilot reviews from the terminal.
- Personal access token (classic or fine-grained) with `repo` and `pull_requests` scopes. Add the `copilot` scope if prompted. Export it as `GITHUB_TOKEN` before running commands that call the GitHub API.
- Local smoke harness familiarity; refresh `pmoves/docs/SMOKETESTS.md` before sending review requests.

## Standard Flow (each PR)

1. **Prep & Evidence**
   - Run `make smoke` (or the targeted smoke variant) and capture logs/screenshots.
   - Log the run in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` so roadmap checklists stay current.
   - Update documentation touched by the change (including this repository’s AGENTS/CHECKLIST docs).

2. **PR Authoring**
   - Fill out `.github/pull_request_template.md` with a concise summary, the commands run, and attach evidence links.
   - Check both boxes in **Review Coordination** once the requests below are issued.

3. **Codex Review (local)**
   - In the Codex CLI, run the review command or prompt sequence you already use (capture transcript if practical).
   - Copy blockers, risks, and suggested tests into the PR “Reviewer Notes” section.

4. **Copilot Review (GitHub)**
   - **GitHub UI**: Open the PR → click the **Copilot** panel → choose **Review**. Ask Copilot to summarize risks, test coverage, and doc alignment. Paste any critical follow-ups into “Reviewer Notes”.
   - **GitHub CLI (optional)**: Authenticate with `gh auth login --hostname github.com --scopes "repo,pull_request,copilot"` (or rely on `GITHUB_TOKEN`). Install the preview Copilot commands and confirm syntax with `gh copilot --help`, then run the review invocation (currently):
     ```bash
     gh copilot review --pr <PR_NUMBER> --suggest
     ```
     The command posts a Copilot review comment with summaries and highlight suggestions.

5. **Synthesis**
   - Resolve Codex blockers first; reply in the PR so there is an audit trail.
   - Action Copilot suggestions or capture rationale for deferring them. Link back to updated docs or roadmap items when closing threads.

## Token Handling Tips

- Store long-lived tokens in your manager (1Password, Bitwarden) and load them via `export GITHUB_TOKEN=...` only for the active shell session.
- For fine-grained PATs, grant access to the `PMOVES.AI` repository with **Contents: Read & Write** and **Pull requests: Read & Write**. Add the **Copilot** resource if available.
- The Copilot CLI extension reuses whichever credential `gh` is configured with; no extra login is required once `gh auth status` reports a valid token.

## Quick Checklist Before Merge

- [ ] Codex review transcript summarized in PR notes.
- [ ] Copilot review posted; actionable items tracked or resolved.
- [ ] Smoke evidence linked and stored in the session plan run log.
- [ ] Documentation pointers updated (AGENTS, roadmap, runbooks).
- [ ] Review coordination boxes in the PR template checked.
