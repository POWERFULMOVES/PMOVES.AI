import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIRS = [
    REPO_ROOT / "pmoves" / "contracts",
    REPO_ROOT / "PMOVES-ToKenism-Multi" / "contracts",
]
TOKENISM_TOPICS = [
    "tokenism.attribution.recorded.v1",
    "tokenism.cgp.weekly.v1",
    "tokenism.cgp.ready.v1",
    "tokenism.swarm.population.v1",
]


def _load_schema(contracts_dir: Path, rel_path: str) -> dict:
    return json.loads((contracts_dir / rel_path).read_text(encoding="utf-8"))


def _validator(schema: dict) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.mark.parametrize("contracts_dir", CONTRACT_DIRS)
@pytest.mark.parametrize("spec", ["chit.cgp.v0.2", "chit.cgp.v1.0"])
def test_geometry_cgp_schema_accepts_wire_specs(contracts_dir: Path, spec: str):
    schema = _load_schema(contracts_dir, "schemas/geometry/cgp.v1.schema.json")
    cgp = {
        "spec": spec,
        "super_nodes": [
            {"constellations": [{"id": "c1", "points": [{"id": "p1"}]}]}
        ],
    }

    _validator(schema).validate(cgp)


@pytest.mark.parametrize("contracts_dir", CONTRACT_DIRS)
def test_swarm_meta_schema_tightens_fitness_and_unknown_fields(contracts_dir: Path):
    schema = _load_schema(contracts_dir, "schemas/geometry/swarm.meta.v1.schema.json")
    validator = _validator(schema)
    valid = {
        "namespace": "pmoves.tokenism",
        "modality": "economic_simulation",
        "pack_id": "sim-week-1",
        "status": "active",
        "best_fitness": 0.9,
        "avg_fitness": 0.8,
        "metrics": {"gini": 0.3, "custom": {"ok": True}},
        "ts": "2026-05-22T00:00:00Z",
        "sig": {"alg": "HMAC-SHA256", "hmac": "abc"},
    }
    validator.validate(valid)

    with pytest.raises(ValidationError):
        validator.validate({**valid, "best_fitness": 1.2})

    with pytest.raises(ValidationError):
        validator.validate({**valid, "unexpected": True})


@pytest.mark.parametrize("contracts_dir", CONTRACT_DIRS)
def test_tokenism_topics_are_registered_and_payloads_validate(contracts_dir: Path):
    topics = json.loads((contracts_dir / "topics.json").read_text(encoding="utf-8"))["topics"]
    for topic in TOKENISM_TOPICS:
        assert topic in topics
        assert (contracts_dir / topics[topic]["schema"]).exists()

    samples = {
        "tokenism.attribution.recorded.v1": {
            "chit_id": "chit-1",
            "address": "0xABC",
            "action": "spending",
            "amount": 12.5,
            "week": 1,
            "category": "groceries",
            "merkle_root": "0x" + "a" * 64,
            "timestamp": "2026-05-22T00:00:00Z",
        },
        "tokenism.cgp.weekly.v1": {
            "week": 1,
            "cgp": {"spec": "chit.cgp.v1.0", "super_nodes": []},
            "super_node_count": 0,
            "total_attributions": 0,
            "gini": 0.4,
            "poverty_rate": 0.1,
            "cgp_spec": "chit.cgp.v1.0",
        },
        "tokenism.cgp.ready.v1": {
            "cgp": {"spec": "chit.cgp.v1.0", "super_nodes": []},
            "super_node_count": 0,
            "source": "test",
            "cgp_spec": "chit.cgp.v1.0",
            "timestamp": "2026-05-22T00:00:00Z",
        },
        "tokenism.swarm.population.v1": {
            "namespace": "pmoves.tokenism",
            "modality": "economic_simulation",
            "pack_id": "sim-week-1",
            "status": "active",
            "best_fitness": 0.75,
            "metrics": {"gini": 0.3},
            "timestamp": "2026-05-22T00:00:00Z",
        },
    }

    for topic, payload in samples.items():
        schema = _load_schema(contracts_dir, topics[topic]["schema"])
        _validator(schema).validate(payload)
