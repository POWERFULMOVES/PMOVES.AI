# TypeSafe System One — PMOVES Integration Scan

**Status:** analysis + recommendation, no code changes
**Node:** B850-CLAUDE (Knuckles) · **Lane:** `docs/typesafe-system-one-integration-scan`
**Date:** 2026-09-20/21 · **Base:** `origin/main` @ `256b60962`

---

## 0. Verdict

TypeSafe is worth integrating in PMOVES, but **not for the reason it usually gets pitched.**

The value here is not "add AI to more places." This repo already has plenty of
inference. The value is that PMOVES is riddled with a specific, recurring defect
shape, and System One is a direct structural answer to it:

> **Uncalibrated numeric proxies standing in for semantic judgments, compared
> against hand-tuned constants, failing silently.**

Every scope surveyed produced the same shape. A float that looks like a
measurement is actually an opinion; it is compared to a magic number nobody has
re-validated; and when it is wrong, nothing errors, nothing logs, and nothing is
disclosed outward. That is the same family as this fleet's documented history of
healthchecks that cannot observe failure, checks that cannot pass, and silent
handlers in paths that report outward.

System One's contribution is **the confidence axis**. Today a good threshold and
a bad threshold are indistinguishable downstream. A calibrated probability plus a
confidence score makes "the system is unsure here" a *routable value* instead of
an invisible coin-flip.

**Recommended first move:** one pilot, on the ingest path, where latency is free
and the current failure is invisible. See §6.

---

## 1. Premise correction — this is greenfield

The working assumption entering this scan was that Agent Zero already carried
TypeSafe as a plugin. Measured, it does not:

| Check | Result |
|---|---|
| `TYPESAFE` across repo | 0 hits |
| `\bjev\b` across code/docs/config | 0 hits |
| A0 `plugins/` | 33 plugins, none TypeSafe |
| `system_one` in A0 tree | 0 hits |
| Corpus validity | 6,552 tracked files; **71/80 submodules populated**; 2,803 files in A0 alone |

The corpus row is load-bearing. An empty grep in this repo routinely means an
unpopulated submodule rather than a real absence, so the corpus was sized before
the zero was trusted. It is a real absence.

What exists is the **Claude Code skill** (`typesafe@typesafe-ai` 0.5.7, installed
2026-09-20). The vendor docs advertise an "Agent skill: drop-in for Claude Code,
Codex, and other agent environments" — that is almost certainly the source of the
recollection. **No runtime integration exists anywhere in PMOVES.**

---

## 2. The contract, pinned from live docs

`POST https://api.typesafe.ai/v1/systemone` · `Authorization: Bearer <key>`

| Primitive | Question | Returns | Limits |
|---|---|---|---|
| **Choice** | which one of N? | pick + `probabilities` + `confidence` | ≤255 options |
| **Noul** | is this true? | probability 0..1 | optional `criteria.true/false` |
| **Score** | which level? | position (may fall *between* levels) + `probabilities` + `confidence` | 2–10 **ordered** levels |

Request: `state` (string \| object \| array) + `model` + `questions` (map of id → question).
Response: `answers[id]` carrying the typed value, `probabilities`, `confidence`, `legend`; plus `usage`.

**Batching economics (measured by vendor):** 13 questions over a ~54k-char
document — **12.2× cheaper, 10.0× faster** batched vs. separate. The reason is
structural: the *state* dominates every request, so sending it once instead of
thirteen times is where the saving lives. Answers are scored independently and
cannot see each other, so batching does not change them (σ=0.0 across 5 runs for
most questions).

**Confidence semantics.** Confidence is distribution *concentration*, not
correctness, and not workflow validity. Vendor guidance: >0.9 automate, <0.5
route to a human, thresholds scaled to consequence. A **Noul near 0.5 means "yes
and no are equally likely," NOT "medium intensity."** Misreading that is the
single most expensive available mistake when wiring one of these into a gate.

Errors: 401 / 422 / 429 / 529, with exponential backoff required on 429 and 529.

---

## 3. Ranked integration points

Scouts swept five scopes. Rankings below are cross-scope, merged and re-ranked
by (consequence × brittleness × isolation of the change).

### Tier 1 — do these first (ingest path: latency free, failure currently silent)

**T1.1 — Content provenance gate** · `pmoves/services/content-provenance-gate/main.py:483-539`
Three magic thresholds decide whether content enters Hi-RAG at all:
`noise_score > 0.58`, `semantic_density < 0.18`, `len(anchor_terms) < 2`. The
scores feeding them are hand-tuned linear combinations of token-repetition ratio,
punctuation ratio and short-token ratio — **no semantics whatsoever.** The module
docstring concedes it is "intentionally heuristic and lightweight."
→ **Score** over an ordered quality ladder (reject / marginal / accept); a
scorecard with three ordinal reasons already exists to map onto.
*Consequence:* false-rejects silently starve the knowledge base — and the
ratio-based formula structurally punishes terse-but-dense and non-English text.
False-accepts put junk into the KB other agents trust. **HIGH.**

**T1.2 — Channel monitor ingest filter** · `pmoves/services/channel-monitor/.../monitor.py:987-1007`
`kw in title.lower()` decides whether a discovered video is ingested at all.
→ **Noul** ("is this video relevant to the configured topic"), thresholded.
*Consequence:* keyword `"AI"` misses `"machine learning"`. The video simply never
appears; no error is raised. This is an invisible-failure ingest gate and the
change is small and isolated. **HIGH.**

**T1.3 — DeepResearch source ranking** · `pmoves/services/deepresearch/parser.py:50-71,110`
Sources are ranked by a relevance score **the LLM wrote about its own output**,
then `float(score) if score is not None else 0.0` — a missing score and a
fabricated source are treated identically and sorted last without being flagged.
→ **Score** each returned source against the research question, batched in one
request.
*Consequence:* research summaries cite weak or fabricated sources as
most-relevant. This is the canonical prompt-and-parse anti-pattern. **HIGH.**

### Tier 2 — high value, larger blast radius (stage behind a flag + shadow-compare)

**T2.1 — Persona publish gate** · `pmoves/services/consciousness-service/cgp_mapper.py:196-254`
`score = 0.5; score += min(keyword_count * 0.03, 0.15)` against fixed keyword
lists, plus `len(description) > 100/200` bumps, on three axes. Feeds
`persona_gate.py:39-45` thresholds that gate `persona.publish.request.v1` —
i.e. **whether a persona goes live.**
→ three **Score** calls (one batched request) judging the description against
ordered rigor levels.
*Consequence:* a well-written description using synonyms of the magic keywords
scores 0.5 forever. Keyword-counting is deciding what ships. **HIGH.**

**T2.2 — Cipher relevance cutoffs** · `Pmoves-cipher/.../swarm-merger.ts:87-98` and `.../search-precision.ts:22-34,109-121,157-190`
`rrfScore >= minRRFScore` then `>= topRRF * rrfGapRatio`; plus
`SCORE_FLOOR=0.3`, `GAP_RATIO=0.75`, `POST_EXPANSION_GAP_RATIO=0.6`. **These
constants are duplicated and already drifting** — the same codebase carries
"ByteRover's 0.45/0.7" at `search-knowledge-service.ts:1234-1242`.
→ **Noul** ("is this result relevant to the query") replacing the RRF-score proxy,
or **Score** for graded keep/maybe/drop.
*Consequence:* silently drops correct answers from federated memory search, or
admits noise. RRF's `K=60` is generic IR tuning, not query-aware. **HIGH**, but
it is on the interactive path — see the latency note in §5.

**T2.3 — Hi-RAG rerank fusion** · `pmoves/services/hi-rag-gateway-v2/routes/query.py:145-148` (mirrored in v1 `gateway.py:338-339,682`)
`0.5 * vector + 0.5 * rerank`, fixed, query-invariant, env-toggled between two
hardcoded formulas. Related: `ALPHA=0.7` and `GRAPH_BOOST=0.15`.
→ **Choice** per query among vector-favored / balanced / rerank-favored, so the
weighting adapts to query type (exact-lookup vs. semantic).
*Consequence:* mis-ranks chunks for **every** Hi-RAG query system-wide. High
value, but correspondingly high blast radius — stage it last in this tier. **HIGH.**

**T2.4 — Gemini evaluator prompt-and-parse** · `pmoves/services/tokenism-simulator/services/gemini_evaluator.py:56-81`
Free-text prompt asks for JSON floats; `json.loads` with a bare
`except json.JSONDecodeError` → **silent fallback `{"alpha_i":1.0,"halfLife":1.0}`**,
and no range/type validation on the happy path either. Published to
`tokenism.swarm.population.v1` — the live economic-simulation population.
→ **Score** on the defined ranges, with confidence to route on.
*Consequence:* a parse failure is indistinguishable from a real evaluation.
**HIGH** — and see §4, because the silent handler is a defect in its own right.

**T2.5 — EvoSwarm fitness heuristics** · `pmoves/services/evoswarm/persona_optimizer.py:740-798`
Already the composite-scoring shape the vendor recommends (code-owned weights
0.25/0.25/0.35/0.15) — but two of four atomic terms are magic-number distance
heuristics: `max(0, 1-abs(temp-0.7))` ("moderate temperature preferred") and a
boost-midpoint penalty, neither informed by what the persona is *for*. Only
`pass_rate` is legitimately deterministic and should stay.
→ **Score** for "is this setting well-suited to this persona's role and eval
history"; **code keeps the combination weights.**
*Consequence:* steers where every persona's evolutionary search converges.
**HIGH.**

### Tier 3 — real fits, low consequence (do only if convenient)

| Site | Mechanism | Note |
|---|---|---|
| `pmoves/tools/docs_reconcile.py:428-437` | `age_days > freshness_days` as a proxy for content drift | Gates CI P1 across ~40 docs, but only works as a fit **if paired with "what changed" context** — a bare day-count swap is not an improvement |
| `integration-coordinator.ts:205-219` | `variance>0.3 FAIL / >0.2 REVIEW` | Advisory report only |
| `calibration-engine.ts:44-49` | `<=10 high / <=25 medium` | Recommendation text only |
| `hi-rag-gateway-v2/.../neo4j.py` + `query.py:82-83` | substring containment for graph-entity boost (`+0.15`) | Entity `"AI"` matches nearly anything |
| `search-knowledge-service.ts:108-129` | fixed 0.55 geometric decay for parent propagation | Shapes agent context |
| `pmoves/tools/chit_verify.py:200` | `SequenceMatcher(...).ratio()` for CGP↔corpus fidelity | **Gates nothing today** — flagged so it is not later built into another magic-threshold gate |
| `query.py:80` | `fuzz.token_set_ratio` lexical fallback | Fallback path only |
| `projection-validator.ts:393-435` | ±15/±10 hand-weighted ranking | Trades one hand-tuned scheme for another; SPECULATIVE |

---

## 4. HARD NO — must stay deterministic

This section matters more than §3. A probabilistic model must never gate a
payment, validate a signature, or count a vote.

**Cryptographic / money path**
- `PMOVES-ToKenism-Multi/integrations/contracts/tally-signer-ed25519.ts` — real Ed25519 k-of-n multisig, distinct-key threshold at `:247-251`. Correct. Do not touch.
- `.../contracts/mode-a-tally.ts:44-90` — secret-ballot tally arithmetic (quorum/turnout/pass-share). Exact by requirement.
- `.../contracts/equalweight-governor-model.ts`, `coopgovernor-model.ts` — quorum/threshold governance math.
- `pmoves/tools/chit_security.py` `verify_cgp` / `verify_cgp_detailed` — HMAC verification.
- `pmoves/tools/sign_trail.py` — identity resolution, schema validation, HMAC signing, NATS publish. No judgment points anywhere in it.
- `pmoves/services/evo-controller/app.py:239-285` `_filter_verified_cgps()` — CHIT signature gate, fail-closed.

**Authorization / security gates**
- `pmoves/tools/chit_security_validator.py:186-210` — TRUSTED_SOURCES allowlist selecting SIGNED vs STRICT tier. Looks like a lookup-table fit; it is access control. Keep the deterministic allowlist.
- `.claude/hooks/damage-control/known_roads.py` — all five domain predicates. Path-segment gate over which files may be edited; the design depends on being exact and auditable.
- `.claude/hooks/governance/claim-collision-pre.py` — the regex parsers. **The flagship keep-deterministic example.** The format is self-authored by `register_append.py`, not free text, and every regex carries an in-file postmortem of a real collision bug it fixed. Replacing any of it reintroduces precisely the silent-collision class those comments record fixing.
- `pmoves/services/tokenism-simulator` approval-gate flags — operator approval is a human decision, never inferred.

**Already correct by design**
- `pmoves/tools/chit_manifest_merge.py` `resolve()` — refuses to auto-resolve true collisions and punts to a human. A judgment call here would *remove* the human checkpoint.
- `pmoves/tools/chit/chit_decoder.py` `geometry_only_decode` — FAISS cosine NN. Converting a principled vector method to a categorical guess is a downgrade.
- `pmoves/services/creator-operator/router.py` — capacity/VRAM/caps-subset constraint match. Exact registry lookup, not semantics.
- `comfy-watcher` extension allowlist + content-hash dedup; `extract-worker` chunk IDs; `channel-monitor` dedup by ID; ASR segment boundaries (model output, not code judgment); Qdrant/embedding calls and RRF's rank math itself; all env-var validation.
- `Pmoves-pretext` — pure canvas text-layout/measurement, arithmetic only. No semantic decisions exist to convert.

---

## 5. Cost, latency and the shape of a correct call

**Batch per state, not per item.** For reranking, put the whole candidate list in
one structured `state` and ask one **Score** per candidate (question id =
candidate id). One request. That is exactly the 12.2× economics — and it is the
opposite of the obvious loop-and-call implementation.

**Watch the ceilings:** Choice ≤255 options, Score 2–10 ordered levels. A
candidate set larger than the question-map comfortably holds must be shortlisted
in code first (the vendor's own pattern: code retrieves, the model selects).

**Latency is the real constraint, and it sorts the roadmap.** ~100ms per request
plus network is free on ingest and expensive on the interactive retrieval path.
Cipher search (T2.2) and Hi-RAG query (T2.3) sit in front of a waiting agent;
content-provenance-gate (T1.1) and channel-monitor (T1.2) do not. **Start where
latency is free.**

**Score levels must describe concrete situations and stand on their own** — the
rubric is the contract, and a level like "medium quality" is not a rubric.

**Keep policy in code.** Judge atomically, combine deterministically. Weights,
thresholds and display filters change without rerunning inference. This is also
what keeps the raw judgments reusable and the decision auditable.

---

## 6. Recommended first move — one pilot

**T1.2, channel-monitor `_apply_filters()`.** It is the best pilot on every axis
that matters: smallest diff, fully isolated, zero latency pressure, an invisible
failure mode today, and an outcome that is trivially shadow-testable.

Run it in **shadow mode first**: keep the substring filter authoritative, call
System One alongside, log both verdicts plus confidence, and change nothing.
After a week of real channel traffic you will have a labeled disagreement set —
which is what you need to pick a threshold *on your own data*, exactly as the
vendor guidance insists, rather than adopting a demo constant.

That shadow harness is also the reusable asset. Every other candidate in §3 wants
the same rig: dual-path, log both, compare later. **Build it once, on a Known
Road, and hand it to the fleet** — briefs are a channel to one agent; a Known
Road is a channel to everyone.

**Prerequisite:** `TYPESAFE_API_KEY` through the secrets funnel. Validate the
credential *shape* at delivery, not just its presence — a truncated key has
burned this fleet before.

---

## 7. Findings that are NOT about TypeSafe

Surfaced during the sweep. These stand on their own and should be filed
regardless of whether any TypeSafe work proceeds.

1. **`settlement-executor.ts:392-394` `isSigned()` is still a truthiness check.**
   `Boolean(signature?.alg && signature.kid && signature.hmac)` — not a MAC
   verification — gating **LIVE Firefly execution** (`validateLiveExecutionGate`
   `:314-364`) and operator-approval scope/expiry. The same shape persists at
   `settlement-deployment-attestation.ts:60,128,156`. Confirmed present at
   `origin/main` today. A literal `hmac: 'abc123'` opens the gate.
2. **`gemini_evaluator.py:81` is a silent handler on an outward-reporting path.**
   A parse failure yields `{"alpha_i":1.0,"halfLife":1.0}` published to the live
   simulation population, indistinguishable from a real evaluation. The caller
   cannot see the degradation — the defining test for this defect class.
3. **EVO controller has no fitness logic.** `evo-controller/app.py:178-207`
   `_tick()` is an explicit placeholder ("Real fitness logic will replace this
   placeholder"). There is nothing there to improve yet — worth knowing before
   anyone plans work that assumes it exists.
4. **Cipher's relevance constants are duplicated and drifting:** `0.3/0.75/0.6`
   in `search-precision.ts` vs. "ByteRover's 0.45/0.7" in
   `search-knowledge-service.ts:1234-1242`. Two copies, one behaviour, already
   diverged.
5. **`agentgym-rl-coordinator/coordinator/training.py:228,237`** computes
   `mean_reward = 0.5 + (epoch/total)*0.3`, commented "Simulated improvement."
   Demo code; ensure nothing downstream treats it as a real signal.

---

## 8. Coverage and gaps

| Scope | Files read in depth / grepped | Outcome |
|---|---|---|
| Cipher · Hi-RAG v1+v2 · deepresearch · graph-linker | ~15 / ~40 | 8 judgment points |
| CHIT tooling · claim register · living-docs | several / ~30 | **2 fits, mostly non-fits** |
| ToKenism-Multi · EVO · consciousness | 157 `.ts`/`.py` + 41 service files | 6 points, large non-fit list |
| YT · creator · comfy · pretext · provenance | ~30 | 2 fits + 1 supporting |
| Flute-gateway · prosody/CGP/BPM · A2UI · hyperdim | **in flight** | **pending — §9 to follow** |

**Known gaps, stated rather than papered over:**
- `pmoves-yt/yt.py` re-exports from `pmoves_yt_service`, **not vendored in this
  repo**. Channel-relevance logic may also live there; unverified.
- `claim-collision-pre.py` — ~1,600 of 1,922 lines unread (the Bash
  write-detection heuristics for heredoc/tee/sed/find). Sampled, not exhausted.
  Another judgment point could plausibly hide in the write-detection classifiers,
  though the same keep-deterministic argument likely applies.
- `pmoves/services/comfyui/` is a Dockerfile and one example workflow — no
  service code exists to scan.

**The CHIT result is itself a finding.** A scope built out of signing, access
control and register parsing returned almost entirely non-fits. That is the
correct answer for that subsystem, and it is worth recording so nobody
re-litigates it: CHIT is where TypeSafe should *not* go.

---

## 9. Prosody / voice / render

*Pending — scout in flight at time of writing. This section will be appended.*
