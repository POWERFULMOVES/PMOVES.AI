"""PMOVES Mini CLI – initial scaffolding."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import json
try:
    import typer
except ImportError as exc:
    print("Typer is required for pmoves mini CLI. Install via 'pip install typer[all]' or add to your environment.")
    raise SystemExit(1) from exc

from pmoves.tools import (
    automation_loader,
    crush_configurator,
    mcp_utils,
    onboarding_helper,
    profile_loader,
    secrets_sync,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVISIONING_SOURCE = REPO_ROOT / "pmoves" / "pmoves_provisioning_pr_pack"
DEFAULT_PROVISIONING_DEST = REPO_ROOT / "CATACLYSM_STUDIOS_INC" / "PMOVES-PROVISIONS"


app = typer.Typer(help="PMOVES mini CLI (alpha)")
secrets_app = typer.Typer(help="CHIT secret operations")
profile_app = typer.Typer(help="Hardware profile management")
mcp_app = typer.Typer(help="Manage MCP toolkits")
automations_app = typer.Typer(help="n8n automations")
crush_app = typer.Typer(help="Crush CLI integration")
app.add_typer(secrets_app, name="secrets")
app.add_typer(profile_app, name="profile")
app.add_typer(mcp_app, name="mcp")
app.add_typer(automations_app, name="automations")
app.add_typer(crush_app, name="crush")


def _default_manifest() -> Path:
    return REPO_ROOT / "pmoves/chit/secrets_manifest.yaml"


def _resolve_path(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return Path.cwd() / expanded


@app.command(help="Run onboarding helper (status or generate).")
def init(
    generate: bool = typer.Option(
        False, "--generate", "-g", help="Generate env files instead of status only."
    ),
    manifest: Optional[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Override secrets manifest path.",
    ),
) -> None:
    manifest_path = manifest or _default_manifest()
    if generate:
        exit_code = onboarding_helper.main(("generate", "--manifest", str(manifest_path)))
    else:
        exit_code = onboarding_helper.main(("status", "--manifest", str(manifest_path)))
    raise typer.Exit(exit_code)


@app.command("bootstrap", help="Bootstrap env files and stage provisioning bundle.")
def bootstrap(
    registry: Optional[Path] = typer.Option(
        None,
        "--registry",
        help="Custom bootstrap registry JSON (defaults to pmoves bootstrap registry).",
    ),
    service: Optional[List[str]] = typer.Option(
        None,
        "--service",
        "-s",
        help="Limit bootstrap to specific service id(s).",
    ),
    accept_defaults: bool = typer.Option(
        False,
        "--accept-defaults",
        help="Use registry defaults and generated values without prompting.",
    ),
    output: Path = typer.Option(
        DEFAULT_PROVISIONING_DEST,
        "--output",
        "-o",
        help="Destination directory for the provisioning bundle.",
    ),
) -> None:
    args: List[str] = []
    if registry is not None:
        args.extend(["--registry", str(registry)])
    for svc in service or []:
        args.extend(["--service", svc])
    if accept_defaults:
        args.append("--accept-defaults")

    exit_code = _run_module("pmoves.scripts.bootstrap_env", args)
    if exit_code != 0:
        raise typer.Exit(exit_code)

    destination = _resolve_path(output)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PROVISIONING_SOURCE, destination, dirs_exist_ok=True)
    except OSError as exc:  # pragma: no cover - error path
        typer.echo(f"Failed to stage provisioning bundle: {exc}")
        raise typer.Exit(1)

    typer.echo(f"Provisioning bundle staged to {destination}")


@app.command(help="Summarize current secret outputs (report).")
def status(
    manifest: Optional[Path] = typer.Option(
        None, "--manifest", "-m", help="Override secrets manifest path."
    ),
    provisioning_path: Path = typer.Option(
        DEFAULT_PROVISIONING_DEST,
        "--provisioning-path",
        help="Expected provisioning bundle directory.",
    ),
) -> None:
    manifest_path = manifest or _default_manifest()
    exit_code = secrets_sync.main(("report", "--manifest", str(manifest_path)))
    active = profile_loader.load_active_profile_id()
    if active:
        typer.echo(f"Active profile: {active}")
    else:
        typer.echo("Active profile: (none)")
    staging_root = _resolve_path(provisioning_path)
    wizard = staging_root / "scripts/install/wizard.sh"
    if wizard.exists():
        typer.echo(f"Provisioning bundle: ready ({wizard})")
    else:
        typer.echo(f"Provisioning bundle: missing (expected {wizard})")
    raise typer.Exit(exit_code)


def _run_module(module: str, args: list[str]) -> int:
    cmd = [sys.executable, "-m", module, *args]
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


@secrets_app.command("encode", help="Encode env to CHIT bundle.")
def secrets_encode(
    env_file: Path = typer.Option(
        Path("pmoves/env.shared"),
        "--env-file",
        "-e",
        help="Source env file to encode.",
    ),
    out: Path = typer.Option(
        Path("pmoves/pmoves/data/chit/env.cgp.json"),
        "--out",
        "-o",
        help="Output CGP path.",
    ),
    no_cleartext: bool = typer.Option(
        False,
        "--no-cleartext",
        help="Store secrets as base64 only.",
    ),
) -> None:
    args = ["--env-file", str(env_file), "--out", str(out)]
    if no_cleartext:
        args.append("--no-cleartext")
    exit_code = _run_module("pmoves.tools.chit_encode_secrets", args)
    raise typer.Exit(exit_code)


@secrets_app.command("decode", help="Decode CHIT bundle to env format.")
def secrets_decode(
    cgp: Path = typer.Option(
        Path("pmoves/pmoves/data/chit/env.cgp.json"),
        "--cgp",
        "-c",
        help="Input CGP file.",
    ),
    out: Path = typer.Option(
        Path("pmoves/pmoves/data/chit/env.decoded"),
        "--out",
        "-o",
        help="Output file for decoded env lines.",
    ),
) -> None:
    args = ["--cgp", str(cgp), "--out", str(out)]
    exit_code = _run_module("pmoves.tools.chit_decode_secrets", args)
    raise typer.Exit(exit_code)


@profile_app.command("list", help="List available hardware profiles.")
def profile_list() -> None:
    profiles = profile_loader.load_profiles()
    if not profiles:
        typer.echo("No profiles found.")
        raise typer.Exit(1)
    active = profile_loader.load_active_profile_id()
    for profile in profiles.values():
        marker = "*" if profile.id == active else " "
        typer.echo(f"{marker} {profile.id} – {profile.name}")


@profile_app.command("show", help="Show profile details.")
def profile_show(profile_id: str) -> None:
    profiles = profile_loader.load_profiles()
    profile = profiles.get(profile_id)
    if not profile:
        typer.echo(f"Profile '{profile_id}' not found.")
        raise typer.Exit(1)
    typer.echo(f"{profile.name} ({profile.id})")
    typer.echo(profile.description)
    typer.echo("")
    typer.echo("Hardware:")
    typer.echo(typer.style(json.dumps(profile.hardware, indent=2), fg=typer.colors.BLUE))
    typer.echo("Compose overrides: " + ", ".join(profile.compose_overrides or ["(none)"]))
    typer.echo("Model bundles: " + ", ".join(profile.model_bundles or ["(none)"]))
    typer.echo("MCP adapters: " + ", ".join(profile.mcp or ["(none)"]))
    if profile.notes:
        typer.echo("Notes:")
        for note in profile.notes:
            typer.echo(f"  - {note}")


@profile_app.command("detect", help="Suggest best matching profiles.")
def profile_detect(top: int = typer.Option(3, "--top", help="Number of suggestions to show.")) -> None:
    profiles = profile_loader.load_profiles().values()
    matches = profile_loader.detect_profiles(profiles)
    if not matches:
        typer.echo("No profile matches detected.")
        raise typer.Exit(1)
    for score, profile in matches[:top]:
        typer.echo(f"{profile.id} ({profile.name}) – score {score}")


@profile_app.command("apply", help="Set active profile.")
def profile_apply(profile_id: str) -> None:
    profiles = profile_loader.load_profiles()
    if profile_id not in profiles:
        typer.echo(f"Profile '{profile_id}' not found.")
        raise typer.Exit(1)
    profile_loader.save_active_profile(profile_id)
    typer.echo(f"Active profile set to {profile_id}.")


@profile_app.command("current", help="Display active profile.")
def profile_current() -> None:
    profiles = profile_loader.load_profiles()
    active_id = profile_loader.load_active_profile_id()
    if not active_id:
        typer.echo("No active profile set.")
        raise typer.Exit(1)
    profile = profiles.get(active_id)
    if not profile:
        typer.echo(f"Active profile '{active_id}' no longer exists.")
        raise typer.Exit(1)
    typer.echo(f"{profile.name} ({profile.id})")


@mcp_app.command("list", help="List configured MCP toolkits with availability.")
def mcp_list() -> None:
    tools = mcp_utils.load_mcp_tools()
    if not tools:
        typer.echo("No MCP tool definitions found.")
        raise typer.Exit(1)
    for tool in tools.values():
        checks = [
            cmd for cmd in tool.required_commands if not mcp_utils.command_available(cmd)
        ]
        status = "ready"
        if checks:
            status = f"missing commands: {', '.join(checks)}"
        typer.echo(f"{tool.id}: {tool.name} – {status}")


@mcp_app.command("health", help="Run MCP health checks.")
def mcp_health() -> None:
    tools = mcp_utils.load_mcp_tools()
    failed = []
    for tool in tools.values():
        ok = mcp_utils.run_health_check(tool)
        status = "ok" if ok else "failed"
        typer.echo(f"{tool.id}: {status}")
        if not ok:
            failed.append(tool.id)
    if failed:
        raise typer.Exit(1)


@mcp_app.command("setup", help="Show setup instructions for an MCP toolkit.")
def mcp_setup(tool_id: str) -> None:
    tools = mcp_utils.load_mcp_tools()
    tool = tools.get(tool_id)
    if not tool:
        typer.echo(f"MCP tool '{tool_id}' not found.")
        raise typer.Exit(1)
    typer.echo(f"{tool.name} ({tool.id}) setup checklist:")
    for step in tool.setup_instructions:
        typer.echo(f"  - {step}")


@automations_app.command("list", help="List n8n automations and channels.")
def automations_list() -> None:
    automations = automation_loader.load_automations()
    if not automations:
        typer.echo("No n8n flows found.")
        raise typer.Exit(1)
    for automation in automations.values():
        channels = ", ".join(automation.channels or ["general"])
        status = "active" if automation.active else "inactive"
        typer.echo(f"{automation.id}: {automation.name} [{status}] → {channels}")


@automations_app.command("webhooks", help="Show webhook endpoints.")
def automations_webhooks() -> None:
    automations = automation_loader.load_automations()
    total = 0
    for automation in automations.values():
        if not automation.webhooks:
            continue
        typer.echo(f"{automation.name}:")
        for hook in automation.webhooks:
            typer.echo(f"  - {hook.method} /{hook.path} ({hook.name})")
            total += 1
    if total == 0:
        typer.echo("No webhook nodes detected.")


@automations_app.command("channels", help="Filter automations by channel keyword.")
def automations_channels(channel: str) -> None:
    automations = automation_loader.load_automations()
    channel = channel.lower()
    matches = [
        automation
        for automation in automations.values()
        if channel in (automation.channels or [])
    ]
    if not matches:
        typer.echo(f"No automations tagged with '{channel}'.")
        raise typer.Exit(1)
    for automation in matches:
        typer.echo(f"{automation.id}: {automation.name}")


@crush_app.command("setup", help="Generate Crush configuration for PMOVES.")
def crush_setup(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Output path for crush.json (default: ~/.config/crush/crush.json)",
    ),
) -> None:
    target = path or crush_configurator.DEFAULT_CONFIG_PATH
    config_path, providers = crush_configurator.write_config(target)
    typer.echo(f"Wrote Crush config to {config_path}")
    typer.echo("Providers configured: " + ", ".join(sorted(providers.keys())))


@crush_app.command("status", help="Show Crush configuration details.")
def crush_status(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to crush.json (default: ~/.config/crush/crush.json)",
    ),
) -> None:
    target = path or crush_configurator.DEFAULT_CONFIG_PATH
    info = crush_configurator.config_status(target)
    typer.echo(f"Path: {info['path']}")
    typer.echo(f"Exists: {info['exists']}")
    providers = info.get("providers") or []
    typer.echo("Providers: " + (", ".join(providers) if providers else "(none)"))


@crush_app.command("preview", help="Print generated Crush configuration JSON.")
def crush_preview() -> None:
    config, providers = crush_configurator.build_config()
    typer.echo(json.dumps(config, indent=2))
    typer.echo("\nProviders: " + ", ".join(sorted(providers.keys())))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
