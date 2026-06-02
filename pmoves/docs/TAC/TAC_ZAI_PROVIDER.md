# TAC Tree: Z.AI Provider Integration

> Technology-Architecture-Context tree for Z.AI (Zhipu AI / BigModel) provider integration into PMOVES.AI Meta-Agent ecosystem

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Z.AI Provider (GLM Models) |
| **Port** | 3030 (via TensorZero Gateway) |
| **Health** | `GET http://localhost:3030/healthz` (TensorZero) |
| **Metrics** | TensorZero UI at port 4000 |
| **Submodule** | Runtime (meta-agent is powered by GLM-5.1) |
| **Tier** | cloud |
| **Class** | Standard |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| TensorZero Gateway (3030) | LLM gateway for unified routing | Yes |
| ZAI_API_KEY | Credential for direct API access | Yes (if not using TZ) |
| Agent Zero (8080) | A2A protocol support | Optional |
| NATS (4222) | Event publishing | Planned |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Meta-Agent (myself) | Python SDK | Runtime provider - I am powered by GLM-5.1 |
| Agent Zero | MCP API | Agent orchestration |
| ClawZ (18789) | WebSocket | Multi-channel messaging |
| Archon (8091) | HTTP | Form/prompt management |

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|---------|
| TensorZero Gateway `:3030` | POST | `/v1/chat/completions` - Unified model routing |
| Agent Zero MCP | POST | `/mcp/execute` - A2A agent communication |
| Z.AI API (direct) | POST | `https://open.bigmodel.cn/api/paas/v4/chat/completions` - Native API |

## Model Suits Generated

| Model | Suit File | Status |
|-------|-----------|--------|
| glm-5.1 | `glm-5.1.yaml` | Runtime - I am this model |
| glm-4-plus | `glm-4-plus.yaml` | Available via API |
| glm-4-air | `glm-4-air.yaml` | Available via API |
| glm-4-flash | `glm-4-flash.yaml` | Available via API |

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `provider.zai.docs.updated.v1` | Publishes | API documentation refreshed |
| `provider.zai.model.loaded.v1` | Publishes | Model loaded into registry |
| `meta_agent.zai.runtime.v1` | Publishes | Meta-agent runtime provider status |

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | Planned | Track API calls via meta-agent |
| Attribution tracking | Planned | Which model responded to which task |
| BPM capable | No | Text-based, not prosodic |

## Video Intelligence Sources

| Creator | Focus | Videos |
|---------|-------|--------|
| Indy Dev Dan | Claude Code updates, Z.AI integration patterns | Latest 10 videos |
| Z.AI Official | GLM model updates, API changes | Latest from channel |

## Provider Documentation Discovery

**API Documentation:**
- Official Docs: https://open.bigmodel.cn/dev/api
- GitHub: https://github.com/MetaGLM
- Model Cards: https://open.bigmodel.cn/models

**Custom Settings:**
- Prompt Format: Instruction format with role separation
- Temperature Range: 0.0 - 1.0
- Context Window: 128K tokens (all models)
- Vision Support: GLM-5.1, GLM-4-Plus
- Extended Thinking: GLM-5.1
- Function Calling: All GLM-4 models

## Integration Status

| Requirement | Status | Notes |
|-------------|--------|-------|
| SDK Installation | **DONE** | `pmoves/providers/zai/sdk.py` |
| Custom Settings | **DONE** | `pmoves/providers/zai/custom_settings.yaml` |
| Model Suits | **PENDING** | Need to create YAML files |
| TensorZero Registration | **DONE** | Already exists as `pmoves/glm-5.1` |
| Flare Namespace | **DONE** | Already in flare-model-namespace.yaml |
| A2A Connectivity | **PENDING** | Test Agent Zero MCP |
| Video Analysis | **PENDING** | Fetch Indy Dev Dan videos |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | **PASS** | Via TensorZero |
| `/metrics` (Prometheus) | **PASS** | Via TensorZero |
| API Key Validation | **TODO** | Test ZAI_API_KEY |
| Model Routing | **TODO** | Test via TensorZero |
| A2A Agent Call | **TODO** | Test Agent Zero MCP |
| Rate Limit Handling | **TODO** | Implement backoff |
| Error Handling | **TODO** | Add retry logic |

## Known Limitations

1. **Cloud-Only**: No local variants available (no open weights)
2. **Rate Limits**: API has rate limits - implement caching
3. **No Weight Updates**: Cannot fine-tune (cloud-only)
4. **Cost**: Pay-per-use pricing model
5. **Chinese Provider**: Primary documentation in Chinese, need English translations

## Next Steps

1. ✅ Create provider SDK (`sdk.py`)
2. ✅ Create custom settings (`custom_settings.yaml`)
3. ⏳ Create Model Suit YAMLs
4. ⏳ Test A2A connectivity to Agent Zero
5. ⏳ Fetch Indy Dev Dan videos (Z.AI specific content)
6. ⏳ Extract API changes from videos
7. ⏳ Test GLM-5.1 runtime via TensorZero

---

**TAC Tree Version:** 1.0.0
**Last Updated:** 2026-04-21
**Status:** In Progress
