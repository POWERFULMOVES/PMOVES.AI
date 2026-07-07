"""Tests for pmoves/tools/pr_hedge_trim.py review-comment classification.

Regression guard for the severity-badge routing fix: CodeRabbit 🟠 Major /
🔴 Critical / ⚠️ Potential-issue and Codex P0/P1/P2 badges must classify as
`actionable`, not fall through to the `nitpick` default; CodeRabbit's 🧹 Nitpick
TYPE marker must stay `nitpick` even when the body contains actionable keywords.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

pr_hedge_trim = pytest.importorskip("pr_hedge_trim")
classify_comment = pr_hedge_trim.classify_comment

MAJOR = "\U0001f7e0"      # 🟠
MINOR = "\U0001f7e1"      # 🟡
CRIT = "\U0001f534"       # 🔴
NIT = "\U0001f9f9"        # 🧹


@pytest.mark.parametrize(
    "body,expected",
    [
        # CodeRabbit high-severity markers -> actionable (were defaulting to nitpick).
        (f"_Functional Correctness_ | _{MAJOR} Major_ | _Quick win_ **serve fallback never fires.**", "actionable"),
        (f"_Maintainability_ | _{MAJOR} Major_ | _Heavy lift_ **Preserve bootstrap lanes.**", "actionable"),
        (f"_Security_ | _{CRIT} Critical_ **secret leaked in log.**", "actionable"),
        ("_⚠️ Potential issue_ | _Minor_ **File handle opened without context manager.**", "actionable"),
        # Codex severity badges (image alt-text) -> actionable.
        ("**![P1 Badge](x)** Add the matching agent signature.", "actionable"),
        ("**![P2 Badge](x)** Refresh the audit seed-count.", "actionable"),
        ("**![P0 Badge](x)** hard blocker.", "actionable"),
        # CodeRabbit Nitpick TYPE marker is authoritative even over actionable keywords.
        (f"_{NIT} Nitpick_ | _{MINOR} Minor_ **Add a language tag to the fenced block.**", "nitpick"),
        (f"_{NIT} Nitpick_ this variable name is missing a prefix and must be renamed", "nitpick"),
        # Severity badge wins over the word "nitpick" appearing in prose (Codex #1985 P2).
        (f"_Functional Correctness_ | _{MAJOR} Major_ this is more than a nitpick — fix the crash", "actionable"),
        ("**![P1 Badge](x)** not a nitpick: the token never reaches Agent Zero", "actionable"),
        # Plain Minor with no Potential-issue/severity marker defaults to nitpick.
        (f"_Maintainability_ | _{MINOR} Minor_ tidy the wording", "nitpick"),
        # Author replies.
        ("This is a false positive — the schema already allows it.", "false-positive"),
        ("Intentional — this is a deliberate design decision, see rationale.", "design-decision"),
    ],
)
def test_classify_comment_severity_routing(body: str, expected: str) -> None:
    assert classify_comment(body, is_bot=True) == expected


def test_unmarked_bot_comment_defaults_to_nitpick() -> None:
    assert classify_comment("looks fine overall", is_bot=True) == "nitpick"


def test_unmarked_human_comment_defaults_to_actionable() -> None:
    assert classify_comment("please rename this", is_bot=False) == "actionable"
