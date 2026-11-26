"""skills_parity reports what each harness can see; it never guesses a directory."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _mod():
    path = REPO_ROOT / "pmoves" / "tools" / "skills_parity.py"
    spec = importlib.util.spec_from_file_location("skills_parity", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["skills_parity"] = module
    spec.loader.exec_module(module)
    return module


def test_the_seven_overlaid_harnesses_each_have_a_skills_dir():
    m = _mod()
    dirs, _ = m.harness_dirs()
    assert set(dirs) == {
        "claude-code", "codex", "opencode", "kimi-code-cli", "kilo", "crush", "hermes-agent",
    }
    assert dirs["claude-code"] == ".claude/skills"
    # the cross-agent dir three harnesses share; Claude Code does not read it
    assert dirs["codex"] == dirs["opencode"] == dirs["kimi-code-cli"] == ".agents/skills"


def test_live_table_parses_when_the_submodule_is_populated(tmp_path):
    m = _mod()
    ts = tmp_path / "agents.ts"
    ts.write_text(
        "  codex: {\n    name: 'codex',\n    displayName: 'Codex',\n"
        "    skillsDir: '.agents/skills',\n  },\n"
        "  kilo: {\n    name: 'kilo',\n    skillsDir: '.kilocode/skills',\n  },\n",
        encoding="utf-8",
    )
    live = m.live_dirs(ts)
    assert live == {"codex": ".agents/skills", "kilo": ".kilocode/skills"}
    assert m.live_dirs(tmp_path / "absent.ts") == {}


def test_report_is_honest_about_gaps_and_harness_only_skills(tmp_path, monkeypatch):
    m = _mod()
    (tmp_path / ".claude" / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "alpha" / "SKILL.md").write_text("x")
    (tmp_path / ".claude" / "skills" / "beta").mkdir()
    (tmp_path / ".claude" / "skills" / "beta" / "SKILL.md").write_text("x")
    (tmp_path / ".agents" / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "alpha" / "SKILL.md").write_text("x")
    (tmp_path / ".kilocode" / "skills" / "kilo-only").mkdir(parents=True)
    (tmp_path / ".kilocode" / "skills" / "kilo-only" / "SKILL.md").write_text("x")
    # a dir without SKILL.md is not a skill
    (tmp_path / ".agents" / "skills" / "not-a-skill").mkdir()
    monkeypatch.setattr(m, "AGENTS_TS", tmp_path / "missing.ts")
    report = m.build_report(tmp_path)
    assert report["canonical_count"] == 2
    assert report["harnesses"]["codex"]["present"] == ["alpha"]
    assert report["harnesses"]["codex"]["missing"] == ["beta"]
    assert report["harnesses"]["kilo"]["harness_only"] == ["kilo-only"]
    assert report["harnesses"]["crush"]["dir_exists"] is False
    assert report["gaps"]["crush"] == ["alpha", "beta"]
    assert any("pinned table" in w for w in report["warnings"])


def test_strict_mode_fails_on_a_gap_and_plain_mode_does_not(capsys):
    m = _mod()
    rc_plain = m.main([])
    assert rc_plain == 0
    out = capsys.readouterr().out
    assert "canonical: .claude/skills" in out
    report = m.build_report()
    rc_strict = m.main(["--strict"])
    assert rc_strict == (1 if report["gaps"] else 0)
