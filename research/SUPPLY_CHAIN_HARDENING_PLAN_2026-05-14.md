# Supply Chain Hardening Orchestration Plan

**Date:** 2026-05-14
**Parent:** AGNOTE4482 Signoff Protocol
**Trigger:** Tanstack npm supply chain attack (169 packages, 50M+ weekly downloads)
**Audit Report:** `research/TANSTACK_SUPPLY_CHAIN_AUDIT_2026-05-14.md`

---

## §9: Supply Chain Hardening (New Signoff Section)

### Checklist

- [x] F-01: `pull_request_target` no longer checks out PR head code in a0-plugins <!-- Lane A: base.sha checkout + author guard. AGENT-ZERO 2026-05-14 -->
- [ ] F-02: `PERSONAL_ACCESS_TOKEN` rotated and replaced with scoped `GITHUB_TOKEN` in crush CLA
- [x] F-03: All `actions/cache@v3` upgraded to `@v4` with hash validation <!-- Lane B: 6 instances patched. AGENT-ZERO 2026-05-14 -->
- [x] F-04: All `secrets: inherit` replaced with explicit secret passing <!-- Lane B: 9 patches across 8 files in 4 repos. AGENT-ZERO 2026-05-14 -->
- [ ] F-05: NPM publish workflows scoped to release-only triggers
- [x] F-06: CLA workflows scoped to `pull-requests: write` only <!-- Lane A: tensorzero + archon CLA. AGENT-ZERO 2026-05-14 -->
- [x] F-07: MCP dependencies pinned to exact versions in `.claude/mcp.json` <!-- Lane C: hostinger@0.2.1, tailscale@2026.4.10-1. AGENT-ZERO 2026-05-14 -->
- [x] F-08: Author association checks added to `claude-code-review.yml` <!-- Lane C: OWNER/MEMBER/COLLABORATOR guard. AGENT-ZERO 2026-05-14 -->

---

## Delegation Map (AGNOTE4482 Village Rule)

| Lane | Agent | Findings | Profile | Status |
|------|-------|----------|---------|--------|
| A | Security Fix Agent A | F-01, F-06 | `developer` | PENDING |
| B | Security Fix Agent B | F-03, F-04 | `developer` | PENDING |
| C | Security Fix Agent C | F-07, F-08 | `developer` | PENDING |
| OP | Operator (DARKXSIDE) | F-02, F-05 | Manual rotation | BLOCKED |

---

## Lane A: Critical Workflow Fixes (F-01, F-06)

### F-01: `validate-plugin-pr.yml` — pull_request_target + PR checkout
- **File:** `PMOVES-a0-plugins/.github/workflows/validate-plugin-pr.yml`
- **Fix:** Checkout `base.sha` instead of PR head. Add `if` guard for author association.
- **After:** Attacker fork code NEVER executes in main repo context.

### F-06: TensorZero + Archon CLA `contents: write`
- **Files:**
  - `PMOVES-tensorzero/.github/workflows/cla.yml`
  - `PMOVES-Archon/.../PMOVES-tensorzero/.github/workflows/cla.yml`
- **Fix:** Reduce permissions to `pull-requests: write` only.

## Lane B: Cache + Secrets Fixes (F-03, F-04)

### F-03: `actions/cache@v3` → `@v4`
- **File:** `PMOVES-BoTZ/archive/pmoves_multi_agent_pro_pack/.github/workflows/integration-tests.yml`
- **Fix:** Replace all 6 instances of `actions/cache@v3` with `actions/cache@v4`.

### F-04: `secrets: inherit` → explicit passing
- **Files:**
  - `PMOVES-tensorzero/.github/workflows/general.yml` (lines 1232, 1247)
  - `PMOVES-supabase/.github/workflows/publish_image.yml` (line 142)
  - `PMOVES-Headscale/.github/workflows/test-integration.yaml` (lines 252, 270)
- **Fix:** Replace `secrets: inherit` with explicit `secrets:` block listing only needed secrets.

## Lane C: MCP Pinning + Author Checks (F-07, F-08)

### F-07: Pin MCP `@latest` deps
- **File:** `.claude/mcp.json` (monorepo root)
- **Fix:** Resolve current versions of `hostinger-api-mcp` and `tailscale-mcp`, pin to exact semver.

### F-08: Author association guard
- **File:** `.github/workflows/claude-code-review.yml`
- **Fix:** Add `if:` condition checking `github.event.pull_request.author_association`.

## Operator Actions (F-02, F-05)

### F-02: PAT Rotation
- **Action:** Rotate `PERSONAL_ACCESS_TOKEN` in GitHub Secrets for PMOVES-crush
- **Then:** Replace with fine-grained PAT scoped to crush repo only, or use `GITHUB_TOKEN`

### F-05: NPM Token Rotation
- **Action:** Rotate `NPM_TOKEN` and `POSTMAN_NPM_TOKEN` in GitHub Secrets
- **Then:** Scope publish workflows to `release: published` trigger only

---

## Execution Order

```
NOW (parallel dispatch):
  Lane A → F-01 + F-06 (CRITICAL + HIGH)
  Lane B → F-03 + F-04 (HIGH + HIGH)
  Lane C → F-07 + F-08 (HIGH + MEDIUM)

OPERATOR (manual, after lanes complete):
  F-02 → Rotate PAT in GitHub Secrets
  F-05 → Rotate NPM tokens + scope publish triggers

VERIFY:
  Re-run security audit to confirm all 8 findings resolved
  Update signoff checklist §9
```

---

*GRAPHITI_MARK: AGENT-ZERO::SUPPLY-CHAIN-HARDENING-PLAN::2026-05-14*
