# Claw Coordination NATS Subjects

Cross-node claw coordination events for the GEOMETRY BUS. These subjects enable
multi-claw orchestration across the PMOVES fleet (4090, 5090, 3090Ti, KVM nodes).

## Subjects

### `claw.node.announce.v1`

Published by each active claw instance. Consumed by peer claws and GPU orchestrator.

```json
{
  "claw_id": "pmoves-4090-claw-01",
  "node_id": "pmoves-4090",
  "coding_stack": "claude_code",
  "tz_function": "coding_claude_fallback",
  "status": "active",
  "gpu_model_loaded": "qwen3-coder:30b",
  "vram_used_mb": 6500,
  "ts": "2026-03-28T12:00:00Z"
}
```

### `claw.task.request.v1`

Published by any claw to delegate work to a claw with matching capabilities.

```json
{
  "request_id": "req-uuid",
  "from_claw": "pmoves-5090-codex-01",
  "from_node": "pmoves-5090",
  "required_caps": ["embeddings", "coding"],
  "preferred_node": "pmoves-4090",
  "task_type": "embed_and_index",
  "payload": {"text": "...", "collection": "pmoves_chunks_qwen3"},
  "priority": "normal",
  "ts": "2026-03-28T12:00:00Z"
}
```

### `claw.task.result.v1`

Published by executing claw. Optionally includes a CGP packet for GEOMETRY BUS attribution.

```json
{
  "request_id": "req-uuid",
  "from_claw": "pmoves-4090-claw-02",
  "from_node": "pmoves-4090",
  "status": "completed",
  "result": {"embedding": "...", "indexed": true},
  "cgp": { "spec": "chit.cgp.v0.1" },
  "duration_ms": 1250,
  "ts": "2026-03-28T12:01:00Z"
}
```

### `claw.task.handoff.v1`

Published by a claw ending its session to transfer context to a successor.

```json
{
  "handoff_id": "handoff-uuid",
  "from_claw": "pmoves-4090-claw-01",
  "to_node": "pmoves-5090",
  "context_summary": "Completed auth refactor, tests passing, PR ready",
  "files_modified": ["src/auth.ts", "src/middleware.ts"],
  "cipher_ref": "cipher-memory-uuid",
  "graphiti_trail": "signed-trail-entry",
  "ts": "2026-03-28T14:00:00Z"
}
```

### `claw.provider.activated.v1`

Published by the Provider Activation Cascade when a new LLM provider key is
configured and the system morphs to incorporate it.

```json
{
  "node_id": "pmoves-4090",
  "provider": "minimax",
  "env_var": "MINIMAX_API_KEY",
  "models_added": ["chat_minimax"],
  "functions_updated": ["coding_minimax"],
  "coding_stacks_activated": ["minimax_token_plan"],
  "vram_warnings": [],
  "timestamp": "2026-03-28T16:00:00Z",
  "success": true
}
```

### `claw.provider.deactivated.v1`

Published when a provider key is removed or rotated. Peer nodes may need to
update their catalogs or take over workloads.

```json
{
  "node_id": "pmoves-4090",
  "provider": "minimax",
  "env_var": "MINIMAX_API_KEY",
  "models_removed": ["chat_minimax"],
  "timestamp": "2026-03-28T18:00:00Z",
  "success": true
}
```

## See Also

- `.claude/context/nats-subjects.md` — Canonical NATS topology index
- `pmoves/docs/CLAW_TAXONOMY.md` — Claw taxonomy (PR #1151)
- `pmoves/config/profiles/laptop-4090.yaml` — 4090 node config with claw section
