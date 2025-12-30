"""
Pydantic models for GitHub API interactions.

Following PMOVES SDK pattern: use Pydantic for request/response validation
with field-level constraints and type-safe enumerations.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, HttpUrl, ValidationInfo, field_validator


# =============================================================================
# Type Definitions (Enums for constrained values)
# =============================================================================

RunnerLocation = Literal["local", "remote", "cloud"]
RunnerStatus = Literal["online", "offline", "busy", "error"]
RunnerOS = Literal["Linux", "Windows", "macOS"]
WorkflowStatus = Literal["queued", "in_progress", "completed", "pending", "waiting", "requested", "failure", "cancelled", "skipped", "timed_out", "action_required"]
WorkflowEvent = Literal["push", "pull_request", "workflow_dispatch", "schedule", "manual", "repository_dispatch"]
RunnerAction = Literal["enable", "disable", "restart", "remove"]
AlertSeverity = Literal["info", "warning", "critical"]


# =============================================================================
# GitHub Runner Models
# =============================================================================

class RunnerConfig(BaseModel):
    """Runner configuration from config file.

    Invariants:
    - name must be non-empty and alphanumeric with hyphens/underscores
    - location must be one of: local, remote, cloud
    - labels limited to 50 items max
    - health_url must be valid HTTPS URL if provided
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Runner name (alphanumeric, hyphens, underscores only)"
    )
    location: RunnerLocation = Field(
        ...,
        description="Runner location (local, remote, cloud)"
    )
    labels: List[str] = Field(
        default_factory=list,
        max_items=50,
        description="GitHub runner labels (max 50)"
    )
    capabilities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Hardware capabilities (cpu_cores, memory_gb, gpu, etc.)"
    )
    workloads: List[str] = Field(
        default_factory=list,
        description="Supported workload types (build, test, deploy, etc.)"
    )
    health_url: Optional[HttpUrl] = Field(
        None,
        description="Health check URL (must be HTTPS)"
    )

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: List[str]) -> List[str]:
        """Ensure labels are non-empty and reasonable length."""
        for label in v:
            if not label or len(label) > 100:
                raise ValueError(f"Invalid label: '{label}'. Must be 1-100 characters.")
        return v

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure capability values are JSON-serializable types."""
        for key, value in v.items():
            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                raise ValueError(f"Capability '{key}' has unsupported type: {type(value)}")
        return v


class GitHubRunner(BaseModel):
    """GitHub runner from API.

    Represents the raw runner data returned by GitHub's self-hosted runners API.
    """

    id: int = Field(..., ge=1, description="GitHub runner ID")
    name: str = Field(..., min_length=1, max_length=100, description="Runner name")
    os: RunnerOS = Field(..., description="Operating system")
    status: RunnerStatus = Field(..., description="Runner status")
    busy: bool = Field(..., description="Whether runner is currently executing a job")
    labels: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Runner labels from GitHub"
    )


class RunnerStatus(BaseModel):
    """Runner status from our monitoring.

    Invariants:
    - queue_depth must be non-negative
    - status must be one of: online, offline, busy, error
    """

    name: str = Field(..., min_length=1, max_length=100, description="Runner name")
    location: RunnerLocation = Field(..., description="Runner location")
    status: RunnerStatus = Field(..., description="Current runner status")
    busy: bool = Field(..., description="Whether runner is busy")
    queue_depth: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="Number of queued jobs (0-1000)"
    )
    last_seen: Optional[datetime] = Field(None, description="Last successful health check")
    capabilities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Hardware capabilities"
    )


# =============================================================================
# GitHub Workflow/Job Models
# =============================================================================

class WorkflowRun(BaseModel):
    """GitHub workflow run.

    Represents a workflow execution returned by GitHub's Actions API.
    """

    id: int = Field(..., ge=1, description="Workflow run ID")
    name: str = Field(..., min_length=1, max_length=255, description="Workflow name")
    status: WorkflowStatus = Field(..., description="Workflow status")
    conclusion: Optional[str] = Field(None, description="Workflow conclusion (success, failure, etc.)")
    created_at: datetime = Field(..., description="Workflow creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    event: WorkflowEvent = Field(..., description="Trigger event type")
    head_branch: str = Field(..., min_length=1, max_length=255, description="Branch name")
    repository: str = Field(..., min_length=1, description="Repository (owner/repo format)")


class JobInfo(BaseModel):
    """GitHub job information.

    Represents a single job within a workflow run.
    """

    id: int = Field(..., ge=1, description="Job ID")
    run_id: int = Field(..., ge=1, description="Parent workflow run ID")
    name: str = Field(..., min_length=1, max_length=255, description="Job name")
    status: WorkflowStatus = Field(..., description="Job status")
    conclusion: Optional[str] = Field(None, description="Job conclusion")
    started_at: Optional[datetime] = Field(None, description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    runner_name: Optional[str] = Field(None, max_length=100, description="Runner that executed job")
    labels: List[str] = Field(
        default_factory=list,
        max_items=50,
        description="Runner labels required for this job"
    )


# =============================================================================
# API Models
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response.

    Standard PMOVES health endpoint response format.
    """

    ok: bool = Field(..., description="Service health status")
    time: int = Field(..., ge=0, description="Current Unix timestamp")
    nats_connected: bool = Field(..., description="NATS connection status")
    runners_monitored: int = Field(..., ge=0, description="Number of runners being monitored")
    github_connected: bool = Field(..., description="GitHub API connection status")


class RunnerListResponse(BaseModel):
    """List runners response.

    Invariants:
    - counts must be non-negative and consistent (online + offline + busy >= total)
    """

    runners: List[RunnerStatus] = Field(..., description="Runner status list")
    total: int = Field(..., ge=0, description="Total number of runners")
    online: int = Field(..., ge=0, description="Number of online runners")
    busy: int = Field(..., ge=0, description="Number of busy runners")

    @field_validator("online", "busy")
    @classmethod
    def validate_counts(cls, v: int, info: ValidationInfo) -> int:
        """Ensure counts don't exceed total."""
        if "total" in info.data and v > info.data["total"]:
            raise ValueError(f"{info.field_name} cannot exceed total")
        return v


class RunnerActionRequest(BaseModel):
    """Request to perform action on a runner.

    Invariants:
    - action must be one of: enable, disable, restart, remove
    - reason if provided must be non-empty
    """

    action: RunnerAction = Field(..., description="Action to perform")
    reason: Optional[str] = Field(
        None,
        min_length=1,
        max_length=500,
        description="Reason for the action"
    )


class QueueStatus(BaseModel):
    """Queue status for a repository.

    Represents the current state of GitHub Actions job queue.
    """

    repository: str = Field(..., min_length=1, description="Repository (owner/repo)")
    queued_jobs: int = Field(..., ge=0, description="Number of queued jobs")
    in_progress_jobs: int = Field(..., ge=0, description="Number of in-progress jobs")
    runners_available: int = Field(..., ge=0, description="Number of available runners")


class RunnerMetrics(BaseModel):
    """Runner metrics snapshot.

    Invariants:
    - all byte/second values must be non-negative
    - cpu_percent must be 0-100 if provided
    """

    runner: str = Field(..., min_length=1, max_length=100, description="Runner name")
    cpu_percent: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="CPU usage percentage (0-100)"
    )
    memory_bytes: int = Field(..., ge=0, description="Memory usage in bytes")
    disk_bytes: int = Field(..., ge=0, description="Disk usage in bytes")
    uptime_seconds: int = Field(..., ge=0, description="Uptime in seconds")


# =============================================================================
# Event Models (for NATS payloads)
# =============================================================================

class RunnerEventPayload(BaseModel):
    """Base payload for runner lifecycle events.

    Published on NATS subjects like:
    - github.runner.registered.v1
    - github.runner.removed.v1
    - github.runner.enabled.v1
    - github.runner.disabled.v1
    """

    runner: str = Field(..., min_length=1, description="Runner name or ID")
    timestamp: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", description="ISO 8601 timestamp")


class JobEventPayload(BaseModel):
    """Base payload for job lifecycle events.

    Published on NATS subjects like:
    - github.job.queued.v1
    - github.job.started.v1
    - github.job.completed.v1
    - github.job.failed.v1
    """

    runner: str = Field(..., min_length=1, description="Runner name or ID")
    repository: str = Field(..., min_length=1, description="Repository (owner/repo)")
    job_id: Optional[str] = Field(None, description="Job identifier")
    timestamp: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", description="ISO 8601 timestamp")


class AlertPayload(BaseModel):
    """Base payload for resource alert events.

    Published on NATS subjects like:
    - github.runner.cpu_high.v1
    - github.runner.memory_high.v1
    - github.runner.disk_low.v1
    - github.runner.queue_backlog.v1
    """

    runner: str = Field(..., min_length=1, description="Runner name or ID")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    message: str = Field(..., min_length=1, max_length=1000, description="Alert message")
    timestamp: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", description="ISO 8601 timestamp")
