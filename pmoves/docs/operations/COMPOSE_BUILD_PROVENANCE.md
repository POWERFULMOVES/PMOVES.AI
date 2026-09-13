# Compose Build Provenance — submodules over hand-rolled shims

**Status:** OPERATOR DOCTRINE (2026-09-12) — "ensure compose build from submodule docker image, not hand-rolled shims with no provenance."

## The rule

A compose service that compiles code must build from a **submodule** Dockerfile — a fork under `POWERFULMOVES/`, pinned by gitlink, covered by `submodule-gitlink-gate`, registered in `fork_registry.json`, and carrying CHIT trail provenance. A `build:` stanza with `context: .` + a Dockerfile in `pmoves/services/<name>/` is a **hand-rolled shim**: it lives only in the superproject, has no upstream, no fork lineage, no gitlink pin, and its provenance chain is exactly one rewrite away from silent drift.

## Measured state (2026-09-12, `docker-compose.yml`)

| class | count | examples |
|---|---|---|
| SUBMODULE build | 8 | archon (`../PMOVES-Archon`), openroom, pmoves-yt, transcribe-backend/frontend, nats-hub, tokenism-ui, llama-throughput-lab |
| IMAGE only (no build) | 38 | published/digest-pinned images |
| SUPERPROJECT shim | 52 | `context: .` + `pmoves/services/*/Dockerfile` |

The 52 are the violation class. Many are legitimate PMOVES-original glue (fleet-sentinel, presign, render-webhook) whose source tree genuinely is the superproject — the doctrine does not demand forks for first-party glue; it demands **registered exceptions**, so the set can only grow deliberately.

## Compliant shapes, in order of preference

1. `build: { context: ../PMOVES-<Name> }` — the fork's own Dockerfile. Gitlink-gated, fork-registry-declared, CHIT-tracked.
2. `image: <registry>/<tag>@sha256:...` — a published image with a digest pin, when the fleet does not need to build.
3. Superproject `build:` — ONLY for PMOVES-original glue whose source tree IS the superproject, and each such service must appear in the baseline of `compose-provenance-audit`.

## The ratchet

`make -C pmoves compose-provenance-audit` (tool: `pmoves/tools/compose_provenance_audit.py`) enumerates every `build:` in every compose file, classifies each stanza as SUBMODULE / IMAGE / SUPERPROJECT-SHIM, and **fails on any shim absent from the baseline** (`pmoves/configs/compose_provenance_baseline.json`). New shims must either be promoted to a fork submodule or added to the baseline with a PR-stated reason. Re-baseline deliberately: `make -C pmoves compose-provenance-baseline`.

## Promotion recipe (shim → fork)

The fleet-standard route for a shim that has outgrown the superproject:

1. Docs-first: a README in the fork repo stating purpose, tier, and the compose service it backs.
2. Fork the upstream (or create the first-party repo under `POWERFULMOVES/` if there is no upstream).
3. Move the Dockerfile + source into the fork; branch `PMOVES.AI-Edition-Hardened`.
4. Submodule into the superproject; register in `fork_registry.json` (upstream, sync decision, reason).
5. Repoint the compose `build.context` at `../<Fork>`; the gitlink gate takes over from there.

## Related doctrine — anchor constellations load from the harvest

When a service consumes algorithmic structure (anchor directions, spectra, constellations), the structure is **harvested from the docs constellation**, not hand-derived at call time.

Reference implementation: **Constellation-Harvest-Regularization** (`pmoves/docs/context/Constellation-Harvest-Regularization/`) — k-means++ anchor-direction initialization on cosine distance, entropy-minimizing anchor updates (softmax assignment → weighted-mean anchors → renormalize), soft-slab histograms, RPE (Range-Partition-Entropy) regularization. It converts corpora (.docx et al.) into structured units, embeds them, and derives the anchor constellation the data actually supports.

The anti-pattern, measured in the tree today: consciousness-service's `CGPMapper.theory_to_constellation()` synthesizes its spectrum from inline string heuristics (`_calculate_empirical_support(name, proponents, description)`, `_calculate_philosophical_coherence(...)`) — pseudo-metrics invented per call, with no harvest citation. An anchor with no harvest citation is the same defect class as a compose build with no fork lineage: plausible-looking structure with no provenance.

The compliant shape: anchors are produced by the CHR pipeline (or a port of it) into a **versioned harvest artifact** (e.g. `pmoves/config/constellations/<name>.harvest.json` — anchor matrix, entropy trajectories, provenance refs to the source corpus and algorithm commit), and consumers load that artifact. Re-harvesting is a deliberate, reviewable act; per-call invention is not.
