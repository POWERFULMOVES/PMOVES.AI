import asyncio
import datetime
import hashlib
import json
import os
import pathlib
import time

from minio import Minio
from nats.aio.client import Client as NATS

from services.common.events import envelope

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_USE_SSL = os.environ.get("MINIO_USE_SSL", "false").lower() == "true"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
BUCKET = os.environ.get("MINIO_BUCKET", "pmoves-comfyui")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://minio:9000")
PRESIGN_HOURS = int(os.environ.get("PRESIGN_EXPIRES_HOURS", "24"))
OUTPUT_DIR = os.environ.get("COMFY_OUTPUT_DIR", "/data/output")
STATE_PATH = os.environ.get("COMFY_WATCHER_STATE_PATH", "/state/state.json")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
POLL_SECONDS = int(os.environ.get("COMFY_WATCHER_POLL_SECONDS", "5"))


def load_state() -> dict:
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {"uploaded": {}}


def save_state(state: dict) -> None:
    pathlib.Path(os.path.dirname(STATE_PATH)).mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)


def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


async def run() -> None:
    if not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
        raise RuntimeError("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set")

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

                    key = datetime.datetime.now(datetime.timezone.utc).strftime("comfyui/%Y/%m/%d/") + fn
                    client.fput_object(BUCKET, key, path, content_type="image/png")
                    state["uploaded"][h] = {"key": key, "ts": time.time(), "size": size}
                    save_state(state)

                    public_url = (
                        f"{PUBLIC_BASE_URL}/{BUCKET}/{key}".replace("//", "/").replace("http:/", "http://").replace("https:/", "https://")
                    )

                    payload = {"artifact_uri": f"s3://{BUCKET}/{key}", "meta": {"public_url": public_url}}
                    try:
                        from datetime import timedelta

                        payload["meta"]["presigned_url"] = client.presigned_get_object(BUCKET, key, expires=timedelta(hours=PRESIGN_HOURS))
                    except Exception:
                        pass

                    env = envelope("gen.image.result.v1", payload, source="comfy-watcher")
                    await nc.publish("gen.image.result.v1", json.dumps(env).encode())
                    print("Uploaded and announced:", key)
                except Exception as e:
                    print("Error processing", path, e)

        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
