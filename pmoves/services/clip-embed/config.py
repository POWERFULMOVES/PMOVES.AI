import os


class Config:
    MODEL_ID = os.environ.get("CLIP_MODEL_ID", "openai/clip-vit-large-patch14")
    MODEL_REVISION = os.environ.get("CLIP_MODEL_REVISION", "main")
    PORT = int(os.environ.get("CLIP_EMBED_PORT", "8109"))
    DEVICE = os.environ.get("CLIP_DEVICE", "cpu")
    NATS_URL = os.environ.get("NATS_URL", "")
    REGISTRY_URL = os.environ.get("MODEL_REGISTRY_URL", "http://model-registry:8110")
    EMBED_DIM = 768
    MAX_UPLOAD_BYTES = int(os.environ.get("CLIP_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
