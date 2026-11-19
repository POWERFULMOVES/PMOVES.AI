# Local-Model Review Infra Plan — Spark + Knuckles — 2026-10-12

**Status:** DRAFT — coding plan only, zero API burn (operator directive 2026-10-12)
**Goal:** coding-plan and PR review served by LOCAL models on Spark and Knuckles — replacing the API-based `claude-review`/`kilocode-review` workflows (which also carry the documented claude-code-action Bun regression, register rows 1698/1845/2492).
**Lane owner:** a0-sidecar · **Reviewer gate:** operator → then Three-Body on implementation PRs.

## 1. Measured node state (probed read-only 2026-10-12 12:45 EDT)

### Spark — PMOVES-SPARK (100.89.7.106, runner label `spark`)

| Item | Measured |
|---|---|
| Ollama service | **active** |
| GPU | NVIDIA GB10, 128GB unified memory |
| Archive mount | **HEALTHY** — /dev/sdb 3.6T, 10% used (10-09 I/O event resolved at mount level) |
| Serving roster (api/tags) | qwen3-embedding:4b, qwen3-embedding:8b ONLY |
| Manifest store on disk | ALSO shows gemma4, hermes3, kimi-k2.6, nemotron-3-super, llama3.2 → **roster/store mismatch: non-embedding blobs damaged by the 10-09 I/O error, dropped from roster** |
| Root disk | 78% used, 196G free (enough for P0 pulls) |
| CI runner | `runs-on: spark` proven (clm-eval-spark.yml); actions-runner + actions-runner-spark on node (10-07 register row) |
| Deploy script | `scripts/spark_deploy_models.sh` — P0: `qwen3.5:35b-a3b-q4_K_M` (~20GB), `qwen2.5-coder:32b` (~19GB) |

### Knuckles — PMOVES-B850-AI-TOP (100.122.182.3)

| Item | Measured |
|---|---|
| SSH | pmoves@ works (passwordless, verified this session) |
| PMOVES stack | tensorzero-ui/gateway/clickhouse, cipher, nats, neo4j — all Up healthy |
| llama.cpp | build tree `/opt/llama.cpp-rdna4` exists; **no llama-server containers, no GGUFs found, haproxy inactive** |
| Ports | 8000/8080/8081 listening **loopback-only**; :8081 answers 404 HTML (not llama.cpp) — external review traffic impossible today |
| Deploy script | `scripts/pmoves-b850-ai-top.sh` ready — Gemma 4 31B Q4_K_M (~18GB) primary, dual R9700 64GB VRAM, HAProxy :8000 TLS |

**Verdict:** Spark = one model-pull away from being the review brain. Knuckles = one deployment away (script exists, never executed). Neither serves a coding model today.

## 2. Lane A — Spark review brain (first, fastest path)

1. **Roster repair:** `ollama pull qwen2.5-coder:32b` then `qwen3.5:35b-a3b-q4_K_M` (P0 per spark_deploy_models.sh). Do NOT trust the damaged manifests — pull fresh; delete broken entries after verify.
2. **Verify:** api/tags shows both; `/api/generate` smoke on qwen2.5-coder with a trivial review prompt; `/v1/embeddings` re-probe.
3. **Expose:** tailscale serve `/ollama` already proven ON (10-07 lane) — re-verify from sidecar; review consumers hit `https://pmoves-spark.tailcad9b4.ts.net/ollama/v1` (OpenAI-compatible).
4. **CI wiring:** new `.github/workflows/local-review.yml`, `runs-on: spark`, steps call localhost:11434 (runner is on-node — no tailnet hop in CI). Output posts as PR review comment. **Zero API tokens anywhere.**
5. **Fallback ladder:** qwen2.5-coder:32b (primary) → gemma4 roster repair → nemotron-3-super (on disk, pull if blobs bad). Circuit breaker: 2 failed pulls on one model → skip to next in ladder, log, continue.

## 3. Lane B — Knuckles review node (parallel, second capacity)

1. Execute `pmoves-b850-ai-top.sh` as designed (Gemma 4 31B Q4_K_M, dual R9700, llama.cpp HIP containers).
2. **Bind fix:** HAProxy :8000 must listen on the tailnet IP (100.122.182.3), not loopback — the measured loopback-only bind is why nothing external can reach it. Edit haproxy frontend `bind` before service start.
3. **Verify:** from sidecar, `https://100.122.182.3:8000/v1/models` returns JSON (llama.cpp OpenAI-compat), then one real review completion.
4. **Register:** add `runs-on: knuckles` runner (or reuse the kimi harness lane's existing runner if present) + label in local-review.yml matrix.

## 4. Review workflow design (both lanes)

- Trigger: PR opened/synchronize, label-gated first (`local-review` label) to control runner burn, then expand.
- Context assembly: `git diff origin/main...HEAD` + PR body — **coding-plan review prompt**: correctness risks, missing Testing section, Known Roads violations (raw docker/tailscale commands), secrets-in-diff check.
- Model call: OpenAI-compatible chat completion against localhost endpoint (spark: :11434 ollama; knuckles: :8000 haproxy→llama.cpp).
- Output: structured verdict (APPROVE / CHANGES-REQUIRED / QUESTION) + findings list, posted as review comment tagged `[local-review:<model>]`.
- Governance: **Control-body assist only** — never approves merges; Three-Body review still gates. Signed review comments (CHIT) once a runner signing card exists (follow-up).
- Fail-open + fall-through: endpoint down or empty review → post `[local-review: SKIPPED — <node> unreachable]` (loud, distinct state, exit 0) and **fall through to the next configured reviewer** (knuckles → secondary model → hosted reviewer). 'No reviewer available' must be a distinct loud state, never a pass. Review infrastructure must never block merges.
- **Registry compliance (repo rule):** no hardcoded models or host endpoints in the workflow — model + endpoint resolve from the model registry (`pmoves/config/models.yaml` surface / `model-registry-1` service); workflow reads a `review_model` input via the registry, defaults resolved at run time. *(2026-10-14 drift-audit fix: was `model_registry.yaml` — file doesn't exist, real surface is `models.yaml`.)*

## 5. KiloClaw tie-in

Self-hosted OpenClaw (KILOCLAW_RECOVERY_PLAN Lane 2) points its model config at these same local endpoints for utility tasks — the claw's coding-plan drafting gets reviewed by Spark/Knuckles locally. Hosted-claw credit drain drops to zero for internal review traffic.

## 6. Sequencing

1. A1 roster repair (pulls ~40GB total, ~30-60 min) — **start here**
2. A2/A3 verify + serve re-check (minutes)
3. A4 local-review.yml PR (plan-reviewed first, then code)
4. B1-B3 Knuckles deployment (longer; HIP build + 18GB pull) — parallel track, don't block Lane A
5. Sign-trail after each lane delivery

## 7. Success criteria

- [ ] Spark serves qwen2.5-coder:32b (roster repaired) — `/api/generate` 200 with review-shaped output
- [ ] local-review.yml posts a `[local-review:*]` comment on a test PR, zero API calls (verify in action logs)
- [ ] Knuckles HAProxy answers `/v1/models` from tailnet with Gemma 4 31B listed
- [ ] Fail-open proven: stop ollama on spark → PR review step SKIPPED, merge flow unaffected
- [ ] Register rows CLAIM/RELEASE per lane; CHIT trail signed

## 8. Open items

1. Damaged-blob cleanup policy on Spark (default: pull-over, delete after verify)
2. Knuckles runner registration (new self-hosted runner vs reuse kimi-harness runner)
3. Review prompt calibration set — use PRs #3263/#3255/#3317 (already Control-reviewed, ground-truth labels exist)
4. Jetsons: out of scope for review lane (RAM-bound); lightweight browser tier per fleet plan only
