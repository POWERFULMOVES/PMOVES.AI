# FlOO$ — Linked Skills with Hooks & Dependencies

Resolve, validate, and inspect skill pairing pipelines with dependency tracking and NATS hook integration.

## Arguments

- `$ARGUMENTS` - Subcommand and options: `resolve <pairing>`, `validate <pairing>`, `status`, `hooks`

## Instructions

Parse the subcommand from `$ARGUMENTS` and execute accordingly:

### `resolve <pairing>`

Show the dependency DAG for a named pairing from `pmoves/configs/skill-pairings.yaml`.

1. Run `python -m pmoves.tools.chit.floos_resolver resolve <pairing>` from the repo root
2. Display the DAG tree showing:
   - Execution order (topological sort)
   - Per-step: agent, input/output, depends, services, health URL, hooks
3. Highlight any dependency errors

### `validate <pairing>`

Check that all dependencies for a pairing are satisfied.

1. Run `python -m pmoves.tools.chit.floos_resolver validate <pairing>`
2. Add `--live` to also check if services are running and health endpoints respond
3. Report: DAG validity, execution order, service port status, health check results
4. Exit with non-zero if any dependency is unsatisfied

### `status`

Show readiness overview of all 6 skill pairings.

1. Run `python -m pmoves.tools.chit.floos_resolver status`
2. Add `--live` to include service health checks
3. Lists each pairing with: name, step count, NATS subject, FlOO$ features (deps/hooks/ultrathink), validation status

### `hooks`

List all registered NATS hooks across all pairings.

1. Run `python -m pmoves.tools.chit.floos_resolver hooks`
2. Groups hooks by NATS subject, showing which pairing/skill publishes each
3. Shows total subject and hook counts

## Examples

```bash
# Show DAG for the CHIT ingestion pipeline
/chit:floos resolve ingest-chit-index

# Validate with live service checks
/chit:floos validate voice-synthesis --live

# Overview of all pipelines
/chit:floos status

# List all NATS hook subjects
/chit:floos hooks
```

## Related

- `/chit:encode` - Encode data as CGP v2 packet
- `/chit:decode` - Decode CGP v2 packets
- `/chit:bus` - Publish to GEOMETRY BUS
- `/chit:visualize` - Render packet geometry
