"""Every road that can build `cipher-api` must run the build-pin gate.

The defect this exists to stop
------------------------------
PR #2875 added `cipher-build-pin-check` as a prerequisite of `up-cipher` and
`up-cipher-full`, and the report claimed "`up-cipher` now always runs the gate
before building". Independent review measured that as FALSE as stated:
`up-agents-stack` -- the FLEET bring-up road, and per the register the target
where `cipher-api` was originally added -- still ran

    $(DC) --profile agents up -d --build ... cipher-api

with no gate. A gate one code path skips is not a gate; an operator bringing up
the agents stack on a drifted node still silently shipped the stale commit.

A second, quieter road turned up in the sweep: `up-core-capable` has no
`--build` at all, but `cipher-api` declares `build:` with no `image:` in
docker-compose.yml and neither overlay that target stacks
(docker-compose.agents.images.yml, docker-compose.hardened.yml) defines
`cipher-api`. So `up -d cipher-api` builds from the worktree whenever the image
is absent -- silent on precisely the fresh node where it fires.

Naming those two targets in a test would repeat the mistake at one remove: the
next target added would be ungated again. So this asserts the PROPERTY over the
whole Makefile -- any recipe that can hand `cipher-api` to `docker compose up`
without `--no-build` carries the gate -- and so it fails on a target that does
not exist yet.

Deliberately static: parses the Makefile text. No docker, no compose, no env
files, so it runs in CI, where the drift it guards is invisible by construction.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES = REPO_ROOT / "pmoves"
MAKEFILE = PMOVES / "Makefile"
COMPOSE = PMOVES / "docker-compose.yml"
CIPHER_DOCKERFILE = REPO_ROOT / "Pmoves-cipher" / "Dockerfile.pmoves"

GATE = "cipher-build-pin-check"
SERVICE = "cipher-api"

# `foo: bar baz ## help` -- but not `FOO := ...` and not `.PHONY:`
TARGET_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.\-/]*)\s*:(?!=)([^\n]*)$")


def _targets() -> dict[str, tuple[str, str]]:
    """{target: (prerequisites, recipe)} for every target in the Makefile.

    A recipe runs from the target line until the first line that is neither
    tab-indented nor blank -- the same rule
    tests/make/test_cipher_collection_provisioned.py uses.
    """
    out: dict[str, tuple[str, str]] = {}
    lines = MAKEFILE.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("\t"):
            continue
        match = TARGET_RE.match(line)
        if not match:
            continue
        name, rest = match.group(1), match.group(2)
        prereqs = rest.split("##", 1)[0]
        recipe: list[str] = []
        for follow in lines[i + 1:]:
            if follow.startswith("\t"):
                recipe.append(follow)
            elif follow.strip() == "":
                continue
            else:
                break
        out[name] = (prereqs, "\n".join(recipe))
    return out


def _can_build_cipher(recipe: str) -> bool:
    """True when a recipe line can hand cipher-api to `docker compose up`.

    Both build shapes count:
      * explicit `--build ... cipher-api`
      * bare `up -d ... cipher-api`, which builds when the image is absent
        because the service declares `build:` and no `image:`.
    `--no-build` is the one shape that structurally cannot build.
    """
    for raw in recipe.splitlines():
        line = raw.strip().lstrip("@").strip()
        if line.startswith("#") or SERVICE not in line:
            continue
        if "--no-build" in line:
            continue
        if not re.search(r"\bup\b", line):
            continue
        if "$(DC)" in line or "docker compose" in line or "$(DC" in line:
            return True
    return False


def _is_gated(name: str, prereqs: str, recipe: str, all_targets: dict) -> bool:
    if GATE in prereqs or GATE in recipe:
        return True
    # Delegating to an already-gated target counts.
    for other, (other_prereqs, _) in all_targets.items():
        if other == name:
            continue
        if GATE in other_prereqs and re.search(r"\b%s\b" % re.escape(other), recipe):
            return True
    return False


def _building_targets() -> dict[str, tuple[str, str]]:
    return {
        name: value for name, value in _targets().items()
        if _can_build_cipher(value[1])
    }


def test_every_road_that_can_build_cipher_runs_the_gate():
    all_targets = _targets()
    ungated = sorted(
        name for name, (prereqs, recipe) in _building_targets().items()
        if not _is_gated(name, prereqs, recipe, all_targets)
    )
    assert not ungated, (
        "these Makefile targets can build %s without running %s, so on a drifted "
        "or mid-change worktree they silently ship something this checkout does "
        "not record: %s" % (SERVICE, GATE, ungated)
    )


def test_the_detector_is_not_vacuous():
    """If this fails, the property test above is guarding nothing."""
    found = set(_building_targets())
    for expected in ("up-cipher", "up-cipher-full", "up-agents-stack", "up-core-capable"):
        assert expected in found, (
            "%s builds %s but the detector missed it -- the property test is blind"
            % (expected, SERVICE)
        )


def test_no_build_road_is_recognised_as_unable_to_build():
    """The exception must stay an exception, not become the loophole."""
    _prereqs, recipe = _targets()["up-cipher-nobuild"]
    assert SERVICE in recipe and "--no-build" in recipe
    assert not _can_build_cipher(recipe), (
        "up-cipher-nobuild uses --no-build and cannot build; gating it would be "
        "a false block on the one road that exists FOR a drifted worktree"
    )


def test_up_core_capable_really_is_a_build_road():
    """Non-vacuity for the quiet road: no `--build`, but no `image:` either.

    If cipher-api ever gains an `image:` -- or an overlay this target stacks
    starts pinning one -- it stops being a build road and the gate on it becomes
    a false block worth removing. Fail here rather than keep a justification
    that has quietly stopped being true.
    """
    text = COMPOSE.read_text(encoding="utf-8")
    start = text.index("\n  %s:\n" % SERVICE)
    nxt = re.search(r"\n  [A-Za-z0-9_.-]+:\n", text[start + 1:])
    block = text[start: start + 1 + nxt.start()] if nxt else text[start:]
    assert "build:" in block, "%s no longer declares build:" % SERVICE
    assert not re.search(r"^\s{4}image:", block, re.MULTILINE), (
        "%s now declares an image:; `up -d %s` would pull instead of build and "
        "the gate on up-core-capable is no longer earning its place"
        % (SERVICE, SERVICE)
    )
    for overlay in ("docker-compose.agents.images.yml", "docker-compose.hardened.yml"):
        path = PMOVES / overlay
        if path.is_file():
            assert SERVICE not in path.read_text(encoding="utf-8"), (
                "%s now defines %s; re-check whether up-core-capable still builds"
                % (overlay, SERVICE)
            )


def test_the_gate_narrows_the_dirty_check_to_what_the_dockerfile_copies():
    """The gate must name the Dockerfile, or it watches the whole worktree.

    Whole-worktree is the safe default in the tool, but on THIS node the real
    Pmoves-cipher worktree carries an untracked `data/` that no COPY reads --
    a permanent false block, and a gate that always blocks gets switched off.
    """
    _prereqs, recipe = _targets()[GATE]
    assert "submodule_build_pin_check.py" in recipe
    assert "Pmoves-cipher:Dockerfile.pmoves" in recipe, (
        "%s must pass the path:dockerfile form so the modified-build-input check "
        "is scoped to the files docker actually copies" % GATE
    )


def test_the_gate_distinguishes_could_not_measure_from_drift():
    """Review F4: exit 3 is not drift, and it is where the operator is told least."""
    _prereqs, recipe = _targets()[GATE]
    assert "-eq 3" in recipe, (
        "the CIPHER_BUILD_PIN=warn branch must say something different for exit 3 "
        "(could not measure) than for exit 1 (drift/dirty)"
    )


def test_non_vacuity_the_dockerfile_still_copies_from_the_build_context():
    """Skips when the submodule is not checked out; CI clones without it."""
    if not CIPHER_DOCKERFILE.is_file():
        pytest.skip("Pmoves-cipher not checked out")
    text = CIPHER_DOCKERFILE.read_text(encoding="utf-8")
    context_copies = [
        line for line in text.splitlines()
        if line.strip().upper().startswith("COPY") and "--from=" not in line
    ]
    assert context_copies, (
        "Dockerfile.pmoves copies nothing from the build context; the narrowed "
        "dirty check would have nothing to watch"
    )
    assert any("src/" in line for line in context_copies), (
        "src/ is no longer copied from the context -- re-check what the gate watches"
    )
