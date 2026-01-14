"""HuggingFace dataset publishing module for AgentGym RL.

Publishes accumulated trajectory datasets to HuggingFace Hub.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from uuid import UUID

import httpx

logger = logging.getLogger("agentgym.publisher")


class HuggingFacePublisher:
    """Publishes AgentGym datasets to HuggingFace Hub.

    Handles:
    1. Exporting trajectory data from Supabase
    2. Converting to HuggingFace dataset format
    3. Publishing to HuggingFace Hub
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        hf_token: Optional[str] = None,
        hf_org: Optional[str] = None,
    ):
        """Initialize HuggingFace publisher.

        Args:
            supabase_url: Supabase API URL
            supabase_key: Supabase service role key
            hf_token: HuggingFace authentication token
            hf_org: HuggingFace organization (default: user account)
        """
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_key = supabase_key
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.hf_org = hf_org or os.getenv("HF_ORG", "pmoves")
        self._client: Optional[httpx.AsyncClient] = None
        self._headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
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

    async def export_trajectory(
        self,
        trajectory_id: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Export trajectory data to JSON file.

        Args:
            trajectory_id: UUID of trajectory to export
            output_path: Output file path (default: auto-generated)

        Returns:
            Path to exported file

        Raises:
            ValueError: If trajectory_id is not a valid UUID
        """
        # Validate trajectory_id is a UUID
        try:
            UUID(trajectory_id)
        except ValueError as exc:
            raise ValueError(
                f"Invalid trajectory_id '{trajectory_id}'. Must be a valid UUID."
            ) from exc

        client = await self._get_client()

        # Get trajectory data
        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            params={
                "id": f"eq.{trajectory_id}",
                "select": "id,session_id,trajectory_data,event_count,task_type,environment",
            },
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get trajectory: {resp.text}")

        trajectories = resp.json()
        if not trajectories:
            raise ValueError(f"Trajectory not found: {trajectory_id}")

        trajectory = trajectories[0]

        # Generate output path
        if not output_path:
            output_path = f"/tmp/trajectory_{trajectory_id}.json"

        # Write to file
        with open(output_path, "w") as f:
            json.dump(trajectory, f, indent=2)

        logger.info("Exported trajectory %s to %s", trajectory_id, output_path)
        return output_path

    async def prepare_dataset(
        self,
        trajectory_ids: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Prepare dataset from trajectories in HuggingFace format.

        Args:
            trajectory_ids: List of trajectory IDs to include
            session_id: Alternative: include all trajectories from a session

        Returns:
            Path to prepared dataset directory
        """
        client = await self._get_client()

        # Collect trajectory data
        trajectories = []
        if trajectory_ids:
            for tid in trajectory_ids:
                resp = await client.get(
                    f"{self.supabase_url}/rest/v1/agentgym_trajectories",
                    headers=self._headers,
                    params={
                        "id": f"eq.{tid}",
                        "select": "*",
                    },
                )
                if resp.status_code == 200:
                    trajectories.extend(resp.json())
        elif session_id:
            resp = await client.get(
                f"{self.supabase_url}/rest/v1/agentgym_trajectories",
                headers=self._headers,
                params={
                    "session_id": f"eq.{session_id}",
                    "select": "*",
                },
            )
            if resp.status_code == 200:
                trajectories = resp.json()

        if not trajectories:
            raise ValueError("No trajectories found")

        # Create dataset directory
        dataset_dir = tempfile.mkdtemp(prefix="agentgym_dataset_")

        # Convert to HuggingFace format
        # Each trajectory becomes a row with prompt + trajectory data
        dataset_rows = []
        for traj in trajectories:
            traj_data = traj.get("trajectory_data", {})
            session_id = traj.get("session_id", "")

            # Extract events and format as dataset entries
            for _event_key, event_val in traj_data.items():
                if isinstance(event_val, dict) and "data" in event_val:
                    data = event_val["data"]
                    dataset_rows.append({
                        "prompt": f"AgentGym session {session_id}",
                        "session_id": session_id,
                        "task_type": traj.get("task_type"),
                        "environment": traj.get("environment"),
                        "event": event_val.get("event_type"),
                        "timestamp": event_val.get("timestamp"),
                        "data": data,
                    })

        # Write as JSON (HuggingFace datasets can load this)
        dataset_path = os.path.join(dataset_dir, "dataset.json")
        with open(dataset_path, "w") as f:
            json.dump(dataset_rows, f, indent=2)

        # Write dataset card
        card_path = os.path.join(dataset_dir, "README.md")
        with open(card_path, "w") as f:
            f.write(f"""---
license: mit
task_categories:
  - reinforcement-learning
language:
  - en
---

# AgentGym RL Dataset

Dataset generated from AgentGym RL training trajectories.

## Statistics

- Trajectories: {len(trajectories)}
- Total Events: {sum(t.get('event_count', 0) for t in trajectories)}
- Rows: {len(dataset_rows)}
- Generated: {datetime.now().isoformat()}

## Usage

```python
from datasets import load_dataset

dataset = load_dataset('{os.path.abspath(dataset_dir)}')
```
""")

        logger.info(
            "Prepared dataset with %d rows at %s",
            len(dataset_rows),
            dataset_dir,
        )
        return dataset_dir

    async def publish_to_huggingface(
        self,
        dataset_name: str,
        trajectory_ids: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        private: bool = False,
    ) -> Dict[str, Any]:
        """Publish dataset to HuggingFace Hub.

        Args:
            dataset_name: Name for the dataset
            trajectory_ids: List of trajectory IDs to include
            session_id: Alternative: include all trajectories from a session
            private: Whether to create a private dataset

        Returns:
            Publication result with dataset_id and repo_url

        Raises:
            ValueError: If HF_TOKEN not configured or huggingface_hub not installed
            RuntimeError: If publishing fails
        """
        if not self.hf_token:
            raise ValueError(
                "HF_TOKEN not configured. Set HF_TOKEN environment variable."
            )

        # Prepare dataset
        dataset_dir = await self.prepare_dataset(trajectory_ids, session_id)

        # Full repo name
        full_repo_name = f"{self.hf_org}/{dataset_name}"

        logger.info(
            "Publishing dataset to HuggingFace: %s (private=%s)",
            full_repo_name,
            private,
        )

        try:
            from huggingface_hub import HfApi
        except ImportError:
            raise RuntimeError(
                "huggingface_hub package not installed. "
                "Install with: pip install huggingface_hub"
            )

        # Use HuggingFace Hub API
        api = HfApi(token=self.hf_token)

        try:
            # Create repository
            repo_url = api.create_repo(
                repo_id=full_repo_name,
                private=private,
                repo_type="dataset",
                exist_ok=True,
            )
            logger.info("Created HuggingFace repository: %s", full_repo_name)
        except Exception as e:
            logger.error("Failed to create HuggingFace repo: %s", e)
            raise RuntimeError(f"Failed to create HuggingFace repository: {e}") from e

        try:
            # Upload dataset files
            api.upload_folder(
                repo_id=full_repo_name,
                folder_path=dataset_dir,
                repo_type="dataset",
            )
            logger.info("Uploaded dataset files to: %s", full_repo_name)
        except Exception as e:
            logger.error("Failed to upload dataset: %s", e)
            raise RuntimeError(f"Failed to upload dataset: {e}") from e

        result = {
            "dataset_id": full_repo_name,
            "repo_url": f"https://huggingface.co/datasets/{full_repo_name}",
            "private": private,
        }

        logger.info("Dataset published: %s", result["repo_url"])

        # Mark trajectories as published
        client = await self._get_client()
        if trajectory_ids:
            for tid in trajectory_ids:
                await client.patch(
                    f"{self.supabase_url}/rest/v1/agentgym_trajectories?id=eq.{tid}",
                    headers=self._headers,
                    json={
                        "published_to_hf": True,
                        "hf_dataset_id": full_repo_name,
                        "hf_repo_url": result["repo_url"],
                    },
                )

        return result

    async def list_published_datasets(self) -> List[Dict[str, Any]]:
        """List all published HuggingFace datasets.

        Returns:
            List of published dataset references
        """
        client = await self._get_client()

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_trajectories",
            headers=self._headers,
            params={
                "published_to_hf": "eq.true",
                "select": "id,hf_dataset_id,hf_repo_url,created_at",
                "order": "created_at.desc",
            },
        )

        if resp.status_code != 200:
            logger.error("Failed to list published datasets: %s", resp.text[:200])
            return []

        trajectories = resp.json()

        # Group by dataset
        datasets = {}
        for traj in trajectories:
            dataset_id = traj.get("hf_dataset_id")
            if dataset_id and dataset_id not in datasets:
                datasets[dataset_id] = {
                    "dataset_id": dataset_id,
                    "repo_url": traj.get("hf_repo_url"),
                    "created_at": traj.get("created_at"),
                    "trajectory_count": 1,
                }
            elif dataset_id:
                datasets[dataset_id]["trajectory_count"] += 1

        return list(datasets.values())
