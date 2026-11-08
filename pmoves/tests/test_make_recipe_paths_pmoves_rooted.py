"""Make recipes run in `pmoves/`, so a `pmoves/...` path in one names `pmoves/pmoves/...`.

Every documented invocation is `make -C pmoves <target>`, and the mk/*.mk
modules are `include`d by pmoves/Makefile, so `$(CURDIR)` is `pmoves/` for every
recipe. A recipe that runs `bash pmoves/scripts/x.sh` therefore asks for
`pmoves/pmoves/scripts/x.sh`, which does not exist:

    $ make -C pmoves mcp-spark-gateway-stop
    bash: pmoves/scripts/mcp-toolkit-gateway-stop.sh: No such file or directory

Shipped in 91591de38 (mk/mcp-toolkit-spark.mk, mk/unsloth.mk) and flagged by
Codex as a P2 on PR #2208; the same sweep found the a2ui living-doc render
targets and gpu-rerank-evidence carrying the same mistake.

Sibling of test_make_submodule_targets_repo_rooted.py, same shape: a ratchet on
recipe lines. It fires on every `pmoves/`-prefixed path in a position the SHELL
resolves against cwd (run by an interpreter, written by mkdir or a redirect) and
on `make -C pmoves`. From cwd `pmoves/` such a path always names `pmoves/pmoves/`,
so nothing on disk is consulted: an existence check would be an exemption, and
the obvious thing to exist is the stray tree this bug itself writes (a single
buggy `mkdir -p pmoves/docs/logs` would silence the ratchet for good; a new
`> pmoves/out/x.txt` would never match at all).

Recipes are read as LOGICAL lines (backslash continuations joined), because that
is what the shell runs: a `cd $(CURDIR)/.. && \\` on one physical line covers the
continuation lines after it. A logical line that `cd`s to the repo root first
(`$(CURDIR)/..`, `$(REPO_ROOT)`, `$(PMOVES_ROOT)`, `..`, or the git toplevel,
quoted or not) is at the repo root, where `pmoves/...` is correct. Arguments
handed to tools that resolve paths against the repo root themselves (e.g.
`secrets_sync.py --manifest pmoves/chit/...`) are not in a cwd-resolved
position and are left alone.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES = REPO_ROOT / "pmoves"
MAKEFILES = [PMOVES / "Makefile"] + sorted((PMOVES / "mk").glob("*.mk"))

# A `pmoves/` path in a position the shell resolves against cwd. The lookbehind
# keeps `$(REPO_ROOT)/pmoves/...` and `../pmoves/...` out: those name the root.
CWD_RESOLVED = re.compile(
    r"(?:^|[;&|(]\s*|"
    r"\b(?:bash|sh|python3?|node|source|uv\s+run(?:\s+--script)?|mkdir\s+-p)\s+|"
    r">{1,2}\s*)"
    r"(?<![\w./$)}-])pmoves/([^\s;&|)\"']+)"
)

# `make -C pmoves` / `$(MAKE) -C pmoves` from inside pmoves/ looks for pmoves/pmoves/Makefile.
MAKE_C_PMOVES = re.compile(r"(?:\bmake|\$\(MAKE\))\s+(?:-\S+\s+)*-C\s+pmoves\b(?!/)")

# The logical line moved to the repo root before naming pmoves/... Checked on the
# line BEFORE quoted text is stripped, so `cd "$(REPO_ROOT)"` counts too.
AT_REPO_ROOT = re.compile(
    r"\bcd\s+([\"']?)"
    r"(?:\$\(CURDIR\)/\.\.|\$\(REPO_ROOT\)|\$\(PMOVES_ROOT\)|\.\."
    r"|\$\(shell git rev-parse --show-toplevel\)|\$\$\(git rev-parse --show-toplevel\))"
    r"/?\1(?=[\s;&|)]|$)"
)

# Quoted text is help/echo, not a command (same rule as the submodule ratchet).
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")

# `$(error Usage: make -C pmoves ...)` is a usage message printed to the operator.
MAKE_MESSAGE = re.compile(r"\$\((?:error|warning|info)\s.*$")


def _recipe_lines(path: Path):
    """Yield (first physical line number, logical recipe line) with continuations joined."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].startswith("\t"):
            i += 1
            continue
        start, parts = i + 1, [lines[i]]
        while parts[-1].endswith("\\") and i + 1 < len(lines):
            i += 1
            parts[-1] = parts[-1][:-1]
            parts.append(lines[i].lstrip("\t"))
        yield start, " ".join(parts)
        i += 1


def _prep(line: str) -> str:
    return MAKE_MESSAGE.sub(" ", QUOTED.sub(" ", line.lstrip("\t").lstrip("@-+")))


def _line_offenders(line: str) -> list[str]:
    """Return the cwd-resolved pmoves/ paths (and `make -C pmoves`) in one logical recipe line."""
    if line.lstrip("\t").lstrip("@-+").lstrip().startswith("#") or AT_REPO_ROOT.search(line):
        return []
    body = _prep(line)
    hits = [f"pmoves/{m.group(1)}" for m in CWD_RESOLVED.finditer(body)]
    if MAKE_C_PMOVES.search(body):
        hits.append("-C pmoves")
    return hits


def _offenders(path: Path) -> list[str]:
    out = []
    for n, line in _recipe_lines(path):
        for hit in _line_offenders(line):
            out.append(f"{path.relative_to(REPO_ROOT)}:{n}: {hit}  <- {_prep(line).strip()[:80]}")
    return out


@pytest.mark.parametrize("mk", MAKEFILES, ids=lambda p: p.name)
def test_recipe_paths_resolve_from_pmoves(mk: Path):
    if not mk.is_file():
        pytest.skip(f"{mk.name} not present")
    bad = _offenders(mk)
    assert not bad, (
        "these recipe lines name a pmoves/-prefixed path the shell resolves against "
        "cwd, but recipes run in pmoves/ (`make -C pmoves ...`), so it means "
        "pmoves/pmoves/... which does not exist:\n  " + "\n  ".join(bad) +
        "\nDrop the `pmoves/` prefix, or `cd $(CURDIR)/.. &&` first when the tool "
        "expects the repo root as cwd; use `$(MAKE) <target>` instead of `make -C pmoves`."
    )


def test_the_check_would_actually_catch_the_original_defect():
    """NEGATIVE CONTROL: `assert not bad` passes trivially if the detector is dead."""
    shipped = [
        "\tbash pmoves/scripts/mcp-toolkit-gateway-stop.sh",
        "\t@python3 pmoves/tools/unsloth_finetune.py \\",
        "\t@uv run --script pmoves/tools/a2ui_renderer/render_living_doc.py \\",
        "\t@mkdir -p pmoves/docs/logs",
        "\t  (echo \"Profile not found\" && make -C pmoves mcp-toolkit-bootstrap)",
        # Variable-prefixed: nothing literal to check, still a pmoves/pmoves/ path.
        "\tbash pmoves/$(SPARK_SCRIPT)",
        "\t@mkdir -p pmoves/${OUT_DIR}",
        # A directory that exists nowhere yet: the redirect would create pmoves/pmoves/out/.
        "\t@./run.sh > pmoves/out/x.txt",
        # `cd ../x` is not the repo root.
        "\t@cd ../deploy && bash pmoves/scripts/x.sh",
    ]
    for line in shipped:
        assert _line_offenders(line), f"detector no longer matches: {line!r}"

    fixed_or_legit = [
        "\tbash scripts/mcp-toolkit-gateway-stop.sh",
        "\t@cd $(CURDIR)/.. && uv run pmoves/tools/analyze_beats.py analyze",
        "\t@cd $(PMOVES_ROOT) && python pmoves/tools/compose/compose_fordham_demo.py x",
        "\t@cd \"$(REPO_ROOT)\" && bash pmoves/scripts/x.sh",
        "\t@cd .. && bash pmoves/scripts/x.sh",
        "\t@cd $$(git rev-parse --show-toplevel) && bash pmoves/scripts/x.sh",
        "\t@bash $(REPO_ROOT)/pmoves/scripts/x.sh",
        "\t@echo \"Wrote pmoves/docs/logs/x.txt\"",
        "\t@$(CODEX_PY) tools/secrets_sync.py report --manifest pmoves/chit/secrets_manifest.yaml",
        "\t\t|| { echo \"run 'make -C pmoves design-tokens' and commit\"; exit 1; }",
        "\t$(if $(strip $(SQL)),,$(error Usage: make -C pmoves supa-query SQL=\"select ...\"))",
        "\t@# a recipe comment naming bash pmoves/scripts/x.sh",
    ]
    for line in fixed_or_legit:
        assert not _line_offenders(line), f"detector wrongly flags: {line!r}"


def test_a_cd_covers_its_continuation_lines(tmp_path: Path):
    """The shell runs logical lines: a `cd` before a `\\` covers the lines after it."""
    mk = tmp_path / "x.mk"
    mk.write_text(
        "ok:\n"
        "\t@cd $(CURDIR)/.. && \\\n"
        "\t  bash pmoves/scripts/x.sh\n"
        "bad:\n"
        "\t@echo start; \\\n"
        "\t  bash pmoves/scripts/y.sh\n",
        encoding="utf-8",
    )
    joined = list(_recipe_lines(mk))
    assert [n for n, _ in joined] == [2, 5], joined
    assert not _line_offenders(joined[0][1]), "a cd on the first physical line did not cover its continuation"
    assert _line_offenders(joined[1][1]), "a continuation line without a cd was not flagged"
