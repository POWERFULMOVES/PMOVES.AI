# GitHub Issue Triage Service

Intelligent issue classification and labeling using semantic search (Hi-RAG v2) and pattern-based matching.

## Overview

This service automatically categorizes GitHub issues by:
1. **Semantic Search**: Querying Hi-RAG v2 for similar historical issues
2. **Pattern Matching**: Fallback to regex-based classification
3. **Confidence Threshold**: Only applies labels above threshold (default: 0.7)

## Architecture

```
GitHub Webhook (issues) → n8n → NATS: github.webhook.issue.v1
→ Issue Triage Service (port 8101)
→ Hi-RAG v2 Query (semantic search)
→ BoTZ MCP GitHub Tools
→ Update Issue Labels
→ NATS: github.issue.triage.v1, github.issue.labeled.v1
```

## Labels Applied

| Label | Description | Patterns |
|-------|-------------|----------|
| `bug` | Defects, errors, crashes | error, crash, broken, doesn't work |
| `feature` | New features, enhancements | add, implement, support for |
| `documentation` | Documentation issues | docs, readme, guide, tutorial |
| `performance` | Performance issues | slow, latency, optimize |
| `security` | Security vulnerabilities | exploit, xss, csrf, injection |
| `refactor` | Code quality issues | refactor, clean up, technical debt |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS connection URL |
| `HIRAG_URL` | `http://hi-rag-gateway-v2:8086` | Hi-RAG v2 gateway URL |
| `LABEL_CONFIDENCE_THRESHOLD` | `0.7` | Minimum confidence for auto-labeling |
| `INDEX_HISTORICAL_ISSUES` | `true` | Index closed issues on startup |
| `BOTZ_MCP_URL` | `http://botz-gateway:8102` | BoTZ MCP gateway URL |

## API Endpoints

### Health Check
```bash
GET /healthz
```

Returns service health and component status.

### Manual Triage
```bash
POST /api/triage?repo=PMOVES.AI&issue_number=1234
```

Manually trigger triage for an issue.

**Response:**
```json
{
  "ok": true,
  "result": {
    "repo": "PMOVES.AI",
    "issue_number": 1234,
    "labels": ["bug"],
    "confidence": 0.85,
    "method": "semantic",
    "reasoning": "Found 5 similar issues"
  }
}
```

### Accuracy Metrics
```bash
GET /api/accuracy?repo=PMOVES.AI&days=30
```

Get triage accuracy statistics (TODO: implement).

### Prometheus Metrics
```bash
GET /metrics
```

Prometheus metrics endpoint.

## Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `github_issue_triaged_total` | Counter | repo, label_type | Total issues triaged |
| `github_issue_label_applied_total` | Counter | repo, label | Total labels applied |
| `github_issue_triage_confidence_histogram` | Histogram | repo | Confidence distribution |
| `github_issue_triage_error_total` | Counter | repo, error_type | Total errors |
| `github_issue_hirag_query_duration_seconds` | Histogram | repo | Hi-RAG query latency |

## NATS Events

### Incoming
- `github.webhook.issue.v1` - GitHub webhook events from n8n

### Outgoing
- `github.issue.triage.v1` - Triage completion events
- `github.issue.labeled.v1` - Label application events

## Development

Run locally:
```bash
cd pmoves/services/github-issue-triage
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Testing

Test triage endpoint:
```bash
curl http://localhost:8101/api/triage?repo=PMOVES.AI&issue_number=1234
```

Test health:
```bash
curl http://localhost:8101/healthz
```

## Dependencies

- **Hi-RAG v2**: Semantic search (must be healthy)
- **BoTZ Gateway**: GitHub MCP tools
- **NATS**: Event bus
- **n8n**: Webhook ingestion (if using webhooks)

## Integration with Hi-RAG v2

The service queries Hi-RAG v2 for semantically similar issues:

```python
POST http://hi-rag-gateway-v2:8086/hirag/query
{
  "query": "Issue text here",
  "top_k": 5,
  "rerank": true
}
```

Results are analyzed to find common labels in similar issues.

## Future Improvements

- [ ] Implement historical issue indexing on startup
- [ ] Add accuracy calculation endpoint
- [ ] Support custom label patterns per repository
- [ ] Add issue triage dashboard in Grafana
- [ ] Learn from manual label corrections
