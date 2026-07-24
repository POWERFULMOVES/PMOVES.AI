# Handoff — tokenism image: initialize `services.common` minimally (CHIT-signing boot fix)

**Date:** 2026-07-22
**Node:** Z890 (now on main)
**Gated path:** `pmoves/services/tokenism-simulator/Dockerfile` (`dockerfile` Known-Road domain)
**Purpose:** Provable Known-Road referent for a small image-build fix that completes the tokenism CHIT-signing packaging.

## Grant

Operator authorizes with:
`dockerfile:handoff:tokenism-pmoves-services-common-packaging-2026-07-22.md`

Scope: **one file** (`pmoves/services/tokenism-simulator/Dockerfile`), the minimal-package correction below. Revoke after use.

## The bug (main-wide, verified live)

`pmoves-tokenism-simulator` enters a crash loop. Root cause is a namespace-packaging mismatch on **main** (the reconciled image build merged via #2184 was incomplete):

- Boot chain: `app.py → api/simulation.py → services/simulation_engine.py → services/chit_encoder.py:23-26`, which tries `from services.common.env import get_secret` first and falls back to `from pmoves.services.common.env import get_secret` on `ImportError`.
- The build copies the repository's full `services/common/__init__.py` but only bundles `env.py`. Importing `services.common.env` executes that initializer first; its unconditional telemetry/model-nexus imports are absent from this narrow image, so the primary import raises `ImportError`.
- The handler then tries its compatibility fallback, `pmoves.services.common.env`, which is not packaged and raises `ModuleNotFoundError: No module named 'pmoves.services'`. The missing fallback is the final error, not the first cause.
- Earlier verification was flawed: it tested `import pmoves.tools.chit_security` (which the fix DID make work) instead of the actual boot import. The crash is one module deeper.

The GHCR CI image `ghcr.io/powerfulmoves/pmoves-tokenism-simulator:edge` is built from the same recipe, so it carries the identical gap — a main fix, not just a local rebuild.

## The fix (make the primary import self-contained)

Keep the partial `services.common` package initializer empty and copy only the
module this image uses:
```dockerfile
# services/common/env.py — CHIT passphrase + secret helpers.
# Keep this partial package initializer empty: the repository initializer imports
# modules that are intentionally not bundled in this narrow service image.
RUN mkdir -p /app/services/common \
    && printf '' > /app/services/common/__init__.py
COPY services/common/env.py /app/services/common/env.py
```

Do not duplicate `env.py` under `/app/pmoves/services/common/`; a healthy primary
import should not rely on the compatibility fallback.

## Acceptance test (the REAL boot path, not chit_security)

Inside the rebuilt image:
```bash
docker run --rm --entrypoint python <tag> -c "import services.simulation_engine; print('BOOT-IMPORT-OK')"
```
Must print `BOOT-IMPORT-OK` with no `ModuleNotFoundError`. A green healthcheck is NOT sufficient (gunicorn can appear up before the worker crash).

## After the fix

1. Rebuild locally: `docker -c default build -f services/tokenism-simulator/Dockerfile -t ghcr.io/powerfulmoves/pmoves-tokenism-simulator:edge pmoves` (context = `pmoves/`).
2. Run the acceptance test above.
3. Recreate on the node: `make -C pmoves compose ARGS="up -d --force-recreate --no-deps tokenism-simulator"` → confirm `healthy`, no restart, CHIT sign/verify round-trip.
4. PR the fix to main (CI image needs it too).
