"""GitHub Cross-Repository PR Automation Service

Automates pull request creation and management across multiple PMOVES.AI
repositories for dependency updates, security patches, and feature backports.

This service listens for cross-repo sync completion events and automatically
creates pull requests in affected repositories using workflow templates.

NATS Events:
  - Subscribe: github.crossrepo.sync.completed.v1
  - Publish: github.crossrepo.pr.created.v1, github.crossrepo.pr.merged.v1

API Endpoints:
  - GET /healthz - Health check
  - GET /metrics - Prometheus metrics
  - GET /api/templates - List workflow templates
  - POST /api/pr/create - Create PR from template
  - POST /api/pr/batch - Batch create PRs across repos

Metrics:
  - github_crossrepo_pr_created_total
  - github_crossrepo_pr_merged_total
  - github_crossrepo_pr_failed_total
  - github_crossrepo_pr_duration_seconds
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from nats.aio.client import Client as NATS

from workflow_templates import (
    PRType,
    get_template,
    list_templates,
    PRWorkflowTemplate
)
from agentzero_client import AgentZeroMCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
NATS_URL = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8104"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
AGENTZERO_MCP_URL = os.getenv("AGENTZERO_MCP_URL", "http://agent-zero:8080/mcp/command")
GITHUB_ORG = os.getenv("GITHUB_ORG", "POWERFULMOVES")

# Repository configuration
REPO_CONFIG = {
    "default_base_branch": "main",
    "protected_branches": [
        "main",
        "PMOVES.AI-Edition-Hardened",
        "PMOVES.AI-Edition-Hardened-Integrations"
    ],
    "auto_merge_enabled_repos": os.getenv("AUTO_MERGE_REPOS", "").split(","),
}


@dataclass
class PRCreateRequest:
    """Request to create a pull request."""
    pr_type: PRType
    repo: str
    base_branch: str
    template_vars: Dict[str, Any]
    organization: str = GITHUB_ORG


@dataclass
class PRBatchRequest:
    """Request to batch create PRs across multiple repos."""
    pr_type: PRType
    repos: List[str]
    base_branch: str
    template_vars: Dict[str, Any]
    organization: str = GITHUB_ORG


@dataclass
class PRCreateResult:
    """Result of PR creation."""
    success: bool
    repo: str
    pr_number: Optional[int]
    pr_url: Optional[str]
    error: Optional[str]
    duration_seconds: float


class PRCreationRequest(BaseModel):
    """API request for PR creation."""
    pr_type: str = Field(..., description="Type of PR (dependency_update, security_patch, etc.)")
    repo: str = Field(..., description="Repository name")
    base_branch: str = Field(default="main", description="Target branch")
    template_vars: Dict[str, Any] = Field(..., description="Template variables")
    organization: str = Field(default=GITHUB_ORG, description="GitHub organization")


class PRBatchCreationRequest(BaseModel):
    """API request for batch PR creation."""
    pr_type: str = Field(..., description="Type of PR")
    repos: List[str] = Field(..., description="List of repositories")
    base_branch: str = Field(default="main", description="Target branch")
    template_vars: Dict[str, Any] = Field(..., description="Template variables")
    organization: str = Field(default=GITHUB_ORG, description="GitHub organization")


# Prometheus metrics
pr_created_total = Counter(
    'github_crossrepo_pr_created_total',
    'Total number of cross-repo PRs created',
    ['pr_type', 'repo', 'status']
)

pr_merged_total = Counter(
    'github_crossrepo_pr_merged_total',
    'Total number of cross-repo PRs merged',
    ['pr_type', 'repo']
)

pr_failed_total = Counter(
    'github_crossrepo_pr_failed_total',
    'Total number of cross-repo PR creation failures',
    ['pr_type', 'repo', 'error_type']
)

pr_duration_seconds = Histogram(
    'github_crossrepo_pr_duration_seconds',
    'Cross-repo PR creation duration',
    ['pr_type', 'repo', 'status'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

active_operations = Gauge(
    'github_crossrepo_pr_active_operations',
    'Number of active cross-repo PR operations'
)

# Global state
nc: Optional[NATS] = None
mcp_client: Optional[AgentZeroMCPClient] = None


async def create_pr_from_template(
    pr_type: PRType,
    repo: str,
    base_branch: str,
    template_vars: Dict[str, Any],
    organization: str = GITHUB_ORG
) -> PRCreateResult:
    """Create a pull request from a workflow template.

    Args:
        pr_type: Type of PR to create
        repo: Repository name
        base_branch: Target branch
        template_vars: Variables for template rendering
        organization: GitHub organization

    Returns:
        PRCreateResult with operation details
    """
    active_operations.inc()
    start_time = datetime.now(timezone.utc)

    try:
        logger.info(f"Creating {pr_type.value} PR for {repo}/{base_branch}")

        # Get template
        template = get_template(pr_type)

        # Render template
        title = template.render_title(**template_vars)
        body = template.render_body(**template_vars)
        branch_name = template.render_branch_name(**template_vars)

        # Validate base branch is not protected
        if base_branch in REPO_CONFIG["protected_branches"]:
            # For protected branches, target main instead
            base_branch = "main"

        if DRY_RUN:
            logger.info(
                f"[DRY RUN] Would create PR in {repo}:\n"
                f"  Title: {title}\n"
                f"  Branch: {branch_name} → {base_branch}\n"
                f"  Labels: {template.labels}"
            )
            return PRCreateResult(
                success=True,
                repo=repo,
                pr_number=None,
                pr_url=None,
                error=None,
                duration_seconds=0.0
            )

        # Create PR via Agent Zero MCP
        result = await mcp_client.create_pull_request(
            repo=repo,
            title=title,
            body=body,
            head=branch_name,
            base=base_branch,
            labels=template.labels,
            reviewers=template.reviewers,
            assignees=template.assignees,
            draft=template.draft,
            organization=organization
        )

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        if result.success:
            pr_created_total.labels(
                pr_type=pr_type.value,
                repo=repo,
                status="success"
            ).inc()

            pr_duration_seconds.labels(
                pr_type=pr_type.value,
                repo=repo,
                status="success"
            ).observe(duration)

            logger.info(
                f"Created PR #{result.pr_number} in {repo}: {result.pr_url}"
            )

            return PRCreateResult(
                success=True,
                repo=repo,
                pr_number=result.pr_number,
                pr_url=result.pr_url,
                error=None,
                duration_seconds=duration
            )
        else:
            pr_created_total.labels(
                pr_type=pr_type.value,
                repo=repo,
                status="failed"
            ).inc()

            pr_failed_total.labels(
                pr_type=pr_type.value,
                repo=repo,
                error_type="creation_failed"
            ).inc()

            pr_duration_seconds.labels(
                pr_type=pr_type.value,
                repo=repo,
                status="failed"
            ).observe(duration)

            return PRCreateResult(
                success=False,
                repo=repo,
                pr_number=None,
                pr_url=None,
                error=result.error,
                duration_seconds=duration
            )

    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        logger.error(f"Failed to create PR in {repo}: {e}")

        pr_failed_total.labels(
            pr_type=pr_type.value,
            repo=repo,
            error_type=type(e).__name__
        ).inc()

        return PRCreateResult(
            success=False,
            repo=repo,
            pr_number=None,
            pr_url=None,
            error=str(e),
            duration_seconds=duration
        )

    finally:
        active_operations.dec()


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


async def handle_sync_completed_event(msg):
    """Handle cross-repo sync completion event from NATS.

    Args:
        msg: NATS message with sync completion payload
    """
    try:
        import json
        data = json.loads(msg.data.decode())

        repo = data.get('repo', '')
        branch = data.get('branch', '')
        submodules_synced = data.get('submodules_synced', [])

        if not repo or not branch:
            logger.warning("Invalid sync event: missing repo or branch")
            return

        logger.info(
            f"Processing sync completed for {repo}@{branch}: "
            f"{len(submodules_synced)} submodules synced"
        )

        # For each synced submodule, check if we need to create PRs
        # This is a placeholder - actual logic depends on use case
        for submodule in submodules_synced:
            logger.info(f"Submodule {submodule} synced, checking if PR needed...")

            # TODO: Implement logic to determine if PR creation is needed
            # Examples:
            # - Check if there are dependency updates
            # - Check if there are security patches
            # - Check if there are feature backports needed

    except Exception as e:
        logger.error(f"Error handling sync completed event: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global nc, mcp_client

    # Initialize MCP client
    mcp_client = AgentZeroMCPClient(mcp_url=AGENTZERO_MCP_URL)

    # Connect to NATS
    try:
        nc = NATS()
        await nc.connect(NATS_URL)
        logger.info(f"Connected to NATS at {NATS_URL}")

        # Subscribe to sync completion events
        await nc.subscribe(
            "github.crossrepo.sync.completed.v1",
            "github-crossrepo-pr",
            handle_sync_completed_event
        )
        logger.info("Subscribed to github.crossrepo.sync.completed.v1")

    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        # Continue without NATS - API endpoints still work

    yield

    # Cleanup
    try:
        if nc:
            await nc.close()
        if mcp_client:
            await mcp_client.close()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


# FastAPI app
app = FastAPI(
    title="GitHub Cross-Repository PR Automation Service",
    description="Automates PR creation across PMOVES.AI repositories",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/healthz")
async def health_check():
    """Health check endpoint for Docker."""
    return {
        "status": "healthy",
        "service": "github-crossrepo-pr",
        "nats_connected": nc is not None and nc.is_connected if nc else False,
        "dry_run": DRY_RUN
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.get("/api/templates")
async def list_workflow_templates():
    """List all available workflow templates."""
    try:
        templates = list_templates()
        return {
            "ok": True,
            "templates": templates,
            "total": len(templates)
        }
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "Internal server error listing templates"
            }
        )


@app.post("/api/pr/create")
async def create_pr_endpoint(request: PRCreationRequest):
    """Create a pull request from a workflow template.

    Args:
        request: PRCreationRequest with PR details

    Returns:
        PRCreateResult with operation details
    """
    try:
        # Parse PR type
        try:
            pr_type = PRType(request.pr_type)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": f"Invalid PR type: {request.pr_type}. "
                            f"Valid types: {[t.value for t in PRType]}"
                }
            )

        # Create PR
        result = await create_pr_from_template(
            pr_type=pr_type,
            repo=request.repo,
            base_branch=request.base_branch,
            template_vars=request.template_vars,
            organization=request.organization
        )

        # Publish NATS event
        if result.success:
            await publish_nats_event("github.crossrepo.pr.created.v1", {
                "repo": request.repo,
                "pr_number": result.pr_number,
                "pr_url": result.pr_url,
                "pr_type": request.pr_type,
                "base_branch": request.base_branch,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        return {
            "ok": result.success,
            "result": {
                "success": result.success,
                "repo": result.repo,
                "pr_number": result.pr_number,
                "pr_url": result.pr_url,
                "error": result.error,
                "duration_seconds": result.duration_seconds
            }
        }

    except Exception as e:
        logger.error(f"PR creation failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "Internal server error creating PR"
            }
        )


@app.post("/api/pr/batch")
async def create_pr_batch_endpoint(
    request: PRBatchCreationRequest,
    background_tasks: BackgroundTasks
):
    """Batch create pull requests across multiple repositories.

    Args:
        request: PRBatchCreationRequest with batch details
        background_tasks: FastAPI background tasks

    Returns:
        List of PRCreateResult objects
    """
    try:
        # Parse PR type
        try:
            pr_type = PRType(request.pr_type)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": f"Invalid PR type: {request.pr_type}. "
                            f"Valid types: {[t.value for t in PRType]}"
                }
            )

        # Create PRs in all repos
        results = []
        for repo in request.repos:
            result = await create_pr_from_template(
                pr_type=pr_type,
                repo=repo,
                base_branch=request.base_branch,
                template_vars=request.template_vars,
                organization=request.organization
            )
            results.append({
                "repo": result.repo,
                "success": result.success,
                "pr_number": result.pr_number,
                "pr_url": result.pr_url,
                "error": result.error,
                "duration_seconds": result.duration_seconds
            })

        # Publish batch completion event
        successful_count = sum(1 for r in results if r["success"])
        await publish_nats_event("github.crossrepo.pr.batch_completed.v1", {
            "pr_type": request.pr_type,
            "repos": request.repos,
            "successful": successful_count,
            "failed": len(request.repos) - successful_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        return {
            "ok": True,
            "results": results,
            "summary": {
                "total": len(request.repos),
                "successful": successful_count,
                "failed": len(request.repos) - successful_count
            }
        }

    except Exception as e:
        logger.error(f"Batch PR creation failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "Internal server error creating batch PRs"
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=True
    )
