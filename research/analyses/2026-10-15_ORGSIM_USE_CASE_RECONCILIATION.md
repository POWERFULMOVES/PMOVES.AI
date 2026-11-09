# ORGSIM Use-Case Reconciliation — Aragon (Peer) ↔ PMOVES.AI

**Date**: 2026-10-15 · **Lane**: ORGSIM ADOPTION (claimed 16:55Z) · **Framing**: Richard Aragon is a **peer** building in the same harness-over-model direction. We mirror the *pattern*, fork the *code* for customization, and do not treat his project as an upstream we serve. Floor-pins remain deliberate PMOVES policy — dependency lockfiles are **NOT** adopted (anti-pattern for our brand/vision).

## His stated use cases → PMOVES equivalents

| # | His stated purpose (from video DsMFuV-u-so) | PMOVES.AI equivalent | Status |
|---|---|---|---|
| 1 | **Train AI models without giving them data** — eliminate the labeled-data requirement by learning from the live system | `scripts/runbook_drift.py` learns our doc corpus's *actual* checkable claims by probing reality — zero labeled test data, zero LLM calls | **SHIPPED** (v3, PR #3375) |
| 2 | **Simulation clone + read-only oracle probing** — trial-and-error against a clone; real system only queried read-only | Auditor probes the repo via `make -n` dry-runs, file existence, GET-only curls — writes nothing, mutates nothing | **SHIPPED** (same tool) |
| 3 | **Sealed rulebooks** — tamper-evident, content-hashed, refuse out-of-scope answers | sha256 hash-chained JSON reports + CHIT sign-trail on every lane close | **SHIPPED** |
| 4 | **"Undecided" as first-class output** — every failure mode ends in I-don't-know, never a confident wrong | VERIFIED / DRIFTED / UNDECIDED fail-closed verdicts; unreachable = UNDECIDED, never asserted dead | **SHIPPED** |
| 5 | **Drift monitor** — quiz the rulebook periodically; discard and relearn on mismatch | `runbook-drift-weekly` scheduler task (6wLxB5cD): weekly run + CHIT-signed delta + notify-on-movement | **SHIPPED** |
| 6 | **Frozen-weight backbone LLMs optional** — core learner makes zero AI calls; LLM accelerates when attached | `--jev` flag (this PR): AgentJev-0.6B int8 ONNX classifies claim intent locally — import-guarded, UNDECIDED-fallback; core audit stays deterministic | **IN PR #3375** |
| 7 | **Sealed exam protocol** — draw exam before studying, lock during, open after answers | CI advisory `docs-drift-check.yml`: verdict snapshot per PR comment = the sealed exam record | **SHIPPED** |
| 8 | **Disposable-clone learning** — active probing only against throwaway environments | Not adopted: our repo *is* the sandbox (read-only probes); no clone infrastructure needed at docs-scale | **DELIBERATE DIVERGENCE** |
| 9 | **Effect model** — predict exact post-action state (stock, status) | Not adopted yet: candidate = predict CI outcome before push (needs commit-level effect model; future lane, not this PR) | **FUTURE LANE** |
| 10 | **Promotion gate** (≥99% accuracy, 0 false attempts, ≥95% coverage, 3 clean rounds) | Not adopted as hard gate: our CI is fail-soft advisory by design; CHIT closeout flow is the gate instead | **DELIBERATE DIVERGENCE** |

## What we deliberately did NOT steal

- **Dependency lockfiles**: floor-pins are deliberate PMOVES policy — portability across fleet nodes (SPARK GB10, Knuckles gfx1201, Jetsons ARM, 5090 Windows) beats reproducibility-freeze. His single-node venv discipline doesn't map to ours.
- **Client-side-only safety**: his permits are unsigned JSON; ours are CHIT HMAC-signed bundles. We keep our trust root.
- **Dolibarr-specific schemas**: the fork (POWERMOVES/orgsim-model-refiner) is for **reading his learner internals** (scorer discipline, sealed artifacts) not running his ERP probes. Customization targets our corpus, not his.

## Fork

`POWERFULMOVES/orgsim-model-refiner` forked from `MMVFIRM/orgsim-model-refiner` (upstream tracking via `fleet-fork-sync` playbook). Customization targets: swap his Dolibarr oracle for our reality-probe oracle; keep his sealed-artifact + promotion-gate patterns as reference implementations.

## Decision-model wiring (local Jev family)

- `research/models/agentjev/agentjev_0.6b_int8.onnx` (on-disk, tokenizer bundled)
- `onnxruntime 1.30.0` verified live
- Wiring: `--jev` flag on `runbook_drift.py` — optional trio-of-options classification (DRAFT/RUNBOOK/HISTORICAL) per claim, replacing filename-heuristic `doc_class()` when the model is present. Import-guarded: no onnxruntime → silent fallback to heuristics, audit stays zero-dependency.
- Sibling models (`layla/`, `needle3/`, `openjev/`, `open_jev_deberta` eval) inventoried in `research/models/MODEL_CANDIDATE_MATRIX_2026-10-12.md` — wiring follows same optional-flag pattern in future lanes.

**Live test (2026-10-15T17:00Z):** wiring works end-to-end — model loads (onnxruntime 1.30.0, CPU, 2 threads), runs, audit completes with identical counts (117 V / 80 U / 1 D). Classification itself returned UNDECIDED 198/198: AgentJev's trained prompt format differs from my raw-text input, so confidence never cleared the 0.5 fail-closed bar. The fail-closed design held (never guessed). Follow-up: match the eval prompt format from the 3/3 @ 129ms run, then re-baseline. Untuned model shipped DISABLED by default (--jev opt-in) — core audit unchanged.
