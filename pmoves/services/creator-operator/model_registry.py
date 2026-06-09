"""Creator model registry + license-gate helpers."""
from pathlib import Path
import yaml


def load_models(path: Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data.get("models", {})


def lookup_model(models: dict, workflow_id: str) -> dict:
    if workflow_id not in models:
        raise KeyError(f"no model registered for workflow {workflow_id!r}")
    return models[workflow_id]


def requires_ack(model: dict) -> bool:
    return bool(model.get("requires_ack", False))
