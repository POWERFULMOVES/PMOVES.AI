# AGENTS.md open-format review

**Submodule:** [PMOVES-agents.md/](https://github.com/POWERFULMOVES/PMOVES-agents.md) (PMOVES fork of [agentsmd/agents.md](https://github.com/agentsmd/agents.md))
**Pin:** d1ac7f063d20e70015ed6732664049ae4ba9d74e
**Upstream site:** https://agents.md/
**Format URL:** https://agents.md/

The fold-in PR3 (PR #2590, 2026-08-17) added this submodule to PMOVES.AI as the canonical home of the agentsmd/agents.md open format. It's a Next.js docs site (not a library) that documents the format and shows real-world examples. This review answers: what does the format say, how does our PMOVES.AI AGENTS.md compare, and what's worth adopting.

## What the open format is

From the upstream README:

> AGENTS.md is a simple, open format for guiding coding agents.
> Think of AGENTS.md as a README for agents: a dedicated, predictable place
> to provide context and instructions to help AI coding agents work on your project.

The format is **deliberately minimal**. The canonical example shows three sections:

```markdown
# Sample AGENTS.md file

## Dev environment tips
- Use `pnpm dlx turbo run where <project_name>` to jump to a package...
- Run `pnpm install --filter <project_name>` to add the package to your workspace...
- Use `pnpm create vite@latest <project_name> -- --template react-ts`...
- Check the name field inside each package's package.json to confirm the right name...

## Testing instructions
- Find the CI plan in the .github/workflows folder.
- Run `pnpm turbo run test --filter <project_name>` to run every check...
- From the package root you can just call `pnpm test`. The commit should pass all tests before you merge.
- To focus on one step, add the Vitest pattern: `pnpm vitest run -t "<test name>"`.
- Fix any test or type errors until the whole suite is green.
- After moving files or changing imports, run `pnpm lint --filter <project_name>`...
- Add or update tests for the code you change, even if nobody asked.

## PR instructions
- Title format: [<project_name>] <Title>
- Always run `pnpm lint` and `pnpm test` before committing.
```

The three canonical section names are **Dev environment tips**, **Testing instructions**, **PR instructions**. The open format does not require any others. The site at https://agents.md/ hosts example repos (openai/codex, apache/airflow, temporalio/sdk-java, PlutoLang/Pluto) that follow this minimal pattern.

## How our PMOVES.AI AGENTS.md compares

Our root `AGENTS.md` is significantly longer. The current section inventory:

| Section | Open format? | Notes |
|---------|--------------|-------|
| Project Structure | (PMOVES extension) | Submodule monorepo topology — unique to PMOVES |
| Operating in This Repo (Non-Obvious Rules) | (PMOVES extension) | Known Roads, env.shared, Compose layering |
| Build & Development Commands | maps to "Dev environment tips" | Our version is much longer (10+ subcommands) |
| Bring-up sequence | (PMOVES extension) | 6-step ordered workflow |
| Coding Style | (PMOVES extension) | Python 3.11+, FastAPI naming, event contracts |
| Testing | maps to "Testing instructions" | Our version includes the pytest framework section |
| Commit & PR Guidelines | maps to "PR instructions" | Conventional Commits, PR descriptions |
| Secrets | (PMOVES extension) | Never commit, env.shared pipeline, secrets-funnel |
| Submodule Workflow | (PMOVES extension) | Submodule-specific guidance, gitlink discipline |
| Deployment | (PMOVES extension) | Sidecar, Compose, multi-target deploys |
| Security | (PMOVES extension) | CHIT, hardening, Trivy, CodeQL |
| AGENTS.md Format Reference | (PMOVES extension) | Points at the PMOVES-agents.md submodule and the agents.md open format spec |

So: 4 sections map to the open format (Build/Development → Dev environment, Testing → Testing, Commit/PR → PR, with Project Structure being adjacent); 8 sections are PMOVES extensions. The PMOVES extensions are load-bearing — they're the operating rules for the monorepo, and the open format's minimal sections don't have a place for them.

## What to adopt

Three adoption items, in priority order:

### 1. Rename "Build & Development Commands" → "Dev environment tips"

This is a no-op content change but a high-signal conformance win. A reader who knows the open format will look for "Dev environment tips" first. We can keep the `## Build & Development Commands` heading as a synonym, but the canonical section name should match.

This is a one-line edit to `AGENTS.md`. Recommendation: do it as a follow-up doc cleanup, not in this PR.

### 2. Add an "AGENTS.md Format Reference" footnote pointing at the submodule

The current "AGENTS.md Format Reference" section is the right idea but it's currently in the middle of the file. Promote it to a top-of-file note that says: "This file follows the [agents.md](https://agents.md/) open format. The canonical spec is at PMOVES-agents.md/ (PMOVES fork of agentsmd/agents.md)."

This is also a small content edit. Recommendation: do it as a follow-up.

### 3. Document the "PMOVES extensions" convention

The 8 PMOVES-specific sections don't have a name in the open format. Adopt the convention of prefixing PMOVES extensions with a marker — e.g. `### PMOVES extension: <name>` or a `<!-- PMOVES-EXT -->` comment. The convention should be documented in `PMOVES-agents.md/` (or a new `pmoves/docs/agents/AGENTS_MD_FORMAT_REVIEW.md`, which is this doc) so future contributors know what to expect.

Recommendation: pick the convention, document it in PMOVES-agents.md (if we ever need to edit that submodule), and apply it incrementally as the file gets edited. This is a longer-term cleanup, not a wire-up PR change.

## What to leave alone

- **The PMOVES-agents.md submodule source** — it's upstream, the spec is upstream, we don't own it. Any fork-specific behavior we want to express goes in PMOVES.AI's own docs, not in the submodule.
- **The Next.js site code** — marketing site, not a library. The PMOVES fork is a fork; the goal is to keep it mergeable with upstream, not to extend it.
- **The three canonical section names** — don't drop any of "Dev environment tips", "Testing instructions", "PR instructions" from any AGENTS.md we author, even if the section is empty. Future agents will look for those names.

## Cross-references

- The PMOVES-agents.md submodule is referenced from our own `AGENTS.md` at the "AGENTS.md Format Reference" section.
- The submodule's `AGENTS.md` (2KB, separate from the upstream repo's AGENTS.md guide) is the file the agents.md project's own agents would read.
- Our root `AGENTS.md` is what Mavis, Hermes, Pinokio, and any other PMOVES-aware agent reads on cold start.

## Reference

- Submodule: `PMOVES-agents.md/` (PMOVES fork of agentsmd/agents.md)
- Submodule pin: `d1ac7f063d20e70015ed6732664049ae4ba9d74e`
- Upstream repo: https://github.com/agentsmd/agents.md
- Upstream site: https://agents.md/
- Format spec: https://agents.md/ (the "How to use" section)
- Fold-in PR: PR #2590 (Mavis, 2026-08-17)
- Mavis docs index: `pmoves/docs/README_DOCS_INDEX.md`
- PMOVES-agents.md index page: `PMOVES-agents.md/pages/index.tsx`
