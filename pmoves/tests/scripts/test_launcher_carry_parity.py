"""Every launcher that resolves a node identity must also report the carry.

`deploy/provision/tests/test-launcher-root-resolution.sh` exists because a
root-resolution fix landed in one launcher and not its two siblings. The python
discovery had the same history: three conventions for one question, two of them
in a single file (#2769), and a `pm_pick_python` fix that landed for
crush-pmoves (#2763) while claude-pmoves kept the broken form.

The carry verdict is the next thing in that family, and it starts out uneven on
purpose — it shipped in claude-pmoves first. This test is the ratchet: the
moment a launcher learns WHO it is, it owes its agent the answer to whether
cipher agrees. A node's agent must not discover that its memories belong to
someone else based on which harness it happened to launch under.

Deliberately NOT asserted: that every launcher appends a system prompt. crush
has no `--append-system-prompt`; its context arrives through an identity file.
The invariant is that the verdict is produced and surfaced, not how.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FRAGMENT = REPO_ROOT / "pmoves" / "scripts" / "pm-cipher-identity.sh"

# Shell launchers only. The .ps1/.cmd twins cannot source a bash fragment and are
# tracked separately — see test_installed_command_gap_is_recorded below.
SHELL_LAUNCHERS = [
    REPO_ROOT / "pmoves" / "scripts" / "claude-pmoves.sh",
    REPO_ROOT / "pmoves" / "scripts" / "crush-pmoves",
    REPO_ROOT / "pmoves" / "scripts" / "kimi-pmoves.sh",
    REPO_ROOT / "pmoves" / "scripts" / "kilo-pmoves.sh",
    REPO_ROOT / "pmoves" / "scripts" / "codex-pmoves.sh",
    REPO_ROOT / "pmoves" / "scripts" / "hermes-pmoves",
    REPO_ROOT / "deploy" / "provision" / "claude-pmoves.sh",
    REPO_ROOT / "deploy" / "provision" / "crush-pmoves.sh",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _sources_fragment(text: str) -> bool:
    """A real `source`/`.` line, not a mention.

    The first version of this helper substring-matched "pm-cipher-identity.sh",
    which every wired launcher ALSO carries in a `# shellcheck source=` comment
    directly above the real line. A mutation that replaced the sourcing line with
    a comment left the shellcheck pragma behind and the test stayed green --
    caught by running that mutation instead of assuming the check worked.
    """
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            continue
        if "pm-cipher-identity.sh" not in line:
            continue
        if line.startswith(". ") or line.startswith("source "):
            return True
    return False


def _invokes_fragment(text: str) -> bool:
    return any(
        ln.strip().startswith("pm_cipher_identity ")
        for ln in text.splitlines()
        if not ln.strip().startswith("#")
    )


def _resolves_identity(text: str) -> bool:
    return "node_identity.py" in text or "node_identity" in text


def test_the_shared_fragment_exists():
    assert FRAGMENT.is_file(), (
        "pm-cipher-identity.sh is the single measurement every launcher sources; "
        "without it the parity check below has nothing to enforce"
    )


@pytest.mark.parametrize("launcher", [p for p in SHELL_LAUNCHERS], ids=lambda p: p.name)
def test_identity_resolving_launchers_also_report_the_carry(launcher: Path):
    if not launcher.is_file():
        pytest.skip(f"{launcher.name} not present in this checkout")
    text = _read(launcher)
    if not _resolves_identity(text):
        # A launcher that never asks who it is cannot be inconsistent about it.
        # It is also the next candidate: see the companion test below.
        pytest.skip(f"{launcher.name} does not resolve a node identity")

    assert _sources_fragment(text), (
        f"{launcher.name} resolves a node identity but never sources "
        "pm-cipher-identity.sh, so its agent is told who it is and not whether "
        "cipher agrees — the exact split this fragment exists to close"
    )
    assert _invokes_fragment(text), (
        f"{launcher.name} sources the fragment but never calls pm_cipher_identity; "
        "sourcing a function and not running it measures nothing"
    )
    assert "PM_CARRY_LINE" in text, (
        f"{launcher.name} sources the fragment but never surfaces PM_CARRY_LINE. "
        "Measuring the carry and not printing it is worse than not measuring: it "
        "looks like the check passed"
    )


def test_at_least_two_harnesses_are_wired():
    """NEGATIVE CONTROL for the parametrised test above.

    Every assertion there is inside a `skip` guard, so a refactor that stopped
    detecting identity resolution — or a typo in the launcher list — would turn
    the whole file green while enforcing nothing. Pin the floor: the fragment was
    introduced precisely because more than one harness needed it.
    """
    wired = [
        p.name
        for p in SHELL_LAUNCHERS
        if p.is_file() and _sources_fragment(_read(p))
    ]
    assert len(wired) >= 2, (
        f"only {wired} source the carry fragment; a shared fragment with one "
        "consumer is a copied block with extra steps"
    )


def test_fragment_always_sets_a_line_on_every_return_path():
    """The skip paths are the ones that matter.

    The first inline version guarded on three conditions with no else, so a node
    with no PyYAML or an unresolved identity printed NOTHING — indistinguishable
    from a node whose carry is fine. Every `return` in the fragment must be
    preceded by an assignment to PM_CARRY_LINE.
    """
    lines = _read(FRAGMENT).splitlines()
    returns = [i for i, ln in enumerate(lines) if ln.strip().startswith("return ")]
    assert returns, "fragment has no return statements — contract not implemented"
    for idx in returns:
        window = "\n".join(lines[max(0, idx - 12) : idx])
        assert "PM_CARRY_LINE=" in window, (
            f"return at line {idx + 1} of pm-cipher-identity.sh is not preceded by a "
            "PM_CARRY_LINE assignment: that path exits silently"
        )


def test_fragment_never_echoes_a_token():
    """It handles a bearer only through the pure tool, which returns a mode."""
    text = _read(FRAGMENT)
    for forbidden in ("$CIPHER_API_TOKEN", "${CIPHER_API_TOKEN"):
        assert forbidden not in text, (
            f"pm-cipher-identity.sh references {forbidden}; the fragment must never "
            "read the bearer itself — cipher_identity.py does, and returns only a mode"
        )


# ---------------------------------------------------------------------------
# The installed `claude-pmoves` command is NOT the launcher that carries any of
# this, on any OS. Measured 2026-09-13:
#
#   install-claude-pmoves-command.ps1:20  ->  deploy/provision/claude-pmoves.cmd
#   claude-pmoves.cmd:4                   ->  deploy/provision/claude-pmoves.ps1
#   install-claude-pmoves-command.sh:91   ->  deploy/provision/claude-pmoves.sh
#
# None of those three resolves a node identity, runs the cipher preflight, or
# reports the carry. Only `make -C pmoves claude-pmoves` reaches
# pmoves/scripts/claude-pmoves.sh, which does all three.
#
# So "it works on Z890" has been true of the MAKE TARGET, and any operator who
# ran the documented installer got a session with none of it — silently, because
# the absence of a verdict looks exactly like a session that was never checked.
#
# This test does not force the gap closed: wiring identity into the provisioning
# launchers is a change to how every node starts a session and is not this lane's
# to make unilaterally. It pins the gap so it cannot be closed by accident and
# then silently reopened, and so the next reader finds it stated rather than
# rediscovering it.
# ---------------------------------------------------------------------------

PROVISION = REPO_ROOT / "deploy" / "provision"


def test_installed_command_gap_is_recorded():
    targets = {
        "claude-pmoves.sh": PROVISION / "claude-pmoves.sh",
        "claude-pmoves.ps1": PROVISION / "claude-pmoves.ps1",
    }
    present = {n: p for n, p in targets.items() if p.is_file()}
    if not present:
        pytest.skip("provisioning launchers not present in this checkout")

    carrying = [n for n, p in present.items() if _sources_fragment(_read(p))]
    if carrying:
        pytest.fail(
            f"{carrying} now report the identity carry — good, and this test is "
            "stale. Move them into SHELL_LAUNCHERS (or add a PowerShell parity "
            "check) and delete this placeholder, so the gap stays measured "
            "rather than assumed closed."
        )

    # The gap as it stands. Stated, not silent.
    for name, path in present.items():
        text = _read(path)
        assert "node_identity" not in text, (
            f"{name} gained identity resolution without the carry — that is the "
            "exact half-wired state this whole lane exists to prevent"
        )
