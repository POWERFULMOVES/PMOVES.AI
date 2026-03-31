"""Infrastructure cleanup PR validation tests.

Verifies that the infra-cleanup PR correctly:
- Removed gpu-5090 node type from hostinger-kvm-setup.sh
- Removed NVIDIA/GPU stack functions from pve9_postinstall.sh
- Removed 4090 deploy/models/status menu items from pinokio.js
- Updated PMOVES-ClawZ submodule branch to PMOVES.AI-Edition-Hardened
- Removed fleet remote access (RustDesk/Tailscale) from gitignore patterns
- Removed claude-code-setup plugin from settings.json
- Removed docker-compose safe paths from damage-control patterns.yaml
- Updated mcp.json with correct structure
- Removed CLAW provider lifecycle / fleet audit sections from nats-subjects.md
- Removed Fleet Audit Watcher service from services-catalog.md
"""
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
HOSTINGER_SETUP = REPO_ROOT / "deploy" / "provision" / "hostinger-kvm-setup.sh"
PVE9_POSTINSTALL = (
    REPO_ROOT
    / "CATACLYSM_STUDIOS_INC"
    / "L4-PLATFORM"
    / "provisions"
    / "proxmox"
    / "pve9_postinstall.sh"
)
PINOKIO_JS = REPO_ROOT / "pbnj" / "pinokio" / "api" / "pmoves-pbnj" / "pinokio.js"
GITMODULES = REPO_ROOT / ".gitmodules"
GITIGNORE = REPO_ROOT / ".gitignore"
SETTINGS_JSON = REPO_ROOT / ".claude" / "settings.json"
MCP_JSON = REPO_ROOT / ".claude" / "mcp.json"
PATTERNS_YAML = REPO_ROOT / ".claude" / "hooks" / "damage-control" / "patterns.yaml"
NATS_SUBJECTS_MD = REPO_ROOT / ".claude" / "context" / "nats-subjects.md"
SERVICES_CATALOG_MD = REPO_ROOT / ".claude" / "context" / "services-catalog.md"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# hostinger-kvm-setup.sh — gpu-5090 removal
# ---------------------------------------------------------------------------
class TestHostingerKvmSetup:
    """Verify gpu-5090 node type was fully removed from hostinger-kvm-setup.sh."""

    def test_file_exists(self):
        assert HOSTINGER_SETUP.is_file(), f"Script not found: {HOSTINGER_SETUP}"

    def test_gpu5090_not_in_node_type_case(self):
        """validate_node_type case statement must not include gpu-5090."""
        content = _read(HOSTINGER_SETUP)
        # The case match line should not have gpu-5090
        assert "gpu-5090)" not in content, (
            "gpu-5090 node type should have been removed from validate_node_type"
        )

    def test_valid_node_types_present(self):
        """The three valid node types must still be present."""
        content = _read(HOSTINGER_SETUP)
        assert "kvm4-1|kvm4-2|kvm2)" in content, (
            "Expected valid node types 'kvm4-1|kvm4-2|kvm2)' not found"
        )

    def test_usage_message_excludes_gpu5090(self):
        """Usage/help message must not reference gpu-5090."""
        content = _read(HOSTINGER_SETUP)
        assert "gpu-5090" not in content, (
            "gpu-5090 reference should be completely absent from hostinger-kvm-setup.sh"
        )

    def test_runner_labels_no_gpu5090(self):
        """Runner labels section must not include gpu-5090 label."""
        content = _read(HOSTINGER_SETUP)
        assert "gpu-5090" not in content, (
            "No gpu-5090 references should remain in runner label configuration"
        )

    def test_valid_node_type_labels_present(self):
        """All three valid node type runner labels must be present."""
        content = _read(HOSTINGER_SETUP)
        assert "kvm4-1)" in content
        assert "kvm4-2)" in content
        assert "kvm2)" in content

    def test_setup_flare_config_removed(self):
        """setup_flare_config function must be removed."""
        content = _read(HOSTINGER_SETUP)
        assert "setup_flare_config" not in content, (
            "setup_flare_config function should have been removed"
        )

    def test_model_namespace_config_removed(self):
        """MODEL_NAMESPACE env var setup must be removed."""
        content = _read(HOSTINGER_SETUP)
        assert "MODEL_NAMESPACE=pmoves" not in content, (
            "PMOVES.Flare MODEL_NAMESPACE config should have been removed"
        )

    def test_vllm_endpoint_config_removed(self):
        """VLLM_ENDPOINT remote GPU endpoint wiring must be removed."""
        content = _read(HOSTINGER_SETUP)
        assert "VLLM_ENDPOINT" not in content, (
            "vLLM endpoint configuration should have been removed"
        )

    def test_summary_excludes_gpu5090_steps(self):
        """show_summary must not contain gpu-5090 next-steps section."""
        content = _read(HOSTINGER_SETUP)
        assert "Install NVIDIA drivers" not in content, (
            "GPU driver install instructions should be absent"
        )
        assert "up-gpu" not in content, (
            "GPU stack startup instructions should be absent"
        )

    def test_node_config_marker_no_model_namespace(self):
        """The .node-config file template must not include MODEL_NAMESPACE."""
        content = _read(HOSTINGER_SETUP)
        # MODEL_NAMESPACE= should not appear in node-config heredoc
        assert "MODEL_NAMESPACE=" not in content, (
            "MODEL_NAMESPACE entry removed from .node-config template"
        )

    def test_script_is_executable_bash(self):
        """Script must start with bash shebang."""
        content = _read(HOSTINGER_SETUP)
        assert content.startswith("#!/bin/bash"), "Script must have #!/bin/bash shebang"


# ---------------------------------------------------------------------------
# pve9_postinstall.sh — GPU/NVIDIA stack removal
# ---------------------------------------------------------------------------
class TestPve9Postinstall:
    """Verify GPU/NVIDIA infrastructure functions were removed from pve9_postinstall.sh."""

    def test_file_exists(self):
        assert PVE9_POSTINSTALL.is_file(), f"Script not found: {PVE9_POSTINSTALL}"

    def test_nvidia_container_toolkit_removed(self):
        """install_nvidia_container_toolkit function must be removed."""
        content = _read(PVE9_POSTINSTALL)
        assert "install_nvidia_container_toolkit" not in content, (
            "install_nvidia_container_toolkit should have been removed"
        )

    def test_gpu_orchestrator_removed(self):
        """configure_gpu_orchestrator function must be removed."""
        content = _read(PVE9_POSTINSTALL)
        assert "configure_gpu_orchestrator" not in content, (
            "configure_gpu_orchestrator should have been removed"
        )

    def test_ollama_gpu_removed(self):
        """configure_ollama_gpu function must be removed."""
        content = _read(PVE9_POSTINSTALL)
        assert "configure_ollama_gpu" not in content, (
            "configure_ollama_gpu should have been removed"
        )

    def test_pmoves_network_setup_removed(self):
        """setup_pmoves_network function must be removed."""
        content = _read(PVE9_POSTINSTALL)
        assert "setup_pmoves_network" not in content, (
            "setup_pmoves_network should have been removed"
        )

    def test_pciutils_removed_from_apt_install(self):
        """pciutils package must not be in the apt install line."""
        content = _read(PVE9_POSTINSTALL)
        assert "pciutils" not in content, (
            "pciutils should have been removed from basic QoL apt install"
        )

    def test_docker_comment_for_rustdesk(self):
        """Docker CE install comment must reference RustDesk containers."""
        content = _read(PVE9_POSTINSTALL)
        assert "RustDesk" in content or "rustdesk" in content, (
            "Docker CE install comment should reference RustDesk containers"
        )

    def test_rustdesk_server_function_present(self):
        """configure_rustdesk_server function must remain (not removed)."""
        content = _read(PVE9_POSTINSTALL)
        assert "configure_rustdesk_server" in content, (
            "configure_rustdesk_server function should still be present"
        )

    def test_tailscale_up_simplified(self):
        """tailscale up command must not include PMOVES tags."""
        content = _read(PVE9_POSTINSTALL)
        # The simplified command should not have --tag=tag:pmoves
        assert "--tag=tag:pmoves" not in content, (
            "--tag=tag:pmoves should have been removed from tailscale up command"
        )

    def test_no_gpu_orchestrator_service_unit(self):
        """gpu-orchestrator.service systemd unit must not be present."""
        content = _read(PVE9_POSTINSTALL)
        assert "gpu-orchestrator.service" not in content, (
            "gpu-orchestrator.service systemd unit should have been removed"
        )

    def test_no_ollama_gpu_service_unit(self):
        """ollama-gpu.service systemd unit must not be present."""
        content = _read(PVE9_POSTINSTALL)
        assert "ollama-gpu.service" not in content, (
            "ollama-gpu.service systemd unit should have been removed"
        )

    def test_script_calls_configure_rustdesk(self):
        """Main flow must still call configure_rustdesk_server."""
        content = _read(PVE9_POSTINSTALL)
        # The function definition already tested; confirm it is also called
        calls = [
            line.strip()
            for line in content.splitlines()
            if "configure_rustdesk_server" in line and not line.strip().startswith("#")
        ]
        # At least 2 lines: definition + call
        assert len(calls) >= 2, (
            "configure_rustdesk_server must be both defined and called"
        )

    def test_docker_pmoves_network_not_created(self):
        """pmoves-net Docker network creation must be removed."""
        content = _read(PVE9_POSTINSTALL)
        assert "pmoves-net" not in content, (
            "pmoves-net Docker network creation should have been removed"
        )


# ---------------------------------------------------------------------------
# pinokio.js — 4090 menu items removal
# ---------------------------------------------------------------------------
class TestPinokioMenu:
    """Verify 4090 deploy/models/status menu items were removed from pinokio.js."""

    def test_file_exists(self):
        assert PINOKIO_JS.is_file(), f"pinokio.js not found: {PINOKIO_JS}"

    def test_4090_deploy_json_not_referenced(self):
        """4090-deploy.json must not be referenced in the menu."""
        content = _read(PINOKIO_JS)
        assert "4090-deploy.json" not in content, (
            "4090-deploy.json reference should have been removed from pinokio.js"
        )

    def test_4090_models_json_not_referenced(self):
        """4090-models.json must not be referenced in the menu."""
        content = _read(PINOKIO_JS)
        assert "4090-models.json" not in content, (
            "4090-models.json reference should have been removed from pinokio.js"
        )

    def test_4090_status_json_not_referenced(self):
        """4090-status.json must not be referenced in the menu."""
        content = _read(PINOKIO_JS)
        assert "4090-status.json" not in content, (
            "4090-status.json reference should have been removed from pinokio.js"
        )

    def test_4090_menu_text_absent(self):
        """Deploy 4090 Coding Workstation menu text must be absent."""
        content = _read(PINOKIO_JS)
        assert "Deploy 4090" not in content, (
            "'Deploy 4090' menu item text should have been removed"
        )
        assert "Pull 4090 Models" not in content, (
            "'Pull 4090 Models' menu item text should have been removed"
        )
        assert "4090 Status" not in content, (
            "'4090 Status' menu item text should have been removed"
        )

    def test_kvm4_deploy_items_still_present(self):
        """KVM4 deploy items must remain (only 4090 items removed)."""
        content = _read(PINOKIO_JS)
        assert "kvm4-1-deploy.json" in content, (
            "kvm4-1-deploy.json must still be present"
        )
        assert "kvm4-2-deploy.json" in content, (
            "kvm4-2-deploy.json must still be present"
        )
        assert "kvm2-deploy.json" in content, (
            "kvm2-deploy.json must still be present"
        )

    def test_module_exports_valid_structure(self):
        """pinokio.js must contain a valid module.exports block with menu function."""
        content = _read(PINOKIO_JS)
        assert "module.exports" in content, "module.exports must be present"
        assert "menu:" in content, "menu: property must be present"
        assert "async (kernel, info)" in content, "async menu function must be present"

    def test_network_tools_section_intact(self):
        """Network diagnostics/fix section must remain intact."""
        content = _read(PINOKIO_JS)
        assert "net-diag.js" in content, "net-diag.js must still be referenced"
        assert "net-fix.js" in content, "net-fix.js must still be referenced"
        assert "glances-start.js" in content, "glances-start.js must still be referenced"


# ---------------------------------------------------------------------------
# .gitmodules — PMOVES-ClawZ branch
# ---------------------------------------------------------------------------
class TestGitmodules:
    """Verify PMOVES-ClawZ branch was updated to PMOVES.AI-Edition-Hardened."""

    def test_file_exists(self):
        assert GITMODULES.is_file(), f".gitmodules not found: {GITMODULES}"

    def test_clawz_branch_is_hardened(self):
        """PMOVES-ClawZ submodule branch must be PMOVES.AI-Edition-Hardened."""
        content = _read(GITMODULES)
        # Find the PMOVES-ClawZ section
        clawz_section = re.search(
            r'\[submodule "PMOVES-ClawZ"\].*?(?=\[submodule|\Z)',
            content,
            re.DOTALL,
        )
        assert clawz_section is not None, "PMOVES-ClawZ submodule entry not found"
        section_text = clawz_section.group(0)
        assert "branch = PMOVES.AI-Edition-Hardened" in section_text, (
            f"PMOVES-ClawZ branch must be 'PMOVES.AI-Edition-Hardened', "
            f"found section: {section_text!r}"
        )

    def test_clawz_branch_not_main(self):
        """PMOVES-ClawZ must NOT be on the main branch."""
        content = _read(GITMODULES)
        clawz_section = re.search(
            r'\[submodule "PMOVES-ClawZ"\].*?(?=\[submodule|\Z)',
            content,
            re.DOTALL,
        )
        assert clawz_section is not None, "PMOVES-ClawZ submodule entry not found"
        section_text = clawz_section.group(0)
        # Confirm it's NOT 'branch = main'
        assert "branch = main" not in section_text, (
            "PMOVES-ClawZ branch must not be 'main' — should be PMOVES.AI-Edition-Hardened"
        )

    def test_clawz_url_present(self):
        """PMOVES-ClawZ submodule must still have its GitHub URL."""
        content = _read(GITMODULES)
        assert "PMOVES-ClawZ.git" in content, (
            "PMOVES-ClawZ repository URL must be present in .gitmodules"
        )


# ---------------------------------------------------------------------------
# .gitignore — fleet/RustDesk patterns removed
# ---------------------------------------------------------------------------
class TestGitignore:
    """Verify fleet/RustDesk secrets ignore patterns were removed from .gitignore."""

    def test_file_exists(self):
        assert GITIGNORE.is_file(), f".gitignore not found: {GITIGNORE}"

    def test_rustdesk_qr_pattern_removed(self):
        """rustdesk-*-qr.png ignore pattern must be removed."""
        content = _read(GITIGNORE)
        assert "rustdesk-*-qr.png" not in content, (
            "rustdesk-*-qr.png pattern should have been removed from .gitignore"
        )

    def test_fleet_audit_pattern_removed(self):
        """FLEET_AUDIT_*.md ignore pattern must be removed."""
        content = _read(GITIGNORE)
        assert "FLEET_AUDIT_" not in content, (
            "FLEET_AUDIT_*.md pattern should have been removed from .gitignore"
        )

    def test_enrollment_ledger_pattern_removed(self):
        """fleet enrollment ledger ignore pattern must be removed."""
        content = _read(GITIGNORE)
        assert ".enrollment-ledger.jsonl" not in content, (
            ".enrollment-ledger.jsonl pattern should have been removed from .gitignore"
        )

    def test_pmoves_ui_lib_exceptions_removed(self):
        """pmoves/ui/lib/ negation rules must be removed."""
        content = _read(GITIGNORE)
        assert "!pmoves/ui/lib/" not in content, (
            "!pmoves/ui/lib/ negation should have been removed from .gitignore"
        )
        assert "!pmoves/ui/lib/rooms.ts" not in content, (
            "!pmoves/ui/lib/rooms.ts negation should have been removed"
        )

    def test_core_env_patterns_still_present(self):
        """Core environment secrets patterns must still be in .gitignore."""
        content = _read(GITIGNORE)
        assert ".env" in content, ".env must still be ignored"
        assert "secrets/" in content, "secrets/ must still be ignored"


# ---------------------------------------------------------------------------
# .claude/settings.json — plugin removal
# ---------------------------------------------------------------------------
class TestSettingsJson:
    """Verify claude-code-setup plugin was removed from settings.json."""

    def test_file_exists(self):
        assert SETTINGS_JSON.is_file(), f"settings.json not found: {SETTINGS_JSON}"

    def test_valid_json(self):
        """settings.json must be valid JSON."""
        content = _read(SETTINGS_JSON)
        data = json.loads(content)  # Raises if invalid
        assert isinstance(data, dict), "settings.json must be a JSON object"

    def test_claude_code_setup_plugin_removed(self):
        """claude-code-setup@claude-plugins-official must not be in enabledPlugins."""
        content = _read(SETTINGS_JSON)
        data = json.loads(content)
        enabled_plugins = data.get("enabledPlugins", {})
        assert "claude-code-setup@claude-plugins-official" not in enabled_plugins, (
            "claude-code-setup@claude-plugins-official should have been removed from enabledPlugins"
        )

    def test_hookify_plugin_still_present(self):
        """hookify@claude-plugins-official must still be enabled."""
        content = _read(SETTINGS_JSON)
        data = json.loads(content)
        enabled_plugins = data.get("enabledPlugins", {})
        assert "hookify@claude-plugins-official" in enabled_plugins, (
            "hookify@claude-plugins-official must remain in enabledPlugins"
        )
        assert enabled_plugins["hookify@claude-plugins-official"] is True

    def test_hooks_section_intact(self):
        """hooks section must remain with PreToolUse/PostToolUse."""
        content = _read(SETTINGS_JSON)
        data = json.loads(content)
        hooks = data.get("hooks", {})
        assert "PreToolUse" in hooks, "PreToolUse hooks must be present"
        assert "PostToolUse" in hooks, "PostToolUse hooks must be present"

    def test_enabled_plugins_is_dict(self):
        """enabledPlugins must be a dict/object, not null."""
        content = _read(SETTINGS_JSON)
        data = json.loads(content)
        assert isinstance(data.get("enabledPlugins"), dict), (
            "enabledPlugins must be a JSON object"
        )

    def test_core_plugins_still_enabled(self):
        """Several core plugins must remain enabled."""
        content = _read(SETTINGS_JSON)
        data = json.loads(content)
        enabled_plugins = data.get("enabledPlugins", {})
        for plugin in [
            "code-review@claude-plugins-official",
            "github@claude-plugins-official",
            "security-guidance@claude-plugins-official",
        ]:
            assert plugin in enabled_plugins, f"{plugin} must still be in enabledPlugins"
            assert enabled_plugins[plugin] is True, f"{plugin} must be enabled (true)"


# ---------------------------------------------------------------------------
# .claude/mcp.json — structure validation
# ---------------------------------------------------------------------------
class TestMcpJson:
    """Verify mcp.json is valid and has the correct server structure."""

    def test_file_exists(self):
        assert MCP_JSON.is_file(), f"mcp.json not found: {MCP_JSON}"

    def test_valid_json(self):
        """mcp.json must be valid JSON."""
        content = _read(MCP_JSON)
        data = json.loads(content)
        assert isinstance(data, dict), "mcp.json must be a JSON object"

    def test_mcp_servers_key_present(self):
        """mcpServers key must be present."""
        content = _read(MCP_JSON)
        data = json.loads(content)
        assert "mcpServers" in data, "mcpServers key must be present in mcp.json"

    def test_docker_server_args_is_list(self):
        """docker server args must be a list (not nested)."""
        content = _read(MCP_JSON)
        data = json.loads(content)
        docker_server = data["mcpServers"].get("docker", {})
        assert "args" in docker_server, "docker server must have args"
        assert isinstance(docker_server["args"], list), "docker args must be a list"

    def test_docker_server_args_correct(self):
        """docker server must have correct mount args for Docker socket."""
        content = _read(MCP_JSON)
        data = json.loads(content)
        docker_args = data["mcpServers"]["docker"]["args"]
        assert "run" in docker_args
        assert "--rm" in docker_args
        assert "-i" in docker_args
        assert "mcp/docker" in docker_args
        # Verify socket mount is present
        assert "type=bind,src=//var/run/docker.sock,dst=/var/run/docker.sock" in docker_args

    def test_hostinger_mcp_args_is_list(self):
        """hostinger-mcp server args must be a flat list."""
        content = _read(MCP_JSON)
        data = json.loads(content)
        hostinger = data["mcpServers"].get("hostinger-mcp", {})
        assert "args" in hostinger, "hostinger-mcp must have args"
        assert isinstance(hostinger["args"], list), "hostinger-mcp args must be a list"
        assert "hostinger-api-mcp@latest" in hostinger["args"]

    def test_hostinger_mcp_api_token_env(self):
        """hostinger-mcp must have API_TOKEN env referencing HOSTINGER_API_KEY."""
        content = _read(MCP_JSON)
        data = json.loads(content)
        hostinger = data["mcpServers"]["hostinger-mcp"]
        env = hostinger.get("env", {})
        assert env.get("API_TOKEN") == "${HOSTINGER_API_KEY}", (
            "hostinger-mcp API_TOKEN must reference ${HOSTINGER_API_KEY}"
        )

    def test_cipher_server_present(self):
        """pmoves-cipher SSE server must be present."""
        content = _read(MCP_JSON)
        data = json.loads(content)
        cipher = data["mcpServers"].get("pmoves-cipher")
        assert cipher is not None, "pmoves-cipher server must be present"
        assert cipher.get("type") == "sse", "pmoves-cipher must be type sse"


# ---------------------------------------------------------------------------
# .claude/hooks/damage-control/patterns.yaml — safe paths cleanup
# ---------------------------------------------------------------------------
class TestDamageControlPatterns:
    """Verify docker-compose safe paths were removed from patterns.yaml chitSafePaths."""

    def test_file_exists(self):
        assert PATTERNS_YAML.is_file(), f"patterns.yaml not found: {PATTERNS_YAML}"

    def test_docker_compose_yml_not_in_chit_safe_paths(self):
        """docker-compose.yml must not be in chitSafePaths."""
        content = _read(PATTERNS_YAML)
        # Find the chitSafePaths section
        chit_section_match = re.search(
            r'chitSafePaths:(.*?)(?=\n[a-zA-Z#]|\Z)',
            content,
            re.DOTALL,
        )
        assert chit_section_match, "chitSafePaths section not found in patterns.yaml"
        chit_section = chit_section_match.group(1)
        assert "docker-compose.yml" not in chit_section, (
            "docker-compose.yml should have been removed from chitSafePaths"
        )

    def test_docker_compose_integrations_not_in_chit_safe_paths(self):
        """docker-compose.integrations must not be in chitSafePaths."""
        content = _read(PATTERNS_YAML)
        chit_section_match = re.search(
            r'chitSafePaths:(.*?)(?=\n[a-zA-Z#]|\Z)',
            content,
            re.DOTALL,
        )
        assert chit_section_match, "chitSafePaths section not found in patterns.yaml"
        chit_section = chit_section_match.group(1)
        assert "docker-compose.integrations" not in chit_section, (
            "docker-compose.integrations should have been removed from chitSafePaths"
        )

    def test_pr_kits_not_in_chit_safe_paths(self):
        """pr-kits must not be in chitSafePaths."""
        content = _read(PATTERNS_YAML)
        chit_section_match = re.search(
            r'chitSafePaths:(.*?)(?=\n[a-zA-Z#]|\Z)',
            content,
            re.DOTALL,
        )
        assert chit_section_match, "chitSafePaths section not found in patterns.yaml"
        chit_section = chit_section_match.group(1)
        assert "pr-kits" not in chit_section, (
            "pr-kits should have been removed from chitSafePaths"
        )

    def test_data_chit_paths_still_present(self):
        """Core CHIT data paths must still be in chitSafePaths."""
        content = _read(PATTERNS_YAML)
        assert '"data/chit/"' in content or "data/chit/" in content, (
            "data/chit/ path must remain in chitSafePaths"
        )

    def test_cipher_paths_still_present(self):
        """Cipher data paths must still be in chitSafePaths."""
        content = _read(PATTERNS_YAML)
        assert "data/cipher/" in content, (
            "data/cipher/ path must remain in chitSafePaths"
        )

    def test_nats_credential_pattern_present(self):
        """NATS credential pattern must still be present in chitSafePaths."""
        content = _read(PATTERNS_YAML)
        assert "nats*credential" in content or "*nats*credential*" in content, (
            "NATS credential pattern must remain in chitSafePaths"
        )


# ---------------------------------------------------------------------------
# .claude/context/nats-subjects.md — fleet/CLAW sections removed
# ---------------------------------------------------------------------------
class TestNatsSubjectsMd:
    """Verify fleet enrollment and CLAW provider lifecycle sections were removed."""

    def test_file_exists(self):
        assert NATS_SUBJECTS_MD.is_file(), f"nats-subjects.md not found: {NATS_SUBJECTS_MD}"

    def test_claw_provider_activated_removed(self):
        """claw.provider.activated.v1 subject must be removed."""
        content = _read(NATS_SUBJECTS_MD)
        assert "claw.provider.activated.v1" not in content, (
            "claw.provider.activated.v1 should have been removed from nats-subjects.md"
        )

    def test_claw_provider_deactivated_removed(self):
        """claw.provider.deactivated.v1 subject must be removed."""
        content = _read(NATS_SUBJECTS_MD)
        assert "claw.provider.deactivated.v1" not in content, (
            "claw.provider.deactivated.v1 should have been removed from nats-subjects.md"
        )

    def test_fleet_enrollment_subject_removed(self):
        """fleet.enrollment.created.v1 subject must be removed."""
        content = _read(NATS_SUBJECTS_MD)
        assert "fleet.enrollment.created.v1" not in content, (
            "fleet.enrollment.created.v1 should have been removed from nats-subjects.md"
        )

    def test_fleet_device_registered_removed(self):
        """fleet.device.registered.v1 subject must be removed."""
        content = _read(NATS_SUBJECTS_MD)
        assert "fleet.device.registered.v1" not in content, (
            "fleet.device.registered.v1 should have been removed from nats-subjects.md"
        )

    def test_fleet_audit_connection_removed(self):
        """fleet.audit.connection.v1 subject must be removed."""
        content = _read(NATS_SUBJECTS_MD)
        assert "fleet.audit.connection.v1" not in content, (
            "fleet.audit.connection.v1 should have been removed from nats-subjects.md"
        )

    def test_fleet_audit_heartbeat_removed(self):
        """fleet.audit.heartbeat.v1 subject must be removed."""
        content = _read(NATS_SUBJECTS_MD)
        assert "fleet.audit.heartbeat.v1" not in content, (
            "fleet.audit.heartbeat.v1 should have been removed from nats-subjects.md"
        )

    def test_fleet_audit_watcher_section_removed(self):
        """Fleet Audit Watcher section must be removed from nats-subjects.md."""
        content = _read(NATS_SUBJECTS_MD)
        assert "Fleet Audit Watcher Subjects" not in content, (
            "Fleet Audit Watcher Subjects section should have been removed"
        )

    def test_openclaw_subjects_still_present(self):
        """openclaw NATS subjects must still be documented."""
        content = _read(NATS_SUBJECTS_MD)
        assert "openclaw" in content, (
            "openclaw subjects must remain documented in nats-subjects.md"
        )


# ---------------------------------------------------------------------------
# .claude/context/services-catalog.md — Fleet Audit Watcher removed
# ---------------------------------------------------------------------------
class TestServicesCatalogMd:
    """Verify Fleet Audit Watcher service entry was removed from services-catalog.md."""

    def test_file_exists(self):
        assert SERVICES_CATALOG_MD.is_file(), f"services-catalog.md not found: {SERVICES_CATALOG_MD}"

    def test_fleet_audit_watcher_removed(self):
        """Fleet Audit Watcher service entry must be removed."""
        content = _read(SERVICES_CATALOG_MD)
        assert "Fleet Audit Watcher" not in content, (
            "Fleet Audit Watcher service entry should have been removed from services-catalog.md"
        )

    def test_fleet_audit_jsonl_removed(self):
        """fleet-audit.jsonl reference must be removed."""
        content = _read(SERVICES_CATALOG_MD)
        assert "fleet-audit.jsonl" not in content, (
            "fleet-audit.jsonl reference should have been removed from services-catalog.md"
        )

    def test_botz_mcp_gateway_still_present(self):
        """BoTZ MCP Gateway service must still be present."""
        content = _read(SERVICES_CATALOG_MD)
        assert "BoTZ MCP Gateway" in content, (
            "BoTZ MCP Gateway service entry must remain in services-catalog.md"
        )

    def test_services_catalog_has_content(self):
        """services-catalog.md must have substantial content (not empty)."""
        content = _read(SERVICES_CATALOG_MD)
        assert len(content) > 500, (
            "services-catalog.md appears too short — may have lost required content"
        )


# ---------------------------------------------------------------------------
# Regression: deleted files must not exist
# ---------------------------------------------------------------------------
class TestDeletedFiles:
    """Confirm that deleted files are truly absent from the repository."""

    @pytest.mark.parametrize("rel_path", [
        ".kilo/agent/darkxside.md",
        ".kilo/agent/kilocode-glm.md",
        ".kilo/agent/powerfulmoves.md",
        ".kilo/command/chit-encode.md",
        ".kilo/command/chit-sign.md",
        ".kilo/command/claim.md",
        ".kilo/command/deploy-up.md",
        ".kilo/command/health.md",
        ".kilo/command/model-populate.md",
        ".kilo/command/release.md",
        ".kilo/command/sitrep.md",
        ".kilo/command/smoke.md",
        ".kilo/command/vllm.md",
        ".kilo/command/zai-mcp.md",
        ".claude/commands/search/ingest-content.md",
        ".claude/commands/tts/express.md",
        "kilo.json",
        "pbnj/pinokio/api/pmoves-agent-zero/install.js",
        "pbnj/pinokio/api/pmoves-agent-zero/start.js",
        "pbnj/pinokio/api/pmoves-agent-zero/status.js",
        "pbnj/pinokio/api/pmoves-agent-zero/update.js",
        "pbnj/pinokio/api/pmoves-agent-zero/reset.js",
        "pbnj/pinokio/api/pmoves-agent-zero/pinokio.js",
        "pbnj/pinokio/api/pmoves-agent-zero/pinokio.json",
        "pbnj/pinokio/api/pmoves-agent-zero/README.md",
        "pbnj/pinokio/api/pmoves-pbnj/4090-deploy.json",
        "pbnj/pinokio/api/pmoves-pbnj/4090-models.json",
        "pbnj/pinokio/api/pmoves-pbnj/4090-status.json",
        "pbnj/pinokio/plugin/code/pmoves-codex/pinokio.js",
        "pbnj/pinokio/plugin/code/pmoves-codex/README.md",
    ])
    def test_deleted_file_absent(self, rel_path: str):
        """Each file deleted in this PR must not exist in the working tree."""
        target = REPO_ROOT / rel_path
        assert not target.exists(), (
            f"File should have been deleted but still exists: {rel_path}"
        )