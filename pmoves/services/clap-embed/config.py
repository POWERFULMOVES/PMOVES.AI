import os


class Config:
    MODEL_ID = os.environ.get("CLAP_MODEL_ID", "laion/larger_clap_music")
    MODEL_REVISION = os.environ.get("CLAP_MODEL_REVISION", "main")
    SR = int(os.environ.get("CLAP_SAMPLE_RATE", "48000"))          # CLAP expects 48 kHz
    CLIP_SECONDS = int(os.environ.get("CLAP_CLIP_SECONDS", "10"))  # deterministic window
    HOP_SECONDS = int(os.environ.get("CLAP_HOP_SECONDS", "10"))    # non-overlapping
    PORT = int(os.environ.get("CLAP_EMBED_PORT", "8108"))
    DEVICE = os.environ.get("CLAP_DEVICE", "cpu")                  # cpu|cuda|mps
    NATS_URL = os.environ.get("NATS_URL", "")                      # empty disables NATS
    REGISTRY_URL = os.environ.get("MODEL_REGISTRY_URL", "http://model-registry:8110")
    EMBED_DIM = 512
    # Hard cap on raw audio payload size (bytes) to bound memory before decode.
    # Default 25 MiB. Applies to both the HTTP upload and the NATS request path.
    MAX_UPLOAD_BYTES = int(os.environ.get("CLAP_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
