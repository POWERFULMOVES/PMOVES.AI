# missinglinc-validator (wave-0, surface depth only). DRAFT

External-peer-review validator for PMOVES agent output. Spec:
`pmoves/docs/AGENTS/MISSINGLINC_MINT_SPEC.md`. Build base: the `PMOVES-Mike`
submodule (`pmoves/docs/integrations/MIKE_INTEGRATION.md`).

## Done

- `missinglinc_validator/verify.py` is a faithful Python port of Mike's
  `verifyCitations.ts` and `normalizeWithMap` (PMOVES-Mike @ 563c8319):
  - a three-tier quote locator (exact, then whitespace+case, then
    punctuation-tolerant);
  - ellipsis-segmented quotes;
  - `[[PAGE_BREAK]]` cross-page quotes, which must appear in order, within
    5,000 chars, with at most 64 attempts;
  - the unreadable-source sentinels.

  Every result carries `match_tier`, so a tolerant match is never reported as
  verbatim. `sha256_text` is used for the per-document and per-span hashes.
- `tests/test_verify.py` covers these behaviours: 10 tests.

## Left (not built yet; nothing here pretends otherwise)

- NATS consumer for `validation.run.requested.v1`, and the
  `validation.verdict.ready.v1` publisher with per-claim `verified` /
  `not_found` plus an evidence chain (sha256 per source doc and per span).
  The `deep` and `adversarial` depths will return `UNDECIDED` with the reason
  "depth not implemented in wave-0".
- FastAPI `/healthz` and `/metrics`, `requirements.txt`, and a
  `requirements.lock` built with `uv pip compile`.
- **Operator-apply under the guard:** the Dockerfile (`dockerfile` road),
  the `validation/run.requested.v1` and `verdict.ready.v1` JSON Schemas under
  `pmoves/contracts/schemas/` (`schema` road), the compose service (`compose`
  road), and the `topics.json` registration.
- MinIO-URI source fetch. Wave-0 will accept inline sources only.
