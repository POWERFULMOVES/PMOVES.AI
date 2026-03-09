# Codex Home Overlay: PMOVES-Pipecat

Scope:
- Pipecat and Flute voice runtime parity.

Core checks:
- `curl -fsS http://localhost:8055/healthz | jq .`
- `curl -fsS http://localhost:7861/gradio_api/info | jq .`
- `make -C pmoves verify-all`

Related parity tokens:
- `/pipecat:status`
- `/pipecat:connect`
- `/voice:synthesize`
