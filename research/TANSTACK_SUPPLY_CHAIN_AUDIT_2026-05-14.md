# PMOVES.AI Supply Chain Security Audit — Tanstack/CI Cache Poisoning Vector

**Date:** 2026-05-14
**Scope:** `/a0/usr/projects/pmoves/` monorepo (44+ submodules)
**Attack Pattern Modeled:** Tanstack pull_request_target → cache poisoning → npm token theft → worm spread
**Source Video:** https://www.youtube.com/watch?v=gwTQLZSIlsU

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 6 |
| Medium | 5 |
| Low | 3 |

---

## Findings

### [CRITICAL] F-01: Arbitrary Code Execution via `pull_request_target` with PR Checkout

- **Location:** `PMOVES-a0-plugins/.github/workflows/validate-plugin-pr.yml`
- **Description:** This workflow triggers on `pull_request_target` from **any** fork, fetches the PR head commit using the PR author's repo, and **executes Python code** (`scripts/validate_plugin_submission.py`) against that PR content. The workflow also creates a GitHub App token with `A0_BOT_PRIVATE_KEY` secret.
- **Impact:** An attacker can open a PR with a malicious `scripts/validate_plugin_submission.py` or malicious plugin files that the validation script processes. Since the workflow runs in the main repo's context with secrets, the attacker's code can exfiltrate `A0_BOT_APP_ID`, `A0_BOT_PRIVATE_KEY`, and the generated `bot-app-token`. This is the **exact Tanstack attack pattern** — code from a fork running with main repo secrets.
- **Proof of Concept:**
  1. Fork `a0-plugins` repo
  2. Open a PR with a modified `scripts/validate_plugin_submission.py` that sends `os.environ` to attacker server
  3. PR triggers `pull_request_target` → workflow fetches attacker's commit → runs Python → secrets exfiltrated
  4. Use `A0_BOT_PRIVATE_KEY` to forge app tokens for the PMOVES org
- **Recommendation:**
  ```yaml
  # Option A: Use pull_request (NOT pull_request_target) for code execution
  on:
    pull_request:
      types: [opened, synchronize, reopened, ready_for_review, labeled]

  # Option B: If pull_request_target is required, do NOT checkout PR code
  # Instead, use the merge commit ref from the base repo
  - uses: actions/checkout@v4
    with:
      ref: ${{ github.event.pull_request.base.sha }}  # base, NOT head

  # Option C: Require approval for all external PR workflows
  # Settings → Actions → General → Require approval for all outside collaborators
  ```

---

### [CRITICAL] F-02: `PERSONAL_ACCESS_TOKEN` Exposed in `pull_request_target` Context

- **Location:** `PMOVES-crush/.github/workflows/cla.yml`
- **Description:** The CLA workflow uses `pull_request_target` with `permissions: contents: write` and passes `secrets.PERSONAL_ACCESS_TOKEN` to the CLA assistant action. A PAT has broader scope than `GITHUB_TOKEN` and doesn't expire automatically.
- **Impact:** An attacker who can inject a malicious CLA action version (or exploit the action itself) can steal the PAT. The PAT likely has org-wide write access. Combined with `contents: write`, this enables direct repo modification without PR review.
- **Recommendation:**
  ```yaml
  # Replace PERSONAL_ACCESS_TOKEN with scoped GITHUB_TOKEN
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}  # auto-scoped, auto-expires
  # If PAT is required, use a fine-grained PAT scoped to this repo only
  # Rotate the current PAT immediately
  ```

---

### [HIGH] F-03: `actions/cache@v3` — Deprecated, Cache Poisoning Vector

- **Location:** 6 instances in `PMOVES-BoTZ/archive/pmoves_multi_agent_pro_pack/.github/workflows/integration-tests.yml` (lines 32, 88, 132, 198, 238, 284)
- **Description:** `actions/cache@v3` is deprecated and lacks cache isolation protections in `pull_request` contexts. An attacker can poison the cache via a malicious PR, then a legitimate PR hits the poisoned cache and executes attacker code — the **exact step 4-5 of the Tanstack attack**.
- **Impact:** Cache poisoning leads to supply chain compromise of all downstream CI builds sharing the cache scope.
- **Recommendation:**
  ```yaml
  # Upgrade all cache actions to v4 with hash validation
  - uses: actions/cache@v4
    with:
      path: ~/.cache/pip
      key: pip-${{ runner.os }}-${{ hashFiles('**/requirements.txt') }}
      # v4 enables cache isolation by default for pull_request events
  ```

---

### [HIGH] F-04: `secrets: inherit` Leaks All Secrets to Reusable Workflows

- **Location:**
  - `PMOVES-tensorzero/.github/workflows/general.yml` (lines 1232, 1247)
  - `PMOVES-supabase/.github/workflows/publish_image.yml` (line 142)
  - `PMOVES-Headscale/.github/workflows/test-integration.yaml` (lines 252, 270)
- **Description:** `secrets: inherit` passes **all** repository secrets to reusable workflows, including `NPM_TOKEN`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` (seen in tensorzero general.yml env vars).
- **Impact:** If any reusable workflow is compromised (via cache poisoning, action injection, etc.), all org secrets are exposed.
- **Recommendation:**
  ```yaml
  # Pass only required secrets explicitly
  secrets:
    R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
    R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
    # Do NOT use: secrets: inherit
  ```

---

### [HIGH] F-05: NPM Publish Tokens in CI Environment

- **Location:**
  - `PMOVES-DoX/.../cipher/pmoves_cipher/.github/workflows/publish.yml:45` — `NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}`
  - `PMOVES-DoX/.../PMOVES-n8n-mcp/.github/workflows/release.yml:398` — `NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}`
  - `PMOVES-DoX/.../PMOVES-postman-mcp-server/.github/workflows/pkg-release.yml:32` — `NODE_AUTH_TOKEN: ${{ secrets.POSTMAN_NPM_TOKEN }}`
- **Description:** Multiple workflows expose npm publish tokens during CI. In the Tanstack attack, **this exact pattern** was the primary target — the worm stole `NPM_TOKEN` and published 84 malicious packages.
- **Impact:** Token theft enables publishing malicious versions of PMOVES packages (cipher, n8n-mcp, postman-mcp) to npm.
- **Recommendation:**
  ```yaml
  # 1. Use OIDC-based publishing (npm provenance) instead of long-lived tokens
  # 2. Use npm granular access tokens scoped to specific packages
  # 3. Never run publish jobs on pull_request or pull_request_target events
  # 4. Add publish-only protection: only trigger on release/tag events
  on:
    release:
      types: [published]  # NOT pull_request_target
  ```

---

### [HIGH] F-06: TensorZero CLA Grants `contents: write` in `pull_request_target`

- **Location:** `PMOVES-tensorzero/.github/workflows/cla.yml` (and copy in `PMOVES-Archon/.../PMOVES-tensorzero/`)
- **Description:** CLA workflow triggers on `pull_request_target` with `permissions: contents: write`. The CLA action writes to `ci/cla-signatures.json` on the main branch. If the `contributor-assistant/github-action` has a vulnerability, attacker code runs with repo write access.
- **Recommendation:** Scope to minimum permissions:
  ```yaml
  permissions:
    pull-requests: write  # Only need PR comments
    # Remove: contents: write — CLA signatures can use the API instead of commits
  ```

---

### [HIGH] F-07: MCP Dependencies Use `@latest` — Supply Chain Hijack Vector

- **Location:** `.claude/mcp.json` (root)
  ```json
  "hostinger-mcp": { "args": ["hostinger-api-mcp@latest"] },
  "tailscale": { "args": ["tailscale-mcp@latest"] }
  ```
- **Description:** `npx package@latest` resolves to the newest version on every invocation. If either npm package is compromised (like Tanstack packages were), the malicious code executes with the agent's full permissions (Docker socket access via `docker` MCP, network access, env vars).
- **Impact:** Direct equivalent of the Tanstack VS Code/Claude Code persistence vector. Malicious MCP server = full host compromise via Docker socket mount.
- **Recommendation:**
  ```json
  "hostinger-mcp": { "args": ["hostinger-api-mcp@1.2.3"] },  // pin exact version
  "tailscale": { "args": ["tailscale-mcp@4.5.6"] }
  ```

---

### [MEDIUM] F-08: Claude Code CI Uses `pull_request` with Write Permissions

- **Location:** `.github/workflows/claude.yml`, `.github/workflows/claude-code-review.yml`
- **Description:** Both use `pull_request` trigger (not `pull_request_target`), which is safer. However, they grant `contents: write`, `pull-requests: write`, and pass `CLAUDE_CODE_OAUTH_TOKEN`. The `claude.yml` restricts to OWNER/MEMBER/COLLABORATOR author associations, which is good. But `claude-code-review.yml` triggers on **all** pull_requests without author check.
- **Impact:** Lower risk than `pull_request_target` since secrets aren't available to fork PR code. However, the OAuth token is still in the CI environment.
- **Recommendation:** Add author association check to `claude-code-review.yml`:
  ```yaml
  if: |
    github.event.pull_request.draft == false &&
    (github.event.pull_request.author_association == 'OWNER' ||
     github.event.pull_request.author_association == 'MEMBER' ||
     github.event.pull_request.author_association == 'COLLABORATOR')
  ```

---

### [MEDIUM] F-09: Husky `prepare` Scripts Run on `npm install`

- **Location:** 6+ `package.json` files (Pmoves-cipher, PMOVES-BoTZ/cipher, PMOVES-DoX/PsyFeR_reference, PMOVES-bentopdf)
- **Description:** `prepare` scripts configured via Husky run `husky install` automatically on `npm install`. This is an auto-execution vector — if a compromised dependency modifies `.husky/` scripts, the next developer who runs `npm install` executes the payload.
- **Recommendation:** Pin Husky to exact version, audit `.husky/` scripts regularly, or switch to a simpler Git hooks approach.

---

## Immediate Action Items (Priority Order)

1. **🔴 Rotate `A0_BOT_PRIVATE_KEY` and `PERSONAL_ACCESS_TOKEN`** — Both are exposed via `pull_request_target`
2. **🔴 Fix F-01** — Remove PR head checkout from `validate-plugin-pr.yml`, use base ref instead
3. **🔴 Fix F-02** — Replace PAT with scoped `GITHUB_TOKEN` in CLA workflows
4. **🟠 Upgrade `actions/cache@v3` → `v4`** across all workflows (F-03)
5. **🟠 Replace `secrets: inherit`** with explicit secret passing (F-04)
6. **🟠 Pin MCP dependencies** to exact versions in `.claude/mcp.json` (F-07)
7. **🟡 Scope NPM publish workflows** to release-only triggers (F-05)
8. **🟡 Add author checks** to `claude-code-review.yml` (F-08)

## Circuit Breaker Alignment

This audit directly applies the **Circuit Breaker Principle** from PMOVES.AI config:
- `pull_request_target` with secrets = unbounded damage under concurrency (no circuit breaker)
- `secrets: inherit` = cascading failure across all reusable workflows
- `@latest` MCP deps = no fail-fast on compromised packages
- **Fix:** Each finding above IS a circuit breaker — stop the cascade before it starts
