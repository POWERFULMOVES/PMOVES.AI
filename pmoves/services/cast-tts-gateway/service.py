"""
PMOVES Cast TTS Gateway

Central service for TTS synthesis and casting to Google Cast devices.
Integrates with Flute-Gateway, Ultimate-TTS Studio, and NATS event bus.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from typing import Optional

from aiohttp import web
import nats
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.exposition import CONTENT_TYPE_LATEST

from flute_client import FluteTTSProvider
from device_manager import CastDeviceManager


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


class CastTTSGateway:
    """Cast TTS gateway service."""

    def __init__(self):
        """Initialize gateway."""
        self.flute_provider = FluteTTSProvider(FLUTE_URL)
        self.device_manager = CastDeviceManager()
        self.nats_client: Optional[nats.aio.client.Client] = None
        self.app = web.Application()
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

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
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
        """Prometheus metrics endpoint."""
        metrics = generate_latest()
        return web.Response(body=metrics, content_type=CONTENT_TYPE_LATEST)

    async def handle_devices(self, request: web.Request) -> web.Response:
        """List discovered devices."""
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
        """Trigger device discovery."""
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
        """Synthesize TTS and cast to device."""
        CAST_REQUESTS.labels(method="speech", status="pending").inc()

        try:
            body = await request.json()
            text = body.get("text", "")
            device = body.get("device")
            voice = body.get("voice", "default")
            use_flute = body.get("use_flute", True)

            if not text:
                CAST_REQUESTS.labels(method="speech", status="error").inc()
                return web.json_response(
                    {"error": "text is required"},
                    status=400
                )

            with CAST_LATENCY.time():
                # Try Flute-Gateway first
                if use_flute:
                    audio_data = await self.flute_provider.synthesize_prosodic(
                        text=text,
                        voice=voice,
                    )

                    if audio_data:
                        # Save to temp file
                        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                            f.write(audio_data)
                            temp_path = f.name

                        result = await self.device_manager.cast_audio(temp_path, device)

                        # Cleanup
                        os.unlink(temp_path)

                        if result["success"]:
                            await self._publish_event("voice.cast.completed.v1", {
                                "device": result.get("device"),
                                "text": text,
                                "voice": voice,
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                            })

                            CAST_REQUESTS.labels(method="speech", status="success").inc()
                            return web.json_response(result)

                # Fallback to Ultimate-TTS via API
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(
                            f"{ULTIMATE_TTS_URL}/api/predict",
                            json={"data": [text, "Kokoro", 0.5, 0.5, 0.5]},
                        )
                        response.raise_for_status()
                        result_data = response.json()

                        if "data" in result_data and len(result_data["data"]) > 0:
                            audio_path = result_data["data"][0]
                            result = await self.device_manager.cast_audio(audio_path, device)

                            if result["success"]:
                                await self._publish_event("voice.cast.completed.v1", {
                                    "device": result.get("device"),
                                    "text": text,
                                    "voice": "Kokoro (Ultimate-TTS)",
                                    "timestamp": datetime.utcnow().isoformat() + "Z",
                                })

                                CAST_REQUESTS.labels(method="speech", status="success").inc()
                                return web.json_response(result)

                except Exception as e:
                    pass

                CAST_REQUESTS.labels(method="speech", status="error").inc()
                return web.json_response(
                    {"error": "Failed to synthesize TTS"},
                    status=500
                )

        except Exception as e:
            CAST_REQUESTS.labels(method="speech", status="error").inc()
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_cast_audio(self, request: web.Request) -> web.Response:
        """Cast audio file to device."""
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

            with CAST_LATENCY.time():
                result = await self.device_manager.cast_audio(audio_path, device)

            if result["success"]:
                await self._publish_event("voice.cast.completed.v1", {
                    "device": result.get("device"),
                    "audio_path": audio_path,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
                CAST_REQUESTS.labels(method="audio", status="success").inc()
            else:
                CAST_REQUESTS.labels(method="audio", status="error").inc()

            return web.json_response(result)

        except Exception as e:
            CAST_REQUESTS.labels(method="audio", status="error").inc()
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def handle_cast_stop(self, request: web.Request) -> web.Response:
        """Stop playback on device."""
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
        """Get device status."""
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

    async def _publish_event(self, subject: str, payload: dict):
        """Publish event to NATS."""
        if not self.nats_client:
            return

        try:
            await self.nats_client.publish(
                subject,
                json.dumps(payload).encode(),
            )
        except Exception as e:
            print(f"NATS publish error: {e}")

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

        # Discover devices on startup
        await self.device_manager.discover(force=True)

        # Start HTTP server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()

        print(f"Cast TTS Gateway running at http://0.0.0.0:{PORT}")
        print(f"Flute-Gateway: {FLUTE_URL}")
        print(f"Ultimate-TTS: {ULTIMATE_TTS_URL}")
        print(f"NATS: {NATS_URL}")

        # Keep running
        try:
            await asyncio.Event().wait()
        finally:
            if self.nats_client:
                await self.nats_client.close()


async def main():
    """Main entry point."""
    gateway = CastTTSGateway()
    await gateway.run()


if __name__ == "__main__":
    asyncio.run(main())
