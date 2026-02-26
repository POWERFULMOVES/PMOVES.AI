"""
PMOVES.AI Mesh Agent

Announces host presence and capabilities to the PMOVES mesh network.
Integrates with:
- NATS message bus for local announcements (mesh.node.announce.v1)
- Service Registry for multi-host discovery
- Tailscale for cross-host mesh networking
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import time
from typing import Any, Dict, Optional

import nats
import requests
import hashlib
import hmac

# Configuration
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
NODE_NAME = os.environ.get("NODE_NAME", socket.gethostname())
HIRAG_URL = os.environ.get("HIRAG_URL", "http://hi-rag-gateway-v2-gpu:8086")
ANNOUNCE_SEC = int(os.environ.get("ANNOUNCE_SEC", "15"))
MESH_PASSPHRASE = os.environ.get("MESH_PASSPHRASE", "")

# Service Registry Integration
SERVICE_REGISTRY_URL = os.environ.get("SERVICE_REGISTRY_URL", "http://service-registry:8100")
SERVICE_MODE = os.environ.get("SERVICE_MODE", "docked")  # "standalone" or "docked"

# Node capabilities for service discovery
NODE_CAPABILITIES = os.environ.get("NODE_CAPABILITIES", "clip,clap,t5,rag,agent").split(",")

def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

def _verify_capsule(capsule: Dict[str, Any]) -> bool:
    if not MESH_PASSPHRASE:
        return True  # verification disabled
    sig = capsule.get("sig") or {}
    mac = sig.get("hmac")
    data = capsule.get("data")
    if not (isinstance(mac, str) and isinstance(data, dict)):
        return False
    try:
        mac1 = hmac.new(MESH_PASSPHRASE.encode("utf-8"), _canon(data), hashlib.sha256).digest()
        import base64
        mac2 = base64.b64decode(mac)
        return hmac.compare_digest(mac1, mac2)
    except Exception:
        return False


def get_tailscale_ip() -> Optional[str]:
    """Get the Tailscale IP address for this node."""
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            ip = result.stdout.strip()
            if ip and ip.startswith("100."):
                return ip
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def get_mesh_host() -> str:
    """Get the host address for mesh communication."""
    # Try Tailscale first for cross-host mesh
    ts_ip = get_tailscale_ip()
    if ts_ip:
        return ts_ip

    # Fallback to local hostname
    try:
        return socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        return "127.0.0.1"


async def register_with_service_registry(port: int = 0, health_url: Optional[str] = None) -> bool:
    """Register this node with the service registry."""
    registry_url = f"{SERVICE_REGISTRY_URL}/api/services"

    payload = {
        "name": NODE_NAME,
        "host": get_mesh_host(),
        "port": port,
        "mode": SERVICE_MODE,
        "capabilities": NODE_CAPABILITIES,
        "health_url": health_url,
        "metadata": {
            "tailscale_ip": get_tailscale_ip(),
            "hostname": socket.gethostname(),
        }
    }

    try:
        response = requests.post(registry_url, json=payload, timeout=5)
        if response.status_code in (200, 201):
            return True
    except requests.RequestException:
        pass
    return False


async def announce_loop(nc):
    """Main announcement loop - announces via NATS and Service Registry."""
    while True:
        ts_now = int(time.time())

        # v1 announcement for backward compatibility
        msg_v1 = {
            "type": "mesh.node.announce.v1",
            "node": NODE_NAME,
            "caps": {cap: True for cap in NODE_CAPABILITIES},
            "host": get_mesh_host(),
            "tailscale_ip": get_tailscale_ip(),
            "mode": SERVICE_MODE,
            "ts": ts_now,
        }
        await nc.publish("mesh.node.announce.v1", json.dumps(msg_v1).encode())

        # v2 announcement with namespace identity and topology context
        peer_raw = os.environ.get("PEER_EXPECTATIONS", "")
        # Compute external services from EXTERNAL_* flags
        ext_svcs = [
            s for s, k in [
                ("neo4j", "EXTERNAL_NEO4J"),
                ("meilisearch", "EXTERNAL_MEILI"),
                ("qdrant", "EXTERNAL_QDRANT"),
                ("supabase", "EXTERNAL_SUPABASE"),
            ]
            if os.environ.get(k, "").lower() in ("true", "1", "yes")
        ]
        msg_v2 = {
            "type": "mesh.node.announce.v2",
            "node": NODE_NAME,
            "caps": {cap: True for cap in NODE_CAPABILITIES},
            "host": get_mesh_host(),
            "tailscale_ip": get_tailscale_ip(),
            "mode": SERVICE_MODE,
            "ts": ts_now,
            "namespace": {
                "project": os.environ.get("COMPOSE_PROJECT_NAME", "pmoves"),
                "tier": os.environ.get("SERVICE_TIER", "unknown"),
                "branch": os.environ.get("GIT_BRANCH", "unknown"),
            },
            "topology": {
                "mode": os.environ.get("TOPOLOGY_MODE", "auto"),
                "supabase_runtime": os.environ.get("SUPABASE_RUNTIME", "compose"),
                "external_services": ext_svcs,
            },
            "slug": os.environ.get("SERVICE_SLUG", NODE_NAME),
            "peers": [p for p in peer_raw.split(",") if p],
            "health": {"status": "announcing"},
        }
        await nc.publish("mesh.node.announce.v2", json.dumps(msg_v2).encode())

        # Service Registry registration for multi-host discovery
        await register_with_service_registry()

        await asyncio.sleep(max(5, ANNOUNCE_SEC))


async def shape_handshake_sub(nc):
    async def handler(msg):
        try:
            data = json.loads(msg.data.decode())
        except Exception:
            return
        if isinstance(data, dict) and data.get("type") == "shape-capsule":
            cap = data.get("capsule") or {}
            if cap.get("kind") == "cgp" and isinstance(cap.get("data"), dict):
                if _verify_capsule(cap):
                    try:
                        requests.post(f"{HIRAG_URL}/geometry/event", json={"type":"geometry.cgp.v1","data":cap["data"]}, timeout=10)
                    except Exception:
                        pass
    await nc.subscribe("mesh.shape.handshake.v1", cb=handler)


async def main():
    nc = await nats.connect(servers=[NATS_URL])
    await shape_handshake_sub(nc)
    await announce_loop(nc)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
