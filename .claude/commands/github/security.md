# GitHub Security

Monitor and manage Dependabot alerts and security vulnerabilities for PMOVES.AI.

## Usage

```
/github:security [filter]
```

## Arguments

- `filter` (optional): `critical`, `high`, `medium`, `low`, `open`, `fixed`

## What This Command Does

1. **List Dependabot Alerts:**
   ```bash
   gh api repos/{owner}/{repo}/dependabot/alerts --jq '.[] | select(.state == "open") | {number, severity: .security_advisory.severity, package: .security_vulnerability.package.name, path: .dependency.manifest_path}'
   ```

2. **Get Alert Details:**
   ```bash
   gh api repos/{owner}/{repo}/dependabot/alerts/{alert_number}
   ```

3. **Check Code Scanning Alerts:**
   ```bash
   gh api repos/{owner}/{repo}/code-scanning/alerts --jq '.[] | select(.state == "open")'
   ```

4. **View Secret Scanning:**
   ```bash
   gh api repos/{owner}/{repo}/secret-scanning/alerts
   ```

## Severity Levels

| Severity | CVSS Score | Response Time | Action Required |
|----------|------------|---------------|-----------------|
| Critical | 9.0 - 10.0 | Immediate | Stop and fix |
| High | 7.0 - 8.9 | < 24h | Prioritize fix |
| Medium | 4.0 - 6.9 | < 1 week | Schedule fix |
| Low | 0.1 - 3.9 | Backlog | Monitor |

## Output Format

```markdown
## Security Status

### Summary
- **Open Alerts:** X total
- **Critical:** X
- **High:** X
- **Medium:** X
- **Low:** X

### Open Vulnerabilities

| # | Severity | Package | Path | Fix Version |
|---|----------|---------|------|-------------|
| ... | ... | ... | ... | ... |

### Recent Fixes (Last 7 Days)
| Package | Was | Fixed | Date |
|---------|-----|-------|------|
| ... | ... | ... | ... |

### Recommendations
<Prioritized action items>
```

## Example

```bash
# Show all open alerts
/github:security

# Filter critical only
/github:security critical

# Show fixed alerts
/github:security fixed
```

## Common Fix Patterns

### Python (requirements.txt)
```bash
# Update pinned version
sed -i 's/package==1.0.0/package>=1.2.3/' requirements.txt

# Use flexible pinning
package>=1.2.3,<2.0.0
```

### Node.js (package.json)
```bash
# Update dependency
npm update <package>

# Force resolution
npm audit fix --force

# Add resolution override
"resolutions": {
  "<vulnerable-package>": "^fixed-version"
}
```

### Docker Images
```bash
# Use specific digest
FROM image@sha256:abc123...

# Update base image
FROM image:latest → FROM image:specific-version
```

## Automated Fixes

Dependabot PRs are auto-created for:
- Direct dependencies with available patches
- Security updates with backward-compatible fixes

To merge Dependabot PRs:
```bash
# List Dependabot PRs
gh pr list --author "app/dependabot"

# Merge specific PR
gh pr merge <pr_number> --squash
```

## PMOVES Security Checklist

### Critical Services
- [ ] TensorZero - LLM gateway (API keys, model access)
- [ ] Supabase - Database (credentials, RLS policies)
- [ ] NATS - Message bus (authentication)
- [ ] MinIO - Object storage (bucket policies)

### Environment Security
- [ ] `.env` files not committed
- [ ] Secrets in GitHub Secrets, not code
- [ ] CHIT encryption enabled for sensitive data
- [ ] Pre-commit hooks validate no secrets

### Container Security
- [ ] Non-root users in Dockerfiles
- [ ] Minimal base images (distroless where possible)
- [ ] No hardcoded credentials
- [ ] Regular base image updates

## Notes

- Requires `gh` CLI with `security_events` scope
- Critical/High alerts should block deployments
- Review Dependabot PRs within 48h of creation
- Security alerts are private - don't share publicly
