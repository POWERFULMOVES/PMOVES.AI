# Claude -> Codex Parity Map (PMOVES)
_Last updated: 2026-02-16_

This map translates common `.claude/commands/*` workflows into Codex-native
operations (`make`, `curl`, and existing PMOVES scripts).

## Health and bring-up

| Claude command | Codex equivalent |
| --- | --- |
| `/health:quick` | `make -C pmoves codex-health-quick` |
| `/health:check-all` | `make -C pmoves verify-all` |
| `/deploy:up` | `SUPABASE_RUNTIME=cli make -C pmoves up` |
| `/deploy:smoke-test` | `make -C pmoves smoke` |

## Retrieval and research

| Claude command | Codex equivalent |
| --- | --- |
| `/search:hirag` | `curl -X POST http://localhost:8086/hirag/query -H "Content-Type: application/json" -d '{"query":"<q>","top_k":10,"rerank":true}'` |
| `/search:supaserch` | `make -C pmoves supaserch-smoke` then query HTTP fallback `http://localhost:8099/v1/search?q=<q>` |
| `/search:deepresearch` | `make -C pmoves deepresearch-smoke` or `make -C pmoves deepresearch-smoke-in-net` |

## CHIT, geometry, and EvoSwarm

| Claude command | Codex equivalent |
| --- | --- |
| `/chit:bus status` | `curl -fsS http://localhost:8086/hirag/admin/stats | jq .` |
| `/chit:encode` | publish through PMOVES producers (`pmoves-yt`, `hi-rag-v2`) and validate via `make -C pmoves smoke` |
| `/chit:decode` | use geometry calibration/report endpoints and retrieval assertions |
| `/chit:visualize` | use geometry UI/demo targets (`make -C pmoves web-geometry`) |
| EvoSwarm checks | `curl -fsS http://localhost:8113/healthz` and `curl -fsS http://localhost:8113/swarm/status | jq .` |

## Agent orchestration and MCP

| Claude command | Codex equivalent |
| --- | --- |
| `/agents:status` | `curl -fsS http://localhost:8080/healthz | jq .` and `curl -fsS http://localhost:8091/healthz | jq .` |
| `/agents:mcp-query` | `curl -fsS http://localhost:8080/mcp/health | jq .` then authenticated `/mcp/*` calls |
| `/botz:mcp` | BotZ config: `PMOVES-BoTZ/config/codex/mcp_gateway.json` and PMOVES root codex profile |
| Claude Cipher MCP (`pmoves-cipher` in `.claude/mcp.json`) | `uv run --directory ./pmoves-cipher-mcp python -m cipher_mcp.server` and verify `curl -fsS http://localhost:8096/health` |

## Voice stack (Flute/TTS/Pipecat)

| Claude command | Codex equivalent |
| --- | --- |
| `/pipecat:status` | `curl -fsS http://localhost:8055/healthz | jq .` |
| `/tts:status` | `curl -fsS http://localhost:7861/gradio_api/info | jq .` |
| `/tts:synthesize` | Flute synth endpoint `POST /v1/voice/synthesize/prosodic` |

## Submodule integration audit

| Claude practice | Codex equivalent |
| --- | --- |
| Manual review of module docs | `make -C pmoves codex-audit` |
| Update command docs | Update `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md` and this parity map |

## Infrastructure (Known Roads)

| Claude command | Codex equivalent |
| --- | --- |
| `/deploy:services` (volume reset) | `make -C pmoves volume-reset SERVICE=...` |
| `/deploy:services` (volume list) | `make -C pmoves volume-list` |
| docker prune (safe) | `make -C pmoves docker-prune` |
| docker prune (aggressive) | `make -C pmoves docker-prune-all` |
| branch audit | `make -C pmoves branch-audit` |
| branch cleanup | `make -C pmoves branch-cleanup EXECUTE=1` |

## Guidance

- Keep Claude and Codex workflows semantically aligned, not text-identical.
- Prefer stable Make targets over ad-hoc one-off shell snippets.
- For every new Claude command added to `.claude/commands/`, add a Codex mapping here.
