# Zeta Method Design Gate

Status: design required before implementation

The current PMOVES zeta filters are engineering heuristics that use known
Riemann zeta zero values as deterministic, nonuniform weights. They are not a
proof-backed spectral model and must not be described as one.

## Acceptance Criteria

- Define the mathematical object being filtered, including domain, sampling
  rate, normalization, and expected invariants.
- State why zeta zeros are the correct basis instead of a generic harmonic,
  wavelet, graph spectral, or learned basis.
- Provide a reproducible benchmark where the zeta method beats at least two
  simpler baselines on PMOVES data.
- Include falsification tests that show when the method should not be used.
- Preserve CHIT provenance: input packet hash, filter config, output hash,
  agent identity, and signed trail reference.

Until those criteria are met, zeta-labeled code should use "heuristic" in
module comments, docs, and exported API text.
