"""No committed NATS credentials anywhere in tracked source.

The pre-existing guard (test_bpm_encoder_nats.TestNatsClientNoHardcodedDefault)
checks exactly ONE module's DEFAULT_NATS_URL. The credential pattern lives in
112 .py files and 24 yml/sh files, so that guard reported green over a surface
it never looked at.

This guard is generated FROM the pattern over the tracked corpus, so it cannot
go stale as files are added.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# A credential embedded in a nats:// URL: scheme, user, password, host.
CREDENTIAL = re.compile(r"nats://([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+)@")

# The credential that actually leaked. In TEST files this is the only pair we
# flag, because a test that exercises redaction or URL parsing MUST contain a
# credential-shaped string to be meaningful -- stripping it silently converts
# the test into one that cannot fail. (A sweep in this lane did exactly that to
# two flute-gateway redaction controls before this rule existed.)
LEAKED_CREDENTIAL = ("nats", "pmoves")

# Obvious documentation placeholders. These SHOULD stay -- they teach the URL
# shape without shipping a secret. Keyed on the user:password pair.
PLACEHOLDERS = {
    ("user", "pass"),
    ("u", "p"),
    ("USER", "PASS"),
    ("username", "password"),
}

# KNOWN, ENUMERATED EXCEPTIONS -- deliberately visible, not silently excluded.
#
# These are NOT source defaults. They are live config (compose, agent profiles,
# TAC trees, the CHIT manifest) where deleting the credential would break
# authenticated connections rather than harden them. They need the opposite
# fix: replace the literal with an env reference (${NATS_URL}) sourced from the
# secrets funnel, AND rotate the credential, since it has been public.
#
# That is an operator-sequenced change, not a mechanical one. Listing them here
# keeps the remaining exposure countable instead of invisible -- shrinking this
# list is the follow-up lane.
KNOWN_CONFIG_EXCEPTIONS = {
    "pmoves/chit/secrets_manifest_v2.yaml",
    "pmoves/configs/agent-profiles/coder_claw.yaml",
    "pmoves/configs/agent-profiles/minimax_claw.yaml",
    "pmoves/configs/agent-profiles/minimax_edition.yaml",
    "pmoves/configs/agent-profiles/nemoclaw.yaml",
    "pmoves/configs/agent-profiles/nemotron_claw.yaml",
    "pmoves/configs/agent-profiles/rocm_claw.yaml",
    "pmoves/configs/agent-profiles/spark_claw.yaml",
    "pmoves/configs/skill-pairings.yaml",
    "pmoves/configs/tac_trees/agent-zero-customization.tac.yaml",
    "pmoves/configs/tac_trees/cast-gateway.tac.yaml",
    "pmoves/configs/tac_trees/dox-intelligence.tac.yaml",
    "pmoves/configs/tac_trees/n8n.tac.yaml",
    "pmoves/configs/tac_trees/networking-defense-in-depth.tac.yaml",
    "pmoves/configs/tac_trees/node-z890-coordinator.tac.yaml",
    "pmoves/configs/tac_trees/security-posture.tac.yaml",
    "pmoves/docker-compose/hf-mcp-server.yml",
    "pmoves/scripts/fleet/fleet-audit-watcher.sh",
    "pmoves/scripts/nats/init_streams.sh",
    "pmoves/scripts/nats/setup_geometry_streams.sh",
    "pmoves/scripts/proxmox/pmoves-bootstrap.sh",
    "pmoves/services/agent-zero/.mprocs.yaml",
    "pmoves/services/agentgym-rl-coordinator/docker-compose.yml",
    "pmoves/services/cast-tts-gateway/docker-compose.yml",
}

SEARCH_GLOBS = [
    "pmoves/**/*.py",
    "pmoves/**/*.yml",
    "pmoves/**/*.yaml",
    "pmoves/**/*.sh",
]


def _tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "--", *SEARCH_GLOBS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def _is_test_file(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return (
        "/tests/" in rel
        or rel.startswith("pmoves/tests/")
        or name.startswith("test_")
        or name == "conftest.py"
    )


def _offenders():
    hits = []
    for rel in _tracked_files():
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in CREDENTIAL.finditer(line):
                if (match.group(1), match.group(2)) in PLACEHOLDERS:
                    continue
                if rel in KNOWN_CONFIG_EXCEPTIONS:
                    continue
                pair = (match.group(1), match.group(2))
                if _is_test_file(rel) and pair != LEAKED_CREDENTIAL:
                    # Synthetic fixture feeding a redaction/parsing test.
                    continue
                hits.append(f"{rel}:{lineno}: {match.group(0)}")
    return hits


def test_the_corpus_is_not_empty():
    """Control: an empty corpus would make the real test below pass vacuously.

    Production change that would make this fail: a broken glob or a wrong
    REPO_ROOT, which would otherwise report 'no offenders' for the wrong reason.
    """
    files = _tracked_files()
    assert len(files) > 500, f"corpus looks wrong: only {len(files)} tracked files matched"


def test_no_committed_nats_credentials_in_tracked_source():
    """Production change that would make this fail: reintroducing a real
    user:password pair into any nats:// URL in tracked source."""
    offenders = _offenders()
    assert not offenders, (
        f"{len(offenders)} committed NATS credential(s) found "
        f"(corpus: {len(_tracked_files())} tracked files):\n  "
        + "\n  ".join(offenders[:25])
        + ("\n  ..." if len(offenders) > 25 else "")
    )
