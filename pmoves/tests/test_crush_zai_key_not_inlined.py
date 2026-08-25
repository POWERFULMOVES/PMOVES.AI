"""The Z.ai key must reach Crush through the environment, never through disk.

Two names for one secret: Crush's README documents `ZAI_API_KEY`; the funnel and
the GitHub secret both spell it `Z_AI_API_KEY` (102 references across the repo).
One underscore apart, so Crush could never read the key env.shared already
carried -- and the workaround was an operator pasting a key into
`~/.config/crush/crush.json`, where it sat in plaintext and could not rotate.

The bridge belongs in the launcher (alias one name onto the other) rather than in
the config file (copy the value onto disk). These tests pin both halves.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGURATOR = REPO_ROOT / "pmoves" / "tools" / "crush_configurator.py"
LAUNCHER = REPO_ROOT / "deploy" / "provision" / "crush-pmoves.sh"

PMOVES_NAME = "Z_AI_API_KEY"   # what the funnel and the GitHub secret call it
CRUSH_NAME = "ZAI_API_KEY"     # what Crush's own README documents


def test_files_exist():
    assert CONFIGURATOR.is_file()
    assert LAUNCHER.is_file()


def test_configurator_does_not_write_the_resolved_secret():
    """`"api_key": zai_key` copied the live secret into the emitted JSON."""
    text = CONFIGURATOR.read_text(encoding="utf-8")
    offenders = re.findall(r'"api_key"\s*:\s*(?!")\w+', text)
    assert not offenders, (
        f"crush_configurator emits a resolved secret as api_key ({offenders}). "
        "Crush reads the key from the environment; writing the value puts it in "
        "~/.config/crush/crush.json at rest, where rotating the funnel changes "
        "nothing."
    )


def test_launcher_bridges_the_two_names():
    """Without the alias, Crush cannot see a key the funnel already delivers."""
    text = LAUNCHER.read_text(encoding="utf-8")
    assert CRUSH_NAME in text, f"launcher never sets {CRUSH_NAME}"
    assert PMOVES_NAME in text, f"launcher never reads {PMOVES_NAME}"
    bridge = re.search(
        rf'export\s+{CRUSH_NAME}=.*{PMOVES_NAME}', text
    ) or re.search(
        rf'{CRUSH_NAME}="\$\{{?{PMOVES_NAME}', text
    )
    assert bridge, f"no {PMOVES_NAME} -> {CRUSH_NAME} assignment found"


def test_bridge_does_not_clobber_an_explicit_value():
    """An operator who exports ZAI_API_KEY themselves must win."""
    text = LAUNCHER.read_text(encoding="utf-8")
    guarded = re.search(rf'-z\s+"\$\{{{CRUSH_NAME}:-\}}"', text)
    assert guarded, (
        f"the {CRUSH_NAME} assignment is unguarded -- it must only apply when "
        "the variable is unset, or it overwrites a deliberate override"
    )


def test_launcher_bridges_before_exec():
    """An export after `exec crush` would never run."""
    text = LAUNCHER.read_text(encoding="utf-8")
    assert text.index(CRUSH_NAME) < text.index("exec crush"), (
        "the name bridge appears after `exec crush` and can never take effect"
    )
