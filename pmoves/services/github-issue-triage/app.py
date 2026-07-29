"""
GitHub Issue Triage Service

Automatically categorizes and labels GitHub issues using semantic search via Hi-RAG v2
and pattern-based classification for intelligent issue triage.

NATS Events:
  - Subscribe: github.webhook.issue.v1 (from n8n)
  - Publish: github.issue.triage.v1, github.issue.labeled.v1

Metrics:
  - github_issue_triaged_total
  - github_issue_label_applied_total
  - github_issue_triage_confidence_histogram
  - github_issue_triage_error_total
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest
from nats.aio.client import Client as NATS

from labeling_rules import LabelingRules
from hirag_client import HiRAGClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
NATS_URL = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")
HIRAG_URL = os.getenv("HIRAG_URL", "http://hi-rag-gateway-v2:8086")
LABEL_CONFIDENCE_THRESHOLD = float(os.getenv("LABEL_CONFIDENCE_THRESHOLD", "0.7"))
INDEX_HISTORICAL_ISSUES = os.getenv("INDEX_HISTORICAL_ISSUES", "true").lower() == "true"
BOTZ_MCP_URL = os.getenv("BOTZ_MCP_URL", "http://botz-gateway:8102")

# Initialize FastAPI
app = FastAPI(
    title="GitHub Issue Triage Service",
    description="Intelligent issue triage using Hi-RAG v2 semantic search",
    version="1.0.0"
)

# Prometheus metrics
issue_triaged_total = Counter(
    'github_issue_triaged_total',
    'Total number of issues triaged',
    ['repo', 'label_type']
)

label_applied_total = Counter(
    'github_issue_label_applied_total',
    'Total number of labels applied',
    ['repo', 'label']
)

triage_confidence_histogram = Histogram(
    'github_issue_triage_confidence_histogram',
    'Confidence scores for triage decisions',
    ['repo'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

triage_error_total = Counter(
    'github_issue_triage_error_total',
    'Total number of triage errors',
    ['repo', 'error_type']
)

hirag_query_duration = Histogram(
    'github_issue_hirag_query_duration_seconds',
    'Hi-RAG query duration in seconds',
    ['repo'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Global state
hirag_client: Optional[HiRAGClient] = None
labeling_rules: Optional[LabelingRules] = None
nc: Optional[NATS] = None


@dataclass
class IssueTriageResult:
    """Result of issue triage operation"""
    repo: str
    issue_number: int
    labels: List[str]
    confidence: float
    classification_method: str  # 'semantic' or 'pattern'
    reasoning: str


class GitHubMCPClient:
    """Client for GitHub operations via BoTZ MCP Gateway"""

    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self.timeout = 30

    async def add_labels(self, repo: str, issue_number: int, labels: List[str]) -> bool:
        """Add labels to an issue via MCP"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.mcp_url}/mcp/github/add_labels",
                    json={
                        "repo": repo,
                        "issue_number": issue_number,
                        "labels": labels
                    }
                )
                response.raise_for_status()
                logger.info(f"Added labels {labels} to {repo}#{issue_number}")
                return True
        except Exception as e:
            logger.error(f"Failed to add labels via MCP: {e}")
            triage_error_total.labels(repo=repo, error_type='mcp_call').inc()
            return False

    async def get_issue(self, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        """Fetch issue details via MCP"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.mcp_url}/mcp/github/get_issue",
                    params={
                        "repo": repo,
                        "issue_number": issue_number
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch issue via MCP: {e}")
            return None


async def triage_issue(
    repo: str,
    issue_number: int,
    issue_data: Optional[Dict[str, Any]] = None
) -> IssueTriageResult:
    """
    Main triage function - classifies issue type and suggests labels

    Strategy:
    1. Try semantic search via Hi-RAG v2 for context-aware classification
    2. Fall back to pattern-based classification if Hi-RAG unavailable
    3. Apply confidence threshold to prevent false positives
    """
    # Fetch issue data if not provided
    if not issue_data:
        github_client = GitHubMCPClient(BOTZ_MCP_URL)
        issue_data = await github_client.get_issue(repo, issue_number)
        if not issue_data:
            raise ValueError(f"Failed to fetch issue {repo}#{issue_number}")

    # Extract issue text
    title = issue_data.get('title', '')
    body = issue_data.get('body', '')
    issue_text = f"{title}\n{body}"

    # Try semantic search first
    labels = []
    confidence = 0.0
    method = "pattern"
    reasoning = "Pattern-based classification"

    try:
        if hirag_client:
            with hirag_query_duration.labels(repo=repo).time():
                similar_issues = await hirag_client.query(issue_text, top_k=5)

            if similar_issues and len(similar_issues) > 0:
                # Analyze similar issues for label patterns
                label_scores = {}
                for issue in similar_issues:
                    for label in issue.get('labels', []):
                        label_scores[label] = label_scores.get(label, 0) + 1

                if label_scores:
                    # Get most common label
                    top_label = max(label_scores, key=label_scores.get)
                    confidence = label_scores[top_label] / len(similar_issues)

                    if confidence >= LABEL_CONFIDENCE_THRESHOLD:
                        labels.append(top_label)
                        method = "semantic"
                        reasoning = f"Found {len(similar_issues)} similar issues"

    except Exception as e:
        logger.warning(f"Hi-RAG query failed, falling back to patterns: {e}")
        triage_error_total.labels(repo=repo, error_type='hirag_query').inc()

    # Pattern-based classification (fallback or enhancement)
    pattern_result = labeling_rules.classify_issue(issue_text)

    # Merge results (prefer semantic if confident)
    if method == "semantic" and confidence >= LABEL_CONFIDENCE_THRESHOLD:
        # Use semantic result
        pass
    else:
        # Use pattern-based result
        if pattern_result['label']:
            labels = [pattern_result['label']]
            confidence = pattern_result['confidence']
            method = "pattern"
            reasoning = pattern_result['reasoning']

    result = IssueTriageResult(
        repo=repo,
        issue_number=issue_number,
        labels=labels,
        confidence=confidence,
        classification_method=method,
        reasoning=reasoning
    )

    # Record metrics
    for label in labels:
        issue_triaged_total.labels(repo=repo, label_type=label).inc()
        label_applied_total.labels(repo=repo, label=label).inc()

    triage_confidence_histogram.labels(repo=repo).observe(confidence)

    return result


async def handle_webhook_event(msg):
    """Handle incoming GitHub webhook events from n8n"""
    try:
        import json
        data = json.loads(msg.data.decode())

        action = data.get('action')
        issue_data = data.get('issue', {})
        repo = issue_data.get('repository', {}).get('full_name')
        issue_number = issue_data.get('number')

        if not repo or not issue_number:
            logger.warning("Invalid webhook event: missing repo or issue_number")
            return

        # Only process opened and edited issues
        if action not in ['opened', 'edited']:
            logger.info(f"Skipping action '{action}' for {repo}#{issue_number}")
            return

        logger.info(f"Triaging issue {repo}#{issue_number} (action: {action})")

        # Perform triage
        result = await triage_issue(repo, issue_number, issue_data)

        # Apply labels via MCP
        if result.labels:
            github_client = GitHubMCPClient(BOTZ_MCP_URL)
            success = await github_client.add_labels(repo, issue_number, result.labels)

            if success:
                # Publish success event
                event_data = {
                    "repo": repo,
                    "issue_number": issue_number,
                    "labels": result.labels,
                    "confidence": result.confidence,
                    "method": result.classification_method,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await nc.publish(
                    "github.issue.labeled.v1",
                    json.dumps(event_data).encode()
                )

                logger.info(
                    f"Triaged {repo}#{issue_number}: "
                    f"labels={result.labels}, confidence={result.confidence:.2f}, "
                    f"method={result.classification_method}"
                )
            else:
                logger.error(f"Failed to apply labels to {repo}#{issue_number}")

    except Exception as e:
        logger.error(f"Error handling webhook event: {e}")
        triage_error_total.labels(repo='unknown', error_type='webhook_handler').inc()


@app.on_event("startup")
async def startup_event():
    """Initialize service connections"""
    global hirag_client, labeling_rules, nc

    logger.info("Starting GitHub Issue Triage Service...")

    # Initialize Hi-RAG client
    try:
        hirag_client = HiRAGClient(HIRAG_URL)
        logger.info(f"Hi-RAG client initialized: {HIRAG_URL}")
    except Exception as e:
        logger.error(f"Failed to initialize Hi-RAG client: {e}")
        # Continue without Hi-RAG - will use pattern-based fallback

    # Initialize labeling rules
    labeling_rules = LabelingRules()
    logger.info("Labeling rules initialized")

    # Connect to NATS
    try:
        nc = NATS()
        await nc.connect(NATS_URL)
        logger.info(f"Connected to NATS: {NATS_URL}")

        # Subscribe to webhook events
        await nc.subscribe("github.webhook.issue.v1", "github-issue-triage", handle_webhook_event)
        logger.info("Subscribed to NATS subject: github.webhook.issue.v1")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup connections"""
    global nc

    if nc:
        try:
            await nc.close()
            logger.info("NATS connection closed")
        except Exception as e:
            logger.error(f"Error closing NATS: {e}")


@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "github-issue-triage",
        "hirag_available": hirag_client is not None,
        "labeling_rules_loaded": labeling_rules is not None,
        "nats_connected": nc is not None and nc.is_connected
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()


@app.post("/api/triage")
async def triage_endpoint(repo: str, issue_number: int, background_tasks: BackgroundTasks):
    """
    Manual triage endpoint for testing and on-demand triage

    Args:
        repo: Repository name (e.g., "PMOVES.AI")
        issue_number: Issue number
    """
    try:
        result = await triage_issue(repo, issue_number)

        return {
            "ok": True,
            "result": {
                "repo": result.repo,
                "issue_number": result.issue_number,
                "labels": result.labels,
                "confidence": result.confidence,
                "method": result.classification_method,
                "reasoning": result.reasoning
            }
        }
    except Exception as e:
        logger.error(f"Triage failed for {repo}#{issue_number}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": f"Internal server error triaging {repo}#{issue_number}"
            }
        )


@app.get("/api/accuracy")
async def accuracy_endpoint(repo: str, days: int = 30):
    """
    Calculate triage accuracy based on recent issues

    Args:
        repo: Repository name
        days: Number of days to look back
    """
    try:
        # TODO: Implement accuracy calculation
        # This would query GitHub for issues labeled in the past N days
        # and compare manual corrections vs automatic labels

        return {
            "ok": True,
            "repo": repo,
            "days": days,
            "accuracy": 0.0,
            "message": "Accuracy calculation not yet implemented"
        }
    except Exception as e:
        logger.error(f"Accuracy calculation failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "Internal server error calculating accuracy"
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8101)
