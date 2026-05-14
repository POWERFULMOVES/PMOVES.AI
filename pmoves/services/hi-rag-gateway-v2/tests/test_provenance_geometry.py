from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def provenance_geometry_module():
    path = Path(__file__).resolve().parents[1] / "provenance_geometry.py"
    spec = importlib.util.spec_from_file_location("hirag_provenance_geometry_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["hirag_provenance_geometry_test"] = module
    spec.loader.exec_module(module)

    try:
        yield module
    finally:
        sys.modules.pop("hirag_provenance_geometry_test", None)


def _sample_payload() -> dict:
    return {
        "content_id": "discord:msg-123",
        "text": "Provenance and merkle lineage anchor the semantic shape while favorite words keep the lexicon contextual.",
        "source_ref": "discord://guild/channel/msg-123",
        "shape_id": "shape-abc123",
        "merkle_root": "0x" + "b" * 64,
        "graphiti_mark": "graphiti:shape-abc123:feedface",
        "kb_namespace": "hirag-provenance",
        "accepted_reason": "context_shape_passed",
        "provenance_refs": [
            "discord://guild/channel/msg-123",
            "shape:shape-abc123",
            "merkle:0xbbbb",
        ],
        "favorite_words": ["provenance", "chimera"],
        "anchor_terms": ["merkle", "lineage"],
        "semantic_weights": [
            {"term": "merkle", "weight": 0.92, "anchor": True},
            {"term": "provenance", "weight": 0.81, "favorite": True},
            {"term": "chimera", "weight": 0.63},
        ],
        "scorecard": {"noise_score": 0.14},
        "meta": {"worker": "content-provenance-gate"},
    }


def test_extract_weighted_terms_preserves_flags(provenance_geometry_module):
    module = provenance_geometry_module
    terms = module.extract_weighted_terms(_sample_payload())

    by_term = {item["term"].lower(): item for item in terms}
    assert "merkle" in by_term
    assert "provenance" in by_term
    assert by_term["merkle"]["anchor"] is True
    assert by_term["provenance"]["favorite"] is True
    assert all(0.15 <= item["weight"] <= 1.0 for item in terms)


def test_provenance_payload_to_cgp_builds_text_constellation(provenance_geometry_module):
    module = provenance_geometry_module
    cgp = module.provenance_payload_to_cgp(_sample_payload())

    assert cgp["type"] == "geometry.cgp.v1"
    assert cgp["source"] == "content.hirag.accepted.v1"
    super_node = cgp["super_nodes"][0]
    constellation = super_node["constellations"][0]
    assert constellation["id"] == "shape-abc123"
    assert constellation["meta"]["source_topic"] == "content.hirag.accepted.v1"
    assert constellation["points"]
    assert all(point["modality"] == "text" for point in constellation["points"])


def test_provenance_payload_to_hyperdimensions_save_emits_live_surface_config(provenance_geometry_module):
    module = provenance_geometry_module
    save = module.provenance_payload_to_hyperdimensions_save(_sample_payload())

    assert save["version"] == 1
    assert "function surface" in save["surface"]["code"]
    names = {item["name"] for item in save["extraParameters"]}
    assert {"delta", "kappa", "hz", "fitness", "attribution", "spectrum", "lineage"} <= names
    assert save["meta"]["source_topic"] == "content.hirag.accepted.v1"
    assert save["meta"]["shape_id"] == "shape-abc123"
