import os, re, json, asyncio, pathlib, requests
from urllib.parse import urljoin
from nats.aio.client import Client as NATS
from minio import Minio
from services.common.events import envelope

NATS_URL = os.environ.get("NATS_URL","nats://nats:4222")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT","minio:9000")
MINIO_USE_SSL = os.environ.get("MINIO_USE_SSL","false").lower() == "true"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY","pmoves")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY","password")
JELLYFIN_URL = os.environ.get("JELLYFIN_URL","http://jellyfin:8096")
JELLYFIN_API_KEY = os.environ.get("JELLYFIN_API_KEY")
MEDIA_LIBRARY_PATH = os.environ.get("MEDIA_LIBRARY_PATH","/library/images")

def parse_s3(uri:str):
    m = re.match(r'^s3://([^/]+)/(.+)$', uri)
    if not m:
        raise ValueError("Bad artifact_uri; expected s3://bucket/key")
    return m.group(1), m.group(2)

def ensure_path(path):
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)

def jellyfin_refresh():
    try:
        headers = {"X-Emby-Token": JELLYFIN_API_KEY} if JELLYFIN_API_KEY else {}
        url = urljoin(JELLYFIN_URL, "/Library/Refresh")
        requests.post(url, headers=headers, timeout=10)
    except Exception as e:
        print("Jellyfin refresh error:", e)

async def main():
    nc = NATS()
    await nc.connect(servers=[NATS_URL])
    s3 = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=MINIO_USE_SSL)

    async def handle(msg):
        try:
            env = json.loads(msg.data.decode())
            p = env.get("payload",{})
            artifact_uri = p.get("artifact_uri")
            title = p.get("title","untitled")
            ns = p.get("namespace","pmoves-demo")
            bucket, key = parse_s3(artifact_uri)

            ensure_path(MEDIA_LIBRARY_PATH)
            name = key.split("/")[-1]
            # try preserve extension
            ext = "." + name.split(".")[-1] if "." in name else ".png"
            out_path = os.path.join(MEDIA_LIBRARY_PATH, f"{title}{ext}")
            s3.fget_object(bucket, key, out_path)

            jellyfin_refresh()

            payload = {
                "artifact_uri": artifact_uri,
                "published_path": out_path,
                "namespace": ns,
                "meta": {"title": title}
            }
            evt = envelope("content.published.v1", payload, parent_id=env.get("id"), correlation_id=env.get("correlation_id"), source="publisher")
            await nc.publish("content.published.v1".encode(), json.dumps(evt).encode())
            print("Published:", out_path)
        except Exception as e:
            print("publisher error:", e)

    await nc.subscribe("content.publish.approved.v1", cb=handle)
    print("publisher ready: listening on content.publish.approved.v1")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
