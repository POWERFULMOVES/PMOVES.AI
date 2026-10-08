"""Integration controls for pr_selfcheck: run it against real history.

Two controls, both against the actual git history of this repository:

1. FAIL-BEFORE: PR #3269's as-reviewed head (104d56375) is the exact diff a
   reviewer roasted, carrying machine-detectable defects. If the tool goes
   quiet on that head it has regressed into decoration.
2. NO-FALSE-POSITIVE: a real docs-only merge from origin/main (bec8dbfec —
   #3264, TAC doc follow-ups) through the REAL diff path (merge-base..sha),
   not an empty-diff shortcut. The first version's "control" ran base==head
   and could not fail no matter what the tool did (PR #3278 thread 6).

Plus a unit control for the template check (PR #3278 threads 1+2): the raw
'{ users }' shape — spaces inside braces — must fire, and an honest strict
field must not.
"""
from __future__ import annotations

import re
import subprocess
import sys
from ast import parse, walk
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import pr_selfcheck as t  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ROASTED_HEAD = "104d56375"  # PR #3269 as reviewed: 5 threads, machine-detectable subset
DOCS_ONLY = "bec8dbfec"    # merge of #3264 (TAC doc follow-ups), docs-only


def _merge_base(sha: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), "merge-base", "origin/main", sha],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _probe(base: str, head: str) -> list[str]:
    rep = t.Report(branch="probe", files=[])
    for check in t.CHECKS:
        check(rep, base, head)
    return [f.check for f in rep.findings]


def test_roasted_head_fires_the_real_defects() -> None:
    fired = _probe(_merge_base(ROASTED_HEAD), ROASTED_HEAD)
    assert "phony-covers-new-targets" in fired
    assert "grep-pipeline-fails-closed" in fired
    assert "hand-edited-generated-file" in fired


def test_docs_only_merge_stays_clean() -> None:
    # a REAL docs-only diff through the real path; reminder-class findings
    # are allowed, no fix-pattern finding may fire
    fired = _probe(_merge_base(DOCS_ONLY), DOCS_ONLY)
    for noise in (
        "format-braces-in-template",
        "phony-covers-new-targets",
        "grep-pipeline-fails-closed",
        "hand-edited-generated-file",
        "line-number-citation",
    ):
        assert noise not in fired, fired


def test_template_check_raw_spaces_fire_strict_fields_do_not() -> None:
    # PR #3278 thread 2: the RAW '{ users }' (spaces inside braces) must be
    # the shape that fires; '{users}' is a strict field and must not. The
    # first version normalized the spaces away and waved through the exact
    # burglar the check was bred to catch.
    src = 'CONF_TEMPLATE = """line {users} done { users } tail"""\n'
    flagged: list[str] = []
    for node in walk(parse(src)):
        if not isinstance(node, t.ast.Assign):
            continue
        if not any(
            isinstance(x, t.ast.Name) and x.id == "CONF_TEMPLATE" for x in node.targets
        ):
            continue
        body = node.value.value
        for token in re.findall(r"\{[^{}\n]*\}", body):
            inner = token[1:-1]
            if not re.fullmatch(r"[a-zA-Z_]\w*(!r|!s|:[^{}]*)?|", inner):
                flagged.append(token)
    assert flagged == ["{ users }"], flagged
