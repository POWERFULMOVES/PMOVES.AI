#!/usr/bin/env python3
"""Safe-Opening Audit — Clause 3 of the Safe-Activation Contract.

`port_audit.py` checks *where* a service binds (loopback vs mesh-allowlisted
0.0.0.0). This tool adds the **bind -> auth coupling** that the binding model
does not assert: for every *reachable* surface (a non-loopback bind), is the
service actually auth-gated? A reachable bind with no verified auth gate is the
"opened unwittingly" case the contract exists to prevent.

It reuses `port_audit`'s compose parsing so the two stay in lockstep:
  - port_audit  -> bind scope    (127.0.0.1 vs 0.0.0.0; VIOLATION on stray 0.0.0.0)
  - this tool   -> auth coupling (reachable surface MUST be GATED, else flagged)

AUTH_GATES is the reviewed registry (mirrors port_audit's in-module
BIND_VAR_TO_SERVICES). It is intentionally a SMALL verified seed: any reachable
service not listed reports UNVERIFIED and fails closed. The first run therefore
produces the operator worklist of reachable-but-unverified surfaces — that is
the deliverable, not an assumption that unlisted == safe.

Reference: pmoves/docs/security/SAFE_ACTIVATION_CONTRACT.md
           pmoves/docs/security/PORT_BINDING_MODEL.md

Usage:
    python tools/safe_opening_audit.py        # audit from pmoves/
    make -C pmoves safe-opening-audit         # via Makefile
"""
import sys

from pmoves.tools.port_audit import (
    audit_ports,
    load_mesh_allowed_services,
    parse_compose_config,
)

LOOPBACK = "127.0.0.1"

# Reviewed auth-gate registry. gate=="public" means an intentionally-public
# surface that has been reviewed and accepted (still SAFE). Anything not listed
# is UNVERIFIED (fail-closed). Keep evidence honest — only add a service here
# once its gate is actually confirmed, not assumed.
AUTH_GATES: dict[str, dict[str, str]] = {
    "agent-zero": {
        "gate": "basic-auth",
        "evidence": "Agent Zero enforces AUTH_LOGIN/AUTH_PASSWORD on its UI/API "
                    "— the reason it may bind 0.0.0.0 (operator-confirmed).",
    },
    "nats": {
        "gate": "token-creds",
        "evidence": "NATS deployment authed via env.shared credentials "
                    "(see project_nats_auth_lane_b; confirm per node).",
    },
}

# Auth statuses that make a reachable surface unsafe (fail-closed).
UNSAFE_STATUSES = {"UNVERIFIED", "UNGATED"}


def is_reachable(bind: str) -> bool:
    """A non-loopback bind is reachable off-host (LAN/mesh). Loopback is host-local."""
    return bind != LOOPBACK


def audit_auth_coupling(
    findings: list[dict],
    auth_gates: dict[str, dict[str, str]],
) -> list[dict]:
    """Classify every *reachable* port finding by auth-gate status.

    findings: output of port_audit.audit_ports (each has service/bind/host_port).
    Returns one row per reachable finding with an added auth_status:
      GATED      — service has a verified auth gate (or reviewed public surface)
      UNGATED    — service explicitly registered with gate none/ungated
      UNVERIFIED — reachable but not in the registry (fail-closed)
    Loopback-only findings are skipped (host-local, out of scope).
    """
    results: list[dict] = []
    for f in findings:
        if not is_reachable(f.get("bind", "0.0.0.0")):
            continue
        svc = f["service"]
        gate = auth_gates.get(svc)
        if gate is None:
            status = "UNVERIFIED"
        elif gate.get("gate", "").lower() in ("none", "ungated", ""):
            status = "UNGATED"
        else:
            status = "GATED"
        results.append({
            **f,
            "auth_status": status,
            "gate": (gate or {}).get("gate", ""),
            "evidence": (gate or {}).get("evidence", ""),
        })
    return results


def print_report(results: list[dict]) -> int:
    """Print the auth-coupling report and return exit code (non-zero if unsafe)."""
    unsafe = [r for r in results if r["auth_status"] in UNSAFE_STATUSES]

    print("=== Safe-Opening Audit (bind -> auth coupling) ===")
    print("Scope: reachable surfaces only (non-loopback binds).\n")

    if not results:
        print("No reachable surfaces published — nothing to gate.")
        print("\nAll reachable surfaces are auth-gated (vacuously).")
        return 0

    print(f"{'SERVICE':<35} {'HOST_PORT':>10} {'BIND':>12} {'AUTH':>12}")
    print("-" * 73)
    for r in sorted(results, key=lambda x: (x["auth_status"] != "GATED", x["service"])):
        marker = "!!" if r["auth_status"] in UNSAFE_STATUSES else "  "
        print(f"{marker}{r['service']:<33} {r['host_port']:>10} {r['bind']:>12} {r['auth_status']:>12}")

    print(f"\nTotal reachable: {len(results)} | Unsafe (UNVERIFIED/UNGATED): {len(unsafe)}")

    if unsafe:
        print("\nREACHABLE WITHOUT VERIFIED AUTH (resolve or register a gate):")
        for r in unsafe:
            print(f"  {r['service']}:{r['host_port']} bound to {r['bind']} — {r['auth_status']}")
        print("\nFunnel, don't expose: gate the surface, lock the bind back to "
              "127.0.0.1, or register a verified gate in AUTH_GATES.")
        return 1

    print("\nAll reachable surfaces are auth-gated.")
    for r in results:
        print(f"  {r['service']}: {r['gate']} — {r['evidence']}")
    return 0


def main() -> int:
    config = parse_compose_config()
    if config is None:
        print("ERROR: dynamic compose parsing failed — failing closed.", file=sys.stderr)
        print("Run 'docker compose config' manually to diagnose.", file=sys.stderr)
        return 1
    if not config.get("services"):
        print("ERROR: compose config returned no services — failing closed.", file=sys.stderr)
        return 1

    _, mesh_allowed_services, _ = load_mesh_allowed_services()
    findings = audit_ports(config, mesh_allowed_services)
    results = audit_auth_coupling(findings, AUTH_GATES)
    return print_report(results)


if __name__ == "__main__":
    sys.exit(main())
