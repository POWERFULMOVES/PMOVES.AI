#!/usr/bin/env python3
"""Classify a node into a capability tier for capability-adaptive standalone Agent Zero.

Agent Zero is the primary orchestrator; "standalone" is NOT minimal — it expands
with node capability (MOF capacity-class model). This classifier maps a node to
one of three tiers, which the bring-up (`up-agents-auto`) uses to pick the
service set:

    lean    -> agent core only (nats + agent-zero + mesh)         [weak VPS]
    capable -> + data tier + Consciousness/CHIT + persona/forms   [strong CPU/RAM]
    gpu     -> capable + GPU services                             [capable + GPU]

Precedence: PMOVES_NODE_TIER override -> glances-autodetect suggested_node_type
mapping -> raw thresholds over the probe (cpu.cores_logical, ram_gb,
gpus[].vram_gb).

See pmoves/docs/architecture/CAPABILITY_ADAPTIVE_STANDALONE.md.

Usage:
    node_capability_tier.py --input probe.json        # full JSON verdict
    node_capability_tier.py --node-type gpu-5090      # classify by node type
    node_capability_tier.py --make                    # print just the tier
    glances-autodetect.sh | node_capability_tier.py   # read probe on stdin
"""

from __future__ import annotations

import argparse
import json
import os
import sys

TIERS = ("lean", "capable", "gpu")

# glances-autodetect `suggested_node_type` -> tier. Keep in sync with the probe's
# class taxonomy (deploy/provision/glances-autodetect.{sh,ps1}).
NODE_TYPE_TIER = {
    "kvm4-1": "lean",
    "kvm4-2": "lean",
    "kvm2": "lean",
    "pve-member": "capable",
    "pve-member-fresh": "capable",
    "gpu-5090": "gpu",
    "rdna4-workstation": "gpu",
    "dgx-spark": "gpu",
}

# Raw-threshold fallback (used only when the node type is unknown). Supabase +
# Neo4j + Hi-RAG comfortably need ~8 cores / ~32 GB headroom alongside the agent.
MIN_CAPABLE_CORES = 8
MIN_CAPABLE_RAM_GB = 32
MIN_GPU_VRAM_GB = 12

# Service sets layered per tier (extra beyond the lean agent core, which the
# bring-up target always starts: nats + agent-zero + mesh-agent).
SERVICES_CAPABLE = [
    "supabase-local",       # data plane (profile)
    "neo4j",                # graph
    "hi-rag-gateway-v2",    # hybrid retrieval (CPU)
    "consciousness-service",  # CHR/CGP (CHIT)
    "cipher-api",           # persistent memory MCP
    "archon",               # persona/forms/prompts
]
SERVICES_GPU = [
    "hi-rag-gateway-v2-gpu",
    "media-video",
    "media-audio",
]


def services_extra(tier: str) -> list[str]:
    """Services a tier adds on top of the lean agent core."""
    if tier == "capable":
        return list(SERVICES_CAPABLE)
    if tier == "gpu":
        return list(SERVICES_CAPABLE) + list(SERVICES_GPU)
    return []


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def classify(
    probe: dict | None = None,
    *,
    node_type: str | None = None,
    override: str | None = None,
) -> dict:
    """Return {tier, rationale, source, services_extra}.

    `probe` is the parsed glances-autodetect JSON. `node_type` forces a node-type
    classification. `override` (PMOVES_NODE_TIER) short-circuits everything.
    """
    # 1. Explicit operator override.
    if override:
        ov = override.strip().lower()
        if ov not in TIERS:
            raise ValueError(
                f"PMOVES_NODE_TIER must be one of {TIERS}, got {override!r}"
            )
        return _verdict(ov, f"PMOVES_NODE_TIER override = {ov}", "override")

    probe = probe or {}
    nt = (node_type or probe.get("suggested_node_type") or "").strip()

    # 2. Known node-type mapping.
    if nt in NODE_TYPE_TIER:
        tier = NODE_TYPE_TIER[nt]
        return _verdict(tier, f"node type {nt} -> {tier}", "node-type")

    # 3. Raw-threshold fallback (unknown or absent node type).
    cores = int(_num((probe.get("cpu") or {}).get("cores_logical")))
    ram = _num(probe.get("ram_gb"))
    gpus = probe.get("gpus") or []
    max_vram = max([_num(g.get("vram_gb")) for g in gpus] + [0.0])

    capable = cores >= MIN_CAPABLE_CORES and ram >= MIN_CAPABLE_RAM_GB
    if capable and max_vram >= MIN_GPU_VRAM_GB:
        tier, why = "gpu", f"{cores} cores, {ram:g} GB RAM, {max_vram:g} GB VRAM"
    elif capable:
        tier, why = (
            "capable",
            f"{cores} cores, {ram:g} GB RAM, no GPU >= {MIN_GPU_VRAM_GB} GB VRAM",
        )
    else:
        tier, why = (
            "lean",
            f"{cores} cores, {ram:g} GB RAM below capable threshold "
            f"({MIN_CAPABLE_CORES} cores / {MIN_CAPABLE_RAM_GB} GB)",
        )
    if nt:
        why = f"unknown node type {nt!r}; {why}"
    return _verdict(tier, why, "thresholds")


def _verdict(tier: str, rationale: str, source: str) -> dict:
    return {
        "tier": tier,
        "rationale": rationale,
        "source": source,
        "services_extra": services_extra(tier),
    }


def _load_probe(path: str | None) -> dict | None:
    if path and path != "-":
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        if data:
            return json.loads(data)
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Classify a node's capability tier.")
    ap.add_argument("--input", help="glances-autodetect JSON file ('-' or stdin)")
    ap.add_argument("--node-type", help="classify by suggested_node_type directly")
    ap.add_argument(
        "--make",
        action="store_true",
        help="print only the tier (for shell/Makefile use)",
    )
    args = ap.parse_args(argv)

    override = os.getenv("PMOVES_NODE_TIER")
    probe = None
    if not override and not args.node_type:
        try:
            probe = _load_probe(args.input)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"node_capability_tier: could not read probe: {exc}", file=sys.stderr)
            return 2

    try:
        verdict = classify(probe, node_type=args.node_type, override=override)
    except ValueError as exc:
        print(f"node_capability_tier: {exc}", file=sys.stderr)
        return 2

    if args.make:
        print(verdict["tier"])
    else:
        print(json.dumps(verdict, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
