"""kimi-pmoves and kilo-pmoves must start the program they are named for.

Both launchers failed on the node that reported them, for reasons that only
show up when the real CLI parses the argv:

- kimi-pmoves passed `--config-file` / `--mcp-config-file`, flags that exist
  only in the legacy kimi-cli. Kimi Code (>= 2.x) exits with
  "error: unknown option '--config-file'" before any session starts.
- kilo-pmoves exec'd `opencode --config <claws file>`: the wrong program, a flag
  neither program has, and a positional node argument that swallowed `--version`.
- Neither changed directory, so a session started from a sibling checkout ran
  against that checkout's project files.

Each test puts a stub CLI first on PATH that records its argv and cwd, runs the
tracked launcher from a directory outside the repo, and asserts on what the
stub saw.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pmoves.tools.bash_resolver import resolve_bash  # never System32's WSL stub

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "pmoves" / "scripts"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

_STUB = """#!/usr/bin/env bash
if [ "${1:-}" = "--help" ]; then
  printf '%s\\n' "$HELP_TEXT"
  exit 0
fi
pwd -P > "$STUB_LOG.cwd"
printf '%s\\n' "$@" > "$STUB_LOG.argv"
"""


def _stub(bin_dir: Path, name: str) -> None:
    path = bin_dir / name
    path.write_text(_STUB, encoding="utf-8")
    path.chmod(0o755)


def _run(
    launcher: str,
    args: list[str],
    tmp_path: Path,
    stub: str,
    help_text: str = "",
    extra_env: dict[str, str] | None = None,
):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir, stub)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    log = tmp_path / "stub"
    env = {
        "PATH": f"{bin_dir}:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "STUB_LOG": str(log),
        "HELP_TEXT": help_text,
        **(extra_env or {}),
    }
    proc = subprocess.run(
        [resolve_bash(), str(SCRIPTS / launcher), *args],
        cwd=outside,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    argv_file = Path(f"{log}.argv")
    argv = argv_file.read_text().splitlines() if argv_file.exists() else None
    cwd_file = Path(f"{log}.cwd")
    cwd = cwd_file.read_text().strip() if cwd_file.exists() else None
    return proc, argv, cwd


def test_kimi_code_gets_no_legacy_flags_and_runs_in_checkout(tmp_path: Path) -> None:
    proc, argv, cwd = _run(
        "kimi-pmoves.sh", ["-p", "hi"], tmp_path, "kimi",
        help_text="Usage: kimi [options] [command]\n  -p, --prompt <prompt>",
    )
    assert argv == ["-p", "hi"], proc.stderr
    assert cwd == str(REPO_ROOT.resolve())


def test_legacy_kimi_cli_still_gets_project_config(tmp_path: Path) -> None:
    if not (REPO_ROOT / ".kimi" / "config.toml").is_file():
        pytest.skip(".kimi/config.toml not present in this checkout")
    proc, argv, _ = _run(
        "kimi-pmoves.sh", ["-p", "hi"], tmp_path, "kimi",
        help_text="--config-file FILE  Config TOML/JSON",
    )
    assert argv is not None, proc.stderr
    assert argv[:2] == ["--config-file", str(REPO_ROOT / ".kimi" / "config.toml")]
    assert argv[-2:] == ["-p", "hi"]


def test_kilo_launcher_execs_kilo_with_args_untouched(tmp_path: Path) -> None:
    proc, argv, cwd = _run("kilo-pmoves.sh", ["--version"], tmp_path, "kilo")
    assert argv == ["--version"], proc.stderr
    assert cwd == str(REPO_ROOT.resolve())


def test_kilo_launcher_drops_legacy_node_argument(tmp_path: Path) -> None:
    proc, argv, _ = _run("kilo-pmoves.sh", ["5090", "run", "x"], tmp_path, "kilo")
    assert argv == ["run", "x"], proc.stderr
    assert "node argument '5090' ignored" in proc.stderr


def test_keep_cwd_opt_out(tmp_path: Path) -> None:
    proc, _, cwd = _run(
        "kilo-pmoves.sh", [], tmp_path, "kilo",
        extra_env={"PMOVES_LAUNCH_KEEP_CWD": "1"},
    )
    assert cwd == str((tmp_path / "elsewhere").resolve()), proc.stderr


def test_kimi_empty_help_is_refused_not_guessed(tmp_path: Path) -> None:
    """`kimi --help` printing nothing (broken install, shim) must not fall through
    into either branch: a silent Kimi Code launch would drop the legacy config,
    a silent legacy launch would die on `--config-file`. Explicit exit 1."""
    proc, argv, _ = _run("kimi-pmoves.sh", ["-p", "hi"], tmp_path, "kimi", help_text="")
    assert proc.returncode == 1, proc.stderr
    assert argv is None, "kimi must not be exec'd when --help is empty"
    assert "cannot tell Kimi Code from the legacy kimi-cli" in proc.stderr


def test_kimi_help_mentioning_the_flag_in_prose_is_not_legacy(tmp_path: Path) -> None:
    """The match is anchored to a flag-definition line. A help text that merely
    MENTIONS --config-file (deprecation note, example) is still Kimi Code."""
    proc, argv, _ = _run(
        "kimi-pmoves.sh", ["-p", "hi"], tmp_path, "kimi",
        help_text="Usage: kimi [options]\n  -p, --prompt <prompt>\nNote: the old --config-file flag was removed in 2.0",
    )
    assert argv == ["-p", "hi"], proc.stderr


_CWD_BLOCK = re.compile(r"ROOT_P=.*?\nesac\n", re.S)


def test_cwd_binding_blocks_are_twins() -> None:
    """Both launchers carry the cwd binding INLINE on purpose (it must hold on a
    checkout with no fragments). The price of a copied block is drift; this test
    is what makes the copy non-driftable: byte-identical modulo the tag."""
    blocks = {}
    for name in ("kimi-pmoves.sh", "kilo-pmoves.sh"):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        m = _CWD_BLOCK.search(text)
        assert m, f"{name}: cwd binding block not found"
        tag = name.removesuffix(".sh")
        blocks[name] = m.group(0).replace(f"[{tag}]", "[TAG]")
    assert blocks["kimi-pmoves.sh"] == blocks["kilo-pmoves.sh"], (
        "cwd binding blocks drifted between kimi-pmoves.sh and kilo-pmoves.sh"
    )
