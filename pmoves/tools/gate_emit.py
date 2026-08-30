"""Operator demo CLI: publish a test geometry.publish.gate.v1 event.

Mirrors the payload shape consumed by pmoves/services/hi-rag-gateway-v2's
pub-gate bridge (gate_bridge.py::handle_gate_event) so a manual `make
gate-emit` run exercises the same fail-closed path as production.

Usage:
    export NATS_URL=nats://nats:pmoves@localhost:4222
    python pmoves/tools/gate_emit.py --artifact s3://pmoves/reports/r1.md --title "Report 1"
"""
import argparse
import asyncio
import json
import os
import nats


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--approved-by", default="operator")
    a = ap.parse_args()
    nc = await nats.connect(servers=[os.environ.get("NATS_URL", "nats://localhost:4222")])
    payload = {"artifact_uri": a.artifact, "title": a.title, "approved_by": a.approved_by, "mode": "manual"}
    await nc.publish("geometry.publish.gate.v1", json.dumps(payload).encode())
    await nc.drain()
    print("emitted geometry.publish.gate.v1:", payload)


if __name__ == "__main__":
    asyncio.run(main())
