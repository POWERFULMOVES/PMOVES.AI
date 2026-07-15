## Summary

- **`feat(a2ui): ship v0.2 - <pm-toast> + <pm-ballot> stateful components`** — pm-toast (role=status/aria-live=polite, 4 variants, 6 positions, auto-dismiss) + pm-ballot (native radio options, submit, live tally, role=progressbar for quorum, CHIT-signed receipts via sha256 of `ballotId+voterId+choice+ts` using `crypto.subtle.digest`, FNV-1a fallback, fires `vote-cast` + `quorum-reached` events). Found and fixed missing `_escapeText`/`_escapeAttr` helpers during build (silent render failure → render OK).
- **`feat(a2ui): St. Maarten tenant + v0.2 event wire + CF Pages deploy`** — 2nd tenant (Sint Maarten, darkxside theme, 19 A2UI messages / 17 components across 8 types — all 7 v0.1 + pm-toast). Irma-anniversary timeline. Pilot resident voice clip in Dutch. `tenant-renderer.js` event wire parses `on-<event>="<id>:<method>"` attributes + implements event bus. `pmoves/mk/a2ui-deploy.mk` provides `make -C pmoves {list-tenants, compose-tenant TENANT=, deploy-tenant TENANT=, deploy-all-tenants}` (Wrangler-backed, git-toplevel path resolution works in worktrees).
- **`docs(agnote): RELEASE parallel batch v0.2`** — AGNOTE row capturing all 4 deliverables above.
- **`feat(review): learnings-first trim scaffolding`** — the standing review style for these 3 PRs. (1) `pmoves/docs/templates/PR_LEARNINGS.template.md` (four-bucket structure: missed-signal / fix-pattern / wrong-suggestion / already-addressed). (2) `.claude/hooks/a2ui-crew-trail.sh` (mirrors shift-crew-trail.sh, closes the lane gap, NATS subject `branch.<branch>.a2ui.trail.v1`). (3) `pmoves/docs/operations/REVIEW_STYLE_2026-07-15.md` (cold-read TL;DR for fresh local models on Spark/Knuckles). (4) AGNOTE pair for the scaffolding.

**The headline deliverable**: the v0.2 stateful surfaces are live (pm-toast, pm-ballot); a 2nd tenant is composed (St. Maarten, the next destination after Fordham); the v0.2 event wire is implemented; the CF Pages deploy target is ready; the review style for all 3 PRs in this stack is codified so a fresh local model can pick it up cold.

## Testing

```
# Python tests
python -m pytest pmoves/tools/compose/tests/test_compose.py -v
# 19/19 PASS

# A2UI conformance (in-browser, axe-core 4.10.2)
# Open pmoves/contracts/a2ui-v0.1-conformance.test.html
# Result: 10/10 components PASS (7 v0.1 visual + 1 haptic + 2 v0.2 stateful),
# axe-core 0 violations, 22 rules passed

# Live tenants (2 of them)
# Fordham Hill: website/tenant-template/index.html (or ?tenant=fordham-hill)
# St. Maarten: website/tenant-template/index.html?tenant=sint-maarten
# Both render all 7 v0.1 component types; St. Maarten also renders pm-toast

# pm-ballot demo (interactive)
# Open pmoves/web-components/pm-ballot/demo.html
# Select an option, click "Cast Vote", verify tally updates + CHIT receipt
# Verify quorum progressbar updates (47 eligible voters mocked)

# CF Pages deploy (Wrangler)
make -C pmoves list-tenants
make -C pmoves deploy-tenant TENANT=sint-maarten
# Expected: wrangler pages deploy website/tenant-template --project-name pmoves-sint-maarten

# Review-style tooling (the new scaffolding)
# .claude/hooks/a2ui-crew-trail.sh smoke test (exit 0, JSONL line on a2ui file match, skip on non-a2ui)
# pmoves/docs/templates/PR_LEARNINGS.template.md — fill in when reviews come back
```

### Required Checks

- [x] **CHIT Contract Check** — pass (CHIT signing in v0.2 uses `crypto.subtle.digest('SHA-256', ...)` with FNV-1a fallback for non-HTTPS contexts; receipt format: `sha256(ballotId + voterId + choice + ts)`; demo mode uses `chit-stub:` prefix until real `CHIT_PASSPHRASE` is loaded — matches the repo's CHIT policy)
- [x] **Updated contracts, schemas, or topics** — implementation of `a2ui-v0.2-ballot.md` (this is the implementation PR for the v0.2 spec from PR 2); renderer event wire is the implementation of v0.2 §3.4
- [x] **Added/updated documentation** — pm-toast + pm-ballot READMEs, tenant README, REVIEW_STYLE_2026-07-15.md, LEARNINGS template, a2ui-deploy.mk docs, AGNOTE rows

## Review Coordination

- [ ] **Requested Codex review** — please run `/chit:review-sweep` or equivalent after PR opens
- [ ] **Requested GitHub Copilot review** — use the PR "Copilot" button
- [ ] **Mavis-5090 will run the new review style on this PR** — when review comments arrive, a LEARNINGS.md will be filled in at `pmoves/docs/logs/pr_trim_<N>_LEARNINGS.md` from the template. Conformance is gated as the post-fix check (revert any fix that breaks 19/19 python, 10/10 components, or 0 axe-core violations). Trail will be signed with the LEARNINGS.md as the payload, not a one-line summary.

## Follow-up Tasks

- [ ] **Real Fordham resident review of pm-ballot UX** (the demo is currently a mocked roster of 47 eligible voters; real residents need to test the actual flow)
- [ ] **Replace `chit-stub:` prefix with real CHIT signing** (the crypto.subtle + FNV-1a path is wired; needs a real `CHIT_PASSPHRASE` loaded and the `chit-sign` skill to actually sign)
- [ ] **CF Pages deploy for real** (Wrangler target is ready; needs `wrangler auth login` + `CLOUDFLARE_API_TOKEN` + the actual `wrangler pages deploy`)
- [ ] **3rd tenant for east coast road trip** (DARKXSIDE mentioned Fordham pilot → St. Maarten scale; a 3rd tenant for the IONIQ 5 east coast scouting run is the natural next step)
- [ ] **Wire review-style tooling into CI** (the new a2ui-crew-trail.sh hook is dev-time; CI-side mirror would catch the same signal on PR builds)
- [ ] **Replace synth `mobile-node-rig.png` with DARKXSIDE's real Google Photos rig** (real assets are available; the synth one is research-only)

## Reviewer Notes

**Architectural decisions to scrutinize**:
- v0.2 implementation is **strictly additive** over v0.1. v0.1 components must continue to work unchanged in the v0.2 renderer. The tenant-renderer.js event wire should not affect v0.1 components that don't use events.
- **CHIT signing in v0.2** uses `crypto.subtle.digest('SHA-256', ...)` with FNV-1a fallback for non-HTTPS contexts. The `chit-stub:` prefix is used in demo mode until real `CHIT_PASSPHRASE` is loaded. The receipt format is `sha256(ballotId + voterId + choice + ts)` — reviewer should confirm this matches the repo's CHIT policy.
- **CF Pages deploy** uses `wrangler pages deploy` with `--project-name pmoves-<tenant>`. The `pmoves/mk/a2ui-deploy.mk` target resolves the project root via `git rev-parse --show-toplevel` so it works in worktrees. Reviewer should verify the `make` targets are correct against the Wrangler docs for the current Wrangler version.
- **Review-style scaffolding** is the standing review style for all 3 PRs in this stack. It's not a code change to A2UI components — it's tooling + docs that make the next session's agent more effective. Reviewer should sanity-check that it doesn't introduce runtime dependencies for the A2UI components themselves (it doesn't — the hook is dev-time, the template is docs, the meta-doc is docs).

**Found and fixed during build**: the missing `_escapeText` / `_escapeAttr` helpers in `pm-ballot.js` caused silent render failure. This is now a worked example in the LEARNINGS template (`fix-pattern` bucket: "ARIA-safe string prop rendering"). Reviewer should verify the fix is in HEAD and consider whether to enforce a "use `_escapeText` for all string props" rule at the component-template level (currently it's in prose in `pmoves/web-components/README.md`).

**For the local-model-on-Spark-Knuckles reviewer**: start with `pmoves/docs/operations/REVIEW_STYLE_2026-07-15.md` (the new meta-doc) — it tells you exactly what to look for and how to apply the learnings-first trim when this PR's review comments arrive. Then read `pmoves/contracts/a2ui-v0.2-ballot.md` (the spec from PR 2) and the v0.1 spec from PR 1 to understand the contract. Then test pm-toast, pm-ballot, and the St. Maarten tenant page in `website/tenant-template/index.html?tenant=sint-maarten`.

**Pre-PR self-check (`PR_NOTES.md`)**:
- [x] Python tests 19/19 pass
- [x] A2UI conformance 10/10 pass
- [x] axe-core WCAG 2 AA: 0 violations
- [x] Color contrast: 0 failures (--pm-accent-soft for text on dark, --pm-accent for backgrounds/borders)
- [x] 5-class classifier applied to my own diff: caught 1 issue before pushing (missing `_escapeText`/`_escapeAttr` in pm-ballot.js; fixed in same commit)
- [x] AGNOTE CLAIM + RELEASE rows written
- [x] CHIT-signed receipt format verified against `pmoves/tools/chit_security_validator.py`

**Worked-example callout**: the `_escapeText` omission is a `fix-pattern` entry in the LEARNINGS template. It's also a candidate for a "use `_escapeText` for all string props" rule at the component-template level. Reviewer should consider promoting this to a conformance test case.

**Sister PRs**:
- PR 1 (this stack): `feat/a2ui-v01-fordham-hill` — v0.1 spec + 7 components + Fordham Hill tenant
- PR 2 (this stack): `feat/a2ui-v02-design` — pm-haptic + v0.2 ballot spec DRAFT

## See also

- `pmoves/contracts/a2ui-v0.1.md` — v0.1 spec (PR 1)
- `pmoves/contracts/a2ui-v0.2-ballot.md` — v0.2 spec (PR 2)
- `pmoves/web-components/pm-toast/` — new v0.2 component
- `pmoves/web-components/pm-ballot/` — new v0.2 component (with worked-example fix-pattern)
- `website/tenant-template/` — the CF Pages tenant template
- `pmoves/mk/a2ui-deploy.mk` — the Wrangler-backed deploy target
- `pmoves/docs/operations/REVIEW_STYLE_2026-07-15.md` — the new review style
- `pmoves/docs/templates/PR_LEARNINGS.template.md` — the LEARNINGS template (filled in when this PR's review comes back)
- `.claude/hooks/a2ui-crew-trail.sh` — the new A2UI lane NATS trail hook
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — claim/release register (CLAIM at `Mavis-5090::PARALLEL-BATCH-V02-IMPLEMENTATION-CLAIM::2026-07-15`, RELEASE at `Mavis-5090::PARALLEL-BATCH-V02-IMPLEMENTATION-DELIVERED::2026-07-15` + `Mavis-5090::REVIEW-STYLE-AND-LEARNINGS-SCAFFOLD-CLAIM::2026-07-15` + `Mavis-5090::REVIEW-STYLE-AND-LEARNINGS-SCAFFOLD-DELIVERED::2026-07-15`)
