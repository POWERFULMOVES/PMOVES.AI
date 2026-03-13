# GitHub Automation Suite - API Reference

Complete API reference for PMOVES.AI's GitHub automation services.

## Table of Contents

- [Branch Cleanup Service API](#branch-cleanup-service-api)
- [Issue Triage Service API](#issue-triage-service-api)
- [Common Patterns](#common-patterns)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

---

## Branch Cleanup Service API

**Base URL:** `http://localhost:8100`
**Service Port:** 8100
**Docker Service:** `github-branch-cleanup`

### Endpoints

#### GET /healthz

Health check endpoint for Docker and monitoring.

**Request:**
```http
GET /healthz
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "github-branch-cleanup"
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "error": "NATS connection failed"
}
```

---

#### GET /metrics

Prometheus metrics endpoint.

**Request:**
```http
GET /metrics
```

**Response:** Prometheus text format metrics

```prometheus
# HELP github_branch_cleanup_stale_total Total number of stale branches detected
# TYPE github_branch_cleanup_stale_total counter
github_branch_cleanup_stale_total{repo="PMOVES.AI"} 42.0

# HELP github_branch_cleanup_deleted_total Total number of branches deleted
# TYPE github_branch_cleanup_deleted_total counter
github_branch_cleanup_deleted_total{repo="PMOVES.AI"} 15.0

# HELP github_branch_cleanup_duration_seconds Branch cleanup operation duration
# TYPE github_branch_cleanup_duration_seconds histogram
github_branch_cleanup_duration_seconds_bucket{repo="PMOVES.AI",status="success",le="0.1"} 0.0
github_branch_cleanup_duration_seconds_bucket{repo="PMOVES.AI",status="success",le="1.0"} 5.0
github_branch_cleanup_duration_seconds_bucket{repo="PMOVES.AI",status="success",le="+Inf"} 15.0
```

---

#### GET /api/stale-branches

List stale branches in a repository.

**Request:**
```http
GET /api/stale-branches?repo=PMOVES.AI&days=30
```

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo` | string | Yes | - | Repository name (e.g., "PMOVES.AI") |
| `days` | integer | No | 30 | Days threshold for staleness |

**Response (200 OK):**
```json
{
  "repo": "PMOVES.AI",
  "stale_branches": [
    {
      "name": "feature/old-feature",
      "last_commit_date": "2026-02-01T00:00:00Z",
      "stale_days": 40,
      "repo": "PMOVES.AI"
    },
    {
      "name": "fix/bug-123",
      "last_commit_date": "2026-01-15T00:00:00Z",
      "stale_days": 57,
      "repo": "PMOVES.AI"
    }
  ],
  "total_stale": 2
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Missing required parameter: repo"
}
```

**Response (500 Internal Server Error):**
```json
{
  "detail": "Failed to fetch branches from GitHub API"
}
```

**cURL Example:**
```bash
curl "http://localhost:8100/api/stale-branches?repo=PMOVES.AI&days=30"
```

---

#### POST /api/cleanup

Cleanup stale branches from a repository.

**Request:**
```http
POST /api/cleanup
Content-Type: application/json

{
  "repo": "PMOVES.AI",
  "dry_run": true,
  "stale_days": 30
}
```

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo` | string | Yes | - | Repository name |
| `dry_run` | boolean | No | true | If true, only report what would be deleted |
| `stale_days` | integer | No | 30 | Days threshold for staleness |

**Response (200 OK):**
```json
{
  "repo": "PMOVES.AI",
  "stale_branches": [
    {
      "name": "feature/old-feature",
      "last_commit_date": "2026-02-01T00:00:00Z",
      "stale_days": 40,
      "repo": "PMOVES.AI"
    }
  ],
  "deleted_branches": ["feature/old-feature"],
  "protected_skipped": ["main", "release-v1.0"],
  "dry_run": true,
  "duration_seconds": 2.5
}
```

**Response (400 Bad Request):**
```json
{
  "detail": "Missing required field: repo"
}
```

**Response (500 Internal Server Error):**
```json
{
  "detail": "Failed to mint GitHub token"
}
```

**cURL Example:**
```bash
# Dry-run (safe)
curl -X POST http://localhost:8100/api/cleanup \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "PMOVES.AI",
    "dry_run": true,
    "stale_days": 30
  }'

# Production (permanently deletes branches!)
curl -X POST http://localhost:8100/api/cleanup \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "PMOVES.AI",
    "dry_run": false,
    "stale_days": 30
  }'
```

---

## Issue Triage Service API

**Base URL:** `http://localhost:8101`
**Service Port:** 8101
**Docker Service:** `github-issue-triage`

### Endpoints

#### GET /healthz

Health check endpoint for Docker and monitoring.

**Request:**
```http
GET /healthz
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "github-issue-triage",
  "hirag_available": true,
  "labeling_rules_loaded": true,
  "nats_connected": true
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "service": "github-issue-triage",
  "hirag_available": false,
  "labeling_rules_loaded": true,
  "nats_connected": true,
  "error": "Hi-RAG connection failed"
}
```

---

#### GET /metrics

Prometheus metrics endpoint.

**Request:**
```http
GET /metrics
```

**Response:** Prometheus text format metrics

```prometheus
# HELP github_issue_triaged_total Total number of issues triaged
# TYPE github_issue_triaged_total counter
github_issue_triaged_total{repo="PMOVES.AI",label_type="bug"} 125.0
github_issue_triaged_total{repo="PMOVES.AI",label_type="feature"} 87.0

# HELP github_issue_triage_confidence_histogram Confidence scores for triage decisions
# TYPE github_issue_triage_confidence_histogram histogram
github_issue_triage_confidence_histogram_bucket{repo="PMOVES.AI",le="0.7"} 15.0
github_issue_triage_confidence_histogram_bucket{repo="PMOVES.AI",le="0.8"} 42.0
github_issue_triage_confidence_histogram_bucket{repo="PMOVES.AI",le="+Inf"} 212.0

# HELP github_issue_hirag_query_duration_seconds Hi-RAG query duration in seconds
# TYPE github_issue_hirag_query_duration_seconds histogram
github_issue_hirag_query_duration_seconds_bucket{repo="PMOVES.AI",le="0.5"} 180.0
github_issue_hirag_query_duration_seconds_bucket{repo="PMOVES.AI",le="1.0"} 205.0
github_issue_hirag_query_duration_seconds_bucket{repo="PMOVES.AI",le="+Inf"} 212.0
```

---

#### POST /api/triage

Manually trigger triage for a specific issue.

**Request:**
```http
POST /api/triage?repo=PMOVES.AI&issue_number=1234
```

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo` | string | Yes | - | Repository name (e.g., "PMOVES.AI") |
| `issue_number` | integer | Yes | - | Issue number |

**Response (200 OK):**
```json
{
  "ok": true,
  "result": {
    "repo": "PMOVES.AI",
    "issue_number": 1234,
    "labels": ["bug"],
    "confidence": 0.85,
    "method": "semantic",
    "reasoning": "Found 5 similar issues with label 'bug'"
  }
}
```

**Response (400 Bad Request):**
```json
{
  "ok": false,
  "error": "Missing required parameter: issue_number"
}
```

**Response (404 Not Found):**
```json
{
  "ok": false,
  "error": "Issue #1234 not found in repository PMOVES.AI"
}
```

**Response (500 Internal Server Error):**
```json
{
  "ok": false,
  "error": "Failed to triage issue: Hi-RAG query timeout"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8101/api/triage?repo=PMOVES.AI&issue_number=1234"
```

---

#### GET /api/accuracy

Calculate triage accuracy based on recent issues.

**⚠️ Note:** This endpoint is not yet implemented and returns placeholder data.

**Request:**
```http
GET /api/accuracy?repo=PMOVES.AI&days=30
```

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `repo` | string | Yes | - | Repository name |
| `days` | integer | No | 30 | Number of days to look back |

**Response (200 OK - Placeholder):**
```json
{
  "ok": true,
  "repo": "PMOVES.AI",
  "days": 30,
  "accuracy": 0.0,
  "message": "Accuracy calculation not yet implemented"
}
```

**cURL Example:**
```bash
curl "http://localhost:8101/api/accuracy?repo=PMOVES.AI&days=30"
```

---

## Common Patterns

### Authentication

Both services use GitHub App authentication via Agent Zero MCP:

```python
# Internal token minting flow
async def get_github_token() -> str:
    response = await http_client.post(
        f"{config.AGENTZERO_MCP_URL}/tools/github_mint_token",
        json={
            "app_id": config.GITHUB_APP_ID,
            "installation_id": config.GITHUB_APP_INSTALLATION_ID
        }
    )
    return response.json()["token"]
```

### Pagination

For large repositories, consider pagination:

```python
# GitHub API pagination
async def get_all_branches(repo: str) -> List[Dict]:
    branches = []
    page = 1
    while True:
        response = await http_client.get(
            f"{GITHUB_API_URL}/repos/{org}/{repo}/branches",
            params={"page": page, "per_page": 100}
        )
        data = response.json()
        if not data:
            break
        branches.extend(data)
        page += 1
    return branches
```

### Error Handling

Standard error response format:

```json
{
  "ok": false,
  "error": "Error message describing what went wrong"
}
```

HTTP Status Codes:
- `200 OK` - Request succeeded
- `400 Bad Request` - Invalid parameters
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server-side error
- `503 Service Unavailable` - Service unhealthy

---

## Error Handling

### Branch Cleanup Service

**Error: "Failed to mint GitHub token"**

**Cause:** Agent Zero MCP unavailable or credentials invalid

**Solution:**
```bash
# Check Agent Zero health
curl http://localhost:8080/healthz

# Verify environment variables
docker compose exec github-branch-cleanup env | grep GITHUB_APP

# Test MCP endpoint directly
curl -X POST http://localhost:8080/mcp/github_mint_token \
  -H "Content-Type: application/json" \
  -d '{"app_id": "123", "installation_id": "456"}'
```

**Error: "Failed to fetch branches from GitHub API"**

**Cause:** Invalid repository name or GitHub API rate limit

**Solution:**
```bash
# Verify repository exists
curl https://api.github.com/repos/POWERFULMOVES/PMOVES.AI

# Check rate limit
curl -I https://api.github.com/repos/POWERFULMOVES/PMOVES.AI
# Look for: X-RateLimit-Remaining
```

### Issue Triage Service

**Error: "Hi-RAG query failed, falling back to patterns"**

**Cause:** Hi-RAG v2 unavailable or query timeout

**Solution:**
```bash
# Check Hi-RAG health
curl http://localhost:8086/healthz

# Test Hi-RAG query
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5, "rerank": true}'
```

**Error: "Failed to add labels via MCP"**

**Cause:** BoTZ Gateway unavailable or MCP endpoint error

**Solution:**
```bash
# Check BoTZ Gateway health
curl http://localhost:8102/healthz

# Test MCP endpoint
curl -X POST http://localhost:8102/mcp/github/add_labels \
  -H "Content-Type: application/json" \
  -d '{"repo": "PMOVES.AI", "issue_number": 1, "labels": ["test"]}'
```

---

## Rate Limiting

### GitHub API Rate Limits

Both services respect GitHub API rate limits:

- **Authenticated requests:** 5,000 requests/hour
- **Unauthenticated requests:** 60 requests/hour

**Best Practices:**
1. Use GitHub App authentication (higher limits)
2. Implement exponential backoff on rate limit errors
3. Cache responses when appropriate
4. Monitor rate limit usage via metrics

**Rate Limit Response:**
```http
HTTP/1.1 403 Forbidden
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4999
X-RateLimit-Reset: 1372700873
```

### Service-Level Rate Limiting

No built-in rate limiting on service endpoints. Consider adding for production:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/cleanup")
@limiter.limit("10/minute")
async def cleanup_stale_branches(request: Request, cleanup_request: CleanupRequest):
    ...
```

---

## Webhook Integration

### Incoming Webhooks

Both services subscribe to NATS subjects for webhook events:

**Branch Cleanup:**
- **Subject:** `github.webhook.pr.v1`
- **Actions:** `closed`, `merged`
- **Payload:**
  ```json
  {
    "action": "closed",
    "repository": {
      "name": "PMOVES.AI",
      "full_name": "POWERFULMOVES/PMOVES.AI"
    },
    "pull_request": {
      "number": 1234,
      "head": {
        "ref": "feature/old-feature"
      }
    }
  }
  ```

**Issue Triage:**
- **Subject:** `github.webhook.issue.v1`
- **Actions:** `opened`, `edited`
- **Payload:**
  ```json
  {
    "action": "opened",
    "issue": {
      "number": 5678,
      "title": "Bug in feature X",
      "body": "Detailed description...",
      "repository": {
        "name": "PMOVES.AI",
        "full_name": "POWERFULMOVES/PMOVES.AI"
      }
    }
  }
  ```

### Outgoing Events

**Branch Cleanup Events:**
- `github.branch.stale_detected.v1`
- `github.branch.deleted.v1`
- `github.branch.auto_deleted.v1`

**Issue Triage Events:**
- `github.issue.triage.v1`
- `github.issue.labeled.v1`

**Event Format:**
```json
{
  "repo": "PMOVES.AI",
  "timestamp": "2026-03-13T12:00:00Z",
  "event_type": "github.branch.deleted.v1",
  "data": {
    "deleted_count": 5,
    "dry_run": false,
    "duration_seconds": 3.2
  }
}
```

---

## Testing

### Unit Tests

```bash
# Branch cleanup tests
pytest pmoves/tests/test_branch_cleanup.py -v

# Issue triage tests
pytest pmoves/tests/test_issue_triage.py -v
```

### Integration Tests

```bash
# Test branch cleanup
curl "http://localhost:8100/api/stale-branches?repo=PMOVES.AI&days=30"

# Test issue triage
curl -X POST "http://localhost:8101/api/triage?repo=PMOVES.AI&issue_number=1"
```

### Load Testing

```bash
# Use Apache Bench
ab -n 1000 -c 10 http://localhost:8100/healthz

# Use wrk
wrk -t4 -c100 -d30s http://localhost:8100/metrics
```

---

## Additional Resources

- **User Guide:** See `GITHUB_AUTOMATION_GUIDE.md`
- **NATS Events:** See `GITHUB_AUTOMATION_NATS.md`
- **Service Documentation:**
  - `pmoves/services/github-branch-cleanup/README.md`
  - `pmoves/services/github-issue-triage/README.md`

---

**Last Updated:** 2026-03-13
**API Version:** 1.0.0
