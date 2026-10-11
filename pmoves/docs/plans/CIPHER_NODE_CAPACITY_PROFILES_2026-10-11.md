# Cipher per node capacity — embedding profiles, multi-dimension vectors, BRV as the floor (design)

| Field | Value |
|---|---|
| Status | **DRAFT, design only.** No code, compose or submodule edits ride on this document. |
| Owner | 5090-CLAUDE (`5090-claude`), lane `docs/cipher-capacity-profiles`, claim filed 2026-10-11 |
| Base | `origin/main` `6d179267a7` |
| Pairs with | `pmoves/docs/TAC/TAC_CIPHER.md` (service), `plans/AGINT_PASSPORT_DESIGN_2026-10-08.md` §3c node evidence (PR #3317), B850 handoff `B850_MEMORY_TRAVELS.md` (BRV, per-node token store) |

Operator canon, 2026-10-11 (verbatim): "your cipher config should be different based on node capacity and embeds are multi dimensions plus lightwieght brv".

## 1. What is true today (measured 2026-10-11 on 5090)

| Fact | Evidence |
|---|---|
| One static cipher config for every node: `embedding: ollama / qwen3-embedding:4b / dimensions: 2560` | `Pmoves-cipher/memAgent/cipher.yml:14-18`; `pmoves/docker-compose.yml:4126` `EMBEDDING_DIM=2560` |
| The embedding URL class is wrong on this node: compose defaults `OLLAMA_URL` / `OLLAMA_BASE_URL` to `host.docker.internal:11434`; nothing answers on 11434 here; the compose Ollama publishes on 11436 and is `pmoves-ollama:11434` in-network | `pmoves/docker-compose.yml:4107-4109`; `curl :11434/api/tags` no answer, `:11436/api/tags` lists `qwen3-embedding:4b` (2.5 GB), `embeddinggemma:300m`, `nomic-embed-text` |
| Consequence: every memory stored this session landed `embedded: false` (four stores, ids `XJ9At38W6D8i`, `wQRWVtVC_tV8`, `qeHUXPilxlYe`, …) so recall is text-match only | cipher `pmoves_cipher_store` responses, 2026-10-11 |
| BRV (ByteRover CLI, the context-tree memory, BM25, no embeddings) is not installed on 5090; `pm-brv-check.sh` (#3313) says so at claude-pmoves launch | `command -v brv` → missing; `pmoves/scripts/pm-brv-check.sh` |
| Qwen3-Embedding is one family with Matryoshka (MRL) output: 0.6B up to 1024 d, 4B up to 2560 d, 8B up to 4096 d, each with user-defined dims from 32 | model cards `Qwen/Qwen3-Embedding-{0.6B,4B}` README, read 2026-10-11 |
| Capacity is already described per node: hardware profiles carry RAM/VRAM (`workstation_5090.yaml` ram 192; `dgx-spark-grace-blackwell.yaml` 128 unified; `z890-coordinator.yaml` 32; `jetson-orin-nano.yaml` 8 unified); `node_roles.yaml` has `gpu-compute` / `always-on` / `lab` / `gateway` roles and `persistent` / `ephemeral-microvm` runtime shapes | `pmoves/config/profiles/*.yaml`, `pmoves/config/node_roles.yaml:60-140` |
| Nothing connects the two: no profile, role or vocabulary entry names an embedding model or dimension; cipher reads one env | grep `EMBED|dimension` across `pmoves/config*`: only the compose literal above |

So "different based on node capacity" has no surface to be different on yet, and on this node the single surface it does have points at a port that is not listening.

## 2. Design

### 2a. Capacity class → embedding profile (declared, never probed at runtime)

A `cipher_profile` key on each node's entry in `pmoves/configs/node-vocabulary.yaml`, resolved from the hardware profile when the entry is written, read by the launcher and the compose env (the harness-overlay rule: declare, do not detect).

| Class | Nodes (from profiles) | Embedding model | Dim | BRV |
|---|---|---|---|---|
| `gpu-large` (≥24 GB VRAM or ≥64 GB unified) | 5090, 4090, B850 (2×32 GB), SPARK | `qwen3-embedding:4b` | 2560 local, **1024 fleet** (see 2b) | yes |
| `gpu-small` / `cpu-rich` (8–16 GB VRAM, or ≥32 GB RAM no GPU) | Z890, KVM4-1, KVM4-2 | `qwen3-embedding:0.6b` | 1024 | yes |
| `edge` (≤8 GB unified, or `ephemeral-microvm`) | Jetson Orin Nano, Jetson Nano, KVM2, tip-of-iceberg nodes | none local; embed through TensorZero to a `gpu-compute` node when reachable | 1024 (remote) | **BRV is the whole memory when offline** |

The class is a derived field with a documented rule, so a new profile gets a class without a judgement call; the rule lives next to `node_roles.yaml`'s role definitions.

### 2b. Multi-dimension vectors: one family, two named vectors, comparable fleet-wide

MRL prefix compatibility holds **within one model**, not across sizes: a 4B vector truncated to 1024 d is not in the 0.6B's space. So "multi dimensions" means two things at once:

1. **Fleet vector, `q06b_1024`:** every node that embeds at all writes this one (0.6B at 1024 d, or 4B output is not used for it). It is the dimension the cross-node collection is searchable in, and it is small enough that an `edge` node can compute it remotely and store it locally.
2. **Local vector, `q4b_2560`:** `gpu-large` nodes also write the 4B vector at full width for better local recall.

Qdrant named vectors carry both in one collection (`vectors: {q06b_1024: 1024 cosine, q4b_2560: 2560 cosine}`); a search names the vector it uses. Each point's payload records `embed_model`, `embed_dim`, `node`, so a vector's provenance is on the record, which is what the passport's node evidence (§3c) and the trail need anyway. The current single `EMBEDDING_DIM=2560` collection becomes the `q4b_2560` vector of the new one; migration is a re-embed of existing points for `q06b_1024`, done once per node.

### 2c. BRV as the floor

`brv` (byterover-cli, BM25 context tree) runs everywhere Node ≥20 runs, needs no GPU and no vector store, and is already what the Pmoves-cipher fork's upstream recommends. It is the memory an `edge` node has when the mesh is down, and the second retrieval path on every node (the Marco/Polo semantic bridge stays on embeddings). Install route stays the one `cli_tools.yaml` records (`npm install -g byterover-cli`); `pm-brv-check.sh` already says when it is missing. What is new: `edge` nodes treat `brv=MISSING` as a P1 at launch, not a WARN, because for them it is the only memory.

### 2d. Where each piece lands (and the road it needs)

| Piece | File | Road |
|---|---|---|
| `cipher_profile` per node | `pmoves/configs/node-vocabulary.yaml` | none (config, not protected) |
| class rule + table | `pmoves/config/node_roles.yaml` comment block, this doc | none |
| `OLLAMA_EMBED_MODEL`, `EMBEDDING_DIM`, named-vector config from the profile | `pmoves/docker-compose*.yml` cipher stanza, `env.shared` keys generated per node | `compose:pr:<n>` |
| named vectors + payload fields | `Pmoves-cipher` fork (`embedding.ts`, Qdrant provisioning) | submodule PR, then gitlink bump |
| TensorZero embedding route for `edge` | `pmoves/tensorzero/config/tensorzero.toml` embedding functions (the same 32 `host.docker.internal:11434` entries that are wrong today) | none, but see §3 |

## 3. Do this first: the URL class

None of §2 produces an embedding on 5090 until `OLLAMA_URL` / `OLLAMA_BASE_URL` in the cipher stanza and the `api_base` entries in `tensorzero.toml` point at the compose Ollama (`http://pmoves-ollama:11434` in-network; the published host port is `${OLLAMA_HOST_PORT:-11435}`, 11436 on this node). `tz_registry_sync.py` already defaults registry blocks to `pmoves-ollama:11434/v1`, so the fix is aligning the two hand-written defaults with the generator, under the compose road. That lane is unclaimed as of this writing; it is the precondition for every row above and for the `embedded: true` that the four memories stored today did not get.

## 4. Open questions for the operator

1. Fleet vector at 1024 d from 0.6B (every node can compute it) vs. 4B-only through TensorZero routing (one space, but `edge` nodes have no memory when the mesh is down). This doc recommends 2b: both, named.
2. Should `gpu-large` nodes also keep `embeddinggemma:300m` (already pulled on 5090) as a third named vector for the chat corpus, or is one family the rule?
3. Where does the class rule live for a node that is both `gpu-compute` and `ephemeral-microvm` (same box, two shapes)? Proposed: the shape decides, per request path.
