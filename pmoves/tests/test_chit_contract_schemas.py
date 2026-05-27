import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, RefResolver, ValidationError


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
    "tokenism.settlement.requested.v1",
    "tokenism.settlement.recorded.v1",
    "tokenism.settlement.failed.v1",
]


def _load_schema(contracts_dir: Path, rel_path: str) -> dict:
    return json.loads((contracts_dir / rel_path).read_text(encoding="utf-8"))


def _validator(schema: dict, schema_path: Path | None = None) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    resolver = (
        RefResolver(base_uri=schema_path.resolve().as_uri(), referrer=schema)
        if schema_path
        else None
    )
    return Draft202012Validator(
        schema,
        resolver=resolver,
        format_checker=FormatChecker(),
    )


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
            "cgp": {
                "spec": "chit.cgp.v1.0",
                "super_nodes": [
                    {"constellations": [{"id": "c1", "points": [{"id": "p1"}]}]}
                ],
            },
            "super_node_count": 1,
            "total_attributions": 0,
            "gini": 0.4,
            "poverty_rate": 0.1,
            "cgp_spec": "chit.cgp.v1.0",
        },
        "tokenism.cgp.ready.v1": {
            "cgp": {
                "spec": "chit.cgp.v1.0",
                "super_nodes": [
                    {"constellations": [{"id": "c1", "points": [{"id": "p1"}]}]}
                ],
            },
            "super_node_count": 1,
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
        "tokenism.settlement.requested.v1": {
            "settlement_id": "settlement_1234abcd5678ef00",
            "source_subject": "tokenism.cgp.weekly.v1",
            "source_id": "weekly-cgp-1",
            "cgp_spec": "chit.cgp.v1.0",
            "cgp_hash": "sha256:" + "a" * 64,
            "week": 1,
            "status": "planned",
            "settlement_profile": "weekly-grotoken-v1",
            "instructions": [
                {
                    "instruction_id": "settle_inst_1234abcd5678ef00",
                    "idempotency_key": "tokenism:weekly-grotoken-v1:week-1:0xabc:1234abcd5678ef00",
                    "lane": "firefly",
                    "action": "grotoken_mint",
                    "address": "0xABC",
                    "amount": 100.0,
                    "asset": "GRO",
                    "source_ref": {
                        "cgp_hash": "sha256:" + "a" * 64,
                        "merkle_root": "0x" + "b" * 64,
                        "contributor_weight": 1.0,
                        "raw_contribution": 100.0,
                    },
                    "firefly": {"transaction_type": "deposit"},
                    "contract": {"contract": "GroToken", "method": "mint"},
                    "metadata": {"categories": ["grotoken"]},
                }
            ],
            "totals": {
                "instruction_count": 1,
                "amount": 100.0,
                "asset": "GRO",
            },
            "created_at": "2026-05-22T00:00:00Z",
            "agent_id": "PMOVES-AGENT-ZERO-CODEX",
            "signature": {"alg": "HMAC-SHA256", "kid": "agent-zero-test", "hmac": "abc"},
        },
        "tokenism.settlement.recorded.v1": {
            "settlement_id": "settlement_1234abcd5678ef00",
            "instruction_id": "settle_inst_1234abcd5678ef00",
            "idempotency_key": "tokenism:weekly-grotoken-v1:week-1:0xabc:1234abcd5678ef00",
            "lane": "firefly",
            "action": "grotoken_mint",
            "status": "recorded",
            "amount": 100.0,
            "asset": "GRO",
            "firefly_transaction_id": "tx-1",
            "timestamp": "2026-05-22T00:00:00Z",
            "agent_id": "PMOVES-AGENT-ZERO-CODEX",
            "signature": {"alg": "HMAC-SHA256", "kid": "agent-zero-test", "hmac": "abc"},
        },
        "tokenism.settlement.failed.v1": {
            "settlement_id": "settlement_1234abcd5678ef00",
            "instruction_id": "settle_inst_1234abcd5678ef00",
            "idempotency_key": "tokenism:weekly-grotoken-v1:week-1:0xabc:1234abcd5678ef00",
            "lane": "firefly",
            "action": "grotoken_mint",
            "error_code": "FIREFLY_UNAVAILABLE",
            "error_message": "Firefly API unavailable",
            "retryable": True,
            "timestamp": "2026-05-22T00:00:00Z",
            "agent_id": "PMOVES-AGENT-ZERO-CODEX",
            "signature": {"alg": "HMAC-SHA256", "kid": "agent-zero-test", "hmac": "abc"},
        },
    }

    for topic, payload in samples.items():
        schema_path = contracts_dir / topics[topic]["schema"]
        schema = _load_schema(contracts_dir, topics[topic]["schema"])
        _validator(schema, schema_path).validate(payload)
