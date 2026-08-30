"""Cron-based scheduler for weekly cookie refresh.

Adapted from pmoves/services/cast-tts-gateway/scheduler.py pattern (croniter).
Default schedule: weekly at Sunday 00:00 UTC (cookies have ~30-day TTL).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from croniter import croniter

logger = logging.getLogger("yt-cookie-refresher.scheduler")

DEFAULT_CRON = "0 0 * * 0"  # weekly, Sunday midnight UTC


class RefreshScheduler:
    """Runs a callback on a cron schedule."""

    def __init__(self, callback, cron_expr: str = ""):
        self._callback = callback
        self._cron = cron_expr or os.environ.get("YT_COOKIE_REFRESH_CRON", DEFAULT_CRON)
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Scheduler started: cron={self._cron}")

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        cron = croniter(self._cron, datetime.now(timezone.utc))
        while self._running:
            next_fire = cron.get_next(datetime).replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delay = (next_fire - now).total_seconds()
            if delay > 0:
                logger.info(f"Next refresh at {next_fire.isoformat()} (in {delay:.0f}s)")
                await asyncio.sleep(delay)
            if self._running:
                try:
                    await self._callback()
                except Exception as e:
                    logger.exception(f"Scheduled refresh failed: {e}")

    async def trigger_now(self) -> None:
        """Force an immediate refresh (for make yt-cookies-refresh)."""
        logger.info("Manual refresh triggered")
        await self._callback()
