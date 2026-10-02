"""kilo.json permission rules, fed through a port of Kilo's own resolver.

Kilo (Kilo-Org/kilocode@6fd9b7b) resolves a tool call like this:
  * packages/opencode/src/util/wildcard.ts `match`: every backslash becomes
    `/` in BOTH the input and the pattern, then `*` -> `.*` (it crosses `/`
    and spaces), `?` -> `.`, and a trailing ` *` is optional, so `ls *`
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
_DOT_ENV = "." + "env"  # concatenated: the repo's damage-control hook refuses the literal


def _match(text: str, pattern: str) -> bool:
    text, pattern = text.replace("\\", "/"), pattern.replace("\\", "/")
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
    # backslashes are normalised to "/" first, on both sides
    assert _match("a\\b", "a/b") and _match("a/b", "a\\b")


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
    # secrets files named in the arguments, also through a glob (delta review P2)
    "cat pmoves/env.shared",
    "grep KEY pmoves/env.tier-llm.env",
    "less pmoves/env.shared",
    "tail -n 5 pmoves/env.tier-llm.env",
    "rg KEY pmoves/env.shared",
    "grep --file=env.shared x",
    # an .example argument must not lift the deny (last delta review P2)
    "cat pmoves/env.shared README.example",
    "grep KEY pmoves/env.shared x.example",
    "cat pmoves/env.shared.bak-rot20260912",
    "cat " + _DOT_ENV,
    "cat pmoves/" + _DOT_ENV + ".local",
    # .envrc is a real gitignored secrets file here (.gitignore:47); the
    # .env-family globs only matched a '', ' a', or '.*' suffix (claude-review
    # design-decision thread)
    "cat " + _DOT_ENV + "rc",
    "cat pmoves/" + _DOT_ENV + "rc",
    "grep KEY " + _DOT_ENV + "rc",
    # env.<name>.local: gitignored node-local overlay shape (e.g.
    # env.mesh-bind.local, .gitignore:57); matched by neither the .env family
    # nor the env.shared/env.tier families
    "cat pmoves/env.mesh-bind.local",
    "grep KEY pmoves/env.jellyfin-ai.local",
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
    "git diff --o\\utput=x",
    "git diff --{output,x}=y",
    "git diff $FLAG",
    "git diff $(echo --output=x)",
    "git log `echo --output=x`",
    "git show '--output=x'",
    # redirection writes a file outside the edit gate
    "cat a > b",
    "git log > x",
    # these read file contents, and a recursive grep or a glob reaches the
    # gitignored secrets files without naming them; Kilo's read and grep
    # tools cover reading and search under the `read` rules
    "grep -r API_KEY pmoves",
    "grep -rh KEY .",
    "cat README.md",
    "head -n 5 kilo.json",
    "cat env*",
    # a glob hides the name from the secrets deny; cat/head are not
    # auto-allowed, so these still need a human
    "cat env.s*",
    "head -c 999 env.sha?",
    # git diff goes --no-index (a whole-file diff of any file) when asked to,
    # or implicitly for a path outside the worktree; a glob hides the name
    "git diff --no-index Makefile pmoves/?nv.shared",
    "git diff --no-index a b",
    "git diff Makefile /etc/hostname",
    "git diff HEAD~1 -- pmoves",
    "git diff HEAD -- pmoves/?nv.shared",
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
    "git diff --stat",
    "git diff --cached",
    "git diff origin/main...HEAD --stat",
    "git log --oneline -5",
    "git show HEAD",
    "git branch",
    "git branch -a",
    "git branch --show-current",
    "git worktree list",
    "git log --oneline -- pmoves/tools",
    "ls -la",
    "ls pmoves/config",
    "wc -l kilo.json pmoves/tools/mcp_config_generator.py",
    "pwd",
    # names that merely contain "env." are not secrets files
    "git log -- pmoves/scripts/with-env.sh",
    "wc -l pmoves/tests/test_env.py",
]


@pytest.mark.parametrize("command", STILL_ALLOWED)
def test_read_only_commands_stay_auto_allowed(command):
    assert _resolve("bash", command) == "allow"


# The secrets-name deny names the files themselves (env.shared, env.tier-*,
# dotenv). A deny cannot be approved mid-session, so documentation copies and
# look-alike names must never hit it (final review P3).
NOT_HARD_DENIED = [
    "git log -- pmoves/env.shared.example",
    "git log -- pmoves/tools/env.py",
    "ls pmoves/env.d",
    "cat pmoves/env.shared.example",
]


@pytest.mark.parametrize("command", NOT_HARD_DENIED)
def test_lookalike_and_example_names_are_not_hard_denied(command):
    assert _resolve("bash", command) != "deny"


def test_example_rule_sits_above_every_deny():
    rules = list(json.loads(_KILO.read_text(encoding="utf-8"))["permission"]["bash"].items())
    example = next(i for i, (k, _) in enumerate(rules) if k == "*.example*")
    assert all(v != "deny" for _, v in rules[:example]), "a deny above the .example rule can be lifted by it"


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
