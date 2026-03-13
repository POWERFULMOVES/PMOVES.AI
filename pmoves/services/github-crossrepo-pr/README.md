# GitHub Cross-Repository PR Automation Service

Automates pull request creation and management across multiple PMOVES.AI repositories for dependency updates, security patches, and feature backports.

## Overview

This service provides intelligent PR automation across PMOVES.AI repositories:

- **Workflow Templates**: Reusable templates for common PR patterns
- **Agent Zero MCP Integration**: Secure GitHub operations via Agent Zero
- **NATS Event Coordination**: Event-driven communication with other GitHub automation services
- **Prometheus Metrics**: Comprehensive observability

## Features

### 1. Workflow Templates

Pre-built templates for common PR patterns:

- **Dependency Update PRs**: Bump package versions across all repositories
- **Security Patch PRs**: Automated security vulnerability patches
- **Feature Backport PRs**: Backport features to release branches
- **Release Automation PRs**: Prepare releases with changelogs
- **Dependabot-style Updates**: Dependency updates with release notes
- **Version Bump PRs**: Automated version bumping

### 2. Agent Zero MCP Integration

- GitHub App authentication via Agent Zero MCP
- Create, update, and merge pull requests
- Add comments and reviewers
- Update PR branches with latest changes

### 3. NATS Event Coordination

- **Subscribe to**: `github.crossrepo.sync.completed.v1`
- **Publish to**:
  - `github.crossrepo.pr.created.v1`
  - `github.crossrepo.pr.merged.v1`
  - `github.crossrepo.pr.batch_completed.v1`

### 4. Dry-Run Mode

Safe testing without creating actual PRs (default: enabled).

## Quick Start

### Prerequisites

- PMOVES.AI infrastructure running (NATS, Prometheus, Grafana)
- Agent Zero MCP service accessible
- GitHub App configured with appropriate permissions

### Start Service

```bash
# Start the service
docker compose --profile github-automation up -d github-crossrepo-pr

# Check service health
curl http://localhost:8104/healthz

# View logs
docker compose logs -f github-crossrepo-pr
```

### Usage Examples

#### List Available Templates

```bash
curl http://localhost:8104/api/templates
```

#### Create a Dependency Update PR

```bash
curl -X POST http://localhost:8104/api/pr/create \
  -H "Content-Type: application/json" \
  -d '{
    "pr_type": "dependency_update",
    "repo": "PMOVES.AI",
    "base_branch": "main",
    "template_vars": {
      "package": "fastapi",
      "old_version": "0.100.0",
      "new_version": "0.115.0",
      "description": "Performance improvements and bug fixes",
      "changes": "- Improved request handling\n- Fixed memory leaks",
      "repos_list": "- PMOVES.AI\n- PMOVES-Agent-Zero"
    }
  }'
```

#### Create a Security Patch PR

```bash
curl -X POST http://localhost:8104/api/pr/create \
  -H "Content-Type: application/json" \
  -d '{
    "pr_type": "security_patch",
    "repo": "PMOVES.AI",
    "base_branch": "main",
    "template_vars": {
      "cve_id": "CVE-2024-12345",
      "severity": "High",
      "cvss_score": "8.5",
      "package": "requests",
      "vulnerable_versions": "< 2.31.0",
      "patched_versions": "2.31.0",
      "description": "URL parsing vulnerability",
      "impact": "Remote code execution possible",
      "repos_list": "- PMOVES.AI\n- PMOVES-Agent-Zero\n- PMOVES-Archon",
      "published_date": "2024-03-13"
    }
  }'
```

#### Batch Create PRs Across Multiple Repos

```bash
curl -X POST http://localhost:8104/api/pr/batch \
  -H "Content-Type: application/json" \
  -d '{
    "pr_type": "dependency_update",
    "repos": ["PMOVES.AI", "PMOVES-Agent-Zero", "PMOVES-Archon"],
    "base_branch": "main",
    "template_vars": {
      "package": "pydantic",
      "old_version": "2.9.0",
      "new_version": "2.10.0",
      "description": "Type validation improvements",
      "changes": "- Better error messages\n- Improved performance"
    }
  }'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS server URL |
| `SERVICE_PORT` | `8104` | Service port |
| `DRY_RUN` | `true` | Enable dry-run mode |
| `AGENTZERO_MCP_URL` | `http://agent-zero:8080/mcp/command` | Agent Zero MCP endpoint |
| `GITHUB_ORG` | `POWERFULMOVES` | GitHub organization name |

### Repository Configuration

```python
REPO_CONFIG = {
    "default_base_branch": "main",
    "protected_branches": [
        "main",
        "PMOVES.AI-Edition-Hardened",
        "PMOVES.AI-Edition-Hardened-Integrations"
    ],
    "auto_merge_enabled_repos": [],
}
```

## API Endpoints

### GET /healthz

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "github-crossrepo-pr",
  "nats_connected": true,
  "dry_run": true
}
```

### GET /metrics

Prometheus metrics endpoint.

### GET /api/templates

List all available workflow templates.

**Response:**
```json
{
  "ok": true,
  "templates": [
    {
      "type": "dependency_update",
      "title_example": "chore(deps): bump fastapi from 0.100.0 to 0.115.0",
      "branch_example": "chore/deps/fastapi-bump-0.115.0",
      "labels": ["dependencies", "automated", "chore"],
      "auto_merge": false
    }
  ],
  "total": 6
}
```

### POST /api/pr/create

Create a pull request from a workflow template.

**Request Body:**
```json
{
  "pr_type": "dependency_update",
  "repo": "PMOVES.AI",
  "base_branch": "main",
  "template_vars": {
    "package": "fastapi",
    "old_version": "0.100.0",
    "new_version": "0.115.0"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "result": {
    "success": true,
    "repo": "PMOVES.AI",
    "pr_number": 1234,
    "pr_url": "https://github.com/POWERFULMOVES/PMOVES.AI/pull/1234",
    "error": null,
    "duration_seconds": 3.45
  }
}
```

### POST /api/pr/batch

Batch create pull requests across multiple repositories.

**Request Body:**
```json
{
  "pr_type": "dependency_update",
  "repos": ["PMOVES.AI", "PMOVES-Agent-Zero"],
  "base_branch": "main",
  "template_vars": {
    "package": "fastapi",
    "old_version": "0.100.0",
    "new_version": "0.115.0"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "results": [
    {
      "repo": "PMOVES.AI",
      "success": true,
      "pr_number": 1234,
      "pr_url": "https://github.com/POWERFULMOVES/PMOVES.AI/pull/1234",
      "error": null,
      "duration_seconds": 3.45
    },
    {
      "repo": "PMOVES-Agent-Zero",
      "success": true,
      "pr_number": 567,
      "pr_url": "https://github.com/POWERFULMOVES/PMOVES-Agent-Zero/pull/567",
      "error": null,
      "duration_seconds": 2.89
    }
  ],
  "summary": {
    "total": 2,
    "successful": 2,
    "failed": 0
  }
}
```

## Monitoring

### Prometheus Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `github_crossrepo_pr_created_total` | Counter | pr_type, repo, status | Total PRs created |
| `github_crossrepo_pr_merged_total` | Counter | pr_type, repo | Total PRs merged |
| `github_crossrepo_pr_failed_total` | Counter | pr_type, repo, error_type | Total PR creation failures |
| `github_crossrepo_pr_duration_seconds` | Histogram | pr_type, repo, status | PR creation duration |
| `github_crossrepo_pr_active_operations` | Gauge | - | Active PR operations |

### Grafana Dashboard

Use the GitHub Automation dashboard at http://localhost:3000 to visualize:
- PR creation rates by type
- PR success/failure ratios
- Operation duration percentiles
- Active operations over time

## Integration with Other Services

### Branch Naming Service (port 8102)

Validate branch names before creating PRs:
```bash
# Validate branch name
curl "http://localhost:8102/api/validate?branch=chore/deps/fastapi-bump-0.115.0"
```

### Cross-Repo Sync Service (port 8103)

Listens to sync completion events to trigger PR creation:
```
github.crossrepo.sync.completed.v1 → github-crossrepo-pr
```

### Branch Cleanup Service (port 8100)

Automatically cleans up source branches after PR merge:
```
github.crossrepo.pr.merged.v1 → github-branch-cleanup
```

## Troubleshooting

### Service won't start

Check NATS connectivity:
```bash
docker compose logs github-crossrepo-pr | grep "NATS"
```

### PR creation fails

Check Agent Zero MCP status:
```bash
curl http://localhost:8080/healthz
```

Check GitHub App permissions:
- Ensure GitHub App has write access to pull requests
- Verify Agent Zero MCP token minting works

### Dry-run mode

Service starts in dry-run mode by default. To enable production mode:
```bash
export DRY_RUN=false
docker compose up -d github-crossrepo-pr
```

⚠️ **WARNING**: Production mode will create real pull requests!

## Development

### Run Tests

```bash
cd pmoves/services/github-crossrepo-pr
pytest tests/
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run service
python -m uvicorn app:app --host 0.0.0.0 --port 8104 --reload
```

## Best Practices

1. **Always test in dry-run mode first** before enabling production mode
2. **Use workflow templates** for consistent PR formatting
3. **Monitor metrics** to ensure PR creation success rates
4. **Coordinate with other services** via NATS events
5. **Validate branch names** before creating PRs
6. **Set appropriate reviewers** for each PR type
7. **Use batch operations** for multi-repo updates

## License

MIT

## Support

For issues and questions:
- GitHub Issues: https://github.com/POWERFULMOVES/PMOVES.AI/issues
- Documentation: pmoves/docs/GITHUB_AUTOMATION_GUIDE.md
