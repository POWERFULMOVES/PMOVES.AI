# Compose Build Provenance — submodules over hand-rolled shims

**Status:** OPERATOR DOCTRINE (2026-09-12) — "ensure compose build from submodule docker image, not hand-rolled shims with no provenance."

## The rule

A compose service that compiles code must build from a **submodule** Dockerfile — a fork under `POWERFULMOVES/`, pinned by gitlink, covered by `submodule-gitlink-gate`, registered in `fork_registry.json`, and carrying CHIT trail provenance. A `build:` stanza with `context: .` + a Dockerfile in `pmoves/services/<name>/` is a **hand-rolled shim**: it lives only in the superproject, has no upstream, no fork lineage, no gitlink pin, and its provenance chain is exactly one rewrite away from silent drift.

## Measured state (2026-09-13, after REMOTE-FORK-CONSUMER class added — operator correction: "a lot more than 14 submodules")

**80 submodules are pinned; 14 compose builds consume one directly; 2 more consume a fork by cloning it inside the image; 72 are pure superproject shims (baselined).**

| class | count | examples |
|---|---|---|
| SUBMODULE build (incl. env-var-prefixed contexts) | 14 | archon, agent-zero (via integrations overlay), openroom, pmoves-yt, transcribe-and-fetch, nats-hub, n8n, llama-throughput-lab, cipher-api, tokenism-ui, jellyfin-ai ×3 |
| REMOTE-FORK-CONSUMER (clones the fork in-image) | 2 | a0-elder-melchor → PMOVES-A0-codex-docker/PMOVES-Agent-Zero, ultimate-tts-studio → PMOVES-Ultimate-TTS-Studio |
| IMAGE only (no build) | 38 | published/digest-pinned images |
| SUPERPROJECT shim (registered exceptions) | 72 | `context: .` + superproject Dockerfiles |

### Promotion shortlist — VERIFIED, not fuzzy-matched (2026-09-13)

The name-similarity shortlist (agent-zero, botz-gateway, pmoves-ui, ultimate-tts-studio) did NOT survive verification:

- **agent-zero** — NOT a violation. The integrations overlay already builds from `${INTEGRATIONS_WORKSPACE}/PMOVES-Agent-Zero`; the base compose's multi-stage Dockerfile clones the fork in-image with a cache-bust ref (the #2202 stale-clone fix). Both faces consume the fork.
- **ultimate-tts-studio** — legitimate REMOTE-FORK-CONSUMER: 209-line hardened multi-stage Dockerfile cloning PMOVES-Ultimate-TTS-Studio; the fork's own root Dockerfile (44 lines) is the upstream UI, a different artifact.
- **botz-gateway** — the shim (FastAPI :8054 coordinator) and the PMOVES-BotZ-gateway fork (the BoTZ engine: botz.py, portal, dotnet) are DIFFERENT programs sharing a name. The shim is first-party glue; the fork is consumed elsewhere. No promotion; both are correctly registered.
- **pmoves-ui** — the Next.js portal's source tree IS `pmoves/ui` (first-party). PMOVES-A2UI is the renderer library (no Next app); not its build context. No promotion.

**Net: zero promotions needed from the shortlist.** The real gap is the other direction — submodules with no consumer at all; that audit is the next lane.

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
