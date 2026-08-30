"""
Scheduled Announcements

Cron-like scheduling for recurring and one-shot audio announcements.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime
from enum import Enum


class ScheduleType(Enum):
    """Types of scheduled announcements."""

    RECURRING = "recurring"
    ONE_SHOT = "one_shot"


@dataclass
class AnnouncementTemplate:
    """Reusable announcement template with variables."""

    name: str
    template: str
    description: str = ""
    created_at: float = field(default_factory=lambda: datetime.utcnow().timestamp())

    def render(self, variables: dict) -> str:
        """
        Render template with variables.

        Args:
            variables: Dict of variable substitutions

        Returns:
            Rendered text
        """
        text = self.template
        for key, value in variables.items():
            text = text.replace(f"{{{key}}}", str(value))
        return text

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "template": self.template,
            "description": self.description,
            "created_at": self.created_at,
            "created_at_iso": datetime.fromtimestamp(self.created_at).isoformat() + "Z",
        }


@dataclass
class ScheduledAnnouncement:
    """Scheduled announcement."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    device: Optional[str] = None
    group: Optional[str] = None
    voice: str = "default"
    schedule_type: ScheduleType = ScheduleType.ONE_SHOT
    cron: str = ""
    scheduled_at: Optional[float] = None
    priority: str = "normal"
    enabled: bool = True
    created_at: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "device": self.device,
            "group": self.group,
            "voice": self.voice,
            "schedule_type": self.schedule_type.value,
            "cron": self.cron,
            "scheduled_at": self.scheduled_at,
            "scheduled_at_iso": datetime.fromtimestamp(self.scheduled_at).isoformat() + "Z"
            if self.scheduled_at
            else None,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "created_at_iso": datetime.fromtimestamp(self.created_at).isoformat() + "Z",
            "last_run": self.last_run,
            "last_run_iso": datetime.fromtimestamp(self.last_run).isoformat() + "Z"
            if self.last_run
            else None,
            "next_run": self.next_run,
            "next_run_iso": datetime.fromtimestamp(self.next_run).isoformat() + "Z"
            if self.next_run
            else None,
            "run_count": self.run_count,
        }


class CastScheduler:
    """Scheduler for Cast announcements."""

    def __init__(self, cast_fn: Callable):
        """
        Initialize scheduler.

        Args:
            cast_fn: Async function to execute cast (takes text, device, group, voice)
        """
        self.cast_fn = cast_fn
        self.scheduled: dict[str, ScheduledAnnouncement] = {}
        self.templates: dict[str, AnnouncementTemplate] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def schedule(
        self,
        text: str,
        cron: str,
        device: Optional[str] = None,
        group: Optional[str] = None,
        voice: str = "default",
        priority: str = "normal",
    ) -> dict:
        """
        Schedule a recurring announcement.

        Args:
            text: Text to announce
            cron: Cron expression (e.g., "0 20 * * *" for 8pm daily)
            device: Device name (optional)
            group: Group name (optional)
            voice: Voice to use
            priority: Priority level

        Returns:
            Result dict
        """
        announcement = ScheduledAnnouncement(
            text=text,
            device=device,
            group=group,
            voice=voice,
            schedule_type=ScheduleType.RECURRING,
            cron=cron,
            priority=priority,
        )

        # Calculate next run time
        next_run = self._parse_cron_next(cron)
        if next_run:
            announcement.next_run = next_run.timestamp()

        async with self._lock:
            self.scheduled[announcement.id] = announcement

        return {
            "success": True,
            "announcement": announcement.to_dict(),
            "message": f"Scheduled recurring announcement (id: {announcement.id})",
        }

    async def schedule_once(
        self,
        text: str,
        at: float,
        device: Optional[str] = None,
        group: Optional[str] = None,
        voice: str = "default",
        priority: str = "normal",
    ) -> dict:
        """
        Schedule a one-shot announcement.

        Args:
            text: Text to announce
            at: Unix timestamp to schedule
            device: Device name (optional)
            group: Group name (optional)
            voice: Voice to use
            priority: Priority level

        Returns:
            Result dict
        """
        if at < datetime.utcnow().timestamp():
            return {
                "success": False,
                "error": "Scheduled time must be in the future",
            }

        announcement = ScheduledAnnouncement(
            text=text,
            device=device,
            group=group,
            voice=voice,
            schedule_type=ScheduleType.ONE_SHOT,
            scheduled_at=at,
            next_run=at,
            priority=priority,
        )

        async with self._lock:
            self.scheduled[announcement.id] = announcement

        return {
            "success": True,
            "announcement": announcement.to_dict(),
            "message": f"Scheduled one-shot announcement (id: {announcement.id})",
        }

    async def cancel(self, announcement_id: str) -> dict:
        """
        Cancel a scheduled announcement.

        Args:
            announcement_id: ID of announcement to cancel

        Returns:
            Result dict
        """
        async with self._lock:
            if announcement_id not in self.scheduled:
                return {
                    "success": False,
                    "error": f"Announcement '{announcement_id}' not found",
                }

            del self.scheduled[announcement_id]

        return {
            "success": True,
            "message": f"Cancelled announcement '{announcement_id}'",
        }

    def list_scheduled(self) -> list[ScheduledAnnouncement]:
        """
        List all scheduled announcements.

        Returns:
            List of scheduled announcements
        """
        return list(self.scheduled.values())

    async def create_template(
        self,
        name: str,
        template: str,
        description: str = "",
    ) -> dict:
        """
        Create an announcement template.

        Args:
            name: Template name
            template: Template text with {variable} placeholders
            description: Template description

        Returns:
            Result dict
        """
        if not name:
            return {
                "success": False,
                "error": "Template name is required",
            }

        if name in self.templates:
            return {
                "success": False,
                "error": f"Template '{name}' already exists",
            }

        tmpl = AnnouncementTemplate(
            name=name,
            template=template,
            description=description,
        )

        self.templates[name] = tmpl

        return {
            "success": True,
            "template": tmpl.to_dict(),
            "message": f"Created template '{name}'",
        }

    def get_template(self, name: str) -> Optional[AnnouncementTemplate]:
        """
        Get template by name.

        Args:
            name: Template name

        Returns:
            Template if found, None otherwise
        """
        return self.templates.get(name)

    def list_templates(self) -> list[AnnouncementTemplate]:
        """
        List all templates.

        Returns:
            List of templates
        """
        return list(self.templates.values())

    async def delete_template(self, name: str) -> dict:
        """
        Delete a template.

        Args:
            name: Template name

        Returns:
            Result dict
        """
        if name not in self.templates:
            return {
                "success": False,
                "error": f"Template '{name}' not found",
            }

        del self.templates[name]

        return {
            "success": True,
            "message": f"Deleted template '{name}'",
        }

    async def start(self):
        """Start scheduler background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        """Stop scheduler background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.utcnow().timestamp()

                async with self._lock:
                    for announcement in list(self.scheduled.values()):
                        # Check if announcement is due
                        if (
                            announcement.enabled
                            and announcement.next_run
                            and announcement.next_run <= now
                        ):
                            # Execute cast
                            try:
                                await self.cast_fn(
                                    text=announcement.text,
                                    device=announcement.device,
                                    group=announcement.group,
                                    voice=announcement.voice,
                                )

                                announcement.last_run = now
                                announcement.run_count += 1

                                # Update next run for recurring
                                if announcement.schedule_type == ScheduleType.RECURRING:
                                    next_run = self._parse_cron_next(announcement.cron)
                                    if next_run:
                                        announcement.next_run = next_run.timestamp()
                                    else:
                                        # Disable if cron parsing fails
                                        announcement.enabled = False
                                else:
                                    # Remove one-shot after execution
                                    del self.scheduled[announcement.id]

                            except Exception as e:
                                print(f"Scheduler error: {e}")

                # Sleep for 1 second
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Scheduler loop error: {e}")
                await asyncio.sleep(5)

    def _parse_cron_next(self, cron: str) -> Optional[datetime]:
        """
        Parse cron expression and return next run time using croniter.

        Supports all standard cron expressions:
        - "0 20 * * *" - 8pm daily
        - "0 */6 * * *" - Every 6 hours
        - "0 12 * * 1-5" - Noon on weekdays
        - "*/30 * * * *" - Every 30 minutes
        - "0 0 1 * *" - First day of month

        Args:
            cron: Cron expression (5-part standard format)

        Returns:
            Next run datetime or None if invalid

        Raises:
            ImportError: If croniter is not installed (install with: pip install croniter)
            ValueError: If cron expression is invalid
        """
        try:
            from croniter import croniter

            base = datetime.utcnow()
            iter = croniter(cron, base)
            return iter.get_next(datetime)

        except ImportError:
            # croniter is now required for scheduler functionality
            print(
                "ERROR: croniter is required for scheduler functionality. "
                "Install with: pip install croniter>=2.0.0"
            )
            return None
        except Exception as e:
            print(f"ERROR: Invalid cron expression '{cron}': {e}")
            return None
