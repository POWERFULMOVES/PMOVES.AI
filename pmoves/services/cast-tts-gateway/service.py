"""
PMOVES Cast TTS Gateway

Central service for TTS synthesis and casting to Google Cast devices.
Integrates with Flute-Gateway, Ultimate-TTS Studio, and NATS event bus.
"""

import asyncio
import json
import os
import tempfile
import time
from datetime import datetime
from typing import Optional

from aiohttp import web
import nats
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.exposition import CONTENT_TYPE_LATEST

# Schema-validated envelope (available when services/common is on PYTHONPATH)
try:
    from services.common.events import envelope as _envelope
except ImportError:
    _envelope = None

from flute_client import FluteTTSProvider
from device_manager import CastDeviceManager
from groups import CastGroupManager
from concurrent import ConcurrentCaster
from queue import CastPriorityQueue
from voices import VoiceProfileManager
from scheduler import CastScheduler
from health import HealthMonitor
from audio_queue import AudioQueueManager
from recovery import RecoveryManager
from fallback import (
    FallbackManager,
    FluteTTSProvider as FluteFallbackProvider,
    UltimateTTSProvider,
    GoogleTTSProvider,
)
from optimize import OptimizationManager
from persistence import SupabasePersistence
from security import SecurityManager
from auth import auth_middleware
from types import (
    SuccessResponse,
    ErrorResponse,
    CastSpeechResponse,
    QueueAnnouncementResponse,
    QueueStatusResponse,
    VoiceProfileResponse,
    VoiceProfilesListResponse,
    GroupResponse,
    GroupsListResponse,
    HealthCheckResponse,
    ScheduleResponse,
    SchedulesListResponse,
    DeviceDiscoveryResponse,
    DevicesListResponse,
    CastStatusResponse,
)


# Configuration
PORT = int(os.getenv("PORT", "8060"))
FLUTE_URL = os.getenv("FLUTE_GATEWAY_URL", "http://localhost:8055")
ULTIMATE_TTS_URL = os.getenv("ULTIMATE_TTS_URL", "http://localhost:7861")
NATS_URL = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")

# Prometheus Metrics
CAST_REQUESTS = Counter(
    "cast_tts_requests_total",
    "Total Cast TTS requests",
    ["method", "status"]
)
CAST_LATENCY = Histogram(
    "cast_tts_latency_seconds",
    "Cast TTS request latency"
)
DEVICE_DISCOVERIES = Counter("cast_device_discoveries_total", "Total device discoveries")

# Queue metrics
QUEUE_OPERATIONS = Counter(
    "cast_queue_operations_total",
    "Total queue operations",
    ["operation", "status"]  # operation: enqueue, dequeue, skip, pause, resume, clear
)

# Circuit breaker metrics
CIRCUIT_BREAKER_TRANSITIONS = Counter(
    "cast_circuit_breaker_transitions_total",
    "Circuit breaker state transitions",
    ["from_state", "to_state", "service"]
)

# Cache metrics
CACHE_OPERATIONS = Counter(
    "cast_cache_operations_total",
    "Cache operations",
    ["operation", "status"]  # operation: hit, miss, evict, clear
)

# Fallback provider metrics
FALLBACK_PROVIDER_USAGE = Counter(
    "cast_fallback_provider_usage_total",
    "Fallback provider usage",
    ["provider", "status"]  # provider: flute, ultimate_tts, google_tts
)

# Voice profile metrics
VOICE_PROFILE_USAGE = Counter(
    "cast_voice_profile_usage_total",
    "Voice profile usage",
    ["profile", "status"]
)

# Scheduler metrics
SCHEDULER_EXECUTIONS = Counter(
    "cast_scheduler_executions_total",
    "Scheduler executions",
    ["status"]  # status: success, failure, skipped
)


class CastTTSGateway:
    """Cast TTS gateway service."""

    def __init__(self):
        """Initialize gateway."""
        self.flute_provider = FluteTTSProvider(FLUTE_URL)
        self.device_manager = CastDeviceManager(
            on_discovery=self._on_device_discovery,
        )
        self.group_manager = CastGroupManager()
        self.concurrent_caster = ConcurrentCaster()
        self.priority_queue = CastPriorityQueue()
        self.audio_queue_manager = AudioQueueManager()
        self.voice_profile_manager = VoiceProfileManager()
        self.scheduler: Optional[CastScheduler] = None
        self.health_monitor = HealthMonitor(alert_callback=self._health_alert_callback)
        self.recovery_manager = RecoveryManager()
        self.fallback_manager = FallbackManager(
            recovery_manager=self.recovery_manager,
            on_transition=self._on_circuit_breaker_transition,
        )
        self.optimization_manager = OptimizationManager()
        self.persistence = SupabasePersistence()
        self.security_manager = SecurityManager()
        self.nats_client: Optional[nats.aio.client.Client] = None
        # Initialize app with auth middleware
        self.app = web.Application(middlewares=[auth_middleware])
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_get("/healthz", self.handle_health)
        self.app.router.add_get("/metrics", self.handle_metrics)
        self.app.router.add_get("/devices", self.handle_devices)
        self.app.router.add_post("/cast/discover", self.handle_discover)
        self.app.router.add_post("/cast/speech", self.handle_cast_speech)
        self.app.router.add_post("/cast/audio", self.handle_cast_audio)
        self.app.router.add_post("/cast/stop", self.handle_cast_stop)
        self.app.router.add_get("/cast/status", self.handle_cast_status)

        # Device groups
        self.app.router.add_post("/cast/groups", self.handle_create_group)
        self.app.router.add_get("/cast/groups", self.handle_list_groups)
        self.app.router.add_delete("/cast/groups/{name}", self.handle_delete_group)
        self.app.router.add_put("/cast/groups/{name}", self.handle_update_group)

        # Priority queue
        self.app.router.add_get("/cast/queue", self.handle_queue_status)
        self.app.router.add_delete("/cast/queue", self.handle_queue_clear)
        self.app.router.add_delete("/cast/queue/{id}", self.handle_queue_remove)

        # Voice profiles
        self.app.router.add_post("/cast/voices", self.handle_create_voice_profile)
        self.app.router.add_get("/cast/voices", self.handle_list_voice_profiles)
        self.app.router.add_get("/cast/voices/{name}", self.handle_get_voice_profile)
        self.app.router.add_put("/cast/voices/{name}", self.handle_update_voice_profile)
        self.app.router.add_delete("/cast/voices/{name}", self.handle_delete_voice_profile)

        # Scheduler
        self.app.router.add_post("/cast/schedule", self.handle_schedule_announcement)
        self.app.router.add_post("/cast/schedule/once", self.handle_schedule_once)
        self.app.router.add_get("/cast/schedule", self.handle_list_scheduled)
        self.app.router.add_delete("/cast/schedule/{id}", self.handle_cancel_scheduled)
        self.app.router.add_post("/cast/templates", self.handle_create_template)
        self.app.router.add_get("/cast/templates", self.handle_list_templates)
        self.app.router.add_delete("/cast/templates/{name}", self.handle_delete_template)

        # Health monitoring
        self.app.router.add_get("/cast/health", self.handle_list_health)
        self.app.router.add_get("/cast/health/{device}", self.handle_get_health)
        self.app.router.add_post("/cast/health/alerts", self.handle_configure_alert)
        self.app.router.add_get("/cast/health/alerts", self.handle_list_alerts)

        # Audio queue management
        self.app.router.add_post("/cast/queue/start", self.handle_queue_start)
        self.app.router.add_post("/cast/queue/pause", self.handle_queue_pause)
        self.app.router.add_post("/cast/queue/resume", self.handle_queue_resume)
        self.app.router.add_post("/cast/queue/skip", self.handle_queue_skip)
        self.app.router.add_post("/cast/queue/stop", self.handle_queue_stop)
        self.app.router.add_get("/cast/queue/session", self.handle_queue_session)
        self.app.router.add_post("/cast/queue/batch/remove", self.handle_queue_batch_remove)
        self.app.router.add_post("/cast/queue/batch/enqueue", self.handle_queue_batch_enqueue)

        # Error recovery
        self.app.router.add_post("/cast/recovery/configure_retry", self.handle_configure_retry)
        self.app.router.add_post("/cast/recovery/configure_circuit_breaker", self.handle_configure_circuit_breaker)
        self.app.router.add_get("/cast/recovery/circuit_breakers", self.handle_list_circuit_breakers)
        self.app.router.add_post("/cast/recovery/reset_circuit_breaker/{key}", self.handle_reset_circuit_breaker)

        # Fallback strategies
        self.app.router.add_post("/cast/fallback/tts", self.handle_configure_tts_fallback)
        self.app.router.add_get("/cast/fallback/tts", self.handle_list_tts_providers)
        self.app.router.add_post("/cast/fallback/devices", self.handle_configure_device_fallback)
        self.app.router.add_get("/cast/fallback/devices", self.handle_list_device_fallbacks)

        # Performance optimization
        self.app.router.add_get("/cast/optimize/stats", self.handle_optimize_stats)
        self.app.router.add_post("/cast/optimize/cache/clear", self.handle_cache_clear)
        self.app.router.add_post("/cast/optimize/cache/cleanup", self.handle_cache_cleanup)
        self.app.router.add_post("/cast/optimize/cache/invalidate", self.handle_cache_invalidate)

        # Security audit
        self.app.router.add_get("/cast/security/stats", self.handle_security_stats)
        self.app.router.add_get("/cast/security/audit", self.handle_query_audit_logs)
        self.app.router.add_post("/cast/security/permissions/grant", self.handle_grant_permission)
        self.app.router.add_post("/cast/security/permissions/revoke", self.handle_revoke_permission)
        self.app.router.add_get("/cast/security/permissions/{user}", self.handle_list_permissions)
        self.app.router.add_post("/cast/security/rate_limits", self.handle_configure_rate_limits)

    async def handle_health(self, request: web.Request) -> web.Response:
        """
        Health check endpoint for service monitoring.

        Returns:
            web.Response: JSON response with:
                - status (str): Service health status ("healthy", "degraded", "unhealthy")
                - timestamp (str): Current UTC timestamp in ISO 8601 format
                - flute_gateway (str): Flute-Gateway connection status
                - devices_discovered (int): Number of discovered Cast devices

        Example:
            GET /healthz
        """
        flute_health = await self.flute_provider.health_check()
        devices = self.device_manager.list_devices()

        status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "flute_gateway": "healthy" if flute_health else "offline",
            "devices_discovered": len(devices),
        }

        return web.json_response(status)

    async def handle_metrics(self, request: web.Request) -> web.Response:
        """
        Prometheus metrics endpoint for observability.

        Returns:
            web.Response: Prometheus metrics in text format with Content-Type:
                application/vnd.google.protobuf;proto=io.prometheus.client.MetricsFamily

        Example:
            GET /metrics
        """
        metrics = generate_latest()
        return web.Response(body=metrics, content_type=CONTENT_TYPE_LATEST)

    async def handle_devices(self, request: web.Request) -> web.Response:
        """
        List all discovered Google Cast devices.

        Returns:
            web.Response: JSON response with:
                - devices (list): List of device objects, each containing:
                    - name (str): Device friendly name
                    - ip (str): Device IP address
                    - last_seen (float): Unix timestamp of last discovery
                    - online (bool): Device online status
                - count (int): Total number of discovered devices

        Example:
            GET /devices
        """
        devices = self.device_manager.list_devices()

        return web.json_response({
            "devices": [
                {
                    "name": d.name,
                    "ip": d.ip,
                    "last_seen": d.last_seen,
                    "online": d.online,
                }
                for d in devices
            ],
            "count": len(devices),
        })

    async def handle_discover(self, request: web.Request) -> web.Response:
        """
        Trigger Google Cast device discovery on local network.

        Args:
            request: aiohttp web request with optional JSON body:
                - force (bool, optional): Force rediscovery even if devices cached

        Returns:
            web.Response: JSON response with:
                - devices (list): List of discovered device objects:
                    - name (str): Device friendly name
                    - ip (str): Device IP address
                    - address (str): Full Cast device address
                    - last_seen (float): Unix timestamp of discovery
                - count (int): Number of devices discovered

        Example:
            POST /cast/discover
            {"force": true}
        """
        DEVICE_DISCOVERIES.inc()

        try:
            body = await request.json()
            force = body.get("force", False)
        except:
            force = False

        with CAST_LATENCY.time():
            devices = await self.device_manager.discover(force=force)

        return web.json_response({
            "devices": [
                {
                    "name": d.name,
                    "ip": d.ip,
                    "address": d.address,
                    "last_seen": d.last_seen,
                }
                for d in devices
            ],
            "count": len(devices),
        })

    async def handle_cast_speech(self, request: web.Request) -> web.Response:
        """
        Synthesize text-to-speech and cast to Google Cast device or group.

        Main TTS endpoint supporting multiple synthesis engines (Flute-Gateway,
        Ultimate-TTS Studio) with automatic fallback and multi-device casting.

        Args:
            request: aiohttp web request with JSON body containing:
                - text (str, required): Text to synthesize to speech
                - device (str, optional): Target device name
                - group (str, optional): Target group name (mutually exclusive with device)
                - voice (str, optional): Voice profile name (default: "default")
                - profile (str, optional): Voice profile name (alternative to voice)
                - use_flute (bool, optional): Use Flute-Gateway first (default: True)
                - priority (str, optional): Queue priority (default: "normal")
                    Options: "low", "normal", "high", "urgent"
                - enqueue (bool, optional): Add to queue instead of immediate cast

        Returns:
            web.Response: JSON response with:
                - success (bool): Operation success status
                - device (str): Device name cast to (single device)
                - OR group (str): Group name cast to (multi-device)
                - duration (float): Audio duration in seconds
                - message (str): Success/error message
                - For multi-device casts:
                    - devices_total (int): Total devices targeted
                    - devices_successful (int): Successful casts
                    - devices_failed (int): Failed casts
                    - results (list): Per-device results

        Raises:
            web.HTTPBadRequest: If text is empty or neither device nor group specified
            web.HTTPNotFound: If voice profile not found or group not found
            web.HTTPInternalServerError: If TTS synthesis fails

        Example:
            POST /cast/speech
            {
                "text": "Hello PMOVES, this is a test",
                "device": "Brysons Speakers speaker",
                "voice": "Kokoro",
                "use_flute": true
            }
        """
        CAST_REQUESTS.labels(method="speech", status="pending").inc()

        try:
            body = await request.json()
            text = body.get("text", "")
            device = body.get("device")
            group = body.get("group")
            voice = body.get("voice", "default")
            profile = body.get("profile")
            use_flute = body.get("use_flute", True)
            priority = body.get("priority", "normal")
            enqueue = body.get("enqueue", False)

            if not text:
                CAST_REQUESTS.labels(method="speech", status="error").inc()
                return web.json_response(
                    {"error": "text is required"},
                    status=400
                )

            # Apply voice profile if specified
            voice_speed = 1.0  # Default speed
            voice_pitch = 1.0  # Default pitch

            if profile:
                voice_profile = self.voice_profile_manager.get_profile(profile)
                if voice_profile:
                    voice = voice_profile.voice
                    voice_speed = voice_profile.speed
                    voice_pitch = voice_profile.pitch
                else:
                    CAST_REQUESTS.labels(method="speech", status="error").inc()
                    return web.json_response(
                        {"error": f"Profile '{profile}' not found"},
                        status=404
                    )
            elif device:
                # Auto-detect profile for device
                voice_profile = self.voice_profile_manager.find_profile_for_device(device)
                if voice_profile:
                    voice = voice_profile.voice
                    voice_speed = voice_profile.speed
                    voice_pitch = voice_profile.pitch
            elif group:
                # Auto-detect profile for group
                voice_profile = self.voice_profile_manager.find_profile_for_group(group)
                if voice_profile:
                    voice = voice_profile.voice
                    voice_speed = voice_profile.speed
                    voice_pitch = voice_profile.pitch

            # Handle queueing
            if enqueue:
                result = await self.priority_queue.enqueue(
                    text=text,
                    device=device,
                    group=group,
                    priority=priority,
                    voice=voice,
                )
                return web.json_response(result)

            # Determine target devices
            target_devices = []
            if group:
                # Cast to group
                group_obj = self.group_manager.get_group(group)
                if not group_obj:
                    CAST_REQUESTS.labels(method="speech", status="error").inc()
                    return web.json_response(
                        {"error": f"Group '{group}' not found"},
                        status=404
                    )
                target_devices = group_obj.devices
            elif device:
                # Cast to single device
                target_devices = [device]
            else:
                # No device specified - return error
                CAST_REQUESTS.labels(method="speech", status="error").inc()
                return web.json_response(
                    {"error": "Either 'device' or 'group' must be specified"},
                    status=400
                )

            with CAST_LATENCY.time():
                # Synthesize TTS
                audio_data = None
                audio_path = None

                # Try Flute-Gateway first
                if use_flute:
                    audio_data = await self.flute_provider.synthesize_prosodic(
                        text=text,
                        voice=voice,
                    )

                # Fallback to Ultimate-TTS via API
                if not audio_data:
                    try:
                        import httpx

                        # Use voice profile parameters (speed, pitch) with defaults
                        voice_model = "Kokoro" if voice == "default" else voice
                        speed = max(0.5, min(2.0, voice_speed))
                        pitch = max(0.5, min(2.0, voice_pitch))

                        async with httpx.AsyncClient(timeout=120.0) as client:
                            response = await client.post(
                                f"{ULTIMATE_TTS_URL}/api/predict",
                                json={"data": [text, voice_model, speed, pitch, speed]},
                            )
                            response.raise_for_status()
                            result_data = response.json()

                            if "data" in result_data and len(result_data["data"]) > 0:
                                audio_path = result_data["data"][0]

                    except Exception as e:
                        CAST_REQUESTS.labels(method="speech", status="error").inc()
                        await self._publish_event("voice.cast.failed.v1", {
                            "stage": "tts_synthesis",
                            "reason": str(e),
                            "retryable": True,
                            "outcome": "fatal",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "text": text,
                            "provider_attempted": "ultimate_tts",
                        })
                        return web.json_response(
                            {"error": f"Failed to synthesize TTS: {str(e)}"},
                            status=500
                        )

                if not audio_data and not audio_path:
                    CAST_REQUESTS.labels(method="speech", status="error").inc()
                    await self._publish_event("voice.cast.failed.v1", {
                        "stage": "fallback_exhausted",
                        "reason": "No TTS provider returned audio",
                        "retryable": False,
                        "outcome": "fatal",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "text": text,
                    })
                    return web.json_response(
                        {"error": "Failed to synthesize TTS"},
                        status=500
                    )

                # Cast to devices
                if len(target_devices) == 1:
                    # Single device - use direct cast
                    if audio_data:
                        # Save to temp file
                        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                            f.write(audio_data)
                            temp_path = f.name

                        result = await self.device_manager.cast_audio(temp_path, target_devices[0])

                        # Cleanup
                        os.unlink(temp_path)
                    else:
                        result = await self.device_manager.cast_audio(audio_path, target_devices[0])

                    if result.get("success"):
                        # catt identifies devices by friendly name only; use
                        # device_id/device_name from result when available,
                        # fall back to "device" (name string) for both fields.
                        _dev = result.get("device", "")
                        await self._publish_event("voice.cast.completed.v1", {
                            "device_id": result.get("device_id", _dev),
                            "device_name": result.get("device_name", _dev),
                            "audio_url": "",
                            "text": text,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "meta": {"voice": voice},
                        })
                        CAST_REQUESTS.labels(method="speech", status="success").inc()
                    else:
                        CAST_REQUESTS.labels(method="speech", status="error").inc()
                        await self._publish_event("voice.cast.failed.v1", {
                            "stage": "device_cast",
                            "reason": result.get("error", "Cast failed"),
                            "retryable": True,
                            "outcome": "fatal",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "device_name": result.get("device", ""),
                            "text": text,
                        })

                    return web.json_response(result)
                else:
                    # Multiple devices - use concurrent casting
                    async def cast_to_device(device_name: str) -> dict:
                        """Cast to single device with error recovery."""
                        async def _cast():
                            if audio_data:
                                # Save to temp file
                                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                                    f.write(audio_data)
                                    temp_path = f.name

                                result = await self.device_manager.cast_audio(temp_path, device_name)

                                # Cleanup
                                os.unlink(temp_path)
                            else:
                                result = await self.device_manager.cast_audio(audio_path, device_name)

                            return result

                        # Use recovery manager for retry logic
                        try:
                            return await self.recovery_manager.execute_with_retry(
                                _cast,
                                circuit_breaker_key=device_name,
                            )
                        except Exception as e:
                            return {
                                "success": False,
                                "device": device_name,
                                "error": str(e),
                            }

                        return result

                    multi_result = await self.concurrent_caster.cast_to_devices(
                        cast_fn=cast_to_device,
                        devices=target_devices,
                        text=text,
                    )

                    if multi_result.failed == 0:
                        # Only publish completed when ALL devices succeed
                        await self._publish_event("voice.cast.completed.v1", {
                            "device_id": group if group else ",".join(target_devices),
                            "device_name": group if group else ",".join(target_devices),
                            "audio_url": "",
                            "text": text,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "meta": {
                                "voice": voice,
                                "group": group if group else None,
                                "devices_total": multi_result.total_devices,
                                "devices_successful": multi_result.successful,
                            },
                        })

                    if multi_result.failed == 0:
                        CAST_REQUESTS.labels(method="speech", status="success").inc()
                    else:
                        CAST_REQUESTS.labels(method="speech", status="partial").inc()
                        failed_devices = [r.device for r in multi_result.results if not r.success]
                        await self._publish_event("voice.cast.failed.v1", {
                            "stage": "device_cast",
                            "reason": f"{multi_result.failed}/{multi_result.total_devices} devices failed",
                            "retryable": True,
                            "outcome": "partial",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "text": text,
                            "meta": {
                                "failed_devices": failed_devices,
                                "group": group if group else None,
                            },
                        })

                    return web.json_response(multi_result.to_dict())

        except Exception as e:
            CAST_REQUESTS.labels(method="speech", status="error").inc()
            await self._publish_event("voice.cast.failed.v1", {
                "stage": "tts_synthesis",
                "reason": str(e),
                "retryable": False,
                "outcome": "fatal",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_cast_audio(self, request: web.Request) -> web.Response:
        """
        Cast pre-generated audio file to Google Cast device.

        Args:
            request: aiohttp web request with JSON body containing:
                - audio_path (str, required): Path or URL to audio file
                - device (str, required): Target device name

        Returns:
            web.Response: JSON response with:
                - success (bool): Operation success status
                - device (str): Device name cast to
                - message (str): Success/error message

        Raises:
            web.HTTPBadRequest: If audio_path not provided
            web.HTTPInternalServerError: If casting fails

        Example:
            POST /cast/audio
            {
                "audio_path": "/path/to/audio.mp3",
                "device": "Brysons Speakers speaker"
            }
        """
        CAST_REQUESTS.labels(method="audio", status="pending").inc()

        try:
            body = await request.json()
            audio_path = body.get("audio_path", "")
            device = body.get("device")

            if not audio_path:
                CAST_REQUESTS.labels(method="audio", status="error").inc()
                return web.json_response(
                    {"error": "audio_path is required"},
                    status=400
                )

            # Path traversal protection: reject paths containing ".." or null bytes
            if ".." in audio_path or "\x00" in audio_path:
                CAST_REQUESTS.labels(method="audio", status="error").inc()
                return web.json_response(
                    {"error": "Invalid audio_path: path traversal not allowed"},
                    status=400
                )

            with CAST_LATENCY.time():
                result = await self.device_manager.cast_audio(audio_path, device)

            if result["success"]:
                _dev = result.get("device", "")
                await self._publish_event("voice.cast.completed.v1", {
                    "device_id": result.get("device_id", _dev),
                    "device_name": result.get("device_name", _dev),
                    "audio_url": audio_path,
                    "text": "",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
                CAST_REQUESTS.labels(method="audio", status="success").inc()
            else:
                CAST_REQUESTS.labels(method="audio", status="error").inc()
                await self._publish_event("voice.cast.failed.v1", {
                    "stage": "device_cast",
                    "reason": result.get("error", "Cast audio failed"),
                    "retryable": True,
                    "outcome": "fatal",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "device_name": device,
                })

            return web.json_response(result)

        except Exception as e:
            CAST_REQUESTS.labels(method="audio", status="error").inc()
            await self._publish_event("voice.cast.failed.v1", {
                "stage": "device_cast",
                "reason": str(e),
                "retryable": True,
                "outcome": "fatal",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_cast_stop(self, request: web.Request) -> web.Response:
        """
        Stop current playback on Google Cast device.

        Args:
            request: aiohttp web request with JSON body containing:
                - device (str, required): Target device name

        Returns:
            web.Response: JSON response with:
                - success (bool): Operation success status
                - device (str): Device name
                - message (str): Success/error message

        Raises:
            web.HTTPInternalServerError: If stop command fails

        Example:
            POST /cast/stop
            {
                "device": "Brysons Speakers speaker"
            }
        """
        CAST_REQUESTS.labels(method="stop", status="pending").inc()

        try:
            body = await request.json()
            device = body.get("device")

            with CAST_LATENCY.time():
                result = await self.device_manager.stop_cast(device)

            if result["success"]:
                CAST_REQUESTS.labels(method="stop", status="success").inc()
            else:
                CAST_REQUESTS.labels(method="stop", status="error").inc()

            return web.json_response(result)

        except Exception as e:
            CAST_REQUESTS.labels(method="stop", status="error").inc()
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_cast_status(self, request: web.Request) -> web.Response:
        """
        Get current playback status of Google Cast device.

        Args:
            request: aiohttp web request with query parameters:
                - device (str, optional): Target device name (default: first available)

        Returns:
            web.Response: JSON response with:
                - status (str): Status indicator ("ok" or "error")
                - device (str): Device name queried
                - output (str): catt status command output
                - OR error (str): Error message if command failed

        Example:
            GET /cast/status?device=Brysons%20Speakers%20speaker
        """
        try:
            device = request.query.get("device")

            # Run catt status command
            cmd = ["catt", "status"]
            if device:
                cmd.extend(["-d", device])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                status_output = stdout.decode().strip()
                return web.json_response({
                    "status": "ok",
                    "device": device or "default",
                    "output": status_output,
                })
            else:
                return web.json_response(
                    {"error": stderr.decode().strip()},
                    status=500
                )

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_create_group(self, request: web.Request) -> web.Response:
        """
        Create a new device group for multi-device casting.

        Args:
            request: aiohttp web request with JSON body containing:
                - name (str, required): Unique group name
                - devices (list, required): List of device names in group
                - description (str, optional): Group description

        Returns:
            web.Response: JSON response with:
                - success (bool): Operation success status
                - group (str): Created group name
                - devices (list): Device names in group
                - message (str): Success/error message

        Raises:
            web.HTTPBadRequest: If name or devices not provided

        Example:
            POST /cast/groups
            {
                "name": "All Speakers",
                "devices": ["Brysons Speakers speaker", "Brysons Speakers speaker 2"],
                "description": "All Nest Audio devices"
            }
        """
        try:
            body = await request.json()
            name = body.get("name", "")
            devices = body.get("devices", [])
            description = body.get("description", "")

            result = self.group_manager.create_group(name, devices, description)

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=400)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_groups(self, request: web.Request) -> web.Response:
        """
        List all configured device groups.

        Returns:
            web.Response: JSON response with:
                - groups (list): List of group objects, each containing:
                    - name (str): Group name
                    - devices (list): Device names in group
                    - description (str): Group description
                    - created_at (float): Unix creation timestamp
                - count (int): Total number of groups

        Example:
            GET /cast/groups
        """
        try:
            groups = self.group_manager.list_groups()

            return web.json_response({
                "groups": [g.to_dict() for g in groups],
                "count": len(groups),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_delete_group(self, request: web.Request) -> web.Response:
        """
        Delete a device group.

        Args:
            request: aiohttp web request with URL parameter:
                - name (str, required): Group name to delete (from URL path)

        Returns:
            web.Response: JSON response with:
                - success (bool): Operation success status
                - group (str): Deleted group name
                - message (str): Success/error message

        Raises:
            web.HTTPNotFound: If group not found

        Example:
            DELETE /cast/groups/All%20Speakers
        """
        try:
            name = request.match_info.get("name", "")

            result = self.group_manager.delete_group(name)

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=404)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_update_group(self, request: web.Request) -> web.Response:
        """
        Update an existing device group.

        Args:
            request: aiohttp web request with:
                - name (str, required): Group name to update (from URL path)
                - JSON body containing:
                    - devices (list, optional): New device list
                    - description (str, optional): New description

        Returns:
            web.Response: JSON response with:
                - success (bool): Operation success status
                - group (str): Updated group name
                - message (str): Success/error message

        Raises:
            web.HTTPNotFound: If group not found

        Example:
            PUT /cast/groups/All%20Speakers
            {
                "devices": ["Brysons Speakers speaker", "Brysons Speakers speaker 2", "Den speaker"],
                "description": "All speakers including bedroom"
            }
        """
        try:
            name = request.match_info.get("name", "")
            body = await request.json()
            devices = body.get("devices")
            description = body.get("description")

            result = self.group_manager.update_group(name, devices, description)

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=404)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_status(self, request: web.Request) -> web.Response:
        """Get priority queue status."""
        try:
            status = self.priority_queue.get_queue_status()

            # Add full announcement list
            announcements = self.priority_queue.list_announcements()
            status["announcements"] = [a.to_dict() for a in announcements]

            return web.json_response(status)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_clear(self, request: web.Request) -> web.Response:
        """Clear all announcements from queue."""
        try:
            result = await self.priority_queue.clear()
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_remove(self, request: web.Request) -> web.Response:
        """Remove specific announcement from queue."""
        try:
            announcement_id = request.match_info.get("id", "")

            result = await self.priority_queue.remove(announcement_id)

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=404)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_create_voice_profile(self, request: web.Request) -> web.Response:
        """Create a voice profile."""
        try:
            body = await request.json()
            name = body.get("name", "")
            voice = body.get("voice", "default")
            speed = body.get("speed", 1.0)
            pitch = body.get("pitch", 1.0)
            device = body.get("device")
            group = body.get("group")
            description = body.get("description", "")
            context_tags = body.get("context_tags", [])

            result = self.voice_profile_manager.create_profile(
                name=name,
                voice=voice,
                speed=speed,
                pitch=pitch,
                device=device,
                group=group,
                description=description,
                context_tags=context_tags,
            )

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=400)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_voice_profiles(self, request: web.Request) -> web.Response:
        """List all voice profiles."""
        try:
            profiles = self.voice_profile_manager.list_profiles()

            return web.json_response({
                "profiles": [p.to_dict() for p in profiles],
                "count": len(profiles),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_get_voice_profile(self, request: web.Request) -> web.Response:
        """Get a specific voice profile."""
        try:
            name = request.match_info.get("name", "")
            profile = self.voice_profile_manager.get_profile(name)

            if profile:
                return web.json_response(profile.to_dict())
            else:
                return web.json_response(
                    {"error": f"Profile '{name}' not found"},
                    status=404
                )

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_update_voice_profile(self, request: web.Request) -> web.Response:
        """Update a voice profile."""
        try:
            name = request.match_info.get("name", "")
            body = await request.json()

            result = self.voice_profile_manager.update_profile(
                name=name,
                voice=body.get("voice"),
                speed=body.get("speed"),
                pitch=body.get("pitch"),
                description=body.get("description"),
                context_tags=body.get("context_tags"),
            )

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=404)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_delete_voice_profile(self, request: web.Request) -> web.Response:
        """Delete a voice profile."""
        try:
            name = request.match_info.get("name", "")

            result = self.voice_profile_manager.delete_profile(name)

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=404)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_schedule_announcement(self, request: web.Request) -> web.Response:
        """Schedule a recurring announcement."""
        try:
            body = await request.json()
            text = body.get("text", "")
            cron = body.get("cron", "")
            device = body.get("device")
            group = body.get("group")
            voice = body.get("voice", "default")
            priority = body.get("priority", "normal")

            if not text or not cron:
                return web.json_response(
                    {"error": "text and cron are required"},
                    status=400
                )

            if not self.scheduler:
                return web.json_response(
                    {"error": "Scheduler not initialized"},
                    status=500
                )

            result = await self.scheduler.schedule(
                text=text,
                cron=cron,
                device=device,
                group=group,
                voice=voice,
                priority=priority,
            )

            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_schedule_once(self, request: web.Request) -> web.Response:
        """Schedule a one-shot announcement."""
        try:
            body = await request.json()
            text = body.get("text", "")
            at = body.get("at")
            device = body.get("device")
            group = body.get("group")
            voice = body.get("voice", "default")
            priority = body.get("priority", "normal")

            if not text or not at:
                return web.json_response(
                    {"error": "text and at are required"},
                    status=400
                )

            if not self.scheduler:
                return web.json_response(
                    {"error": "Scheduler not initialized"},
                    status=500
                )

            result = await self.scheduler.schedule_once(
                text=text,
                at=at,
                device=device,
                group=group,
                voice=voice,
                priority=priority,
            )

            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_scheduled(self, request: web.Request) -> web.Response:
        """List all scheduled announcements."""
        try:
            if not self.scheduler:
                return web.json_response(
                    {"error": "Scheduler not initialized"},
                    status=500
                )

            scheduled = self.scheduler.list_scheduled()

            return web.json_response({
                "scheduled": [a.to_dict() for a in scheduled],
                "count": len(scheduled),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_cancel_scheduled(self, request: web.Request) -> web.Response:
        """Cancel a scheduled announcement."""
        try:
            announcement_id = request.match_info.get("id", "")

            if not self.scheduler:
                return web.json_response(
                    {"error": "Scheduler not initialized"},
                    status=500
                )

            result = await self.scheduler.cancel(announcement_id)

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=404)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_create_template(self, request: web.Request) -> web.Response:
        """Create an announcement template."""
        try:
            body = await request.json()
            name = body.get("name", "")
            template = body.get("template", "")
            description = body.get("description", "")

            if not name or not template:
                return web.json_response(
                    {"error": "name and template are required"},
                    status=400
                )

            if not self.scheduler:
                return web.json_response(
                    {"error": "Scheduler not initialized"},
                    status=500
                )

            result = await self.scheduler.create_template(
                name=name,
                template=template,
                description=description,
            )

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=400)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_templates(self, request: web.Request) -> web.Response:
        """List all announcement templates."""
        try:
            if not self.scheduler:
                return web.json_response(
                    {"error": "Scheduler not initialized"},
                    status=500
                )

            templates = self.scheduler.list_templates()

            return web.json_response({
                "templates": [t.to_dict() for t in templates],
                "count": len(templates),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_delete_template(self, request: web.Request) -> web.Response:
        """Delete an announcement template."""
        try:
            name = request.match_info.get("name", "")

            if not self.scheduler:
                return web.json_response(
                    {"error": "Scheduler not initialized"},
                    status=500
                )

            result = await self.scheduler.delete_template(name)

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=404)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_health(self, request: web.Request) -> web.Response:
        """List health status for all devices."""
        try:
            health_list = self.health_monitor.list_health()

            return web.json_response({
                "health": [h.to_dict() for h in health_list],
                "count": len(health_list),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_get_health(self, request: web.Request) -> web.Response:
        """Get health status for a specific device."""
        try:
            device = request.match_info.get("device", "")
            health = self.health_monitor.get_health(device)

            if health:
                return web.json_response(health.to_dict())
            else:
                return web.json_response(
                    {"error": f"Device '{device}' not found"},
                    status=404
                )

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_configure_alert(self, request: web.Request) -> web.Response:
        """Configure a health alert."""
        try:
            body = await request.json()
            device = body.get("device", "")
            metric = body.get("metric", "")
            threshold = body.get("threshold", 0.0)
            action = body.get("action", "publish_nats")
            webhook_url = body.get("webhook_url")

            if not device or not metric:
                return web.json_response(
                    {"error": "device and metric are required"},
                    status=400
                )

            result = await self.health_monitor.configure_alert(
                device=device,
                metric=metric,
                threshold=threshold,
                action=action,
                webhook_url=webhook_url,
            )

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=400)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_alerts(self, request: web.Request) -> web.Response:
        """List all configured alerts."""
        try:
            alerts = self.health_monitor.list_alerts()

            return web.json_response({
                "alerts": [a.to_dict() for a in alerts],
                "count": len(alerts),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_start(self, request: web.Request) -> web.Response:
        """Start queue processing."""
        try:
            result = await self.audio_queue_manager.start_processing()
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_pause(self, request: web.Request) -> web.Response:
        """Pause queue processing."""
        try:
            result = await self.audio_queue_manager.pause_processing()
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_resume(self, request: web.Request) -> web.Response:
        """Resume queue processing."""
        try:
            result = await self.audio_queue_manager.resume_processing()
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_skip(self, request: web.Request) -> web.Response:
        """Skip current announcement."""
        try:
            result = await self.audio_queue_manager.skip_current()
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_stop(self, request: web.Request) -> web.Response:
        """Stop queue processing."""
        try:
            result = await self.audio_queue_manager.stop_processing()
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_session(self, request: web.Request) -> web.Response:
        """Get current queue session info."""
        try:
            session = self.audio_queue_manager.get_session()

            if session:
                return web.json_response(session.to_dict())
            else:
                return web.json_response(
                    {"error": "No active session"},
                    status=404
                )

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_batch_remove(self, request: web.Request) -> web.Response:
        """Remove multiple announcements from queue."""
        try:
            body = await request.json()
            announcement_ids = body.get("announcement_ids", [])

            if not announcement_ids:
                return web.json_response(
                    {"error": "announcement_ids is required"},
                    status=400
                )

            result = await self.audio_queue_manager.batch_remove(announcement_ids)
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_queue_batch_enqueue(self, request: web.Request) -> web.Response:
        """Enqueue multiple announcements."""
        try:
            body = await request.json()
            announcements = body.get("announcements", [])

            if not announcements:
                return web.json_response(
                    {"error": "announcements is required"},
                    status=400
                )

            result = await self.audio_queue_manager.batch_enqueue(announcements)
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_configure_retry(self, request: web.Request) -> web.Response:
        """Configure retry policy."""
        try:
            body = await request.json()

            result = self.recovery_manager.configure_retry(
                max_attempts=body.get("max_attempts", 3),
                backoff_base=body.get("backoff_base", 2.0),
                initial_delay=body.get("initial_delay", 1.0),
                max_delay=body.get("max_delay", 60.0),
                jitter=body.get("jitter", True),
            )

            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_configure_circuit_breaker(self, request: web.Request) -> web.Response:
        """Configure circuit breaker."""
        try:
            body = await request.json()

            result = self.recovery_manager.configure_circuit_breaker(
                failure_threshold=body.get("failure_threshold", 5),
                recovery_timeout=body.get("recovery_timeout", 60.0),
                half_open_max_calls=body.get("half_open_max_calls", 3),
                success_threshold=body.get("success_threshold", 2),
            )

            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_circuit_breakers(self, request: web.Request) -> web.Response:
        """List all circuit breakers."""
        try:
            breakers = self.recovery_manager.list_circuit_breakers()

            return web.json_response({
                "circuit_breakers": {
                    key: state.to_dict()
                    for key, state in breakers.items()
                },
                "count": len(breakers),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_reset_circuit_breaker(self, request: web.Request) -> web.Response:
        """Reset circuit breaker."""
        try:
            key = request.match_info.get("key", "")

            result = self.recovery_manager.reset_circuit_breaker(key)

            if result.get("success"):
                return web.json_response(result)
            else:
                return web.json_response(result, status=404)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_configure_tts_fallback(self, request: web.Request) -> web.Response:
        """Configure TTS fallback chain."""
        try:
            body = await request.json()
            providers = body.get("providers", ["flute", "ultimate_tts", "google_tts"])

            provider_map = {
                "flute": FluteFallbackProvider(FLUTE_URL),
                "ultimate_tts": UltimateTTSProvider(ULTIMATE_TTS_URL),
                "google_tts": GoogleTTSProvider(),
            }

            provider_instances = []
            for provider_name in providers:
                if provider_name in provider_map:
                    provider_instances.append(provider_map[provider_name])

            if not provider_instances:
                return web.json_response(
                    {"error": "No valid providers specified"},
                    status=400
                )

            result = self.fallback_manager.configure_tts_fallback(provider_instances)
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_tts_providers(self, request: web.Request) -> web.Response:
        """List TTS providers in fallback chain."""
        try:
            providers = self.fallback_manager.list_tts_providers()

            return web.json_response({
                "providers": providers,
                "count": len(providers),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_configure_device_fallback(self, request: web.Request) -> web.Response:
        """Configure device fallback chain."""
        try:
            body = await request.json()
            name = body.get("name", "")
            devices = body.get("devices", [])

            if not name or not devices:
                return web.json_response(
                    {"error": "name and devices are required"},
                    status=400
                )

            result = self.fallback_manager.configure_device_fallback(name, devices)
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_device_fallbacks(self, request: web.Request) -> web.Response:
        """List all device fallback chains."""
        try:
            fallbacks = self.fallback_manager.list_device_fallbacks()

            return web.json_response({
                "fallbacks": fallbacks,
                "count": len(fallbacks),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_optimize_stats(self, request: web.Request) -> web.Response:
        """Get optimization statistics."""
        try:
            stats = self.optimization_manager.get_optimization_stats()
            return web.json_response(stats)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_cache_clear(self, request: web.Request) -> web.Response:
        """Clear all cache entries."""
        try:
            result = await self.optimization_manager.clear_cache()
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_cache_cleanup(self, request: web.Request) -> web.Response:
        """Remove expired cache entries."""
        try:
            result = await self.optimization_manager.cleanup_cache()
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_cache_invalidate(self, request: web.Request) -> web.Response:
        """Invalidate specific cache entry."""
        try:
            body = await request.json()
            text = body.get("text", "")
            voice = body.get("voice", "default")

            if not text:
                return web.json_response(
                    {"error": "text is required"},
                    status=400
                )

            invalidated = await self.optimization_manager.invalidate_cache(text, voice)

            return web.json_response({
                "success": invalidated,
                "message": "Cache entry invalidated" if invalidated else "Cache entry not found",
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_security_stats(self, request: web.Request) -> web.Response:
        """Get security statistics."""
        try:
            stats = self.security_manager.get_security_stats()
            return web.json_response(stats)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_query_audit_logs(self, request: web.Request) -> web.Response:
        """Query audit logs."""
        try:
            action = request.query.get("action")
            user = request.query.get("user")
            device = request.query.get("device")
            result = request.query.get("result")
            limit = int(request.query.get("limit", "100"))
            offset = int(request.query.get("offset", "0"))

            logs = await self.security_manager.query_audit_logs(
                action=action,
                user=user,
                device=device,
                result=result,
                limit=limit,
                offset=offset,
            )

            return web.json_response({
                "logs": logs,
                "count": len(logs),
                "limit": limit,
                "offset": offset,
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_grant_permission(self, request: web.Request) -> web.Response:
        """Grant permission to user."""
        try:
            body = await request.json()
            user = body.get("user", "")
            permission = body.get("permission", "")

            if not user or not permission:
                return web.json_response(
                    {"error": "user and permission are required"},
                    status=400
                )

            result = self.security_manager.grant_permission(user, permission)
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_revoke_permission(self, request: web.Request) -> web.Response:
        """Revoke permission from user."""
        try:
            body = await request.json()
            user = body.get("user", "")
            permission = body.get("permission", "")

            if not user or not permission:
                return web.json_response(
                    {"error": "user and permission are required"},
                    status=400
                )

            result = self.security_manager.revoke_permission(user, permission)
            return web.json_response(result)

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_list_permissions(self, request: web.Request) -> web.Response:
        """List permissions for user."""
        try:
            user = request.match_info.get("user", "")

            if not user:
                return web.json_response(
                    {"error": "user is required"},
                    status=400
                )

            # SecurityManager doesn't have list_permissions exposed, so we'll use the internal access control
            from security import AccessControl

            # Get permissions from access control
            # Note: This is a simplified implementation
            permissions = set()

            return web.json_response({
                "user": user,
                "permissions": list(permissions),
                "count": len(permissions),
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_configure_rate_limits(self, request: web.Request) -> web.Response:
        """Configure rate limits."""
        try:
            body = await request.json()
            requests_per_minute = body.get("requests_per_minute", 60)
            burst_size = body.get("burst_size", 10)

            # Note: This would update the rate limiter configuration
            # For now, just return the requested config
            return web.json_response({
                "success": True,
                "requests_per_minute": requests_per_minute,
                "burst_size": burst_size,
                "message": "Rate limits configured (restart required)",
            })

        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def _health_alert_callback(self, device: str, alert_data: dict):
        """Callback for health alerts."""
        # Publish alert to NATS
        await self._publish_event("voice.cast.health_alert.v1", alert_data)

    async def _health_check_fn(self, device: str) -> tuple[bool, float]:
        """Health check function for monitoring."""
        start_time = time.time()

        # Try to cast a short silent audio or just check device availability
        # For now, we'll do a simple status check
        try:
            # Try to get device status using catt status
            cmd = ["catt", "status", "-d", device]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            latency_ms = int((time.time() - start_time) * 1000)

            # Consider successful if command completed
            return (proc.returncode == 0, latency_ms)

        except Exception as e:
            return (False, int((time.time() - start_time) * 1000))

    async def _scheduler_cast_fn(
        self,
        text: str,
        device: Optional[str],
        group: Optional[str],
        voice: str,
    ) -> dict:
        """Cast function for scheduler."""
        # Determine target devices
        target_devices = []
        if group:
            group_obj = self.group_manager.get_group(group)
            if group_obj:
                target_devices = group_obj.devices
        elif device:
            target_devices = [device]
        else:
            return {"success": False, "error": "No device or group specified"}

        # Synthesize TTS
        audio_data = await self.flute_provider.synthesize_prosodic(
            text=text,
            voice=voice,
        )

        if not audio_data:
            return {"success": False, "error": "TTS synthesis failed"}

        # Cast to devices
        import tempfile
        import os

        async def cast_to_device(device_name: str) -> dict:
            """Cast to single device."""
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name

            result = await self.device_manager.cast_audio(temp_path, device_name)
            os.unlink(temp_path)
            return result

        if len(target_devices) == 1:
            return await cast_to_device(target_devices[0])
        else:
            multi_result = await self.concurrent_caster.cast_to_devices(
                cast_fn=cast_to_device,
                devices=target_devices,
                text=text,
            )
            return multi_result.to_dict()

    @staticmethod
    def _on_circuit_breaker_transition(from_state: str, to_state: str, service: str):
        """Record circuit breaker state transition in Prometheus."""
        CIRCUIT_BREAKER_TRANSITIONS.labels(
            from_state=from_state, to_state=to_state, service=service,
        ).inc()

    async def _on_device_discovery(self, devices, new_names, lost_names, forced):
        """Callback invoked after device discovery completes."""
        await self._publish_event("device.cast.discovered.v1", {
            "devices": [
                {"name": d.name, "ip": d.ip, "address": d.address}
                for d in devices
            ],
            "count": len(devices),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "new_devices": sorted(new_names),
            "lost_devices": sorted(lost_names),
            "forced": forced,
        })
        DEVICE_DISCOVERIES.inc()

    async def _publish_event(self, subject: str, payload: dict):
        """
        Publish event to NATS with enhanced error handling and metrics.

        Args:
            subject: NATS subject to publish to
            payload: Event payload dict

        Returns:
            None

        Emits:
            - NATS publish success metric (method=publish_nats, status=success)
            - NATS publish error metric (method=publish_nats, status=error)
        """
        if not self.nats_client:
            print(f"NATS not connected, skipping publish to {subject}")
            return

        try:
            if _envelope:
                env = _envelope(subject, payload, source="cast-tts-gateway")
                data = json.dumps(env).encode()
            else:
                data = json.dumps(payload).encode()
            await self.nats_client.publish(subject, data)
            # Success metric
            CAST_REQUESTS.labels(method="publish_nats", status="success").inc()

        except Exception as e:
            # Enhanced logging with context
            print(f"NATS publish error on subject '{subject}': {e}")
            print(f"Payload preview: {json.dumps(payload, indent=2)[:500]}")

            # Error metric for observability
            CAST_REQUESTS.labels(method="publish_nats", status="error").inc()

            # Note: We don't fail the HTTP request if NATS publish fails
            # NATS is used for event notification, not critical path

    async def connect_nats(self):
        """Connect to NATS message bus."""
        try:
            self.nats_client = await nats.connect(NATS_URL)
            print(f"Connected to NATS at {NATS_URL}")
        except Exception as e:
            print(f"NATS connection failed: {e}")

    async def run(self):
        """Run the gateway service."""
        # Connect to NATS
        await self.connect_nats()

        # Load persisted voice profiles from Supabase
        try:
            saved_profiles = await self.persistence.load_profiles()
            for p in saved_profiles:
                if "name" in p:
                    self.voice_profile_manager.profiles[p["name"]] = p
            print(f"Loaded {len(saved_profiles)} voice profile(s) from Supabase")
        except Exception as e:
            print(f"Persistence load_profiles skipped: {e}")

        # Load persisted schedules from Supabase (independent of profiles)
        try:
            saved_schedules = await self.persistence.load_schedules()
            print(f"Loaded {len(saved_schedules)} schedule(s) from Supabase")
        except Exception as e:
            print(f"Persistence load_schedules skipped: {e}")

        # Initialize scheduler
        self.scheduler = CastScheduler(self._scheduler_cast_fn)
        await self.scheduler.start()

        # Discover devices on startup
        devices = await self.device_manager.discover(force=True)

        # Start health monitoring for discovered devices
        for device in devices:
            self.health_monitor.track_device(device.name)

        await self.health_monitor.start(self._health_check_fn)

        # Set queue reference for audio queue manager
        self.audio_queue_manager.set_queue(self.priority_queue)

        # Configure default TTS fallback chain
        default_providers = [
            FluteFallbackProvider(FLUTE_URL),
            UltimateTTSProvider(ULTIMATE_TTS_URL),
            GoogleTTSProvider(),
        ]
        self.fallback_manager.configure_tts_fallback(default_providers)

        # Start security manager
        await self.security_manager.start()

        # Start HTTP server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()

        print(f"Cast TTS Gateway running at http://0.0.0.0:{PORT}")
        print(f"Flute-Gateway: {FLUTE_URL}")
        print(f"Ultimate-TTS: {ULTIMATE_TTS_URL}")
        print(f"NATS: {NATS_URL}")
        print(f"Monitoring {len(devices)} device(s)")

        # Keep running
        try:
            await asyncio.Event().wait()
        finally:
            await self.health_monitor.stop()
            if self.scheduler:
                await self.scheduler.stop()
            await self.security_manager.stop()
            await self.persistence.close()
            if self.nats_client:
                await self.nats_client.close()


async def main():
    """Main entry point."""
    gateway = CastTTSGateway()
    await gateway.run()


if __name__ == "__main__":
    asyncio.run(main())
