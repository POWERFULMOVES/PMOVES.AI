"""The Z.ai key must reach Crush through the environment, never through disk.

Two names for one secret: Crush's README documents `ZAI_API_KEY`; the funnel and
the GitHub secret both spell it `Z_AI_API_KEY` (102 references across the repo).
One underscore apart, so Crush could never read the key env.shared already
carried -- and the workaround was an operator pasting a key into
`~/.config/crush/crush.json`, where it sat in plaintext and could not rotate.

The bridge belongs in the launcher (alias one name onto the other) rather than in
the config file (copy the value onto disk). These tests pin both halves.

The tests come in two kinds, and the split is the point:

  text-level    read the launchers as source. Cheap, and they pin intent.
  behavioural   source the loader, then read the result from a CHILD PROCESS.

The first cut shipped only the text-level kind, and the bridge it pinned was a
no-op on every run. `crush-env.sh` parses every key it finds into an ENV_MAP and
then exports only an explicit ALLOWLIST of them. `Z_AI_API_KEY` was not on that
list, so the bridge's `-n "${Z_AI_API_KEY:-}"` guard could never be true -- and a
test that greps for the bridge passes either way. Crush is a separate process
(`exec crush`) and inherits exported variables only, so the child is the one
place where "set" and "exported" look different.

Nothing below asserts on a real secret. The behavioural tests run the real loader
over synthetic sentinels defined in this file; the single live check reports
lengths only.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGURATOR = REPO_ROOT / "pmoves" / "tools" / "crush_configurator.py"
# BOTH loaders. `make install-tools` installs pmoves/scripts/crush-pmoves, which
# sources crush-env.sh -- the first cut bridged only the deploy/provision path,
# which the installed command never takes (Codex P1 on #2764).
LOADER = REPO_ROOT / "pmoves" / "scripts" / "crush-env.sh"
LAUNCHERS = [
    LOADER,
    REPO_ROOT / "deploy" / "provision" / "crush-pmoves.sh",
]

PMOVES_NAME = "Z_AI_API_KEY"   # what the funnel and the GitHub secret call it
CRUSH_NAME = "ZAI_API_KEY"     # what Crush's own README documents


def test_files_exist():
    assert CONFIGURATOR.is_file()
    for path in LAUNCHERS:
        assert path.is_file(), f"launcher/loader missing: {path}"


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


@pytest.mark.parametrize("LAUNCHER", LAUNCHERS, ids=lambda p: p.name)
def test_launcher_bridges_the_two_names(LAUNCHER):
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


@pytest.mark.parametrize("LAUNCHER", LAUNCHERS, ids=lambda p: p.name)
def test_bridge_does_not_clobber_an_explicit_value(LAUNCHER):
    """An operator who exports ZAI_API_KEY themselves must win."""
    text = LAUNCHER.read_text(encoding="utf-8")
    guarded = re.search(rf'-z\s+"\$\{{{CRUSH_NAME}:-\}}"', text)
    assert guarded, (
        f"the {CRUSH_NAME} assignment is unguarded -- it must only apply when "
        "the variable is unset, or it overwrites a deliberate override"
    )


def test_bridge_precedes_exec_where_the_file_execs():
    """An export after `exec crush` would never run."""
    for path in LAUNCHERS:
        text = path.read_text(encoding="utf-8")
        if "exec crush" not in text:
            continue  # a sourced loader has no exec of its own
        assert text.index(CRUSH_NAME) < text.index("exec crush"), (
            f"{path.name}: the bridge appears after `exec crush`"
        )


# ---------------------------------------------------------------------------
# Behavioural: does the key actually cross into the child?
# ---------------------------------------------------------------------------

# Synthetic, and distinct in length so no assertion can pass by reading the
# wrong one. Nothing here is or resembles a credential.
SENTINEL = "sentinel-not-a-real-key-00000000"           # 32
OPERATOR_SENTINEL = "operator-exported-this-one-explicitly"  # 37
UNLISTED_SENTINEL = "sentinel-for-an-unlisted-key"       # 28

# A key the loader parses but must NOT export -- the negative control that stops
# the fix from quietly turning the allowlist into a bulk export.
UNLISTED_KEY = "PMOVES_TEST_UNLISTED_KEY"

# The loader reads a fixed set of tier files relative to its own location; this
# is the one the funnel actually delivers the Z.ai key in.
TIER_FILE = "env.tier-llm"


def _lengths_seen_by_child(loader_path, names, preset=None):
    """Source `loader_path`, then read `names` from a CHILD process.

    The sourcing shell's own view is deliberately not consulted: a variable that
    is merely SET there is invisible to `exec crush`. Only lengths are printed,
    so no value can leak into pytest output on failure.
    """
    probe = "; ".join(f'printf "{n}=%s\\n" "${{#{n}}}"' for n in names)
    script = f'. "{loader_path}" >/dev/null 2>&1\nbash --noprofile --norc -c \'{probe}\'\n'

    env = {
        k: v
        for k, v in os.environ.items()
        # start from a shell carrying none of the three, so the loader's
        # "only when unset" guards are exercised rather than short-circuited
        if k not in {CRUSH_NAME, PMOVES_NAME, UNLISTED_KEY}
    }
    env.update(preset or {})

    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    seen = {}
    for line in proc.stdout.splitlines():
        name, _, value = line.partition("=")
        if name in names and value.isdigit():
            seen[name] = int(value)
    missing = set(names) - set(seen)
    assert not missing, (
        f"child probe produced no reading for {sorted(missing)} "
        f"(rc={proc.returncode}); stderr: {proc.stderr[-400:]}"
    )
    return seen


@pytest.fixture
def synthetic_loader(tmp_path):
    """The real `crush-env.sh` over a synthetic tier file. No real secrets.

    The loader derives its repo root from its own location, so a copy dropped
    into `<tmp>/pmoves/scripts/` reads the tier files under `<tmp>` and nothing
    on this machine is touched.
    """
    pmoves_dir = tmp_path / "pmoves"
    scripts = pmoves_dir / "scripts"
    scripts.mkdir(parents=True)
    copied = scripts / LOADER.name
    shutil.copy2(LOADER, copied)
    (pmoves_dir / TIER_FILE).write_text(
        f"{PMOVES_NAME}={SENTINEL}\n{UNLISTED_KEY}={UNLISTED_SENTINEL}\n",
        encoding="utf-8",
    )
    return copied


def test_the_funnel_name_is_exported(synthetic_loader):
    """Drop Z_AI_API_KEY from the allowlist in crush-env.sh and this fails.

    It is the precondition for the bridge: the bridge reads Z_AI_API_KEY out of
    the environment, and only allowlisted keys are ever put there.
    """
    seen = _lengths_seen_by_child(synthetic_loader, [PMOVES_NAME])
    assert seen[PMOVES_NAME] == len(SENTINEL), (
        f"{PMOVES_NAME} never left ENV_MAP. crush-env.sh exports an explicit "
        "allowlist; a key absent from it stays parsed-but-unexported, and the "
        "name bridge below it has nothing to fire on."
    )


def test_bridge_reaches_a_child_process(synthetic_loader):
    """The regression the text-level tests above cannot see.

    Fails if the bridge is a no-op, if it is removed, or if it assigns
    ZAI_API_KEY without exporting it -- three states a grep cannot tell apart.
    """
    seen = _lengths_seen_by_child(synthetic_loader, [CRUSH_NAME])
    assert seen[CRUSH_NAME] == len(SENTINEL), (
        f"{CRUSH_NAME} did not reach the child process. `exec crush` inherits "
        "only exported variables, so Crush would launch with no Z.ai key."
    )


def test_allowlist_is_still_an_allowlist(synthetic_loader):
    """Negative control: the fix must not become a bulk export.

    That allowlist governs which secrets enter Crush's process env. A key the
    loader parses but does not list must stay out of the child.
    """
    seen = _lengths_seen_by_child(synthetic_loader, [UNLISTED_KEY])
    assert seen[UNLISTED_KEY] == 0, (
        f"{UNLISTED_KEY} crossed into the child without being allowlisted -- "
        "crush-env.sh is exporting in bulk, widening Crush's secret exposure"
    )


def test_explicit_override_survives_to_the_child(synthetic_loader):
    """An operator who exports ZAI_API_KEY must still win, in the child too."""
    assert len(OPERATOR_SENTINEL) != len(SENTINEL), "sentinels must differ in length"
    seen = _lengths_seen_by_child(
        synthetic_loader, [CRUSH_NAME], preset={CRUSH_NAME: OPERATOR_SENTINEL}
    )
    assert seen[CRUSH_NAME] == len(OPERATOR_SENTINEL), (
        f"the bridge clobbered an explicitly-exported {CRUSH_NAME}"
    )


def test_live_loader_delivers_the_key_to_a_child():
    """On a funnelled node, the real loader must hand Crush a real key.

    Lengths only. The value is never read into this process, never asserted on,
    never logged. Skips where the funnel has not populated the key, so this is a
    node-local regression guard rather than a CI requirement.
    """
    seen = _lengths_seen_by_child(LOADER, [CRUSH_NAME, PMOVES_NAME])
    if seen[PMOVES_NAME] == 0:
        pytest.skip(f"{PMOVES_NAME} absent from this node's tier env")
    assert seen[CRUSH_NAME] == seen[PMOVES_NAME], (
        f"{PMOVES_NAME} is present on this node but {CRUSH_NAME} did not reach "
        "the child -- Crush would still launch without a Z.ai key"
    )
