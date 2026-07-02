# Zeta Spectral Filtering Method Design

Status: method-design gate, not an accepted proof-backed implementation.

## Scope

This document defines the review gate for PMOVES zeta spectral filtering. The
current code is a bounded weighting heuristic over CGP spectrum arrays. It must
remain described as heuristic until this design is reviewed, implemented, and
validated with reproducible evidence.

Out of scope for this pass:

- claiming Riemann Hypothesis-backed behavior
- replacing CGP validation or CHIT signatures
- using zeta scores as settlement authority
- treating swarm fitness improvements as proof of zeta correctness

## Current Behavior

Existing zeta-related code applies deterministic weights derived from early
non-trivial zeta-zero ordinates to a finite CGP spectrum. The useful property is
operational, not mathematical proof: it produces stable, inspectable spectral
features that can be compared across runs.

The current behavior is acceptable only when labeled:

- experimental
- heuristic
- bounded to telemetry and ranking support
- subordinate to CHIT signature/provenance checks

## Proposed Method

The candidate zeta filter should be specified as a pure transform:

```text
filtered_spectrum = Z(input_spectrum, zero_table, decay, normalization)
```

Required properties:

- deterministic for identical inputs
- finite-input safe for empty, short, or malformed spectra
- output length matches input length unless an explicit projection is requested
- no output value is NaN or infinite
- normalization is documented and bounded
- zero-table provenance is recorded
- parameters are emitted in CGP metadata

Candidate parameters:

| Parameter | Purpose | Default Review Position |
| --- | --- | --- |
| `zero_table` | Ordered ordinates used for weighting | fixed checked-in table |
| `decay` | Weight attenuation by zero index | `1/log(gamma_n)` heuristic |
| `normalization` | Keep output comparable across spectrum sizes | L2 or max-abs |
| `window` | Optional finite window over long spectra | disabled until tested |

## Validation Plan

Acceptance requires evidence in four classes:

1. Determinism: identical spectra and parameters produce identical output.
2. Safety: malformed, empty, tiny, large, and adversarial spectra remain bounded.
3. Utility: downstream CGP ranking or decoder quality improves against a fixed
   benchmark without degrading baseline cases.
4. Provenance: emitted metadata records zeta parameters, table version, and
   whether filtering was applied or skipped.

Suggested fixtures:

- synthetic flat, impulse, ramp, noisy, and periodic spectra
- captured CGP spectra from text, image, audio, and mixed lanes
- regression cases where current heuristic previously changed ranking
- negative controls where filtering must not change a decision

## Decision Gate

The zeta lane can move from `Heuristic` to `Validated experimental` only after:

- this method is reviewed and updated with accepted parameter choices
- focused unit tests cover determinism and safety
- benchmark evidence is checked into `pmoves/docs/evidence/`
- docs stop using ambiguous "zeta proof" language
- CHIT implementation matrix is updated with the accepted status

Until then, production services must keep zeta behavior fail-soft and must not
use zeta output as a required security, settlement, or identity signal.

<!-- GRAPHITI_MARK: CODEX-GPT5::ZETA-METHOD-DESIGN-GATE::2026-06-05 -->
