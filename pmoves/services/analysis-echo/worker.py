import os, asyncio, json, re
from nats.aio.client import Client as NATS
from services.common.events import envelope

NATS_URL = os.environ.get("NATS_URL","nats://nats:4222")

def extract_topics(text, top_k=5):
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    from collections import Counter
    common = Counter(words).most_common(top_k)
    return [{"label": w, "score": min(1.0, c/10.0)} for w,c in common]

async def main():
    nc = NATS()
    await nc.connect(servers=[NATS_URL])

    async def handle_request(msg):
        data = json.loads(msg.data.decode())
        text = data["payload"].get("text","")
        topics = extract_topics(text, data["payload"].get("top_k",5))
        payload = {"media_id": data["payload"].get("media_id","unknown"), "topics": topics}
        env = envelope("analysis.extract_topics.result.v1", payload, correlation_id=data.get("correlation_id"), parent_id=data.get("id"), source="analysis-echo")
        await nc.publish("analysis.extract_topics.result.v1", json.dumps(env).encode())

    await nc.subscribe("analysis.extract_topics.request.v1", cb=handle_request)
    print("analysis-echo worker listening on analysis.extract_topics.request.v1")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
