import os, time, json, hashlib, pathlib, datetime
from minio import Minio
from nats.aio.client import Client as NATS
from services.common.events import envelope

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT","minio:9000")
MINIO_USE_SSL = os.environ.get("MINIO_USE_SSL","false").lower() == "true"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY","pmoves")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY","password")
BUCKET = os.environ.get("MINIO_BUCKET","pmoves-comfyui")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL","http://localhost:9000")
PRESIGN_HOURS = int(os.environ.get("PRESIGN_EXPIRES_HOURS","24"))
OUTPUT_DIR = "/data/output"
STATE_PATH = "/state/state.json"
NATS_URL = os.environ.get("NATS_URL","nats://nats:4222")

def load_state():
    try:
        return json.loads(open(STATE_PATH).read())
    except Exception:
        return {"uploaded":{}}

def save_state(state):
    pathlib.Path("/state").mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH,"w") as f:
        json.dump(state,f)

def file_hash(p):
    h = hashlib.sha256()
    with open(p,"rb") as f:
        while True:
            b = f.read(1<<20)
            if not b: break
            h.update(b)
    return h.hexdigest()

async def run():
    state = load_state()
    client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=MINIO_USE_SSL)
    nc = NATS()
    await nc.connect(servers=[NATS_URL])

    try:
        if not client.bucket_exists(BUCKET):
            client.make_bucket(BUCKET)
    except Exception as e:
        print("Bucket check/make:", e)

    while True:
        for root, _, files in os.walk(OUTPUT_DIR):
            for fn in files:
                path = os.path.join(root, fn)
                try:
                    size = os.path.getsize(path)
                    if size == 0: 
                        continue
                    h = file_hash(path)
                    if state["uploaded"].get(h):
                        continue
                    key = datetime.datetime.utcnow().strftime("comfyui/%Y/%m/%d/") + fn
                    client.fput_object(BUCKET, key, path, content_type="image/png")
                    state["uploaded"][h] = {"key": key, "ts": time.time(), "size": size}
                    save_state(state)
                    # presign
                    try:
                        from datetime import timedelta
                        presigned = client.presigned_get_object(BUCKET, key, expires=timedelta(hours=PRESIGN_HOURS))
                    except Exception as e:
                        presigned = None
                    public_url = f"{PUBLIC_BASE_URL}/{BUCKET}/{key}".replace('//','/').replace('http:/','http://').replace('https:/','https://')
                    payload = {"artifact_uri": f"s3://{BUCKET}/{key}"}
                    meta = {"public_url": public_url}
                    if presigned: meta["presigned_url"] = presigned
                    env = envelope("gen.image.result.v1", payload, source="comfy-watcher")
                    env["payload"]["meta"] = meta
                    await nc.publish("gen.image.result.v1", json.dumps(env).encode())
                    print("Uploaded and announced:", key)
                except Exception as e:
                    print("Error processing", path, e)
        time.sleep(5)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
