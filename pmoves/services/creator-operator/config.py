"""creator-operator service config (env-driven, no secrets in code)."""
import os
from pathlib import Path


class Config:
    SERVICE_SLUG = "creator-operator"
    PORT = int(os.getenv("CREATOR_OPERATOR_PORT", "8120"))
    NATS_URL = os.getenv("NATS_URL", "")
    SUBJECT_WORKORDER = "archon.workorder.creator.v1"
    SUBJECT_RESULT = "creator.operator.result.v1"
    SUBJECT_ASSIGNED = "creator.operator.assigned.v1"
    # Registries (repo-relative; overridable for tests)
    REPO_ROOT = Path(os.getenv("PMOVES_REPO_ROOT", Path(__file__).resolve().parents[3]))
    NODES_PATH = Path(os.getenv("CREATOR_NODES_PATH", REPO_ROOT / "pmoves/config/operator_nodes.yaml"))
    MODELS_PATH = Path(os.getenv("CREATOR_MODELS_PATH", REPO_ROOT / "pmoves/config/creator_models.yaml"))
    PENDING_DIR = Path(os.getenv("CREATOR_PENDING_DIR", REPO_ROOT / "pmoves/services/creator-operator/.pending"))
