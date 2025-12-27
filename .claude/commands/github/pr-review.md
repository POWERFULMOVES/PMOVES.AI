# GitHub PR Review

Review a pull request with AI assistance, analyzing changes and providing feedback.

## Usage

```
/github:pr-review <pr_number_or_url>
```

## Arguments

- `pr_number_or_url`: PR number (e.g., `286`) or full URL

## What This Command Does

1. **Fetch PR Details:**
   ```bash
   gh pr view <pr_number> --json title,body,state,author,files,additions,deletions,changedFiles
   ```

2. **Get PR Diff:**
   ```bash
   gh pr diff <pr_number>
   ```

3. **Check CI Status:**
   ```bash
   gh pr checks <pr_number>
   ```

4. **Review Comments:**
   ```bash
   gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews --jq '.[].body'
   ```

## Review Analysis

Analyze the PR for:

### Code Quality
- Coding standards adherence
- Error handling patterns
- Security considerations (OWASP top 10)
- Performance implications

### Architecture
- Integration with existing PMOVES services
- NATS event patterns
- Service boundaries

### Testing
- Test coverage
- Smoke test compatibility
- Integration test needs

### Documentation
- README updates needed
- API documentation
- Context file updates for `.claude/context/`

## Output Format

Provide a structured review:

```markdown
## PR Review: #<number> - <title>

### Summary
<1-2 sentence overview>

### Changes Analysis
- **Files Changed:** X
- **Lines Added:** +Y
- **Lines Removed:** -Z

### Strengths
- <bullet points>

### Concerns
- <bullet points with severity: P0/P1/P2>

### Suggestions
- <actionable recommendations>

### CI Status
- <pass/fail with details>

### Recommendation
- [ ] Approve
- [ ] Request Changes
- [ ] Comment Only
```

## Example

```bash
# Review PR by number
/github:pr-review 286

# Review PR by URL
/github:pr-review https://github.com/POWERFULMOVES/PMOVES.AI/pull/286
```

## Notes

- Requires `gh` CLI authenticated with repo access
- For large PRs, focus on high-impact files first
- Cross-reference with PMOVES architecture in `.claude/CLAUDE.md`
