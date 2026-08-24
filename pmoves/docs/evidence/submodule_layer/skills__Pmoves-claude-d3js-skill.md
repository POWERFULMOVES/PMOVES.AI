# Submodule Layer Validation
_Generated: 2026-08-22 21:29 UTC_

## Summary
- Manifest: `pmoves/configs/submodule_layer_validation_manifest.json`
- Submodules declared: **1**
- Initialized: **0/1**
- Top-level modules: **0**
- Findings: **1 error(s)**, **0 warning(s)**

## Matrix
| Submodule | Initialized | Status | Remote Commit | Docs(any) | Top-level Dossier | Nested .gitmodules | Python Compile |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `skills/Pmoves-claude-d3js-skill` | no | `-` | `skip-uninitialized` | no | yes | ok | `skip` |

## Findings
- [ERROR] `UNINITIALIZED` `skills/Pmoves-claude-d3js-skill`: Submodule is not initialized.

## Layering Guidance
1. Run `make -C pmoves submodule-layer-validate-strict` until this report is clean.
2. Then run `make -C pmoves audit-layers-static` for root/static gates.
3. Finally run `make -C pmoves audit-layers-runtime` once services are up.

