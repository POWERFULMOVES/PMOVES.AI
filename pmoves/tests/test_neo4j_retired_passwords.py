"""Retired Neo4j fallback passwords must not survive anywhere in the tree.

#3251 replaces two compose fallbacks with `:?` guards: elder-melchor's
`${NEO4J_PASSWORD:-...}` and jellyfin-ai's `${JELLYFIN_NEO4J_PASSWORD:-...}`.
Retiring the fallback is not enough when the same literal is printed somewhere
else. scripts/start-cipher-stack.sh still echoed elder-melchor's as
"(user: neo4j, pass: ...)", and two planning docs carried jellyfin's as a
NEO4J_AUTH value. A `:-` grep finds neither of those.

This file holds only sha256 digests. It hashes every token in every tracked text
file and fails on a match. It never prints the token, and it asserts on an int,
so a failure cannot leak the value through pytest's assertion rewrite. Treat the
values as burned: they remain in git history, and rotation is an operator step.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]
REPO = PMOVES.parent

RETIRED_SHA256 = {
    "6f2dbdbf89806f02d2b93c1d77e01e37922e29ab0a434d5874d778a0b8fcf36a": "elder-melchor NEO4J_PASSWORD fallback",
    "6171db567a4112f6b22257ef2be51d19f6d145ff5aa546da4c58cd63d9bcacf6": "jellyfin-ai JELLYFIN_NEO4J_PASSWORD fallback",
}
# Tokens split on whitespace, quotes and the punctuation that delimits a value in
# shell, YAML, compose interpolation and URLs (`neo4j/<pw>`, `:-<pw>}`, `pass: <pw>)`).
TOKEN = re.compile(r"[^\s\"'`,;(){}<>=:/\\|\[\]]{6,64}")
# A literal password printed next to the word neo4j, e.g. `neo4j, pass: hunter2`.
# A value that starts with `$`, `<` or `{` is a reference or placeholder, not a literal.
ECHOED = re.compile(r"(?i)neo4j.*\bpass(?:word)?\s*[:=]\s*(?![$<{])[A-Za-z0-9_!@#%^&*+.-]{4,}")


def _digests(token: str) -> set[str]:
    return {hashlib.sha256(v.encode()).hexdigest() for v in {token, token.strip("-.")}}


def _tracked_text() -> dict[str, str]:
    proc = subprocess.run(["git", "-C", str(REPO), "grep", "-Il", "."], capture_output=True, text=True)
    assert proc.returncode in (0, 1), proc.stderr
    out = {}
    for rel in filter(None, proc.stdout.split("\n")):
        try:
            out[rel] = (REPO / rel).read_text(errors="ignore")
        except OSError:
            continue
    return out


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_no_tracked_file_carries_a_retired_neo4j_password():
    carriers = sorted({rel for rel, text in _tracked_text().items()
                       for tok in set(TOKEN.findall(text)) if _digests(tok) & RETIRED_SHA256.keys()})
    # paths are safe to show; the tokens are not
    assert len(carriers) == 0, f"retired password literal (value not printed) in: {carriers}"


def _neo4j_shell_scripts() -> list[Path]:
    roots = [REPO / "scripts", PMOVES / "scripts", PMOVES / "data"]
    files = {f for r in roots if r.is_dir() for f in r.rglob("*.sh")}
    return sorted(f for f in files if re.search(r"(?i)neo4j", f.read_text(errors="ignore")))


def test_scope_includes_the_cipher_stack_script():
    assert PMOVES / "scripts" / "start-cipher-stack.sh" in _neo4j_shell_scripts()


@pytest.mark.parametrize("script", _neo4j_shell_scripts(), ids=lambda f: str(f.relative_to(REPO)))
def test_no_neo4j_script_prints_a_literal_password(script):
    hits = sum(1 for line in script.read_text(errors="ignore").splitlines() if ECHOED.search(line))
    assert hits == 0, f"{hits} line(s) print a literal Neo4j password (value not printed)"


def test_echo_pattern_catches_the_shape_it_replaced():
    assert ECHOED.search('echo "   Neo4j: bolt://localhost:7687 (user: neo4j, pass: hunter22)"')
    assert not ECHOED.search('echo "   Neo4j: bolt://localhost:7687 (user: neo4j, password: <NEO4J_PASSWORD in env.shared>)"')
    assert not ECHOED.search('echo "neo4j pass: $NEO4J_PASSWORD"')
    assert not ECHOED.search('echo "neo4j password: <set in env.shared>"')
