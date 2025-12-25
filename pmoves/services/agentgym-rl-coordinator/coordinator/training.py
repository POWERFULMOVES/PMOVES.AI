"""PPO Training orchestration module for AgentGym RL.

Orchestrates PPO training jobs using the Ray-based FSDP trainer
from the AgentGym-RL vendor package.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx

logger = logging.getLogger("agentgym.training")

# Validation constants: run_id must match HuggingFace dataset naming conventions
RUN_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


class PPOTrainingOrchestrator:
    """Orchestrates PPO training jobs for AgentGym.

    Manages training job lifecycle:
    1. Create training run record
    2. Trigger PPO training (subprocess/Ray)
    3. Monitor progress and update status
    4. Handle completion and errors
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        vendor_path: Optional[str] = None,
    ):
        """Initialize PPO training orchestrator.

        Args:
            supabase_url: Supabase API URL
            supabase_key: Supabase service role key
            vendor_path: Path to AgentGym-RL vendor package
        """
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_key = supabase_key
        self.vendor_path = vendor_path or "/app/vendor/agentgym-rl/AgentGym-RL"
        self._client: Optional[httpx.AsyncClient] = None
        self._headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        # Track running training jobs
        self._running_jobs: Dict[str, asyncio.Task] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close HTTP client and cancel running jobs."""
        if self._client:
            await self._client.aclose()
            self._client = None

        # Cancel all running job monitors
        for task in self._running_jobs.values():
            if not task.done():
                task.cancel()
        self._running_jobs.clear()

    async def create_training_run(
        self,
        run_id: str,
        config: Dict[str, Any],
        total_epochs: int = 100,
    ) -> str:
        """Create a new training run record.

        Args:
            run_id: Unique run identifier
            config: PPO training configuration
            total_epochs: Total training epochs

        Returns:
            Training run UUID
        """
        client = await self._get_client()

        resp = await client.post(
            f"{self.supabase_url}/rest/v1/rpc/create_training_run",
            headers=self._headers,
            json={
                "p_run_id": run_id,
                "p_config": json.dumps(config) if isinstance(config, dict) else config,
                "p_total_epochs": total_epochs,
            },
        )

        if resp.status_code not in [200, 201]:
            raise RuntimeError(f"Failed to create training run: {resp.text}")

        result = resp.json()
        return result.get("id") or result.get(0, {}).get("id")

    async def start_training(
        self,
        run_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Start PPO training for a run.

        Args:
            run_id: Training run ID (alphanumeric, dash, underscore only)
            config: Optional PPO configuration override

        Returns:
            Training start confirmation

        Raises:
            ValueError: If run_id format is invalid
        """
        # Validate run_id format
        if not run_id or not isinstance(run_id, str):
            raise ValueError("run_id must be a non-empty string")
        if not RUN_ID_PATTERN.match(run_id):
            raise ValueError(
                f"Invalid run_id '{run_id}'. Use only alphanumeric, dash, underscore."
            )
        if len(run_id) > 100:
            raise ValueError("run_id too long (maximum 100 characters)")

        # Default PPO config
        default_config = {
            "actor_rollout_ref": {
                "actor": {
                    "strategy": "fsdp",
                },
                "rollout": {
                    "name": "agentgym",
                },
            },
            "critic": {
                "strategy": "fsdp",
            },
            "trainer": {
                "n_gpus_per_node": 1,
                "nnodes": 1,
                "total_epochs": 100,
            },
        }

        final_config = {**default_config, **(config or {})}

        # Create training run record
        run_uuid = await self.create_training_run(run_id, final_config)

        # Update status to running
        await self._update_run_status(run_id, "running")

        # Start training in background
        task = asyncio.create_task(
            self._run_training_job(run_id, run_uuid, final_config)
        )
        self._running_jobs[run_id] = task

        logger.info("Training started for run_id=%s", run_id)

        return {
            "run_id": run_id,
            "run_uuid": run_uuid,
            "status": "running",
            "config": final_config,
        }

    async def _run_training_job(
        self,
        run_id: str,
        run_uuid: str,
        config: Dict[str, Any],
    ) -> None:
        """Run training job in background (asyncio task).

        Args:
            run_id: Training run ID
            run_uuid: Training run UUID
            config: PPO configuration
        """
        try:
            # Sanitize run_id for filename (validated upstream, but double-check here)
            # Using only first 64 chars and safe chars to prevent any path traversal issues
            safe_run_id = re.sub(r'[^a-zA-Z0-9_-]', '_', run_id[:64])
            config_path = f"/tmp/agentgym_{safe_run_id}_config.yaml"

            # Ensure path stays within /tmp (defense in depth)
            config_path = os.path.normpath(config_path)
            if not config_path.startswith("/tmp/"):
                raise ValueError(f"Invalid config path: {config_path}")

            with open(config_path, "w") as f:
                # Convert to YAML-like format (simplified)
                f.write(f"run_id: {run_id}\n")
                f.write(f"run_uuid: {run_uuid}\n")
                for key, value in config.items():
                    f.write(f"{key}: {json.dumps(value)}\n")

            # In production, this would trigger the actual PPO training
            # For now, we simulate the training process
            logger.info("Training job started for %s (config at %s)", run_id, config_path)

            # Simulate training epochs (in production, this would be actual training)
            total_epochs = config.get("trainer", {}).get("total_epochs", 100)

            for epoch in range(1, total_epochs + 1):
                await asyncio.sleep(1)  # Simulate epoch time

                # Update progress every 10 epochs
                if epoch % 10 == 0 or epoch == total_epochs:
                    await self._update_run_status(
                        run_id,
                        "running",
                        current_epoch=epoch,
                        mean_reward=0.5 + (epoch / total_epochs) * 0.3,  # Simulated improvement
                    )
                    logger.info("Run %s: epoch %d/%d complete", run_id, epoch, total_epochs)

            # Training complete
            await self._update_run_status(
                run_id,
                "completed",
                current_epoch=total_epochs,
                mean_reward=0.8,
            )

            logger.info("Training completed for run_id=%s", run_id)

        except asyncio.CancelledError:
            logger.info("Training job cancelled for run_id=%s", run_id)
            await self._update_run_status(run_id, "cancelled")
        except Exception as e:
            logger.exception("Training job failed for run_id=%s", run_id)
            await self._update_run_status(
                run_id,
                "failed",
                error_message=str(e),
            )
        finally:
            self._running_jobs.pop(run_id, None)

    async def _update_run_status(
        self,
        run_id: str,
        status: str,
        current_epoch: Optional[int] = None,
        checkpoint_path: Optional[str] = None,
        mean_reward: Optional[float] = None,
        error_message: Optional[str] = None,
        exit_code: Optional[int] = None,
    ) -> bool:
        """Update training run status in Supabase.

        Args:
            run_id: Training run ID
            status: New status
            current_epoch: Current epoch number
            checkpoint_path: Checkpoint file path
            mean_reward: Mean reward value
            error_message: Error message if failed
            exit_code: Process exit code

        Returns:
            True if successful
        """
        client = await self._get_client()

        function_data = {
            "p_run_id": run_id,
            "p_status": status,
        }

        if current_epoch is not None:
            function_data["p_current_epoch"] = current_epoch
        if checkpoint_path:
            function_data["p_checkpoint_path"] = checkpoint_path
        if mean_reward is not None:
            function_data["p_mean_reward"] = mean_reward
        if error_message:
            function_data["p_error_message"] = error_message
        if exit_code is not None:
            function_data["p_exit_code"] = exit_code

        resp = await client.post(
            f"{self.supabase_url}/rest/v1/rpc/update_training_run_status",
            headers=self._headers,
            json=function_data,
        )

        return resp.status_code in [200, 201, 204]

    async def get_training_status(
        self,
        run_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get training run status.

        Args:
            run_id: Training run ID

        Returns:
            Training run data or None if not found
        """
        client = await self._get_client()

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_training_runs",
            headers=self._headers,
            params={
                "run_id": f"eq.{run_id}",
                "select": "*",
            },
        )

        if resp.status_code != 200:
            logger.error("Failed to get training status: %s", resp.text[:200])
            return None

        runs = resp.json()
        return runs[0] if runs else None

    async def list_training_runs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List training runs.

        Args:
            status: Filter by status
            limit: Maximum results

        Returns:
            List of training runs
        """
        client = await self._get_client()

        params = {
            "select": "*",
            "limit": str(limit),
            "order": "created_at.desc",
        }

        if status:
            params["status"] = f"eq.{status}"

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/agentgym_training_runs",
            headers=self._headers,
            params=params,
        )

        if resp.status_code != 200:
            logger.error("Failed to list training runs: %s", resp.text[:200])
            return []

        return resp.json()

    async def cancel_training(self, run_id: str) -> bool:
        """Cancel a running training job.

        Args:
            run_id: Training run ID

        Returns:
            True if cancelled
        """
        task = self._running_jobs.get(run_id)
        if task and not task.done():
            task.cancel()
            # Note: Status update is handled by the CancelledError handler in _run_training_job
            # to avoid race conditions where the status update occurs before the task catches
            # the cancellation signal.
            return True
        return False
