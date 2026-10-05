# HF Model Inventory — 2026-09-22

**Node:** PMOVES-SPARK (`/home/powerfulmoves/agent-zero/PMOVES.AI`) · **Branch:** `feat/comfyui-ui-to-api` · **Operating surface:** OpenRoom
**Task:** `t-20260922T202933Z-7e2b9f4a1c8d` · **Goal:** `g-20260922T142400Z-d1e2f3a4b5c6d7e8` · round 1 · criterion **SC-1**
**Pre-flight:** `make -C pmoves submodule-integrity` exit 0 (81 gitlinks, 0 uninitialized, 0 drifted, 0 conflicts)
**Sibling tasks:** SC-2 probe `t-20260922T202933Z-8f3a0b5b2d9e` reads this file's verdicts; SC-3/4/5 do not start until SC-2 settles.

---

## 1. Bar and disclosure policy

This document answers one question: **for each of the three candidates the user named, what is the grounded capability claim that downstream SC-2/SC-3/SC-4/SC-5 may rely on?** It does **not** probe any model, does **not** change harness state, and does **not** open a registry PR.

Every cell below carries a disclosure tag:

- **`doc-verified`** — sourced from the architecture-doc commit named in §0 of the row. Treat as the model's own published claim, not a fleet measurement.
- **`card-verified`** — sourced from the model's own HF model card (cited inline). Treat as the model's own published claim, not a fleet measurement.
- **`fleet-verified`** — measured on this fleet. None of the three rows are fleet-verified at this round.
- **`unverified`** — no source of evidence stronger than the user naming the candidate. Recorded plainly, not invented.

An `unverified` cell is **acceptable**. A misleading cell is not. The user's framing distinguishes "verified" from "research input," and §0 of each row names which it is.

---

## 2. Source-of-options anchors

| Candidate | Task spec anchor | Actual anchor in git | Resolution |
|---|---|---|---|
| Laya | `eedd32913 docs(architecture): Laya is the leading open alternative — inverts §5 latency sort` | `f212431da docs(architecture): Laya is the leading open alternative — inverts §5 latency sort` (2026-09-21) | **Spec mismatch.** The task spec transposed two commits; `eedd32913` is actually the OpenJEV row (see below). Per the developer failure-mode discipline (ground in evidence, not in prose), this row cites **`f212431da`**. The doc file itself (`pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md`) is reachable via `git show <hash>:<path>`; it is on branch `origin/docs/typesafe-system-one-integration-scan`, not on the local `feat/comfyui-ui-to-api` tip, so the workspace does not carry a working-copy of the doc — every quote below is from `git show`. |
| Needle 3 | `5c191efa1 docs(architecture): Needle 3 as the local sibling to hosted TypeSafe` (2026-09-21) | `5c191efa1 docs(architecture): Needle 3 as the local sibling to hosted TypeSafe` (2026-09-21) | Match. |
| OpenJEV | "entered by the operator at session time as a fresh research input with **no fleet-side trace**" | `eedd32913 docs(architecture): open-Jev landscape corrects two §3 rankings` (2026-09-21) — covers `com-kotobalabs/open-jev-deberta-v3-large` in §11 | **Spec mismatch in the other direction.** The task spec asserts no fleet-side trace; the architecture doc carries a substantial §11 entry on `com-kotobalabs/open-jev-deberta-v3-large` with measured figures, lineage, and correction context. Per the disclosure policy, this row's verified facts come from that doc commit; the absence of a **fleet measurement** (no model run on this fleet) is the genuinely unverified half. |

**Resolution policy applied throughout:** the candidate-level evidence is the architecture doc commit, **plus** the model card / Hub listing for facts the doc itself does not assert. Where the two disagree, the model card wins. Where neither covers a column, the column is `unverified`.

---

## 3. Verdict table

| # | Candidate | HF repo path | License | Active params | Verdict | Source-of-options anchor |
|---|---|---|---|---|---|---|
| 1 | **Laya** | `convaiinnovations/laya` (3 checkpoints) | Apache-2.0 | 421M (root) / 322M (multilingual, mmBERT-base) / 421M (typed-decisions) | **`local-viable`** | `f212431da` |
| 2 | **Needle 3** | `Cactus-Compute/needle3` | Apache-2.0 | 121M | **`defer`** — no documented per-option distribution, no documented ordered-level between-level Score | `5c191efa1` |
| 3 | **OpenJEV** (`open-jev-deberta`) | `com-kotobalabs/open-jev-deberta-v3-large` | Apache-2.0 | ~435M (DeBERTa-v3-large; the doc states "deberta-v3-large"; parameter count is from the DeBERTa-v3-large public card, not from the OpenJEV card) | **`defer`** — 256-token state cap excludes Tier 1–2 except T1.2; weakest measured axis is ordered level sets | `eedd32913` |

---

## 4. Row 1 — Laya (`convaiinnovations/laya`)

> *"the serious open alternative … 1,450 likes, trending score 1,417 … published 18 Sep 2026 … Apache-2.0, tagged `commercial-use`."* — `git show f212431da:pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md` §12

| column | value | disclosure |
|---|---|---|
| **HF repo path** | `convaiinnovations/laya` — three checkpoints in one repo: `laya` (root), `laya-multilingual`, `laya-typed-decisions` | doc-verified (`f212431da` §12) — Hub listing exists; not opened from this fleet |
| **License** | Apache-2.0; model card is tagged `commercial-use` | doc-verified (`f212431da` §12) — single-license, no dual-licensing gating |
| **Parameter count** | root `laya` = **421M** (ModernBERT-large); `laya-multilingual` = **322M** (mmBERT-base); `laya-typed-decisions` = **421M** (ModernBERT-large). These are **active** params; CQ-training (RLCD) does not add inference-time parameters | doc-verified (`f212431da` §12 table). Card-level confirmation not opened from this fleet. |
| **Available quants** | Parent repos: safetensors only (ModernBERT/mmBERT native). **Ports:** `mys/laya-multilingual-GGUF` (1.3K dl), `mys/laya-GGUF` (374), `Weidows/laya-multilingual-GGUF` (249), `mys/laya-typed-decisions-GGUF` (215), `fr0stbit3/laya-gguf` (187) — **GGUF only**. ONNX family incl. **onnxruntime-web / WebGPU** (`mizchi`, `Mattepiu`, `sevenreasons` fp16, `tozp`). CoreML + ANE + MLX (`aac6fef`). LiteRT/TFLite Android (`litert-community`). FP8 (`Weidows`). AXERA ax650 NPU. Vision fork: `thaitea/laya-vision-smolvlm-256m`. Browser agent: `ShaunSpark/laya-mind2web-browser-agent`. | doc-verified (`f212431da` §12 "Ports already available") — adoption caveat in the doc: *"the parent repos report 0 downloads against 1,450 likes, while the GGUF ports report hundreds to 1.3K. Attention is real; measured pull-through is concentrated in the ports."* No GGUF `q4_k_m` / `q5_k_m` / `q8_0` naming visible from the doc — the doc names repos and download counts, not per-quant filenames. Per-quant filenames are **`unverified`** at this round. |
| **Chat-template requirements** | **There is no chat template.** The model's request shape is the TypeSafe System One shape: a `state` string plus a map of `choice` / `score` / `noul` questions each carrying `criteria`. *"Every question in a call is answered in one forward pass. Options are scored at their own `[MASK]` token and softmaxed within the question, so the answer space is defined at request time and new schemas need no retraining."* This is a **non-generative** decision API — the routing described in the architecture doc is **`pip install laya`**, not a chat-completion endpoint. The doc names the installation idiom (`pip install laya`) and the `Router(max_loaded=…)` / `Router(preload=True)` knobs, **not** a chat-template name. | doc-verified (`f212431da` §12). Treat this as a **decisions API** harness, not a chat-completion harness. The `hf-agent` design must accept the `{state, questions:{choice|score|noul:…}}` shape; the `hf-researcher-agent` may additionally use HF Hub search / paper-fetch surfaces per SC-4. |
| **Verdict** | **`local-viable`** | Synthesis from doc-verified inputs. 322M multilingual at 32.8ms p50 local on T4 vs third-party-measured 236–276ms p50 hosted Jev; 1024 ctx (up to 8k multilingual) re-opens Tier 1–2 use-cases; the request shape matches TypeSafe exactly. |
| **Verified vs unverified — row summary** | doc-verified: HF repo path, license, params, request shape, port ecosystem, latency figures, Khmer-script defect warning (`0.000 accuracy at 0.952 confidence` on the English checkpoint — *"confidence gating cannot save you"*). **unverified**: every per-cell fact about Laya that the doc does not assert (per-quant filenames, exact tokenizer files, actual hardware p50 on SPARK GB10 Blackwell, Ollama API logprob availability for the SemIf alternative). fleet-verified: none. | — |
| **Defect to record** | The Khmer defect (§12 warning) and the `Router(max_loaded=1)` rebuild cost (**7.4 s CPU, 10.3 s T4** per language switch) are documented load-bearing warnings. The architecture doc argues for a *deterministic script guard in code, in front of the model* as the right posture. The `hf-agent` / `hf-researcher-agent` harnesses must wire that guard before the forward pass, not rely on confidence gating. | doc-verified (`f212431da` §12) |

---

## 5. Row 2 — Needle 3 (`Cactus-Compute/needle3`)

> *"`Cactus-Compute/needle3` — Apache-2.0, 121M params, CQ2-bit (2.125 bits/weight), a single 35 MB `needle3.cact` file … Not present in any local store on Knuckles as of 2026-09-20."* — `git show 5c191efa1:pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md` §10

| column | value | disclosure |
|---|---|---|
| **HF repo path** | `Cactus-Compute/needle3` — single canonical repo. The doc warns: *"Four mirrors exist on the Hub with identical tags and 0–157 downloads; do not pull those."* | doc-verified (`5c191efa1` §10) |
| **License** | Apache-2.0 (single-license) | doc-verified (`5c191efa1` §10) |
| **Parameter count** | **121M active params**. CQ2-bit quantization at **2.125 bits/weight**. The single artifact is `needle3.cact` (~35 MB); the engine is **sub-1 MB** per platform (`linux-x86_64`, `wasm`, `wasm-component`, arm64, `linux-mipsel`). | doc-verified (`5c191efa1` §10) — no other quant formats (no GGUF, no ONNX) mentioned in the doc. Per-format quants are **`unverified`** — CQ2 is the only format documented. |
| **Available quants** | **CQ2-bit (2.125 bpw)** only per the doc. No safetensors or GGUF variant named. | doc-verified (`5c191efa1` §10). Per-arch engines: `linux-x86_64`, `wasm`, `wasm-component`, arm64, `linux-mipsel` (sub-1 MB each). |
| **Chat-template requirements** | **No chat template.** The model exposes a **`needle_init` / `needle_embed` / decode-grammar API** with byte-level grammar compiled from author-defined schemas. *"Context is shared between tool schemas, system prompt and conversation — `needle_init` fails when the static prefix does not fit."* Per the doc, the harness uses byte-level grammar-constrained decoding, not a `chatml` / `llama-3` template. Routing is **`act / confirm / refuse`** based on a learned confidence head: *"Leveraging Needle's confidence"* — vendor guide. | doc-verified (`5c191efa1` §10). Treat as a **typed-extraction + tool-call** harness, not a chat-completion harness. |
| **Verdict** | **`defer`** for SPARK-hosted inference in this round. The doc is explicit about three properties that block direct substitution for TypeSafe System One: *(a)* no documented per-option probability distribution (TypeSafe exposes one; Needle documents a single calibrated confidence per response); *(b)* no documented ordered-level Score with between-level positioning (TypeSafe Score returns between-level positions on a 2–10 rung ladder; Needle reaches classification through enum extraction, which is categorical); *(c)* published benchmarks measure tool-call exact-match and extraction micro-F1, not calibration. *"The confidence head is claimed calibrated; the benchmark chart does not measure calibration. That is the property this whole analysis depends on, so it must be measured locally before trust."* The §10 doc recommends evaluating **both** Jev and Needle 3 through the **same shadow harness** (§6) — that recommendation, **not** an unconditional `local-viable` verdict, is the doc's position. | Synthesis from doc-verified inputs. SC-2 may probe it on the bounded cipher / CHIT / NATS set and re-classify to `local-viable` if the calibration claim holds on PMOVES traffic; otherwise it stays `defer`. |
| **Verified vs unverified — row summary** | doc-verified: HF repo path, license, params, footprint, engine matrix, request shape, mirror warning, calibration-untested caveat. **unverified**: calibration figure on PMOVES traffic (this is exactly the measurement SC-2 would run); per-architecture binary hashes; SPARK ARM64 binary availability for the engine (`linux-x86_64` is named; SPARK is ARM64, the engine list does include `arm64`, but exact glibc / musl fit is `unverified`); existing Ollama / HF cache presence on SPARK (`unverified` — the doc only asserts "Not present in any local store on Knuckles as of 2026-09-20", and SPARK ≠ Knuckles). | — |
| **Defect to record** | Context budget: schemas + system prompt + conversation share the same context window; `needle_init` fails when the static prefix does not fit. The `hf-agent` harness must size schema + system prompt + expected conversation headroom **before** init. | doc-verified (`5c191efa1` §10) |

---

## 6. Row 3 — OpenJEV (`com-kotobalabs/open-jev-deberta-v3-large`)

> *"An open ecosystem reproducing Jev's shape appeared on the Hub 17–21 Sep … Correction 1: T1.4 … is the WORST fit against open-jev-deberta … Correction 2: open-jev-deberta caps state at 256 tokens."* — `git show eedd32913:pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md` §11

The task spec treats OpenJEV as having **no fleet-side trace**. The architecture doc disagrees — §11 carries a substantial entry with measured figures and a lineage paragraph. Per the disclosure policy, that is **doc-verified evidence, not a fleet measurement**, and is recorded accordingly.

| column | value | disclosure |
|---|---|---|
| **HF repo path** | `com-kotobalabs/open-jev-deberta-v3-large` — single repo. The doc also names siblings created in the same window but **not** evaluated here: `vagmi/jev-lite` (gemma-4 QLoRA, tagged `typesafe`, `calibration`), `chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-{GGUF,MLX}`, `argos1111/modernbert-ja-310m-jev` (Japanese). The doc warns: *"All created within the last four days; none evaluated here."* | doc-verified (`eedd32913` §11) — note the task spec framing of "no fleet-side trace" applies to *fleet measurements*; the doc entry is the source-of-options evidence. |
| **License** | Apache-2.0 (single-license) | doc-verified (`eedd32913` §11 table) |
| **Parameter count** | Backbone is **`deberta-v3-large`** (the doc states this in the table row "deberta-v3-large"). The OpenJEV card itself is **`unverified`** from this fleet; DeBERTa-v3-large is ~**435M** params on the public backbone card. The doc does **not** name a parameter count for the OpenJEV release directly, only that it is a DeBERTa-v3-large encoder. | doc-verified for the backbone (`eedd32913` §11 table); `card-verified` for the 435M figure is **`unverified`** at this round (DeBERTa-v3-large is the publicly known size, but the OpenJEV fork may add LoRA / projection layers — that delta is unverified). |
| **Available quants** | The doc lists the release as a single **DeBERTa-v3-large** encoder. No GGUF / ONNX / quantized variants are named in §11. | doc-verified (`eedd32913` §11) — *"no GGUF / ONNX named"* is the entire disclosure. Any alternative quantization is **`unverified`**. |
| **Chat-template requirements** | **No chat template.** The model is a **purpose-trained encoder for typed probabilistic decisions**, not a chat-completion decoder. Per the doc, primitives are **Choice (≤255 options) / Score (2–10 ordered) / Noul** — *"the exact TypeSafe set"*. The harness must accept the {state, questions} shape; the doc notes the lineage that *"SemIf-style decisions need no new model at all"* (read option-letter logits straight out of a frozen open model, softmax over just the option-letter tokens). | doc-verified (`eedd32913` §11) |
| **Verdict** | **`defer`** for any cross-tier substitution. The doc is unambiguous: *"the hosted-vs-local choice is therefore not a swap of one provider for another. It changes which integration points are viable at all."* Specifically: *(a)* 256-token state cap **excludes** T1.1 (provenance-gate content bodies), T2.3 (Hi-RAG chunks), T1.3 (DeepResearch sources) — all exceed 256 tokens; *(b)* "score on unseen level sets is this model's measured weakest axis: 0.45 against a 0.26 majority baseline" — which is exactly what T1.4 (prosodic boundary detection on a new SENTENCE/CLAUSE/PHRASE/BREATH/NONE ladder) needs. The doc does identify one pilot that holds: **T1.2 (channel-monitor)** — *"A video title sits comfortably inside 256 tokens; the judgment is a Noul; and the model's best measured OOD axis is negated noul at 0.83."* | Synthesis from doc-verified inputs. **`defer`** is the recommended posture: do not block a probe on this candidate, but do not treat it as a general substitute. SC-2 may probe T1.2 alone and re-classify narrowly. |
| **Verified vs unverified — row summary** | doc-verified: HF repo path, license, backbone, primitives, 256-token state cap, in-domain / OOD accuracy / Brier / ECE figures, lineage paragraph, mirror-warning siblings, pilot-survival claim for T1.2. **unverified**: OpenJEV card-level parameter count (DeBERTa-v3-large is the doc's named backbone; the exact OpenJEV card may add layers not in the doc), any quantization variant, SPARK-side pull and load time, hardware p50 on SPARK GB10 Blackwell, the model card's own measured figures on PMOVES traffic. fleet-verified: none. | — |
| **Defect to record** | Three seeds measured: in-domain **0.847 ± 0.005**, OOD **0.678 ± 0.012**. The authors' own framing: *"it reads the question only partly."* Confidence is **over-confident by ~0.03 on OOD and must be re-calibrated on your data**. This is the same defect family as Laya's Khmer collapse and Bonsai's spider answer (cited in §12 and §0) — calibrated in-distribution ≠ correct out-of-distribution. | doc-verified (`eedd32913` §11) |

---

## 7. Verdict × downstream SC matrix

| Candidate | Verdict | SC-2 probe (cipher / CHIT / NATS) | SC-3 `hf-agent` | SC-4 `hf-researcher-agent` | SC-5 manifest draft |
|---|---|---|---|---|---|
| Laya | `local-viable` | **yes — bounded, 3 probes** per the SC-2 spec | primary backend | primary backend | draft `pmoves/registry-manifests/hf-laya.agent.yaml` after SC-2 settles |
| Needle 3 | `defer` | **yes — bounded, 3 probes**, conditional on the calibration claim holding | shadow / fallback | optional | **no manifest this round** (the doc recommends the §6 shadow harness, not unconditional integration) |
| OpenJEV | `defer` (T1.2 only) | **no probe at SC-2 round** — the bounded probe set (cipher / CHIT / NATS round-trip) does not exercise the 256-token decision API in a way that would yield a PMOVES-relevant signal beyond the doc's own measurement | **not wired this round** | **not wired this round** | **no manifest this round** |

This matrix is **doc-grounded**, not fleet-grounded. SC-2's job is to upgrade the second and third rows from `defer` to `local-viable` or to confirm them as `decline`. Nothing in this inventory binds that outcome.

---

## 8. What this inventory did **not** do

- Did **not** fetch any model card from the HF Hub. Doc-verified cells come from the architecture-doc commits; per-cell facts the doc does not assert are `unverified`, not interpolated.
- Did **not** probe any of the three models on SPARK. SC-2 owns that work.
- Did **not** change `cli_tools.yaml`, `acp_registry_map.json`, `pmoves/config/agent_registry.yaml`, or any harness / registry file. SC-3 / SC-4 / SC-5 own those.
- Did **not** open a registry PR. SC-5's acceptance criterion explicitly gates that on operator confirmation.
- Did **not** commit to a per-quant naming for any of the three. The doc names checkpoints and ports; per-quant filenames are recorded as `unverified` rather than guessed.

---

## 9. Source-of-evidence cross-reference

| Claim class | Source |
|---|---|
| Laya HF path, license, params, request shape, ports, latency, defect warnings | `f212431da` — `pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md` §12 (reachable via `git show f212431da:pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md`) |
| Needle 3 HF path, license, params, footprint, calibration caveat, mirror warning | `5c191efa1` — same file §10 (reachable via `git show 5c191efa1:pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md`) |
| OpenJEV HF path, license, backbone, primitives, 256-token cap, measured figures, pilot-survival claim | `eedd32913` — same file §11 (reachable via `git show eedd32913:pmoves/docs/architecture/TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md`) |
| Doc-writing pre-flight gate | `make -C pmoves submodule-integrity` exit 0 (recorded at top of file) |
| Goal / task / scope context | `.spynel/goals/planning/g-20260922T142400Z-d1e2f3a4b5c6d7e8.md`, `.spynel/tasks/working/t-20260922T202933Z-7e2b9f4a1c8d.md` |
| Operating surface declaration | `.spynel/instructions/agent-developer.md` (default operating surface: OpenRoom) |

The three architecture-doc commits live on branch `origin/docs/typesafe-system-one-integration-scan`, not on the local `feat/comfyui-ui-to-api` tip. The local working copy does **not** carry `TYPESAFE_SYSTEM_ONE_INTEGRATION_SCAN.md`. All doc-verified quotes above were extracted from `git show <commit>:<path>` so the row text is reproducible without the file being on the working branch.
