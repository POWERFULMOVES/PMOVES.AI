from fastapi.testclient import TestClient

from pmoves.services.common.events import envelope


def _load_gate(load_service_module, monkeypatch):
    """
    Load the content provenance gate service module with NATS disabled for tests.
    
    Sets the environment variable `CONTENT_PROVENANCE_DISABLE_NATS` to `"1"` using the provided `monkeypatch`, then loads and returns the gate service module by calling `load_service_module` with the service name and entry path.
    
    Parameters:
        load_service_module (callable): Function that accepts `(service_name, entry_path)` and returns the loaded module.
        monkeypatch: Pytest `monkeypatch` fixture used to set environment variables.
    
    Returns:
        module: The loaded `content_provenance_gate_service` module.
    """
    monkeypatch.setenv("CONTENT_PROVENANCE_DISABLE_NATS", "1")
    return load_service_module(
        "content_provenance_gate_service",
        "services/content-provenance-gate/main.py",
    )


def test_preview_pipeline_shapes_attests_and_accepts(load_service_module, monkeypatch):
    gate = _load_gate(load_service_module, monkeypatch)
    client = TestClient(gate.app)

    response = client.post(
        "/v1/preview/raw",
        json={
            "content_id": "msg-001",
            "text": (
                "Provenance mapping needs a semantic lexicon with merkle attestation, "
                "hyperdimensional anchors, and contextual shape controls for HiRAG."
            ),
            "source_ref": "spark://messages/msg-001",
            "favorite_words": ["provenance", "hyperdimensional", "shape"],
            "aliases": ["spark", "hirag"],
            "labels": ["infra", "art"],
        },
    )

    assert response.status_code == 200
    body = response.json()

    shaped = body["shaped"]
    assert shaped["shape_id"].startswith("shape-")
    assert "provenance" in shaped["anchor_terms"]
    assert shaped["semantic_density"] >= gate.SEMANTIC_DENSITY_MIN

    attested = body["attested"]
    assert attested["merkle_root"].startswith("0x")
    assert attested["graphiti_mark"].startswith("graphiti:")
    assert attested["hyperbolic_coords"]["curvature"] == -1.0

    assert body["decision_subject"] == gate.ACCEPTED_SUBJECT
    assert body["decision"]["kb_namespace"] == gate.HIRAG_NAMESPACE


def test_preview_pipeline_rejects_low_signal_content(load_service_module, monkeypatch):
    gate = _load_gate(load_service_module, monkeypatch)
    client = TestClient(gate.app)

    response = client.post(
        "/v1/preview/raw",
        json={
            "content_id": "msg-noise",
            "text": "buy buy buy now!!! buy!!! now!!!",
            "source_ref": "spark://messages/msg-noise",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["decision_subject"] == gate.REJECTED_SUBJECT
    assert "rejected_reason" in body["decision"]


def test_new_content_topics_validate_against_contracts(load_service_module, monkeypatch):
    gate = _load_gate(load_service_module, monkeypatch)

    preview = gate.preview_raw_pipeline(
        {
            "content_id": "msg-contracts",
            "text": "Shape and provenance should map favorite words to a merkle-rooted semantic surface.",
            "source_ref": "spark://messages/msg-contracts",
            "favorite_words": ["shape", "provenance"],
        }
    )

    shaped_env = envelope(gate.SHAPED_SUBJECT, preview["shaped"], source="test")
    attested_env = envelope(gate.ATTESTED_SUBJECT, preview["attested"], source="test")
    decision_env = envelope(preview["decision_subject"], preview["decision"], source="test")

    assert shaped_env["topic"] == gate.SHAPED_SUBJECT
    assert attested_env["topic"] == gate.ATTESTED_SUBJECT
    assert decision_env["topic"] == preview["decision_subject"]
