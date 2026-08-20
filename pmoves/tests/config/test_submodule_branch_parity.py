"""The tracked branch of a submodule is declared in FOUR places. Keep them equal.

Why
---
Review of #2632 put it exactly: "the branch name was declared in four places, not
one." Correcting `.gitmodules` alone left three other files naming a branch that
did not exist on any of the three forks, and one of them —
branch_protection/pmoves_standard.json — takes PRECEDENCE over `.gitmodules` in
`resolve_branch()`. So the daily drift audit and any ruleset apply kept targeting
a branch nothing consumed, while `.gitmodules` looked correct.

The four surfaces:

  1. .gitmodules                                    submodule.<name>.branch
  2. pmoves/configs/branch_protection/…json         per_repo_overrides[slug].branch
  3. pmoves/config/fork_registry.json               <name>.branch
  4. pmoves/mk/preflight.mk                         SUBMODULE_BRANCH_ALLOW

Each is consumed by a different tool, so drift between them is silent by
construction: every individual tool keeps working, on a different answer.

Running this cross-check for the first time found four disagreements beyond the
three that prompted it. Three were settled against the forks themselves and
fixed in the same change:

  PMOVES-ClawZ   pin identical to hardened, DIVERGED from main
                 -> the preflight allowlist entry saying `main` was wrong
  PMOVES-DoX     preflight named PMOVES.AI-Edition-Hardened-DoX, which 404s on
                 the fork; the pin is identical to hardened
  PMOVES-crush   pin identical to hardened -> the registry saying `main` was wrong

The fourth is a real decision, not a typo, and is recorded below rather than
guessed at.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = REPO_ROOT / "pmoves" / "configs" / "branch_protection" / "pmoves_standard.json"
REGISTRY = REPO_ROOT / "pmoves" / "config" / "fork_registry.json"
PREFLIGHT = REPO_ROOT / "pmoves" / "mk" / "preflight.mk"

# Submodules whose surfaces disagree for a reason that needs a human decision,
# not a typo fix. Each entry must say what the disagreement IS and what settles
# it — an allowlist without that becomes a place where drift goes to be forgotten.
KNOWN_DISAGREEMENTS = {
    # The gitlink is IDENTICAL to the fork's `main` and DIVERGED from its
    # `PMOVES.AI-Edition-Hardened`, which does exist. So this is not the
    # missing-branch typo that ClawZ/DoX/crush were: the fleet standard branch is
    # real and the parent simply consumes a commit that is not on it. Settling it
    # means either re-pinning the gitlink onto hardened or declaring `main` as the
    # tracked branch, and that is the submodule owner's call. Until then the
    # branch-protection spec targets hardened while the consumed commit is on
    # main, i.e. protection guards a branch nothing pins.
    "PMOVES-Danger-infra",
}


def _gitmodules() -> dict[str, dict[str, str]]:
    out = subprocess.run(
        ["git", "config", "-f", ".gitmodules", "--get-regexp",
         r"^submodule\..*\.(url|branch|path)$"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout
    parsed: dict[str, dict[str, str]] = {}
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        name = key[len("submodule."):].rsplit(".", 1)[0]
        parsed.setdefault(name, {})[key.rsplit(".", 1)[1]] = value
    return parsed


def _slug(url: str) -> str:
    return re.sub(r"^(git@github\.com:|https?://github\.com/)", "", url).removesuffix(".git")


def _registry_branches() -> dict[str, str]:
    def walk(node, acc):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, dict) and "branch" in value:
                    acc[key] = value["branch"]
                else:
                    walk(value, acc)
        return acc
    return walk(json.loads(REGISTRY.read_text(encoding="utf-8")), {})


def _preflight_allow() -> dict[str, str]:
    text = PREFLIGHT.read_text(encoding="utf-8")
    match = re.search(r"SUBMODULE_BRANCH_ALLOW \?=(.*?)\n[A-Z_]+ \?=", text, re.S)
    allow: dict[str, str] = {}
    if match:
        for token in re.split(r"[,\\\s]+", match.group(1)):
            if "=" in token:
                name, _, branch = token.partition("=")
                allow[name.strip()] = branch.strip()
    return allow


def _declarations() -> dict[str, dict[str, str]]:
    modules = _gitmodules()
    spec = {r: o.get("branch") for r, o in
            json.loads(SPEC.read_text(encoding="utf-8"))["per_repo_overrides"].items()}
    registry = _registry_branches()
    allow = _preflight_allow()
    out: dict[str, dict[str, str]] = {}
    for name, fields in modules.items():
        found = {
            "gitmodules": fields.get("branch"),
            "spec": spec.get(_slug(fields.get("url", ""))),
            "registry": registry.get(name),
            "preflight": allow.get(name),
        }
        out[name] = {k: v for k, v in found.items() if v}
    return out


def test_sources_are_readable():
    """If any surface stops parsing, every assertion below passes vacuously."""
    decls = _declarations()
    assert len(decls) > 60, f"only {len(decls)} submodules discovered"
    assert SPEC.is_file() and REGISTRY.is_file() and PREFLIGHT.is_file()
    assert any("spec" in v for v in decls.values())
    assert any("registry" in v for v in decls.values())
    assert any("preflight" in v for v in decls.values())


def test_all_four_surfaces_declare_the_same_branch():
    offenders = []
    for name, values in sorted(_declarations().items()):
        if name in KNOWN_DISAGREEMENTS:
            continue
        if len(set(values.values())) > 1:
            rendered = ", ".join(f"{k}={v}" for k, v in sorted(values.items()))
            offenders.append(f"{name}: {rendered}")
    assert not offenders, (
        "submodule tracked-branch declarations disagree:\n  "
        + "\n  ".join(offenders)
        + "\n\nCheck the fork before choosing which one to change — a declaration "
          "naming a branch that does not exist reads as gitlink drift and is not. "
          "Compare the pinned commit against each candidate branch first."
    )


def test_known_disagreements_still_disagree():
    """A stale exemption is drift with permission. If one of these has been
    settled, the entry must be removed rather than left standing."""
    decls = _declarations()
    for name in sorted(KNOWN_DISAGREEMENTS):
        assert name in decls, f"{name} is exempted but no longer a submodule"
        values = decls[name]
        assert len(set(values.values())) > 1, (
            f"{name} is listed in KNOWN_DISAGREEMENTS but its declarations now "
            f"agree ({values}). Remove the exemption."
        )


def test_preflight_allowlist_holds_only_real_exceptions():
    """SUBMODULE_BRANCH_ALLOW exempts submodules from the fleet default. An entry
    that merely repeats what .gitmodules already says is not an exception, and an
    entry that contradicts it is the bug this file exists to catch."""
    modules = _gitmodules()
    offenders = []
    for name, branch in sorted(_preflight_allow().items()):
        declared = modules.get(name, {}).get("branch")
        if declared and declared != branch:
            offenders.append(f"{name}: preflight={branch} but .gitmodules={declared}")
    assert not offenders, "preflight allowlist contradicts .gitmodules:\n  " + "\n  ".join(offenders)
