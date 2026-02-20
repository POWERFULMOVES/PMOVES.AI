# CHIT Flow: Pytest Import/Collection Recovery

Flow ID: `chit.flow.ci.pytest-import-recovery.v1`

Use this flow when a CI Python test lane fails during collection with errors like:
- `ModuleNotFoundError`
- `ImportError`
- `Plugin already registered under a different name`
- `no tests ran` / `exit code 4` for missing test directories

## Detection

1. Pull the failed CI job log.
2. Extract the first import/collection error (ignore downstream noise).
3. Classify into one of these buckets:
- Hyphenated service path collision (multiple `tests/conftest.py` modules loaded in one pytest process)
- Missing compatibility shim (e.g., underscore import alias for a hyphenated module)
- Missing runtime dependency in workflow bootstrap
- Missing test directory referenced by static workflow target list

## Recovery Actions

1. Isolate suites per service:
- Run one pytest invocation per service path in CI.
- Keep `--import-mode=importlib`.

2. Guard target directories:
- In workflow loops, skip targets that do not exist (`if [ ! -d "$target" ]; then continue; fi`).

3. Restore compatibility shims for hyphenated modules:
- Provide underscore package aliases where tests import `services.<name_with_underscore>`.

4. Keep CI bootstrap deps explicit:
- Add required base packages (for this repo: `typer`, `yt-dlp`, `boto3`, `tenacity`, `supabase`) in the workflow install step.

5. Re-run focused local suites before push:
- `pmoves/services/pmoves-yt/tests`
- `pmoves/services/gateway/tests`
- `pmoves/services/flute-gateway/tests`

## Verification

A run is considered recovered when:
- `tests (3.11)` passes
- No collection/import errors remain
- Workflow skips missing directories cleanly instead of failing

## Porting To Other Repos

1. Keep the same flow ID and copy this file.
2. Update only:
- Service target list
- Required base packages
- Shim package names
3. Keep the detect-classify-recover order unchanged.

