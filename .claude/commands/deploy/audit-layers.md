Run static certification audit layers across submodules, secrets, CI runners, and tooling.

This is the comprehensive pre-deployment audit that validates the entire PMOVES infrastructure is correctly configured before any runtime tests.

## Audit Layer Stack (executed in order)

```
1. submodule-layer-validate-all-strict  — Per-submodule deterministic validation
2. submodule-layer-validate-strict      — Cross-submodule consistency check
3. submodule-integrity-strict           — Git submodule pointer integrity
4. submodule-docs-audit-strict          — Documentation completeness
5. integration-contract-check-baseline  — CHIT contract schema validation
6. tooling-audit-strict                 — Tools/scripts overlap analysis
7. secrets-audit                        — CHIT paths, sync workflow, export hygiene
8. ci-runners-lockdown-strict           — Runner lane phase policy enforcement
9. supa-runtime-guard                   — Supabase runtime mode guardrails
```

## Implementation

Execute the following steps:

1. **Run static audit layers (no running services needed):**
   ```bash
   make -C pmoves audit-layers-static
   ```

   This runs all 9 checks above. Each must pass for the audit to succeed.

2. **If you also want runtime validation (services must be running):**
   ```bash
   make -C pmoves audit-layers-runtime
   ```

   This runs static layers PLUS smoke tests and monitoring validation.
   Requires services to be up via `make -C pmoves up` first.

3. **For GPU-aware runtime audit:**
   ```bash
   AUDIT_RUNTIME_GPU=1 make -C pmoves audit-layers-runtime
   ```

## Interpreting Results

- **submodule-layer-validate** failures: Check `configs/submodule_layer_validation_manifest.json` for expected structure
- **secrets-audit** failures: Run `/deploy:secrets-funnel` to regenerate tier files
- **ci-runners-lockdown** failures: Runner lanes not registered for current phase — check `tools/runner_lane_map.py`
- **tooling-audit** failures: Script overlap between repo tools and submodule tools — see `docs/AGENTS/TOOLING_SCRIPT_AUDIT.md`

## Order of Operations

If audit fails, the typical recovery path is:

```
1. make -C pmoves secrets-funnel        (fix secrets issues)
2. make -C pmoves bootstrap-tier-envs   (fix missing tier files)
3. git submodule update --init          (fix submodule pointers)
4. make -C pmoves audit-layers-static   (re-run audit)
```

## Notes

- Static audit requires no running containers — safe to run anytime
- Runtime audit requires `make -C pmoves up` stack to be healthy
- Strict mode means warnings are promoted to errors
- Full audit output goes to stdout — pipe to file for evidence: `make -C pmoves audit-layers-static 2>&1 | tee audit-evidence.log`
