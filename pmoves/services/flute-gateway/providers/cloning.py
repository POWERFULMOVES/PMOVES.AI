"""Voice Cloning Provider for Flute Gateway.

Implements voice cloning workflow using RVC (Retrieval-based Voice Conversion).
This module handles:
- Voice sample registration and validation
- Training status tracking
- Cloned voice synthesis

The actual RVC training is performed by the Ultimate-TTS GPU service.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional

import httpx

from .base import VoiceProvider

logger = logging.getLogger("flute-gateway.cloning")

# NATS subject for voice training requests
VOICE_TRAINING_SUBJECT = "voice.training.request.v1"


class VoiceCloningProvider:
    """Voice cloning provider using RVC (Retrieval-based Voice Conversion).

    This provider manages the voice cloning workflow:
    1. Register voice sample → store in MinIO
    2. Trigger training → GPU service trains RVC model
    3. Monitor status → track progress via Supabase
    4. Synthesize with cloned voice → use trained model
    """

    # Training states
    STATUS_PENDING = "pending"
    STATUS_TRAINING = "training"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        ultimate_tts_url: str,
        presign_url: Optional[str] = None,
        nats_client: Optional[Any] = None,
    ):
        """Initialize voice cloning provider.

        Args:
            supabase_url: Supabase API URL
            supabase_key: Supabase service role key
            ultimate_tts_url: Ultimate-TTS service URL for GPU training
            presign_url: Presign service URL for MinIO access
            nats_client: Optional NATS client for async training triggers
        """
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_key = supabase_key
        self.ultimate_tts_url = ultimate_tts_url.rstrip("/")
        self.presign_url = presign_url.rstrip("/") if presign_url else None
        self.nats_client = nats_client

        self._client: Optional[httpx.AsyncClient] = None
        self._headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def register_voice_sample(
        self,
        persona_slug: str,
        sample_audio_data: bytes,
        sample_format: str = "wav",
    ) -> Dict[str, Any]:
        """Register a voice sample for cloning.

        Args:
            persona_slug: Voice persona slug to attach sample to
            sample_audio_data: Audio bytes (WAV/MP3 format)
            sample_format: Audio format (wav, mp3)

        Returns:
            Dict with persona_id, status, and message

        Raises:
            httpx.HTTPError: If registration fails
        """
        client = await self._get_client()

        # Step 1: Get persona by slug
        resp = await client.get(
            f"{self.supabase_url}/rest/v1/voice_persona",
            headers=self._headers,
            params={"slug": f"eq.{persona_slug}", "select": "id"},
        )
        if resp.status_code != 200:
            raise ValueError(f"Persona not found: {persona_slug}")
        personas = resp.json()
        if not personas:
            raise ValueError(f"Persona not found: {persona_slug}")
        persona_id = personas[0]["id"]

        # Step 2: Upload sample to MinIO (via presigned URL)
        sample_uri = await self._upload_sample(
            persona_id=persona_id,
            audio_data=sample_audio_data,
            audio_format=sample_format,
        )

        # Step 3: Update persona with sample URI and pending status
        update_data = {
            "voice_sample_uri": sample_uri,
            "voice_cloning_status": "pending",
            "training_progress": 0,
            "training_message": "Queued for training",
        }
        resp = await client.patch(
            f"{self.supabase_url}/rest/v1/voice_persona?id=eq.{persona_id}",
            headers=self._headers,
            json=update_data,
        )
        if resp.status_code not in [200, 204]:
            raise RuntimeError(f"Failed to update persona: {resp.text}")

        logger.info(
            "Registered voice sample for persona %s: %s",
            persona_slug,
            sample_uri,
        )

        return {
            "persona_id": str(persona_id),
            "status": "pending",
            "sample_uri": sample_uri,
            "message": "Voice sample registered. Use /v1/voice/clone/train to start training.",
        }

    async def _upload_sample(
        self,
        persona_id: str,
        audio_data: bytes,
        audio_format: str,
    ) -> str:
        """Upload voice sample to MinIO via presigned URL.

        Args:
            persona_id: UUID of voice persona
            audio_data: Audio bytes
            audio_format: Audio format (wav, mp3)

        Returns:
            MinIO URI for uploaded file

        Raises:
            RuntimeError: If PRESIGN_URL not configured or upload fails
        """
        if not self.presign_url:
            raise RuntimeError(
                "Voice sample upload requires PRESIGN_URL to be configured. "
                "Set PRESIGN_URL environment variable to enable MinIO uploads "
                "(via pmoves/services/presign service)."
            )

        client = await self._get_client()
        object_name = f"voice-samples/{persona_id}.{audio_format}"

        # Step 1: Get presigned PUT URL from presign service
        presign_resp = await client.post(
            f"{self.presign_url}/presign",
            params={"object_name": object_name, "operation": "put"},
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )

        if presign_resp.status_code != 200:
            raise RuntimeError(
                f"Failed to get presigned URL from presign service: "
                f"HTTP {presign_resp.status_code} - {presign_resp.text[:200]}"
            )

        presigned_url = presign_resp.json().get("url")
        if not presigned_url:
            raise RuntimeError("Presign service returned no URL in response")

        # Step 2: Upload audio data to MinIO using presigned URL
        upload_resp = await client.put(
            presigned_url,
            content=audio_data,
            headers={
                "Content-Type": f"audio/{audio_format}",
                "Content-Length": str(len(audio_data)),
            },
            timeout=60.0,
        )

        if upload_resp.status_code not in [200, 201]:
            raise RuntimeError(
                f"MinIO upload failed: HTTP {upload_resp.status_code} - {upload_resp.text[:200]}"
            )

        logger.info(
            "Uploaded voice sample: %s (%d bytes)",
            object_name,
            len(audio_data),
        )

        return f"minio://{object_name}"

    async def start_training(
        self,
        persona_id: str,
    ) -> Dict[str, Any]:
        """Start RVC training for a registered voice sample.

        Args:
            persona_id: UUID of voice persona with registered sample

        Returns:
            Dict with training job ID and status

        Raises:
            ValueError: If persona not found or no sample registered
            RuntimeError: If training fails to start
        """
        client = await self._get_client()

        # Step 1: Get persona and verify sample exists
        resp = await client.get(
            f"{self.supabase_url}/rest/v1/voice_persona",
            headers=self._headers,
            params={"id": f"eq.{persona_id}", "select": "*"},
        )
        if resp.status_code != 200:
            raise ValueError(f"Persona not found: {persona_id}")
        personas = resp.json()
        if not personas:
            raise ValueError(f"Persona not found: {persona_id}")

        persona = personas[0]
        if not persona.get("voice_sample_uri"):
            raise ValueError("No voice sample registered. Use /v1/voice/clone/register first.")

        # Step 2: Update status to training
        update_resp = await client.patch(
            f"{self.supabase_url}/rest/v1/voice_persona?id=eq.{persona_id}",
            headers=self._headers,
            json={
                "voice_cloning_status": "training",
                "training_progress": 0,
                "training_message": "Training started",
                "training_started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if update_resp.status_code not in [200, 204]:
            raise RuntimeError(f"Failed to update persona status: {update_resp.text}")

        # Step 3: Trigger training job via NATS
        training_event = {
            "type": "voice_cloning_training_request",
            "persona_id": str(persona_id),
            "sample_uri": persona["voice_sample_uri"],
            "slug": persona.get("slug", "unknown"),
            "rvc_config": {
                "model_name": "RVC_v2",
                "sample_rate": 48000,
                "epochs": 100,
                "batch_size": 8,
            },
            "callback_url": f"{self.supabase_url}/rest/v1/voice_persona",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Try to publish via NATS if available
        if self.nats_client and hasattr(self.nats_client, 'is_connected') and self.nats_client.is_connected:
            try:
                await self.nats_client.publish(
                    VOICE_TRAINING_SUBJECT,
                    json.dumps(training_event).encode("utf-8"),
                )
                logger.info(
                    "Published training request to NATS subject '%s' for persona %s",
                    VOICE_TRAINING_SUBJECT,
                    persona_id,
                )
            except Exception as nats_err:
                logger.error("Failed to publish to NATS: %s", nats_err)
                # Revert status on NATS failure
                await client.patch(
                    f"{self.supabase_url}/rest/v1/voice_persona?id=eq.{persona_id}",
                    headers=self._headers,
                    json={
                        "voice_cloning_status": "pending",
                        "training_message": f"NATS publish failed: {nats_err}",
                    }
                )
                raise RuntimeError(
                    f"Failed to publish training request to NATS: {nats_err}"
                ) from nats_err
        else:
            # Fallback: Direct API call to Ultimate-TTS service
            logger.warning(
                "NATS not available, using direct API call to %s",
                self.ultimate_tts_url
            )
            try:
                # Call Ultimate-TTS training endpoint
                # This assumes the Ultimate-TTS service has a training endpoint
                training_resp = await client.post(
                    f"{self.ultimate_tts_url}/api/train_rvc",
                    json=training_event,
                    timeout=10.0,
                )
                if training_resp.status_code not in [200, 201, 202]:
                    raise RuntimeError(
                        f"Ultimate-TTS training request failed: HTTP {training_resp.status_code}"
                    )
            except Exception as api_err:
                logger.error("Direct API training request failed: %s", api_err)
                # Revert status on API failure
                await client.patch(
                    f"{self.supabase_url}/rest/v1/voice_persona?id=eq.{persona_id}",
                    headers=self._headers,
                    json={
                        "voice_cloning_status": "pending",
                        "training_message": f"API request failed: {api_err}",
                    },
                )
                raise

        return {
            "persona_id": str(persona_id),
            "status": "training",
            "message": "Training job started",
        }

    async def get_training_status(
        self,
        persona_id: str,
    ) -> Dict[str, Any]:
        """Get training status for a voice clone.

        Args:
            persona_id: UUID of voice persona

        Returns:
            Dict with status, progress, and model URIs
        """
        client = await self._get_client()

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/voice_persona",
            headers=self._headers,
            params={
                "id": f"eq.{persona_id}",
                "select": "voice_cloning_status,training_progress,training_message,rvc_model_uri,rvc_index_uri,training_started_at,training_completed_at",
            },
        )
        if resp.status_code != 200:
            raise ValueError(f"Persona not found: {persona_id}")
        personas = resp.json()
        if not personas:
            raise ValueError(f"Persona not found: {persona_id}")

        return {
            "persona_id": persona_id,
            **personas[0],
        }

    async def synthesize_cloned(
        self,
        text: str,
        persona_id: str,
    ) -> bytes:
        """Synthesize speech using a cloned voice.

        Args:
            text: Text to synthesize
            persona_id: UUID of voice persona with trained model

        Returns:
            Audio bytes (WAV format)

        Raises:
            ValueError: If persona not found or training incomplete
            RuntimeError: If synthesis fails
        """
        client = await self._get_client()

        # Step 1: Get persona and verify training completed
        resp = await client.get(
            f"{self.supabase_url}/rest/v1/voice_persona",
            headers=self._headers,
            params={
                "id": f"eq.{persona_id}",
                "select": "voice_cloning_status,rvc_model_uri,rvc_index_uri,slug",
            },
        )
        if resp.status_code != 200:
            raise ValueError(f"Persona not found: {persona_id}")
        personas = resp.json()
        if not personas:
            raise ValueError(f"Persona not found: {persona_id}")

        persona = personas[0]
        if persona.get("voice_cloning_status") != "completed":
            raise ValueError(
                f"Voice training not complete. Current status: {persona.get('voice_cloning_status')}"
            )

        # Step 2: Call Ultimate-TTS with RVC model
        # For now, this is a placeholder that would use the trained model
        # In production, call Ultimate-TTS with custom model parameters
        model_uri = persona.get("rvc_model_uri")
        index_uri = persona.get("rvc_index_uri")

        logger.info(
            "Synthesizing with cloned voice %s (model=%s, index=%s)",
            persona.get("slug"),
            model_uri,
            index_uri,
        )

        # In production:
        # audio = await ultimate_tts_provider.synthesize_with_rvc(
        #     text=text,
        #     rvc_model=model_uri,
        #     rvc_index=index_uri,
        # )

        # TODO: Integrate with Ultimate-TTS RVC synthesis endpoint
        raise NotImplementedError(
            "Cloned voice synthesis requires GPU service integration. "
            "Use Ultimate-TTS directly with the trained model for now."
        )

    async def list_training_jobs(
        self,
        status: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        """List all voice cloning training jobs.

        Args:
            status: Filter by status (pending, training, completed, failed)

        Returns:
            List of training job summaries
        """
        client = await self._get_client()

        params = {
            "select": "id,slug,name,voice_cloning_status,training_progress,training_message,training_started_at,training_completed_at",
            "order": "training_started_at.desc",
        }
        if status:
            params["voice_cloning_status"] = f"eq.{status}"

        resp = await client.get(
            f"{self.supabase_url}/rest/v1/voice_persona",
            headers=self._headers,
            params=params,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to query training jobs: {resp.text}")

        return resp.json()

    async def health_check(self) -> bool:
        """Check if voice cloning service is available."""
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.supabase_url}/rest/v1/voice_persona",
                headers=self._headers,
                params={"select": "id", "limit": "1"},
            )
            return resp.status_code == 200
        except (httpx.HTTPError, httpx.TimeoutException):
            return False


# Extend VoiceProvider base for compatibility (optional)
class CloningSynthesisProvider(VoiceProvider):
    """Voice provider for synthesis with cloned voices.

    This wraps the VoiceCloningProvider to implement the VoiceProvider interface
    for synthesis with trained RVC models.
    """

    def __init__(self, cloning_provider: VoiceCloningProvider):
        """Initialize with voice cloning provider."""
        super().__init__("<internal>")
        self.cloning = cloning_provider

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Synthesize with cloned voice.

        Args:
            text: Text to synthesize
            voice: Persona ID (UUID) with trained model
            **kwargs: Additional parameters

        Returns:
            Audio bytes
        """
        persona_id = voice or kwargs.get("persona_id")
        if not persona_id:
            raise ValueError("persona_id required for cloned voice synthesis")

        return await self.cloning.synthesize_cloned(text, persona_id)

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """Stream synthesis with cloned voice."""
        audio = await self.synthesize(text, voice, **kwargs)
        # Yield in chunks
        chunk_size = 4096
        for i in range(0, len(audio), chunk_size):
            yield audio[i : i + chunk_size]

    async def recognize(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Voice cloning doesn't support STT."""
        raise NotImplementedError("Voice cloning provider doesn't support speech recognition")

    async def health_check(self) -> bool:
        """Check if provider is available."""
        return await self.cloning.health_check()
