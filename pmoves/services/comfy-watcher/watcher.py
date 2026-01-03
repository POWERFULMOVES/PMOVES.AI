import asyncio
import datetime
from datetime import timedelta
import hashlib
import json
import logging
import os
import pathlib
import shutil
import time

from minio import Minio
from nats.aio.client import Client as NATS

from services.common.events import envelope

logger = logging.getLogger("comfy-watcher")


def _parse_int_env(key: str, default: int) -> int:
    """Parse integer from environment with validation.

    Args:
        key: Environment variable name.
        default: Default value if missing or invalid.

    Returns:
        Parsed integer value or default.
    """
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid {key}={value!r}, using default={default}")
        return default

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_USE_SSL = os.environ.get("MINIO_USE_SSL", "false").lower() == "true"
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
BUCKET = os.environ.get("MINIO_BUCKET", "pmoves-comfyui")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://minio:9000")
PRESIGN_HOURS = _parse_int_env("PRESIGN_EXPIRES_HOURS", 24)
OUTPUT_DIR = os.environ.get("COMFY_OUTPUT_DIR", "/data/output")
STATE_PATH = os.environ.get("COMFY_WATCHER_STATE_PATH", "/state/state.json")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
POLL_SECONDS = _parse_int_env("COMFY_WATCHER_POLL_SECONDS", 5)


def load_state() -> dict:
    """Load state from disk with proper error handling.

    Returns the uploaded file registry. Handles missing state files,
    corrupted JSON, and other I/O errors gracefully with logging.
    """
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info(f"State file not found, starting fresh: {STATE_PATH}")
        return {"uploaded": {}}
    except json.JSONDecodeError as exc:
        logger.error(f"Corrupted state file at {STATE_PATH}, backing up and starting fresh: {exc}")
        # Backup corrupted file for investigation
        backup_path = f"{STATE_PATH}.corrupted.{int(time.time())}"
        try:
            shutil.copy(STATE_PATH, backup_path)
            logger.info(f"Backed up corrupted state to: {backup_path}")
        except Exception as backup_exc:
            logger.warning(f"Could not backup corrupted state file: {backup_exc}")
        return {"uploaded": {}}
    except Exception as exc:
        logger.error(f"Unexpected error loading state from {STATE_PATH}: {exc}")
        return {"uploaded": {}}


def save_state(state: dict) -> None:
    """Save the watcher state to disk.

    Persists the current state dictionary to JSON storage, ensuring the
    target directory exists. Creates parent directories as needed.

    Args:
        state: A dictionary containing the watcher state, typically with
            an "uploaded" key mapping file hashes to their metadata
            (key, timestamp, size).

    Raises:
        OSError: If the state file cannot be written due to permission
            or disk space issues.
        TypeError: If the state dictionary contains non-serializable objects.
    """
    pathlib.Path(os.path.dirname(STATE_PATH)).mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)


def file_hash(path: str) -> str:
    """Calculate the SHA-256 hash of a file.

    Computes a cryptographic hash by reading the file in 1 MB chunks,
    allowing efficient hashing of large files without loading them
    entirely into memory.

    Args:
        path: The absolute or relative path to the file to hash.

    Returns:
        A hexadecimal string representing the SHA-256 hash of the
        file's contents.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        PermissionError: If the file cannot be read due to permissions.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


async def run() -> None:
    """Main watcher loop for ComfyUI output files.

    Continuously monitors the configured output directory for new files,
    uploads them to MinIO object storage, and publishes NATS events
    with artifact metadata and presigned URLs.

    The function:
    - Validates MinIO credentials are configured
    - Loads the upload state to avoid re-uploading files
    - Ensures the target MinIO bucket exists
    - Polls the output directory at configured intervals
    - Uploads new files with timestamped S3-style keys
    - Generates presigned URLs for temporary access
    - Publishes completion events to NATS for downstream processing

    Raises:
        RuntimeError: If MinIO credentials are not set or bucket
            creation fails.

    The loop runs indefinitely until the process is terminated.
    """
    if not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
        raise RuntimeError("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set")

    state = load_state()
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_USE_SSL,
    )
    nc = NATS()
    await nc.connect(servers=[NATS_URL])

    # Ensure MinIO bucket exists with proper error handling
    try:
        if not client.bucket_exists(BUCKET):
            client.make_bucket(BUCKET)
            logger.info(f"Created MinIO bucket: {BUCKET}")
    except Exception as exc:
        logger.error(f"Failed to verify/create MinIO bucket '{BUCKET}': {exc}")
        raise RuntimeError(f"MinIO bucket setup failed for '{BUCKET}': {exc}") from exc

    while True:
        for root, _, files in os.walk(OUTPUT_DIR):
            for fname in files:
                if not fname.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                    continue
                path = os.path.join(root, fname)
                h = file_hash(path)

                if h in state.get("uploaded", {}):
                    continue

                size_bytes = os.path.getsize(path)
                timestamp = int(time.time())
                key = f"comfyui/{timestamp}/{fname}"

                try:
                    with open(path, "rb") as f:
                        client.put_object(BUCKET, key, f, length=size_bytes)
                    state.setdefault("uploaded", {})[h] = {
                        "key": key,
                        "timestamp": timestamp,
                        "size": size_bytes,
                    }
                    save_state(state)

                    public_url = (
                        f"{PUBLIC_BASE_URL}/{BUCKET}/{key}".replace("//", "/").replace("http:/", "http://").replace("https:/", "https://")
                    )

                    payload = {"artifact_uri": f"s3://{BUCKET}/{key}", "meta": {"public_url": public_url}}

                    # Generate presigned URL with error handling
                    try:
                        payload["meta"]["presigned_url"] = client.presigned_get_object(BUCKET, key, expires=timedelta(hours=PRESIGN_HOURS))
                    except Exception as presign_exc:
                        logger.warning(f"Failed to generate presigned URL for {key}: {presign_exc}")
                        # Continue without presigned URL - not critical for all workflows

                    env = envelope("gen.image.result.v1", payload, source="comfy-watcher")
                    await nc.publish("gen.image.result.v1", json.dumps(env).encode())
                    logger.info(f"Uploaded and announced: {key}")
                except Exception as exc:
                    logger.error(f"Error processing file {path}: {exc}", exc_info=True)
                    # Continue to next file instead of aborting entire loop

        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
