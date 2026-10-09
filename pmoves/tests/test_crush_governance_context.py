"""Crush must boot CHIT-aware, through the mechanisms Crush actually documents.

The operator direction (2026-09-02): crush loads the CHIT-aware AGNOTE4482
governance docs, the AGENTS.md contract, and the skills constellation. The
upstream README fixes HOW each of those is delivered, and these tests pin the
configurator to it:

  * AGNOTE4482.md (Village Rule, signoff contract) and the SITREP digest are
    context_paths -- they are not root instruction files, so context_paths is
    the documented vehicle (same class as ROADMAP/NEXT_STEPS);
  * AGENTS.md is NOT a context candidate: Crush auto-loads root instruction
    files (AGENTS.md/CLAUDE.md/GEMINI.md/.cursorrules) natively -- verified
    live: those four ride the session context while context_paths names none
    of them. Listing AGENTS.md would double-load it every session;
  * the skills constellation loads through native Agent Skills discovery:
    .claude/skills mirrors (agent-sandbox, fork-repository, claude-d3js) are
    scanned by default, and the PMOVES-skills package fork -- outside every
    default scan path -- gets an explicit options.skills_paths entry. The
    binary must know that option (present since well before 0.84.1);
  * the ACTIVE claims register (AGNOTE4482PHI.t1.md, ~921KB / ~230k tokens)
    is deliberately NOT always-loaded. The SITREP pays that down; wanting it
    in every system prompt is a decision that must be made on purpose;
  * the register file itself is clean UTF-8 with no NUL bytes. It carried a
    corrupted `0` (literal U+0000 inside `0.0.0.0:4482`) at byte 396577,
    which made every grep treat the fleet's live claims ledger as binary.
    Tools that skip binary files were silently skipping the register.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGURATOR = REPO_ROOT / "pmoves" / "tools" / "crush_configurator.py"
REGISTER = REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "AGNOTE4482PHI.t1.md"
SKILLS_PACKAGE = REPO_ROOT / "skills" / "PMOVES-skills" / "skills"
GLM_SUIT = REPO_ROOT / "pmoves" / "configs" / "model-suits" / "glm-5.2.yaml"

GOVERNANCE_CANDIDATES = [
    "pmoves/docs/AGENTS/AGNOTE4482.md",
    "pmoves/docs/AGENTS/AGNOTE4482_SITREP.md",
]


def _candidates_block() -> str:
    text = CONFIGURATOR.read_text(encoding="utf-8")
    return text.split("context_candidates = [", 1)[1].split("]", 1)[0]


def test_governance_candidates_are_listed():
    block = _candidates_block()
    for rel in GOVERNANCE_CANDIDATES:
        assert f'Path("{rel}")' in block, (
            f"{rel} is missing from crush_configurator context_candidates; "
            "crush boots without the CHIT-aware governance set."
        )


def test_governance_candidates_exist_in_the_repo():
    """exists() filtering keeps only real files -- a candidate that points at
    nothing is a silent no-op, so the files themselves are part of the contract."""
    for rel in GOVERNANCE_CANDIDATES:
        assert (REPO_ROOT / rel).is_file(), (
            f"context candidate {rel} does not exist; the exists() filter "
            "would drop it from every generated config without a signal."
        )


def test_agents_md_is_not_duplicated_into_context_paths():
    """Crush auto-loads root instruction files natively. A context_paths entry
    for AGENTS.md would double-load it -- this is the load-bearing NO."""
    block = _candidates_block()
    assert 'Path("AGENTS.md")' not in block, (
        "AGENTS.md was added to context_candidates, but Crush already "
        "auto-loads it as a root instruction file; it would ride the system "
        "prompt twice. Remove the candidate."
    )


def test_skills_package_is_wired_via_skills_paths():
    """PMOVES-skills lives outside every default skill-scan path (.claude/skills
    et al.), so the documented delivery is options.skills_paths."""
    text = CONFIGURATOR.read_text(encoding="utf-8")
    assert "skills_paths" in text and "skills/PMOVES-skills/skills" in text, (
        "the PMOVES-skills package must be wired through options.skills_paths "
        "(native Agent Skills discovery), not through context_paths."
    )
    if SKILLS_PACKAGE.is_dir():  # submodule not initialized on every node
        assert any(
            p.is_dir() and (p / "SKILL.md").is_file() for p in SKILLS_PACKAGE.iterdir()
        ), (
            "skills/PMOVES-skills/skills contains no SKILL.md folders; "
            "skills_paths would point at nothing."
        )


def test_active_claims_register_is_not_always_loaded():
    """~230k tokens per session is a cost the SITREP digest already pays down.
    If someone wants the register always-loaded they must change this test AND
    the configurator comment together."""
    block = _candidates_block()
    assert 'Path("AGNOTE4482PHI.t1.md")' not in block, (
        "AGNOTE4482PHI.t1.md was added to context_candidates -- that is a "
        "per-session context-cost decision, not a default. Reverse it or "
        "update this test on purpose."
    )


def test_claims_register_is_clean_text():
    """The register must stay grep-able and loader-able: no NUL bytes, valid
    UTF-8. Guards the byte-396577 corruption class this lane repaired."""
    data = REGISTER.read_bytes()
    assert data.count(b"\x00") == 0, (
        "AGNOTE4482PHI.t1.md contains NUL bytes; tools treat it as binary and "
        "silently skip the fleet's live claims ledger."
    )
    data.decode("utf-8")  # raises on invalid UTF-8


def test_configurator_has_no_stale_skills_readme_candidate():
    """The first cut of this lane put skills/README.md in context_paths; the
    documented mechanism is skills discovery, not a context README. Guard
    against regression to the wrong vehicle."""
    block = _candidates_block()
    assert 'Path("skills/README.md")' not in block


def test_zai_models_carry_suit_windows():
    """glm-5.2 is not in Crush's bundled model registry: without a
    suit-sourced context_window the harness assumes a small default and
    compacts sessions at a fraction of the model's real window. The model
    suits (pmoves/configs/model-suits/*.yaml) are the fleet's source of
    truth; the configurator must read them, and must use effective_window
    (the deployable figure), not max_window (the provider headline)."""
    text = CONFIGURATOR.read_text(encoding="utf-8")
    assert "_zai_models_from_suits" in text and "model-suits" in text, (
        "the zai provider must carry per-model entries sourced from "
        "pmoves/configs/model-suits/; without them Crush cannot size the "
        "GLM context window."
    )
    assert 'entry["context_window"] = context["effective_window"]' in text, (
        "context_window must come from the suit's effective_window; "
        "max_window risks provider 400s at the margin."
    )
    suit = yaml.safe_load(GLM_SUIT.read_text(encoding="utf-8"))["model_suit"]
    assert suit["context"]["effective_window"] >= 500_000, (
        "glm-5.2 suit lost its effective window; the configurator would "
        "silently fall back to a tiny default."
    )
    assert suit["defaults"]["max_tokens"] >= 128_000
