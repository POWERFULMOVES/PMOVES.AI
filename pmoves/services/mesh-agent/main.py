from __future__ import annotations

import asyncio
import json
import os
import socket
import time
from typing import Any, Dict

import nats
import requests
import hashlib
import hmac

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
NODE_NAME = os.environ.get("NODE_NAME", socket.gethostname())
HIRAG_URL = os.environ.get("HIRAG_URL", "http://hi-rag-gateway-v2-gpu:8086")
ANNOUNCE_SEC = int(os.environ.get("ANNOUNCE_SEC", "15"))
MESH_PASSPHRASE = os.environ.get("MESH_PASSPHRASE", "")

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


async def announce_loop(nc):
    while True:
        msg = {
            "type": "mesh.node.announce.v1",
            "node": NODE_NAME,
            "caps": {"clip": True, "clap": True, "t5": True},
            "ts": int(time.time())
        }
        await nc.publish("mesh.node.announce.v1", json.dumps(msg).encode())
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
