"""pm-brv-check.sh — a missing ByteRover CLI must be announced, never silent.

Measured 2026-10-08 on knuckles: ``command -v brv`` printed nothing and no
launcher said so. The contract these tests hold:

* the function ALWAYS returns 0 (fail-open: a missing brv costs the context
  tree, not the launch);
* when brv is missing it produces a WARN line AND a prompt sentence, both
  naming the install route;
* the install route is the one ``pmoves/configs/cli_tools.yaml`` records, so
  ``make -C pmoves cli-check`` and the launcher cannot drift apart.

Hermetic: PATH is replaced with a stub directory, so the result does not depend
on whether this node happens to have brv installed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml
from pmoves.tools.bash_resolver import find_bash

REPO_ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = REPO_ROOT / "pmoves" / "scripts" / "pm-brv-check.sh"
CLI_MANIFEST = REPO_ROOT / "pmoves" / "configs" / "cli_tools.yaml"

PROBE = (
    '. "$1"; pm_brv_check; rc=$?; '
    'printf "rc=%s\\nOK=%s\\nLINE=%s\\nPROMPT=%s\\nHINT=%s\\n" '
    '"$rc" "$PM_BRV_OK" "$PM_BRV_LINE" "$PM_BRV_PROMPT" "$PM_BRV_INSTALL_HINT"'
)


def _run(path_dir: Path) -> dict[str, str]:
    bash = find_bash()
    if not bash:
        pytest.skip("no bash on this host")
    proc = subprocess.run(
        [bash, "-c", PROBE, "probe", str(FRAGMENT)],
        env={"PATH": str(path_dir), "HOME": str(path_dir)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stderr == "", f"fragment wrote to stderr itself: {proc.stderr!r}"
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        key, _, value = line.partition("=")
        out[key] = value
    return out


def test_missing_brv_is_loud_and_fail_open(tmp_path: Path) -> None:
    out = _run(tmp_path)  # empty PATH dir: no brv
    assert out["rc"] == "0", "a missing brv must never cost the launch"
    assert out["OK"] == "0"
    assert out["LINE"].startswith("WARN: brv=MISSING"), out["LINE"]
    assert out["HINT"] in out["LINE"], "the stderr line must name the install route"
    assert out["HINT"] in out["PROMPT"], "the prompt sentence must name the install route"


def test_present_brv_is_reported_quietly(tmp_path: Path) -> None:
    stub = tmp_path / "brv"
    stub.write_text("#!/bin/sh\necho stub\n")
    stub.chmod(0o755)
    out = _run(tmp_path)
    assert out["rc"] == "0"
    assert out["OK"] == "1"
    assert out["LINE"] == f"brv=present ({stub})"
    assert out["PROMPT"] == "", "a present brv must not add prompt text"


def test_install_hint_matches_cli_manifest() -> None:
    manifest = yaml.safe_load(CLI_MANIFEST.read_text(encoding="utf-8"))
    entry = manifest["host_clis"]["brv"]
    out = _run(Path(os.devnull).parent)  # /dev: no brv there
    assert entry["install"]["linux"] == out["HINT"], (
        "pm-brv-check.sh PM_BRV_INSTALL_HINT drifted from "
        "cli_tools.yaml host_clis.brv.install.linux"
    )
    assert entry["check"].split()[0] == "brv"
