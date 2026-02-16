# Operations - firefly-iii (PMOVES-Wealth)

## Checks

- `../tools/validate-submodule.sh`
- `../tools/submodule-sitrep.sh`
- `../tools/validate-integration.sh .. --strict-hooks`

## Bring-up

1. Configure secrets via CHIT + secrets funnel.
2. Start integrations stack (`make -C pmoves integrations-up-firefly` or `integrations-up-all`).
3. Import/sync n8n flows from `n8n/flows/`.

## Auth/bootstrap order

1. Run PMOVES auth bootstrap (`make -C pmoves auth-bootstrap`).
2. Run this overlay bootstrap if needed (`../auth/bootstrap.sh`).

## Smoke checks

- `make -C pmoves auth-check`
- `make -C pmoves monitoring-status`

## Rollback

1. Stop integrations compose profile.
2. Revert flow changes to prior export set.
3. Re-run validation checks and restart.
