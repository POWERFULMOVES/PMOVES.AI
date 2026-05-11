import asyncio
import json
import logging
import os
from typing import Any, Dict
from nats.aio.client import Client as NATS
from chit_signing import verify_cgp

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def main():
    nc = NATS()
    nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
    try:
        await nc.connect(nats_url)
        logger.info(f"Connected to NATS at {nats_url}")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        return

    async def message_handler(msg):
        subject = msg.subject
        data = msg.data.decode()
        logger.info(f"Received message on {subject}")

        try:
            payload: Dict[str, Any] = json.loads(data)
            
            # Optionally verify signature if passphrase exists
            # We will forward it anyway if it is structurally valid, but could reject here.
            is_valid = verify_cgp(payload)
            if not is_valid:
                logger.warning("Packet signature invalid or missing.")

            # Translate to geometry.packet.decoded.v1
            # For flute, we might just unwrap the points
            decoded_event = {
                "source_spec": payload.get("spec"),
                "super_nodes": payload.get("super_nodes", []),
                "control_plane": payload.get("control_plane", {})
            }
            
            publish_subject = "geometry.packet.decoded.v1"
            await nc.publish(publish_subject, json.dumps(decoded_event).encode())
            logger.info(f"Successfully decoded and published to {publish_subject}")

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from message.")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    subscribe_subject = "geometry.cgp.v1"
    await nc.subscribe(subscribe_subject, cb=message_handler)
    logger.info(f"Subscribed to {subscribe_subject}")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
    finally:
        await nc.drain()

if __name__ == "__main__":
    asyncio.run(main())
