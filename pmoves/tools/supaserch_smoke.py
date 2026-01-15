import asyncio
import json
import os
import sys
import uuid
import urllib.request
from urllib.error import URLError, HTTPError

from nats.aio.client import Client as NATS


async def publish_and_wait() -> dict[str, object]:
    request_id = f"supaserch-smoke-{uuid.uuid4().hex[:8]}"
    nc = NATS()
    url = os.getenv("NATS_URL", "nats://localhost:4222")
    await nc.connect(url)
    loop = asyncio.get_running_loop()
    future: asyncio.Future | None = loop.create_future()

    async def handler(msg):
        nonlocal future
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except json.JSONDecodeError:
            return
        if data.get("request_id") != request_id:
            return
        if future and not future.done():
            future.set_result(data)

    sid = await nc.subscribe("supaserch.result.v1", cb=handler)
    payload = {
        "request_id": request_id,
        "query": "supaserch smoke verification",
        "correlation_id": request_id,
        "trigger": "make supaserch-smoke",
    }
    await nc.publish("supaserch.request.v1", json.dumps(payload).encode("utf-8"))
    await nc.flush()
    try:
        result = await asyncio.wait_for(future, timeout=10)
    except asyncio.TimeoutError:
        print("✖ Did not receive supaserch.result.v1 within 10s")
        await nc.unsubscribe(sid)
        await nc.drain()
        sys.exit(1)
    await nc.unsubscribe(sid)
    await nc.drain()
    fallback = result.get("fallback", {}) if isinstance(result, dict) else {}
    if fallback.get("status") != "ok":
        print("✖ NATS fallback status not ok:", json.dumps(fallback))
        sys.exit(1)
    via = fallback.get("via", "unknown")
    latency = fallback.get("latency_ms", 0)
    print(f"✔ NATS round-trip complete (via {via}, latency {latency} ms)")
    return result


def main():
    result = asyncio.run(publish_and_wait())
    host_port = os.getenv("SUPASERCH_HOST_PORT", os.getenv("SUPASERCH_PORT", "8099"))
    http_url = f"http://localhost:{host_port}/v1/search?q=supaserch+smoke+http"
    try:
        with urllib.request.urlopen(http_url, timeout=8) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"✖ HTTP fallback request failed: {exc}")
        sys.exit(1)

    fallback = body.get("fallback", {}) if isinstance(body, dict) else {}
    if fallback.get("status") != "ok":
        print("✖ HTTP fallback status not ok:", json.dumps(fallback))
        sys.exit(1)

    via = fallback.get("via", "unknown")
    latency = fallback.get("latency_ms", 0)
    print(f"✔ HTTP fallback responded (via {via}, latency {latency} ms)")


if __name__ == "__main__":
    main()
