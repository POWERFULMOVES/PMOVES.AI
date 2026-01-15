from __future__ import annotations

import argparse
import asyncio
import json
import os
import nats


async def main():
    ap = argparse.ArgumentParser(description="Publish a shape-capsule handshake over NATS")
    ap.add_argument("file", help="JSON file containing a CGP (data field optional)")
    ap.add_argument("--subject", default="mesh.shape.handshake.v1")
    ap.add_argument("--nats", default=os.environ.get("NATS_URL","nats://localhost:4222"))
    args = ap.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        doc = json.load(f)
    cgp = doc.get("data") or doc
    payload = {"type":"shape-capsule","capsule":{"kind":"cgp","data": cgp}}

    nc = await nats.connect(servers=[args.nats])
    await nc.publish(args.subject, json.dumps(payload).encode())
    await nc.flush()
    await nc.drain()
    print("published", args.subject)

if __name__ == "__main__":
    asyncio.run(main())

