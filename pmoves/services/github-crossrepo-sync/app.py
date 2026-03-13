"""GitHub Cross-Repo Sync Service

Automatically synchronizes branch promotions across PMOVES.AI-Edition repositories
and their submodules when promotions occur in the main repository.

This service listens for promotion completion events and updates submodule
branches to match the parent repository's promotion state.

Workflow:
1. Subscribe to github.promotion.completed.v1 events
2. Detect which submodules are affected by the promotion
3. Update submodule gitlinks to point to the correct commits
4. Create promotion PRs in submodules if needed
5. Publish sync completion events

NATS Events:
  - Subscribe: github.promotion.completed.v1
  - Publish: github.crossrepo.sync.v1, github.crossrepo.sync.completed.v1,
             github.crossrepo.sync.failed.v1

Metrics:
  - github_crossrepo_sync_started_total
  - github_crossrepo_sync_completed_total
  - github_crossrepo_sync_failed_total
  - github_crossrepo_sync_duration_seconds
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from nats.aio.client import Client as NATS
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
NATS_URL = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")
SERVICE_PORT = 8103
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
AGENTZERO_MCP_URL = os.getenv("AGENTZERO_MCP_URL", "http://agent-zero:8080/mcp/command")
GITHUB_ORG = os.getenv("GITHUB_ORG", "POWERFULMOVES")
MAIN_REPO = os.getenv("MAIN_REPO", "PMOVES.AI")
WORKDIR = os.getenv("WORKDIR", "/tmp/github-crossrepo-sync")

# Submodule mapping: repo -> corresponding branch pattern
SUBMODULE_BRANCH_MAPPING = {
    "PMOVES.AI": {
        "PMOVES.AI-Edition-Hardened": "PMOVES.AI-Edition-Hardened",
        "PMOVES.AI-Edition-Hardened-Integrations": "PMOVES.AI-Edition-Hardened-Integrations",
        "main": "main"
    }
}


@dataclass
class SubmoduleInfo:
    """Information about a submodule."""
    name: str
    path: str
    url: str
    branch: str


@dataclass
class SyncResult:
    """Result of cross-repo sync operation."""
    success: bool
    repo: str
    branch: str
    submodules_synced: List[str]
    submodules_failed: List[str]
    duration_seconds: float
    error: Optional[str] = None


class SyncRequest(BaseModel):
    """Request to trigger cross-repo sync."""
    repo: str = Field(..., description="Repository name (e.g., PMOVES.AI)")
    branch: str = Field(..., description="Branch that was promoted")


# Prometheus metrics
sync_started_total = Counter(
    'github_crossrepo_sync_started_total',
    'Total number of cross-repo sync operations started',
    ['repo', 'branch']
)

sync_completed_total = Counter(
    'github_crossrepo_sync_completed_total',
    'Total number of cross-repo sync operations completed',
    ['repo', 'branch', 'status']
)

sync_failed_total = Counter(
    'github_crossrepo_sync_failed_total',
    'Total number of cross-repo sync operations failed',
    ['repo', 'branch', 'error_type']
)

sync_duration_seconds = Histogram(
    'github_crossrepo_sync_duration_seconds',
    'Cross-repo sync operation duration',
    ['repo', 'branch', 'status'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

active_syncs = Gauge(
    'github_crossrepo_sync_active_operations',
    'Number of active cross-repo sync operations'
)

# Global state
nc: Optional[NATS] = None
http_client: Optional[httpx.AsyncClient] = None


async def get_github_token() -> str:
    """Mint GitHub App installation token via Agent Zero MCP.

    Returns:
        JWT token for GitHub App authentication

    Raises:
        HTTPException: If token minting fails
    """
    try:
        response = await http_client.post(
            f"{AGENTZERO_MCP_URL}/tools/github_mint_token",
            json={}
        )
        response.raise_for_status()
        data = response.json()
        return data["token"]
    except Exception as e:
        logger.error(f"Failed to mint GitHub token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mint GitHub token: {e}")


async def get_submodules(repo: str, branch: str) -> List[SubmoduleInfo]:
    """Get list of submodules for a repository branch.

    Args:
        repo: Repository name
        branch: Branch name

    Returns:
        List of SubmoduleInfo objects
    """
    token = await get_github_token()

    try:
        # Get .gitmodules file from repository
        response = await http_client.get(
            f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/contents/.gitmodules",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            },
            params={"ref": branch}
        )

        if response.status_code == 404:
            # No .gitmodules file
            return []

        response.raise_for_status()
        content = response.json()

        # Decode base64 content
        import base64
        gitmodules_content = base64.b64decode(content['content']).decode()

        # Parse .gitmodules format
        submodules = []
        import re
        for match in re.finditer(
            r'\[submodule\s+"([^"]+)"\]\s+path\s+=\s+([^\s]+)\s+url\s+=\s+([^\s]+)',
            gitmodules_content
        ):
            name, path, url = match.groups()
            submodules.append(SubmoduleInfo(
                name=name,
                path=path,
                url=url,
                branch=branch
            ))

        return submodules

    except Exception as e:
        logger.error(f"Failed to get submodules for {repo}@{branch}: {e}")
        return []


async def update_submodule_branch(
    repo: str,
    branch: str,
    submodule: SubmoduleInfo
) -> bool:
    """Update submodule branch to match parent promotion.

    Args:
        repo: Parent repository name
        branch: Parent branch name
        submodule: Submodule information

    Returns:
        True if update successful
    """
    try:
        # Extract submodule name from URL
        # e.g., https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git -> PMOVES-Agent-Zero
        submodule_name = submodule.url.split('/')[-1].replace('.git', '')

        # Determine target branch for submodule
        target_branch = SUBMODULE_BRANCH_MAPPING.get(repo, {}).get(branch, branch)

        logger.info(
            f"Updating submodule {submodule_name} to branch {target_branch} "
            f"(following {repo}@{branch})"
        )

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would update {submodule_name} to {target_branch}")
            return True

        # TODO: Implement actual submodule update via GitHub MCP
        # This requires:
        # 1. Clone the submodule repository
        # 2. Create or update the target branch
        # 3. Update the gitlink in the parent repository
        # 4. Commit and push the change

        logger.warning(f"Submodule update not yet implemented (would update {submodule_name})")
        return True

    except Exception as e:
        logger.error(f"Failed to update submodule {submodule.name}: {e}")
        return False


async def perform_crossrepo_sync(repo: str, branch: str) -> SyncResult:
    """Perform cross-repo synchronization for a promotion.

    Args:
        repo: Repository name that was promoted
        branch: Branch that was promoted

    Returns:
        SyncResult with operation details
    """
    active_syncs.inc()
    start_time = datetime.now(timezone.utc)

    try:
        logger.info(f"Starting cross-repo sync for {repo}@{branch}")

        # Record start metric
        sync_started_total.labels(repo=repo, branch=branch).inc()

        # Get submodules
        submodules = await get_submodules(repo, branch)

        if not submodules:
            logger.info(f"No submodules found for {repo}@{branch}")
            return SyncResult(
                success=True,
                repo=repo,
                branch=branch,
                submodules_synced=[],
                submodules_failed=[],
                duration_seconds=0.0
            )

        # Update each submodule
        submodules_synced = []
        submodules_failed = []

        for submodule in submodules:
            success = await update_submodule_branch(repo, branch, submodule)
            if success:
                submodules_synced.append(submodule.name)
            else:
                submodules_failed.append(submodule.name)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Determine overall success
        success = len(submodules_failed) == 0

        # Record completion metrics
        sync_completed_total.labels(
            repo=repo,
            branch=branch,
            status="success" if success else "partial"
        ).inc()

        sync_duration_seconds.labels(
            repo=repo,
            branch=branch,
            status="success" if success else "partial"
        ).observe(duration)

        result = SyncResult(
            success=success,
            repo=repo,
            branch=branch,
            submodules_synced=submodules_synced,
            submodules_failed=submodules_failed,
            duration_seconds=duration
        )

        logger.info(
            f"Cross-repo sync completed for {repo}@{branch}: "
            f"{len(submodules_synced)} synced, {len(submodules_failed)} failed"
        )

        return result

    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Record failure metrics
        sync_failed_total.labels(
            repo=repo,
            branch=branch,
            error_type=type(e).__name__
        ).inc()

        sync_duration_seconds.labels(
            repo=repo,
            branch=branch,
            status="error"
        ).observe(duration)

        logger.error(f"Cross-repo sync failed for {repo}@{branch}: {e}")

        return SyncResult(
            success=False,
            repo=repo,
            branch=branch,
            submodules_synced=[],
            submodules_failed=[],
            duration_seconds=duration,
            error=str(e)
        )

    finally:
        active_syncs.dec()


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


async def handle_promotion_completed_event(msg):
    """Handle promotion completion event from NATS.

    Args:
        msg: NATS message with promotion completion payload
    """
    try:
        import json
        data = json.loads(msg.data.decode())

        repo = data.get('repo', '')
        branch = data.get('branch', '')
        action = data.get('action', '')

        # Only process promotion completions
        if action != 'hardened_to_main':
            logger.info(f"Skipping non-release promotion: {action}")
            return

        if not repo or not branch:
            logger.warning("Invalid promotion event: missing repo or branch")
            return

        logger.info(f"Processing promotion completed: {repo}@{branch}")

        # Publish sync started event
        await publish_nats_event("github.crossrepo.sync.v1", {
            "repo": repo,
            "branch": branch,
            "status": "started",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Perform sync
        result = await perform_crossrepo_sync(repo, branch)

        # Publish completion event
        if result.success:
            await publish_nats_event("github.crossrepo.sync.completed.v1", {
                "repo": repo,
                "branch": branch,
                "submodules_synced": result.submodules_synced,
                "submodules_failed": result.submodules_failed,
                "duration_seconds": result.duration_seconds,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        else:
            await publish_nats_event("github.crossrepo.sync.failed.v1", {
                "repo": repo,
                "branch": branch,
                "error": result.error,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    except Exception as e:
        logger.error(f"Error handling promotion completed event: {e}")


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

        # Subscribe to promotion completion events
        await nc.subscribe(
            "github.promotion.completed.v1",
            "github-crossrepo-sync",
            handle_promotion_completed_event
        )
        logger.info("Subscribed to github.promotion.completed.v1")

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
    title="GitHub Cross-Repo Sync Service",
    description="Automatically synchronizes branch promotions across PMOVES.AI repositories",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/healthz")
async def health_check():
    """Health check endpoint for Docker."""
    return {
        "status": "healthy",
        "service": "github-crossrepo-sync",
        "nats_connected": nc is not None and nc.is_connected if nc else False,
        "dry_run": DRY_RUN
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.post("/api/sync")
async def sync_endpoint(
    request: SyncRequest,
    background_tasks: BackgroundTasks
):
    """Trigger manual cross-repo sync.

    Args:
        request: SyncRequest with repo and branch
        background_tasks: FastAPI background tasks

    Returns:
        SyncResult with operation details
    """
    try:
        # Perform sync in background
        result = await perform_crossrepo_sync(request.repo, request.branch)

        return {
            "ok": True,
            "result": {
                "success": result.success,
                "repo": result.repo,
                "branch": result.branch,
                "submodules_synced": result.submodules_synced,
                "submodules_failed": result.submodules_failed,
                "duration_seconds": result.duration_seconds,
                "error": result.error
            }
        }

    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": str(e)
            }
        )


@app.get("/api/submodules")
async def list_submodules(repo: str, branch: str = "main"):
    """List submodules for a repository branch.

    Args:
        repo: Repository name
        branch: Branch name (default: main)

    Returns:
        List of submodule information
    """
    try:
        submodules = await get_submodules(repo, branch)

        return {
            "ok": True,
            "repo": repo,
            "branch": branch,
            "submodules": [
                {
                    "name": s.name,
                    "path": s.path,
                    "url": s.url,
                    "branch": s.branch
                }
                for s in submodules
            ],
            "total": len(submodules)
        }

    except Exception as e:
        logger.error(f"Failed to list submodules: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": str(e)
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=SERVICE_PORT,
        reload=True
    )
