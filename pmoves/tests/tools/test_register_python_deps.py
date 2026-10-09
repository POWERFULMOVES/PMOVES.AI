"""The register road must pick an interpreter that has EVERY dependency it uses.

Measured 2026-09-15, twice, on real `make -C pmoves register-release` runs:

    register-append: DEGRADED - pydantic is not importable in this interpreter,
    so prose is validated by the stdlib fallback rather than by the RegisterProse
    model. ... Run this through `make -C pmoves register-claim`, which picks an
    interpreter that has it.

Three linked defects, and each one hid the next:

  1. `REGISTER_PYTHON` probed `import yaml` and nothing else, so an interpreter
     with PyYAML and no pydantic was selected as GOOD.
  2. `register-claim` expands the SAME `REGISTER_PYTHON` as `register-release`,
     so the remedy the notice named was the thing you had just run. A warning
     whose fix is a no-op teaches people to skip warnings, which costs more than
     the degradation it reports.
  3. The PEP 723 block declared only `pyyaml`, so even the `uv run --script`
     fallback could not have supplied pydantic. The offline fetch bought nothing
     and the notice fired anyway.

These tests read the declarations rather than the behaviour, because the
behaviour is "whatever this node happens to have installed" — which is exactly
the thing that varies across the fleet and made the defect invisible on any node
that happened to carry both.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "pmoves" / "tools" / "register_append.py"
MAKEFILE = REPO_ROOT / "pmoves" / "Makefile"

# Third-party modules register_append.py relies on, and the distribution that
# provides each. Import name != package name for PyYAML, which is precisely the
# kind of detail a probe gets wrong.
REQUIRED = {"yaml": "pyyaml", "pydantic": "pydantic"}


def _pep723_block(text: str) -> str:
    m = re.search(r"^# /// script\n(.*?)^# ///", text, re.S | re.M)
    return m.group(1) if m else ""


@pytest.fixture(scope="module")
def tool_text() -> str:
    if not TOOL.is_file():
        pytest.skip("register_append.py not present")
    return TOOL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def makefile_text() -> str:
    if not MAKEFILE.is_file():
        pytest.skip("Makefile not present")
    return MAKEFILE.read_text(encoding="utf-8")


def test_pep723_declares_every_required_distribution(tool_text: str):
    block = _pep723_block(tool_text)
    assert block, "register_append.py has no PEP 723 script block"
    missing = [dist for dist in REQUIRED.values() if dist not in block.lower()]
    assert not missing, (
        f"PEP 723 dependencies omit {missing}. `uv run --script` reads ONLY this "
        "block, so an omitted dependency means the fallback interpreter cannot "
        "supply it — the fetch happens and buys nothing."
    )


def test_the_makefile_probe_tests_every_required_import(makefile_text: str):
    m = re.search(r"REGISTER_PYTHON\s*=.*?-c\s*'([^']+)'", makefile_text, re.S)
    assert m, "REGISTER_PYTHON probe not found or no longer uses a -c '<imports>' form"
    probe = m.group(1)
    imported = {n.strip() for n in probe.replace("import", "").split(",") if n.strip()}
    missing = set(REQUIRED) - imported
    assert not missing, (
        f"the REGISTER_PYTHON probe checks {sorted(imported)} but the tool also "
        f"needs {sorted(missing)}. A probe that checks one of two dependencies "
        "reports on the half it looked at, and selects a degraded interpreter as good."
    )


def test_the_degraded_remedy_is_not_the_command_that_emitted_it(tool_text: str):
    """The fix a warning names must differ from what the user just ran.

    `register-claim` and `register-release` expand the same REGISTER_PYTHON, so
    naming one as the other's remedy is a loop. This is the defect, not a wording
    nit: the notice was self-referential on BOTH targets, every time.
    """
    idx = tool_text.find("DEGRADED - pydantic")
    assert idx != -1, "the pydantic DEGRADED notice is gone; update or drop this test"
    message = tool_text[idx: idx + 1200]
    assert "register-claim" not in message, (
        "the DEGRADED notice still points at `register-claim`, which expands the "
        "same REGISTER_PYTHON as register-release — the remedy is the thing that "
        "produced the warning"
    )
    assert any(word in message for word in ("install", "uv")), (
        "the notice should name an action that changes the outcome (install the "
        "dependency, or install uv so the PEP 723 fallback can)"
    )


def test_both_register_targets_use_the_same_selected_interpreter(makefile_text: str):
    """NEGATIVE CONTROL for the test above.

    The claim "register-claim is not a remedy" rests on both targets sharing one
    interpreter variable. If they ever stop sharing it, the old message becomes
    true again and the test above would be wrong to forbid it. Pin the premise.
    """
    users = re.findall(r"^\t@?\$\(REGISTER_PYTHON\)\s+tools/register_append\.py\s+(\w+)",
                       makefile_text, re.M)
    assert {"claim", "release"} <= set(users), (
        f"expected both claim and release to invoke $(REGISTER_PYTHON); found {users}. "
        "If they now select interpreters differently, revisit the remedy wording."
    )


def test_import_names_and_distribution_names_are_not_confused(tool_text: str):
    """`import yaml` comes from the `pyyaml` distribution.

    A probe written as `import pyyaml`, or a PEP 723 block listing `yaml`, both
    look right and both fail — in opposite directions and only at runtime.
    """
    block = _pep723_block(tool_text).lower()
    assert "pyyaml" in block, "PEP 723 must name the DISTRIBUTION (pyyaml)"
    assert not re.search(r'"yaml"|\'yaml\'', block), (
        "PEP 723 lists `yaml` as a distribution; the distribution is `pyyaml` "
        "and installing `yaml` gets an unrelated package"
    )


# ---------------------------------------------------------------------------
# THE PATTERN, not just the one target.
#
# `make -C pmoves cipher-identity` had the SAME defect and it was found by
# running it: a bare $(PYTHON) with no PyYAML reported `signing card: unknown`
# for an agent whose card is active and present. A tool that cannot read the
# card file reports on its own inability, in the same shape as a real verdict.
#
#   1. every tool declares its third-party deps in a PEP 723 block
#   2. every target selects an interpreter that SATISFIES that declaration
#   3. the fallback is `uv run --script`, which reads the block
#
# $(PYTHON) answers "is there an interpreter". That is a different question from
# "can it import what this tool needs", and only the second decides whether the
# tool can do its job.
# ---------------------------------------------------------------------------

YAML_TOOLS = {
    "cipher_identity.py": "PYTHON_YAML",
    "register_append.py": "REGISTER_PYTHON",
}


def test_yaml_reading_tools_declare_pyyaml():
    missing = []
    for name in YAML_TOOLS:
        path = REPO_ROOT / "pmoves" / "tools" / name
        if not path.is_file():
            continue
        if "pyyaml" not in _pep723_block(path.read_text(encoding="utf-8")).lower():
            missing.append(name)
    assert not missing, (
        f"{missing} import yaml but declare no PEP 723 dependency, so "
        "`uv run --script` cannot supply it and the tool degrades instead"
    )


def test_targets_running_yaml_tools_use_a_yaml_capable_selector(makefile_text: str):
    bad = []
    for name, selector in YAML_TOOLS.items():
        for line in makefile_text.splitlines():
            if name not in line or not line.startswith("\t"):
                continue
            if "$(%s)" % selector not in line:
                bad.append(f"{line.strip()[:88]}  (expected $({selector}))")
    assert not bad, (
        "these recipes run a yaml-reading tool through an interpreter that was "
        "never checked for yaml:\n  " + "\n  ".join(bad) +
        "\nMeasured: cipher-identity reported `signing card: unknown` for a card "
        "that is present and active, because $(PYTHON) here has no PyYAML."
    )


def test_the_selector_actually_probes_yaml(makefile_text: str):
    """NEGATIVE CONTROL: naming a variable PYTHON_YAML does not make it one."""
    m = re.search(r"PYTHON_YAML\s*=.*?-c\s*'([^']+)'", makefile_text, re.S)
    assert m, "PYTHON_YAML is not defined as a probe over an import list"
    assert "yaml" in m.group(1), (
        f"PYTHON_YAML probes {m.group(1)!r}, which does not include yaml — the "
        "name would be the only thing guaranteeing the property"
    )
