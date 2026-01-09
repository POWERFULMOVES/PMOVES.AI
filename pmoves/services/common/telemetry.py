"""Shared telemetry helpers for publisher-style services."""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class PublisherMetrics:
    """Aggregate metrics for publisher style services."""

    downloads: int = 0
    download_failures: int = 0
    refresh_attempts: int = 0
    refresh_success: int = 0
    refresh_failures: int = 0
    turnaround_samples: int = 0
    total_turnaround_seconds: float = 0.0
    max_turnaround_seconds: float = 0.0
    approval_latency_samples: int = 0
    total_approval_latency_seconds: float = 0.0
    max_approval_latency_seconds: float = 0.0
    engagement_events: int = 0
    engagement_totals: Dict[str, float] = field(default_factory=dict)
    cost_events: int = 0
    cost_totals: Dict[str, float] = field(default_factory=dict)

    def record_download_success(self) -> None:
        self.downloads += 1

    def record_download_failure(self) -> None:
        self.download_failures += 1

    def record_refresh_attempt(self) -> None:
        self.refresh_attempts += 1

    def record_refresh_success(self) -> None:
        self.refresh_success += 1

    def record_refresh_failure(self) -> None:
        self.refresh_failures += 1

    def record_turnaround(self, seconds: Optional[float]) -> None:
        if seconds is None or seconds < 0:
            return
        self.turnaround_samples += 1
        self.total_turnaround_seconds += seconds
        if seconds > self.max_turnaround_seconds:
            self.max_turnaround_seconds = seconds

    def record_approval_latency(self, seconds: Optional[float]) -> None:
        if seconds is None or seconds < 0:
            return
        self.approval_latency_samples += 1
        self.total_approval_latency_seconds += seconds
        if seconds > self.max_approval_latency_seconds:
            self.max_approval_latency_seconds = seconds

    def record_engagement(self, engagement: Dict[str, float]) -> None:
        if not engagement:
            return
        self.engagement_events += 1
        for key, value in engagement.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            self.engagement_totals[key] = self.engagement_totals.get(key, 0.0) + numeric

    def record_cost(self, cost: Dict[str, float]) -> None:
        if not cost:
            return
        self.cost_events += 1
        for key, value in cost.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            self.cost_totals[key] = self.cost_totals.get(key, 0.0) + numeric

    def summary(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.turnaround_samples:
            data["avg_turnaround_seconds"] = self.total_turnaround_seconds / self.turnaround_samples
        if self.approval_latency_samples:
            data["avg_approval_latency_seconds"] = (
                self.total_approval_latency_seconds / self.approval_latency_samples
            )
        return data


@dataclass
class PublishTelemetry:
    published_at: _dt.datetime
    turnaround_seconds: Optional[float]
    approval_latency_seconds: Optional[float]
    engagement: Dict[str, float]
    cost: Dict[str, float]

    def to_meta(self) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "published_at": self.published_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        if self.turnaround_seconds is not None:
            meta["turnaround_seconds"] = self.turnaround_seconds
        if self.approval_latency_seconds is not None:
            meta["approval_to_publish_seconds"] = self.approval_latency_seconds
        if self.engagement:
            meta["engagement"] = self.engagement
        if self.cost:
            meta["cost"] = self.cost
        return meta

    def to_rollup_row(self, *, artifact_uri: str, namespace: str, slug: str) -> Dict[str, Any]:
        return {
            "artifact_uri": artifact_uri,
            "namespace": namespace,
            "slug": slug,
            "published_at": self.published_at.isoformat(),
            "turnaround_seconds": self.turnaround_seconds,
            "approval_latency_seconds": self.approval_latency_seconds,
            "engagement": self.engagement or None,
            "cost": self.cost or None,
        }


def _parse_iso8601(value: Optional[Any]) -> Optional[_dt.datetime]:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return _dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _coerce_numeric(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        numeric = float(value)
        if numeric != numeric:  # NaN
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _extract_first(meta: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
    for key in keys:
        candidate = meta.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def compute_publish_telemetry(
    incoming_meta: Optional[Dict[str, Any]],
    event_ts: Optional[str],
    published_at: _dt.datetime,
) -> PublishTelemetry:
    meta = incoming_meta or {}
    start_keys = (
        "ingest_started_at",
        "submitted_at",
        "created_at",
        "capture_completed_at",
    )
    approval_keys = (
        "approval_granted_at",
        "approved_at",
        "approval_completed_at",
    )

    start_ts = _parse_iso8601(_extract_first(meta, start_keys))
    approval_ts = _parse_iso8601(_extract_first(meta, approval_keys))
    event_timestamp = _parse_iso8601(event_ts)

    turnaround_seconds: Optional[float] = None
    if start_ts is not None:
        turnaround_seconds = (published_at - start_ts).total_seconds()

    approval_latency_seconds: Optional[float] = None
    reference_ts = approval_ts or event_timestamp
    if reference_ts is not None:
        approval_latency_seconds = (published_at - reference_ts).total_seconds()

    engagement: Dict[str, float] = {}
    for key in ("engagement", "analytics", "metrics"):
        candidate = meta.get(key)
        if isinstance(candidate, dict):
            for metric_key, value in candidate.items():
                numeric = _coerce_numeric(value)
                if numeric is None:
                    continue
                engagement[metric_key] = engagement.get(metric_key, 0.0) + numeric

    cost: Dict[str, float] = {}
    for key in ("cost", "spend", "usage"):
        candidate = meta.get(key)
        if isinstance(candidate, dict):
            for cost_key, value in candidate.items():
                numeric = _coerce_numeric(value)
                if numeric is None:
                    continue
                cost[cost_key] = cost.get(cost_key, 0.0) + numeric

    return PublishTelemetry(
        published_at=published_at,
        turnaround_seconds=turnaround_seconds,
        approval_latency_seconds=approval_latency_seconds,
        engagement=engagement,
        cost=cost,
    )


__all__ = [
    "PublisherMetrics",
    "PublishTelemetry",
    "compute_publish_telemetry",
]

