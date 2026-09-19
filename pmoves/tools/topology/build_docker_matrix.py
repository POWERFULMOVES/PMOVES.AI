#!/usr/bin/env python3
"""Regenerate pmoves/configs/topology/docker_matrix.yaml.

Two-source approach (operator-designated, directory-first):

  Source A (canonical): every directory under pmoves/services/ or
    pmoves/integrations/ that has a Dockerfile (any flavor: Dockerfile,
    Dockerfile.pmoves, Dockerfile.amd). Each such directory IS a real
    service. The directory's basename becomes the service name in the
    matrix (canonical form, with hyphens normalized from underscores
    where the compose file uses underscores).

  Source B (overlay mapping): every pmoves/docker-compose*.yml file
    scanned for top-level service-name keys (after excluding the known
    false-positive keys: networks, volumes, secrets, x-* anchors).
    Each name is matched against Source A; names that match a real
    service get that service's overlay entry recorded. Names that don't
    match are flagged in the matrix under an 'unmapped_compose_keys'
    section — they appear in compose but have no source directory.

  Why two sources: Source A prevents the matrix from being polluted by
  compose noise (tmpfs, network-name patterns, secret-name patterns).
  Source B prevents the matrix from missing services that are declared
  in compose but lack a sibling directory (operator-managed externally,
  e.g. agent-zero-spark under pmoves/integrations/).

  The output is a Pydantic-compatible YAML shape (typed name, typed
  overlay name as string enum, list of paths). The corresponding
  pmoves/tools/topology/check_known_roads.py reads it.

Usage:
    python pmoves/tools/topology/build_docker_matrix.py
    python pmoves/tools/topology/build_docker_matrix.py --out PATH
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "pmoves" / "configs" / "topology" / "docker_matrix.yaml"

KNOWN_TOP_LEVEL_KEYS = frozenset({
    "version", "name", "extends", "extends_hardened", "x-",
    "services", "networks", "volumes", "secrets", "configs",
    "agent", "agents", "compose", "depends_on",
    "healthcheck", "environment", "ports", "image", "container_name", "restart",
    "command", "build", "profiles", "labels", "logging", "driver", "driver_opts",
    "external", "ipam", "config", "mem_limit", "mem_reservation", "cpus", "cpuset",
    "shm_size", "user", "working_dir", "entrypoint", "stdin_open", "tty", "deploy",
    "pids_limit", "init", "privileged", "cap_add", "devices", "dns", "dns_search",
    "dns_opt", "extra_hosts", "links", "network_mode", "pid", "uts", "userns_mode",
    "volume_driver", "volumes_from", "stop_grace_period", "stop_signal", "domainname",
    "hostname", "platform", "runtime", "sysctls", "ulimits", "oom_score_adj",
    "swappiness",
})

DOCKERFILE_VARIANTS = ("Dockerfile", "Dockerfile.pmoves", "Dockerfile.amd")


def _overlay_short(path: Path) -> str:
    name = path.name
    name = name.removeprefix("docker-compose").removesuffix(".yml")
    name = name.lstrip(".").lstrip("-")
    return name or "main"


def _discover_real_services(repo_root: Path) -> dict:
    """Source A: every directory under services/ or integrations/ with a Dockerfile.

    Returns {canonical_name: {"directory": str, "dockerfile": str, "variants": list}}.
    Underscores in directory names are normalized to hyphens to match
    the convention used in compose files (e.g. botz_gateway -> botz-gateway).
    """
    roots = [repo_root / "pmoves" / "services", repo_root / "pmoves" / "integrations"]
    out: dict = {}
    for root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith((".", "_")):
                continue
            variants = [v for v in DOCKERFILE_VARIANTS if (child / v).exists()]
            if not variants:
                continue
            canonical = child.name.replace("_", "-")
            entry = {
                "directory": str(child.relative_to(repo_root)),
                "dockerfile": str((child / variants[0]).relative_to(repo_root)),
                "variants": variants,
                "roots": [str(root.relative_to(repo_root))],
            }
            existing = out.get(canonical)
            if existing:
                # merge variants, prefer the first
                for v in variants:
                    if v not in existing["variants"]:
                        existing["variants"].append(v)
                if root not in existing["roots"]:
                    existing["roots"].append(str(root.relative_to(repo_root)))
            else:
                out[canonical] = entry
    return out


def _discover_submodule_services(repo_root: Path) -> dict:
    """Source C: statically-declared submodule-resident services.

    Reads pmoves/configs/topology/submodule_services.yaml. Each entry
    becomes a matrix row with overlays populated from the entry's
    compose_overlays list (matched against the Source B overlay keys).
    """
    yaml_path = repo_root / "pmoves" / "configs" / "topology" / "submodule_services.yaml"
    if not yaml_path.exists():
        return {}
    import yaml
    with yaml_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or []
    if not isinstance(data, list):
        return {}
    out: dict = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        compose_keys = entry.get("compose_keys", []) or [name]
        compose_overlays = entry.get("compose_overlays", []) or []
        out[name] = {
            "compose_keys": compose_keys,
            "compose_overlays": compose_overlays,
            "source_repo": entry.get("source_repo"),
            "source_path": entry.get("source_path"),
            "directory": f"<submodule:{entry.get('source_repo','?')}>",
            "dockerfile": f"<submodule:{entry.get('source_repo','?')}>/{entry.get('source_path','Dockerfile')}",
            "variants": [entry.get("source_path", "Dockerfile")],
            "roots": ["pmoves/configs/topology"],
            "guard_paths": sorted(set(entry.get("guard_paths", []) or [])),
        }
    return out


def _collect_overlay_service_names(repo_root: Path) -> dict:
    """Source B: every service-name key from every compose overlay.

    Returns {overlay_short: {service_name: [path,...]}}. Service names
    include both canonical (hyphenated) and underscore-versions found in
    compose.
    """
    overlays = sorted(repo_root.glob("pmoves/docker-compose*.yml"))
    out: dict = {}
    for p in overlays:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        ov_short = _overlay_short(p)
        for m in re.finditer(r"^ {1,4}([a-z][a-z0-9_-]+):\s*$", text, re.MULTILINE):
            name = m.group(1)
            if name in KNOWN_TOP_LEVEL_KEYS:
                continue
            out.setdefault(ov_short, {}).setdefault(name, []).append(str(p))
    return out


def _build(repo_root: Path) -> tuple:
    real_services = _discover_real_services(repo_root)
    submodule_services = _discover_submodule_services(repo_root)
    real_services.update(submodule_services)
    overlays_by_name = _collect_overlay_service_names(repo_root)
    return real_services, overlays_by_name


def _match(real_name: str, real_entry: dict, compose_name: str) -> bool:
    """Match a compose-declared name to a real service.

    Rules:
      1. exact match (compose name == real name)
      2. underscore variant (compose name with '_' -> '-')
      3. substring: compose name endswith -realname OR realname endswith -composename
      4. directory basename substring
    """
    cn = compose_name.replace("_", "-")
    if cn == real_name:
        return True
    if compose_name == real_name.replace("-", "_"):
        return True
    if cn.endswith(real_name) or real_name.endswith(cn):
        return True
    # directory basename
    dir_base = real_entry["directory"].rsplit("/", 1)[-1].replace("_", "-")
    if compose_name == dir_base or compose_name.replace("_", "-") == dir_base:
        return True
    if compose_name.endswith(dir_base) or dir_base.endswith(compose_name):
        return True
    return False


def _emit(real_services: dict, overlays_by_name: dict) -> str:
    out: list = []
    out.append("# Docker Matrix - directory-first enumeration of real PMOVES services.")
    out.append("#")
    out.append("# Source A: every pmoves/services/ and pmoves/integrations/ directory")
    out.append("#   with a Dockerfile (any variant). The directory's basename is the")
    out.append("#   canonical service name (underscores normalized to hyphens).")
    out.append("# Source B: every service-name key from every pmoves/docker-compose*.yml")
    out.append("#   file, matched back to Source A by name/underscore/substring rules.")
    out.append("#")
    out.append("# The matrix is the static schema for the Known Roads provenance")
    out.append("# checker at pmoves/tools/topology/check_known_roads.py. Reason tokens")
    out.append("# are validated against the reference shape regexes in that script.")
    out.append("#")
    out.append("# Generated by: pmoves/tools/topology/build_docker_matrix.py")
    out.append("# Regen on compose or service-dir change.")
    out.append("#")
    out.append("version: '1.0'")
    out.append("generated_by: 'pmoves/tools/topology/build_docker_matrix.py'")
    out.append("source_a: 'directory walk under pmoves/services and pmoves/integrations'")
    out.append("source_b: 'top-level service-name keys in pmoves/docker-compose*.yml'")
    out.append("")
    out.append("known_road_domains:")
    out.append("  - compose")
    out.append("  - dockerfile")
    out.append("  - schema")
    out.append("  - topic")
    out.append("  - secrets")
    out.append("")

    # overlays block
    overlays = sorted(overlays_by_name.keys())
    out.append("overlays:")
    for ov in overlays:
        # path reconstruction: pick first overlay file in overlays_by_name[ov]
        first_path = next(iter(overlays_by_name[ov].values()), [])
        first = first_path[0] if first_path else f"pmoves/docker-compose.{ov}.yml"
        out.append(f"  - name: {ov}")
        out.append(f"    canonical_path: {first}")
    out.append("")

    # services block (Source A: every real service)
    out.append("services:")
    for name in sorted(real_services.keys()):
        entry = real_services[name]
        out.append(f"  - name: {name}")
        out.append(f"    directory: {entry['directory']}")
        out.append(f"    dockerfile: {entry['dockerfile']}")
        out.append("    dockerfile_variants:")
        for v in entry["variants"]:
            out.append(f"      - {v}")
        out.append("    roots:")
        for r in entry["roots"]:
            out.append(f"      - {r}")
        # find which overlays declare this service
        matched_overlays: list = []
        for ov, name_to_paths in overlays_by_name.items():
            for cn, paths in name_to_paths.items():
                if _match(name, entry, cn):
                    matched_overlays.append((ov, cn, paths))
        if matched_overlays:
            out.append("    overlays:")
            for ov, cn, paths in matched_overlays:
                out.append(f"      - overlay: {ov}")
                out.append(f"        compose_key: {cn}")
                out.append(f"        paths:")
                for p in sorted(set(paths)):
                    out.append(f"          - {p}")
        else:
            out.append("    overlays: []")
            out.append(f"    # NOTE: no compose overlay declares this service")
        # Source C: guard_paths (submodule-resident services declare exact paths)
        guard_paths = entry.get("guard_paths") or []
        if guard_paths:
            out.append("    guard_paths:")
            for gp in guard_paths:
                out.append(f"      - {gp}")
        else:
            out.append("    guard_paths: []")
        out.append("    known_road_domains:")
        for d in ("compose", "dockerfile", "schema", "topic"):
            out.append(f"      - {d}")
    out.append("")

    # unmapped_compose_keys block (Source B noise that didn't match Source A)
    out.append("# Compose keys that did NOT match any Source A service. These are")
    out.append("# typically sub-services (postgres/redis/worker siblings) or volume/")
    out.append("# network-name patterns. Listed here for visibility; the gate does")
    out.append("# not gate on them, but the operator can review for false negatives.")
    out.append("unmapped_compose_keys:")
    for ov in overlays:
        for cn in sorted(overlays_by_name[ov].keys()):
            matched_any = any(
                _match(name, real_services[name], cn)
                for name in real_services.keys()
            )
            if not matched_any:
                out.append(f"  - overlay: {ov}")
                out.append(f"    compose_key: {cn}")
                for p in sorted(set(overlays_by_name[ov][cn])):
                    out.append(f"    path: {p}")
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()

    real_services, overlays_by_name = _build(args.root)
    if not real_services:
        print(f"no real services found under services/ or integrations/", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(_emit(real_services, overlays_by_name), encoding="utf-8")
    print(f"wrote {args.out} ({len(real_services)} real services, {len(overlays_by_name)} overlays)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
