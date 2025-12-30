"""
PMOVES GitHub Runner Controller

FastAPI service for orchestrating self-hosted GitHub Actions runners
across hybrid local-to-cloud infrastructure.

Following PMOVES SDK patterns:
- Standard /healthz and /metrics endpoints
- NATS event publishing with PMOVES envelope format
- Environment-based configuration
- Prometheus metrics integration
- Docker compose profile support

Port: 8100
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

# Local imports
from metrics import (
    API_LATENCY,
    API_REQUESTS_TOTAL,
    RUNNER_UP,
    RUNNER_BUSY,
)
from nats_publisher import NATSPublisher
from github.client import GitHubClient, RunnerMonitor
from github.models import (
    HealthResponse,
    RunnerActionRequest,
    RunnerListResponse,
    RunnerStatus,
    QueueStatus,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("github-runner-ctl")

# Environment configuration (PMOVES pattern: env-based with defaults)
PORT = int(os.environ.get("PORT", 8100))
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
GITHUB_PAT_FILE = os.environ.get("GITHUB_PAT_FILE", "/run/secrets/github_pat")
RUNNERS_CONFIG = os.environ.get("RUNNERS_CONFIG", "/app/config/runners.yaml")
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL_SECONDS", "60"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Set log level
logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

# Global state (set in lifespan)
github_client: Optional[GitHubClient] = None
runner_monitor: Optional[RunnerMonitor] = None
nats_publisher: Optional[NATSPublisher] = None
runner_configs: Dict[str, Dict[str, Any]] = {}
_refresh_task: Optional[asyncio.Task] = None


def load_runner_configs(config_path: str) -> Dict[str, Dict[str, Any]]:
    """Load runner configurations from YAML file.

    Args:
        config_path: Path to runners.yaml config file

    Returns:
        Dictionary of runner configurations
    """
    try:
        import yaml

        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Runner config not found: {config_path}, using defaults")
            return {}

        with open(path) as f:
            data = yaml.safe_load(f)

        runners = {}
        for name, config in data.get("runners", {}).items():
            runners[name] = {
                "name": name,
                "location": config.get("location", "unknown"),
                "labels": config.get("labels", []),
                "capabilities": config.get("capabilities", {}),
                "workloads": config.get("workloads", []),
                "health_url": config.get("health_url"),
            }

        logger.info(f"Loaded {len(runners)} runner configurations from {config_path}")
        return runners

    except ImportError:
        logger.warning("PyYAML not installed, using empty runner config")
        return {}
    except Exception as e:
        logger.error(f"Failed to load runner config: {e}")
        return {}


async def check_runner_health(runner_name: str, health_url: str) -> bool:
    """Check health of a runner via its health endpoint.

    Args:
        runner_name: Name of the runner
        health_url: Health check URL

    Returns:
        True if runner is healthy
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{health_url}/healthz")
            is_healthy = response.status_code == 200

            # Update Prometheus metrics
            location = runner_configs.get(runner_name, {}).get("location", "unknown")
            RUNNER_UP.labels(runner=runner_name, location=location).set(1 if is_healthy else 0)

            return is_healthy
    except Exception as e:
        logger.debug(f"Health check failed for {runner_name}: {e}")
        location = runner_configs.get(runner_name, {}).get("location", "unknown")
        RUNNER_UP.labels(runner=runner_name, location=location).set(0)
        return False


async def refresh_runner_status():
    """Background task to refresh runner status periodically."""
    while True:
        try:
            start = time.time()

            # Refresh status from GitHub API
            if runner_monitor:
                results = await runner_monitor.refresh_all()

                # Update Prometheus metrics
                for runner in results.get("runners", []):
                    name = runner["name"]
                    location = runner_configs.get(name, {}).get("location", runner.get("source", "unknown"))
                    RUNNER_UP.labels(runner=name, location=location).set(1)
                    RUNNER_BUSY.labels(runner=name, location=location).set(1 if runner["status"] == "busy" else 0)

                    # Publish NATS event for busy runners
                    if runner["status"] == "busy" and nats_publisher:
                        await nats_publisher.publish_job_event(
                            "started",
                            name,
                            runner.get("source", "unknown"),
                        )

                logger.info(
                    f"Runner status refreshed: {results['online']} online, "
                    f"{results['busy']} busy, {results['offline']} offline "
                    f"({time.time() - start:.2f}s)"
                )

            # Check health of configured runners with health URLs
            for name, config in runner_configs.items():
                if config.get("health_url"):
                    is_healthy = await check_runner_health(name, config["health_url"])
                    if not is_healthy and nats_publisher:
                        await nats_publisher.publish_alert(
                            "unreachable",
                            name,
                            f"Runner {name} health check failed",
                            severity="warning",
                        )

        except Exception as e:
            logger.error(f"Failed to refresh runner status: {e}")

        await asyncio.sleep(REFRESH_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown.

    Following PMOVES SDK pattern: use asynccontextmanager for lifespan.
    """
    global github_client, runner_monitor, nats_publisher, runner_configs, _refresh_task

    logger.info("Starting GitHub Runner Controller...")

    # Load runner configurations
    runner_configs = load_runner_configs(RUNNERS_CONFIG)

    # Initialize NATS publisher (non-blocking during startup)
    try:
        nats_publisher = NATSPublisher(NATS_URL)
        # Try to connect with a short timeout during startup
        connected = await asyncio.wait_for(
            nats_publisher.connect(retry=False),
            timeout=2.0
        )
        if connected:
            logger.info(f"NATS publisher connected to {NATS_URL}")
        else:
            logger.warning(f"NATS connection failed, will retry in background")
    except asyncio.TimeoutError:
        logger.warning(f"NATS connection timed out, will retry in background")
    except Exception as e:
        logger.warning(f"NATS connection failed: {e} (continuing without NATS)")
        nats_publisher = None

    # Initialize GitHub client
    github_client = GitHubClient(
        pat_file=GITHUB_PAT_FILE,
        nats_publisher=nats_publisher,
    )

    # Initialize runner monitor with configured repos
    monitored_repos = []
    for name, config in runner_configs.items():
        if "repositories" in config:
            monitored_repos.extend(config["repositories"])

    # Add default repos from environment
    if repos := os.environ.get("GITHUB_REPOSITORIES", ""):
        monitored_repos.extend([r.strip() for r in repos.split(",")])

    if monitored_repos:
        runner_monitor = RunnerMonitor(
            github_client=github_client,
            runners=monitored_repos,
            nats_publisher=nats_publisher,
        )
        logger.info(f"Monitoring {len(monitored_repos)} repositories")

        # Start background refresh task
        _refresh_task = asyncio.create_task(refresh_runner_status())
    else:
        logger.warning("No repositories configured for monitoring")

    logger.info(f"GitHub Runner Controller started on port {PORT}")
    yield

    # Shutdown
    logger.info("Shutting down GitHub Runner Controller...")
    if _refresh_task:
        _refresh_task.cancel()
        try:
            await _refresh_task
        except asyncio.CancelledError:
            pass
    if github_client:
        await github_client.close()
    if nats_publisher:
        await nats_publisher.close()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="PMOVES GitHub Runner Controller",
    description="Orchestration service for self-hosted GitHub Actions runners",
    version="1.0.0",
    lifespan=lifespan,
)


# Health check endpoint (PMOVES SDK pattern)
@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Check service health and connectivity.

    Following PMOVES pattern: return {ok, time, ...} structure.
    """
    return HealthResponse(
        ok=True,
        time=int(time.time()),
        nats_connected=nats_publisher.is_connected if nats_publisher else False,
        runners_monitored=len(runner_configs),
        github_connected=github_client.is_authenticated if github_client else False,
    )


# Prometheus metrics endpoint (PMOVES SDK pattern)
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint.

    Following PMOVES pattern: use prometheus_client generate_latest().
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# API Routes

@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "PMOVES GitHub Runner Controller",
        "version": "1.0.0",
        "status": "running",
        "documentation": "/docs",
    }


@app.get("/runners", response_model=RunnerListResponse)
async def list_runners():
    """List all configured runners with their status.

    Returns:
        Runner list with status summary
    """
    start = time.time()
    try:
        runners = []
        online = 0
        busy = 0

        for name, config in runner_configs.items():
            location = config.get("location", "unknown")
            runners.append(
                RunnerStatus(
                    name=name,
                    location=location,
                    status="online",  # TODO: Query actual status
                    busy=False,
                    queue_depth=0,
                    capabilities=config.get("capabilities", {}),
                )
            )

        # Also include runners from GitHub API if available
        if runner_monitor:
            results = await runner_monitor.refresh_all()
            for runner in results.get("runners", []):
                runners.append(
                    RunnerStatus(
                        name=runner["name"],
                        location=runner.get("source", "unknown"),
                        status=runner["status"],
                        busy=runner["status"] == "busy",
                        queue_depth=0,
                    )
                )
                online = results.get("online", 0)
                busy = results.get("busy", 0)

        API_REQUESTS_TOTAL.labels(endpoint="/runners", status="200").inc()
        API_LATENCY.labels(endpoint="/runners").observe(time.time() - start)

        return RunnerListResponse(
            runners=runners,
            total=len(runners),
            online=online,
            busy=busy,
        )

    except Exception as e:
        logger.error(f"Failed to list runners: {e}")
        API_REQUESTS_TOTAL.labels(endpoint="/runners", status="500").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runners/{runner_name}")
async def get_runner_status(runner_name: str):
    """Get detailed status for a specific runner.

    Args:
        runner_name: Name of the runner

    Returns:
        Runner status details
    """
    start = time.time()
    try:
        if runner_name not in runner_configs:
            raise HTTPException(status_code=404, detail=f"Runner {runner_name} not found")

        config = runner_configs[runner_name]
        status = {
            "name": runner_name,
            "location": config.get("location"),
            "labels": config.get("labels", []),
            "capabilities": config.get("capabilities", {}),
            "workloads": config.get("workloads", []),
            "status": "online",  # TODO: Query actual status
        }

        API_REQUESTS_TOTAL.labels(endpoint="/runners/{runner_name}", status="200").inc()
        API_LATENCY.labels(endpoint="/runners/{runner_name}").observe(time.time() - start)

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get runner {runner_name}: {e}")
        API_REQUESTS_TOTAL.labels(endpoint="/runners/{runner_name}", status="500").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/runners/{runner_name}/action")
async def runner_action(runner_name: str, request: RunnerActionRequest):
    """Perform an action on a runner (enable, disable, restart).

    Args:
        runner_name: Name of the runner
        request: Action request

    Returns:
        Action result
    """
    start = time.time()
    try:
        if runner_name not in runner_configs:
            raise HTTPException(status_code=404, detail=f"Runner {runner_name} not found")

        action = request.action
        if action not in {"enable", "disable", "restart"}:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

        # Publish NATS event
        if nats_publisher:
            await nats_publisher.publish_runner_event(
                event_type=f"{action}d" if action != "restart" else "restarted",
                runner=runner_name,
                data={"reason": request.reason or "Manual action via API"},
            )

        # TODO: Implement actual runner control logic
        result = {
            "runner": runner_name,
            "action": action,
            "status": "success",
            "message": f"Action '{action}' queued for {runner_name}",
        }

        API_REQUESTS_TOTAL.labels(endpoint="/runners/{runner}/action", status="200").inc()
        API_LATENCY.labels(endpoint="/runners/{runner}/action").observe(time.time() - start)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform action on {runner_name}: {e}")
        API_REQUESTS_TOTAL.labels(endpoint="/runners/{runner}/action", status="500").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue/{repository}")
async def get_queue_status(repository: str):
    """Get queue status for a specific repository.

    Args:
        repository: Repository in "owner/repo" format

    Returns:
        Queue status with depth and available runners
    """
    start = time.time()
    try:
        if "/" not in repository:
            raise HTTPException(status_code=400, detail="Repository must be in 'owner/repo' format")

        owner, repo = repository.split("/", 1)

        if not github_client:
            raise HTTPException(status_code=503, detail="GitHub client not available")

        status_data = await github_client.get_queue_status(owner, repo)

        status = QueueStatus(
            repository=repository,
            queued_jobs=status_data.get("queued", 0),
            in_progress_jobs=status_data.get("in_progress", 0),
            runners_available=len([r for r in runner_configs.values()
                                   if r.get("location") != "cloud"]),  # Local runners
        )

        # Publish alert if queue is high
        if status.queued_jobs > 10 and nats_publisher:
            await nats_publisher.publish_alert(
                alert_type="queue_backlog",
                runner=repository,
                message=f"Queue backlog: {status.queued_jobs} jobs waiting",
                severity="warning" if status.queued_jobs < 20 else "critical",
                data={"queue_depth": status.queued_jobs},
            )

        API_REQUESTS_TOTAL.labels(endpoint="/queue/{repo}", status="200").inc()
        API_LATENCY.labels(endpoint="/queue/{repo}").observe(time.time() - start)

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get queue status for {repository}: {e}")
        API_REQUESTS_TOTAL.labels(endpoint="/queue/{repo}", status="500").inc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=PORT,
        log_level=LOG_LEVEL.lower(),
    )
