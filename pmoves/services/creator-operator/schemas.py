"""JSON-schema validation for creator-operator contracts."""
import json
from pathlib import Path
from jsonschema import validate

_DIR = Path(__file__).resolve().parent / "contracts"
_WORKORDER = json.loads((_DIR / "creator_workorder.schema.json").read_text(encoding="utf-8"))
_RESULT = json.loads((_DIR / "creator_operator_result.schema.json").read_text(encoding="utf-8"))


def validate_workorder(d: dict) -> None:
    validate(instance=d, schema=_WORKORDER)


def validate_result(d: dict) -> None:
    validate(instance=d, schema=_RESULT)
