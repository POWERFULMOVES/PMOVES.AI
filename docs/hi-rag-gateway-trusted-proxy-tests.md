# hi-rag Gateway Trusted Proxy Tests

_Updated: 2025-10-09_

## Purpose

The regression suite in `pmoves/services/hi-rag-gateway/tests/test_trusted_proxies.py` verifies that
both hi-rag gateways enforce strict client IP handling:

- Requests arriving directly from untrusted peers must not be able to spoof an internal address via
  the `X-Forwarded-For` header.
- Requests relayed by a trusted proxy (as configured via `HIRAG_TRUSTED_PROXIES`) continue to
  surface the original client IP so downstream allow/deny logic remains intact.

## Test Coverage

| Test | Scenario | Expected outcome |
| ---- | -------- | ---------------- |
| `test_v1_rejects_spoofed_forwarded_for` | v1 gateway receives a request from an untrusted client that supplies a forged `X-Forwarded-For`. | Gateway blocks the request with `403 Forbidden`. |
| `test_v1_allows_trusted_proxy_forwarded_for` | v1 gateway is contacted by a trusted proxy and the forwarded address is valid. | Request succeeds with `200 OK`. |
| `test_v2_rejects_spoofed_forwarded_for` | v2 gateway receives a forged forwarded IP from an untrusted peer. | Gateway blocks the request with `403 Forbidden`. |
| `test_v2_allows_trusted_proxy_forwarded_for` | v2 gateway receives a request via a trusted proxy. | Request succeeds with `200 OK`. |

## Running the Tests

```bash
pip install -r pmoves/services/hi-rag-gateway/requirements.txt pytest
pytest pmoves/services/hi-rag-gateway/tests/test_trusted_proxies.py
```

The tests rely on lightweight stubs for optional service dependencies (Qdrant, Sentence
Transformers, Neo4j, etc.) so they execute quickly without requiring external services.

## Configuration Notes

Set `HIRAG_TRUSTED_PROXIES` (comma-separated list of IPs or CIDR blocks) to define which proxy
addresses may forward client IPs. The tests monkeypatch `_TRUSTED_PROXY_NETWORKS` directly to
simulate different deployment scenarios, but production environments should configure the
environment variable instead.
