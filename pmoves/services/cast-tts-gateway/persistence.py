"""
Supabase Persistence for Cast TTS Gateway

Persists voice profiles and scheduled announcements to Supabase PostgREST.
"""

import asyncio
import logging
import os
from typing import Optional

import aiohttp


log = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "http://supabase-kong:8000")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


class SupabasePersistence:
    """Persist voice profiles and schedules to Supabase."""

    def __init__(self, base_url: str = SUPABASE_URL, key: str = SUPABASE_SERVICE_ROLE_KEY):
        self._base = base_url.rstrip("/")
        self._key = key
        self._session: Optional[aiohttp.ClientSession] = None
        if not self._key:
            log.warning(
                "SUPABASE_SERVICE_ROLE_KEY is not set; persistence is DISABLED. "
                "Profiles and schedules will not survive restarts."
            )

    def _headers(self) -> dict:
        return {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
            )

    async def _check_response(self, resp: aiohttp.ClientResponse, operation: str) -> bool:
        """Log non-2xx responses. Returns True if response is OK."""
        if 200 <= resp.status < 300:
            return True
        body = await resp.text()
        log.error(
            "Persistence %s failed: HTTP %d from %s: %s",
            operation, resp.status, resp.url, body[:500],
        )
        return False

    # ── Voice Profiles ──────────────────────────────────────────────

    async def load_profiles(self) -> list[dict]:
        """Load all voice profiles from Supabase."""
        if not self._key:
            return []
        await self._ensure_session()
        url = f"{self._base}/rest/v1/cast_voice_profiles?select=*"
        try:
            async with self._session.get(url, headers=self._headers()) as resp:
                if await self._check_response(resp, "load_profiles"):
                    return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.error("Persistence load_profiles error: %s", e)
        except Exception as e:
            log.exception("Persistence load_profiles unexpected error: %s", e)
        return []

    async def save_profile(self, profile: dict) -> bool:
        """Upsert a voice profile."""
        if not self._key:
            return False
        await self._ensure_session()
        url = f"{self._base}/rest/v1/cast_voice_profiles"
        headers = {**self._headers(), "Prefer": "resolution=merge-duplicates,return=representation"}
        try:
            async with self._session.post(url, json=profile, headers=headers) as resp:
                return await self._check_response(resp, "save_profile")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.error("Persistence save_profile error: %s", e)
            return False
        except Exception as e:
            log.exception("Persistence save_profile unexpected error: %s", e)
            return False

    async def delete_profile(self, name: str) -> bool:
        """Delete a voice profile by name."""
        if not self._key:
            return False
        await self._ensure_session()
        url = f"{self._base}/rest/v1/cast_voice_profiles?name=eq.{name}"
        try:
            async with self._session.delete(url, headers=self._headers()) as resp:
                return await self._check_response(resp, "delete_profile")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.error("Persistence delete_profile error: %s", e)
            return False
        except Exception as e:
            log.exception("Persistence delete_profile unexpected error: %s", e)
            return False

    # ── Schedules ───────────────────────────────────────────────────

    async def load_schedules(self) -> list[dict]:
        """Load all scheduled announcements from Supabase."""
        if not self._key:
            return []
        await self._ensure_session()
        url = f"{self._base}/rest/v1/cast_scheduled_announcements?select=*&enabled=eq.true"
        try:
            async with self._session.get(url, headers=self._headers()) as resp:
                if await self._check_response(resp, "load_schedules"):
                    return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.error("Persistence load_schedules error: %s", e)
        except Exception as e:
            log.exception("Persistence load_schedules unexpected error: %s", e)
        return []

    async def save_schedule(self, schedule: dict) -> bool:
        """Upsert a schedule."""
        if not self._key:
            return False
        await self._ensure_session()
        url = f"{self._base}/rest/v1/cast_scheduled_announcements"
        headers = {**self._headers(), "Prefer": "resolution=merge-duplicates,return=representation"}
        try:
            async with self._session.post(url, json=schedule, headers=headers) as resp:
                return await self._check_response(resp, "save_schedule")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.error("Persistence save_schedule error: %s", e)
            return False
        except Exception as e:
            log.exception("Persistence save_schedule unexpected error: %s", e)
            return False

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule by ID."""
        if not self._key:
            return False
        await self._ensure_session()
        url = f"{self._base}/rest/v1/cast_scheduled_announcements?id=eq.{schedule_id}"
        try:
            async with self._session.delete(url, headers=self._headers()) as resp:
                return await self._check_response(resp, "delete_schedule")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.error("Persistence delete_schedule error: %s", e)
            return False
        except Exception as e:
            log.exception("Persistence delete_schedule unexpected error: %s", e)
            return False

    # ── Lifecycle ───────────────────────────────────────────────────

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception as e:
                log.warning("Error closing persistence session: %s", e)
