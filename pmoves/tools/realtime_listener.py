import asyncio
import json
import os
import websockets

REALTIME_URL = os.environ.get("REALTIME_URL", "ws://localhost:4000/socket/websocket")
API_KEY = os.environ.get("REALTIME_ANON_KEY", "anon-key")


async def main():
    # Phoenix channels protocol
    url = f"{REALTIME_URL}?apikey={API_KEY}&vsn=2.0.0"
    async with websockets.connect(url, ping_interval=20) as ws:
        # Join a table/topic: public:shape_points (listen for INSERT)
        ref = 1
        join_payload = {
            "topic": "realtime:public:shape_points",
            "event": "phx_join",
            "payload": {"config": {"events": ["INSERT"]}},
            "ref": str(ref),
        }
        await ws.send(json.dumps(join_payload))
        print("Joined realtime:public:shape_points; waiting for inserts...")
        while True:
            msg = await ws.recv()
            try:
                data = json.loads(msg)
            except Exception:
                print("<<", msg)
                continue
            print("<<", json.dumps(data, indent=2))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

