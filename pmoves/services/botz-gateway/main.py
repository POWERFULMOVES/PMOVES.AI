"""
PMOVES-BoTZ Gateway Service

Coordinates work item distribution across BoTZ CLI instances.
Tracks skill levels and capabilities per CLI instance.
Routes work items to appropriate skill-level CLIs.
Integrates with TensorZero for LLM routing.

Port: 8054
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import nats
from nats.aio.client import Client as NATS
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("botz-gateway")

# Environment configuration
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://supabase-kong:8000")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
TENSORZERO_URL = os.getenv("TENSORZERO_URL", "http://tensorzero:3030")
HEARTBEAT_INTERVAL = int(os.getenv("BOTZ_HEARTBEAT_INTERVAL", "30"))
STALE_THRESHOLD_MINUTES = int(os.getenv("BOTZ_STALE_THRESHOLD", "5"))

# Global state
nc: Optional[NATS] = None
supabase_headers: Dict[str, str] = {}


# Pydantic models
class BotzRegistration(BaseModel):
    botz_name: str
    instance_id: str
    skill_level: str = "basic"
    available_mcp_tools: List[str] = Field(default_factory=list)
    available_tac_commands: List[str] = Field(default_factory=list)
    runner_host: Optional[str] = None
    config_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BotzHeartbeat(BaseModel):
    instance_id: str
    is_available: bool = True
    current_work_item_id: Optional[str] = None


class WorkItemClaim(BaseModel):
    work_item_id: str
    botz_id: str
    session_id: Optional[str] = None


class WorkItemComplete(BaseModel):
    work_item_id: str
    botz_id: str
    commit_sha: Optional[str] = None
    pr_url: Optional[str] = None
    files_modified: List[str] = Field(default_factory=list)
    files_created: List[str] = Field(default_factory=list)


class WorkItemFilter(BaseModel):
    integration_name: Optional[str] = None
    skill_level: Optional[str] = None
    priority: Optional[str] = None
    limit: int = 20


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global nc, supabase_headers

    # Setup Supabase headers
    supabase_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    # Connect to NATS
    try:
        nc = await nats.connect(NATS_URL)
        logger.info(f"Connected to NATS at {NATS_URL}")

        # Subscribe to BoTZ events
        await nc.subscribe("botz.heartbeat.v1", cb=handle_heartbeat_event)
        await nc.subscribe("botz.register.v1", cb=handle_register_event)
        logger.info("Subscribed to BoTZ NATS subjects")
    except Exception as e:
        logger.warning(f"NATS connection failed: {e}")
        nc = None

    # Start background task for stale instance cleanup
    cleanup_task = asyncio.create_task(cleanup_stale_instances())

    yield

    # Cleanup
    cleanup_task.cancel()
    if nc:
        await nc.close()
        logger.info("NATS connection closed")


app = FastAPI(
    title="PMOVES-BoTZ Gateway",
    description="Coordinates work item distribution across BoTZ CLI instances",
    version="0.1.0",
    lifespan=lifespan
)


# NATS event handlers
async def handle_heartbeat_event(msg):
    """Handle heartbeat events from BoTZ instances."""
    try:
        import json
        data = json.loads(msg.data.decode())
        await update_heartbeat(data["instance_id"], data.get("is_available", True))
    except Exception as e:
        logger.error(f"Error handling heartbeat: {e}")


async def handle_register_event(msg):
    """Handle registration events from BoTZ instances."""
    try:
        import json
        data = json.loads(msg.data.decode())
        registration = BotzRegistration(**data)
        await register_botz_instance(registration)
    except Exception as e:
        logger.error(f"Error handling registration: {e}")


async def cleanup_stale_instances():
    """Background task to mark stale instances as unavailable."""
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            threshold = datetime.now(timezone.utc) - timedelta(minutes=STALE_THRESHOLD_MINUTES)

            async with httpx.AsyncClient() as client:
                # Mark instances with old heartbeats as unavailable
                response = await client.patch(
                    f"{SUPABASE_URL}/rest/v1/botz_instances",
                    headers=supabase_headers,
                    params={
                        "last_heartbeat": f"lt.{threshold.isoformat()}",
                        "is_available": "eq.true"
                    },
                    json={"is_available": False}
                )
                if response.status_code == 200:
                    updated = response.json()
                    if updated:
                        logger.info(f"Marked {len(updated)} stale instances as unavailable")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")


# Helper functions
async def update_heartbeat(instance_id: str, is_available: bool = True):
    """Update heartbeat timestamp for a BoTZ instance."""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{SUPABASE_URL}/rest/v1/botz_instances",
            headers=supabase_headers,
            params={"instance_id": f"eq.{instance_id}"},
            json={
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "is_available": is_available
            }
        )
        return response.status_code == 200


async def register_botz_instance(registration: BotzRegistration) -> Dict[str, Any]:
    """Register or update a BoTZ instance."""
    async with httpx.AsyncClient() as client:
        # Check if instance exists
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/botz_instances",
            headers=supabase_headers,
            params={"instance_id": f"eq.{registration.instance_id}"}
        )

        existing = response.json() if response.status_code == 200 else []

        data = {
            "botz_name": registration.botz_name,
            "instance_id": registration.instance_id,
            "skill_level": registration.skill_level,
            "available_mcp_tools": registration.available_mcp_tools,
            "available_tac_commands": registration.available_tac_commands,
            "runner_host": registration.runner_host,
            "config_path": registration.config_path,
            "metadata": registration.metadata,
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "is_available": True
        }

        if existing:
            # Update existing
            response = await client.patch(
                f"{SUPABASE_URL}/rest/v1/botz_instances",
                headers=supabase_headers,
                params={"instance_id": f"eq.{registration.instance_id}"},
                json=data
            )
        else:
            # Create new
            data["botz_id"] = str(uuid4())
            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/botz_instances",
                headers=supabase_headers,
                json=data
            )

        if response.status_code in [200, 201]:
            result = response.json()
            return result[0] if result else data
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)


# API Endpoints
@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "healthy", "service": "botz-gateway", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint."""
    # Get stats from Supabase
    stats = {"active_botz": 0, "available_items": 0, "in_progress_items": 0}

    try:
        async with httpx.AsyncClient() as client:
            # Count active BoTZ
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/botz_instances",
                headers={**supabase_headers, "Prefer": "count=exact"},
                params={"is_available": "eq.true"}
            )
            if "content-range" in response.headers:
                stats["active_botz"] = int(response.headers["content-range"].split("/")[1])

            # Count available work items
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/integration_work_items",
                headers={**supabase_headers, "Prefer": "count=exact"},
                params={"status": "eq.ready"}
            )
            if "content-range" in response.headers:
                stats["available_items"] = int(response.headers["content-range"].split("/")[1])

            # Count in-progress items
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/integration_work_items",
                headers={**supabase_headers, "Prefer": "count=exact"},
                params={"status": "eq.in_progress"}
            )
            if "content-range" in response.headers:
                stats["in_progress_items"] = int(response.headers["content-range"].split("/")[1])
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")

    # Format as Prometheus metrics
    metrics_text = f"""# HELP botz_active_instances Number of active BoTZ instances
# TYPE botz_active_instances gauge
botz_active_instances {stats['active_botz']}

# HELP botz_available_work_items Number of work items ready for claiming
# TYPE botz_available_work_items gauge
botz_available_work_items {stats['available_items']}

# HELP botz_in_progress_work_items Number of work items currently being worked on
# TYPE botz_in_progress_work_items gauge
botz_in_progress_work_items {stats['in_progress_items']}
"""
    return JSONResponse(content=metrics_text, media_type="text/plain")


@app.post("/v1/botz/register")
async def register_botz(registration: BotzRegistration):
    """Register a new BoTZ instance."""
    result = await register_botz_instance(registration)

    # Publish to NATS
    if nc:
        import json
        await nc.publish(
            "botz.registered.v1",
            json.dumps({
                "botz_id": result.get("botz_id"),
                "instance_id": registration.instance_id,
                "botz_name": registration.botz_name,
                "skill_level": registration.skill_level
            }).encode()
        )

    return {"status": "registered", "botz": result}


@app.post("/v1/botz/heartbeat")
async def heartbeat(hb: BotzHeartbeat):
    """Update BoTZ heartbeat."""
    success = await update_heartbeat(hb.instance_id, hb.is_available)
    if success:
        return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
    else:
        raise HTTPException(status_code=404, detail="BoTZ instance not found")


@app.get("/v1/botz/instances")
async def list_botz_instances(available_only: bool = False):
    """List all registered BoTZ instances."""
    async with httpx.AsyncClient() as client:
        params = {}
        if available_only:
            params["is_available"] = "eq.true"

        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/botz_instances",
            headers=supabase_headers,
            params=params
        )

        if response.status_code == 200:
            return {"instances": response.json()}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)


@app.get("/v1/botz/{botz_id}")
async def get_botz_instance(botz_id: str):
    """Get details of a specific BoTZ instance."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/botz_instances",
            headers=supabase_headers,
            params={"botz_id": f"eq.{botz_id}"}
        )

        if response.status_code == 200:
            instances = response.json()
            if instances:
                return instances[0]
            raise HTTPException(status_code=404, detail="BoTZ instance not found")
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)


@app.post("/v1/workitems/list")
async def list_work_items(filter: WorkItemFilter):
    """List available work items with optional filters."""
    async with httpx.AsyncClient() as client:
        params = {"status": "eq.ready", "limit": filter.limit, "order": "priority,created_at"}

        if filter.integration_name:
            params["integration_name"] = f"eq.{filter.integration_name}"
        if filter.skill_level:
            params["required_skill_level"] = f"lte.{filter.skill_level}"
        if filter.priority:
            params["priority"] = f"eq.{filter.priority}"

        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/integration_work_items",
            headers=supabase_headers,
            params=params
        )

        if response.status_code == 200:
            return {"work_items": response.json()}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)


@app.post("/v1/workitems/claim")
async def claim_work_item(claim: WorkItemClaim):
    """Claim a work item for a BoTZ instance."""
    async with httpx.AsyncClient() as client:
        # Call the claim function via RPC
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/claim_work_item",
            headers=supabase_headers,
            json={
                "p_work_item_id": claim.work_item_id,
                "p_botz_id": claim.botz_id,
                "p_session_id": claim.session_id
            }
        )

        if response.status_code == 200:
            # Publish claim event to NATS
            if nc:
                import json
                await nc.publish(
                    "botz.workitem.claimed.v1",
                    json.dumps({
                        "work_item_id": claim.work_item_id,
                        "botz_id": claim.botz_id,
                        "session_id": claim.session_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }).encode()
                )

            return {"status": "claimed", "work_item_id": claim.work_item_id}
        else:
            raise HTTPException(status_code=400, detail=response.text)


@app.post("/v1/workitems/complete")
async def complete_work_item(completion: WorkItemComplete):
    """Mark a work item as completed."""
    async with httpx.AsyncClient() as client:
        # Call the complete function via RPC
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/complete_work_item",
            headers=supabase_headers,
            json={
                "p_work_item_id": completion.work_item_id,
                "p_botz_id": completion.botz_id,
                "p_commit_sha": completion.commit_sha,
                "p_pr_url": completion.pr_url,
                "p_files_modified": completion.files_modified,
                "p_files_created": completion.files_created
            }
        )

        if response.status_code == 200:
            # Publish completion event to NATS
            if nc:
                import json
                await nc.publish(
                    "botz.workitem.completed.v1",
                    json.dumps({
                        "work_item_id": completion.work_item_id,
                        "botz_id": completion.botz_id,
                        "commit_sha": completion.commit_sha,
                        "pr_url": completion.pr_url,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }).encode()
                )

            return {"status": "completed", "work_item_id": completion.work_item_id}
        else:
            raise HTTPException(status_code=400, detail=response.text)


@app.get("/v1/workitems/{work_item_id}")
async def get_work_item(work_item_id: str):
    """Get details of a specific work item."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/integration_work_items",
            headers=supabase_headers,
            params={"work_item_id": f"eq.{work_item_id}"}
        )

        if response.status_code == 200:
            items = response.json()
            if items:
                return items[0]
            raise HTTPException(status_code=404, detail="Work item not found")
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)


@app.get("/v1/stats")
async def get_stats():
    """Get BoTZ ecosystem statistics."""
    async with httpx.AsyncClient() as client:
        stats = {
            "botz": {"total": 0, "available": 0, "by_skill": {}},
            "work_items": {"total": 0, "by_status": {}, "by_integration": {}},
            "executions": {"total": 0, "succeeded": 0, "failed": 0}
        }

        try:
            # BoTZ stats
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/botz_stats",
                headers=supabase_headers
            )
            if response.status_code == 200:
                botz_data = response.json()
                stats["botz"]["total"] = len(botz_data)
                stats["botz"]["available"] = sum(1 for b in botz_data if b.get("is_available"))
                for b in botz_data:
                    skill = b.get("skill_level", "unknown")
                    stats["botz"]["by_skill"][skill] = stats["botz"]["by_skill"].get(skill, 0) + 1

            # Work item stats
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/integration_work_items",
                headers=supabase_headers,
                params={"select": "status,integration_name"}
            )
            if response.status_code == 200:
                items = response.json()
                stats["work_items"]["total"] = len(items)
                for item in items:
                    status = item.get("status", "unknown")
                    integration = item.get("integration_name", "unknown")
                    stats["work_items"]["by_status"][status] = stats["work_items"]["by_status"].get(status, 0) + 1
                    stats["work_items"]["by_integration"][integration] = stats["work_items"]["by_integration"].get(integration, 0) + 1
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")

        return stats


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8054)
