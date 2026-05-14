# TAC Tree: Anthropic Provider Integration

> Technology-Architecture-Context tree for Anthropic (Claude) provider integration into PMOVES.AI Meta-Agent ecosystem

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Anthropic Provider (Claude) |
| **Port** | 3030 (via TensorZero Gateway) |
| **Health** | `GET http://localhost:3030/healthz` (TensorZero) |
| **Metrics** | TensorZero UI at port 4000 |
| **Submodule** | Native (meta-agent is Claude) |
| **Tier** | cloud |
| **Class** | Standard |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| TensorZero Gateway (3030) | LLM gateway for unified routing | Yes |
| ANTHROPIC_API_KEY | Credential for direct API access | Yes (if not using TZ) |
| Agent Zero (8080) | A2A protocol support | Optional |
| NATS (4222) | Event publishing | Planned |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Meta-Agent (myself) | Python SDK | Native provider - I am Claude |
| Agent Zero | MCP API | Agent orchestration |
| ClawZ (18789) | WebSocket | Multi-channel messaging |
| Archon (8091) | HTTP | Form/prompt management |

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|---------|
| TensorZero Gateway `:3030` | POST | `/v1/chat/completions` - Unified model routing |
| Agent Zero MCP | POST | `/mcp/execute` - A2A agent communication |
| Anthropic API (direct) | POST | `https://api.anthropic.com/v1/messages` - Native API |

## Model Suits Generated

| Model | Suit File | Status |
|-------|-----------|--------|
| claude-sonnet-4 | `claude-sonnet.yaml` | Native - I am this model |
| claude-opus-4 | `claude-opus.yaml` | Available via API |
| claude-haiku-4 | `claude-haiku.yaml` | Available via API |

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `provider.anthropic.docs.updated.v1` | Publishes | API documentation refreshed |
| `provider.anthropic.model.loaded.v1` | Publishes | Model loaded into registry |
| `meta_agent.anthropic.native.v1` | Publishes | Meta-agent native provider status |

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | Planned | Track API calls via meta-agent |
| Attribution tracking | Planned | Which model responded to which task |
| BPM capable | No | Text-based, not prosodic |

## Video Intelligence Sources

| Creator | Focus | Videos |
|---------|-------|--------|
| Indy Dev Dan | Claude Code API updates, new features | Latest 10 videos |
| Discover AI | Multi-provider benchmarks | Playlist analysis |

## Provider Documentation Discovery

**API Documentation:**
- Official Docs: https://docs.anthropic.com
- API Reference: https://docs.anthropic.com/en/api/getting-started-with-the-api
- Model Cards: https://docs.anthropic.com/en/docs/about-models

**Custom Settings:**
- Prompt Format: XML tags preferred
- Temperature Range: 0.0 - 1.0
- Context Window: 200K tokens (all models)
- Vision Support: Yes (all models)
- Extended Thinking: Opus only

## Integration Status

| Requirement | Status | Notes |
|-------------|--------|-------|
| SDK Installation | **DONE** | `pmoves/providers/anthropic/sdk.py` |
| Custom Settings | **DONE** | `pmoves/providers/anthropic/custom_settings.yaml` |
| Model Suits | **PENDING** | Need to create YAML files |
| TensorZero Registration | **PENDING** | Add to `tensorzero.toml` at `weight=0.0` |
| Flare Namespace | **PENDING** | Add to `flare-model-namespace.yaml` |
| A2A Connectivity | **PENDING** | Test Agent Zero MCP |
| Video Analysis | **PENDING** | Fetch Indy Dev Dan videos |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | **PASS** | Via TensorZero |
| `/metrics` (Prometheus) | **PASS** | Via TensorZero |
| API Key Validation | **TODO** | Test ANTHROPIC_API_KEY |
| Model Routing | **TODO** | Test via TensorZero |
| A2A Agent Call | **TODO** | Test Agent Zero MCP |
| Rate Limit Handling | **TODO** | Implement backoff |
| Error Handling | **TODO** | Add retry logic |

## Known Limitations

1. **Cloud-Only**: No local variants available (no open weights)
2. **Rate Limits**: API has rate limits - implement caching
3. **No Weight Updates**: Cannot fine-tune (cloud-only)
4. **Cost**: Pay-per-use pricing model

## Next Steps

1. ✅ Create provider SDK (`sdk.py`)
2. ✅ Create custom settings (`custom_settings.yaml`)
3. ⏳ Create Model Suit YAMLs
4. ⏳ Register in TensorZero (weight=0.0)
5. ⏳ Register in flare namespace
6. ⏳ Test A2A connectivity to Agent Zero
7. ⏳ Fetch Indy Dev Dan videos
8. ⏳ Extract API changes from videos

---

**TAC Tree Version:** 1.0.0  
**Last Updated:** 2026-04-21  
**Status:** In Progress
