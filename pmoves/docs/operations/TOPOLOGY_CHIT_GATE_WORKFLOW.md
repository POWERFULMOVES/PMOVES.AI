# Topology + CHIT Gate Workflow

Last updated: 2026-02-25

## Goal

Run a deterministic production gate that validates:

- container topology policy (networks, published ports, namespace rules)
- Archon UI/headless Archon health/topology
- CHIT manifest sync and CHIT runtime enforcement on required services

## Source of truth

- Gate script: `pmoves/tools/topology_chit_gate.py`
- Policy manifest: `pmoves/configs/topology_policy_manifest.json`
- Make targets: `topology-chit-gate`, `topology-chit-gate-strict`

## Standard runbook

1. Bring up or recreate services so env interpolation is current.

```bash
make -C pmoves up
make -C pmoves up-agents
make -C pmoves up-yt
```

2. Run warning mode and capture findings.

```bash
make -C pmoves topology-chit-gate
```

3. Remediate warnings/errors in policy, compose, or env.

4. Run strict mode (must be green before promotion PR).

```bash
make -C pmoves topology-chit-gate-strict
```

## CHIT production defaults

Core CHIT services now use compose-level production overlays:

- `CHIT_REQUIRE_SIGNATURE=${CHIT_PROD_REQUIRE_SIGNATURE:-true}`
- `CHIT_DECRYPT_ANCHORS=${CHIT_PROD_DECRYPT_ANCHORS:-true}`
- `CHIT_PASSPHRASE=${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}`

Set these in `env.shared` (gitignored, never committed):

- `CHIT_PROD_REQUIRE_SIGNATURE`
- `CHIT_PROD_DECRYPT_ANCHORS`
- `CHIT_PROD_PASSPHRASE`

### Generating CHIT_PROD_PASSPHRASE

A strong 64-character random passphrase is required. Generate one with:

```bash
openssl rand -base64 48 | tr -d '\n=' | cut -c1-64
```

Then set **both** variables in `pmoves/env.shared`:

```env
CHIT_PASSPHRASE=<generated-64-char-value>
CHIT_PROD_PASSPHRASE=<same-value>
```

`CHIT_PASSPHRASE` is the base variable used by non-compose contexts.
`CHIT_PROD_PASSPHRASE` is the compose overlay variable referenced by docker-compose.yml.
Setting both ensures the passphrase resolves regardless of execution context.

### Docker Compose V2 nesting caveat

Docker Compose V2 does **not** evaluate nested variable substitution like
`${A:-${B:-default}}`. The inner expression is treated as a literal string.
For this reason, all compose CHIT_PASSPHRASE lines use the `:?` (required)
operator to fail fast if the variable is not set:

```yaml
CHIT_PASSPHRASE=${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}
```

This causes `docker compose up` to abort with a clear error message if
`CHIT_PROD_PASSPHRASE` is missing from the environment, rather than
silently running with a weak default.

### Verifying the fix

After setting the passphrase and recreating containers:

```bash
cd pmoves
docker compose up -d hi-rag-gateway hi-rag-gateway-v2 agent-zero evo-controller flute-gateway
make topology-chit-gate-strict
```

Expected: 0 errors, 0 warnings.

## Policy fields to tune for other repositories

- `required_networks_by_service`
- `required_published_ports_by_service`
- `published_external_exceptions`
- `loopback_exception_keys_by_service`
- `chit_required_services`

## PR hygiene for this workflow

- keep policy changes, gate logic changes, and service/runtime changes in separate atomic commits
- include gate command output in PR testing notes
- require strict gate green before merge
