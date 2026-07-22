# Handoff — tokenism image: package `pmoves.services.common` (CHIT-signing boot fix)

**Date:** 2026-07-22
**Node:** Z890 (now on main)
**Gated path:** `pmoves/services/tokenism-simulator/Dockerfile` (`dockerfile` Known-Road domain)
**Purpose:** Provable Known-Road referent for a small image-build fix that completes the tokenism CHIT-signing packaging.

## Grant

Operator authorizes with:
`dockerfile:handoff:tokenism-pmoves-services-common-packaging-2026-07-22.md`

Scope: **one file** (`pmoves/services/tokenism-simulator/Dockerfile`), the additive packaging below. Revoke after use.

## The bug (main-wide, verified live)

`pmoves-tokenism-simulator` crash-loops. Root cause is a namespace-packaging mismatch on **main** (the reconciled image build merged via #2184 was incomplete):

- Boot chain: `app.py → api/simulation.py → services/simulation_engine.py → services/chit_encoder.py:26`, which does `from pmoves.services.common.env import get_secret`.
- The build packages `services/common/env.py` at `/app/services/common/` (importable as `services.common.env`) and `pmoves/tools/*` at `/app/pmoves/tools/` — but **not** `pmoves/services/common/`. So `pmoves.services.common.env` → `ModuleNotFoundError: No module named 'pmoves.services'`.
- Earlier verification was flawed: it tested `import pmoves.tools.chit_security` (which the fix DID make work) instead of the actual boot import. The crash is one module deeper.

The GHCR CI image `ghcr.io/powerfulmoves/pmoves-tokenism-simulator:edge` is built from the same recipe, so it carries the identical gap — a main fix, not just a local rebuild.

## The fix (additive, mirrors the existing `pmoves/tools/` block)

Add after the existing `services/common` block (~line 45):
```
# pmoves.services.common.env — the boot path (chit_encoder) imports this namespace
RUN mkdir -p /app/pmoves/services/common \
    && printf '' > /app/pmoves/services/__init__.py \
    && printf '' > /app/pmoves/services/common/__init__.py
COPY services/common/__init__.py /app/pmoves/services/common/__init__.py
COPY services/common/env.py /app/pmoves/services/common/env.py
```
(Keep the existing `/app/services/common/` copy — other spellings may use `services.common`.)

## Acceptance test (the REAL boot path, not chit_security)

Inside the rebuilt image:
```
docker run --rm --entrypoint python <tag> -c "import services.simulation_engine; print('BOOT-IMPORT-OK')"
```
Must print `BOOT-IMPORT-OK` with no `ModuleNotFoundError`. A green healthcheck is NOT sufficient (gunicorn can appear up before the worker crash).

## After the fix

1. Rebuild locally: `docker -c default build -f services/tokenism-simulator/Dockerfile -t ghcr.io/powerfulmoves/pmoves-tokenism-simulator:edge pmoves` (context = `pmoves/`).
2. Run the acceptance test above.
3. Recreate on the node: `make -C pmoves compose ARGS="up -d --force-recreate --no-deps tokenism-simulator"` → confirm `healthy`, no restart, CHIT sign/verify round-trip.
4. PR the fix to main (CI image needs it too).
