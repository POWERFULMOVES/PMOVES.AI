"""The installed wrapper must be a DELEGATE, and drift must be reportable.

WHAT WENT WRONG (measured on Z890, 2026-09-17):
``~/.local/bin/claude-pmoves.bat`` was a frozen COPY of the tracked template,
written 2026-08-15. By September the tracked template had gained the canonical
launcher hand-off (env.shared + ``--mcp-config`` roster) and the node-identity
binding; the copy still ran ``claude --agent delivery-agent`` directly. So every
session on the repo's infrastructure node launched credless, roster-less and
identity-less -- and launched *successfully*, which is why it went a month
unnoticed.

Two independent defects, one test file:

1. Windows installed a copy while Unix installed a delegate. A copy cannot be
   fixed; fixing the template has to be enough.
2. ``--check`` validated host CLIs only, so nothing on the node could report a
   stale shim. The doctor was blind to the exact artifact it installs.

These tests are the guard. The first class is checked against ALL SEVEN
templates, not just claude-pmoves: the installer loops over all of them, so a
delegate that only one template understood would leave the other six resolving
their repo root to the literal placeholder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))

import install_tools  # noqa: E402

WINDOWS_TEMPLATES = sorted((REPO_ROOT / "pmoves" / "scripts" / "windows").glob("*.bat"))


def test_there_are_windows_templates_to_check():
    """Guard the guard: a bad glob would make every parametrised test vacuous."""
    assert len(WINDOWS_TEMPLATES) >= 7, WINDOWS_TEMPLATES


@pytest.mark.parametrize("template", WINDOWS_TEMPLATES, ids=lambda p: p.name)
def test_every_windows_template_honours_the_delegate_root(template):
    """The delegate passes the root in PMOVES_LAUNCHER_ROOT; the template must
    prefer it over its own baked placeholder, or the hand-off is inert."""
    text = template.read_text(encoding="utf-8")
    assert install_tools.REPO_ROOT_PLACEHOLDER in text, (
        f"{template.name}: lost its baked-root placeholder, so a copy-install "
        "would resolve nothing"
    )
    assert 'if defined PMOVES_LAUNCHER_ROOT set "REPO_ROOT=%PMOVES_LAUNCHER_ROOT%"' in text, (
        f"{template.name}: does not honour the delegate's root. The installed "
        "shim would set it and this file would ignore it, leaving REPO_ROOT as "
        "the literal __PMOVES_REPO_ROOT__ text."
    )


@pytest.mark.parametrize("template", WINDOWS_TEMPLATES, ids=lambda p: p.name)
def test_the_root_assignment_is_not_in_a_parenthesised_block(template):
    """cmd.exe expands %VAR% while PARSING a parenthesised block, so a root
    containing `)` -- C:\\Program Files (x86) -- closes the block early and the
    script dies with "was unexpected at this time."  Two plain `set`s, not an
    if/else. Same trap the identity reason strings hit in claude-pmoves.bat."""
    for line in template.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("rem"):
            continue
        if "PMOVES_LAUNCHER_ROOT" in stripped:
            assert "(" not in stripped and ")" not in stripped, (
                f"{template.name}: parenthesised root assignment: {stripped!r}"
            )


def test_the_windows_delegate_is_a_delegate_not_a_copy():
    """It must hand off to the tracked path, not carry the template's logic."""
    template = REPO_ROOT / "pmoves" / "scripts" / "windows" / "claude-pmoves.bat"
    delegate = install_tools.WINDOWS_DELEGATE.format(
        root=str(REPO_ROOT), target=str(template), command="claude-pmoves"
    )
    assert f'call "{template}"' in delegate, "the delegate does not call the template"
    assert f'set "PMOVES_LAUNCHER_ROOT={REPO_ROOT}"' in delegate
    # The giveaway that it is not a copy: none of the template's own machinery.
    assert "node_identity.py" not in delegate, (
        "the delegate carries the template's identity logic -- that is a copy, "
        "and a copy is what went stale"
    )
    assert "DEFAULT_AGENT" not in delegate, "delegate carries agent selection"
    assert len(delegate) < len(template.read_text(encoding="utf-8")), (
        "a delegate that is not dramatically smaller than its target is a copy"
    )


def test_the_delegate_says_the_template_is_missing_without_a_block():
    """Fail loudly if the repo moved, and do it with goto: the baked root may
    contain parentheses, which a parenthesised if would break on."""
    delegate = install_tools.WINDOWS_DELEGATE.format(
        root=r"C:\Program Files (x86)\pmoves",
        target=r"C:\Program Files (x86)\pmoves\t.bat",
        command="claude-pmoves",
    )
    assert "goto missing" in delegate and ":missing" in delegate
    assert "install-tools" in delegate, "the fix is not named in the failure path"
    for line in delegate.splitlines():
        if line.strip().startswith("if "):
            assert line.rstrip().endswith("goto missing"), (
                f"guard uses a block, not a goto: {line!r}"
            )


def test_the_drift_doctor_flags_a_stale_shim(tmp_path):
    """Positive control. Without this, check_installed_wrappers could return 0
    unconditionally and every test above would still pass -- which is exactly
    the shape of the bug it exists to catch."""
    expected = install_tools.expected_wrappers(tmp_path)
    assert expected, "no wrappers expected; the fixture proves nothing"

    # A fresh install is clean.
    for dest, (content, _label) in expected.items():
        dest.write_text(content, encoding="utf-8")
    assert install_tools.check_installed_wrappers(tmp_path) == 0

    # The real Z890 artifact: a shim that calls raw `claude`.
    victim = next(iter(sorted(expected)))
    victim.write_text("@echo off\nclaude --agent delivery-agent %*\n", encoding="utf-8")
    assert install_tools.check_installed_wrappers(tmp_path) == 1, (
        "a shim running raw `claude` was reported as OK"
    )


def test_line_endings_alone_are_not_drift(tmp_path):
    """The installer writes CRLF on Windows; a checkout or editor round-trip may
    change only the endings. Reporting that as STALE would train operators to
    ignore the doctor, which is worse than not having one."""
    expected = install_tools.expected_wrappers(tmp_path)
    for dest, (content, _label) in expected.items():
        dest.write_text(content.replace("\r\n", "\n").replace("\n", "\r\n"),
                        encoding="utf-8", newline="")
    assert install_tools.check_installed_wrappers(tmp_path) == 0


def test_absent_is_a_note_not_an_error(tmp_path):
    """Nothing installed is a legitimate state (a fresh clone). Only a shim that
    EXISTS and is wrong is an error -- that is the one that runs and lies."""
    assert install_tools.check_installed_wrappers(tmp_path) == 0


def test_installer_and_doctor_share_one_definition():
    """If the doctor computed expectations its own way it would eventually bless
    a shim the installer would rewrite. install_windows/install_unix must both
    source their content from expected_wrappers()."""
    src = Path(install_tools.__file__).read_text(encoding="utf-8")
    body = src.split("def install_windows", 1)[1].split("\ndef ", 1)[0]
    assert "expected_wrappers(" in body, (
        "install_windows no longer uses expected_wrappers(); the doctor can drift"
    )


@pytest.mark.skipif(os.name != "nt", reason="windows install path")
def test_a_windows_install_round_trips_clean(tmp_path):
    install_tools.install_windows(tmp_path, dry_run=False)
    assert install_tools.check_installed_wrappers(tmp_path) == 0
    text = (tmp_path / "claude-pmoves.bat").read_text(encoding="utf-8")
    assert "node_identity.py" not in text, "installed a copy, not a delegate"
