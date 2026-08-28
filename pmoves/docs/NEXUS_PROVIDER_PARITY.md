# PMOVES Nexus Provider Parity
_Last updated: 2026-03-25_

## Purpose
Nexus is the provider abstraction boundary for PMOVES.AI.

It does not replace TensorZero today. It defines the rules that let PMOVES use provider-native SDKs where they are strongest while keeping one runtime contract for the mesh.

That means:
- TensorZero stays the default execution gateway.
- Provider-native SDKs stay additive.
- Every provider must map back onto the same PMOVES envelope for tools, streaming, structured outputs, retries, tracing, and usage capture.

The authoritative config for this layer is `pmoves/config/model_nexus.yaml`.

## Why This Exists
The repo currently mixes three realities:
1. TensorZero is the canonical shared gateway.
2. Several services already rely on OpenAI-compatible shapes.
3. Future agent maturity will benefit from provider-native features instead of forcing every provider through the same lowest-common-denominator wrapper.

Without an explicit boundary, each lane will invent its own adapter logic. That breaks parity, observability, and debugging.

Nexus fixes that by separating:
- provider culture: use the native SDK when it unlocks real provider capability
- PMOVES contract: keep one request and response shape for the mesh
- execution default: keep TensorZero as the safe default path

## Architecture Boundary
### Control Plane
- Supabase model registry remains authoritative for providers, aliases, mappings, and deployment state.
- CHIT and Graphiti remain the workflow rails.

### Routing Plane
- Nexus decides the adapter boundary.
- TensorZero remains the default route.
- Native SDK adapters are explicit exemptions, not ad hoc bypasses.

### Runtime Plane
- OpenAI uses the official SDK and native request surface where justified.
- Anthropic uses the official SDK and native request surface where justified.
- Gemini uses the provider-native Google client where justified.
- NVIDIA NIM serves Nemotron on beefy GPU nodes where optimized local inference matters more than remote provider access.
- Ollama and vLLM remain local-first lanes, typically routed through TensorZero unless a lane proves a reason not to.

## Parity Rules
A provider-native lane is acceptable only if it preserves these PMOVES-level behaviors:
- Tool calls normalize into one logical shape.
- Structured outputs normalize into one logical shape.
- Streaming emits a predictable event model.
- Retry and timeout policy are explicit.
- Trace context is preserved for NATS, CHIT, and Graphiti correlation.
- Usage and cost accounting can still be mirrored into shared observability.
- Health and readiness checks stay visible at the service level.

If a native lane cannot preserve those rules, it should route through TensorZero.

## Provider Strategy
### OpenAI
- Prefer the official OpenAI SDK for native lanes.
- Use provider-native reasoning, multimodal, tools, and structured output features when they materially improve the lane.
- Mirror request metadata and usage back into the shared PMOVES telemetry path.
- Fall back to TensorZero when parity would otherwise drift.

### Anthropic
- Prefer the official Anthropic SDK for native reasoning lanes.
- Keep the same PMOVES envelope so upstream agents do not learn Anthropic-specific schemas.
- Fall back to TensorZero for shared or cost-sensitive routes.

### Gemini
- Prefer the provider-native Google client for multimodal and long-context lanes.
- Keep media and retrieval flows mapped onto the same PMOVES envelope.
- Fall back to TensorZero when the lane needs the shared gateway path.

### NVIDIA / Nemotron
- Prefer NVIDIA NIM for Nemotron on 5090-class and larger GPU nodes.
- Treat Nemotron as a first-class local reasoning lane for claw and coding workflows.
- Mirror health, usage, and trace metadata back into the shared PMOVES telemetry path.
- Keep AIQ as the workflow/orchestration layer when NVIDIA-native agent composition is needed; keep NIM as the inference substrate.
- Fall back to TensorZero or Ollama when a direct Nemotron lane is unavailable.

### Local Providers
- Ollama and vLLM remain first-class local providers.
- TensorZero remains the preferred way to route into them for observability and fallback control.
- Direct local adapter use should be the exception, not the default.

## Implementation Order
1. Keep TensorZero as the default route for all current mesh lanes.
2. Add additive Nexus adapter scaffolding for OpenAI, Anthropic, and Gemini.
3. Add NVIDIA NIM-backed Nemotron support for beefy GPU claw lanes.
4. Normalize one PMOVES request envelope and one response envelope.
5. Add parity tests comparing native adapters to TensorZero-backed results.
6. Expose adapter health and mirrored usage metrics.
7. Expand the P7 and skill lanes only after the agent mesh contract is stable.

## Review Split
### Codex
- Own the Nexus contract docs and config.
- Build adapter scaffolding and parity tests.
- Keep changes additive to the existing TensorZero-first routing policy.

### 4090 Claude
- Validate remote P7, skill, and multimodal mesh behavior.
- Pressure-test local model parity and timeout behavior on the actual nodes.
- Verify that voice and mobile-adjacent flows survive the new adapter layer.

## Immediate Next Files
- `pmoves/config/model_nexus.yaml`
- `pmoves/docs/MODEL_FABRIC_CONTRACT.md`
- native adapter modules under the service lanes that need direct SDK use
- parity tests for request and response normalization
