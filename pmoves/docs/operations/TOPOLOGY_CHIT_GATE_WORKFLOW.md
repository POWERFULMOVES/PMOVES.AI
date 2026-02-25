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
- `CHIT_PASSPHRASE=${CHIT_PROD_PASSPHRASE:-${JWT_SECRET:-}}`

Set these in `env.shared`/secrets if you need non-default behavior:

- `CHIT_PROD_REQUIRE_SIGNATURE`
- `CHIT_PROD_DECRYPT_ANCHORS`
- `CHIT_PROD_PASSPHRASE`

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
