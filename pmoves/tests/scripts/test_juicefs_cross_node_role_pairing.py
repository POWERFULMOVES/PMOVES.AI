"""Role/credential pairing in scripts/juicefs-cross-node-setup.sh.

The defect
----------
The funnel-delivered fallback credential, JUICEFS_META_PASSWORD, is the
``juicefs_meta`` role's password. origin/main defaulted META_ROLE to
``supabase_admin``, so using the funnel credential without naming a role
paired juicefs_meta's password with supabase_admin and always failed auth.
The first fix (an earlier revision of PR #3150) added an automatic pairing that was dead (the
default ran first), and the make recipe defeated it a second time by resolving
the fallback into DB_PASS.

The behaviour now follows the documented precedent
(docs/operations/JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md:92-102, pass META_ROLE
explicitly): an explicit role always wins; the funnel credential without a role
FAILS LOUDLY; it is never silently paired, and never with supabase_admin.

How it is measured
------------------
The script runs for real with ``docker`` resolving to a recorder stub (no
daemon is contacted). The stub answers the storage preflight with
``"Storage": "file"``, so the script refuses (exit 2) before any mount, and the
role is read back from the DSN the script handed to ``docker run``.

Set JUICEFS_PAIRING_SCRIPT to another copy (e.g. ``git show origin/main:...``)
to run the same cases against it as a failing-before control.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
from pmoves.tools.bash_resolver import resolve_bash  # never System32's WSL stub

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES = REPO_ROOT / "pmoves"
SCRIPT = Path(os.environ.get("JUICEFS_PAIRING_SCRIPT") or PMOVES / "scripts" / "juicefs-cross-node-setup.sh")

# Any `docker run --rm` is the storage preflight: answer it so the script stops
# at the file-storage refusal. Everything else just records.
DOCKER_BEHAVIOUR = 'if [ "${1:-}" = run ] && [ "${2:-}" = --rm ]; then echo \'  "Storage": "file",\'; fi'
DSN_ROLE = re.compile(r"postgres://([^@]*)@")


def _role(tmp_path, stub_env_factory, **env: str) -> str:
    stub = stub_env_factory(tmp_path / "stub", base_env={"PATH": os.environ["PATH"], "HOME": str(tmp_path)})
    stub.update({"MOUNT_POINT": str(tmp_path / "mnt"), "DATA_DIR": str(tmp_path / "data"), **env})
    result = subprocess.run([resolve_bash(), str(SCRIPT)], env=stub, capture_output=True, text=True, timeout=60)
    assert result.returncode == 2, f"expected the file-storage refusal (2), got {result.returncode}:\n{result.stdout}\n{result.stderr}"
    dsns = [m.group(1) for call in stub.calls("docker") for arg in call for m in [DSN_ROLE.search(arg)] if m]
    assert dsns, f"no metadata DSN reached docker: {stub.calls('docker')}"
    assert len(set(dsns)) == 1, dsns
    return dsns[0]


@pytest.fixture
def stub_env_factory():
    from pmoves.tests.conftest import _DOCKER_GUARD

    if os.name == "nt":
        pytest.skip("stub tool dir uses POSIX sh recorders")
    return lambda directory, base_env: _DOCKER_GUARD.build_stub_env(
        directory, stub_make=True, base_env=base_env, behaviours={"docker": DOCKER_BEHAVIOUR}
    )


def _run(tmp_path, stub_env_factory, **env: str):
    stub = stub_env_factory(tmp_path / "stub", base_env={"PATH": os.environ["PATH"], "HOME": str(tmp_path)})
    stub.update({"MOUNT_POINT": str(tmp_path / "mnt"), "DATA_DIR": str(tmp_path / "data"), **env})
    result = subprocess.run([resolve_bash(), str(SCRIPT)], env=stub, capture_output=True, text=True, timeout=60)
    return stub, result


@pytest.mark.parametrize("meta_role", [None, ""], ids=["unset", "empty"])
def test_funnel_credential_without_a_role_fails_loudly(tmp_path, stub_env_factory, meta_role):
    env = {"JUICEFS_META_PASSWORD": "fallback-pw"}
    if meta_role is not None:
        env["META_ROLE"] = meta_role
    stub, result = _run(tmp_path, stub_env_factory, **env)
    out = result.stdout + result.stderr
    assert result.returncode == 1, out
    assert "META_ROLE=juicefs_meta" in out and "JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md:92-102" in out, out
    # Fails before anything reaches docker: no DSN, so no silent supabase_admin.
    assert stub.calls("docker") == [], stub.calls("docker")


def test_forwarded_empty_role_with_funnel_credential_fails_loudly(tmp_path, stub_env_factory):
    # What the recipe sends when the operator named nothing: empty JFS_SETUP_*.
    env = {"JFS_SETUP_META_ROLE": "", "JFS_SETUP_DB_PASS": "", "JUICEFS_META_PASSWORD": "fallback-pw"}
    stub, result = _run(tmp_path, stub_env_factory, **env)
    assert result.returncode == 1 and stub.calls("docker") == []


def test_documented_path_uses_juicefs_meta(tmp_path, stub_env_factory):
    # The runbook invocation: META_ROLE=juicefs_meta, funnel credential, no DB_PASS.
    env = {"JFS_SETUP_META_ROLE": "juicefs_meta", "JFS_SETUP_DB_PASS": "", "JUICEFS_META_PASSWORD": "fallback-pw"}
    assert _role(tmp_path, stub_env_factory, **env) == "juicefs_meta"


def test_explicit_db_pass_without_role_keeps_default_and_says_so(tmp_path, stub_env_factory):
    stub, result = _run(tmp_path, stub_env_factory, DB_PASS="explicit-pw")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "back-compat default supabase_admin" in result.stdout
    dsns = [m.group(1) for call in stub.calls("docker") for arg in call for m in [DSN_ROLE.search(arg)] if m]
    assert set(dsns) == {"supabase_admin"}, dsns


@pytest.mark.parametrize("role", ["supabase_admin", "juicefs_meta"])
def test_named_role_always_wins(tmp_path, stub_env_factory, role):
    assert _role(tmp_path, stub_env_factory, META_ROLE=role, JUICEFS_META_PASSWORD="fallback-pw") == role


def test_make_forwarded_role_beats_node_env_file(tmp_path, stub_env_factory):
    # with-env.sh re-sources .env.local over the caller's env, so a node file's
    # META_ROLE is what the script sees as META_ROLE; the command-line value
    # arrives as JFS_SETUP_META_ROLE and must win.
    env = {"META_ROLE": "juicefs_meta", "JFS_SETUP_META_ROLE": "supabase_admin", "DB_PASS": "pw"}
    assert _role(tmp_path, stub_env_factory, **env) == "supabase_admin"


@pytest.mark.parametrize(
    "password",
    [
        # BRE `ab*c` matches a, any b's, then c, so it does NOT match the literal
        # "ab*c": a regex grep keeps the line and prints the password. This is the
        # silent leak path (grep exits 0, nothing looks wrong).
        "ab*c",
        # An unbalanced bracket makes a regex grep error out ("Unmatched [") and
        # swallow every diagnostic line instead.
        "p.ss[w0rd*",
    ],
    ids=["regex-leak", "regex-error"],
)
def test_redaction_is_literal_not_regex(tmp_path, stub_env_factory, password):
    # A preflight with no Storage field prints the probe output with the
    # credential's lines removed.
    stub = stub_env_factory(tmp_path / "stub", base_env={"PATH": os.environ["PATH"], "HOME": str(tmp_path)})
    (stub.stub_dir / "docker").write_text(
        (stub.stub_dir / "docker").read_text().replace(
            DOCKER_BEHAVIOUR,
            f'if [ "${{1:-}}" = run ] && [ "${{2:-}}" = --rm ]; then echo \'auth failed for {password}\'; echo \'other line\'; fi',
        )
    )
    stub.update({"MOUNT_POINT": str(tmp_path / "mnt"), "DATA_DIR": str(tmp_path / "data"), "DB_PASS": password, "META_ROLE": "juicefs_meta"})
    result = subprocess.run([resolve_bash(), str(SCRIPT)], env=stub, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    assert password not in result.stdout + result.stderr
    assert "other line" in result.stderr


def test_make_recipe_does_not_resolve_the_fallback_into_db_pass():
    recipe = (PMOVES / "mk" / "egress.mk").read_text(encoding="utf-8")
    body = re.split(r"(?m)^juicefs-cross-node-setup:", recipe, maxsplit=1)[1].split("\n\n", 1)[0]
    command = "\n".join(
        line for line in body.splitlines()[1:] if line.startswith("\t") and not line.lstrip("\t").startswith("@#")
    )
    assert "JUICEFS_META_PASSWORD" not in command, command
    assert 'JFS_SETUP_DB_PASS="$(DB_PASS)"' in command
    assert 'JFS_SETUP_META_ROLE="$(META_ROLE)"' in command
