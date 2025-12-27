"""Supabase storage interface for AgentGym RL coordinator.

Provides a unified interface for storing and retrieving trajectories,
training runs, and related data from Supabase.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("agentgym.storage")


class SupabaseStorage:
    """Supabase storage interface for AgentGym.

    Provides methods for:
    - Trajectory CRUD operations
    - Training run management
    - Query helpers
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
    ):
        """Initialize Supabase storage interface.

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

    # ============================================================================
    # Trajectory Operations
    # ============================================================================

    async def create_trajectory(
        self,
        session_id: str,
        trajectory_data: Dict[str, Any],
        event_count: int = 0,
        task_type: Optional[str] = None,
        environment: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new trajectory.

        Args:
            session_id: Session identifier
            trajectory_data: Trajectory data (JSON)
            event_count: Number of events
            task_type: Optional task type
            environment: Optional environment name
            agent_id: Optional agent UUID

        Returns:
            Created trajectory record
        """
        client = await self._get_client()

        data = {
            "session_id": session_id,
            "trajectory_data": trajectory_data,
            "event_count": event_count,
        }

        if task_type:
            data["task_type"] = task_type
        if environment:
            data["environment"] = environment
        if agent_id:
            data["agent_id"] = agent_id

        resp = await client.post(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            json=data,
        )

        if resp.status_code not in [200, 201]:
            raise RuntimeError(f"Failed to create trajectory: {resp.text}")

        return resp.json()

    async def get_trajectory(self, trajectory_id: str) -> Optional[Dict[str, Any]]:
        """Get trajectory by ID.

        Args:
            trajectory_id: UUID of trajectory

        Returns:
            Trajectory data or None
        """
        client = await self._get_client()

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            params={"id": f"eq.{trajectory_id}"},
        )

        if resp.status_code != 200:
            return None

        results = resp.json()
        return results[0] if results else None

    async def update_trajectory(
        self,
        trajectory_id: str,
        **updates,
    ) -> bool:
        """Update trajectory fields.

        Args:
            trajectory_id: UUID of trajectory
            **updates: Fields to update

        Returns:
            True if successful
        """
        client = await self._get_client()

        resp = await client.patch(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            params={"id": f"eq.{trajectory_id}"},
            json=updates,
        )

        return resp.status_code in [200, 204]

    async def delete_trajectory(self, trajectory_id: str) -> bool:
        """Delete trajectory.

        Args:
            trajectory_id: UUID of trajectory

        Returns:
            True if deleted
        """
        client = await self._get_client()

        resp = await client.delete(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            params={"id": f"eq.{trajectory_id}"},
        )

        return resp.status_code in [200, 204]

    # ============================================================================
    # Training Run Operations
    # ============================================================================

    async def create_training_run(
        self,
        run_id: str,
        config: Dict[str, Any],
        total_epochs: int = 100,
    ) -> Dict[str, Any]:
        """Create a new training run.

        Args:
            run_id: Unique run identifier
            config: PPO configuration
            total_epochs: Total epochs

        Returns:
            Created training run record
        """
        client = await self._get_client()

        data = {
            "run_id": run_id,
            "config": config,
            "total_epochs": total_epochs,
            "status": "pending",
        }

        resp = await client.post(
            f"{self.supabase_url}/rest/v1/agentgym_training_runs",
            headers=self._headers,
            json=data,
        )

        if resp.status_code not in [200, 201]:
            raise RuntimeError(f"Failed to create training run: {resp.text}")

        return resp.json()

    async def get_training_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get training run by ID.

        Args:
            run_id: Training run ID

        Returns:
            Training run data or None
        """
        client = await self._get_client()

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_training_runs",
            headers=self._headers,
            params={"run_id": f"eq.{run_id}"},
        )

        if resp.status_code != 200:
            return None

        results = resp.json()
        return results[0] if results else None

    async def update_training_run(
        self,
        run_id: str,
        **updates,
    ) -> bool:
        """Update training run fields.

        Args:
            run_id: Training run ID
            **updates: Fields to update

        Returns:
            True if successful
        """
        client = await self._get_client()

        resp = await client.patch(
            f"{self.supabase_url}/rest/v1/agentgym_training_runs",
            headers=self._headers,
            params={"run_id": f"eq.{run_id}"},
            json=updates,
        )

        return resp.status_code in [200, 204]

    # ============================================================================
    # Query Helpers
    # ============================================================================

    async def list_trajectories(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List trajectories with optional filters.

        Args:
            filters: Optional filter dict
            limit: Max results
            offset: Offset for pagination

        Returns:
            List of trajectories
        """
        client = await self._get_client()

        params = {
            "select": "*",
            "limit": str(limit),
            "offset": str(offset),
            "order": "created_at.desc",
        }

        if filters:
            for key, value in filters.items():
                params[key] = f"eq.{value}"

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            params=params,
        )

        if resp.status_code != 200:
            logger.warning(
                "Failed to list trajectories: status=%s, body=%s",
                resp.status_code,
                resp.text[:200] if resp.text else "empty",
            )
            return []

        return resp.json()

    async def list_training_runs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List training runs with optional filters.

        Args:
            filters: Optional filter dict
            limit: Max results
            offset: Offset for pagination

        Returns:
            List of training runs
        """
        client = await self._get_client()

        params = {
            "select": "*",
            "limit": str(limit),
            "offset": str(offset),
            "order": "created_at.desc",
        }

        if filters:
            for key, value in filters.items():
                params[key] = f"eq.{value}"

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_training_runs",
            headers=self._headers,
            params=params,
        )

        if resp.status_code != 200:
            logger.warning(
                "Failed to list training runs: status=%s, body=%s",
                resp.status_code,
                resp.text[:200] if resp.text else "empty",
            )
            return []

        return resp.json()

    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dict with trajectory and training run counts
        """
        client = await self._get_client()

        def parse_count(resp) -> int:
            """Parse count from Supabase Content-Range header."""
            content_range = resp.headers.get("Content-Range", "")
            if "/" in content_range:
                return int(content_range.split("/")[-1])
            return 0

        # Use HEAD request with Prefer: count=exact header for efficient counting
        count_headers = {**self._headers, "Prefer": "count=exact"}

        # Get trajectory count
        traj_resp = await client.head(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=count_headers,
        )

        # Get training run count
        run_resp = await client.head(
            f"{self.supabase_url}/rest/v1/agentgym_training_runs",
            headers=count_headers,
        )

        trajectory_count = parse_count(traj_resp) if traj_resp.status_code in [200, 206] else 0
        training_run_count = parse_count(run_resp) if run_resp.status_code in [200, 206] else 0

        return {
            "trajectory_count": trajectory_count,
            "training_run_count": training_run_count,
        }
