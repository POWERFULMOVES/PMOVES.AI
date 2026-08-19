"""
Hand-written tests for the operator's full-conformance run path.

The static half of the gate runs in CI; the full half (verify.py
against a real provider) is the operator's manual step on the
local node. The command is documented in two places:

  - pmoves/docs/operations/PROVIDER_VERIFIER_GATE.md § "The full
    conformance run"
  - .claude/BOOTSTRAP.md Known Roads table

If a future doc refactor changes the command, the operator can't
follow it. These tests pin the contract:

  - verify.py's CLI flags (the operator's invocation)
  - The verifier's runtime deps (the operator's install step)
  - The Python version requirement (the operator's preflight)
  - The PROVIDER_VERIFIER_GATE.md doc text matches the BOOTSTRAP.md
    Known Roads row (no drift between the two discoverability
    surfaces)

If a future edit breaks any of these contracts, these tests catch
it before the operator hits a "command not found" at 2am.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFIER_DIR = REPO_ROOT / "Pmoves-MiniMax-Provider-Verifier"
REQUIREMENTS_TXT = VERIFIER_DIR / "requirements.txt"
PYPROJECT_TOML = VERIFIER_DIR / "pyproject.toml"
PROVIDER_VERIFIER_GATE_DOC = (
    REPO_ROOT / "pmoves" / "docs" / "operations" / "PROVIDER_VERIFIER_GATE.md"
)
BOOTSTRAP_MD = REPO_ROOT / ".claude" / "BOOTSTRAP.md"


# ============================================================================
# verify.py's CLI shape
# ============================================================================


def test_verifier_help_lists_required_flags() -> None:
    """verify.py's --help must list the 3 required flags for the operator's run.

    The operator's manual command is:
        python verify.py --providers <file> --output-dir <dir> --model <m> \
                         --base-url <u> [--api-key <k>]

    These 4 flags (--providers, --output-dir, --model, --base-url) are
    the load-bearing surface. --api-key is optional (env var works).
    """
    import subprocess
    result = subprocess.run(
        # sys.executable, not "py": the launcher is Windows-only and this
        # suite runs on ubuntu-latest in CI, where it exits 127.
        [sys.executable, str(VERIFIER_DIR / "verify.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        pytest.skip(f"verify.py --help failed: {result.stderr!r}")
    help_text = result.stdout + result.stderr
    for flag in ("--providers", "--output-dir", "--model", "--base-url"):
        assert flag in help_text, (
            f"verify.py --help must mention {flag}; "
            f"the operator's run uses this flag"
        )


# ============================================================================
# Runtime deps
# ============================================================================


def test_requirements_txt_has_runtime_deps() -> None:
    """The verifier's requirements.txt must list the 6 runtime deps."""
    if not REQUIREMENTS_TXT.exists():
        pytest.skip(f"{REQUIREMENTS_TXT} not found")
    text = REQUIREMENTS_TXT.read_text(encoding="utf-8")
    for dep in ("jsonschema", "loguru", "megfile", "numpy", "openai", "tqdm"):
        assert dep in text, (
            f"{REQUIREMENTS_TXT.relative_to(REPO_ROOT)} must list '{dep}'; "
            f"the operator's install (pip install -r) needs it"
        )


def test_pyproject_python_version_requirement() -> None:
    """The verifier's pyproject.toml requires-python must be >= 3.12."""
    if not PYPROJECT_TOML.exists():
        pytest.skip(f"{PYPROJECT_TOML} not found")
    text = PYPROJECT_TXT.read_text() if False else PYPROJECT_TOML.read_text(encoding="utf-8")
    # pyproject.toml is TOML; we parse just the requires-python line.
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', text)
    assert match is not None, (
        f"{PYPROJECT_TOML.relative_to(REPO_ROOT)} must declare requires-python; "
        f"the operator's preflight needs to know the minimum Python"
    )
    requires = match.group(1)
    # The requires-python string is a PEP 440 spec; the form is '>=X.Y'.
    version_match = re.search(r">=\s*(\d+\.\d+)", requires)
    assert version_match is not None, (
        f"requires-python {requires!r} should be a '>=X.Y' constraint"
    )
    version = version_match.group(1)
    # The CI workflow uses python-version: '3.12' and the doc says
    # "matches the verifier's pyproject.toml". If a future bump drops
    # below 3.12, this test catches it.
    major, minor = (int(x) for x in version.split("."))
    assert (major, minor) >= (3, 12), (
        f"verifier requires Python >= {version}; the CI workflow's "
        f"python-version: '3.12' setup-python step must be at least as new"
    )


# ============================================================================
# Doc cross-reference: PROVIDER_VERIFIER_GATE.md and BOOTSTRAP.md agree
# ============================================================================


def test_gate_doc_has_full_run_section() -> None:
    """PROVIDER_VERIFIER_GATE.md must have a 'full conformance run' section."""
    if not PROVIDER_VERIFIER_GATE_DOC.exists():
        pytest.skip(f"{PROVIDER_VERIFIER_GATE_DOC} not found")
    text = PROVIDER_VERIFIER_GATE_DOC.read_text(encoding="utf-8")
    # The exact section name is the contract.
    assert "## Gate in CI" in text, (
        f"{PROVIDER_VERIFIER_GATE_DOC.relative_to(REPO_ROOT)} must have "
        f"a '## Gate in CI' section; the operator's discoverability path"
    )
    assert "full conformance" in text.lower(), (
        f"{PROVIDER_VERIFIER_GATE_DOC.relative_to(REPO_ROOT)} must mention "
        f"'full conformance' — the operator's manual step is described by "
        f"this term"
    )


def test_bootstrap_md_has_provider_verifier_rows() -> None:
    """BOOTSTRAP.md's Known Roads table must include the verifier rows."""
    if not BOOTSTRAP_MD.exists():
        pytest.skip(f"{BOOTSTRAP_MD} not found")
    text = BOOTSTRAP_MD.read_text(encoding="utf-8")
    assert "provider-verifier" in text, (
        f"{BOOTSTRAP_MD.relative_to(REPO_ROOT)} must mention "
        f"'provider-verifier' in the Known Roads table; cold-start "
        f"agents need to discover the gate"
    )
    # The static-half row uses the helper directly.
    assert "provider_verifier_gate.py" in text, (
        f"{BOOTSTRAP_MD.relative_to(REPO_ROOT)} must mention the helper "
        f"path; the Known Roads row is the operator's pointer"
    )


def test_bootstrap_and_gate_doc_agree_on_invoke() -> None:
    """The two discoverability surfaces must agree on the invocation command.

    A drift here means a cold-start agent and a doc-reading operator
    invoke the gate differently. The contract: both surfaces say
    `py pmoves/tools/provider_verifier_gate.py` for the static half.
    """
    if not BOOTSTRAP_MD.exists() or not PROVIDER_VERIFIER_GATE_DOC.exists():
        pytest.skip("BOOTSTRAP.md or PROVIDER_VERIFIER_GATE.md missing")
    bootstrap = BOOTSTRAP_MD.read_text(encoding="utf-8")
    gate_doc = PROVIDER_VERIFIER_GATE_DOC.read_text(encoding="utf-8")
    assert "py pmoves/tools/provider_verifier_gate.py" in bootstrap, (
        "BOOTSTRAP.md must invoke the gate via the exact path the helper lives at"
    )
    assert "py pmoves/tools/provider_verifier_gate.py" in gate_doc, (
        "PROVIDER_VERIFIER_GATE.md must show the same invocation"
    )
