"""Supabase client for model deployment tracking.

This module provides integration with the PMOVES model registry,
syncing model deployments from the GPU Orchestrator to Supabase.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


class SupabaseRegistryClient:
    """Client for syncing model deployments to Supabase model registry.

    This client registers model load/unload events in the Supabase
    pmoves_core.model_deployments table, enabling centralized tracking
    of which models are loaded on which GPU nodes.
    """

    def __init__(self):
        """Initialize the Supabase client from environment settings."""
        settings = get_settings()
        self.supabase_url = settings.supabase_url
        self.supabase_key = settings.supabase_service_key
        self.node_id = settings.node_id
        self.enabled = bool(self.supabase_url and self.supabase_key)

        if self.enabled:
            self.headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            }
        else:
            logger.info("Supabase registry client disabled (no credentials configured)")

    async def register_deployment(
        self,
        model_id: str,
        provider: str,
        status: str = "loaded",
        vram_mb: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Dict]:
        """Register or update a model deployment in Supabase.

        Args:
            model_id: Model identifier (e.g., "qwen3:8b")
            provider: Provider type (ollama, vllm, tts)
            status: Deployment status (loading, loaded, unloaded, error)
            vram_mb: VRAM allocated in MB
            error_message: Error message if status is "error"

        Returns:
            Supabase response if enabled, None otherwise
        """
        if not self.enabled:
            return None

        # First, find the model UUID by model_id and provider type
        model_uuid = await self._find_model_uuid(model_id, provider)
        if not model_uuid:
            logger.warning(f"Model {provider}/{model_id} not found in registry")
            return None

        # Check for existing deployment
        existing = await self._find_deployment(model_uuid)

        data = {
            "model_id": model_uuid,
            "node_id": self.node_id,
            "provider_type": provider,
            "status": status,
            "vram_allocated_mb": vram_mb,
            "loaded_at": datetime.utcnow().isoformat() if status == "loaded" else None,
            "last_used_at": datetime.utcnow().isoformat(),
            "error_message": error_message,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if existing:
                    # Update existing deployment
                    url = f"{self.supabase_url}/rest/v1/model_deployments?id=eq.{existing['id']}"
                    response = await client.patch(url, json=data, headers=self.headers)
                else:
                    # Create new deployment
                    url = f"{self.supabase_url}/rest/v1/model_deployments"
                    response = await client.post(url, json=data, headers=self.headers)

                if response.status_code in (200, 201):
                    logger.debug(f"Registered deployment: {provider}/{model_id} -> {status}")
                    return response.json()
                else:
                    logger.error(f"Failed to register deployment: {response.status_code} {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error registering deployment for {provider}/{model_id}: {e}")
            return None

    async def update_deployment_status(
        self,
        model_id: str,
        provider: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[Dict]:
        """Update the status of an existing deployment.

        Args:
            model_id: Model identifier
            provider: Provider type
            status: New status
            error_message: Optional error message

        Returns:
            Supabase response if enabled, None otherwise
        """
        return await self.register_deployment(model_id, provider, status, None, error_message)

    async def _find_model_uuid(self, model_id: str, provider: str) -> Optional[str]:
        """Find a model UUID by model_id and provider type.

        Args:
            model_id: Model identifier (e.g., "qwen3:8b")
            provider: Provider type

        Returns:
            Model UUID if found, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Query via v_active_models view
                url = f"{self.supabase_url}/rest/v1/v_active_models"
                params = {
                    "model_id": f"eq.{model_id}",
                    "provider_type": f"eq.{provider}",
                }
                response = await client.get(url, params=params, headers=self.headers)

                if response.status_code == 200:
                    results = response.json()
                    if results:
                        return results[0]["id"]
        except Exception as e:
            logger.error(f"Error finding model UUID for {provider}/{model_id}: {e}")

        return None

    async def _find_deployment(self, model_uuid: str) -> Optional[Dict]:
        """Find existing deployment for a model on this node.

        Args:
            model_uuid: Model UUID

        Returns:
            Existing deployment record if found, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{self.supabase_url}/rest/v1/model_deployments"
                params = {
                    "model_id": f"eq.{model_uuid}",
                    "node_id": f"eq.{self.node_id}",
                }
                response = await client.get(url, params=params, headers=self.headers)

                if response.status_code == 200:
                    results = response.json()
                    if results:
                        return results[0]
        except Exception as e:
            logger.error(f"Error finding deployment for {model_uuid}: {e}")

        return None

    async def get_active_deployments(self) -> list:
        """Get all active deployments from Supabase.

        Returns:
            List of active deployments
        """
        if not self.enabled:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{self.supabase_url}/rest/v1/v_active_deployments"
                response = await client.get(url, headers=self.headers)

                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.error(f"Error getting active deployments: {e}")

        return []
