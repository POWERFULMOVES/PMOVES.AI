"""
Supabase Persistence for Cast TTS Gateway

Persists voice profiles and scheduled announcements to Supabase PostgREST.
"""

import os
from typing import Optional

import aiohttp


SUPABASE_URL = os.getenv("SUPABASE_URL", "http://supabase-rest:3010")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


class SupabasePersistence:
    """Persist voice profiles and schedules to Supabase."""

    def __init__(self, base_url: str = SUPABASE_URL, key: str = SUPABASE_SERVICE_ROLE_KEY):
        self._base = base_url.rstrip("/")
        self._key = key
        self._session: Optional[aiohttp.ClientSession] = None

    def _headers(self) -> dict:
        return {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    # ── Voice Profiles ──────────────────────────────────────────────

    async def load_profiles(self) -> list[dict]:
        """Load all voice profiles from Supabase."""
        if not self._key:
            return []
        await self._ensure_session()
        url = f"{self._base}/rest/v1/cast_voice_profiles?select=*"
        try:
            async with self._session.get(url, headers=self._headers()) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            print(f"Persistence load_profiles error: {e}")
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
                return resp.status in (200, 201)
        except Exception as e:
            print(f"Persistence save_profile error: {e}")
            return False

    async def delete_profile(self, name: str) -> bool:
        """Delete a voice profile by name."""
        if not self._key:
            return False
        await self._ensure_session()
        url = f"{self._base}/rest/v1/cast_voice_profiles?name=eq.{name}"
        try:
            async with self._session.delete(url, headers=self._headers()) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            print(f"Persistence delete_profile error: {e}")
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
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            print(f"Persistence load_schedules error: {e}")
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
                return resp.status in (200, 201)
        except Exception as e:
            print(f"Persistence save_schedule error: {e}")
            return False

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule by ID."""
        if not self._key:
            return False
        await self._ensure_session()
        url = f"{self._base}/rest/v1/cast_scheduled_announcements?id=eq.{schedule_id}"
        try:
            async with self._session.delete(url, headers=self._headers()) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            print(f"Persistence delete_schedule error: {e}")
            return False

    # ── Lifecycle ───────────────────────────────────────────────────

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
