"""
Security Audit

Access control, rate limiting, and audit logging for production security.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from collections import deque


@dataclass
class AuditLogEntry:
    """Audit log entry."""

    timestamp: float = field(default_factory=time.time)
    action: str = ""
    user: Optional[str] = None
    device: Optional[str] = None
    result: str = "success"  # success, failure, error
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat() + "Z",
            "action": self.action,
            "user": self.user,
            "device": self.device,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        cleanup_interval: float = 300.0,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Sustained rate limit
            burst_size: Maximum burst size
            cleanup_interval: Seconds between bucket cleanups
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.cleanup_interval = cleanup_interval
        # Track bucket state: dict[str, {"tokens": float, "last_refill": float}]
        self.buckets: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background cleanup task."""
        if not self._cleanup_task or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def check_rate_limit(
        self,
        key: str,
        tokens: int = 1,
    ) -> dict:
        """
        Check if request is within rate limit using token bucket algorithm.

        Implements proper token bucket with time-based refill:
        - Tokens refill continuously at rate (requests_per_minute / 60 per second)
        - Burst capacity allows temporary bursts up to burst_size
        - Sustained rate enforced over time

        Args:
            key: Rate limit key (e.g., user_id, ip_address)
            tokens: Number of tokens to consume

        Returns:
            Result dict with:
                - allowed (bool): Whether request is allowed
                - limit (int): Sustained rate limit (requests per minute)
                - burst (int): Burst capacity
                - remaining (int): Tokens remaining (if allowed)
                - reason (str): Why request was denied (if not allowed)
                - retry_after (int): Seconds before retry (if not allowed)
        """
        async with self._lock:
            current_time = time.time()

            # Get or create bucket state
            if key not in self.buckets:
                self.buckets[key] = {
                    "tokens": float(self.burst_size),
                    "last_refill": current_time,
                }

            bucket_state = self.buckets[key]

            # Calculate token refill based on elapsed time
            elapsed = current_time - bucket_state["last_refill"]
            refill_rate = self.requests_per_minute / 60.0  # tokens per second
            tokens_to_add = elapsed * refill_rate

            # Refill tokens (up to burst_size)
            bucket_state["tokens"] = min(
                self.burst_size,
                bucket_state["tokens"] + tokens_to_add
            )
            bucket_state["last_refill"] = current_time

            # Check if we have enough tokens
            if bucket_state["tokens"] < tokens:
                tokens_needed = tokens - bucket_state["tokens"]
                refill_time = tokens_needed / refill_rate

                return {
                    "allowed": False,
                    "limit": self.requests_per_minute,
                    "burst": self.burst_size,
                    "reason": "rate_limit_exceeded",
                    "retry_after": int(refill_time) + 1,
                }

            # Consume tokens
            bucket_state["tokens"] -= tokens

            return {
                "allowed": True,
                "limit": self.requests_per_minute,
                "burst": self.burst_size,
                "remaining": int(bucket_state["tokens"]),
            }

    async def _cleanup_loop(self):
        """Background cleanup loop to remove stale buckets."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                async with self._lock:
                    current_time = time.time()
                    stale_threshold = 300.0  # 5 minutes of inactivity

                    # Remove stale buckets
                    for key in list(self.buckets.keys()):
                        bucket_state = self.buckets[key]

                        # Remove if bucket hasn't been used in 5 minutes
                        if current_time - bucket_state["last_refill"] > stale_threshold:
                            del self.buckets[key]

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Rate limiter cleanup error: {e}")

    def get_stats(self) -> dict:
        """Get rate limiter stats."""
        total_buckets = len(self.buckets)
        total_tokens = sum(bucket["tokens"] for bucket in self.buckets.values())

        return {
            "active_keys": total_buckets,
            "total_tokens": int(total_tokens),
            "requests_per_minute": self.requests_per_minute,
            "burst_size": self.burst_size,
        }


class AuditLogger:
    """Structured audit logging."""

    def __init__(
        self,
        max_entries: int = 10000,
        retention_hours: float = 24.0,
    ):
        """
        Initialize audit logger.

        Args:
            max_entries: Maximum log entries to keep
            retention_hours: Hours to retain logs
        """
        self.max_entries = max_entries
        self.retention_hours = retention_hours
        self.logs: deque[AuditLogEntry] = deque(maxlen=max_entries)
        self._lock = asyncio.Lock()

    async def log(
        self,
        action: str,
        user: Optional[str] = None,
        device: Optional[str] = None,
        result: str = "success",
        error: Optional[str] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """
        Log audit entry.

        Args:
            action: Action performed
            user: User identifier
            device: Device name
            result: Result (success, failure, error)
            error: Error message if failed
            metadata: Additional metadata
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Result dict
        """
        async with self._lock:
            entry = AuditLogEntry(
                action=action,
                user=user,
                device=device,
                result=result,
                error=error,
                metadata=metadata or {},
                ip_address=ip_address,
                user_agent=user_agent,
            )

            self.logs.append(entry)

            return {
                "success": True,
                "entry_id": len(self.logs) - 1,
                "message": "Audit entry logged",
            }

    async def query(
        self,
        action: Optional[str] = None,
        user: Optional[str] = None,
        device: Optional[str] = None,
        result: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """
        Query audit logs.

        Args:
            action: Filter by action
            user: Filter by user
            device: Filter by device
            result: Filter by result
            limit: Maximum results to return
            offset: Offset for pagination

        Returns:
            List of audit entries
        """
        async with self._lock:
            filtered = list(self.logs)

            # Apply filters
            if action:
                filtered = [e for e in filtered if e.action == action]

            if user:
                filtered = [e for e in filtered if e.user == user]

            if device:
                filtered = [e for e in filtered if e.device == device]

            if result:
                filtered = [e for e in filtered if e.result == result]

            # Sort by timestamp (newest first)
            filtered.sort(key=lambda e: e.timestamp, reverse=True)

            # Apply pagination
            return filtered[offset:offset + limit]

    async def cleanup_old_entries(self) -> dict:
        """Remove entries older than retention period."""
        async with self._lock:
            cutoff_time = time.time() - (self.retention_hours * 3600)

            # Create new deque with only recent entries
            recent_entries = deque(
                [e for e in self.logs if e.timestamp > cutoff_time],
                maxlen=self.max_entries,
            )

            removed = len(self.logs) - len(recent_entries)
            self.logs = recent_entries

            return {
                "removed": removed,
                "remaining": len(self.logs),
                "message": f"Removed {removed} old entries",
            }

    def get_stats(self) -> dict:
        """Get audit logger stats."""
        # Count by action
        action_counts: dict[str, int] = {}
        result_counts: dict[str, int] = {}

        for entry in self.logs:
            action_counts[entry.action] = action_counts.get(entry.action, 0) + 1
            result_counts[entry.result] = result_counts.get(entry.result, 0) + 1

        return {
            "total_entries": len(self.logs),
            "max_entries": self.max_entries,
            "retention_hours": self.retention_hours,
            "action_counts": action_counts,
            "result_counts": result_counts,
        }


class AccessControl:
    """Access control and permission checker."""

    def __init__(self):
        """Initialize access control."""
        self.permissions: dict[str, set[str]] = {}

    def grant_permission(self, user: str, permission: str) -> dict:
        """
        Grant permission to user.

        Args:
            user: User identifier
            permission: Permission string

        Returns:
            Result dict
        """
        if user not in self.permissions:
            self.permissions[user] = set()

        self.permissions[user].add(permission)

        return {
            "success": True,
            "user": user,
            "permission": permission,
            "message": f"Granted '{permission}' to '{user}'",
        }

    def revoke_permission(self, user: str, permission: str) -> dict:
        """
        Revoke permission from user.

        Args:
            user: User identifier
            permission: Permission string

        Returns:
            Result dict
        """
        if user not in self.permissions:
            return {
                "success": False,
                "error": f"User '{user}' not found",
            }

        if permission not in self.permissions[user]:
            return {
                "success": False,
                "error": f"Permission '{permission}' not granted to '{user}'",
            }

        self.permissions[user].remove(permission)

        return {
            "success": True,
            "user": user,
            "permission": permission,
            "message": f"Revoked '{permission}' from '{user}'",
        }

    def check_permission(
        self,
        user: str,
        permission: str,
    ) -> bool:
        """
        Check if user has permission.

        Args:
            user: User identifier
            permission: Permission string

        Returns:
            True if user has permission, False otherwise
        """
        if user not in self.permissions:
            return False

        return permission in self.permissions[user]

    def list_permissions(self, user: str) -> set[str]:
        """
        List all permissions for user.

        Args:
            user: User identifier

        Returns:
            Set of permissions
        """
        return self.permissions.get(user, set())

    def get_stats(self) -> dict:
        """Get access control stats."""
        return {
            "total_users": len(self.permissions),
            "total_permissions": sum(len(perms) for perms in self.permissions.values()),
            "users": list(self.permissions.keys()),
        }


class SecurityManager:
    """Manage all security components."""

    def __init__(self):
        """Initialize security manager."""
        self.rate_limiter = RateLimiter()
        self.audit_logger = AuditLogger()
        self.access_control = AccessControl()

    async def start(self):
        """Start security components."""
        await self.rate_limiter.start()

    async def stop(self):
        """Stop security components."""
        await self.rate_limiter.stop()

    async def check_rate_limit(
        self,
        key: str,
        tokens: int = 1,
    ) -> dict:
        """Check rate limit."""
        return await self.rate_limiter.check_rate_limit(key, tokens)

    async def log_audit(
        self,
        action: str,
        user: Optional[str] = None,
        device: Optional[str] = None,
        result: str = "success",
        error: Optional[str] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """Log audit entry."""
        return await self.audit_logger.log(
            action=action,
            user=user,
            device=device,
            result=result,
            error=error,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def query_audit_logs(
        self,
        action: Optional[str] = None,
        user: Optional[str] = None,
        device: Optional[str] = None,
        result: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query audit logs."""
        entries = await self.audit_logger.query(
            action=action,
            user=user,
            device=device,
            result=result,
            limit=limit,
            offset=offset,
        )

        return [e.to_dict() for e in entries]

    def grant_permission(self, user: str, permission: str) -> dict:
        """Grant permission to user."""
        return self.access_control.grant_permission(user, permission)

    def revoke_permission(self, user: str, permission: str) -> dict:
        """Revoke permission from user."""
        return self.access_control.revoke_permission(user, permission)

    def check_permission(self, user: str, permission: str) -> bool:
        """Check if user has permission."""
        return self.access_control.check_permission(user, permission)

    def get_security_stats(self) -> dict:
        """Get all security stats."""
        return {
            "rate_limiter": self.rate_limiter.get_stats(),
            "audit_logger": self.audit_logger.get_stats(),
            "access_control": self.access_control.get_stats(),
        }
