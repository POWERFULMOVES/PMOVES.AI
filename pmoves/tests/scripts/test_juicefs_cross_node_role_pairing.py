"""Role/credential pairing in scripts/juicefs-cross-node-setup.sh.

The defect
----------
The funnel-delivered fallback credential, JUICEFS_META_PASSWORD, is the
``juicefs_meta`` role's password. When DB_PASS arrives via that fallback and no
role was named, the metadata DSN must use ``juicefs_meta``: ``supabase_admin``
paired with juicefs_meta's password always fails auth.

origin/main had no pairing at all (META_ROLE defaulted to supabase_admin). The
first fix (#3150 @ 6e13d0f18) added a rule but assigned the default FIRST, so
"no role named" could never be observed and the rule was dead. A second,
independent defeat lived in mk/egress.mk: the recipe resolved the fallback into
DB_PASS itself, so the script always saw an "explicit" DB_PASS.

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
    result = subprocess.run(["bash", str(SCRIPT)], env=stub, capture_output=True, text=True, timeout=60)
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


@pytest.mark.parametrize("meta_role", [None, ""], ids=["unset", "empty"])
def test_fallback_credential_pairs_with_juicefs_meta(tmp_path, stub_env_factory, meta_role):
    env = {"JUICEFS_META_PASSWORD": "fallback-pw"}
    if meta_role is not None:
        env["META_ROLE"] = meta_role
    assert _role(tmp_path, stub_env_factory, **env) == "juicefs_meta"


def test_explicit_db_pass_keeps_supabase_admin_default(tmp_path, stub_env_factory):
    assert _role(tmp_path, stub_env_factory, DB_PASS="explicit-pw", JUICEFS_META_PASSWORD="fallback-pw") == "supabase_admin"


def test_no_credential_hint_keeps_supabase_admin_default(tmp_path, stub_env_factory):
    assert _role(tmp_path, stub_env_factory, DB_PASS="explicit-pw") == "supabase_admin"


@pytest.mark.parametrize("role", ["supabase_admin", "juicefs_meta"])
def test_named_role_always_wins(tmp_path, stub_env_factory, role):
    assert _role(tmp_path, stub_env_factory, META_ROLE=role, JUICEFS_META_PASSWORD="fallback-pw") == role


def test_make_forwarded_role_beats_node_env_file(tmp_path, stub_env_factory):
    # with-env.sh re-sources .env.local over the caller's env, so a node file's
    # META_ROLE is what the script sees as META_ROLE; the command-line value
    # arrives as JFS_SETUP_META_ROLE and must win.
    env = {"META_ROLE": "juicefs_meta", "JFS_SETUP_META_ROLE": "supabase_admin", "DB_PASS": "pw"}
    assert _role(tmp_path, stub_env_factory, **env) == "supabase_admin"


def test_make_forwarding_empty_db_pass_is_not_explicit(tmp_path, stub_env_factory):
    # What the recipe sends when the operator named nothing: empty JFS_SETUP_*.
    env = {"JFS_SETUP_META_ROLE": "", "JFS_SETUP_DB_PASS": "", "JUICEFS_META_PASSWORD": "fallback-pw"}
    assert _role(tmp_path, stub_env_factory, **env) == "juicefs_meta"


def test_redaction_is_literal_not_regex(tmp_path, stub_env_factory):
    # A preflight with no Storage field prints the probe output with the
    # credential's lines removed. A regex grep lets a password with BRE
    # metacharacters fail to match its own line and print it.
    password = "p.ss[w0rd*"
    stub = stub_env_factory(tmp_path / "stub", base_env={"PATH": os.environ["PATH"], "HOME": str(tmp_path)})
    (stub.stub_dir / "docker").write_text(
        (stub.stub_dir / "docker").read_text().replace(
            DOCKER_BEHAVIOUR,
            f'if [ "${{1:-}}" = run ] && [ "${{2:-}}" = --rm ]; then echo \'auth failed for {password}\'; echo \'other line\'; fi',
        )
    )
    stub.update({"MOUNT_POINT": str(tmp_path / "mnt"), "DATA_DIR": str(tmp_path / "data"), "DB_PASS": password})
    result = subprocess.run(["bash", str(SCRIPT)], env=stub, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
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
