# PMOVES Integration Validation Tools

Use these can-openers when onboarding or promoting submodule integrations:

- `./validate-submodule.sh`
  - Runs the PMOVES non-recursive submodule integrity gate.
- `./submodule-sitrep.sh`
  - Generates the submodule alignment SITREP report.
- `./validate-integration.sh [path] [--strict-hooks]`
  - Validates the integration overlay contract (layout + required announcer/GPU subjects + hook terms).

These wrappers resolve `PMOVES_ROOT` automatically by walking up to the repo root.
