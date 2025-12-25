"""Trajectory accumulation module for AgentGym RL.

Collects and stores trajectory data from NATS geometry events for
reinforcement learning training.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx

logger = logging.getLogger("agentgym.trajectory")


class TrajectoryAccumulator:
    """Accumulates trajectory data from NATS geometry events.

    Listens to NATS subjects like geometry.event.v1 and stores
    trajectory data in Supabase for later PPO training.
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
    ):
        """Initialize trajectory accumulator.

        Args:
            supabase_url: Supabase API URL
            supabase_key: Supabase service role key
        """
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_key = supabase_key
        self._client: Optional[httpx.AsyncClient] = None
        self._headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def process_geometry_event(
        self,
        subject: str,
        data: bytes,
    ) -> Optional[Dict[str, Any]]:
        """Process a geometry event from NATS.

        Args:
            subject: NATS subject (e.g., geometry.event.v1)
            data: Event data bytes

        Returns:
            Processing result with trajectory_id and event_count
        """
        try:
            event = json.loads(data.decode("utf-8"))
            return await self._accumulate_event(event, subject)
        except json.JSONDecodeError as e:
            logger.error("Failed to decode geometry event: %s", e)
            return None
        except Exception as e:
            logger.exception("Failed to process geometry event")
            return None

    async def _accumulate_event(
        self,
        event: Dict[str, Any],
        subject: str,
    ) -> Dict[str, Any]:
        """Accumulate event data into trajectory storage.

        Args:
            event: Parsed geometry event data
            subject: NATS subject

        Returns:
            Dict with trajectory_id and event_count
        """
        client = await self._get_client()

        # Extract session_id and relevant fields
        session_id = event.get("session_id") or event.get("session")
        if not session_id:
            # Generate session ID from event data
            session_id = str(uuid4())

        # Build trajectory entry
        trajectory_entry = {
            "timestamp": event.get("ts") or datetime.now(timezone.utc).isoformat(),
            "subject": subject,
            "event_type": event.get("type", "geometry_event"),
            "data": event,
        }

        # Prepare function call data
        function_data = {
            "p_session_id": session_id,
            "p_trajectory_data": json.dumps({f"event_{uuid4()}": trajectory_entry}),
            "p_event_count": 1,
            "p_task_type": event.get("task_type"),
            "p_environment": event.get("environment"),
        }

        # Call Supabase RPC function
        resp = await client.post(
            f"{self.supabase_url}/rest/v1/rpc/upsert_trajectory",
            headers=self._headers,
            json=function_data,
        )

        if resp.status_code not in [200, 201]:
            logger.error(
                "Failed to upsert trajectory: status=%s body=%s",
                resp.status_code,
                resp.text[:200],
            )
            return {"error": "Failed to upsert trajectory"}

        result = resp.json()
        trajectory_id = result.get("id") or result.get(0, {}).get("id")

        logger.debug(
            "Accumulated event for session %s: trajectory_id=%s",
            session_id,
            trajectory_id,
        )

        return {
            "trajectory_id": trajectory_id,
            "session_id": session_id,
            "event_count": 1,
        }

    async def get_trajectory(
        self,
        trajectory_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get trajectory by ID.

        Args:
            trajectory_id: UUID of trajectory

        Returns:
            Trajectory data or None if not found
        """
        client = await self._get_client()

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            params={"id": f"eq.{trajectory_id}", "select": "*"},
        )

        if resp.status_code != 200:
            logger.error("Failed to get trajectory: %s", resp.text[:200])
            return None

        trajectories = resp.json()
        return trajectories[0] if trajectories else None

    async def list_trajectories(
        self,
        session_id: Optional[str] = None,
        unpublished_only: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List trajectories.

        Args:
            session_id: Filter by session ID
            unpublished_only: Only return unpublished trajectories
            limit: Maximum results

        Returns:
            List of trajectory summaries
        """
        client = await self._get_client()

        params = {"select": "*", "limit": str(limit), "order": "created_at.desc"}

        if session_id:
            params["session_id"] = f"eq.{session_id}"
        if unpublished_only:
            params["published_to_hf"] = "eq.false"

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            params=params,
        )

        if resp.status_code != 200:
            logger.error("Failed to list trajectories: %s", resp.text[:200])
            return []

        return resp.json()

    async def get_trajectory_stats(self) -> Dict[str, Any]:
        """Get statistics about accumulated trajectories.

        Returns:
            Dict with total_trajectories, total_events, unpublished_count
        """
        client = await self._get_client()

        # Get total count
        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            params={"select": "id,event_count,published_to_hf"},
        )

        if resp.status_code != 200:
            return {"error": "Failed to get stats"}

        trajectories = resp.json()
        total_trajectories = len(trajectories)
        total_events = sum(t.get("event_count", 0) for t in trajectories)
        unpublished_count = sum(1 for t in trajectories if not t.get("published_to_hf"))

        return {
            "total_trajectories": total_trajectories,
            "total_events": total_events,
            "unpublished_count": unpublished_count,
            "published_count": total_trajectories - unpublished_count,
        }

    async def mark_published(
        self,
        trajectory_id: str,
        hf_dataset_id: str,
        hf_repo_url: str,
    ) -> bool:
        """Mark trajectory as published to HuggingFace.

        Args:
            trajectory_id: UUID of trajectory
            hf_dataset_id: HuggingFace dataset ID
            hf_repo_url: HuggingFace repository URL

        Returns:
            True if successful
        """
        client = await self._get_client()

        resp = await client.patch(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories?id=eq.{trajectory_id}",
            headers=self._headers,
            json={
                "published_to_hf": True,
                "hf_dataset_id": hf_dataset_id,
                "hf_repo_url": hf_repo_url,
            },
        )

        return resp.status_code in [200, 204]
