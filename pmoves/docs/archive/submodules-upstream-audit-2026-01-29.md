# PMOVES.AI Submodules - Upstream Sync & CI/CD Audit

**Last Updated:** 2026-01-29
**Branch:** PMOVES.AI-Edition-Hardened

## Audit Parameters

For each forked submodule, we track:
1. **Upstream Sync Status** - Commits behind/ahead of upstream
2. **CI/CD Status** - GitHub Actions passing/failing
3. **Docker Build Status** - Dockerfile build health
4. **Security Hardening** - USER directives, CVEs
5. **Upstream PR Candidates** - Changes suitable for contributing back

---

## PMOVES-A2UI (fork of google/A2UI)

| Parameter | Status | Notes |
|-----------|--------|-------|
| **Upstream** | https://github.com/google/A2UI.git | |
| **Upstream Sync** | 19 behind, 3 ahead | Needs sync |
| **CI/CD** | ✅ Passing | Latest run: 21458321989 (success) |
| **Docker Build** | ✅ Healthy | docker-compose.pmoves.yml present |
| **Security** | ✅ Hardened | USER directives added (ff88ffa) |
| **Workflows** | 7 workflows | All passing |

### PMOVES-Specific Changes (ahead of upstream):
1. `ff88ffa` - security: Add USER directives to A2UI demo Dockerfiles
2. `2e0fe72` - Merge PR #1: PMOVES.AI integration v2
3. `ee8f52c` - feat(pmoves-ai): Add PMOVES.AI integration patterns

### Upstream Changes We're Missing (19 commits):
- `95a1333` - Fix schema URLs, publish schema on a2ui.org (#572)
- `9c31af2` - Revert #515 and modify stringFormat (#573)
- `20d6471` - fix(lit): use .checked instead of .value (#459)
- ... (16 more)

### Action Items:
- [ ] **HIGH PRIORITY**: Sync with 19 upstream commits (security fixes, bug fixes)
- [ ] Create PR to google/A2UI for USER directive security pattern
- [ ] Review PMOVES.AI integration changes for upstream suitability

---

## PMOVES-n8n (fork of n8n-io/n8n)

| Parameter | Status | Notes |
|-----------|--------|-------|
| **Upstream** | https://github.com/n8n-io/n8n | |
| **Upstream Sync** | TBD | Needs audit |
| **CI/CD** | TBD | Needs audit |
| **Docker Build** | TBD | Needs audit |
| **Security** | TBD | Needs audit |

### Action Items:
- [ ] Add upstream remote and check sync status
- [ ] Audit CI/CD workflows
- [ ] Review Docker build configuration

---

## Pmoves-Health-wger (fork of wger-project/wger)

| Parameter | Status | Notes |
|-----------|--------|-------|
| **Upstream** | https://github.com/wger-project/wger | |
| **Upstream Sync** | TBD | Needs audit |
| **CI/CD** | TBD | Needs audit |
| **Docker Build** | TBD | Needs audit |
| **Security** | TBD | Needs audit |

### Action Items:
- [ ] Add upstream remote and check sync status
- [ ] Audit CI/CD workflows
- [ ] Review Docker build configuration

---

## PMOVES-Wealth (fork of firefly-iii/firefly-iii)

| Parameter | Status | Notes |
|-----------|--------|-------|
| **Upstream** | https://github.com/firefly-iii/firefly-iii | |
| **Upstream Sync** | TBD | Needs audit |
| **CI/CD** | TBD | Needs audit |
| **Docker Build** | TBD | Needs audit |
| **Security** | TBD | Needs audit |

### Action Items:
- [ ] Add upstream remote and check sync status
- [ ] Audit CI/CD workflows
- [ ] Review Docker build configuration

---

## PMOVES-Pipecat (fork of pipecat-ai/pipecat)

| Parameter | Status | Notes |
|-----------|--------|-------|
| **Upstream** | https://github.com/pipecat-ai/pipecat | |
| **Upstream Sync** | TBD | Needs audit |
| **CI/CD** | TBD | Needs audit |
| **Docker Build** | TBD | Needs audit |
| **Security** | TBD | Needs audit |

### Action Items:
- [ ] Add upstream remote and check sync status
- [ ] Audit CI/CD workflows
- [ ] Review Docker build configuration

---

## PMOVES-tensorzero (fork of tensorzero/tensorzero)

| Parameter | Status | Notes |
|-----------|--------|-------|
| **Upstream** | https://github.com/tensorzero/tensorzero | |
| **Upstream Sync** | TBD | Needs audit |
| **CI/CD** | TBD | Needs audit |
| **Docker Build** | TBD | Needs audit |
| **Security** | TBD | Needs audit |

### Action Items:
- [ ] Add upstream remote and check sync status
- [ ] Audit CI/CD workflows
- [ ] Review Docker build configuration

---

## PMOVES-AgentGym (fork of WooooDyy/AgentGym)

| Parameter | Status | Notes |
|-----------|--------|-------|
| **Upstream** | https://github.com/WooooDyy/AgentGym | |
| **Upstream Sync** | TBD | Needs audit |
| **CI/CD** | TBD | Needs audit |
| **Docker Build** | TBD | Needs audit |
| **Security** | TBD | Needs audit |

### Action Items:
- [ ] Add upstream remote and check sync status
- [ ] Audit CI/CD workflows
- [ ] Review Docker build configuration

---

## PMOVES-Open-Notebook (fork of lfnovo/open-notebook)

| Parameter | Status | Notes |
|-----------|--------|-------|
| **Upstream** | https://github.com/lfnovo/open-notebook | |
| **Upstream Sync** | TBD | Needs audit |
| **CI/CD** | TBD | Needs audit |
| **Docker Build** | TBD | Needs audit |
| **Security** | TBD | Needs audit |

### Action Items:
- [ ] Add upstream remote and check sync status
- [ ] Audit CI/CD workflows
- [ ] Review Docker build configuration

---

## Audit Workflow

For each submodule:

1. **Add Upstream Remote**
   ```bash
   cd <submodule>
   git remote add upstream https://github.com/<owner>/<repo>.git
   git fetch upstream
   ```

2. **Check Sync Status**
   ```bash
   git log --oneline HEAD..upstream/main | wc -l  # behind
   git log --oneline upstream/main..HEAD | wc -l  # ahead
   ```

3. **Check CI/CD**
   ```bash
   gh run list --limit 5
   ```

4. **Check Docker Build**
   ```bash
   docker build -t test .
   ```

5. **Create Sync Branch** (if behind)
   ```bash
   git checkout -b sync-upstream-$(date +%Y%m%d)
   git merge upstream/main
   # Resolve conflicts if any
   ```

6. **Create Upstream PR** (for changes that benefit upstream)
   ```bash
   git checkout -b upstream-contribution/<feature>
   git push origin upstream-contribution/<feature>
   gh pr create --repo <owner>/<repo> --title "..."
   ```

---

## Notes

- **Upstream sync frequency**: Monthly recommended
- **Security patches**: Immediately when available
- **Breaking changes**: Review before syncing
- **PMOVES-specific branches**: Keep on PMOVES.AI-Edition-Hardened
