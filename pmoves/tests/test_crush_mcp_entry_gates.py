"""crush_configurator MCP entry gates: check the thing being enabled.

Measured 2026-11-20 on knuckles, after three MCP entries (hostinger,
pmoves-docker-gateway, tailscale) showed "connection closed / EOF" in every
Crush session while the existing gates were green:

- hostinger gated on docker + HOSTINGER_API_TOKEN, but never on the
  pmz-hostinger container, which does not exist on that node; `docker exec`
  then dies instantly and the entry EOFs at connect.
- pmoves-docker-gateway gated on `docker`, but the entry needs the `docker
  mcp` CLI plugin (a Docker Desktop component); without it the command is
  "unknown command" and the entry EOFs at connect.
- tailscale-mcp@2026.4.10-1 (the latest release) ships a bin with no shebang;
  npx exec falls back to /bin/sh and dies on the first JS line.
- stdio commands were stored as bare names resolved against the launching
  shell's PATH; fnm multishell bin dirs die with their shell, so entries
  generated from one shell EOF in the next.

These tests pin the gate semantics without docker, npm, or fnm present.
"""

from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGURATOR = REPO_ROOT / "pmoves" / "tools" / "crush_configurator.py"


def _module():
    spec = importlib.util.spec_from_file_location("crush_configurator_gates", CONFIGURATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules["crush_configurator_gates"] = module
    spec.loader.exec_module(module)
    return module


cc = _module()

EMPTY_ENV_CACHE: dict[Path, dict[str, str]] = {}


def _spec(**kwargs) -> "cc.MCPSpec":
    base = {"key": "unit", "config": {"type": "stdio", "command": "true", "timeout": 5}}
    base.update(kwargs)
    return cc.MCPSpec(**base)


# ------------------------------------------------------------------ gates


def test_container_gate_disables_with_named_reason(monkeypatch):
    monkeypatch.setattr(cc, "_docker_container_exists", lambda name: False)
    spec = _spec(key="hostinger", required_container="pmz-hostinger")
    config = dict(spec.config)
    disabled, note = cc._apply_mcp_gates(spec, config, EMPTY_ENV_CACHE)
    assert disabled
    assert "pmz-hostinger" in note


def test_container_gate_passes_when_container_exists(monkeypatch):
    monkeypatch.setattr(cc, "_docker_container_exists", lambda name: True)
    spec = _spec(key="hostinger", required_container="pmz-hostinger")
    config = dict(spec.config)
    disabled, note = cc._apply_mcp_gates(spec, config, EMPTY_ENV_CACHE)
    assert not disabled and note is None


def test_docker_subcommand_gate_disables_without_plugin(monkeypatch):
    monkeypatch.setattr(cc, "_docker_subcommand_available", lambda sub: False)
    spec = _spec(key="pmoves-docker-gateway", required_docker_subcommand="mcp")
    disabled, note = cc._apply_mcp_gates(spec, dict(spec.config), EMPTY_ENV_CACHE)
    assert disabled
    assert "docker mcp" in note


def test_docker_subcommand_probe_discovers_cli_plugin_binary(monkeypatch, tmp_path):
    # `docker mcp --help` exits 0 even WITHOUT the plugin (the CLI prints its
    # own top-level help), so the probe must look for the docker-mcp plugin
    # binary, not run the command.
    monkeypatch.setattr(cc.shutil, "which", lambda name: None)
    monkeypatch.setattr(cc, "_DOCKER_CLI_PLUGIN_DIRS", (tmp_path / "cliplugins",))
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cc._docker_subcommand_available("mcp") is False
    _make_executable(tmp_path / "cliplugins" / "docker-mcp")
    assert cc._docker_subcommand_available("mcp") is True


def test_npm_entry_gate_rewrites_to_node_with_absolute_entry(monkeypatch):
    entry = Path("/opt/fnm/lib/node_modules/tailscale-mcp/dist/index.js")
    monkeypatch.setattr(cc, "_npm_global_entry_path", lambda pkg, rel: entry)
    monkeypatch.setattr(cc, "_stable_which", lambda cmd: f"/stable/{cmd}")
    spec = _spec(key="tailscale", npm_global_entry=("tailscale-mcp", "dist/index.js"))
    config = dict(spec.config)
    disabled, note = cc._apply_mcp_gates(spec, config, EMPTY_ENV_CACHE)
    assert not disabled and note is None
    assert config["command"] == "/stable/node"
    assert config["args"] == [str(entry)]


def test_npm_entry_gate_disables_with_install_hint_when_missing(monkeypatch):
    monkeypatch.setattr(cc, "_npm_global_entry_path", lambda pkg, rel: None)
    spec = _spec(key="tailscale", npm_global_entry=("tailscale-mcp", "dist/index.js"))
    disabled, note = cc._apply_mcp_gates(spec, dict(spec.config), EMPTY_ENV_CACHE)
    assert disabled
    assert "npm i -g tailscale-mcp" in note


# ------------------------------------------------------- stable resolution


def _make_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_stable_which_prefers_fnm_default_alias_over_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    volatile = tmp_path / "volatile-bin"
    _make_executable(volatile / "npx")
    fnm_alias = tmp_path / ".local/share/fnm/aliases/default/bin/npx"
    _make_executable(fnm_alias)
    monkeypatch.setenv("PATH", str(volatile))
    assert cc._stable_which("npx") == str(fnm_alias)


def test_stable_which_falls_back_to_local_bin_then_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    local_bin = tmp_path / ".local/bin/npx"
    _make_executable(local_bin)
    assert cc._stable_which("npx") == str(local_bin)
    (tmp_path / ".local/bin/npx").unlink()
    on_path = tmp_path / "path-bin/uvx"
    _make_executable(on_path)
    monkeypatch.setenv("PATH", str(on_path.parent))
    assert cc._stable_which("uvx") == str(on_path)


def test_stable_which_leaves_explicit_paths_alone():
    assert cc._stable_which("/usr/bin/docker") == "/usr/bin/docker"


def test_stdio_command_resolved_to_stable_absolute(monkeypatch):
    monkeypatch.setattr(cc, "_stable_which", lambda cmd: f"/stable/{cmd}")
    spec = _spec()
    config = dict(spec.config)
    disabled, _ = cc._apply_mcp_gates(spec, config, EMPTY_ENV_CACHE)
    assert not disabled
    assert config["command"] == "/stable/true"


def test_disabled_entry_keeps_bare_command(monkeypatch):
    monkeypatch.setattr(cc, "_docker_container_exists", lambda name: False)
    monkeypatch.setattr(cc, "_stable_which", lambda cmd: f"/stable/{cmd}")
    spec = _spec(required_container="nope")
    config = dict(spec.config)
    disabled, _ = cc._apply_mcp_gates(spec, config, EMPTY_ENV_CACHE)
    assert disabled
    assert config["command"] == "true"
