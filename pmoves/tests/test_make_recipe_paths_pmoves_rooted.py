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
recipe lines only. It fires where a `pmoves/`-prefixed path is in a position the
SHELL resolves against cwd (run by an interpreter, written by mkdir or a
redirect, or `make -C pmoves`) when the path was evidently meant repo-rooted:
its first component exists under `pmoves/` (so `pmoves/<it>` from cwd
`pmoves/` names the wrong place), or the path starts with a make/shell
variable and so cannot be checked statically. Existence under `pmoves/pmoves/`
is NEVER an exemption: that is exactly the directory this bug populates, so one
local run of a buggy `mkdir -p pmoves/docs/logs` would otherwise silence the
ratchet for good. Arguments handed to tools that resolve paths against the repo
root themselves (e.g. `secrets_sync.py --manifest pmoves/chit/...`) are not in
those positions and are left alone. A recipe that first does
`cd $(CURDIR)/..` (or `cd $(REPO_ROOT)` / `cd $(PMOVES_ROOT)`) is at the repo
root, where `pmoves/...` is correct.
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

# Recipe already moved to the repo root before naming pmoves/...
AT_REPO_ROOT = re.compile(r"\bcd\s+\"?\$\((?:CURDIR\)/\.\.|REPO_ROOT\)|PMOVES_ROOT\))")

# Quoted text is help/echo, not a command (same rule as the submodule ratchet).
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")

# `$(error Usage: make -C pmoves ...)` is a usage message printed to the operator.
MAKE_MESSAGE = re.compile(r"\$\((?:error|warning|info)\s.*$")


def _recipe_lines(path: Path):
    for n, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if raw.startswith("\t"):
            yield n, raw


def _prep(line: str) -> str:
    return MAKE_MESSAGE.sub(" ", QUOTED.sub(" ", line.lstrip("\t").lstrip("@-+")))


def _line_offenders(body: str, pmoves_dir: Path = PMOVES) -> list[str]:
    """Return the cwd-resolved pmoves/ paths in one recipe line that point at pmoves/pmoves/."""
    if body.lstrip().startswith("#") or AT_REPO_ROOT.search(body):
        return []
    hits = []
    for m in CWD_RESOLVED.finditer(body):
        rel = m.group(1)
        # Literal prefix before any make/shell variable; empty means `pmoves/$(X)...`.
        literal = re.split(r"\$[({]", rel, maxsplit=1)[0]
        head = literal.split("/", 1)[0]
        # Flag when the path was meant repo-rooted (its first component lives in
        # pmoves/) or cannot be checked. Never consult pmoves/pmoves/ itself.
        if not head or (pmoves_dir / head).exists():
            hits.append(f"pmoves/{rel}")
    if MAKE_C_PMOVES.search(body):
        hits.append("-C pmoves")
    return hits


def _offenders(path: Path) -> list[str]:
    out = []
    for n, line in _recipe_lines(path):
        body = _prep(line)
        for hit in _line_offenders(body):
            out.append(f"{path.relative_to(REPO_ROOT)}:{n}: {hit}  <- {body.strip()[:80]}")
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
    ]
    for line in shipped:
        assert _line_offenders(_prep(line)), f"detector no longer matches: {line!r}"

    fixed_or_legit = [
        "\tbash scripts/mcp-toolkit-gateway-stop.sh",
        "\t@cd $(CURDIR)/.. && uv run pmoves/tools/analyze_beats.py analyze",
        "\t@cd $(PMOVES_ROOT) && python pmoves/tools/compose/compose_fordham_demo.py x",
        "\t@bash $(REPO_ROOT)/pmoves/scripts/x.sh",
        "\t@echo \"Wrote pmoves/docs/logs/x.txt\"",
        "\t@$(CODEX_PY) tools/secrets_sync.py report --manifest pmoves/chit/secrets_manifest.yaml",
        "\t\t|| { echo \"run 'make -C pmoves design-tokens' and commit\"; exit 1; }",
        "\t$(if $(strip $(SQL)),,$(error Usage: make -C pmoves supa-query SQL=\"select ...\"))",
    ]
    for line in fixed_or_legit:
        assert not _line_offenders(_prep(line)), f"detector wrongly flags: {line!r}"


def test_variable_prefixed_path_is_flagged():
    """`pmoves/$(X)` has no literal to check, so it must be flagged, not waved through."""
    for line in ("\tbash pmoves/$(SPARK_SCRIPT)", "\t@mkdir -p pmoves/${OUT_DIR}"):
        assert _line_offenders(_prep(line)), f"variable-prefixed path not flagged: {line!r}"


def test_a_stray_pmoves_pmoves_copy_does_not_exempt(tmp_path: Path):
    """The bug writes into pmoves/pmoves/. A stray copy there must not hide the bug."""
    fake = tmp_path / "pmoves"
    (fake / "docs" / "logs").mkdir(parents=True)
    (fake / "pmoves" / "docs" / "logs").mkdir(parents=True)  # left by an earlier buggy run
    (fake / "pmoves" / "Makefile").write_text("", encoding="utf-8")
    assert _line_offenders(_prep("\t@mkdir -p pmoves/docs/logs"), fake), (
        "a path that also exists under pmoves/pmoves/ was exempted"
    )
    assert _line_offenders(_prep("\t(make -C pmoves x)"), fake), (
        "a stray pmoves/pmoves/Makefile exempted `make -C pmoves`"
    )
