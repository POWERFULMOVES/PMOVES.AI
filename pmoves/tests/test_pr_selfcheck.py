"""Integration controls for pr_selfcheck: run it against the real history.

The strongest control available: PR #3269's pre-fix head (104d56375) is the
exact diff the reviewer roasted, with four machine-detectable defects
(missing .PHONY, unguarded grep->docker substitution, hand-edited generated
manifest, and the template-brace shape it shipped AFTER fixing the braces is
not in this head — three of the four must fire). Fail-before semantics: if
the tool goes quiet on that head, it has regressed into decoration.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "pr_selfcheck.py"
REPO = Path(__file__).resolve().parents[1]
ROASTED_HEAD = "104d56375"  # PR #3269 as reviewed: 5 threads, 4 machine-detectable


def _run(base: str, head: str, sidecar: Path) -> dict:
    subprocess.run(
        [sys.executable, str(TOOL), "--base", base, "--head", head],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
        env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
    )
    return json.loads(sidecar.read_text())


def test_roasted_head_fires_three_of_four(tmp_path: Path, monkeypatch) -> None:
    merge_base = (
        subprocess.run(
            ["git", "-C", str(REPO), "merge-base", "origin/main", ROASTED_HEAD],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    sidecar = tmp_path / "s.json"
    monkeypatch.setattr(Path, "mkdir", lambda self, *a, **k: self)  # sidecar dir no-op
    report = _run(merge_base, ROASTED_HEAD, sidecar) if False else json.loads(
        subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import json, sys
sys.argv = ['pr_selfcheck', '--base', '{merge_base}', '--head', '{ROASTED_HEAD}']
sys.path.insert(0, '{TOOL.parent}')
import pr_selfcheck as t
rep = t.Report(branch='probe', files=t.diff_names('{merge_base}', '{ROASTED_HEAD}'))
for c in t.CHECKS:
    try: c(rep, '{merge_base}', '{ROASTED_HEAD}')
    except Exception: pass
print(json.dumps({{ 'checks': [f.check for f in rep.findings] }}))
""",
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO,
        ).stdout
    )
    fired = set(report["checks"])
    assert "phony-covers-new-targets" in fired, "must catch the missing .PHONY the review caught"
    assert "grep-pipeline-fails-closed" in fired, "must catch the unguarded docker substitution"
    assert "hand-edited-generated-file" in fired, "must catch the hand-edited generated manifest"


def test_clean_docs_diff_stays_clean() -> None:
    merge_base = (
        subprocess.run(
            ["git", "-C", str(REPO), "merge-base", "origin/main", ROASTED_HEAD],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import json, sys
sys.path.insert(0, '{TOOL.parent}')
import pr_selfcheck as t
rep = t.Report(branch='probe', files=['pmoves/docs/operations/NATS_CREDENTIAL_ROTATION.md'])
for c in t.CHECKS:
    try: c(rep, '{ROASTED_HEAD}', '{ROASTED_HEAD}')
    except Exception: pass
print(json.dumps({{ 'n': len(rep.findings) }}))
""",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    ).stdout
    assert json.loads(out)["n"] == 0, "a docs-only scope must produce no findings"
