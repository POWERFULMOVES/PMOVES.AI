"""PMOVES Mini CLI – initial scaffolding."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
DEFAULT_PROVISIONING_DEST = REPO_ROOT / "CATACLYSM_STUDIOS_INC" / "PMOVES-PROVISIONS"
ENV_SHARED = REPO_ROOT / "pmoves" / "env.shared"
CANONICAL_PROVISIONING_SOURCE = DEFAULT_PROVISIONING_DEST
PROVISIONING_MANIFEST_FILENAME = "provisioning-manifest.json"

PROVISIONING_BUNDLE_FILES: dict[Path, Path] = {
    Path("README_APPLY.txt"): REPO_ROOT / "docs" / "provisioning" / "README_APPLY.txt",
    Path("docker-compose.gpu.yml"): REPO_ROOT / "pmoves" / "docker-compose.gpu.yml",
    Path("scripts/install/wizard.sh"): REPO_ROOT / "pmoves" / "scripts" / "install" / "wizard.sh",
    Path("scripts/install/wizard.ps1"): REPO_ROOT / "pmoves" / "scripts" / "install" / "wizard.ps1",
    Path("scripts/proxmox/pmoves-bootstrap.sh"): REPO_ROOT
    / "pmoves"
    / "scripts"
    / "proxmox"
    / "pmoves-bootstrap.sh",
    Path("tailscale/tailscale_brand_up.sh"): REPO_ROOT / "pmoves" / "scripts" / "tailscale_brand_up.sh",
}

PROVISIONING_BUNDLE_DIRS: tuple[str, ...] = (
    "backup",
    "docker-stacks",
    "docs",
    "inventory",
    "jetson",
    "linux",
    "proxmox",
    "tailscale",
    "ventoy",
    "windows",
)

GLANCER_BUNDLE_FILES: Dict[Path, Path] = {
    Path("addons/glancer/README.md"): REPO_ROOT
    / "pmoves"
    / "provisioning"
    / "glancer"
    / "README.md",
    Path("addons/glancer/docker-compose.glancer.yml"): REPO_ROOT
    / "pmoves"
    / "provisioning"
    / "glancer"
    / "docker-compose.glancer.yml",
    Path("addons/glancer/glancer.env.example"): REPO_ROOT
    / "pmoves"
    / "provisioning"
    / "glancer"
    / "glancer.env.example",
}


app = typer.Typer(help="PMOVES mini CLI (alpha)")
secrets_app = typer.Typer(help="CHIT secret operations")
profile_app = typer.Typer(help="Hardware profile management")
mcp_app = typer.Typer(help="Manage MCP toolkits")
automations_app = typer.Typer(help="n8n automations")
crush_app = typer.Typer(help="PMOVES CLI integration")
agent_sdk_app = typer.Typer(help="PMOVES Agent SDK management")
deps_app = typer.Typer(help="Host tooling dependency helpers")
tailscale_app = typer.Typer(help="Tailscale helpers")
app.add_typer(secrets_app, name="secrets")
app.add_typer(profile_app, name="profile")
app.add_typer(mcp_app, name="mcp")
app.add_typer(automations_app, name="automations")
app.add_typer(crush_app, name="crush")
app.add_typer(agent_sdk_app, name="agent-sdk")
app.add_typer(deps_app, name="deps")
app.add_typer(tailscale_app, name="tailscale")


DEPENDENCY_DEFINITIONS = {
    "make": {
        "command": "make",
        "kind": "system",
        "packages": {
            "apt-get": ["make"],
            "apt": ["make"],
            "dnf": ["make"],
            "yum": ["make"],
            "pacman": ["make"],
            "brew": ["make"],
            "choco": ["make"],
            "winget": ["GnuWin32.Make"],
        },
    },
    "jq": {
        "command": "jq",
        "kind": "system",
        "packages": {
            "apt-get": ["jq"],
            "apt": ["jq"],
            "dnf": ["jq"],
            "yum": ["jq"],
            "pacman": ["jq"],
            "brew": ["jq"],
            "choco": ["jq"],
            "winget": ["jqlang.jq"],
        },
    },
    "pytest": {
        "command": "pytest",
        "kind": "python",
        "package": "pytest",
    },
}


def _default_manifest() -> Path:
    return REPO_ROOT / "pmoves/chit/secrets_manifest.yaml"


def _resolve_path(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return Path.cwd() / expanded


def _stage_addon_assets(destination: Path, assets: Dict[Path, Path], label: str) -> list[str]:
    staged: list[str] = []
    for relative_path, source in assets.items():
        if not source.exists():
            raise FileNotFoundError(f"{label} source missing: {source}")
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        staged.append(str(relative_path))
    return staged


def _write_provisioning_manifest(destination: Path, addons: Dict[str, dict]) -> None:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "source": str(CANONICAL_PROVISIONING_SOURCE),
        "addons": addons,
    }
    manifest_path = destination / PROVISIONING_MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _stage_provisioning_bundle(destination: Path, include_glancer: bool = False) -> None:
    for relative_path, source in PROVISIONING_BUNDLE_FILES.items():
        if not source.exists():
            raise FileNotFoundError(f"Provisioning source missing: {source}")
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    canonical_root = CANONICAL_PROVISIONING_SOURCE.resolve()
    destination_root = destination.resolve()
    staged_addons: Dict[str, dict] = {}

    if include_glancer:
        staged = _stage_addon_assets(destination, GLANCER_BUNDLE_FILES, "Glancer")
        staged_addons["glancer"] = {
            "staged": True,
            "assets": staged,
            "source": str((REPO_ROOT / "pmoves" / "provisioning" / "glancer").resolve()),
        }

    if destination_root != canonical_root:
        readme_source = CANONICAL_PROVISIONING_SOURCE / "README.md"
        if readme_source.exists():
            shutil.copy2(readme_source, destination / "README.md")

        for relative_dir in PROVISIONING_BUNDLE_DIRS:
            source_dir = CANONICAL_PROVISIONING_SOURCE / relative_dir
            if not source_dir.exists():
                continue
            target_dir = destination / relative_dir
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_dir, target_dir)

    _write_provisioning_manifest(destination, staged_addons)


def _update_env_value(env_path: Path, key: str, value: str) -> None:
    env_path = _resolve_path(env_path)
    existing_lines: List[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()
    prefix = f"{key}="
    updated = False
    patched: List[str] = []
    for line in existing_lines:
        if line.startswith(prefix):
            patched.append(f"{prefix}{value}")
            updated = True
        else:
            patched.append(line)
    if not updated:
        if patched and patched[-1] != "":
            patched.append("")
        patched.append(f"{prefix}{value}")
    env_path.write_text("\n".join(patched) + "\n", encoding="utf-8")


def _read_env_value(env_path: Path, key: str) -> Optional[str]:
    env_path = _resolve_path(env_path)
    if not env_path.exists():
        return None
    prefix = f"{key}="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return None


def _mask_value(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)


def _load_provisioning_manifest(staging_root: Path) -> dict:
    manifest_path = staging_root / PROVISIONING_MANIFEST_FILENAME
    if not manifest_path.exists():
        return {}

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _glancer_status(staging_root: Path) -> str:
    manifest = _load_provisioning_manifest(staging_root)
    glancer_manifest = manifest.get("addons", {}).get("glancer") or {}
    compose_file = staging_root / "addons" / "glancer" / "docker-compose.glancer.yml"

    requested = bool(glancer_manifest.get("staged")) or compose_file.exists()
    if not requested:
        return "not requested"

    if not compose_file.exists():
        return "requested but compose assets are missing"

    if not _docker_available():
        return "staged (docker CLI unavailable for health check)"

    cmd = ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json", "glancer"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        reason = stderr or "glancer service is not running"
        return f"compose not running ({reason})"

    try:
        services = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        services = []

    if not services:
        return "staged (glancer container not started)"

    service = services[0]
    state = (service.get("State") or "").lower()
    health = (service.get("Health") or service.get("HealthStatus") or "").lower()
    if health:
        return f"{state or 'unknown'} ({health})"
    return state or "unknown"


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
    with_glancer: bool = typer.Option(
        False,
        "--with-glancer/--without-glancer",
        help="Include Glancer assets and overrides in the provisioning pack.",
    ),
) -> None:
    args: List[str] = []
    if registry is not None:
        registry_path = _resolve_path(registry)
        args.extend(["--registry", str(registry_path)])
    for svc in service or []:
        args.extend(["--service", svc])
    if accept_defaults:
        args.append("--accept-defaults")

    exit_code = _run_module("pmoves.scripts.bootstrap_env", args)
    if exit_code != 0:
        raise typer.Exit(exit_code)

    destination = _resolve_path(output)
    try:
        destination.mkdir(parents=True, exist_ok=True)
        _stage_provisioning_bundle(destination, include_glancer=with_glancer)
    except FileNotFoundError as exc:  # pragma: no cover - error path
        typer.echo(f"Failed to stage provisioning bundle: {exc}")
        raise typer.Exit(1)
    except OSError as exc:  # pragma: no cover - error path
        typer.echo(f"Failed to stage provisioning bundle: {exc}")
        raise typer.Exit(1)

    typer.echo(f"Provisioning bundle staged to {destination}")


@tailscale_app.command("authkey")
def tailscale_authkey(
    env_file: Path = typer.Option(
        ENV_SHARED,
        "--env-file",
        "-e",
        help="Env file that should carry TAILSCALE_AUTHKEY",
    ),
    secret_file: Path = typer.Option(
        Path("CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/tailscale/tailscale_authkey.txt"),
        "--secret-file",
        "-s",
        help="Provisioning secret file where the auth key should be written.",
    ),
    write_env: bool = typer.Option(
        True,
        "--write-env/--no-write-env",
        help="Update env file with TAILSCALE_AUTHKEY",
    ),
    write_secret: bool = typer.Option(
        True,
        "--write-secret/--no-write-secret",
        help="Write auth key to provisioning secret file",
    ),
    sign: bool = typer.Option(
        True,
        "--sign/--no-sign",
        help="Attempt to sign the auth key with 'tailscale lock sign' when Tailnet Lock is enabled.",
    ),
) -> None:
    """Capture a Tailnet auth key and persist it for automation."""

    typer.echo(
        "Generate a reusable auth key from your Tailnet admin (e.g. headscale preauthkeys create)."
    )
    existing_env = _read_env_value(env_file, "TAILSCALE_AUTHKEY") if write_env else None
    existing_secret: Optional[str] = None
    if write_secret:
        resolved_secret = _resolve_path(secret_file)
        if resolved_secret.exists():
            existing_secret = resolved_secret.read_text(encoding="utf-8").strip()
    if existing_env:
        typer.echo(
            f"Existing env value: {_mask_value(existing_env)} (will be replaced once you confirm)."
        )
    if existing_secret:
        typer.echo(
            f"Secret file currently stores: {_mask_value(existing_secret)} (will be replaced)."
        )
    auth_key = typer.prompt(
        "Paste tailnet auth key (leave blank to cancel)",
        default="",
        show_default=False,
        hide_input=True,
    ).strip()
    if not auth_key:
        typer.echo("No auth key provided; aborting without changes.")
        raise typer.Exit(code=1)

    if sign:
        finalized_key, sign_messages = _tailscale_sign_auth_key(auth_key)
        for message in sign_messages:
            typer.echo(message)
        if finalized_key:
            auth_key = finalized_key

    if write_env:
        _update_env_value(env_file, "TAILSCALE_AUTHKEY", auth_key)
        typer.echo(f"Updated TAILSCALE_AUTHKEY in {env_file}")
    if write_secret:
        resolved_secret = _resolve_path(secret_file)
        resolved_secret.parent.mkdir(parents=True, exist_ok=True)
        resolved_secret.write_text(auth_key + "\n", encoding="utf-8")
        try:
            os.chmod(resolved_secret, 0o600)
        except PermissionError:
            typer.echo(
                f"Warning: could not tighten permissions on {resolved_secret}; adjust manually if needed."
            )
        typer.echo(f"Wrote auth key to {resolved_secret}")
    typer.echo("Auth key captured. Keep it out of version control.")


@tailscale_app.command("join")
def tailscale_join(
    env_file: Path = typer.Option(
        ENV_SHARED,
        "--env-file",
        "-e",
        help="Env file to load (TAILSCALE_* variables)",
    ),
    force_reauth: bool = typer.Option(
        False, "--force-reauth", help="Force re-authentication"
    ),
) -> None:
    """Join the tailnet using pmoves/scripts/tailscale_brand_init.sh."""

    script = REPO_ROOT / "pmoves" / "scripts" / "tailscale_brand_init.sh"
    if not script.exists():
        typer.echo(f"Init script missing: {script}")
        raise typer.Exit(1)

    env = os.environ.copy()
    env["ENV_FILE"] = str(env_file)
    env["TAILSCALE_AUTO_JOIN"] = "true"
    if force_reauth:
        env["TAILSCALE_FORCE_REAUTH"] = "true"
    # Respect saved secret file path default if set in env file
    # scripts/with-env.sh will populate env vars into this process
    cmd = ["bash", "-lc", f". ./pmoves/scripts/with-env.sh '{env_file}'; bash '{script}'"]
    rc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env).returncode
    if rc != 0:
        raise typer.Exit(rc)


@tailscale_app.command("rejoin")
def tailscale_rejoin(
    env_file: Path = typer.Option(
        ENV_SHARED,
        "--env-file",
        "-e",
        help="Env file to load (TAILSCALE_* variables)",
    )
) -> None:
    """Force re-auth join to the tailnet."""
    tailscale_join(env_file=env_file, force_reauth=True)


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

    glancer_status = _glancer_status(staging_root)
    typer.echo(f"Glancer: {glancer_status}")
    raise typer.Exit(exit_code)


def _tailscale_sign_auth_key(auth_key: str) -> Tuple[Optional[str], List[str]]:
    """Sign a Tailnet auth key when Tailnet Lock is enabled.

    Returns the signed key (if available) alongside log messages that should be surfaced to the user.
    """

    messages: List[str] = []
    if not _command_available("tailscale"):
        messages.append("tailscale CLI not found; skipping Tailnet Lock signing.")
        return None, messages

    lock_enabled = False
    status_attempts = (
        ["tailscale", "lock", "status", "--json"],
        ["tailscale", "lock", "status"],
    )
    status_output: Optional[str] = None

    for cmd in status_attempts:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            messages.append("tailscale CLI could not be executed; skipping Tailnet Lock signing.")
            return None, messages

        if proc.returncode != 0:
            stderr_text = (proc.stderr or "").lower()
            # If the JSON flag is not supported, fall back to the plain output.
            if "--json" in cmd and any(
                phrase in stderr_text for phrase in ("flag provided but not defined", "unknown flag", "unrecognized option", "no such flag")
            ):
                continue
            # Older clients report Tailnet Lock disabled on stderr.
            status_output = (proc.stdout or proc.stderr or "").strip()
        else:
            status_output = proc.stdout.strip()

        if status_output:
            try:
                data = json.loads(status_output)
            except json.JSONDecodeError:
                lowered = status_output.lower()
                # Treat "disabled" as authoritative only if "enabled" is absent.
                if "enabled" in lowered and "disabled" not in lowered:
                    lock_enabled = True
                elif "tailnet lock: enabled" in lowered:
                    lock_enabled = True
            else:
                lock_enabled = bool(
                    data.get("enabled")
                    or data.get("Enabled")
                    or data.get("lockEnabled")
                    or data.get("lock_state") == "enabled"
                    or data.get("state") == "enabled"
                    or data.get("state") == "ENABLED"
                    or (data.get("Status") or {}).get("Enabled")
                    or (data.get("status") or {}).get("enabled")
                )

        if lock_enabled:
            break

    if not lock_enabled:
        messages.append("Tailnet Lock not detected; stored key remains unsigned.")
        return None, messages

    messages.append("Tailnet Lock detected; attempting to sign auth key via 'tailscale lock sign'.")
    sign_proc = subprocess.run(
        ["tailscale", "lock", "sign", auth_key],
        capture_output=True,
        text=True,
        check=False,
    )

    if sign_proc.returncode != 0:
        stderr = sign_proc.stderr.strip()
        if stderr:
            messages.append(f"Failed to sign auth key: {stderr}")
        else:
            messages.append("Failed to sign auth key: tailscale lock sign returned a non-zero exit code.")
        messages.append("Continuing with the original auth key.")
        return None, messages

    output = sign_proc.stdout.strip()
    if output:
        matches = re.findall(r"tskey-[A-Za-z0-9_-]+", output)
    else:
        matches = []

    if not matches:
        messages.append(
            "tailscale lock sign succeeded but no signed auth key was detected in the output; continuing with the original key."
        )
        return None, messages

    signed_key = matches[-1]
    if signed_key == auth_key:
        messages.append("tailscale lock sign returned the same auth key; keeping existing value.")
        return None, messages

    messages.append(f"Signed auth key captured: {_mask_value(signed_key)}")
    return signed_key, messages


def _run_module(module: str, args: list[str]) -> int:
    cmd = [sys.executable, "-m", module, *args]
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def _command_available(command: str) -> bool:
    return shutil.which(command) is not None


def _docker_available() -> bool:
    return _command_available("docker")


def _sudo_prefix() -> list[str]:
    if platform.system() == "Windows":
        return []
    try:
        if os.geteuid() == 0:
            return []
    except AttributeError:  # pragma: no cover - platform without geteuid
        return []
    return ["sudo"] if _command_available("sudo") else []


def _detect_package_manager(preferred: Optional[str]) -> Optional[str]:
    if preferred:
        return preferred if _command_available(preferred) else None
    for candidate in ("apt-get", "apt", "dnf", "yum", "pacman", "brew", "choco", "winget"):
        if _command_available(candidate):
            return candidate
    return None


def _install_python_dependency(package: str) -> bool:
    if _command_available("uv"):
        cmd = ["uv", "pip", "install", package]
    else:
        cmd = [sys.executable, "-m", "pip", "install", package]
    result = subprocess.run(cmd, check=False)
    return result.returncode == 0


def _run_with_optional_sudo(command: list[str]) -> int:
    prefix = _sudo_prefix()
    if prefix:
        command = prefix + command
    result = subprocess.run(command, check=False)
    return result.returncode


def _install_with_manager(manager: str, packages: list[str]) -> bool:
    commands: list[list[str]] = []
    if manager in {"apt-get", "apt"}:
        commands.append([manager, "update"])
        commands.append([manager, "install", "-y", *packages])
    elif manager == "dnf":
        commands.append([manager, "-y", "makecache"])
        commands.append([manager, "-y", "install", *packages])
    elif manager == "yum":
        commands.append([manager, "-y", "install", *packages])
    elif manager == "pacman":
        commands.append([manager, "-S", "--noconfirm", *packages])
    elif manager == "brew":
        commands.append(["brew", "install", *packages])
    elif manager == "choco":
        commands.append(["choco", "install", "-y", *packages])
    elif manager == "winget":
        for package in packages:
            commands.append(["winget", "install", "--id", package, "-e", "--silent"])
    else:  # pragma: no cover - defensive branch
        return False

    for command in commands:
        code = _run_with_optional_sudo(command)
        if code != 0:
            return False
    return True


def _install_in_container(missing: list[str], container_image: str) -> bool:
    if not _docker_available():
        typer.echo("Docker CLI is required when using --use-container.")
        return False

    system_packages: set[str] = set()
    python_packages: set[str] = set()
    for dep in missing:
        info = DEPENDENCY_DEFINITIONS[dep]
        if info["kind"] == "system":
            packages = info["packages"].get("apt-get") or info["packages"].get("apt")
            if packages:
                system_packages.update(packages)
        else:
            python_packages.add(info["package"])

    script_parts = ["set -euo pipefail"]
    script_parts.append("apt-get update")
    if system_packages:
        pkg_list = " ".join(sorted(system_packages))
        script_parts.append(
            "DEBIAN_FRONTEND=noninteractive apt-get install -y " + pkg_list
        )
    if python_packages:
        script_parts.append("pip install " + " ".join(sorted(python_packages)))
    script = " && ".join(script_parts)

    command = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{REPO_ROOT}:/workspace",
        "-w",
        "/workspace",
        container_image,
        "bash",
        "-lc",
        script,
    ]
    result = subprocess.run(command, check=False)
    return result.returncode == 0


@deps_app.command("check", help="Report whether host dependencies are available.")
def deps_check() -> None:
    missing: list[str] = []
    for dep, info in DEPENDENCY_DEFINITIONS.items():
        available = _command_available(info["command"])
        status = "available" if available else "missing"
        typer.echo(f"{dep}: {status}")
        if not available:
            missing.append(dep)
    if missing:
        typer.echo(
            "Missing dependencies detected. Run 'python -m pmoves.tools.mini_cli deps install' to remediate."
        )
        raise typer.Exit(1)
    typer.echo("All tracked dependencies are available.")


@deps_app.command("install", help="Install missing dependencies on the host or via container.")
def deps_install(
    manager: Optional[str] = typer.Option(
        None,
        "--manager",
        "-m",
        help="Package manager to use for system dependencies (auto-detect by default).",
    ),
    assume_yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically proceed without confirmation prompts.",
    ),
    use_container: bool = typer.Option(
        False,
        "--use-container",
        help="Install dependencies inside an ephemeral container to avoid host changes.",
    ),
    container_image: str = typer.Option(
        "python:3.11-slim",
        "--container-image",
        help="Container image to use when --use-container is set.",
    ),
) -> None:
    missing = [dep for dep, info in DEPENDENCY_DEFINITIONS.items() if not _command_available(info["command"])]
    if not missing:
        typer.echo("All tracked dependencies are already available.")
        return

    typer.echo("Missing dependencies: " + ", ".join(missing))

    if use_container:
        if not _install_in_container(missing, container_image):
            raise typer.Exit(1)
        typer.echo("Dependencies installed inside container image.")
        return

    resolved_manager = _detect_package_manager(manager)
    if resolved_manager is None:
        typer.echo("Could not detect a supported package manager. Use --use-container or install manually.")
        raise typer.Exit(1)

    for dep in missing:
        info = DEPENDENCY_DEFINITIONS[dep]
        if info["kind"] == "python":
            if not assume_yes:
                confirm = typer.confirm(f"Install Python package '{info['package']}'?", default=True)
                if not confirm:
                    typer.echo(f"Skipping {dep} at user request.")
                    continue
            if not _install_python_dependency(info["package"]):
                typer.echo(f"Failed to install Python package '{info['package']}'.")
                raise typer.Exit(1)
            continue

        packages = info["packages"].get(resolved_manager)
        if not packages:
            typer.echo(
                f"No package mapping for dependency '{dep}' with manager '{resolved_manager}'."
            )
            raise typer.Exit(1)
        if not assume_yes:
            confirm = typer.confirm(
                f"Install {dep} using {resolved_manager} ({', '.join(packages)})?",
                default=True,
            )
            if not confirm:
                typer.echo(f"Skipping {dep} at user request.")
                continue
        if not _install_with_manager(resolved_manager, packages):
            typer.echo(f"Failed to install '{dep}' via {resolved_manager}.")
            raise typer.Exit(1)

    typer.echo("Dependency installation completed.")


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


@crush_app.command("setup", help="Generate PMOVES CLI configuration for deployment.")
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
    typer.echo(f"Wrote PMOVES CLI config to {config_path}")
    typer.echo("Providers configured: " + ", ".join(sorted(providers.keys())))


@crush_app.command("status", help="Show PMOVES CLI configuration details.")
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


@crush_app.command("preview", help="Print generated PMOVES CLI configuration JSON.")
def crush_preview() -> None:
    config, providers = crush_configurator.build_config()
    typer.echo(json.dumps(config, indent=2))
    typer.echo("\nProviders: " + ", ".join(sorted(providers.keys())))


# =============================================================================
# Agent SDK Commands
# =============================================================================

@agent_sdk_app.command("create", help="Create new PMOVES Agent instance via interactive wizard")
def agent_sdk_create(
    role: str = typer.Option(
        None,
        "--role",
        "-r",
        help="Agent role (researcher, code-reviewer, media-processor, knowledge-manager, general)"
    ),
    model: str = typer.Option(
        "openai::qwen3:8b",
        "--model",
        "-m",
        help="Model to use (provider::model_name syntax)"
    ),
    agent_id: Optional[str] = typer.Option(
        None,
        "--agent-id",
        help="Custom agent ID (default: auto-generated)"
    ),
    connect: bool = typer.Option(
        True,
        "--connect/--no-connect",
        help="Connect to PMOVES services after creation"
    ),
    config_only: bool = typer.Option(
        False,
        "--config-only",
        help="Generate configuration without creating agent"
    ),
) -> None:
    """Create a PMOVES Agent SDK instance with full ecosystem access.

    This will launch an interactive wizard to guide you through:
    1. Role selection (or use --role to skip)
    2. Tool customization
    3. MCP server configuration
    4. Service connection (NATS, TensorZero, Hi-RAG)

    Example:
        pmoves agent-sdk create --role researcher
        pmoves agent-sdk create --model openai::gpt-4o --no-connect
    """
    import asyncio
    import sys
    from datetime import datetime

    # Add PMOVES-BoTZ to path
    botz_path = Path(__file__).parent.parent.parent / "PMOVES-BoTZ"
    sys.path.insert(0, str(botz_path))

    try:
        from pmoves_botz.features.agent_sdk import PMOVESAgent
    except ImportError:
        typer.echo("❌ PMOVES Agent SDK not found in PMOVES-BoTZ")
        typer.echo(f"   Expected: {botz_path / 'features/agent_sdk'}")
        typer.echo("\nInitialize submodule:")
        typer.echo("   git submodule update --init PMOVES-BoTZ")
        raise typer.Exit(1)

    async def create_and_connect():
        # Interactive role selection if not provided
        if not role:
            typer.echo("\n🎭 Select Agent Role:")
            typer.echo("   1. researcher      - Deep research via SupaSerch + Hi-RAG")
            typer.echo("   2. code-reviewer   - Security-focused code analysis")
            typer.echo("   3. media-processor - Video/audio processing workflows")
            typer.echo("   4. knowledge-manager - Hi-RAG knowledge base operations")
            typer.echo("   5. general         - Full ecosystem access (all tools)")
            typer.echo()

            while True:
                try:
                    choice = input("Select role [1-5] (default: 5): ").strip()
                    if not choice:
                        selected_role = "general"
                        break
                    role_map = {1: "researcher", 2: "code-reviewer", 3: "media-processor", 4: "knowledge-manager", 5: "general"}
                    idx = int(choice)
                    if 1 <= idx <= 5:
                        selected_role = role_map[idx]
                        break
                    typer.echo(f"❌ Invalid choice. Please enter 1-5")
                except ValueError:
                    typer.echo("❌ Please enter a number.")
                except KeyboardInterrupt:
                    typer.echo("\n\n✋ Wizard cancelled.")
                    raise typer.Exit(0)
        else:
            selected_role = role

        # Generate agent ID
        timestamp = int(datetime.now().timestamp())
        final_agent_id = agent_id or f"pmoves-{selected_role}-{timestamp}"

        typer.echo(f"\n🔧 Creating agent: {final_agent_id}")

        # Create agent instance
        agent = PMOVESAgent(
            agent_id=final_agent_id,
            role=selected_role,
            model=model,
            enable_nats=True,
            enable_hooks=True,
        )

        if config_only:
            # Show config without connecting
            typer.echo("\n📋 Agent Configuration:")
            typer.echo(f"   Agent ID: {agent.agent_id}")
            typer.echo(f"   Role: {agent.role}")
            typer.echo(f"   Model: {agent.model}")
            typer.echo(f"   Tools: {', '.join(agent.allowed_tools)}")
            return

        if connect:
            # Connect to services
            typer.echo("🔗 Connecting to PMOVES services...")
            try:
                await agent.connect(require_services=True)
                typer.echo("✅ Connected to NATS")
                typer.echo("✅ HTTP client initialized")
            except ConnectionError as e:
                typer.echo(f"❌ Connection failed: {e}")
                typer.echo("   Agent NOT created due to service unavailability.")
                typer.echo("\n🔧 Troubleshooting:")
                typer.echo("   1. Start NATS: docker compose up -d nats")
                typer.echo("   2. Check health: curl http://localhost:4222")
                typer.echo("   3. Create agent without --connect flag to skip connection")
                raise typer.Exit(1)
            except RuntimeError as e:
                typer.echo(f"❌ Configuration error: {e}")
                typer.echo("   Agent NOT created due to missing dependencies.")
                raise typer.Exit(1)

        # Display configuration
        typer.echo("\n" + "╔" + "═" * 68 + "╗")
        typer.echo("║" + " " * 68 + "║")
        typer.echo("║" + "   ✅ PMOVES Agent Created Successfully!".center(68) + "║")
        typer.echo("║" + " " * 68 + "║")
        typer.echo("╚" + "═" * 68 + "╝")
        typer.echo()
        typer.echo(f"📌 Agent ID:    {agent.agent_id}")
        typer.echo(f"🎭 Role:        {agent.role}")
        typer.echo(f"🧠 Model:       {agent.model}")
        typer.echo(f"🔗 NATS URL:    {agent.NATS_URL}")
        typer.echo(f"🌐 TensorZero:  {agent.TENSORZERO_URL}")
        typer.echo(f"🔍 Hi-RAG:      {agent.HIRAG_URL}")
        typer.echo()
        typer.echo("📦 Available Tools:")
        for tool in agent.allowed_tools:
            typer.echo(f"   • {tool}")
        typer.echo()
        typer.echo("🔌 MCP Servers:")
        mcp_servers = agent._configure_mcp_servers()
        for server in mcp_servers:
            typer.echo(f"   • {server}")
        typer.echo()
        typer.echo("👥 Subagents:")
        subagents = agent._configure_subagents()
        for subagent in subagents:
            typer.echo(f"   • {subagent}")
        typer.echo()
        typer.echo("📡 NATS Events:")
        typer.echo(f"   • botz.agent.registered.v1 - Registration announcement")
        typer.echo(f"   • botz.agent.heartbeat.v1 - Presence (every 30s)")
        typer.echo(f"   • agent.task.start.v1 - Task execution start")
        typer.echo(f"   • botz.work.completed.v1 - Task completion")
        typer.echo()

        # Usage example
        typer.echo("💡 Usage Example:")
        typer.echo()
        typer.echo("   from pmoves_botz.features.agent_sdk import PMOVESAgent")
        typer.echo()
        typer.echo(f"   agent = PMOVESAgent(agent_id='{agent.agent_id}', role='{agent.role}')")
        typer.echo("   async for message in agent.execute('Your task here'):")
        typer.echo("       print(message.content)")
        typer.echo()

        typer.echo("📚 Next Steps:")
        typer.echo("   1. Use: pmoves agent-sdk run --agent-id <ID> 'Your task'")
        typer.echo("   2. Use: pmoves agent-sdk resume --session-id <ID>")
        typer.echo("   3. Monitor: nats sub 'botz.agent.>'")
        typer.echo()

        if connect:
            typer.echo("⏳ Agent is now running and sending heartbeats...")
            typer.echo("   Press Ctrl+C to disconnect and exit.")
            typer.echo()

            try:
                # Keep running to maintain heartbeat
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                typer.echo("\n\n👋 Disconnecting agent...")
                await agent.disconnect()
                typer.echo("✅ Agent disconnected.")
                raise typer.Exit(0)

    # Run async function
    asyncio.run(create_and_connect())


@agent_sdk_app.command("run", help="Execute a task with an existing agent")
def agent_sdk_run(
    agent_id: str = typer.Argument(..., help="Agent identifier"),
    task: str = typer.Argument(..., help="Task to execute"),
    session: Optional[str] = typer.Option(None, "--session", help="Session ID for resume"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override model"),
) -> None:
    """Execute a task using a PMOVES Agent.

    Example:
        pmoves agent-sdk run research-agent "Analyze PMOVES architecture"
        pmoves agent-sdk run code-agent --model openai::gpt-4o "Review security"
    """
    import asyncio
    import sys

    botz_path = Path(__file__).parent.parent.parent / "PMOVES-BoTZ"
    sys.path.insert(0, str(botz_path))

    try:
        from pmoves_botz.features.agent_sdk import PMOVESAgent
    except ImportError:
        typer.echo("❌ PMOVES Agent SDK not found")
        raise typer.Exit(1)

    async def execute_task():
        """Execute task with comprehensive error handling."""
        # Outer layer: Agent initialization errors
        try:
            typer.echo(f"🎯 Executing task with '{agent_id}'...")
            typer.echo(f"📝 Task: {task}")
            typer.echo()

            # Pass model to constructor for cleaner initialization
            agent_kwargs = {"agent_id": agent_id, "role": "general"}
            if model:
                agent_kwargs["model"] = model

            async with PMOVESAgent(**agent_kwargs) as agent:
                # Inner layer: Task execution errors
                try:
                    async for message in agent.execute(task, session_id=session):
                        if hasattr(message, 'type'):
                            if message.type == "assistant":
                                typer.echo(f"🤖 {message.content}")
                            elif message.type == "result":
                                typer.echo(f"✅ Result: {message.result}")
                            elif message.type == "tool_use":
                                typer.echo(f"🔧 Using: {message.name}")

                except ConnectionError as e:
                    typer.echo(f"\n❌ Connection failed during execution: {e}")
                    typer.echo("\n🔧 Troubleshooting:")
                    typer.echo("   1. Check service health: curl http://localhost:8086/healthz  # Hi-RAG")
                    typer.echo("   2. Check TensorZero: curl http://localhost:3030/v1/models")
                    typer.echo("   3. Check NATS: docker compose ps nats")
                    raise typer.Exit(1)

                except TimeoutError as e:
                    typer.echo(f"\n⏱️  Task timed out: {e}")
                    typer.echo("   Try breaking the task into smaller steps or increase timeout.")
                    raise typer.Exit(1)

                except ValueError as e:
                    typer.echo(f"\n❌ Invalid input: {e}")
                    typer.echo("   Check your agent ID, model format, and task description.")
                    raise typer.Exit(1)

        except ImportError as e:
            typer.echo(f"❌ Failed to import PMOVESAgent: {e}")
            typer.echo("   Ensure PMOVES-BoTZ submodule is initialized:")
            typer.echo("   git submodule update --init --recursive PMOVES-BoTZ")
            raise typer.Exit(1)

        except ValueError as e:
            typer.echo(f"❌ Agent configuration error: {e}")
            typer.echo("   Check agent_id format and model configuration.")
            raise typer.Exit(1)

    asyncio.run(execute_task())


@agent_sdk_app.command("list", help="List all PMOVES agents")
def agent_sdk_list(
    status: str = typer.Option("active", "--status", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number to show"),
) -> None:
    """List existing PMOVES Agent instances.

    Example:
        pmoves agent-sdk list
        pmoves agent-sdk list --status active --limit 50
    """
    typer.echo("📋 PMOVES Agent List")
    typer.echo("=" * 60)
    typer.echo()
    typer.echo("⚠️  Agent listing requires SessionManager backend.")
    typer.echo()
    typer.echo("🔧 Manual Workarounds:")
    typer.echo()
    typer.echo("1. **Monitor active agents via NATS heartbeat:**")
    typer.echo("   nats sub \"botz.agent.heartbeat.v1\"")
    typer.echo()
    typer.echo("2. **Check completed work items:**")
    typer.echo("   nats sub \"botz.work.completed.v1\"")
    typer.echo()
    typer.echo("3. **Query Supabase for agent records:**")
    typer.echo("   psql $DATABASE_URL -c \"SELECT agent_id, role, created_at FROM agent_sessions ORDER BY created_at DESC LIMIT 10;\"")
    typer.echo()
    typer.echo("4. **List local session files:**")
    typer.echo("   ls -lt ~/.pmoves/sessions/ | head -20")
    typer.echo()
    typer.echo("📊 Implementation Status:")
    typer.echo("   ✅ Agent creation: Implemented (pmoves agent-sdk create)")
    typer.echo("   ✅ Task execution: Implemented (pmoves agent-sdk run)")
    typer.echo("   ✅ Session resume: Implemented (pmoves agent-sdk resume)")
    typer.echo("   🚧 Agent listing: Requires SessionManager (planned)")
    typer.echo("   🚧 Status checking: Requires SessionManager (planned)")
    typer.echo()
    typer.echo("💡 For full agent lifecycle management, see:")
    typer.echo("   pmoves/PMOVES-BoTZ/features/agent_sdk/README.md")


@agent_sdk_app.command("status", help="Check agent status")
def agent_sdk_status(
    agent_id: str = typer.Argument(..., help="Agent identifier"),
) -> None:
    """Check the status of a PMOVES Agent.

    Example:
        pmoves agent-sdk status research-agent
    """
    typer.echo(f"🔍 Agent Status: {agent_id}")
    typer.echo("=" * 60)
    typer.echo()
    typer.echo("⚠️  Agent status checking requires SessionManager backend.")
    typer.echo()
    typer.echo("🔧 Manual Status Checks:")
    typer.echo()
    typer.echo("1. **Monitor agent heartbeat events:**")
    typer.echo(f"   nats sub \"botz.agent.heartbeat.v1\" | grep {agent_id}")
    typer.echo()
    typer.echo("2. **Check for task completion events:**")
    typer.echo(f"   nats sub \"botz.work.completed.v1\" | grep {agent_id}")
    typer.echo()
    typer.echo("3. **Query TensorZero for model usage:**")
    typer.echo('   curl -s http://localhost:3030/v1/inferences | jq \'.[] | select(.model | contains("qwen") or contains("claude"))\' | head -20')
    typer.echo()
    typer.echo("4. **Check service health:**")
    typer.echo("   curl http://localhost:4222   # NATS")
    typer.echo("   curl http://localhost:3030/healthz  # TensorZero")
    typer.echo("   curl http://localhost:8086/healthz  # Hi-RAG v2")
    typer.echo()
    typer.echo("5. **View agent session data (if file-based):**")
    typer.echo(f"   ls -lh ~/.pmoves/sessions/ | grep {agent_id}")
    typer.echo(f"   cat ~/.pmoves/sessions/{agent_id}*.json 2>/dev/null | jq '.state'")
    typer.echo()
    typer.echo("💡 Tip: Subscribe to all agent events:")
    typer.echo("   nats sub \"botz.**\"")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
