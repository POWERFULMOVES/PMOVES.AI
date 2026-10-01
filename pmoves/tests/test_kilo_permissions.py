"""kilo.json permission rules, fed through a port of Kilo's own resolver.

Kilo (Kilo-Org/kilocode@6fd9b7b) resolves a tool call like this:
  * packages/opencode/src/util/wildcard.ts `match`: `*` -> `.*` (it crosses
    `/` and spaces), `?` -> `.`, and a trailing ` *` is optional, so `ls *`
    matches `ls`;
  * packages/opencode/src/permission/index.ts `evaluate`: the LAST rule whose
    permission and pattern both match wins (config order). There is no
    deny-wins rule: a deny only beats an allow that comes before it;
  * packages/opencode/src/tool/shell.ts: each parsed command is checked on its
    own text, redirects included. Operators inside quotes are masked to `_`.
These commands are plain enough that their text IS the checked pattern.

The deny cases were also replayed through the real @kilocode/cli 7.6.2 under
`kilo run --auto` (a stub model issuing the bash calls): every one was refused
by the rule this port names (#3246).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_KILO = Path(__file__).resolve().parents[2] / "kilo.json"


def _match(text: str, pattern: str) -> bool:
    escaped = re.sub(r"[.+^${}()|\[\]\\]", lambda m: "\\" + m.group(0), pattern)
    escaped = escaped.replace("*", ".*").replace("?", ".")
    if escaped.endswith(" .*"):
        escaped = escaped[:-3] + "( .*)?"
    return re.fullmatch(escaped, text, re.S) is not None


def _resolve(permission: str, target: str) -> str:
    rules = json.loads(_KILO.read_text(encoding="utf-8"))["permission"][permission]
    action = "ask"
    for pattern, rule in rules.items():  # dicts keep config order
        if _match(target, pattern):
            action = rule
    return action


def test_port_matches_kilo_documented_examples():
    # https://kilo.ai/docs/customize/agent-permissions, "Patterns"
    assert _match("git", "git *") and _match("git log --oneline", "git *")
    assert _match("git status", "git status *") and _match("git status -s", "git status *")
    assert not _match("gitx", "git *")


# Each of these executes a program or writes a file from inside a command
# that was auto-allowed before (#3246 review, P2-1).
ESCAPES_DENIED = [
    "rg --pre sh x",
    "rg --pre-glob '*.py' --pre ./evil x",
    "make -C pmoves register-status --eval=x",
    "make -C pmoves register-status -f evil.mk",
    "make -C pmoves register-status --file=evil.mk",
    "make -E 'all: ; id'",
    "git diff --output=/tmp/x",
    "git diff --ou=/tmp/x",
    "git log -p --output=x",
    "git show HEAD --output=x",
    "git branch -D main",
    "git branch -d feature",
    "git branch -f main HEAD~3",
    "git branch -m a b",
    "git branch -M a b",
    "git branch --delete feature",
    "git branch --force main HEAD~1",
    "git branch --move a b",
    "git stash",
    "git stash pop",
    "env",
    "env | grep KEY",
    "printenv",
    "printenv Z_AI_API_KEY",
    "cat /proc/self/environ",
    "cat /proc/1/environ",
    "cat pmoves/env.shared",
    "grep KEY pmoves/env.tier-llm.env",
]


@pytest.mark.parametrize("command", ESCAPES_DENIED)
def test_exec_and_write_escapes_are_denied(command):
    assert _resolve("bash", command) == "deny"


# Not denied, but no longer auto-allowed: they ask.
ASK_NOT_ALLOW = [
    # pytest and make run repo code, and `edit` can rewrite that code
    # (conftest.py, any test, pyproject addopts, the Makefile)
    "python -m pytest pmoves/tests -q",
    "python3 -m pytest",
    "uv run pytest pmoves/tests",
    "make -C pmoves register-status",
    # rg has an exec flag; Kilo's built-in grep tool covers search
    "rg foo pmoves",
    # shell syntax that can rebuild a denied flag inside an allowed prefix
    'git diff --o""utput=x',
    "git diff -\\-output=x",
    "git diff --{output,x}=y",
    "git diff $FLAG",
    "git diff $(echo --output=x)",
    "git log `echo --output=x`",
    "git show '--output=x'",
    # redirection writes a file outside the edit gate
    "cat a > b",
    "git log > x",
    # git branch is listing-only; anything else asks
    "git branch new-branch",
    "git branch -vD x",
]


@pytest.mark.parametrize("command", ASK_NOT_ALLOW)
def test_risky_forms_fall_back_to_ask(command):
    assert _resolve("bash", command) != "allow"


STILL_ALLOWED = [
    "git status",
    "git status --short",
    "git diff",
    "git diff HEAD~1 -- pmoves",
    "git log --oneline -5",
    "git show HEAD",
    "git branch",
    "git branch -a",
    "git branch --show-current",
    "git worktree list",
    "ls -la",
    "cat README.md",
    "grep -rn foo pmoves",
    "wc -l kilo.json",
    "pwd",
]


@pytest.mark.parametrize("command", STILL_ALLOWED)
def test_read_only_commands_stay_auto_allowed(command):
    assert _resolve("bash", command) == "allow"


@pytest.mark.parametrize("path,expected", [
    (".git/config", "deny"),           # core.fsmonitor / diff.external -> exec on `git status`
    (".git", "deny"),                  # a worktree's gitdir pointer
    ("sub/.git/config", "deny"),       # a planted nested repository
    ("--output=x", "deny"),            # a dash-named file turns a glob into a flag
    ("pmoves/-f", "deny"),
    ("pmoves/tools/x.py", "allow"),
])
def test_edit_rules(path, expected):
    assert _resolve("edit", path) == expected


@pytest.mark.parametrize("path,expected", [
    ("pmoves/env.shared", "deny"),
    ("pmoves/env.tier-llm.env", "deny"),
    ("pmoves/env.shared.example", "allow"),
    ("pmoves/tools/x.py", "allow"),
])
def test_read_rules(path, expected):
    assert _resolve("read", path) == expected


def test_proc_is_outside_the_reachable_directories():
    assert _resolve("external_directory", "/proc/self/*") == "deny"
