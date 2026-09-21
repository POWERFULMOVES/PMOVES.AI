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

**T1.4 — Prosodic boundary detection** · `pmoves/services/flute-gateway/prosodic/boundary_detector.py:20-67`
Regex on trailing punctuation plus a 40-word `PHRASE_STARTERS` keyword set
classifies each word boundary into five ordered levels — SENTENCE(4) > CLAUSE(3)
> PHRASE(2) > BREATH(1) > NONE(0) — feeding `BPM_MAP` (60/90/120/80/150), which
drives the entire CGP v0.2 prosodic packet published to `tokenism.prosodic.bpm.v1`.
→ **Score.** This is the cleanest fit in the whole survey: the ordered ladder
already exists as the `BoundaryType` enum, and Score is explicitly permitted to
land *between* levels rather than snapping to one of five buckets.
*Batching note:* today this is a per-word loop. The correct shape is **one
request** — full utterance as `state`, one Score question per boundary. That is
simultaneously cheaper and better, because each judgment then sees full sentence
context instead of the trailing token plus next word, so sentence-opening
`"However,"` and mid-clause `"however"` stop collapsing into the same bucket.
*Consequence:* wrong pause length and BPM for the entire utterance — and CGP,
Hyperdim beat-sync and A2UI animation timing all read it as ground truth. **HIGH.**

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

**T2.6 — Breath insertion** · `pmoves/services/flute-gateway/prosodic/types.py:74-81` + `audio_processor.py:233,243`
`rng.random() < breath_prob` against a fixed per-boundary table
(SENTENCE=0.35, CLAUSE=0.15, BREATH=0.90, PHRASE/NONE=0.0) — a coin flip with
zero sensitivity to syllable run length, speaking rate or persona.
→ **Noul**, conditioned on the actual utterance rather than a table indexed only
by boundary type.
*Consequence:* over- or under-breathing reads as mechanical or asthmatic. Low
stakes per instance, but it runs on every synthesis call. **MEDIUM.**

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

### Tier 4 — missing entirely: documented but unimplemented

Two skills document judgment behaviour that **does not exist in code.** These are
not brittle mechanisms to replace; they are absent capabilities that a Choice or
Score call would genuinely deliver.

**T4.1 — `tts:express` "automatic engine selection based on intent."**
`.claude/commands/tts/express.md:22-27` is: parse `--intent` flag (default
`narrate`) → dict lookup against `pmoves/configs/tts-engine-expressions.yaml`.
No text→intent classifier exists anywhere in `flute-gateway` or
`cast-tts-gateway`. "Automatic" means only *the engine follows from the intent
you typed.* A **Choice** over the nine intents (narrate / emote / dramatic /
clone / multilingual / podcast / persona / agent / bpm_sync) inferred from
freeform text would make the documented behaviour true. The engine lookup itself
is a correct deterministic config lookup and should stay. **HIGH** — the sharpest
gap on this scope.

**T4.2 — `shift-from-bpm` text→BPM auto-detect.**
`SKILL.md` documents piping `analyze_beats --text "..." --output-json` into
`bpm_encoder`. `pmoves/tools/analyze_beats.py` is 823 lines of **audio-file**
fingerprinting and clustering (ffprobe / ffmpeg / librosa / CLAP → KMeans) with
three commands — `analyze`, `groups`, `status`. It accepts neither `--text` nor
`--output-json`, and operates on a folder of audio files, not a string. **The
documented pipeline does not exist.** The only real text→BPM path is the
deterministic `boundary_detector` → `BPM_MAP` chain in T1.4.

Note the family these belong to: they are the mirror image of a check that cannot
pass. A documented capability with nothing behind it does not fail loudly — it
reads as a working feature. Both should be fixed by either implementing the
judgment or correcting the doc, independent of any TypeSafe decision.

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
- `cast-tts-gateway/fallback.py` — multi-provider retry chain (Flute → Ultimate-TTS → …), try/except-and-advance. No classification.
- `a2ui-renderer` `src/index.ts`, `A2UIComposition.tsx` — `el.type` dispatch (`bar_chart`/`text`/`heading`/`glyph`/`geometry_mesh`) and format→codec branching are typed-schema switches over author-supplied CGP fields, not inference from freeform content. `pretextLayout.ts` is canvas font-metric math.
- `persona-bind` / `BEATS_VOICE` — explicit user-set env var → fixed persona preset table. Not inference.

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
6. **`tts:express` documents an inference step that does not exist.** The skill
   advertises "automatic engine selection based on intent"; the implementation is
   a flag parse and a dict lookup. See T4.1.
7. **`shift-from-bpm` documents a CLI surface that does not exist.** It pipes
   `analyze_beats --text ... --output-json`; that tool has no such flags and
   consumes audio files. See T4.2.

---

## 8. Coverage and gaps

| Scope | Files read in depth / grepped | Outcome |
|---|---|---|
| Cipher · Hi-RAG v1+v2 · deepresearch · graph-linker | ~15 / ~40 | 8 judgment points |
| CHIT tooling · claim register · living-docs | several / ~30 | **2 fits, mostly non-fits** |
| ToKenism-Multi · EVO · consciousness | 157 `.ts`/`.py` + 41 service files | 6 points, large non-fit list |
| YT · creator · comfy · pretext · provenance | ~30 | 2 fits + 1 supporting |
| Flute-gateway · prosody/CGP/BPM · A2UI · hyperdim | ~25 | 2 fits + 2 documented-but-missing |

**Known gaps, stated rather than papered over:**
- `pmoves-yt/yt.py` re-exports from `pmoves_yt_service`, **not vendored in this
  repo**. Channel-relevance logic may also live there; unverified.
- `claim-collision-pre.py` — ~1,600 of 1,922 lines unread (the Bash
  write-detection heuristics for heredoc/tee/sed/find). Sampled, not exhausted.
  Another judgment point could plausibly hide in the write-detection classifiers,
  though the same keep-deterministic argument likely applies.
- `pmoves/services/comfyui/` is a Dockerfile and one example workflow — no
  service code exists to scan.
- **Hyperdim is UNKNOWN, not absent.** `Pmoves-hyperdimensions/` is unpopulated
  locally (0 files), so `hyperdim:render/animate/export` have no inspectable
  implementation to judge. Recorded as unverifiable rather than as a non-fit —
  that distinction has cost this fleet real time before.
- `a2ui-nats-bridge/bridge.py` confirmed present but not inspected in detail;
  scout time went to the higher-signal prosody surface.

**The CHIT result is itself a finding.** A scope built out of signing, access
control and register parsing returned almost entirely non-fits. That is the
correct answer for that subsystem, and it is worth recording so nobody
re-litigates it: CHIT is where TypeSafe should *not* go.

---

## 9. Scope completion

All five scopes are complete; prosody findings are merged inline above rather
than isolated in an appendix (T1.4, T2.6, T4.1, T4.2, plus non-fits in §4 and
gaps in §8).

The prosody sweep contributed the one structural addition to this analysis:
**Tier 4.** The other four scopes found brittle mechanisms to replace. Prosody
found documented capabilities with no implementation behind them — a different
defect, needing a different fix, and invisible by exactly the same mechanism.

---

## 10. The local sibling: Needle 3

TypeSafe is a hosted API (`api.typesafe.ai`, bearer key, ~100ms + network). This
fleet's standing position is that **cloud plans orchestrate and local models are
worker siblings**, so the obvious question is whether a local model can hold the
same role. One can, and it is closer than expected.

**`Cactus-Compute/needle3`** — Apache-2.0, 121M params, CQ2-bit (2.125 bits/weight),
**a single 35 MB `needle3.cact` file**, with a sub-1 MB engine per platform
(`linux-x86_64`, `wasm`, `wasm-component`, arm64, even `linux-mipsel`). Not
present in any local store on Knuckles as of 2026-09-20.

### Why it is a real analog, not a superficial one

| TypeSafe System One | Needle 3 |
|---|---|
| Typed primitives, output constrained to author-defined options | Byte-level **decode grammar compiled from your schemas** constrains every token; output is guaranteed to parse |
| `confidence` from distribution shape | **"every response carries a calibrated confidence score from a learned head"** |
| >0.9 automate / <0.5 escalate to human | Vendor guide *"Leveraging Needle's confidence"* — routing on **act, confirm or refuse** |
| No-match outcome so the model need not force a pick | *"ask for something no tool covers and you get an empty list, not a guess"* |
| Choice over enumerated options | *"extraction generalises to classification"* via enums |
| — | Also returns **text embeddings** from the same model (`needle_embed`) |

### Where it fits better than the hosted API

- **T4.1 (`tts:express` intent selection)** is Needle's stated core competency
  almost verbatim: *"given the functions your app exposes, Needle picks the right
  ones and fills every argument from what the user said."* That is exactly
  intent-plus-parameters selection, and it removes the API-key and network
  dependency from the voice path entirely.
- **T1.4 (prosodic boundary detection)** is latency-sensitive and on the synthesis
  path. On-device inference from a 35 MB file beats a network round trip.
- **Retrieval (T2.2/T2.3)** sits in front of a waiting agent, where the hosted
  API's ~100ms + network is the binding constraint. Local changes that maths.

### Where it does NOT substitute — state this before anyone plans on it

- **No documented per-option probability distribution.** TypeSafe returns
  `probabilities` across every option and derives `confidence` from its shape.
  Needle documents a single calibrated confidence per response. For anything that
  consumes the *distribution* rather than the winner, these are not equivalent.
- **No documented ordered-level Score with between-level positioning.** TypeSafe
  Score explicitly lands between levels on a 2–10 rung ladder. Needle reaches
  classification through enum extraction, which is categorical. T1.4 specifically
  wanted the between-level behaviour — verify before assuming.
- **Published benchmarks are tool-calling exact-match and extraction micro-F1,
  not calibration.** The confidence head is claimed calibrated; the benchmark
  chart does not measure calibration. That is the property this whole analysis
  depends on, so it must be measured locally before trust.
- It **trades away general chat capacity** by design, and context is shared
  between tool schemas, system prompt and conversation — `needle_init` fails when
  the static prefix does not fit.

### Recommended posture

Evaluate both against the **same** shadow harness from §6. The harness is
model-agnostic by construction: dual-path, log both verdicts plus confidence,
compare later. Running hosted Jev and local Needle 3 through one rig on the same
traffic produces the only comparison that matters — **on PMOVES data, not on
either vendor's benchmark** — and it satisfies the no-hardcoded-models position
by making the choice a registry entry rather than an import.

Canonical repo is `Cactus-Compute/needle3`. Four mirrors exist on the Hub with
identical tags and 0–157 downloads; do not pull those.

---

## 11. The open-Jev landscape — and two corrections to §3

An open ecosystem reproducing Jev's *shape* appeared on the Hub between
17 and 21 Sep 2026. It is days old and small (0–920 downloads), but two entries
are documented well enough to plan against, and one of them changes conclusions
above.

### Lineage, as the community records it

1. **TypeSafe** shipped Jev and named the category — models returning typed
   probabilistic decisions instead of text.
2. **TheoLeeCJ** open-sourced the *mechanism* as **SemIf**, originally released
   as **OpenJev**: read option logits straight out of a **frozen** open model.
3. Others port that onto different bases (Bonsai low-bit, Qwen3.5, gemma, ModernBERT-ja).

Rung 2 is the one that matters most here: **SemIf-style decisions need no new
model at all.** Build a lettered multiple-choice prompt, run one forward pass,
softmax over just the option-letter tokens. That works against models this fleet
already holds locally — `qwen3-coder:30b`, `gemma-2-27b-it-GGUF`. *Open question,
not yet measured: whether Ollama's API exposes per-token logprobs. llama.cpp does.*

### The three local shapes

| | `com-kotobalabs/open-jev-deberta-v3-large` | `Cactus-Compute/needle3` | SemIf-style logprob reading |
|---|---|---|---|
| Mechanism | purpose-trained encoder, one forward pass | on-device tool-caller + extractor | prompt + softmax over option-letter tokens |
| Primitives | **Choice ≤255 / Score 2–10 ordered / Noul** — the exact TypeSafe set | tool-call, structured extraction, embedding | Choice-shaped only (≤26 options) |
| Distribution | **full, per question** | not documented | over option letters |
| Calibration | **measured** — see below | claimed, not benchmarked | none |
| Context | **512 total; state capped at 256 tokens** | schema + prompt + history share context | the base model's |
| Footprint | deberta-v3-large | **35 MB single file** | whatever you already run |
| Licence | Apache-2.0 | Apache-2.0 | MIT code |

### What open-jev-deberta actually measured

Public gold labels only — banking77, SST-5, BoolQ. 18,000 states / 42,000
questions, 1 epoch, one H100, ≈ $0.25.

| | accuracy | Brier | ECE |
|---|---|---|---|
| in-domain | 0.854 | 0.213 | **0.022** |
| banking77 intent (77 options) | 0.916 | | |
| **OOD** (new instructions, new option sets) | **0.690** | 0.399 | 0.035 |
| OOD — negated boolq noul | **0.83** | | |
| OOD — sst5 on **new level sets** | **0.45** (majority 0.26) | | |

Three seeds: in-domain 0.847 ± 0.005, OOD 0.678 ± 0.012. The authors state the
gap plainly — *"it reads the question only partly"* — and note confidence is
over-confident by ~0.03 on OOD and must be re-calibrated on your data.

### Correction 1 — T1.4 is the WORST local fit, not the best

Against the hosted API, prosodic boundary detection remains the cleanest Score
fit in this survey. Against **open-jev-deberta specifically, it is the worst
one**, because T1.4 requires a brand-new ordered level set (SENTENCE / CLAUSE /
PHRASE / BREATH / NONE) — and *score on unseen level sets is this model's
measured weakest axis*: **0.45 against a 0.26 majority baseline.**

The hosted-vs-local choice is therefore **not** a swap of one provider for
another. It changes which integration points are viable.

### Correction 2 — the 256-token state cap excludes most of Tier 1–2

TypeSafe was measured on a ~54,000-character document. open-jev-deberta caps
state at **256 tokens**. Hi-RAG chunks (T2.3), provenance-gate content bodies
(T1.1) and DeepResearch sources (T1.3) all exceed that. Those are hosted-API
candidates or SemIf-on-a-long-context-model candidates — not deberta candidates.

### What survives — and it is the pilot

**T1.2, channel-monitor, gets stronger.** A video title sits comfortably inside
256 tokens; the judgment is a Noul; and the model's *best measured OOD axis is
negated noul at 0.83.* The pilot choice in §6 holds under local substitution,
which is exactly what a pilot should do.

### The warning to carry into any of this

From the Bonsai port's own limitations, and it is the best single artifact in
this whole scan:

> `label_mass` is not confidence in correctness. It reports how much probability
> mass landed on the option letters, meaning you got *an* answer, not a right one.
> Bonsai 1 8B answers *"does a spider have two legs?"* with `true` at **0.998**
> confidence and `label_mass` **0.9997**.

That is precisely the defect family §0 describes — a number that looks like a
measurement and is an artifact — reappearing inside the proposed cure. If PMOVES
adopts SemIf-style logprob reading and treats `label_mass` as confidence, we
rebuild the same silent failure in a new place with a more respectable name.
**Distribution concentration over the options you supplied is not correctness.**

Scale is worth noting too: on WANLI-256 (chance 33.3%), Bonsai 1.7B scores 52.0%
and Bonsai 2 27B scores 74.6%. A 0.25 GB decision model is not a small version of
a good one.

### Also present, unread

`Meanblock/JEV-CPU` (Qwen3-0.6B, zero-shot), `mobarmg/jev-schema-scorer-deberta-v3-large`
(schema-conditioned candidate scoring), `ZefanCai/Open-Jev-9B` / `-2B` (Qwen3.5
LoRA, non-generative), `vagmi/jev-lite` (gemma-4 QLoRA, tagged `typesafe`,
`calibration`), `chaoliangUNSW/Jev-Style-Qwen3.5-2B-Decision-{GGUF,MLX}`,
`argos1111/modernbert-ja-310m-jev` (Japanese). All created within the last four
days; none evaluated here.
