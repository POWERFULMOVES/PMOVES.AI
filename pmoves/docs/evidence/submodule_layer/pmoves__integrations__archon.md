# Submodule Layer Validation
_Generated: 2026-02-26 18:22 UTC_

## Summary
- Manifest: `pmoves/configs/submodule_layer_validation_manifest.json`
- Submodules declared: **1**
- Initialized: **1/1**
- Top-level modules: **0**
- Findings: **0 error(s)**, **0 warning(s)**

## Matrix
| Submodule | Initialized | Status | Remote Commit | Docs(any) | Top-level Dossier | Nested .gitmodules | Python Compile |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pmoves/integrations/archon` | yes | ` ` | `local` | yes | yes | ok | `skip` |

## Findings
- No findings.

## Layering Guidance
1. Run `make -C pmoves submodule-layer-validate-strict` until this report is clean.
2. Then run `make -C pmoves audit-layers-static` for root/static gates.
3. Finally run `make -C pmoves audit-layers-runtime` once services are up.

