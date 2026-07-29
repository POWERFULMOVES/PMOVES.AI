"""One-shot generator for the 12 slice-4 curated pinokio-app entries.

Run from the worktree root:
    python pmoves/tools/pinokio_apps/_write_curated.py

Writes pmoves/configs/pinokio-apps/curated/<slug>.yaml for each of the
12 known apps, with a hand-tuned per-app network_exposure block.
"""
import os

ROOT = "pmoves/configs/pinokio-apps/curated"
os.makedirs(ROOT, exist_ok=True)

APPS = [
    {
        "slug": "comfyui-desktop", "title": "ComfyUI Desktop",
        "description": "Node-based Stable Diffusion / SDXL / Flux workflow runner (Gradio). The primary creator-collab rendering surface for image and video work.",
        "version_seen": "0.3.41", "tailscale_host": "powerfulmoves-1",
        "primary_port": 8188, "primary_protocol": "http", "health": "/system_stats",
        "launcher_script": "start.js", "autostart": True,
        "gpu_required": True, "min_vram_mb": 16384,
        "gpu_arch": ["sm_120", "sm_110"], "gpu_reservation_mb": 16384,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": True, "pinokio_skill_ref": None, "l4_public": True,
    },
    {
        "slug": "ace-step", "title": "ACE-Step Music",
        "description": "Music generation (lyrics + instrumental). Gradio. Concurrent with comfyui-desktop on a 32GB 5090.",
        "version_seen": "0.5.0", "tailscale_host": "powerfulmoves-1",
        "primary_port": 0, "primary_protocol": "http", "health": "/gradio_api/info",
        "launcher_script": "start.js", "autostart": True,
        "gpu_required": True, "min_vram_mb": 8192,
        "gpu_arch": ["sm_120", "sm_110"], "gpu_reservation_mb": 8192,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": True, "pinokio_skill_ref": None, "l4_public": False,
    },
    {
        "slug": "wan", "title": "Wan Video",
        "description": "Video generation (WanGP). On-demand only; 24GB exclusive claim goes to DGX Spark per the slice-1 review-iter-2 cycle-2 4-quadrant autostart x gpu_reservation_mode matrix.",
        "version_seen": "1.2.0", "tailscale_host": "powerfulmoves-1",
        "primary_port": 0, "primary_protocol": "http", "health": None,
        "launcher_script": "start.js", "autostart": False,
        "gpu_required": True, "min_vram_mb": 24000,
        "gpu_arch": ["sm_120", "sm_110", "sm_90"], "gpu_reservation_mb": 24000,
        "gpu_reservation_mode": "exclusive", "dependencies": [],
        "requires_hf_login": True, "pinokio_skill_ref": None, "l4_public": False,
    },
    {
        "slug": "lightonocr-2-1b", "title": "LightOnOCR 2.1B",
        "description": "Vision-language OCR. Small footprint (~2GB VRAM). Concurrently co-hosted with comfyui-desktop and ace-step on a 32GB 5090.",
        "version_seen": "0.1.4", "tailscale_host": "powerfulmoves-1",
        "primary_port": 0, "primary_protocol": "http", "health": "/gradio_api/info",
        "launcher_script": "start.js", "autostart": True,
        "gpu_required": True, "min_vram_mb": 2048,
        "gpu_arch": ["sm_120", "sm_110", "sm_89"], "gpu_reservation_mb": 2048,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": True, "pinokio_skill_ref": None, "l4_public": False,
    },
    {
        "slug": "ultimate-tts-studio", "title": "Ultimate TTS Studio",
        "description": "14-engine TTS hub (Gradio). Always-on baseline voice surface on the 5090.",
        "version_seen": "3.1.7", "tailscale_host": "powerfulmoves-1",
        "primary_port": 7860, "primary_protocol": "http", "health": "/gradio_api/info",
        "launcher_script": "start.js", "autostart": True,
        "gpu_required": True, "min_vram_mb": 6144,
        "gpu_arch": ["sm_120", "sm_110"], "gpu_reservation_mb": 6144,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": True, "pinokio_skill_ref": None, "l4_public": True,
    },
    {
        "slug": "qwen3-tts", "title": "Qwen3 TTS",
        "description": "Qwen3 standalone TTS with VoiceDesign mode. On-demand; launched by the helpdesk-skill (slice 6) or the creator-canvas-primary surface.",
        "version_seen": "0.6.2", "tailscale_host": "powerfulmoves-1",
        "primary_port": 0, "primary_protocol": "http", "health": "/gradio_api/info",
        "launcher_script": "start.js", "autostart": False,
        "gpu_required": True, "min_vram_mb": 4096,
        "gpu_arch": ["sm_120", "sm_110"], "gpu_reservation_mb": 4096,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": True, "pinokio_skill_ref": None, "l4_public": False,
    },
    {
        "slug": "vibevoice-realtime", "title": "VibeVoice Realtime",
        "description": "WebSocket streaming TTS (uvicorn). On-demand; the realtime voice lane prefers this over Ultimate-TTS-Studio when latency matters.",
        "version_seen": "0.3.0", "tailscale_host": "powerfulmoves-1",
        "primary_port": 0, "primary_protocol": "ws", "health": None,
        "launcher_script": "start.js", "autostart": False,
        "gpu_required": True, "min_vram_mb": 4096,
        "gpu_arch": ["sm_120", "sm_110"], "gpu_reservation_mb": 4096,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": True, "pinokio_skill_ref": None, "l4_public": False,
    },
    {
        "slug": "voxforge-pro", "title": "VoxForge Pro",
        "description": "PDF-to-audiobook pipeline. On-demand; the long-form voice lane. Bookmarks + chapter splits live in the Gradio UI.",
        "version_seen": "1.0.2", "tailscale_host": "powerfulmoves-1",
        "primary_port": 0, "primary_protocol": "http", "health": "/gradio_api/info",
        "launcher_script": "start.js", "autostart": False,
        "gpu_required": True, "min_vram_mb": 4096,
        "gpu_arch": ["sm_120", "sm_110"], "gpu_reservation_mb": 4096,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": True, "pinokio_skill_ref": None, "l4_public": False,
    },
    {
        "slug": "n8n", "title": "n8n Workflow Automation",
        "description": "n8n workflow engine. CPU-only. Always-on baseline on the 5090; bridges to NATS via webhook nodes for PMOVES event flow.",
        "version_seen": "1.45.1", "tailscale_host": "powerfulmoves-1",
        "primary_port": 0, "primary_protocol": "http", "health": "/healthz",
        "launcher_script": "start.js", "autostart": True,
        "gpu_required": False, "min_vram_mb": 0,
        "gpu_arch": [], "gpu_reservation_mb": 0,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": False, "pinokio_skill_ref": None, "l4_public": False,
    },
    {
        "slug": "sillytavern", "title": "SillyTavern",
        "description": "Chat UI for local LLMs. On-demand; pairs with Ollama on the same node.",
        "version_seen": "1.12.7", "tailscale_host": "powerfulmoves-1",
        "primary_port": 0, "primary_protocol": "http", "health": None,
        "launcher_script": "start.js", "autostart": False,
        "gpu_required": True, "min_vram_mb": 4096,
        "gpu_arch": ["sm_120", "sm_110"], "gpu_reservation_mb": 4096,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": False, "pinokio_skill_ref": None, "l4_public": False,
    },
    {
        "slug": "unsloth", "title": "Unsloth LLM Training",
        "description": "LLM fine-tuning (Unsloth). On-demand only; 24GB exclusive claim goes to DGX Spark for the actual training runs.",
        "version_seen": "2024.10", "tailscale_host": "powerfulmoves-1",
        "primary_port": 0, "primary_protocol": "http", "health": None,
        "launcher_script": "start.js", "autostart": False,
        "gpu_required": True, "min_vram_mb": 24000,
        "gpu_arch": ["sm_120", "sm_110", "sm_90"], "gpu_reservation_mb": 24000,
        "gpu_reservation_mode": "exclusive", "dependencies": [],
        "requires_hf_login": True, "pinokio_skill_ref": None, "l4_public": False,
    },
    {
        "slug": "customokio", "title": "CustomOkio Scaffold",
        "description": "PMOVES-side scaffold for new Pinokio launchers (gepeto output). No runtime cost; lives in the registry so creator-studio smoke can reference it as the launchers-author target.",
        "version_seen": "0.1.0", "tailscale_host": "pmoves-z890",
        "primary_port": 0, "primary_protocol": "http", "health": None,
        "launcher_script": "pinokio.js", "autostart": False,
        "gpu_required": False, "min_vram_mb": 0,
        "gpu_arch": [], "gpu_reservation_mb": 0,
        "gpu_reservation_mode": "concurrent", "dependencies": [],
        "requires_hf_login": False, "pinokio_skill_ref": None, "l4_public": False,
    },
]


def render(app):
    """Render one app entry as clean YAML (no textwrap gymnastics)."""
    port_line = f"port: {app['primary_port']}" if app['primary_port'] else "port: 0  # dynamic, resolved via pinokio_bridge /v1/apps/{slug}/status"
    health_line = f'health: "{app["health"]}"' if app["health"] else "health: null"
    gpu_arch = "[" + ", ".join(app["gpu_arch"]) + "]" if app["gpu_arch"] else "[]"
    deps = "[" + ", ".join(app["dependencies"]) + "]" if app["dependencies"] else "[]"
    skill = f'"{app["pinokio_skill_ref"]}"' if app["pinokio_skill_ref"] else "null"

    # L2/L3 address: null when port is 0 (dynamic); the consumer (mesh_exposure
    # service) reads the actual port from pinokio_bridge at runtime.
    if app["primary_port"] == 0:
        l2_addr = "null"
        l3_addr = "null"
    else:
        l2_addr = f'"http://host.docker.internal:{app["primary_port"]}"'
        l3_addr = f'"http://{app["slug"]}.{app["tailscale_host"]}.ts.pmoves.net:{app["primary_port"]}"'
    l3_ports = "[]" if app["primary_port"] == 0 else f"[{app['primary_port']}]"

    if app["l4_public"]:
        l4_block = (
            f"    reachable: true\n"
            f"    tunnel: pmoves-edge\n"
            f"    dns_record: {app['slug']}.pmoves.ai\n"
            f"    public_url: https://{app['slug']}.pmoves.ai"
        )
    else:
        l4_block = (
            f"    reachable: false\n"
            f"    tunnel: null\n"
            f"    dns_record: null\n"
            f"    public_url: null"
        )

    lines = [
        'schema_version: "1.0.0"',
        f"slug: {app['slug']}",
        f'title: "{app["title"]}"',
        f'description: "{app["description"]}"',
        "owner: pinokio",
        f'version_seen: "{app["version_seen"]}"',
        "runtime:",
        f"  launcher_script: {app['launcher_script']}",
        f"  autostart: {str(app['autostart']).lower()}",
        f"  gpu_required: {str(app['gpu_required']).lower()}",
        f"  min_vram_mb: {app['min_vram_mb']}",
        f"  gpu_arch: {gpu_arch}",
        f"  gpu_reservation_mb: {app['gpu_reservation_mb']}",
        f"  gpu_reservation_mode: {app['gpu_reservation_mode']}",
        f"  dependencies: {deps}",
        f"  requires_hf_login: {str(app['requires_hf_login']).lower()}",
        "endpoints:",
        "  primary:",
        f"    {port_line}",
        f"    protocol: {app['primary_protocol']}",
        f"    {health_line}",
        "  alt: []",
        f"pinokio_skill_ref: {skill}",
        "network_exposure:",
        "  l1_venv:",
        "    reachable: true",
        "  l2_container_same_host:",
        "    reachable: true",
        f"    address: {l2_addr}",
        "  l3_mesh:",
        "    reachable: true",
        f"    address: {l3_addr}",
        f"    headscale_acl_ports: {l3_ports}",
        "    tags_required: []",
        "  l4_public:",
        l4_block,
        "notes:",
        f'  - "node tailscale_host={app["tailscale_host"]}; runtime facts from slice-1 review-iter-2 cycle-2 record"',
        '  - "mesh_exposure (slice 4) reconciles L3 ACL ports + L4 tunnel + L4 DNS from this entry"',
        "",
    ]
    return "\n".join(lines)


for app in APPS:
    out = os.path.join(ROOT, f"{app['slug']}.yaml")
    with open(out, "w") as f:
        f.write(render(app))
    print("wrote", out)

print(f"\n{len(APPS)} curated entries written to {ROOT}/")
