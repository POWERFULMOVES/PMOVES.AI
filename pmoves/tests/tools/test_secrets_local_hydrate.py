"""`secrets-local-hydrate KEYS=...` — force ONE rotated key, touch nothing else.

The problem this pins (2026-11-19, GH_APP_SEC rotation): hydrate overlays a
local.env value only where env.shared is empty/placeholder, and ``--force``
overwrote EVERY matching key. A single rotated GitHub secret therefore could
not be pushed over its stale local value without also force-overwriting the
node-specific keys (SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET,
SUPABASE_ANON_KEY ...) that pair this node's Kong with cipher. ``--keys`` is an
allowlist: keys outside it are never considered, with or without force.

Every fixture is a tmp file. Nothing here reads a real env file.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pmoves.tools import secrets_local_hydrate as slh
from pmoves.tools.secrets_local_hydrate import hydrate, main

CODEX_MK = Path(__file__).resolve().parents[2] / "mk" / "codex.mk"

# Distinctive values so a leak into stdout/stderr is unambiguous.
ROTATED = "rotated-gh-app-secret-VALUE-0001"
STALE = "stale-gh-app-secret-VALUE-0002"
NODE_SRK = "node-local-service-role-VALUE-0003"
FLEET_SRK = "fleet-service-role-VALUE-0004"
NODE_JWT = "node-local-jwt-secret-VALUE-0005"
FLEET_JWT = "fleet-jwt-secret-VALUE-0006"
FRESH = "fresh-value-for-empty-key-VALUE-0007"
ALL_VALUES = (ROTATED, STALE, NODE_SRK, FLEET_SRK, NODE_JWT, FLEET_JWT, FRESH)


@pytest.fixture()
def envs(tmp_path: Path):
    """local.env carries the rotated key AND fleet values for node-specific keys."""
    local = tmp_path / "local.env"
    local.write_text(
        f"GH_APP_SEC={ROTATED}\n"
        f"SUPABASE_SERVICE_ROLE_KEY={FLEET_SRK}\n"
        f"SUPABASE_JWT_SECRET={FLEET_JWT}\n"
        f"EMPTY_IN_SHARED={FRESH}\n",
        encoding="utf-8",
    )
    shared = tmp_path / "env.shared"
    shared.write_text(
        f"GH_APP_SEC={STALE}\n"
        f"SUPABASE_SERVICE_ROLE_KEY={NODE_SRK}\n"
        f"SUPABASE_JWT_SECRET={NODE_JWT}\n"
        "EMPTY_IN_SHARED=\n",
        encoding="utf-8",
    )
    return local, shared, tmp_path


def _isolate(monkeypatch, cleared=(), pinned=()):
    """Point the tombstone/pin readers at fixtures, never the repo's real ones."""
    monkeypatch.setattr(slh, "read_cleared_keys", lambda _p=None: list(cleared))
    monkeypatch.setattr(slh, "_pinned_keys", lambda _p=None: set(pinned))


def _shared_value(shared: Path, key: str) -> str:
    for line in shared.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} missing from fixture env.shared")


# ---------------------------------------------------------------- hydrate() API


def test_keys_filter_limits_the_non_force_overlay(envs, monkeypatch):
    local, shared, _ = envs
    _isolate(monkeypatch)
    # Without the filter EMPTY_IN_SHARED would hydrate; naming a different key
    # must keep it out of scope entirely.
    updates = hydrate(local, shared, keys=["GH_APP_SEC"])
    assert updates == {}  # GH_APP_SEC is non-placeholder in shared, no force
    assert _shared_value(shared, "EMPTY_IN_SHARED") == ""


def test_force_plus_keys_overwrites_only_the_listed_key(envs, monkeypatch):
    local, shared, _ = envs
    _isolate(monkeypatch)
    updates = hydrate(local, shared, force=True, keys=["GH_APP_SEC"])
    assert set(updates) == {"GH_APP_SEC"}
    assert _shared_value(shared, "GH_APP_SEC") == ROTATED
    # The node-specific pairing survives a forced rotation of a different key.
    assert _shared_value(shared, "SUPABASE_SERVICE_ROLE_KEY") == NODE_SRK
    assert _shared_value(shared, "SUPABASE_JWT_SECRET") == NODE_JWT
    assert _shared_value(shared, "EMPTY_IN_SHARED") == ""


def test_baseline_force_without_keys_clobbers_node_specific_keys(envs, monkeypatch):
    """Control: proves the hazard --keys exists to avoid is real."""
    local, shared, _ = envs
    _isolate(monkeypatch)
    updates = hydrate(local, shared, force=True)
    assert {"GH_APP_SEC", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"} <= set(updates)
    assert _shared_value(shared, "SUPABASE_SERVICE_ROLE_KEY") == FLEET_SRK


@pytest.mark.parametrize("guard", ["cleared", "pinned"])
def test_protected_key_named_in_keys_is_still_untouched(envs, monkeypatch, guard):
    local, shared, _ = envs
    kwargs = {guard: ["SUPABASE_JWT_SECRET"]}
    _isolate(monkeypatch, **kwargs)
    for force in (False, True):
        updates = hydrate(local, shared, force=force,
                          keys=["SUPABASE_JWT_SECRET", "GH_APP_SEC"])
        assert "SUPABASE_JWT_SECRET" not in updates
    assert _shared_value(shared, "SUPABASE_JWT_SECRET") == NODE_JWT
    assert _shared_value(shared, "GH_APP_SEC") == ROTATED  # the force pass


def test_force_does_not_report_a_key_whose_value_is_already_current(envs, monkeypatch):
    local, shared, _ = envs
    _isolate(monkeypatch)
    shared.write_text(f"GH_APP_SEC={ROTATED}\n", encoding="utf-8")
    assert hydrate(local, shared, force=True, keys=["GH_APP_SEC"], dry_run=True) == {}


# --------------------------------------------------------------------- CLI main


def _run(argv, capsys):
    rc = main(argv)
    out, err = capsys.readouterr()
    return rc, out, err


def test_cli_keys_force_one_key(envs, monkeypatch, capsys):
    local, shared, _ = envs
    _isolate(monkeypatch)
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared),
                         "--force", "--keys", "GH_APP_SEC"], capsys)
    assert rc == 0
    assert "GH_APP_SEC" in out
    assert "SUPABASE_SERVICE_ROLE_KEY" not in out
    assert _shared_value(shared, "SUPABASE_SERVICE_ROLE_KEY") == NODE_SRK
    assert _shared_value(shared, "GH_APP_SEC") == ROTATED


def test_cli_absent_keys_are_named_and_partial_absence_is_not_fatal(envs, monkeypatch, capsys):
    local, shared, _ = envs
    _isolate(monkeypatch)
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared),
                         "--force", "--keys", "GH_APP_SEC,NOT_IN_LOCAL"], capsys)
    assert rc == 0
    assert "NOT_IN_LOCAL" in err
    assert _shared_value(shared, "GH_APP_SEC") == ROTATED


def test_cli_exits_nonzero_when_no_requested_key_exists(envs, monkeypatch, capsys):
    local, shared, _ = envs
    _isolate(monkeypatch)
    before = shared.read_text(encoding="utf-8")
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared),
                         "--force", "--keys", "NOPE_ONE, NOPE_TWO"], capsys)
    assert rc != 0
    assert "NOPE_ONE" in err and "NOPE_TWO" in err
    assert shared.read_text(encoding="utf-8") == before


def test_cli_empty_keys_list_is_refused_not_treated_as_all(envs, monkeypatch, capsys):
    local, shared, _ = envs
    _isolate(monkeypatch)
    before = shared.read_text(encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["--local-env", str(local), "--env-shared", str(shared),
              "--force", "--keys", " , "])
    assert exc.value.code != 0
    assert shared.read_text(encoding="utf-8") == before


def test_cli_scoped_run_with_missing_local_env_fails_not_succeeds(tmp_path, monkeypatch, capsys):
    # A scoped --force --keys K is an explicit rotation ask; a missing local.env
    # must not be reported as a successful no-op rotation.
    _isolate(monkeypatch)
    shared = tmp_path / "env.shared"
    shared.write_text(f"GH_APP_SEC={STALE}\n", encoding="utf-8")
    rc, out, err = _run(["--local-env", str(tmp_path / "absent.env"),
                         "--env-shared", str(shared),
                         "--force", "--keys", "GH_APP_SEC"], capsys)
    assert rc == 1
    assert "does not exist" in err
    assert _shared_value(shared, "GH_APP_SEC") == STALE


def test_cli_unscoped_missing_local_env_keeps_optional_file_success(tmp_path, monkeypatch, capsys):
    # The optional-file behaviour survives for unscoped runs (hydrate is a
    # best-effort step in the funnel; only the explicit ask is fail-closed).
    _isolate(monkeypatch)
    shared = tmp_path / "env.shared"
    shared.write_text("A=1\n", encoding="utf-8")
    rc, out, err = _run(["--local-env", str(tmp_path / "absent.env"),
                         "--env-shared", str(shared)], capsys)
    assert rc == 0


@pytest.mark.parametrize("guard", ["cleared", "pinned"])
def test_cli_says_why_a_protected_key_was_skipped(envs, monkeypatch, capsys, guard):
    local, shared, _ = envs
    _isolate(monkeypatch, **{guard: ["SUPABASE_JWT_SECRET"]})
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared),
                         "--force", "--keys", "SUPABASE_JWT_SECRET,GH_APP_SEC"], capsys)
    assert rc == 0
    assert re.search(r"SUPABASE_JWT_SECRET.*never overlaid", err)
    assert _shared_value(shared, "SUPABASE_JWT_SECRET") == NODE_JWT


def test_cli_dry_run_lists_names_never_values(envs, monkeypatch, capsys):
    local, shared, _ = envs
    _isolate(monkeypatch)
    before = shared.read_text(encoding="utf-8")
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared),
                         "--dry-run", "--force", "--keys", "GH_APP_SEC,SUPABASE_JWT_SECRET"],
                        capsys)
    assert rc == 0
    assert "GH_APP_SEC" in out and "SUPABASE_JWT_SECRET" in out
    for value in ALL_VALUES:
        # Not the value, and not the masked first-4/last-4 fragment either.
        assert value not in out + err
        assert value[:4] + "..." + value[-4:] not in out + err
    assert shared.read_text(encoding="utf-8") == before


# --------------------------------------------------------------- make wiring


def _hydrate_recipe() -> str:
    text = CODEX_MK.read_text(encoding="utf-8")
    m = re.search(r"^secrets-local-hydrate:[^\n]*\n((?:\t[^\n]*\n)+)", text, re.M)
    assert m, "secrets-local-hydrate target not found in codex.mk"
    return m.group(0)


def test_make_target_documents_keys():
    header = _hydrate_recipe().splitlines()[0]
    assert "KEYS=" in header


@pytest.mark.skipif(shutil.which("make") is None, reason="GNU make not installed")
@pytest.mark.parametrize(
    "cmdline, env_keys, expect",
    [
        ([], None, None),                                    # unset -> no --keys
        (["KEYS=GH_APP_SEC"], None, "GH_APP_SEC"),           # command line -> passed
        (["KEYS=A,B"], None, "A,B"),
        # Explicitly EMPTY KEYS= must still reach the tool as --keys "" (which
        # the tool refuses). Dropping the flag here -- the old $(strip) guard --
        # turned "rotate nothing" into an unscoped --force over every key.
        (["KEYS="], None, ""),
        # A stray exported KEYS (generic name) must NOT silently scope the
        # funnel's hydrate step; only an explicit make argument counts.
        ([], "LEAKED_FROM_SHELL", None),
    ],
)
def test_make_recipe_passes_keys_only_when_set(tmp_path, stub_docker_path, cmdline, env_keys, expect):
    # Run the REAL recipe text under the real make (stub_docker_path: docker /
    # compose resolve to recorders), with the tool replaced by a printer and the
    # env-file prerequisite dropped -- nothing touches a real env file.
    header, *body = _hydrate_recipe().splitlines()
    mk = tmp_path / "t.mk"
    mk.write_text(
        "CODEX_PY := @printf '%s\\n'\n"
        "secrets-local-hydrate:\n" + "\n".join(body).replace("@$(CODEX_PY)", "$(CODEX_PY)") + "\n",
        encoding="utf-8",
    )
    env = stub_docker_path
    for k in ("KEYS", "MAKEFLAGS", "MAKELEVEL"):
        env.pop(k, None)
    if env_keys is not None:
        env["KEYS"] = env_keys
    proc = subprocess.run(["make", "-s", "-f", str(mk), "secrets-local-hydrate", *cmdline],
                          capture_output=True, text=True, env=env, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    args = proc.stdout.split()
    if expect is None:
        assert "--keys" not in args
    elif expect == "":
        assert "--keys" in args and args.index("--keys") == len(args) - 1
    else:
        assert args[args.index("--keys") + 1] == expect


# ------------------------------------------- validation skips are not success
#
# _write_updates drops a value that fails validate_secret_value with only a
# stderr WARNING. main() used to print "Hydrated N keys" listing that key and
# exit 0 -- on the GH_APP_SEC rotation path that reported a rotation which
# never happened.

# A value the WRITE path's validation rejects (concatenated API key + base64
# fragment; fabricated). These tests used a quoted '+'-with-padding value until
# #3498 removed that rule as false (docker compose passes such values
# unchanged, measured). No single-line file value now passes the parser and
# fails the writer, so -- like the raw-newline case -- the bad value is injected
# after parsing, for every key whose file value is the BAD_LINE sentinel.
BAD_PLUS = "fakekey" + "x" * 63 + "==" + "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo"
BAD_LINE = "bad-value-injected-after-parse"


def _inject_bad(monkeypatch):
    real_parse = slh._parse_env

    def parse(path):
        values = real_parse(path)
        return {k: (BAD_PLUS if v == BAD_LINE else v) for k, v in values.items()}

    monkeypatch.setattr(slh, "_parse_env", parse)
# A \n-ESCAPED single-line PEM: the storage form the runbook prescribes.
GOOD_PEM = (
    "-----BEGIN RSA PRIVATE KEY-----\\nMIIEowIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gun"
    "\\nVTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u+qKhbwKfBstIs+bMY2Zkp18gnTxK\\n-----END RSA PRIVATE KEY-----"
)


def _with_raw_newline(monkeypatch, local: Path, key: str):
    """Inject a value with a REAL newline for `key` (a line-based file cannot carry one)."""
    real_parse = slh._parse_env

    def parse(path):
        values = real_parse(path)
        if Path(path) == local:
            values[key] = "-----BEGIN PRIVATE KEY-----\nMIIBOgIBAAJBAKj34\n-----END PRIVATE KEY-----"
        return values

    monkeypatch.setattr(slh, "_parse_env", parse)


@pytest.mark.parametrize("bad", ["concatenated", "raw_newline"])
def test_cli_force_keys_validation_skip_is_a_failure_not_a_success(envs, monkeypatch, capsys, bad):
    local, shared, _ = envs
    _isolate(monkeypatch)
    if bad == "concatenated":
        local.write_text(f"GH_APP_SEC={BAD_LINE}\n", encoding="utf-8")
        _inject_bad(monkeypatch)
    else:
        _with_raw_newline(monkeypatch, local, "GH_APP_SEC")
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared),
                         "--force", "--keys", "GH_APP_SEC"], capsys)
    assert rc == 1
    assert re.search(r"NOT hydrated \(failed validation\)[^\n]*GH_APP_SEC", out + err)
    assert not re.search(r"Hydrated \d+ keys", out), "a skipped key was reported as hydrated"
    assert _shared_value(shared, "GH_APP_SEC") == STALE
    assert BAD_PLUS not in out + err


def test_cli_force_without_keys_any_skip_exits_1_and_valid_keys_still_land(envs, monkeypatch, capsys):
    local, shared, _ = envs
    _isolate(monkeypatch)
    local.write_text(f"GH_APP_SEC={BAD_LINE}\nEMPTY_IN_SHARED={FRESH}\n", encoding="utf-8")
    _inject_bad(monkeypatch)
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared), "--force"], capsys)
    assert rc == 1
    assert re.search(r"NOT hydrated \(failed validation\)[^\n]*GH_APP_SEC", out + err)
    assert _shared_value(shared, "EMPTY_IN_SHARED") == FRESH
    assert _shared_value(shared, "GH_APP_SEC") == STALE


def test_cli_plain_run_lists_skip_but_keeps_exit_0(tmp_path, monkeypatch, capsys):
    _isolate(monkeypatch)
    local = tmp_path / "local.env"
    local.write_text(f"BAD_ONE={BAD_LINE}\nGOOD_ONE={FRESH}\n", encoding="utf-8")
    _inject_bad(monkeypatch)
    shared = tmp_path / "env.shared"
    shared.write_text("BAD_ONE=\nGOOD_ONE=\n", encoding="utf-8")
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared)], capsys)
    assert rc == 0
    assert re.search(r"NOT hydrated \(failed validation\)[^\n]*BAD_ONE", out + err)
    assert re.search(r"Hydrated 1 keys", out)
    assert _shared_value(shared, "BAD_ONE") == ""


def test_cli_dry_run_reports_would_skip(envs, monkeypatch, capsys):
    local, shared, _ = envs
    _isolate(monkeypatch)
    local.write_text(f"GH_APP_SEC={BAD_LINE}\n", encoding="utf-8")
    _inject_bad(monkeypatch)
    before = shared.read_text(encoding="utf-8")
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared),
                         "--dry-run", "--force", "--keys", "GH_APP_SEC"], capsys)
    assert rc == 1
    assert re.search(r"NOT hydrated \(failed validation\)[^\n]*GH_APP_SEC", out + err)
    assert shared.read_text(encoding="utf-8") == before


def test_cli_escaped_single_line_pem_is_written(envs, monkeypatch, capsys):
    local, shared, _ = envs
    _isolate(monkeypatch)
    local.write_text(f"GH_APP_SEC={GOOD_PEM}\n", encoding="utf-8")
    rc, out, err = _run(["--local-env", str(local), "--env-shared", str(shared),
                         "--force", "--keys", "GH_APP_SEC"], capsys)
    assert rc == 0, err
    assert "NOT hydrated" not in out + err
    assert _shared_value(shared, "GH_APP_SEC") == GOOD_PEM
