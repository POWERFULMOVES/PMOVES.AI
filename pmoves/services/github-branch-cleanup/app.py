"""GitHub Branch Cleanup Service

Automatically removes stale branches across POWERFULMOVES repositories.
Integrates with BoTZ MCP Gateway for GitHub operations.
Publishes events to NATS for observability.

Port: 8100
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import nats
from nats.aio.client import Client as NATS
import httpx
from prometheus_client import Counter, Histogram, Gauge, generate_latest

from .config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("github-branch-cleanup")

# Prometheus Metrics
branches_stale_total = Counter(
    'github_branch_cleanup_stale_total',
    'Total number of stale branches detected',
    ['repo']
)

branches_deleted_total = Counter(
    'github_branch_cleanup_deleted_total',
    'Total number of branches deleted',
    ['repo']
)

branches_protected_skipped_total = Counter(
    'github_branch_cleanup_protected_skipped_total',
    'Total number of protected branches skipped',
    ['repo']
)

cleanup_duration_seconds = Histogram(
    'github_branch_cleanup_duration_seconds',
    'Branch cleanup operation duration',
    ['repo', 'status']
)

active_operations = Gauge(
    'github_branch_cleanup_active_operations',
    'Number of active cleanup operations'
)

# Global state
nc: Optional[NATS] = None
http_client: Optional[httpx.AsyncClient] = None


# Pydantic models
class StaleBranch(BaseModel):
    """Represents a stale branch."""
    name: str
    last_commit_date: datetime
    stale_days: int
    repo: str


class CleanupRequest(BaseModel):
    """Request to trigger branch cleanup."""
    repo: str = Field(..., description="Repository name (e.g., PMOVES.AI)")
    dry_run: bool = Field(
        default=True,
        description="If true, only report what would be deleted"
    )
    stale_days: int = Field(
        default=30,
        description="Days of inactivity to consider branch stale"
    )


class CleanupResult(BaseModel):
    """Result of branch cleanup operation."""
    repo: str
    stale_branches: List[StaleBranch]
    deleted_branches: List[str]
    protected_skipped: List[str]
    dry_run: bool
    duration_seconds: float


class BranchListResponse(BaseModel):
    """Response listing stale branches."""
    repo: str
    stale_branches: List[StaleBranch]
    total_stale: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global nc, http_client

    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise

    # Initialize HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)

    # Connect to NATS
    try:
        nc = await nats.connect(config.NATS_URL)
        logger.info(f"Connected to NATS at {config.NATS_URL}")

        # Subscribe to webhook events
        await nc.subscribe(
            "github.webhook.pr.v1",
            "branch-cleanup",
            handle_pr_webhook
        )
        logger.info("Subscribed to github.webhook.pr.v1")

    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        raise

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
    title="GitHub Branch Cleanup Service",
    description="Automatically removes stale branches from POWERFULMOVES repositories",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/healthz")
async def health_check():
    """Health check endpoint for Docker."""
    return {"status": "healthy", "service": "github-branch-cleanup"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


async def get_github_token() -> str:
    """Mint GitHub App installation token via Agent Zero MCP.

    Returns:
        JWT token for GitHub App authentication

    Raises:
        HTTPException: If token minting fails
    """
    try:
        response = await http_client.post(
            f"{config.AGENTZERO_MCP_URL}/tools/github_mint_token",
            json={
                "app_id": config.GITHUB_APP_ID,
                "installation_id": config.GITHUB_APP_INSTALLATION_ID
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["token"]
    except Exception as e:
        logger.error(f"Failed to mint GitHub token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mint GitHub token: {e}")


async def get_branches(repo: str) -> List[Dict[str, Any]]:
    """Get all branches from repository.

    Args:
        repo: Repository name (e.g., PMOVES.AI)

    Returns:
        List of branch information from GitHub API
    """
    token = await get_github_token()

    response = await http_client.get(
        f"https://api.github.com/repos/{config.GITHUB_ORG}/{repo}/branches",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    )
    response.raise_for_status()
    return response.json()


async def get_branch_commit_date(repo: str, branch_name: str) -> Optional[datetime]:
    """Get last commit date for a branch.

    Args:
        repo: Repository name
        branch_name: Branch name

    Returns:
        Last commit datetime or None if not found
    """
    token = await get_github_token()

    try:
        response = await http_client.get(
            f"https://api.github.com/repos/{config.GITHUB_ORG}/{repo}/branches/{branch_name}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
        )
        response.raise_for_status()
        data = response.json()

        # Parse commit date
        commit_date_str = data["commit"]["commit"]["committer"]["date"]
        return datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
    except Exception as e:
        logger.warning(f"Failed to get commit date for {branch_name}: {e}")
        return None


async def delete_branch(repo: str, branch_name: str) -> bool:
    """Delete a branch via GitHub API.

    Args:
        repo: Repository name
        branch_name: Branch to delete

    Returns:
        True if deleted successfully
    """
    token = await get_github_token()

    try:
        response = await http_client.delete(
            f"https://api.github.com/repos/{config.GITHUB_ORG}/{repo}/git/refs/heads/{branch_name}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to delete branch {branch_name}: {e}")
        return False


def is_stale(last_commit_date: datetime, stale_days: int) -> bool:
    """Check if branch is stale based on last commit date.

    Args:
        last_commit_date: Last commit datetime
        stale_days: Days threshold for staleness

    Returns:
        True if branch is stale
    """
    threshold = datetime.now(timezone.utc) - timedelta(days=stale_days)
    return last_commit_date < threshold


async def get_stale_branches(repo: str, stale_days: int) -> List[StaleBranch]:
    """Get list of stale branches in repository.

    Args:
        repo: Repository name
        stale_days: Days threshold for staleness

    Returns:
        List of StaleBranch objects
    """
    branches = await get_branches(repo)
    stale_branches: List[StaleBranch] = []

    for branch_data in branches:
        branch_name = branch_data["name"]

        # Skip protected branches
        if config.is_protected_branch(branch_name):
            logger.debug(f"Skipping protected branch: {branch_name}")
            branches_protected_skipped_total.labels(repo=repo).inc()
            continue

        # Get last commit date
        commit_date = await get_branch_commit_date(repo, branch_name)
        if not commit_date:
            continue

        # Check if stale
        if is_stale(commit_date, stale_days):
            stale_days_count = (datetime.now(timezone.utc) - commit_date).days
            stale_branch = StaleBranch(
                name=branch_name,
                last_commit_date=commit_date,
                stale_days=stale_days_count,
                repo=repo
            )
            stale_branches.append(stale_branch)
            branches_stale_total.labels(repo=repo).inc()

    return stale_branches


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


@app.get("/api/stale-branches", response_model=BranchListResponse)
async def list_stale_branches(
    repo: str,
    days: int = 30
) -> BranchListResponse:
    """List stale branches in repository.

    Args:
        repo: Repository name (e.g., PMOVES.AI)
        days: Days threshold for staleness (default: 30)

    Returns:
        BranchListResponse with stale branches
    """
    try:
        stale_branches = await get_stale_branches(repo, days)

        await publish_nats_event("github.branch.stale_detected.v1", {
            "repo": repo,
            "stale_count": len(stale_branches),
            "stale_days": days,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        return BranchListResponse(
            repo=repo,
            stale_branches=stale_branches,
            total_stale=len(stale_branches)
        )
    except Exception as e:
        logger.error(f"Failed to list stale branches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cleanup", response_model=CleanupResult)
async def cleanup_stale_branches(
    request: CleanupRequest,
    background_tasks: BackgroundTasks
) -> CleanupResult:
    """Cleanup stale branches from repository.

    Args:
        request: Cleanup request with repo, dry_run, and stale_days

    Returns:
        CleanupResult with operation details
    """
    active_operations.inc()
    start_time = datetime.now(timezone.utc)

    try:
        logger.info(f"Starting branch cleanup for {request.repo} (dry_run={request.dry_run})")

        # Get stale branches
        stale_branches = await get_stale_branches(request.repo, request.stale_days)

        deleted_branches: List[str] = []
        protected_skipped: List[str] = []

        for branch in stale_branches:
            # Check if protected
            if config.is_protected_branch(branch.name):
                protected_skipped.append(branch.name)
                logger.debug(f"Skipping protected branch: {branch.name}")
                continue

            # Delete branch (or simulate if dry_run)
            if request.dry_run:
                logger.info(f"[DRY RUN] Would delete branch: {branch.name}")
                deleted_branches.append(branch.name)
            else:
                success = await delete_branch(request.repo, branch.name)
                if success:
                    deleted_branches.append(branch.name)
                    branches_deleted_total.labels(repo=request.repo).inc()
                    logger.info(f"Deleted branch: {branch.name}")

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        result = CleanupResult(
            repo=request.repo,
            stale_branches=stale_branches,
            deleted_branches=deleted_branches,
            protected_skipped=protected_skipped,
            dry_run=request.dry_run,
            duration_seconds=duration
        )

        # Publish completion event
        await publish_nats_event("github.branch.deleted.v1", {
            "repo": request.repo,
            "deleted_count": len(deleted_branches),
            "dry_run": request.dry_run,
            "duration_seconds": duration,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        cleanup_duration_seconds.labels(
            repo=request.repo,
            status="success"
        ).observe(duration)

        logger.info(
            f"Cleanup completed: {len(deleted_branches} deleted, "
            f"{len(protected_skipped)} protected skipped, "
            f"duration={duration:.2f}s"
        )

        return result

    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        cleanup_duration_seconds.labels(
            repo=request.repo,
            status="error"
        ).observe(duration)

        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_operations.dec()


async def handle_pr_webhook(msg):
    """Handle PR closed webhook from NATS.

    Triggered when a PR is closed/merged. Checks if source branch should be deleted.

    Args:
        msg: NATS message with webhook payload
    """
    try:
        import json
        data = json.loads(msg.data.decode())

        repo = data.get("repository", {}).get("name", "")
        action = data.get("action", "")
        pr = data.get("pull_request", {})

        # Only process closed/merged PRs
        if action not in ["closed", "merged"]:
            return

        # Get branch name
        branch = pr.get("head", {}).get("ref", "")
        if not branch:
            return

        # Check if branch should be auto-deleted
        # (Typically: user branches, not release/main)
        if config.is_protected_branch(branch):
            logger.info(f"Branch {branch} is protected, skipping auto-delete")
            return

        # Delete branch (respect DRY_RUN global setting)
        if config.DRY_RUN:
            logger.info(f"[DRY RUN] Would auto-delete branch after PR: {branch}")
        else:
            success = await delete_branch(repo, branch)
            if success:
                branches_deleted_total.labels(repo=repo).inc()
                logger.info(f"Auto-deleted branch after PR: {branch}")

        await publish_nats_event("github.branch.auto_deleted.v1", {
            "repo": repo,
            "branch": branch,
            "trigger": "pr_closed",
            "dry_run": config.DRY_RUN,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error handling PR webhook: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=config.SERVICE_PORT,
        reload=True
    )
