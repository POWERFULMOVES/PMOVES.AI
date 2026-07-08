#!/usr/bin/env python3
"""
Split pmoves/docker-compose.yml into logical overlay files (Rec #9).

Produces:
  - docker-compose.base.yml  — x-anchors, name, volumes, networks
  - docker-compose.core.yml   — Essential infrastructure services
  - docker-compose.agents.yml — Agent services
  - docker-compose.media.yml  — Media services
  - docker-compose.ui.yml     — UI services
  - docker-compose.workers.yml— Worker services
  - docker-compose.apps.yml   — Application services

Usage: docker compose -f docker-compose.base.yml -f docker-compose.core.yml up -d
"""

import sys
from pathlib import Path
from ruamel.yaml import YAML

# Service groupings
SERVICE_GROUPS = {
    "core": [
        "nats",
        "nats-init",
        # Supabase stack (13 services)
        "supabase-db",
        "supabase-gotrue",
        "supabase-realtime",
        "supabase-storage",
        "supabase-imgproxy",
        "supabase-meta",
        "supabase-kong",
        "supabase-edge-functions",
        "supabase-postgrest",
        "supabase-pooler",
        "supabase-analytics",
        "supabase-studio",
        "supabase-vector",
        # Data infrastructure
        "qdrant",
        "meilisearch",
        "neo4j",
        "minio",
        "tensorzero-clickhouse",
        "tensorzero-gateway",
        "tensorzero-ui",
        "cloudflared",
        "invidious-db",
    ],
    "agents": [
        "agent-zero",
        "archon",
        "gateway-agent",
        "hi-rag-gateway",
        "hi-rag-gateway-v2",
        "hi-rag-gateway-gpu",
        "hi-rag-gateway-v2-gpu",
        "mesh-agent",
        "cipher-api",
        "notebooklm-agent",
        "a2ui-nats-bridge",
        "nats-echo-req",
        "nats-echo-res",
        "consciousness-service",
        "evo-controller",
    ],
    "media": [
        "media-video",
        "media-audio",
        "ffmpeg-whisper",
        "transcribe-backend",
        "jellyfin-bridge",
        "ultimate-tts-studio",
        "flute-gateway",
        "cast-tts-gateway",
        "voice-relay",
        "bgutil-pot-provider",
        "pmoves-ollama",
        "nvidia-nim",
        "gpu-orchestrator",
        "llama-throughput-lab",
        "comfy-watcher",
    ],
    "ui": [
        "pmoves-ui",
        "tokenism-ui",
        "tokenism-simulator",
        "invidious",
        "invidious-companion",
        "invidious-companion-proxy",
        "grayjay-plugin-host",
        "grayjay-server",
    ],
    "workers": [
        "extract-worker",
        "spark-shape-worker",
        "pdf-ingest",
        "langextract",
        "notebook-sync",
        "session-context-worker",
        "deepresearch",
        "supaserch",
        "channel-monitor",
        "retrieval-eval",
        "publisher-discord",
        "model-registry",
        "presign",
        "render-webhook",
        "github-branch-cleanup",
        "github-issue-triage",
        "github-branch-naming",
        "github-crossrepo-sync",
        "github-crossrepo-pr",
        "github-runner-ctl",
    ],
    "apps": [
        "wger",
        "wger-db",
        "wger-nats-bridge",
        "botz-gateway",
        "pmoves-yt",
    ],
    "juicefs": [
        "juicefs-redis",
        "juicefs-format",
        "juicefs-gateway",
        "juicefs-smoke",
    ],
}

# All known services
ALL_KNOWN = []
for _g, _svcs in SERVICE_GROUPS.items():
    ALL_KNOWN.extend(_svcs)

OVERLAY_DESCRIPTIONS = {
    "core": "Essential Infrastructure",
    "agents": "Agent Services",
    "media": "Media Services",
    "ui": "UI Services",
    "workers": "Worker Services",
    "apps": "Applications",
    "juicefs": "JuiceFS Object Store (S3 gateway PoC)",
}


def make_header(name: str, desc: str) -> str:
    bar = "#" * 78
    return (
        f"{bar}\n"
        f"# PMOVES.AI - Docker Compose Overlay: {desc}\n"
        f"{bar}\n"
        f"# Services: {name} tier\n"
        f"# Always combine with base: docker compose -f docker-compose.base.yml -f docker-compose.{name}.yml up -d\n"
        f"#\n"
        f"# Generated from docker-compose.yml by scripts/split_compose.py\n"
        f"{bar}\n"
    )


def main():
    # Windows consoles default to cp1252 and choke on the ✓/✗ status glyphs
    # (and any non-ASCII in the compose file). Force UTF-8 stdout so a routine
    # regen / drift-check never crashes on encoding.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    compose_dir = Path(__file__).resolve().parent.parent
    src = compose_dir / "docker-compose.yml"

    if not src.exists():
        print(f"ERROR: {src} not found")
        sys.exit(1)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 200

    with open(src, encoding="utf-8") as f:
        data = yaml.load(f)

    services = data.get("services", {})

    # Validate all known services exist
    missing = [s for s in ALL_KNOWN if s not in services]
    if missing:
        print(f"WARNING: Services not found in docker-compose.yml: {missing}")

    # Check for ungrouped services
    ungrouped = [s for s in services if s not in ALL_KNOWN]
    if ungrouped:
        print(f"WARNING: Ungrouped services (adding to core): {ungrouped}")
        SERVICE_GROUPS["core"].extend(ungrouped)

    # ── Build docker-compose.base.yml ──
    base = yaml.map()
    for key in data:
        if key == "services":
            continue
        base[key] = data[key]

    base_header = (
        "#" + "=" * 77 + "\n"
        "# PMOVES.AI - Docker Compose Base (shared anchors, volumes, networks)\n"
        "#" + "=" * 77 + "\n"
        "# This file contains YAML anchors (x-env-tier-*, x-hardening-*),\n"
        "# shared volumes, and networks definitions used by all overlay files.\n"
        "#\n"
        "# Usage: docker compose \\\n"
        "#   -f docker-compose.base.yml \\\n"
        "#   -f docker-compose.core.yml \\\n"
        "#   -f docker-compose.agents.yml up -d\n"
        "#\n"
        "# Or use Makefile targets: make up-full, make up-core, etc.\n"
        "#\n"
        "# Generated from docker-compose.yml by scripts/split_compose.py\n"
        "#" + "=" * 77 + "\n"
    )

    base_path = compose_dir / "docker-compose.base.yml"
    with open(base_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(base_header)
        yaml.dump(base, f)
    svc_count = sum(len(v) for v in SERVICE_GROUPS.values())
    print(f"✓ docker-compose.base.yml (anchors + volumes + networks)")

    # ── Build overlay files ──
    total = 0
    for group_name, svc_names in SERVICE_GROUPS.items():
        overlay = yaml.map()
        overlay_services = yaml.map()
        for svc_name in svc_names:
            if svc_name in services:
                svc = services[svc_name]
                # Strip security_opt to prevent duplicate list items when
                # overlays are merged with docker-compose.yml (Compose v2
                # appends list items, causing rejection on duplicate entries).
                if 'security_opt' in svc:
                    svc = svc.copy()
                    del svc['security_opt']
                overlay_services[svc_name] = svc
                total += 1
            else:
                print(f"  WARNING: Service '{svc_name}' not found in source, skipping")
        overlay["services"] = overlay_services

        header = make_header(group_name, OVERLAY_DESCRIPTIONS[group_name])
        out_path = compose_dir / f"docker-compose.{group_name}.yml"
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(header)
            yaml.dump(overlay, f)
        print(f"✓ docker-compose.{group_name}.yml ({len(overlay_services)} services)")

    print(f"\nTotal services across overlays: {total}/{len(services)}")
    if total != len(services):
        print(f"WARNING: Service count mismatch! {len(services) - total} services missing.")
    else:
        print("All services accounted for.")

    # ── Validate YAML syntax ──
    print("\nValidating YAML syntax...")
    for fpath in sorted(compose_dir.glob("docker-compose.*.yml")):
        try:
            with open(fpath, encoding="utf-8") as f:
                yaml.load(f)
            print(f"  ✓ {fpath.name}")
        except Exception as e:
            print(f"  ✗ {fpath.name}: {e}")


if __name__ == "__main__":
    main()
