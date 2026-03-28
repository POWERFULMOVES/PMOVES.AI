# PMOVES-Tailscale — Status
_Last updated: 2026-03-28_

## Purpose
- Tailnet connectivity and secure access workflows for PMOVES operators.

## Implemented items
- Tailnet ACL policy captured at `pmoves/configs/tailscale-acl-policy.json`.
  Evidence: policy-management flow and admin API notes are documented in `../operations/FLEET_REMOTE_ACCESS_RUNBOOK.md`.
- Remote-access runbooks now exist:
  - `../operations/FLEET_REMOTE_ACCESS_RUNBOOK.md`
  - `../operations/RUSTDESK_SELF_HOSTED.md`
  - `../TAILSCALE_NODE_HYGIENE.md`
  Evidence: the runbooks now carry the operator path, cleanup procedure, and privacy-safe handling rules for live tailnet inventory.
- Enrollment and KVM2 watcher flow landed through:
  - `pmoves/scripts/fleet/generate-enrollment.py`
  - `pmoves/scripts/fleet/fleet-audit-watcher.sh`
  - `pmoves/scripts/fleet/fleet-audit-watcher.service`
  Evidence: the KVM2 install/verify path is documented in `../operations/RUSTDESK_SELF_HOSTED.md`, and the signed deployment notes plus current blocker state are recorded in `../AGENTS/AGNOTE4482PHI.t1.md`.

## Remaining items
- Expose one NATS broker on a Tailscale-reachable interface so KVM2 watcher events can publish beyond local JSON logs.
- Automate stale-device cleanup with `TAILSCALE_API_KEY` or a scoped trust-credential path.
- Keep PMOVES-Tailscale overlays and shared z890 Codex/Claude infra docs aligned as the fleet grows.
