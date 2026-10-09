"""Make recipes that touch submodules must name the repo root.

Submodules live at the SUPERPROJECT root; every documented invocation in this
repo is `make -C pmoves <target>`, so `$(CURDIR)` is `pmoves/` — a subdirectory.
A bare `git submodule update -- "Pmoves-cipher"` resolves the pathspec against
`pmoves/` and matches nothing:

    $ make -C pmoves submodule-sync-one SM=Pmoves-cipher
    error: pathspec 'Pmoves-cipher' did not match any file(s) known to git

Measured 2026-09-15 while promoting the cipher gitlink. The target could not run
from the invocation its own help string documented, so the promotion was done by
hand from the repo root instead — the failure mode Known Roads exist to prevent.
A road that cannot run teaches everyone to drive around it, and then the road is
not the road.

This is a ratchet, not a style rule: it fires on recipe lines only, and only on
the git subcommands whose meaning actually depends on which directory git starts
in.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILES = [REPO_ROOT / "pmoves" / "Makefile"] + sorted(
    (REPO_ROOT / "pmoves" / "mk").glob("*.mk")
)

# git subcommands that operate on the repository as a whole, so the directory
# git starts in decides which repository (or which pathspec root) they mean.
#
# This MUST match the fixed spelling too (`git -C "X" submodule`). The first
# version anchored `git` directly against the subcommand, so a corrected line
# stopped matching and the rule became UNENFORCED rather than satisfied — the
# negative control below is the only reason that was caught.
ROOT_SENSITIVE = re.compile(
    # {0,8} bound (CodeQL re-dos alert): the unbounded star over a
    # alternation-with-optional-value can backtrack exponentially on
    # adversarial input; git flag lists here are short, so the bound is
    # semantically identical and provably linear.
    r"\bgit\s+(?:-[-\w]+(?:[= ]\S+)?\s+){0,8}(?:submodule|worktree)\b"
)

# `git -C <something>` names the repo explicitly — that is the fix, in any spelling.
NAMES_A_REPO = re.compile(r"\bgit\s+-C\b")

# Text inside quotes is not a command. `echo "run: git submodule update --init"`
# is HELP, and flagging it would push authors to reword their help rather than
# fix a road — three such lines exist today and all three are correct as written.
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


# Recipe lines start with a TAB. Anything else is a comment, a variable, or prose.
def _recipe_lines(path: Path):
    for n, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if raw.startswith("\t"):
            yield n, raw


def _offenders(path: Path):
    out = []
    for n, line in _recipe_lines(path):
        body = line.lstrip("\t").lstrip("@-+")
        # A tab-indented line whose body starts with `#` is a SHELL COMMENT
        # inside the recipe, not a command. Makefile:3753 explains the gate in
        # prose and quotes `git submodule status` while doing it.
        if body.lstrip().startswith("#"):
            continue
        body = QUOTED.sub(" ", body)
        if not ROOT_SENSITIVE.search(body):
            continue
        if NAMES_A_REPO.search(body):
            continue
        out.append(f"{path.relative_to(REPO_ROOT)}:{n}: {body.strip()[:88]}")
    return out


@pytest.mark.parametrize("mk", MAKEFILES, ids=lambda p: p.name)
def test_submodule_recipes_name_the_repo(mk: Path):
    if not mk.is_file():
        pytest.skip(f"{mk.name} not present")
    bad = _offenders(mk)
    assert not bad, (
        "these recipe lines run a repo-wide git command without naming the repo, "
        "so they operate on pmoves/ when invoked the documented way "
        "(`make -C pmoves ...`):\n  " + "\n  ".join(bad) +
        '\nUse `git -C "$(REPO_ROOT)" ...` — REPO_ROOT := $(abspath $(CURDIR)/..)'
    )


def test_the_check_would_actually_catch_the_original_defect():
    """NEGATIVE CONTROL.

    Every assertion above is `assert not bad`, which passes trivially if the
    detector never matches anything — a typo in ROOT_SENSITIVE would turn this
    whole file green while enforcing nothing. Feed it the exact line that was
    shipped and require a hit.
    """
    def prep(line: str) -> str:
        return QUOTED.sub(" ", line.lstrip("\t").lstrip("@-+"))

    shipped = prep('\tgit submodule update --init -- "$(SM)"')
    assert ROOT_SENSITIVE.search(shipped), "detector no longer matches the original defect"
    assert not NAMES_A_REPO.search(shipped), "detector would wrongly excuse the original defect"

    fixed = prep('\tgit -C "$(REPO_ROOT)" submodule update --init -- "$(SM)"')
    assert ROOT_SENSITIVE.search(fixed) and NAMES_A_REPO.search(fixed), (
        "the fixed form must still be RECOGNISED as root-sensitive and then excused; "
        "if it stopped matching ROOT_SENSITIVE the rule would be unenforced rather "
        "than satisfied"
    )

    # Help text must NOT be flagged, or authors reword their docs instead of
    # fixing a road. All three of today's instances are correct as written.
    helptext = prep('\t@echo "  run: git submodule update --init --recursive skills/"')
    assert not ROOT_SENSITIVE.search(helptext), (
        "a quoted help string was treated as a command; the detector must strip "
        "quoted text before matching"
    )


def test_repo_root_is_defined_identically_everywhere_it_is_defined():
    """Three .mk files compute REPO_ROOT. Identical value makes redefinition safe.

    If one of them ever computed a different path, make would take the last
    include silently and the targets in the other files would start operating on
    a directory their authors never named.
    """
    pattern = re.compile(r"^REPO_ROOT\s*:?=\s*(.+?)\s*$", re.M)
    found = {}
    for mk in MAKEFILES:
        if not mk.is_file():
            continue
        for m in pattern.finditer(mk.read_text(encoding="utf-8", errors="replace")):
            found.setdefault(m.group(1), []).append(mk.name)
    if len(found) <= 1:
        return
    pytest.fail(
        "REPO_ROOT is defined with different values across included makefiles; "
        "make keeps the last one and the rest silently change meaning:\n  "
        + "\n  ".join(f"{v!r} in {sorted(names)}" for v, names in found.items())
    )
