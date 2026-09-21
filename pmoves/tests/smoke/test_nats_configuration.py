"""
Test NATS configuration consistency across PMOVES.AI.

Validates that:
1. NATS service is properly configured
2. All services reference NATS_URL consistently
3. Documentation is up to date
4. NATS subjects follow naming conventions
"""

import re
import pytest
from pathlib import Path

from _smoke_helpers import grep_file, grep_count, grep_context, PROJECT_ROOT, PMOVES_DIR


NATS_CONFIG_DOC = PMOVES_DIR / "docs" / "NATS_CONFIGURATION.md"

# env.tier-* are funnel-generated operator-checkout artifacts (gitignored);
# CI runners and smoke hosts never carry them.
requires_env_files = pytest.mark.skipif(
    not any((PMOVES_DIR / f"env.tier-{t}").exists() for t in ("agent", "worker")),
    reason="env.tier-agent/worker not present (funnel-generated operator "
           "artifacts; not on CI runners or smoke hosts) — run on a node checkout",
)
COMPOSE_FILE = PMOVES_DIR / "docker-compose.yml"


@pytest.mark.smoke
def test_nats_documentation_exists() -> None:
    """Verify NATS configuration documentation exists."""
    assert NATS_CONFIG_DOC.exists(), (
        "NATS_CONFIGURATION.md should exist in pmoves/docs/"
    )

    content = NATS_CONFIG_DOC.read_text()
    required_sections = [
        "## Overview",
        "## Standard Configuration",
        "## Environment Variable Sources",
        "## Common Subjects",
        "## Debugging",
    ]

    for section in required_sections:
        assert section in content, (
            f"NATS_CONFIGURATION.md should have section: {section}"
        )


@pytest.mark.smoke
def test_nats_service_exists() -> None:
    """Verify NATS service is defined in docker-compose.yml."""
    count = grep_count(COMPOSE_FILE, r"^  nats:")
    assert count > 0, "NATS service should be defined in docker-compose.yml"


@pytest.mark.smoke
def test_nats_service_has_documentation_header() -> None:
    """Verify NATS service has documentation comment header."""
    # Check for comment header above the nats service definition.
    # The comment may be several lines above the service key, so search
    # with enough context (up to 15 lines before the service definition).
    output = grep_context(COMPOSE_FILE, r"^  nats:", before=15)
    assert output, "NATS service not found"

    assert "NATS Message Bus" in output or "NATS provides" in output, (
        "NATS service should have documentation comment header"
    )


@pytest.mark.smoke
@requires_env_files
def test_nats_url_defined_in_tier_files() -> None:
    """Verify NATS_URL is defined in all required tier env files (not env.shared)."""
    import warnings

    required_tiers = ["env.tier-agent", "env.tier-worker"]
    optional_tiers = ["env.tier-ui"]  # May not exist yet

    missing: list[str] = []
    for tier in required_tiers:
        path = PMOVES_DIR / tier
        if not path.exists():
            missing.append(f"{tier} (file missing)")
            continue
        matches = grep_file(path, r"^NATS_URL=")
        if not matches:
            missing.append(f"{tier} (no NATS_URL)")

    assert not missing, (
        f"NATS_URL should be defined in all required tier files. Missing: {missing}"
    )

    # Advisory: check optional tiers too
    for tier in optional_tiers:
        path = PMOVES_DIR / tier
        if path.exists():
            matches = grep_file(path, r"^NATS_URL=")
            if not matches:
                warnings.warn(f"NATS_URL not found in {tier} (optional)")


@pytest.mark.smoke
@requires_env_files
def test_nats_url_has_credentials() -> None:
    """Verify NATS_URL includes authentication credentials in tier files."""
    checked = 0
    for tier_file in ["env.tier-agent", "env.tier-worker", "env.tier-ui"]:
        path = PMOVES_DIR / tier_file
        if not path.exists():
            continue
        matches = grep_file(path, r"^NATS_URL=")
        if matches:
            checked += 1
            url = matches[0].split("=", 1)[1]
            assert "nats://" in url, (
                f"NATS_URL in {tier_file} should use nats:// protocol, got: {url}"
            )
            # Use robust regex to match user:pass@ pattern (not just "@" which
            # could be part of other URL components)
            assert re.search(r"nats://[^:@]+:[^@]+@", url), (
                f"NATS_URL in {tier_file} should include credentials "
                f"(nats://user:pass@host), got: {url}"
            )

    if checked == 0:
        pytest.fail(
            "No tier files with NATS_URL found — at least env.tier-agent and "
            "env.tier-worker must define NATS_URL"
        )


@pytest.mark.smoke
def test_services_have_consistent_nats_documentation() -> None:
    """Verify all services with NATS_URL have consistent documentation comments."""
    matches = grep_file(COMPOSE_FILE, r"NATS_URL.*from env\.")
    if not matches:
        pytest.skip("No NATS_URL references with env documentation found")

    inconsistent = []
    for line in matches:
        if line.strip() and not line.strip().startswith("#"):
            if "from env.tier-" in line:
                tier = line.split("from env.")[1].split(" ")[0] if "from env." in line else ""
                if tier:
                    if "env.tier-agent" not in line and "env.tier-media" not in line and "env.tier-worker" not in line:
                        inconsistent.append(line.strip())

    assert not inconsistent, (
        f"Some NATS_URL comments may reference incorrect tier files: {inconsistent}"
    )


@pytest.mark.smoke
def test_nats_subjects_follow_naming_convention() -> None:
    """Verify NATS subjects in documentation follow naming conventions."""
    if not NATS_CONFIG_DOC.exists():
        pytest.skip("NATS_CONFIGURATION.md not found")

    content = NATS_CONFIG_DOC.read_text()

    subjects = re.findall(r'`([a-z][a-z0-9_]*\.[^\s]+)`', content)

    for subject in subjects:
        assert subject.islower() or ">" in subject, (
            f"NATS subject should be lowercase: {subject}"
        )

        if ".v" in subject and not subject.endswith(">"):
            parts = subject.rsplit(".", 1)
            assert parts[-1].startswith("v"), (
                f"NATS subject version should use vN format: {subject}"
            )


def _nats_service() -> dict:
    """Parse the nats service out of the compose file.

    Previously these two tests grepped a FIXED LINE WINDOW after `^  nats:`
    (after=25 / after=35) and asserted against the raw text. That makes the
    assertion position-dependent: adding COMMENTS to the service pushes `ports:`
    out of the window and the test fails with "NATS should expose client port
    4222" while the port is present and unchanged. It is a false negative that
    accuses the wrong thing, and it had already been band-aided once — the
    removed comment read "Use a wider context window ... may be separated from
    the service key by anchor expansion."

    Parsing the YAML removes the whole failure mode. `yaml` is already the
    convention for compose assertions in this directory (test_compose_structure,
    test_port_conflicts, test_service_contracts all import it).
    """
    import yaml

    with open(COMPOSE_FILE, encoding="utf-8") as fh:
        compose = yaml.safe_load(fh)
    svc = (compose.get("services") or {}).get("nats")
    assert svc, "NATS service not found in compose"
    return svc


@pytest.mark.smoke
def test_nats_has_correct_ports_exposed() -> None:
    """Verify NATS exposes the correct ports."""
    ports = " ".join(str(p) for p in (_nats_service().get("ports") or []))
    assert "4222:4222" in ports or "${NATS_PORT" in ports, (
        f"NATS should expose client port 4222 (ports: {ports!r})"
    )


@pytest.mark.smoke
def test_nats_includes_jetstream() -> None:
    """Verify NATS is configured with JetStream enabled."""
    svc = _nats_service()
    command = " ".join(str(c) for c in (svc.get("command") or []))
    assert "-js" in command or "jetstream" in command.lower(), (
        f"NATS should have JetStream enabled (-js flag) (command: {command!r})"
    )


@pytest.mark.smoke
def test_nats_jetstream_store_is_persistent() -> None:
    """JetStream must not fall back to the container's /tmp.

    Without an explicit --store_dir, nats-server uses /tmp/nats/jetstream and
    warns "Temporary storage directory used, data could be lost on system
    reboot". Measured on z890 2026-09-15 that was the live state: streams=0,
    because every recreate discarded them. Core pub/sub stayed green throughout,
    so nothing else catches this.
    """
    svc = _nats_service()
    command = [str(c) for c in (svc.get("command") or [])]
    assert "--store_dir" in command, (
        "NATS -js without --store_dir defaults to /tmp and loses durable "
        f"streams on recreate (command: {command!r})"
    )
    store = command[command.index("--store_dir") + 1]
    assert not store.startswith("/tmp"), f"JetStream store must not be under /tmp: {store!r}"

    mounts = " ".join(str(v) for v in (svc.get("volumes") or []))
    assert store in mounts, (
        f"--store_dir {store!r} is not backed by a volume (volumes: {mounts!r}) — "
        "the store would still be lost on recreate"
    )


@pytest.mark.smoke
def test_nats_has_healthcheck() -> None:
    """Verify NATS service has a healthcheck configured.

    The healthcheck may be defined directly on the service block or
    inherited from a YAML anchor (e.g. *tier-data-hardened).  We search
    a wide window (30 lines after the service key) to capture both cases.
    """
    output = grep_context(COMPOSE_FILE, r"^  nats:", after=35)
    assert output, "NATS service not found"

    has_healthcheck = "healthcheck:" in output.lower()

    # Also check if it might come from the anchor — look for the anchor
    # definition in the compose file
    if not has_healthcheck:
        anchor_output = grep_context(COMPOSE_FILE, r"tier-data-hardened", after=15)
        if anchor_output:
            has_healthcheck = "healthcheck:" in anchor_output.lower()

    assert has_healthcheck, (
        "NATS should have a healthcheck configured (directly or via anchor)"
    )

    assert "8222" in output or "varz" in output, (
        "NATS healthcheck should verify monitoring endpoint (8222/varz)"
    )


@pytest.mark.smoke
def test_critical_services_depend_on_nats() -> None:
    """Verify critical services that need NATS have proper depends_on."""
    critical_services = [
        "agent-zero",
        "deepresearch",
        "supaserch",
        "publisher-discord",
    ]

    missing_deps = []
    for service in critical_services:
        # Use a wide context window to capture depends_on from the service
        # block. agent-zero's depends_on sits ~164 lines into its block
        # (environment + volumes first), so 50 lines missed it and reported
        # a dependency that exists. 250 covers the largest service block.
        output = grep_context(COMPOSE_FILE, rf"^  {service}:", after=250)
        if not output:
            continue  # Service may not exist in this compose file

        if "NATS_URL" in output or "NATS" in output:
            has_nats_dep = "nats:" in output and "depends_on:" in output
            # Also accept nats dependency via nats-init (implies nats)
            has_nats_init_dep = "nats-init:" in output
            if not has_nats_dep and not has_nats_init_dep:
                missing_deps.append(service)

    assert not missing_deps, (
        f"Services using NATS_URL but missing depends_on nats: {missing_deps}"
    )


@pytest.mark.smoke
def test_nats_on_correct_networks() -> None:
    """Verify NATS is on the correct Docker networks.

    Network assignment may come from a YAML anchor or be listed directly.
    The nats block carries ~30 lines of ports + security commentary before
    its networks: list, so a 25-line window truncated before networks: and
    failed while the assignment was present. 250 covers the whole block.
    """
    output = grep_context(COMPOSE_FILE, r"^  nats:", after=250)

    if output:
        assert "pmoves_bus" in output, (
            "NATS should be on pmoves_bus network (not just any pmoves-prefixed network)"
        )


@pytest.mark.smoke
def test_no_hardcoded_nats_urls_in_compose() -> None:
    """Verify docker-compose.yml doesn't have hardcoded NATS URLs (should use ${NATS_URL})."""
    matches = grep_file(COMPOSE_FILE, r"NATS_URL=nats://")

    if matches:
        hardcoded = [line for line in matches if "${" not in line]
        assert not hardcoded, (
            f"Found hardcoded NATS_URL in docker-compose.yml:\n"
            + "\n".join(hardcoded)
            + "\nUse ${NATS_URL:?NATS_URL must come from the secrets funnel} instead."
        )


@pytest.mark.smoke
def test_nats_documentation_matches_env_shared() -> None:
    """Verify NATS documentation references correct credential format."""
    if not NATS_CONFIG_DOC.exists():
        pytest.skip("NATS_CONFIGURATION.md not found")

    doc_content = NATS_CONFIG_DOC.read_text()

    # Documentation should reference the authenticated NATS URL format
    assert "nats://" in doc_content, (
        "NATS documentation should reference nats:// protocol"
    )
    # Match the full authenticated URL pattern (nats://user:pass@host)
    assert re.search(r"nats://[^:@]+:[^@]+@", doc_content), (
        "NATS documentation should include the full authenticated URL "
        "(nats://user:pass@host format)"
    )
