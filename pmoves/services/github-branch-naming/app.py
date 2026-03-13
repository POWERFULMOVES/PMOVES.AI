"""GitHub Branch Naming Enforcement Service

Validates branch names against PMOVES.AI conventions and publishes
validation events to NATS for observability.

NATS Events:
  - Subscribe: github.branch.created.v1
  - Publish: github.branch.validation.v1, github.branch.rename_suggested.v1

API Endpoints:
  - GET /healthz - Health check
  - GET /metrics - Prometheus metrics
  - GET /api/validate?branch={name} - Validate branch name
  - POST /api/validate - Validate branch name (JSON payload)

Metrics:
  - github_branch_naming_validated_total
  - github_branch_naming_failed_total
  - github_branch_naming_rename_suggested_total
"""

import asyncio
import re
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest
from nats.aio.client import Client as NATS
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
NATS_URL = "nats://nats:pmoves@nats:4222"
SERVICE_PORT = 8102
DRY_RUN = True
AGENTZERO_MCP_URL = "http://agent-zero:8080/mcp/command"

# Branch naming patterns
VALID_PATTERNS = [
    (r'^feat/', 'feature'),
    (r'^fix/', 'bugfix'),
    (r'^chore/', 'chore'),
    (r'^docs/', 'documentation'),
    (r'^codex/', 'CODEX-generated'),
    (r'^ref/docs/', 'reference documentation'),
    (r'^PMOVES\.AI-Edition-Hardened(-Integrations)?$', 'protected branch'),
    (r'^main$', 'protected branch'),
]

# Protected branches (no validation required)
PROTECTED_BRANCHES = [
    'PMOVES.AI-Edition-Hardened',
    'PMOVES.AI-Edition-Hardened-Integrations',
    'main',
]

# Suggested renames for invalid patterns
RENAME_SUGGESTIONS = {
    r'feature/(.+)': 'feat/\\1',
    r'bugfix/(.+)': 'fix/\\1',
    r'documentation/(.+)': 'docs/\\1',
    r'maintenance/(.+)': 'chore/\\1',
    r'ref/(.+)': 'ref/docs/\\1',
}


@dataclass
class ValidationResult:
    """Result of branch name validation."""
    branch: str
    is_valid: bool
    category: Optional[str]
    suggested_name: Optional[str]
    reason: str


class BranchValidationRequest(BaseModel):
    """Request to validate a branch name."""
    branch: str = Field(..., description="Branch name to validate")


class BranchValidationResponse(BaseModel):
    """Response from branch validation."""
    branch: str
    is_valid: bool
    category: Optional[str] = None
    suggested_name: Optional[str] = None
    reason: str
    timestamp: str


# Prometheus metrics
branches_validated_total = Counter(
    'github_branch_naming_validated_total',
    'Total number of branch names validated',
    ['valid', 'category']
)

branches_failed_total = Counter(
    'github_branch_naming_failed_total',
    'Total number of invalid branch names',
    ['suggested_rename']
)

rename_suggested_total = Counter(
    'github_branch_naming_rename_suggested_total',
    'Total number of branch rename suggestions',
    ['original_pattern']
)

# Global state
nc: Optional[NATS] = None
http_client: Optional[httpx.AsyncClient] = None


def validate_branch_name(branch: str) -> ValidationResult:
    """Validate branch name against PMOVES.AI conventions.

    Args:
        branch: Branch name to validate

    Returns:
        ValidationResult with validation outcome
    """
    # Check protected branches first
    if branch in PROTECTED_BRANCHES:
        return ValidationResult(
            branch=branch,
            is_valid=True,
            category='protected',
            suggested_name=None,
            reason='Protected branch (no validation required)'
        )

    # Check against valid patterns
    for pattern, category in VALID_PATTERNS:
        if re.match(pattern, branch):
            return ValidationResult(
                branch=branch,
                is_valid=True,
                category=category,
                suggested_name=None,
                reason=f'Valid {category} branch name'
            )

    # Branch is invalid, suggest rename
    suggested_name = None
    for pattern, suggestion in RENAME_SUGGESTIONS.items():
        match = re.match(pattern, branch)
        if match:
            suggested_name = suggestion.replace('\\1', match.group(1))
            break

    if not suggested_name:
        # Generic suggestion
        suggested_name = f"feat/{branch.replace('_', '-')}"

    return ValidationResult(
        branch=branch,
        is_valid=False,
        category=None,
        suggested_name=suggested_name,
        reason=f'Invalid branch name format. Suggested: {suggested_name}'
    )


async def publish_nats_event(subject: str, data: Dict[str, Any]) -> None:
    """Publish event to NATS.

    Args:
        subject: NATS subject
        data: Event payload
    """
    if not nc:
        logger.warning("NATS not connected, skipping event publish")
        return

    try:
        import json
        await nc.publish(subject, json.dumps(data).encode())
        logger.debug(f"Published event to {subject}")
    except Exception as e:
        logger.error(f"Failed to publish NATS event: {e}")


async def handle_branch_created_event(msg):
    """Handle branch creation event from NATS.

    Args:
        msg: NATS message with branch creation payload
    """
    try:
        import json
        data = json.loads(msg.data.decode())

        branch = data.get('branch', '')
        repo = data.get('repo', '')
        action = data.get('action', '')

        # Only process branch creation
        if action != 'created':
            return

        if not branch:
            logger.warning("Invalid branch creation event: missing branch name")
            return

        logger.info(f"Validating branch: {branch}")

        # Validate branch name
        result = validate_branch_name(branch)

        # Record metrics
        branches_validated_total.labels(
            valid=result.is_valid,
            category=result.category or 'invalid'
        ).inc()

        # Publish validation event
        await publish_nats_event("github.branch.validation.v1", {
            "repo": repo,
            "branch": branch,
            "is_valid": result.is_valid,
            "category": result.category,
            "suggested_name": result.suggested_name,
            "reason": result.reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # If invalid and rename suggested, publish suggestion event
        if not result.is_valid and result.suggested_name:
            rename_suggested_total.labels(
                original_pattern='unknown'
            ).inc()

            await publish_nats_event("github.branch.rename_suggested.v1", {
                "repo": repo,
                "original_branch": branch,
                "suggested_branch": result.suggested_name,
                "reason": result.reason,
                "dry_run": DRY_RUN,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            logger.warning(
                f"Invalid branch name: {branch} → Suggested: {result.suggested_name}"
            )

        # Optionally rename branch (if DRY_RUN is False)
        if not result.is_valid and not DRY_RUN and result.suggested_name:
            logger.info(f"Would rename branch: {branch} → {result.suggested_name}")
            # TODO: Implement branch rename via GitHub MCP
            # This requires admin permissions and careful handling

    except Exception as e:
        logger.error(f"Error handling branch created event: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global nc, http_client

    # Initialize HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)

    # Connect to NATS
    try:
        nc = NATS()
        await nc.connect(NATS_URL)
        logger.info(f"Connected to NATS at {NATS_URL}")

        # Subscribe to branch creation events
        await nc.subscribe(
            "github.branch.created.v1",
            "github-branch-naming",
            handle_branch_created_event
        )
        logger.info("Subscribed to github.branch.created.v1")

    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        # Continue without NATS - API endpoints still work

    yield

    # Cleanup
    try:
        if nc:
            await nc.close()
        if http_client:
            await http_client.aclose()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


# FastAPI app
app = FastAPI(
    title="GitHub Branch Naming Enforcement Service",
    description="Validates branch names against PMOVES.AI conventions",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/healthz")
async def health_check():
    """Health check endpoint for Docker."""
    return {
        "status": "healthy",
        "service": "github-branch-naming",
        "nats_connected": nc is not None and nc.is_connected if nc else False
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.get("/api/validate", response_model=BranchValidationResponse)
async def validate_branch_get(branch: str = Query(..., description="Branch name to validate")):
    """Validate branch name via GET request.

    Args:
        branch: Branch name to validate

    Returns:
        BranchValidationResponse with validation result
    """
    result = validate_branch_name(branch)

    # Record metrics
    branches_validated_total.labels(
        valid=result.is_valid,
        category=result.category or 'invalid'
    ).inc()

    if not result.is_valid:
        branches_failed_total.labels(
            suggested_rename=str(result.suggested_name is not None)
        ).inc()

    return BranchValidationResponse(
        branch=result.branch,
        is_valid=result.is_valid,
        category=result.category,
        suggested_name=result.suggested_name,
        reason=result.reason,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.post("/api/validate", response_model=BranchValidationResponse)
async def validate_branch_post(request: BranchValidationRequest):
    """Validate branch name via POST request.

    Args:
        request: BranchValidationRequest with branch name

    Returns:
        BranchValidationResponse with validation result
    """
    result = validate_branch_name(request.branch)

    # Record metrics
    branches_validated_total.labels(
        valid=result.is_valid,
        category=result.category or 'invalid'
    ).inc()

    if not result.is_valid:
        branches_failed_total.labels(
            suggested_rename=str(result.suggested_name is not None)
        ).inc()

    # Publish validation event to NATS
    await publish_nats_event("github.branch.validation.v1", {
        "repo": "unknown",  # Not available in API context
        "branch": result.branch,
        "is_valid": result.is_valid,
        "category": result.category,
        "suggested_name": result.suggested_name,
        "reason": result.reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return BranchValidationResponse(
        branch=result.branch,
        is_valid=result.is_valid,
        category=result.category,
        suggested_name=result.suggested_name,
        reason=result.reason,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/api/patterns")
async def list_patterns():
    """List all valid branch naming patterns."""
    return {
        "valid_patterns": [
            {"pattern": pattern, "category": category}
            for pattern, category in VALID_PATTERNS
        ],
        "protected_branches": PROTECTED_BRANCHES,
        "rename_suggestions": [
            {"pattern": pattern, "suggestion": suggestion}
            for pattern, suggestion in RENAME_SUGGESTIONS.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=True
    )
