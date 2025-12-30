"""
Pydantic models for GitHub API interactions.

Following PMOVES SDK pattern: use Pydantic for request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# GitHub Runner Models

class RunnerConfig(BaseModel):
    """Runner configuration from config file."""

    name: str = Field(..., description="Runner name")
    location: str = Field(..., description="Runner location (local, remote, cloud)")
    labels: List[str] = Field(default_factory=list, description="GitHub runner labels")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Hardware capabilities")
    workloads: List[str] = Field(default_factory=list, description="Supported workload types")
    health_url: Optional[str] = Field(None, description="Health check URL")


class GitHubRunner(BaseModel):
    """GitHub runner from API."""

    id: int
    name: str
    os: str
    status: str  # online, offline, busy
    busy: bool
    labels: List[Dict[str, str]]


class RunnerStatus(BaseModel):
    """Runner status from our monitoring."""

    name: str
    location: str
    status: str  # online, offline, busy, error
    busy: bool
    queue_depth: int = 0
    last_seen: Optional[datetime] = None
    capabilities: Dict[str, Any] = Field(default_factory=dict)


# GitHub Workflow/Job Models

class WorkflowRun(BaseModel):
    """GitHub workflow run."""

    id: int
    name: str
    status: str
    conclusion: Optional[str]
    created_at: datetime
    updated_at: datetime
    event: str
    head_branch: str
    repository: str


class JobInfo(BaseModel):
    """GitHub job information."""

    id: int
    run_id: int
    name: str
    status: str
    conclusion: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    runner_name: Optional[str]
    labels: List[str]


# API Models

class HealthResponse(BaseModel):
    """Health check response."""

    ok: bool
    time: int
    nats_connected: bool
    runners_monitored: int
    github_connected: bool


class RunnerListResponse(BaseModel):
    """List runners response."""

    runners: List[RunnerStatus]
    total: int
    online: int
    busy: int


class RunnerActionRequest(BaseModel):
    """Request to perform action on a runner."""

    action: str = Field(..., description="Action: enable, disable, restart")
    reason: Optional[str] = Field(None, description="Reason for action")


class QueueStatus(BaseModel):
    """Queue status for a repository."""

    repository: str
    queued_jobs: int
    in_progress_jobs: int
    runners_available: int


class RunnerMetrics(BaseModel):
    """Runner metrics snapshot."""

    runner: str
    cpu_percent: Optional[float]
    memory_bytes: int
    disk_bytes: int
    uptime_seconds: int


# Event Models (for NATS payloads)

class RunnerEventPayload(BaseModel):
    """Base payload for runner events."""

    runner: str
    timestamp: str


class JobEventPayload(BaseModel):
    """Base payload for job events."""

    runner: str
    repository: str
    job_id: Optional[str]
    timestamp: str


class AlertPayload(BaseModel):
    """Base payload for alert events."""

    runner: str
    severity: str
    message: str
    timestamp: str
