"""ClawZ (OpenClaw) Field Tests -- 4090-claude

Validates submodule structure, service health, and NATS integration readiness.
ClawZ status: pre_stage -- submodule present, not yet in Docker compose stack.
NATS bridge: documented in TAC tree but unimplemented in codebase.
"""
import json
import os
import socket
import urllib.request

import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLAWZ_DIR = REPO_ROOT / "PMOVES-ClawZ"
CLAWZ_PORT = int(os.getenv("CLAWZ_PORT") or "18789")

# Expected NATS subjects from agent_registry.yaml / nats-subjects.md context doc
EXPECTED_NATS_SUBJECTS = [
    "openclaw.message.received.v1",
    "openclaw.message.sent.v1",
    "openclaw.channel.connected.v1",
]

NATS_SUBJECTS_DOC = REPO_ROOT / ".claude" / "context" / "nats-subjects.md"
AGENT_REGISTRY = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"


def _service_running() -> bool:
    """Check whether ClawZ is reachable on CLAWZ_PORT."""
    try:
        with socket.create_connection(("127.0.0.1", CLAWZ_PORT), timeout=2):
            return True
    except (OSError, ConnectionRefusedError):
        return False


# ---------------------------------------------------------------------------
# Submodule structure validation
# ---------------------------------------------------------------------------
class TestClawZSubmodule:
    """Verify ClawZ submodule presence, package metadata, and registry entry."""

    def test_submodule_exists(self):
        """PMOVES-ClawZ submodule directory must exist at repo root."""
        assert CLAWZ_DIR.is_dir(), (
            f"ClawZ submodule not found at {CLAWZ_DIR}. "
            "Run: git submodule update --init PMOVES-ClawZ"
        )

    def test_package_json_valid(self):
        """package.json must parse and contain expected metadata."""
        pkg_path = CLAWZ_DIR / "package.json"
        assert pkg_path.is_file(), f"Missing {pkg_path}"
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
        assert data.get("name") == "openclaw", (
            f"Expected package name 'openclaw', got '{data.get('name')}'"
        )
        assert "version" in data, "package.json missing 'version' field"
        assert "description" in data, "package.json missing 'description' field"

    def test_core_channel_count(self):
        """ClawZ must have at least 7 core channel normalizers in src/channels/."""
        channels_dir = CLAWZ_DIR / "src" / "channels"
        assert channels_dir.is_dir(), f"Core channels directory not found: {channels_dir}"
        # Count normalizer modules in plugins/normalize/ (discord, signal, slack, etc.)
        normalize_dir = channels_dir / "plugins" / "normalize"
        core_channels = set()
        if normalize_dir.is_dir():
            core_channels = {
                f.stem for f in normalize_dir.iterdir()
                if f.suffix == ".ts"
                and not f.stem.endswith(".test")
                and f.stem != "shared"  # shared is a utility, not a channel
            }
        # Also count the web channel (built-in HTTP channel)
        web_dir = channels_dir / "web"
        if web_dir.is_dir():
            core_channels.add("web")
        assert len(core_channels) >= 7, (
            f"Expected >= 7 core channels, found {len(core_channels)}: {sorted(core_channels)}"
        )

    def test_extension_count(self):
        """ClawZ must have at least 40 extensions in the extensions/ directory."""
        ext_dir = CLAWZ_DIR / "extensions"
        assert ext_dir.is_dir(), f"Extensions directory not found: {ext_dir}"
        extensions = [
            d.name for d in ext_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
        assert len(extensions) >= 40, (
            f"Expected >= 40 extensions, found {len(extensions)}: {sorted(extensions)}"
        )

    def test_agent_registry_entry(self):
        """Agent registry must contain a clawz entry with evolution_stage pre_stage."""
        assert AGENT_REGISTRY.is_file(), f"Agent registry not found: {AGENT_REGISTRY}"
        content = AGENT_REGISTRY.read_text(encoding="utf-8")
        assert "clawz:" in content, "Missing 'clawz:' entry in agent_registry.yaml"
        assert "evolution_stage: pre_stage" in content, (
            "ClawZ registry entry missing 'evolution_stage: pre_stage'"
        )
        assert "port: 18789" in content, (
            "ClawZ registry entry missing 'port: 18789'"
        )


# ---------------------------------------------------------------------------
# Service health (skip if ClawZ not running)
# ---------------------------------------------------------------------------
class TestClawZHealth:
    """Probe ClawZ health and readiness endpoints when the service is live."""

    @pytest.mark.skipif(not _service_running(), reason="ClawZ not running on port 18789")
    def test_healthz(self):
        """/healthz must return HTTP 200."""
        url = f"http://127.0.0.1:{CLAWZ_PORT}/healthz"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 — hardcoded localhost
            assert resp.status == 200, f"/healthz returned {resp.status}"

    @pytest.mark.skipif(not _service_running(), reason="ClawZ not running on port 18789")
    def test_readyz(self):
        """/readyz must return HTTP 200."""
        url = f"http://127.0.0.1:{CLAWZ_PORT}/readyz"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 — hardcoded localhost
            assert resp.status == 200, f"/readyz returned {resp.status}"


# ---------------------------------------------------------------------------
# NATS integration readiness
# ---------------------------------------------------------------------------
class TestClawZNATS:
    """Verify NATS subjects are documented but confirm bridge is not yet implemented."""

    def test_nats_subjects_documented(self):
        """Expected NATS subjects must appear in nats-subjects.md context doc."""
        assert NATS_SUBJECTS_DOC.is_file(), (
            f"NATS subjects context doc not found: {NATS_SUBJECTS_DOC}"
        )
        content = NATS_SUBJECTS_DOC.read_text(encoding="utf-8")
        missing = [
            subj for subj in EXPECTED_NATS_SUBJECTS
            if subj not in content
        ]
        assert not missing, (
            f"NATS subjects missing from context doc: {missing}. "
            "Update .claude/context/nats-subjects.md to include planned ClawZ subjects."
        )
        # Confirm bridge extension does NOT yet exist (pre_stage status)
        nats_bridge_dir = CLAWZ_DIR / "extensions" / "nats-bridge"
        assert not nats_bridge_dir.exists(), (
            f"nats-bridge extension found at {nats_bridge_dir} -- "
            "if implemented, update evolution_stage in agent_registry.yaml"
        )
