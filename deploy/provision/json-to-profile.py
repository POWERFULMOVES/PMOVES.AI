#!/usr/bin/env python3
"""json-to-profile.py — Convert a glances-autodetect probe JSON into a PMOVES node profile YAML.

USAGE:
    python json-to-profile.py --json /path/to/probe.json --node-id pmoves-rdna4 \\
        [--out-dir pmoves/config/profiles/] [--dry-run] [--force]

INPUT: JSON produced by deploy/provision/glances-autodetect.sh (or .ps1)
OUTPUT: YAML profile written to <out-dir>/<node-id>.yaml (or printed with --dry-run)

Requires: pyyaml  (pip install pyyaml)
All other dependencies are stdlib only.
"""

import argparse
import json
import os
import sys

try:
    import yaml
except ImportError:
    print(
        "ERROR: pyyaml is required but not installed.\n"
        "       Run: pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

_REQUIRED_PROBE_FIELDS = ("cpu", "ram_gb", "suggested_node_type")


def validate_probe(data: dict) -> None:
    missing = [f for f in _REQUIRED_PROBE_FIELDS if f not in data]
    if missing:
        print(
            f"ERROR: Probe JSON is missing required fields: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)


_TAILSCALE_ROLE_MAP = {
    "gpu-5090": "gpu-node",
    "gpu-4090": "gpu-node",
    "rdna4-workstation": "gpu-node",
    "dgx-spark": "gpu-node",
    "pve-member": "pve-member",
    "pve-member-fresh": "pve-member",
    "desktop-workstation": "desktop-workstation",
}


def map_arch(arch_str: str) -> str:
    """Normalise architecture string to PMOVES canonical form."""
    return {"x86_64": "amd64", "aarch64": "arm64"}.get(arch_str, arch_str)


def map_tailscale_role(suggested_node_type: str) -> str:
    """Return the Tailscale role for a given suggested node type."""
    return _TAILSCALE_ROLE_MAP.get(suggested_node_type, "unknown")


def build_tags(arch: str, gpus: list, suggested_node_type: str) -> list:
    """Derive hardware tags from arch, GPU list, and suggested node type."""
    tags = [map_arch(arch)]

    for g in gpus:
        vendor = g.get("vendor", "").lower()
        if vendor in ("nvidia", "amd", "intel") and vendor not in tags:
            tags.append(vendor)

    # Workload class tag derived from node type
    ntype = suggested_node_type.lower()
    if ntype.startswith("gpu-") or ntype.startswith("rdna4-"):
        tags.append("workstation")
    elif ntype == "dgx-spark":
        tags.append("dgx")
    elif ntype.startswith("pve-member"):
        tags.append("pve")
    elif ntype.startswith("desktop-"):
        tags.append("desktop")
    elif ntype.startswith("kvm"):
        tags.append("kvm")
    # else: no workload tag for unknown

    return tags


def build_name(suggested_node_type: str, cpu_model: str) -> str:
    """Derive a human-readable profile name."""
    return f"{suggested_node_type} — {cpu_model}"


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_profile(data: dict, node_id: str) -> dict:
    """Map probe JSON dict to a PMOVES node profile dict."""

    os_info = data.get("os", {})
    arch = data.get("arch", "x86_64")
    cpu = data.get("cpu", {})
    ram_gb = data.get("ram_gb", 0)
    gpus = data.get("gpus", [])
    nic_collisions = data.get("nic_collisions", [])
    platform_hints = data.get("platform_hints", {})
    suggested_node_type = data.get("suggested_node_type", "unknown")
    suggestion_confidence = data.get("suggestion_confidence", "high")

    # --- CPU sub-dict ---
    cpu_dict = {
        "vendor": _infer_cpu_vendor(cpu.get("model", "")),
        "model": cpu.get("model", ""),
        "cores": cpu.get("cores_physical", 0),
        "threads": cpu.get("cores_logical", 0),
        "arch": map_arch(arch),
    }

    # --- GPU(s) ---
    gpu_block = _build_gpu_block(gpus)

    # --- Hardware dict ---
    hardware: dict = {"cpu": cpu_dict}
    hardware.update(gpu_block)  # injects "gpus" key (list, always consistent)
    hardware["ram_gb"] = ram_gb
    hardware["tags"] = build_tags(arch, gpus, suggested_node_type)

    # --- compose_overrides ---
    compose_overrides = (
        ["docker-compose.arm64.override.yml"] if arch == "aarch64" else []
    )

    # --- notes ---
    notes: list = []

    # nic_collisions
    ghost_adapter_warning = False
    if nic_collisions:
        ghost_adapter_warning = True
        for col in nic_collisions:
            primary = col.get("primary", "")
            ghost = col.get("ghost", "")
            subnet = col.get("subnet", "")
            notes.append(
                f"NIC collision on {subnet}: primary={primary}  ghost={ghost}"
            )

    # Docker not present
    if not platform_hints.get("has_docker", True):
        notes.append(
            "Docker not detected — install Docker before running compose stacks."
        )

    # Low confidence
    if suggestion_confidence == "low":
        notes.append(
            "Auto-detected node type has low confidence — review and override manually."
        )

    # Windows host
    if os_info.get("distro", "").lower() == "windows":
        notes.append(
            "Windows host — add docker-compose.windows.override.yml to compose_overrides."
        )

    # --- Assemble profile ---
    profile: dict = {
        "id": node_id,
        "name": build_name(suggested_node_type, cpu.get("model", "")),
        "hardware": hardware,
        "compose_overrides": compose_overrides,
        "services": ["mesh-agent", "fleet-agent"],
        "tailscale": {
            "role": map_tailscale_role(suggested_node_type),
            "hostname_pattern": node_id,
        },
        "unifi_topology": data.get("unifi_topology"),
        "notes": notes,
    }

    # ghost_adapter_warning sits at top-level if triggered
    if ghost_adapter_warning:
        profile["ghost_adapter_warning"] = True

    return profile


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _infer_cpu_vendor(model: str) -> str:
    """Best-effort CPU vendor from model string."""
    m = model.lower()
    if "amd" in m or "ryzen" in m or "epyc" in m or "threadripper" in m:
        return "AMD"
    if "intel" in m or "core" in m or "xeon" in m or "celeron" in m or "pentium" in m:
        return "Intel"
    if "arm" in m or "cortex" in m or "grace" in m or "neoverse" in m:
        return "ARM"
    if "apple" in m:
        return "Apple"
    return "Unknown"


def _build_gpu_block(gpus: list) -> dict:
    """Return {gpus: [...]} for any number of GPUs (consistent list, never singular gpu key)."""
    if not gpus:
        return {}
    return {
        "gpus": [
            {
                "vendor": g.get("vendor", ""),
                "model":  g.get("model", ""),
                "vram_gb": g.get("vram_gb", 0),
            }
            for g in gpus
        ]
    }


# ---------------------------------------------------------------------------
# YAML dumper — preserve insertion order, no aliases, literal strings
# ---------------------------------------------------------------------------

class _NoAliasDumper(yaml.Dumper):
    """YAML dumper that never emits aliases and preserves dict insertion order."""

    def ignore_aliases(self, data):
        return True


def _dump_yaml(profile: dict) -> str:
    return yaml.dump(
        profile,
        Dumper=_NoAliasDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict:
    """Load and parse a JSON file, with clear error messages."""
    if not os.path.isfile(path):
        print(f"ERROR: JSON file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Failed to parse JSON: {exc}", file=sys.stderr)
        sys.exit(1)


def write_profile(yaml_text: str, out_dir: str, node_id: str, force: bool) -> str:
    """Write profile YAML to <out_dir>/<node_id>.yaml. Returns the output path."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{node_id}.yaml")
    if os.path.exists(out_path) and not force:
        print(
            f"ERROR: Profile already exists: {out_path}\n"
            "       Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(yaml_text)
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="json-to-profile.py",
        description=(
            "Convert a glances-autodetect probe JSON into a PMOVES node profile YAML.\n\n"
            "Reads JSON probe output produced by glances-autodetect.sh (or .ps1) and\n"
            "writes a PMOVES node profile YAML to --out-dir/<node-id>.yaml.\n\n"
            "Example:\n"
            "  python json-to-profile.py \\\n"
            "      --json /tmp/probe.json \\\n"
            "      --node-id pmoves-rdna4 \\\n"
            "      --out-dir pmoves/config/profiles/"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--json",
        required=True,
        metavar="PATH",
        help="Path to the probe JSON file (from glances-autodetect.sh --json-file=PATH).",
    )
    p.add_argument(
        "--node-id",
        required=True,
        metavar="ID",
        help="Fleet hostname used as profile id and output filename (e.g. pmoves-rdna4).",
    )
    p.add_argument(
        "--out-dir",
        default="pmoves/config/profiles/",
        metavar="DIR",
        help="Directory to write <node-id>.yaml into. Created if absent. (default: pmoves/config/profiles/)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated YAML to stdout; do not write any file.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing profile. Default: error if the file already exists.",
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    data = load_json(args.json)
    validate_probe(data)
    profile = build_profile(data, args.node_id)
    yaml_text = _dump_yaml(profile)

    if args.dry_run:
        print(yaml_text, end="")
        return

    out_path = write_profile(yaml_text, args.out_dir, args.node_id, args.force)
    print(f"Profile written: {out_path}")


if __name__ == "__main__":
    main()
