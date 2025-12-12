from fastapi.testclient import TestClient


class _FakePoint:
    def __init__(self, payload, score):
        self.payload = payload
        self.score = score


def test_hirag_query_returns_stubbed_results(load_service_module, monkeypatch):
    gateway = load_service_module("hirag_gateway", "services/hi-rag-gateway/gateway.py")

    fake_results = [
        _FakePoint(
            payload={
                "doc_id": "doc-1",
                "section_id": "sec-1",
                "chunk_id": "chunk-1",
                "text": "example chunk",
                "namespace": "demo",
            },
            score=0.9,
        )
    ]

    class _FakeQdrant:
        def __init__(self):
            self.calls = []

        def search(self, collection, query_vector, limit, query_filter, with_payload, with_vectors):
            self.calls.append(
                {
                    "collection": collection,
                    "query_vector": query_vector,
                    "limit": limit,
                    "query_filter": query_filter,
                    "with_payload": with_payload,
                    "with_vectors": with_vectors,
                }
            )
            return fake_results

    gateway.qdrant = _FakeQdrant()
    monkeypatch.setattr(gateway, "embed_query", lambda q: [0.1, 0.2, 0.3])
    monkeypatch.setattr(gateway, "driver", None)
    # Disable Tailscale IP checks for TestClient (returns "testclient" as IP)
    monkeypatch.setattr(gateway, "TAILSCALE_ONLY", False)
    monkeypatch.setattr(gateway, "require_tailscale", lambda request, admin_only=False: None)

    client = TestClient(gateway.app)
    resp = client.post(
        "/hirag/query",
        json={"query": "hello world", "namespace": "demo", "k": 4, "alpha": 0.5},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "hello world"
    assert body["results"] and body["results"][0]["doc_id"] == "doc-1"
    assert gateway.qdrant.calls, "qdrant.search should be invoked"
    assert gateway.qdrant.calls[0]["limit"] == 16
