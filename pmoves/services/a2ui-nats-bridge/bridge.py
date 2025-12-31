"""
A2UI NATS Bridge

Bridges A2UI (Google Agent-to-User Interface) events to the PMOVES NATS geometry bus.

A2UI Format (v0.9):
- createSurface: Initialize a new UI surface
- updateComponents: Add/update UI components
- updateDataModel: Update data bindings
- Events published to: a2ui.render.v1
- Geometry subscription: geometry.> (for bidirectional)

NATS WebSocket: ws://localhost:9223
Author: PMOVES.AI
Date: 2025-12-30
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
import nats
from nats.js.errors import Error as JSError
from prometheus_client import Counter, Gauge, generate_latest

# Configuration
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
A2UI_WS_URL = os.getenv("A2UI_WS_URL", "ws://localhost:9223")
A2UI_RENDER_SUBJECT = os.getenv("A2UI_RENDER_SUBJECT", "a2ui.render.v1")
A2UI_REQUEST_SUBJECT = os.getenv("A2UI_REQUEST_SUBJECT", "a2ui.request.v1")
GEOMETRY_WILDCARD = os.getenv("GEOMETRY_WILDCARD", "geometry.>")
PORT = int(os.getenv("PORT", "9224"))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("a2ui-nats-bridge")

# Prometheus Metrics
a2ui_events_published = Counter("a2ui_events_published_total", "A2UI events published to NATS", ["event_type"])
a2ui_events_received = Counter("a2ui_events_received_total", "Events received from A2UI agents")
a2ui_events_forwarded = Counter("a2ui_events_forwarded_total", "A2UI events forwarded to WebSocket clients")
active_websockets = Gauge("a2ui_active_websockets", "Active WebSocket connections")
nats_connected = Gauge("a2ui_nats_connected", "NATS connection status")

# A2UI Event Types
A2UI_CREATE_SURFACE = "createSurface"
A2UI_BEGIN_RENDERING = "beginRendering"
A2UI_SURFACE_UPDATE = "surfaceUpdate"
A2UI_UPDATE_COMPONENTS = "updateComponents"
A2UI_UPDATE_DATA_MODEL = "updateDataModel"
A2UI_DATA_MODEL_UPDATE = "dataModelUpdate"
A2UI_USER_ACTION = "userAction"
A2UI_CLOSE_SURFACE = "closeSurface"


@dataclass
class A2UIEvent:
    """A2UI event wrapper for NATS transport."""
    version: str = "0.9"
    source: str = "a2ui"
    timestamp: str = ""
    surface_id: str = ""
    event_type: str = ""
    payload: dict[str, Any] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if self.payload is None:
            self.payload = {}

    def to_nats_message(self) -> bytes:
        """Convert to NATS message format."""
        return json.dumps(asdict(self)).encode()

    @classmethod
    def from_a2ui_dict(cls, data: dict[str, Any]) -> "A2UIEvent":
        """Create A2UIEvent from A2UI dictionary format.

        Args:
            data: A2UI event dictionary (e.g., {"createSurface": {...}})

        Returns:
            A2UIEvent instance

        Raises:
            ValueError: If data is invalid or missing required fields
            TypeError: If data is not a dictionary
        """
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data).__name__}")

        if not data:
            raise ValueError("Empty A2UI event data")

        event_type = list(data.keys())[0]
        payload = data[event_type]

        if not isinstance(payload, dict):
            raise TypeError(f"Expected payload dict for {event_type}, got {type(payload).__name__}")

        # Extract surfaceId from payload
        surface_id = payload.get("surfaceId", "")

        return cls(
            surface_id=surface_id,
            event_type=event_type,
            payload=payload
        )


# Global state
nc: Optional[nats.aio.client.Client] = None
js: Optional["nats.js.client.JetStreamContext"] = None
active_ws_connections: set[WebSocket] = set()
connected_a2ui_surfaces: dict[str, str] = {}  # surface_id -> client_id


async def connect_nats() -> None:
    """Connect to NATS with JetStream enabled.

    Establishes connection, creates the A2UI stream, and subscribes to
    geometry events for bidirectional communication.

    Retries up to 5 times with linear backoff (5s, 10s, 15s, 20s, 25s).

    Side effects:
        - Sets global `nc` and `js` variables
        - Updates `nats_connected` Prometheus gauge
        - Creates A2UI JetStream stream if not exists
        - Subscribes to geometry.* wildcard subject

    Note:
        Logs error but continues if geometry subscription fails (non-critical).
    """
    global nc, js
    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        try:
            logger.info(f"Connecting to NATS at {NATS_URL}...")
            nc = await nats.connect(NATS_URL)
            js = nc.jetstream()

            # Create or get A2UI stream
            try:
                await js.add_stream(
                    name="A2UI",
                    subjects=[
                        A2UI_RENDER_SUBJECT,
                        A2UI_REQUEST_SUBJECT,
                        "a2ui.>"
                    ],
                    description="A2UI (Agent-to-User Interface) events"
                )
                logger.info("Created NATS stream 'A2UI'")
            except JSError as e:
                # Stream already exists is not an error - it's expected on restart
                if "stream name already in use" in str(e).lower() or "already in use" in str(e).lower():
                    logger.info("NATS stream 'A2UI' already exists")
                else:
                    logger.error(f"Failed to create A2UI stream: {e}")
                    raise

            # Subscribe to geometry events for bidirectional communication
            try:
                await js.subscribe(
                    GEOMETRY_WILDCARD,
                    "a2ui_geom_sub",
                    stream="GEOMETRY"
                )
                logger.info(f"Subscribed to {GEOMETRY_WILDCARD}")
            except Exception as e:
                logger.warning(f"Could not subscribe to geometry: {e}")

            nats_connected.set(1)
            logger.info("NATS connection established")
            return

        except Exception as e:
            retry_count += 1
            logger.warning(f"NATS connection failed (attempt {retry_count}/{max_retries}): {e}")
            await asyncio.sleep(5 * retry_count)

    logger.error("Failed to connect to NATS after max retries")
    nats_connected.set(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan.

    Args:
        app: FastAPI application instance.

    Yields:
        None: Control yields after startup completes, before shutdown begins.

    Startup actions:
        - Connect to NATS with JetStream
        - Create A2UI stream
        - Subscribe to geometry events

    Shutdown actions:
        - Close NATS connection
        - Reset connection gauge
    """
    # Startup
    await connect_nats()
    yield
    # Shutdown
    global nc
    if nc:
        await nc.close()
        nats_connected.set(0)


# FastAPI App
app = FastAPI(
    title="A2UI NATS Bridge",
    description="Bridges A2UI (Agent-to-User Interface) events to PMOVES NATS geometry bus",
    version="1.0.0",
    lifespan=lifespan
)


async def publish_a2ui_event(event: A2UIEvent) -> None:
    """Publish A2UI event to NATS.

    Raises:
        ConnectionError: If NATS is not connected
        RuntimeError: If publish fails
    """
    if nc is None:
        raise ConnectionError("NATS not connected, cannot publish event")

    try:
        # Publish to render subject
        subject = f"{A2UI_RENDER_SUBJECT}.{event.surface_id}" if event.surface_id else A2UI_RENDER_SUBJECT
        await js.publish(subject, event.to_nats_message(), stream="A2UI")

        a2ui_events_published.labels(event_type=event.event_type).inc()
        logger.info(f"Published A2UI event: {event.event_type} (surface: {event.surface_id})")

    except Exception as e:
        logger.error(f"Failed to publish A2UI event: {e}")
        raise RuntimeError(f"NATS publish failed: {e}") from e


async def handle_user_action(action: dict[str, Any]) -> None:
    """Handle user action from UI, forward to A2UI agent.

    Raises:
        ConnectionError: If NATS is not connected
        RuntimeError: If publish fails
    """
    action_name = action.get("name", "unknown")
    surface_id = action.get("surfaceId", "")
    context = action.get("context", {})

    logger.info(f"User action: {action_name} on surface {surface_id}")

    # Publish user action for agents to handle
    event = A2UIEvent(
        surface_id=surface_id,
        event_type=A2UI_USER_ACTION,
        payload=action
    )
    await publish_a2ui_event(event)


@app.get("/healthz")
async def health_check():
    """Health check endpoint.

    Returns 'healthy' if NATS is connected, 'degraded' otherwise.
    This allows downstream monitoring to detect connection issues.
    """
    nats_status = bool(nc and nc.is_connected())
    overall_status = "healthy" if nats_status else "degraded"

    return {
        "status": overall_status,
        "nats_connected": nats_status,
        "active_websockets": len(active_ws_connections),
        "active_surfaces": list(connected_a2ui_surfaces.keys()),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")


@app.post("/api/v1/a2ui")
async def a2ui_endpoint(data: dict[str, Any]):
    """REST endpoint for A2UI events.

    Accepts A2UI JSON format and publishes to NATS.
    """
    a2ui_events_received.inc()
    try:
        event = A2UIEvent.from_a2ui_dict(data)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        await publish_a2ui_event(event)
    except (ConnectionError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return {
        "status": "published",
        "surface_id": event.surface_id,
        "event_type": event.event_type
    }


@app.post("/api/v1/action")
async def user_action_endpoint(action: dict[str, Any]):
    """Handle user action from UI.

    Returns 200 even if NATS unavailable (logs warning for debugging).
    """
    try:
        await handle_user_action(action)
    except (ConnectionError, RuntimeError) as e:
        logger.warning(f"User action failed to publish: {e}")
        # Return 200 to avoid disrupting UI, but log the error
    return {"status": "handled"}


@app.post("/api/v1/simulate")
async def simulate_a2ui_event():
    """Simulate an A2UI event for testing."""
    mock_event = A2UIEvent(
        surface_id="test_surface",
        event_type=A2UI_SURFACE_UPDATE,
        payload={
            "surfaceId": "test_surface",
            "components": [
                {
                    "id": "root",
                    "component": "Column",
                    "children": ["title", "button"]
                },
                {
                    "id": "title",
                    "component": "Text",
                    "text": "Hello from A2UI!"
                },
                {
                    "id": "button_text",
                    "component": "Text",
                    "text": "Click Me"
                },
                {
                    "id": "button",
                    "component": "Button",
                    "child": "button_text",
                    "action": {"name": "test_action"}
                }
            ]
        }
    )
    try:
        await publish_a2ui_event(mock_event)
    except (ConnectionError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {
        "status": "simulated",
        "surface_id": mock_event.surface_id,
        "nats_subject": A2UI_RENDER_SUBJECT
    }


@app.websocket("/ws/a2ui")
async def a2ui_agent_websocket(websocket: WebSocket):
    """WebSocket for A2UI agents to push UI updates.

    Accepts A2UI JSONL format (one JSON object per line).
    """
    await websocket.accept()
    active_ws_connections.add(websocket)
    active_websockets.set(len(active_ws_connections))
    client_id = f"{websocket.client.host}:{websocket.client.port}"
    logger.info(f"A2UI agent WebSocket connected: {client_id}")

    try:
        while True:
            data = await websocket.receive_text()

            # Handle JSONL format (one JSON per line)
            lines = data.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                try:
                    a2ui_dict = json.loads(line)
                    a2ui_events_received.inc()

                    # Extract event type and surface ID
                    event_type = list(a2ui_dict.keys())[0] if a2ui_dict else "unknown"
                    payload = a2ui_dict[event_type] if event_type else {}
                    surface_id = payload.get("surfaceId", "")

                    # Track surface
                    if surface_id and event_type in (A2UI_CREATE_SURFACE, A2UI_BEGIN_RENDERING):
                        connected_a2ui_surfaces[surface_id] = client_id
                        logger.info(f"Surface registered: {surface_id} from {client_id}")
                    elif surface_id and event_type == A2UI_CLOSE_SURFACE:
                        connected_a2ui_surfaces.pop(surface_id, None)
                        logger.info(f"Surface closed: {surface_id}")

                    # Create and publish event
                    event = A2UIEvent.from_a2ui_dict(a2ui_dict)
                    await publish_a2ui_event(event)

                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from agent: {e}")
                    await websocket.send_json({"error": "Invalid JSON format"})
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid A2UI event: {e}")
                    await websocket.send_json({"error": f"Invalid event: {e}"})
                except (ConnectionError, RuntimeError) as e:
                    logger.error(f"NATS error: {e}")
                    await websocket.send_json({"error": "NATS unavailable"})
                except Exception as e:
                    logger.warning(f"Error processing A2UI event: {e}")

    except WebSocketDisconnect:
        logger.info(f"A2UI agent WebSocket disconnected: {client_id}")
    finally:
        active_ws_connections.discard(websocket)
        active_websockets.set(len(active_ws_connections))
        # Remove surfaces from this client
        to_remove = [sid for sid, cid in connected_a2ui_surfaces.items() if cid == client_id]
        for sid in to_remove:
            connected_a2ui_surfaces.pop(sid, None)


@app.websocket("/ws/client")
async def client_websocket(websocket: WebSocket):
    """WebSocket for PMOVES UI clients to receive A2UI updates.

    Clients connect here to receive real-time UI updates from A2UI agents.
    """
    await websocket.accept()
    active_ws_connections.add(websocket)
    active_websockets.set(len(active_ws_connections))
    client_id = f"{websocket.client.host}:{websocket.client.port}"
    logger.info(f"Client WebSocket connected: {client_id}")

    # Subscribe to NATS messages
    async def a2ui_handler(msg):
        """Forward NATS A2UI messages to WebSocket client."""
        try:
            data = json.loads(msg.data.decode())
            # Send as JSONL (one JSON per line) for A2UI format compatibility
            line = json.dumps(data)
            await websocket.send_text(line + "\n")
            a2ui_events_forwarded.inc()
        except Exception as e:
            logger.warning(f"Failed to forward A2UI message: {e}")

    sub = None
    try:
        if nc:
            # Subscribe to all A2UI events
            sub = await nc.subscribe("a2ui.>", cb=a2ui_handler)
            logger.info(f"Forwarding A2UI events to {client_id}")

            # Keep connection alive
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        logger.info(f"Client WebSocket disconnected: {client_id}")
    finally:
        active_ws_connections.discard(websocket)
        active_websockets.set(len(active_ws_connections))
        if sub:
            await sub.unsubscribe()


def main() -> None:
    """Run the A2UI NATS bridge server.

    Starts the uvicorn server on all interfaces (0.0.0.0) with the configured PORT.

    Environment variables:
        PORT: Server port (default: 9224)
        NATS_URL: NATS server URL (default: nats://nats:4222)
    """
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
