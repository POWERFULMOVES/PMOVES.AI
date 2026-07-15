## Summary

- **`docs(website): baseline + brand asset family`** — Playwright + axe-core baseline of `website/` + `/stage/`; 5 expected 404s (founder TODOs); 2 real color-contrast violations identified (CSS-fix PR candidate, separate); 4 brand assets generated (og-image, favicon, apple-touch-icon, mobile-node rig)
- **`docs(agnote): CLAIM WEBSITE_AS_AGENT_CANVAS`** — DARKXSIDE assigned Mavis-5090 architectural leadership for the lane
- **`docs(contracts): A2UI v0.1 spec`** — HTML5 Web Components contract, data-binding model C (push + single-pull, no chains), 7 component recipes, 15 persona theming tokens, ARIA rules
- **`feat(a2ui): v0.1 first slice`** — 3 components (`<pm-space-agent-card>`, `<pm-project-card>`, `<pm-metric-tile>`) + `compose_tenant_page()` Python tool + conformance test (19/19 Python tests, 0 axe-core violations)
- **`feat(a2ui): complete v0.1 registry + Fordham Hill tenant`** — 4 more components (`<pm-timeline>`, `<pm-voice-clip>`, `<pm-image>`, `<pm-quote-block>`) + `website/tenant-template/` + Fordham Hill composed tenant page live

**The headline deliverable**: the Fordham Hill Co-op tenant page is a working CF Pages-shaped site composed via `compose_tenant_page()` from a JSON fixture. The "CF Pages is a canvas PMOVES agents paint on" reframe is proven.

## Testing

```
# Python tests (compose tool + fixtures)
python -m pytest pmoves/tools/compose/tests/test_compose.py -v
# 19/19 PASS

# A2UI v0.1 conformance (in-browser harness, axe-core 4.10.2)
# Open pmoves/contracts/a2ui-v0.1-conformance.test.html in browser
# Result: 7/7 components PASS, axe-core 0 violations, 21 rules passed

# Live Fordham Hill tenant page render
# Open website/tenant-template/index.html in browser
# 18 A2UI messages / 16 components across all 7 v0.1 types
```

### Required Checks

- [x] **CHIT Contract Check** — pass (no contract changes; new contracts added under `pmoves/contracts/a2ui-v0.1.md`)
- [x] **Updated contracts, schemas, or topics** — new spec `pmoves/contracts/a2ui-v0.1.md` + new conformance test `pmoves/contracts/a2ui-v0.1-conformance.test.html`
- [x] **Added/updated documentation** — `pmoves/docs/operations/WEBSITE_UI_BASELINE_2026-07-14.md` + AGNOTE trail entries

### Evidence directory

`pmoves/docs/evidence/website-baseline-2026-07-14/` — baseline screenshots, conformance runs, brand assets, tenant page render, demo HTML files for each component.

## Review Coordination

- [ ] **Requested Codex review** — please run `/chit:review-sweep` or equivalent after PR opens
- [ ] **Requested GitHub Copilot review** — use the PR "Copilot" button

## Follow-up Tasks

- [ ] Real Fordham resident review of the Fordham Hill tenant page (legitimacy, copy tone, voice-clip sample)
- [ ] Sign-off on the 4 generated brand assets before promoting to `website/og-image.png` + `website/assets/{favicon.ico,apple-touch-icon.png,mobile-node-rig.jpg}`
- [ ] CSS fix PR for the 2 identified color-contrast violations (1-3 line change, <15 min effort, low-risk)
- [ ] Wire the v0.1 conformance test into CI (currently manual in-browser)

## Reviewer Notes

**Architectural decisions to scrutinize**:
- HTML5 Web Components (Custom Elements + Shadow DOM) as substrate, no framework. Lit fine for renderer (`website/stage/vendor/a2ui.mjs`); the library is plain Web Components so any agent in any language can emit them.
- Data-binding model C (push via props + single `data-source` pull; no chained pull). The "single pull" rule is the strict subset that keeps conformance simple. v0.2 unlocks chained pull additively.
- ARIA attrs on HOST elements (not just shadow root) because axe-core doesn't pierce shadow DOM by default.
- 15 `--pm-*` CSS custom properties for persona theming. Components that hardcode colors fail conformance.

**For the reviewer on a fresh node**: the conformance test (`pmoves/contracts/a2ui-v0.1-conformance.test.html`) is the single source of truth. If a component passes there, ship it. If it fails, fix it before reviewing other concerns.

**For the local-model-on-Spark-Knuckles reviewer**: start with `pmoves/docs/operations/WEBSITE_UI_BASELINE_2026-07-14.md` for the original baseline; then read `pmoves/contracts/a2ui-v0.1.md` for the contract; then run the conformance test in a browser; then look at the 7 components + the Fordham Hill tenant page in `website/tenant-template/`.

**Pre-PR self-check (`PR_NOTES.md`)**:
- [x] Python tests 19/19 pass
- [x] A2UI conformance 7/7 pass
- [x] axe-core WCAG 2 AA: 0 violations
- [x] 5-class classifier applied to my own diff: caught 2 issues before pushing (`role` prop → renamed `agentRole`/`attributionRole` to avoid ARIA attr conflict; ARIA attrs on host not shadow root)
- [x] AGNOTE CLAIM + RELEASE rows written

**Worked-example callout**: a fix-pattern from this PR is the "ARIA attrs on host" rule. It's now codified in `a2ui-v0.1.md §6.2` and tested in conformance. Future PRs that violate it will fail conformance — that's the desired behavior.

**Sister PRs**:
- PR 2 (this stack): `feat/a2ui-v02-design` — pm-haptic + v0.2 ballot spec DRAFT
- PR 3 (this stack): `feat/a2ui-v02-impl-review-style` — pm-toast + pm-ballot + St. Maarten tenant + v0.2 event wire + CF Pages deploy + review-style scaffolding

## See also

- `pmoves/contracts/a2ui-v0.1.md` — the spec
- `pmoves/contracts/a2ui-v0.1-conformance.test.html` — the conformance test (run this in a browser to verify)
- `pmoves/web-components/README.md` — component recipe index
- `pmoves/tools/compose/README.md` — compose tool docs
- `pmoves/docs/operations/WEBSITE_UI_BASELINE_2026-07-14.md` — original baseline
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — claim/release register (CLAIM at `Mavis-5090::WEBSITE-AS-AGENT-CANVAS-CLAIM::2026-07-15`, RELEASE at `Mavis-5090::A2UI-V0.1-FIRST-SLICE-SHIPPED::2026-07-15` + `Mavis-5090::WEBSITE-AS-AGENT-CANVAS-PARALLEL-BUILD::2026-07-15`)
