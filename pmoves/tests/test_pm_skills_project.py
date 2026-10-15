"""pm-skills-project.sh — every harness sees every skill, and a failure is loud.

The contract these tests hold:

* the function ALWAYS returns 0 (fail-open: a failed projection costs the other
  harnesses their skills for the session, not the launch);
* the CLI is called with one `-a` per harness from the pinned list, `--copy`
  and the local `.claude/skills` source, telemetry disabled;
* the stamp is a content fingerprint of `.claude/skills`: an unchanged tree
  skips the call; an edited, added or DELETED skill, or FORCE=1, runs it again,
  and a deleted skill loses the copies this script projected (kilo review on
  #3351: an mtime stamp never sees a deletion); a failing CLI leaves no stamp
  and produces a WARN line;
* the harness list matches `pmoves/tools/skills_parity.py` when that tool is
  present, so the projector and the parity check cannot drift apart.

Hermetic: PM_SKILLS_CLI points at a stub that records its argv and can be told
to fail; PATH carries only the directory bash lives in (coreutils for the
fragment, bash for the stub's shebang) and never node or npx. Measured
2026-10-11: an empty PATH passes on Git Bash, which prepends /usr/bin on its
own, and fails on the Linux runner, where `#!/usr/bin/env bash` and `find`
then resolve nothing.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from pmoves.tools.bash_resolver import find_bash

REPO_ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = REPO_ROOT / "pmoves" / "scripts" / "pm-skills-project.sh"
PARITY = REPO_ROOT / "pmoves" / "tools" / "skills_parity.py"

PROBE = (
    '. "$1"; pm_skills_project "$2" "${3:-0}"; rc=$?; '
    'printf "rc=%s\\nOK=%s\\nLINE=%s\\n" "$rc" "$PM_SKILLS_OK" "$PM_SKILLS_LINE"'
)


def _stub(tmp_path: Path, fail: bool = False) -> Path:
    stub = tmp_path / "stub-cli"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$@" > "$STUB_ARGV"\n'
        'printf "%s\\n" "$PWD" > "$STUB_CWD"\n'
        'printf "%s|%s\\n" "${DISABLE_TELEMETRY:-}" "${DO_NOT_TRACK:-}" > "$STUB_ENV"\n'
        + ("exit 1\n" if fail else "exit 0\n"),
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".claude" / "skills" / "alpha").mkdir(parents=True)
    (root / ".claude" / "skills" / "alpha" / "SKILL.md").write_text("x")
    (root / ".claude" / "skills" / "beta").mkdir()
    (root / ".claude" / "skills" / "beta" / "SKILL.md").write_text("x")
    return root


def _run(tmp_path: Path, root: Path, stub: Path | None, force: str = "0") -> dict[str, str]:
    bash = find_bash()
    if not bash:
        pytest.skip("no bash on this host")
    env = {
        "PATH": os.pathsep.join([str(tmp_path / "empty-path"), str(Path(bash).parent)]),
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "STUB_ARGV": str(tmp_path / "argv"),
        "STUB_CWD": str(tmp_path / "cwd"),
        "STUB_ENV": str(tmp_path / "envrec"),
    }
    if stub is not None:
        env["PM_SKILLS_CLI"] = str(stub)
    (tmp_path / "empty-path").mkdir(exist_ok=True)
    proc = subprocess.run(
        [bash, "-c", PROBE, "probe", str(FRAGMENT), str(root), force],
        env=env, capture_output=True, text=True, check=False,
    )
    assert proc.stderr == "", f"fragment wrote to stderr itself: {proc.stderr!r}"
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        key, _, value = line.partition("=")
        out[key] = value
    return out


def test_projects_with_one_agent_flag_per_harness_and_no_telemetry(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    out = _run(tmp_path, root, _stub(tmp_path))
    assert out["rc"] == "0"
    assert out["OK"] == "1", out["LINE"]
    assert out["LINE"].startswith("skills=projected (2 skills"), out["LINE"]
    argv = (tmp_path / "argv").read_text().splitlines()
    assert argv[:2] == ["add", "./.claude/skills"]
    assert "--copy" in argv and "-y" in argv
    agents = [argv[i + 1] for i, a in enumerate(argv) if a == "-a"]
    assert agents == ["codex", "opencode", "kimi-code-cli", "kilo", "crush", "hermes-agent"]
    assert (tmp_path / "cwd").read_text().strip().replace("\\", "/").endswith("/repo")
    assert (tmp_path / "envrec").read_text().strip() == "1|1"
    assert (root / ".agents" / ".pmoves-skills-stamp").is_file()


def test_unchanged_tree_skips_and_edit_or_force_reruns(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    stub = _stub(tmp_path)
    assert _run(tmp_path, root, stub)["OK"] == "1"
    stamp = root / ".agents" / ".pmoves-skills-stamp"
    assert stamp.read_text().splitlines()[1:] == ["alpha", "beta"], "stamp lists the projected names"
    (tmp_path / "argv").unlink()
    out = _run(tmp_path, root, stub)
    assert out["OK"] == "2", out["LINE"]
    assert not (tmp_path / "argv").exists(), "an unchanged tree must not call the CLI"
    # FORCE runs regardless of the stamp
    assert _run(tmp_path, root, stub, force="1")["OK"] == "1"
    # an edited source file runs again, even with its mtime pushed into the past
    (tmp_path / "argv").unlink()
    skill = root / ".claude" / "skills" / "beta" / "SKILL.md"
    skill.write_text("changed")
    past = time.time() - 3600
    os.utime(skill, (past, past))
    assert _run(tmp_path, root, stub)["OK"] == "1"
    assert (tmp_path / "argv").exists()
    # a new skill runs again too
    (tmp_path / "argv").unlink()
    (root / ".claude" / "skills" / "gamma").mkdir()
    (root / ".claude" / "skills" / "gamma" / "SKILL.md").write_text("x")
    out = _run(tmp_path, root, stub)
    assert out["OK"] == "1" and out["LINE"].startswith("skills=projected (3 skills"), out["LINE"]


def test_deleted_skill_reruns_and_removes_only_its_own_projected_copies(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    stub = _stub(tmp_path)
    assert _run(tmp_path, root, stub)["OK"] == "1"
    # simulate what the real CLI leaves behind: a copy per harness dir, plus
    # content this script never projected and must not touch
    for rel in (".agents/skills", ".kilocode/skills", ".crush/skills", ".hermes/skills"):
        for name in ("alpha", "beta"):
            (root / rel / name).mkdir(parents=True)
            (root / rel / name / "SKILL.md").write_text("copy")
    (root / ".kilocode" / "skills" / "kilocode-native").mkdir()
    (root / ".kilocode" / "skills" / "kilocode-native" / "SKILL.md").write_text("kilo's own")
    (root / ".agents" / "skills" / "beta-unrelated").mkdir()

    shutil.rmtree(root / ".claude" / "skills" / "beta")
    (tmp_path / "argv").unlink()
    out = _run(tmp_path, root, stub)
    assert out["OK"] == "1", out["LINE"]
    assert (tmp_path / "argv").exists(), "a deletion must re-run the CLI"
    assert out["LINE"] == (
        "skills=projected (1 skills -> codex, opencode, kimi-code-cli, kilo, crush, hermes-agent; 4 stale copies removed)"
    ), out["LINE"]
    for rel in (".agents/skills", ".kilocode/skills", ".crush/skills", ".hermes/skills"):
        assert not (root / rel / "beta").exists(), rel
        assert (root / rel / "alpha").is_dir(), rel
    assert (root / ".kilocode" / "skills" / "kilocode-native" / "SKILL.md").is_file()
    assert (root / ".agents" / "skills" / "beta-unrelated").is_dir()
    stamp = root / ".agents" / ".pmoves-skills-stamp"
    assert stamp.read_text().splitlines()[1:] == ["alpha"]
    # and the tree is fresh again afterwards
    (tmp_path / "argv").unlink()
    assert _run(tmp_path, root, stub)["OK"] == "2"


def test_failed_cli_is_loud_fail_open_and_leaves_no_stamp(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    out = _run(tmp_path, root, _stub(tmp_path, fail=True))
    assert out["rc"] == "0", "a failed projection must never cost the launch"
    assert out["OK"] == "0"
    assert out["LINE"].startswith("WARN: skills=FAILED"), out["LINE"]
    assert not (root / ".agents" / ".pmoves-skills-stamp").exists()


def test_no_cli_is_loud_and_names_the_build_route(tmp_path: Path) -> None:
    bash = find_bash()
    if bash and any(shutil.which(t, path=str(Path(bash).parent)) for t in ("node", "npx")):
        pytest.skip("node/npx share a directory with bash here; the NO-CLI branch cannot be isolated")
    root = _repo(tmp_path)
    out = _run(tmp_path, root, None)  # no PM_SKILLS_CLI, empty PATH, no built fork
    assert out["rc"] == "0"
    assert out["OK"] == "0"
    assert out["LINE"].startswith("WARN: skills=NO-CLI"), out["LINE"]
    assert "pnpm -C skills/PMOVES-skills" in out["LINE"]


def test_missing_source_dir_is_a_skip(tmp_path: Path) -> None:
    root = tmp_path / "bare"
    root.mkdir()
    out = _run(tmp_path, root, _stub(tmp_path))
    assert out["rc"] == "0" and out["OK"] == "0"
    assert out["LINE"].startswith("skills=SKIP")


def test_harness_list_matches_skills_parity_when_present() -> None:
    text = FRAGMENT.read_text(encoding="utf-8")
    m = re.search(r'^PM_SKILLS_AGENTS="([^"]+)"', text, re.M)
    assert m, "PM_SKILLS_AGENTS not found"
    projected = set(m.group(1).split())
    if not PARITY.is_file():
        pytest.skip("skills_parity.py not in this checkout (lands with #3347)")
    pinned = set(re.findall(r'^\s+"([a-z0-9-]+)":\s+"\.[a-z]+/skills"', PARITY.read_text(encoding="utf-8"), re.M))
    assert pinned - {"claude-code"} == projected, (
        "pm-skills-project.sh PM_SKILLS_AGENTS drifted from skills_parity.py PINNED_DIRS"
    )
