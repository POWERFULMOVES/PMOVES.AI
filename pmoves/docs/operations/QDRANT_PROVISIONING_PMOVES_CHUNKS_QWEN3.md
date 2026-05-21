# Qdrant `pmoves_chunks_qwen3` provisioning runbook

**Runbook ID:** `QDRANT-PMOVES-CHUNKS-QWEN3-2026-05-20`
**Lane:** L9 of 5-lane orchestration (see `~/.claude/plans/nested-sniffing-pancake.md`)
**TAC node:** `p7.nats.embedding-quality` in `pmoves/configs/tac_trees/pinokio-p7.tac.yaml`

## When to use this

The TAC node `p7.nats.embedding-quality` is `status: pending` with notes "Needs Qdrant `pmoves_chunks_qwen3` collection created on prod." This runbook closes the gap.

The stack standardized on TensorZero + Qwen3-embedding:4b (PR #1082). Without this collection, P7-triggered ingestion through Extract Worker fails on first write to Qdrant.

## Critical: dimension is 2560, NOT 3072

Per `pmoves/services/extract-worker/CLAUDE.md`:

> Vector dimensions (cite if you change models):
> - `qwen3_embedding_4b_local` → **2560d** (NOT 3072 — common mistake)
> - `qwen3_embedding_8b_local` → **4096d**

Hi-RAG-v2 assumes 2560d unless overridden. Operator memory `project_qwen3_embedding_dimensions.md` independently confirms the 2560d figure. The collection MUST be created at 2560d or the pipeline silently produces zero-hit retrieval.

## Pre-flight

```bash
# Verify Qdrant container is healthy
docker ps --filter name=pmoves-qdrant --format '{{.Names}}\t{{.Status}}'
# Expect: pmoves-qdrant-1  Up <time> (healthy)

# Verify auth path: QDRANT_URL + QDRANT_API_KEY are in env.tier-data (operator-side)
ls pmoves/env.tier-data 2>&1 | head -1  # should exist; never paste the key in chat
```

## Method 1 — Operator-side script (recommended)

```bash
cd pmoves
. ./scripts/with-env.sh                                    # loads env.shared + tier files
python3 scripts/provision_qdrant_pmoves_chunks_qwen3.py
```

Exit codes:
| Exit | Meaning |
|---:|---|
| `0` | Collection exists at 2560d/Cosine OR was just created |
| `1` | Auth or network error (check `QDRANT_URL` + `QDRANT_API_KEY`) |
| `2` | Dimension mismatch detected — operator decides recreate vs separate collection name |
| `3` | Unexpected exception |

Sample output (fresh create):
```
[provision] Target: http://qdrant:6333/collections/pmoves_chunks_qwen3 (dim=2560, distance=Cosine)
[provision] Collection 'pmoves_chunks_qwen3' not found — creating fresh.
[provision] OK — created pmoves_chunks_qwen3 (dim=2560, distance=Cosine).
```

Sample output (already-exists, no-op):
```
[provision] Target: http://qdrant:6333/collections/pmoves_chunks_qwen3 (dim=2560, distance=Cosine)
[provision] OK — collection 'pmoves_chunks_qwen3' already exists at dim=2560, distance=Cosine. No-op.
```

## Method 2 — Run inside extract-worker container (if env already loaded there)

If `pmoves-extract-worker-1` is up with `QDRANT_*` env loaded:

```bash
docker cp pmoves/scripts/provision_qdrant_pmoves_chunks_qwen3.py \
    pmoves-extract-worker-1:/tmp/provision.py

docker exec pmoves-extract-worker-1 python3 /tmp/provision.py
```

## Method 3 — Direct Qdrant API (no Python client)

If the operator wants to avoid the qdrant-client dependency:

```bash
# Read QDRANT_URL + QDRANT_API_KEY from env (never paste in chat)
. ./pmoves/scripts/with-env.sh

# Probe — does collection exist?
curl -sS -H "api-key: $QDRANT_API_KEY" "$QDRANT_URL/collections/pmoves_chunks_qwen3" | jq .

# If 404 / not-found: create
curl -sS -X PUT \
    -H "api-key: $QDRANT_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"vectors":{"size":2560,"distance":"Cosine"}}' \
    "$QDRANT_URL/collections/pmoves_chunks_qwen3" | jq .
# Expect: {"result": true, "status": "ok"}
```

## Dim-mismatch troubleshooting

If the probe reveals an existing collection at the wrong dimension (e.g., 3072 from an older Qwen variant), the operator has three options — each captured by the script's exit-code-2 stderr block:

**A. Recreate with data loss** (only if the collection has no useful data):

```bash
QDRANT_RECREATE_ON_DIM_MISMATCH=1 \
    python3 pmoves/scripts/provision_qdrant_pmoves_chunks_qwen3.py
```

**B. Use a separate collection name** (preserves data, deploys side-by-side):

Update `QDRANT_COLLECTION=pmoves_chunks_qwen3_v2` (or similar) in `env.shared` / `env.tier-data`, restart Extract Worker + Hi-RAG-v2 consumers, run the provisioning script against the new name (edit `COLLECTION` constant or duplicate the script).

**C. Investigate root cause**: confirm Extract Worker (`worker.py`) and Hi-RAG Gateway v2 are both pinned to `qwen3_embedding_4b_local` in their TensorZero config. The 3072 vs 2560 trap usually originates from a stale model rename or a downstream consumer that hard-coded the older dim.

## Post-provisioning verification

```bash
# Confirm collection lands at the right shape
curl -sS -H "api-key: $QDRANT_API_KEY" "$QDRANT_URL/collections/pmoves_chunks_qwen3" \
    | jq '.result.config.params.vectors'
# Expect: {"size": 2560, "distance": "Cosine", ...}

# Confirm Extract Worker can write (after first P7-triggered ingestion)
docker logs pmoves-extract-worker-1 --tail 20 | grep -i qdrant
# Expect: successful upserts, no dim-mismatch errors
```

## TAC status flip

After verification, flip the TAC node from `pending` to `done`:

```yaml
# pmoves/configs/tac_trees/pinokio-p7.tac.yaml
- id: p7.nats.embedding-quality
  ...
  status: done   # ← was: pending
  notes: "Provisioned 2026-05-20 via pmoves/scripts/provision_qdrant_pmoves_chunks_qwen3.py. 2560d/Cosine confirmed."
```

This PR ships the status as `in_progress` (script + doc landing, operator-execution pending). Operator's follow-up commit flips `in_progress` → `done` once the script runs cleanly.

## Verification checklist (PR signoff)

- [ ] `pmoves/scripts/provision_qdrant_pmoves_chunks_qwen3.py` exists and `python3 -m py_compile` passes
- [ ] Script reads `QDRANT_URL` + `QDRANT_API_KEY` from env (never hard-coded)
- [ ] Dim constant `DIM = 2560` matches `pmoves/services/extract-worker/CLAUDE.md` declaration
- [ ] TAC node `p7.nats.embedding-quality` status flipped to `in_progress` in the PR
- [ ] Runbook documented 3 invocation methods + 3 dim-mismatch responses
- [ ] Cross-references to extract-worker subsystem CLAUDE.md + `project_qwen3_embedding_dimensions` memory

## Cross-references

- Source pattern: `pmoves/services/extract-worker/worker.py:138-169` (`_ensure_qdrant`)
- Dimension authority: `pmoves/services/extract-worker/CLAUDE.md` § TensorZero embedding contract
- TAC node: `pmoves/configs/tac_trees/pinokio-p7.tac.yaml` (`p7.nats.embedding-quality`)
- Convergence checklist 5090-CLAUDE next-24h: `pmoves/docs/AGENTS/AGNOTE_CONVERGENCE_CHECKLIST_2026-05-16.md` (now closed)
- Plan file: `~/.claude/plans/nested-sniffing-pancake.md` § L9

agent_signature (advisory unsigned-local): `ACK::5090-CLAUDE::QDRANT-PROVISIONING-RUNBOOK-2026-05-20`
