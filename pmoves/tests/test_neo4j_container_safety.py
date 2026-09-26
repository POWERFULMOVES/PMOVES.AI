"""Neo4j lifecycle scripts must never start a second Neo4j, or a volumeless one.

On Knuckles (2026-09) the live graph ran in an out-of-compose container named
`pmoves-neo4j` on the only Neo4j volume, `pmoves_neo4j-data`. Every lifecycle
path disagreed about its name, and each one's fallback was destructive:

  * backup-neo4j.sh looked for `pmoves-neo4j-1`, never found it, and ran
    `compose up -d neo4j`: a SECOND Neo4j on the volume the first one held.
  * `make neo4j-backup` looked it up with `$(DC) ps -q neo4j`, which cannot see
    an out-of-compose container, and fell through to `neo4j-local-up`: the same.
  * `make neo4j-restore` removed only the compose service, then ran a volume
    removal that silently failed on the held volume, then started a compose
    Neo4j beside the running one.
  * start-cipher-stack.sh force-removed `pmoves-neo4j` and started a replacement
    with NO volume, an empty graph in place of the live one.

The name now has ONE source (`services.neo4j.container_name`, read by
scripts/neo4j_container.py). These tests run the real scripts against a stub
`docker` that only records its argv; nothing touches a real container.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]
SCRIPTS = PMOVES / "scripts"
HELPER = SCRIPTS / "neo4j_container.py"

sys.path.insert(0, str(SCRIPTS))
import neo4j_container  # noqa: E402

FAKE_COMPOSE = "services:\n  neo4j:\n    image: neo4j:x\n    container_name: fake-neo4j\n"

STUB_DOCKER = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG"
if [ "$1" = "ps" ]; then
  for n in $FAKE_RUNNING; do echo "$n"; done
fi
exit 0
"""


def _tree(tmp_path: Path, script: str) -> Path:
    """A throwaway pmoves/ with the real script + helper and a fake compose."""
    root = tmp_path / "pmoves"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPTS / script, root / "scripts" / script)
    shutil.copy2(HELPER, root / "scripts" / "neo4j_container.py")
    (root / "docker-compose.yml").write_text(FAKE_COMPOSE)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {
        "docker": STUB_DOCKER,
        "curl": "#!/usr/bin/env bash\nexit 0\n",
        "sleep": "#!/usr/bin/env bash\nexit 0\n",
    }.items():
        f = bin_dir / name
        f.write_text(body)
        f.chmod(0o755)
    return root


def _run(tmp_path: Path, script: str, running: str) -> tuple[int, list[list[str]], str]:
    root = _tree(tmp_path, script)
    log = tmp_path / "docker.log"
    env = dict(os.environ)
    env.update(
        PATH=f"{tmp_path / 'bin'}:{env['PATH']}",
        STUB_LOG=str(log),
        FAKE_RUNNING=running,
    )
    proc = subprocess.run(
        ["bash", str(root / "scripts" / script)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )
    calls = [ln.split() for ln in log.read_text().splitlines()] if log.exists() else []
    return proc.returncode, calls, proc.stdout + proc.stderr


def _neo4j_mutations(calls: list[list[str]]) -> list[list[str]]:
    """docker calls that would remove, start or compose-up a Neo4j."""
    bad = []
    for c in calls:
        if not c:
            continue
        if c[0] == "rm" and any("neo4j" in a for a in c):
            bad.append(c)
        elif c[0] == "run" and any("neo4j" in a for a in c):
            bad.append(c)
        elif c[0] == "compose" and "up" in c:
            bad.append(c)
    return bad


# --- the single name source -------------------------------------------------

def test_the_helper_reads_container_name_from_compose(tmp_path):
    f = tmp_path / "docker-compose.yml"
    f.write_text(FAKE_COMPOSE)
    assert neo4j_container.container_name(f) == "fake-neo4j"


def test_no_container_name_is_could_not_measure_not_a_guess(tmp_path):
    f = tmp_path / "docker-compose.yml"
    f.write_text("services:\n  neo4j:\n    image: neo4j:x\n")
    proc = subprocess.run([sys.executable, str(HELPER), str(f)], capture_output=True, text=True)
    assert proc.returncode == 3
    assert proc.stdout == ""


@pytest.mark.xfail(
    strict=True,
    reason="awaits KNOWN_ROAD compose:pr:3193: container_name is not declared in "
    "docker-compose.yml yet. strict=True makes this FAIL the moment it is, so the "
    "marker cannot outlive the change it waits for.",
)
def test_the_real_compose_names_the_live_container():
    """The name the live Knuckles container already has, so Phase 1b keeps it."""
    assert neo4j_container.container_name() == "pmoves-neo4j"


# --- backup-neo4j.sh --------------------------------------------------------

def test_backup_refuses_instead_of_starting_a_second_neo4j(tmp_path):
    rc, calls, out = _run(tmp_path, "backup-neo4j.sh", running="")
    assert rc == 1, out
    assert _neo4j_mutations(calls) == [], calls
    assert "not running" in out


def test_backup_uses_the_compose_declared_name(tmp_path):
    rc, calls, out = _run(tmp_path, "backup-neo4j.sh", running="fake-neo4j")
    execs = [c for c in calls if c[:1] == ["exec"]]
    assert execs and all(c[1] == "fake-neo4j" for c in execs), calls
    assert _neo4j_mutations(calls) == [], calls


# --- start-cipher-stack.sh --------------------------------------------------

def test_start_cipher_stack_leaves_a_running_neo4j_alone(tmp_path):
    rc, calls, out = _run(tmp_path, "start-cipher-stack.sh", running="fake-neo4j")
    assert _neo4j_mutations(calls) == [], calls
    assert "leaving it untouched" in out


def test_start_cipher_stack_never_starts_a_volumeless_neo4j(tmp_path):
    rc, calls, out = _run(tmp_path, "start-cipher-stack.sh", running="")
    assert rc == 1, out
    assert _neo4j_mutations(calls) == [], calls
    assert "up-data-tier DATA_SERVICES=neo4j" in out


# --- Makefile targets ---------------------------------------------------------

def _recipe(target: str) -> str:
    text = (PMOVES / "Makefile").read_text()
    start = text.index(f"\n{target}:")
    end = text.index("\n\n", start + 1)
    return text[start:end]


def test_make_neo4j_backup_does_not_start_neo4j():
    r = _recipe("neo4j-backup")
    assert "neo4j-local-up" not in r
    assert "container_name=$$($(DC) ps -q neo4j" not in r, "the lookup that cannot see the live container"
    assert "scripts/neo4j_container.py" in r


def test_make_neo4j_restore_refuses_over_an_out_of_compose_container():
    r = _recipe("neo4j-restore")
    guard = r.index("not managed by compose")
    assert guard < r.index("neo4j-local-down"), "the refusal must precede the destructive steps"
    assert "container_name=$$($(DC) ps -q neo4j" not in r
    assert "scripts/neo4j_container.py" in r


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_make_n_neo4j_backup_renders_no_start():
    """Dry run of the real target (it has no nested make, so -n executes nothing)."""
    proc = subprocess.run(
        ["make", "-s", "-n", "-C", str(PMOVES), "neo4j-backup"],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert "neo4j-local-up" not in proc.stdout
    assert "up -d neo4j" not in proc.stdout


def test_make_neo4j_restore_volume_removal_fails_closed():
    """A removal that failed (volume held by another Neo4j) used to be swallowed,
    and the recipe went on to start and load over that volume."""
    r = _recipe("neo4j-restore")
    vol_lines = [ln for ln in r.splitlines()
                 if "pmoves_neo4j-data" in ln and not ln.strip().startswith(("@#", "#", "@echo", "echo"))]
    assert vol_lines, "restore no longer touches the volume -- update this test"
    for ln in vol_lines:
        assert not ln.rstrip().endswith("|| true"), ln
        assert "exit 1" in ln, ln
