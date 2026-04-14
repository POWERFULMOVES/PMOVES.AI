#!/usr/bin/env python3
"""Subscribe to CGP + voice NATS subjects and print any messages received.

Covers two subject families:
  - Geometry/CHIT CGP: tokenism.geometry.event.v1, geometry.cgp.v1 (+ wildcards)
  - Voice chain: voice.agent.response.v1, agentzero.task.result.v1,
    voice.training.request.v1

The voice subjects were added in Session 12 Lane 2 because the geometry.>
and tokenism.> wildcards do NOT cover them — voice-relay publishes on the
voice.* and agentzero.* hierarchies, which are distinct from the CGP/geometry
namespaces. Use this probe to verify the full voice chain emits events end-to-end.
"""
import asyncio
import os
import nats


async def main() -> None:
    """Connect to NATS and print CGP + voice events for 10 seconds."""
    url = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
    nc = await nats.connect(url)
    print(f"Connected to NATS: {url}")
    msgs = []

    async def handler(msg: "nats.aio.msg.Msg") -> None:
        msgs.append(msg)
        print(f"RECV: {msg.subject} ({len(msg.data)} bytes)")
        print(f"Preview: {msg.data[:300]!r}")

    # Geometry / CHIT CGP subjects (existing)
    await nc.subscribe("tokenism.geometry.event.v1", cb=handler)
    await nc.subscribe("geometry.cgp.v1", cb=handler)
    await nc.subscribe("geometry.>", cb=handler)
    await nc.subscribe("tokenism.>", cb=handler)

    # Voice chain subjects (added Session 12 Lane 2)
    # voice-relay input (consumed):
    await nc.subscribe("agentzero.task.result.v1", cb=handler)
    # voice-relay output (consumed by voice_follow_agent, voice_follow_cast_agent, publisher-discord):
    await nc.subscribe("voice.agent.response.v1", cb=handler)
    # voice cloning training trigger (planned consumer: training worker):
    await nc.subscribe("voice.training.request.v1", cb=handler)

    print(
        "Subscribed to:\n"
        "  geometry/CHIT: tokenism.geometry.event.v1, geometry.cgp.v1, geometry.>, tokenism.>\n"
        "  voice chain:   agentzero.task.result.v1, voice.agent.response.v1, voice.training.request.v1\n"
        "Waiting 10s..."
    )
    await asyncio.sleep(10)
    print(f"Total messages: {len(msgs)}")
    await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
