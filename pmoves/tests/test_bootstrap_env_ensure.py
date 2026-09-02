"""Tests for bootstrap_env.ensure_secret — the secrets-funnel minting primitive.

``ensure_secret`` mints a stack-generated secret into env.shared ONLY when the
slot is absent or empty. It exists because SECRET_KEY_BASE, VAULT_ENC_KEY and the
two LOGFLARE tokens are declared ``required: true`` in both the bootstrap registry
(with generators) and the CHIT manifest, yet no step of ``make secrets-funnel``
ever ran a generator for them. They never reached env.shared, never reached the
CGP bundle, secrets_sync classified them operator-missing, and -- because a
missing required entry lands in ``rejected_out`` -- the funnel actively DELETED
them from the generated tier file. Compose's ``${SECRET_KEY_BASE:?}`` then failed,
and since compose interpolates the whole project before acting, four unset
Supabase variables blocked ``up -d cipher-api`` and every unrelated service.

The load-bearing property under test is the NEGATIVE one: an existing value is
never overwritten. VAULT_ENC_KEY is read with ``bytes.fromhex()`` by the yt OAuth
vault, so a rotation is a data-loss event for stored OAuth cookies.
"""

from __future__ import annotations

import importlib.util
import json
import string
import sys
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_env.py"
_spec = importlib.util.spec_from_file_location("bootstrap_env_ensure_under_test", _MOD_PATH)
be = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass annotation resolution can find the module.
sys.modules[_spec.name] = be
_spec.loader.exec_module(be)

REGISTRY = Path(__file__).resolve().parents[1] / "bootstrap" / "registry.json"


def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


def test_mints_when_key_is_absent(tmp_path):
    env = _write(tmp_path / "env.shared", "FOO=keep\n")
    generated, reason = be.ensure_secret(
        "LOGFLARE_PUBLIC_ACCESS_TOKEN", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is True
    assert "generated" in reason
    assert len(be.read_env_value("LOGFLARE_PUBLIC_ACCESS_TOKEN", env)) == 32
    assert be.read_env_value("FOO", env) == "keep"


def test_mints_when_key_is_present_but_empty(tmp_path):
    env = _write(tmp_path / "env.shared", "SECRET_KEY_BASE=\n")
    generated, _ = be.ensure_secret(
        "SECRET_KEY_BASE", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is True

    # 64 is a FLOOR, not a target. Phoenix rejects a shorter value at boot
    # ("cookie store expects conn.secret_key_base to be at least 64 bytes") and
    # PMOVES-supabase/docker/CONFIG.md:926 calls 64 the *recommended* length --
    # neither is an upper bound. #2881 raised the registry 64 -> 96 for margin,
    # after a 48-char value held supabase-realtime in a crash loop.
    #
    # Units: `random_urlsafe` is `secrets.token_urlsafe(n)[:n]`, so a declared
    # length is output CHARACTERS. That alphabet is ASCII, so N characters is N
    # bytes and the registry and Phoenix specs are directly comparable.
    # (Contrast VAULT_ENC_KEY: `random_hex` length is also characters, but the
    # yt OAuth vault feeds it to bytes.fromhex(), so 32 chars is 16 bytes.)
    #
    # Assert against the registry so a deliberate bump is not a test failure,
    # and assert the floor separately so a bump *below* what Supabase accepts
    # fails here rather than at container boot.
    minted = be.read_env_value("SECRET_KEY_BASE", env)
    declared = be._registry_generator("SECRET_KEY_BASE", str(REGISTRY))
    assert len(minted) == declared["length"]
    assert len(minted) >= 64


def test_never_overwrites_an_existing_value(tmp_path):
    """The safety property: a live secret is never rotated by the funnel."""
    live = "deadbeefdeadbeefdeadbeefdeadbeef"
    env = _write(tmp_path / "env.shared", f"VAULT_ENC_KEY={live}\n")
    generated, reason = be.ensure_secret(
        "VAULT_ENC_KEY", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is False
    assert reason == "already set"
    assert be.read_env_value("VAULT_ENC_KEY", env) == live


def test_does_not_reshape_a_value_that_fails_the_format_check(tmp_path):
    """A malformed value is left ALONE here.

    ``bootstrap()`` regenerates a slot failing ``value_matches_spec``; that
    self-heal must stay operator-invoked (``make env-setup``) rather than fire on
    every funnel run, because reshaping VAULT_ENC_KEY destroys stored yt OAuth
    cookies. ensure_secret only ever fills a hole.
    """
    malformed = "not-hex-at-all-zzzz"  # would FAIL random_hex value_matches_spec
    assert not be.value_matches_spec(malformed, {"type": "random_hex", "length": 32})
    env = _write(tmp_path / "env.shared", f"VAULT_ENC_KEY={malformed}\n")
    generated, _ = be.ensure_secret(
        "VAULT_ENC_KEY", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is False
    assert be.read_env_value("VAULT_ENC_KEY", env) == malformed


def test_is_idempotent(tmp_path):
    env = _write(tmp_path / "env.shared", "# header\nFOO=keep\n")
    be.ensure_secret("SECRET_KEY_BASE", env_path=env, registry_path=str(REGISTRY))
    after_first = env.read_text(encoding="utf-8")
    generated, reason = be.ensure_secret(
        "SECRET_KEY_BASE", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is False and reason == "already set"
    assert env.read_text(encoding="utf-8") == after_first
    assert after_first.startswith("# header")


def test_honours_the_registry_declared_generator_type(tmp_path):
    """VAULT_ENC_KEY must come out hex, not urlsafe.

    The yt OAuth vault does bytes.fromhex() on it. A urlsafe value parses as a
    secret, satisfies compose's ${VAR:?}, and then raises ValueError at use.
    """
    env = _write(tmp_path / "env.shared", "")
    be.ensure_secret("VAULT_ENC_KEY", env_path=env, registry_path=str(REGISTRY))
    value = be.read_env_value("VAULT_ENC_KEY", env)
    assert len(value) == 32
    assert all(c in string.hexdigits for c in value)
    bytes.fromhex(value)  # the actual downstream consumer's call


def test_refuses_a_key_with_no_declared_generator(tmp_path):
    """No generator means no invented value -- an operator secret stays missing."""
    env = _write(tmp_path / "env.shared", "")
    generated, reason = be.ensure_secret(
        "ANTHROPIC_API_KEY", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is False
    assert "no generator" in reason
    assert be.read_env_value("ANTHROPIC_API_KEY", env) is None


def test_read_env_value_is_last_wins_and_skips_comments(tmp_path):
    """Matches chit_encode_secrets' parser: the last duplicate is what is read."""
    env = _write(
        tmp_path / "env.shared",
        "# SECRET_KEY_BASE=commented\nSECRET_KEY_BASE=first\nSECRET_KEY_BASE=second\n",
    )
    assert be.read_env_value("SECRET_KEY_BASE", env) == "second"
    assert be.read_env_value("ABSENT_KEY", env) is None


def test_the_four_blocking_keys_are_generatable_from_the_registry():
    """Guard the registry contract the funnel now depends on.

    If someone drops a generator from one of these, the funnel silently returns
    to warning-while-compose-fails. Fail here instead.
    """
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    specs = {
        v["key"]: v.get("generate")
        for s in data.get("services", [])
        for v in s.get("variables", [])
    }
    # 96, not 64, since #2881: 64 is Phoenix's floor and Supabase's
    # "recommended length", not a maximum, and it cleared the floor with zero
    # margin. Pinned literally on purpose -- this test's job is to notice an
    # edit to the registry, so it is meant to fail on a bump and be updated
    # deliberately. If you are here because it failed: check the new value is
    # still >= 64 characters before changing it.
    assert specs["SECRET_KEY_BASE"] == {"type": "random_urlsafe", "length": 96}
    assert specs["VAULT_ENC_KEY"] == {"type": "random_hex", "length": 32}
    assert specs["LOGFLARE_PUBLIC_ACCESS_TOKEN"] == {"type": "random_urlsafe", "length": 32}
    assert specs["LOGFLARE_PRIVATE_ACCESS_TOKEN"] == {"type": "random_urlsafe", "length": 32}


def test_the_four_are_sourced_from_the_funnel_source_file():
    """They must target env.shared, not a generated tier file.

    Targeting a tier file is what made this unfixable by running env-setup: the
    funnel OWNS the tier files and rewrites them from the CGP bundle, so a value
    written straight into a tier file is deleted on the next funnel run.
    """
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    files = {
        v["key"]: v.get("file")
        for s in data.get("services", [])
        for v in s.get("variables", [])
    }
    shared = "pmoves/env." + "shared"
    for key in (
        "SECRET_KEY_BASE",
        "VAULT_ENC_KEY",
        "LOGFLARE_PUBLIC_ACCESS_TOKEN",
        "LOGFLARE_PRIVATE_ACCESS_TOKEN",
    ):
        assert files[key] == shared, f"{key} must be sourced from the funnel source file"


def test_dry_run_reports_unprovisioned_without_writing(tmp_path, monkeypatch):
    """--ensure-dry-run is the gate: it must never write, and must exit non-zero.

    This is the check that stops the funnel from exiting 0 while a compose
    ``${VAR:?}`` variable is unprovisioned -- the state that blocked every
    service on the node.
    """
    env = _write(tmp_path / "env.shared", "FOO=keep\n")
    monkeypatch.setattr(be, "ENV_SHARED_PATH", env)
    rc = be.main(["--ensure", "SECRET_KEY_BASE", "--ensure-dry-run",
                  "--registry", str(REGISTRY)])
    assert rc == 1
    assert be.read_env_value("SECRET_KEY_BASE", env) is None  # wrote nothing
    assert env.read_text(encoding="utf-8") == "FOO=keep\n"


def test_dry_run_passes_once_provisioned(tmp_path, monkeypatch):
    env = _write(tmp_path / "env.shared", "")
    monkeypatch.setattr(be, "ENV_SHARED_PATH", env)
    be.ensure_secret("SECRET_KEY_BASE", env_path=env, registry_path=str(REGISTRY))
    rc = be.main(["--ensure", "SECRET_KEY_BASE", "--ensure-dry-run",
                  "--registry", str(REGISTRY)])
    assert rc == 0


def test_ensure_is_mutually_exclusive_with_rotate(tmp_path, monkeypatch):
    """Guard against a caller both minting-if-missing and force-rotating."""
    env = _write(tmp_path / "env.shared", "SECRET_KEY_BASE=live\n")
    monkeypatch.setattr(be, "ENV_SHARED_PATH", env)
    rc = be.main(["--ensure", "SECRET_KEY_BASE", "--rotate", "SECRET_KEY_BASE",
                  "--registry", str(REGISTRY)])
    assert rc == 2
    assert be.read_env_value("SECRET_KEY_BASE", env) == "live"


def test_ensure_secret_never_returns_the_minted_value(tmp_path, capsys):
    """The property CodeQL 388/389 asked about, pinned so it stays true.

    `py/clear-text-logging-sensitive-data` flags bootstrap_env.py:89 and :93 --
    the generic `_warn`/`_info` printers -- with the source given as the call
    expression `ensure_secret(key, registry_path=args.registry)`. That is the
    analyzer's name heuristic (a callable matching *secret* is assumed to return
    sensitive data), not an observed dataflow: `main()` tuple-unpacks the result
    into `generated, reason` and prints `reason`, so both elements inherit the
    taint mark.

    It is a false positive only for as long as `reason` stays metadata. Nothing
    in the type signature enforces that, and the obvious future edit -- adding
    the value to the message to help someone debug -- would turn it into a real
    leak silently, because the alert is already dismissed. So assert it:
    `reason` is built from the registry's declared generator type and length,
    the minted value is never interpolated into it, and nothing reaches stdout
    or stderr either.
    """
    env = _write(tmp_path / "env.shared", "SECRET_KEY_BASE=\n")
    generated, reason = be.ensure_secret(
        "SECRET_KEY_BASE", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated is True

    minted = be.read_env_value("SECRET_KEY_BASE", env)
    assert minted  # the mint really happened, so the check below is not vacuous

    # The returned reason carries generator metadata, not the material.
    assert minted not in reason
    assert reason == "generated (random_urlsafe length 96)"

    # And ensure_secret itself emits nothing: main() owns the reporting, so a
    # value cannot escape through a print inside the primitive either.
    captured = capsys.readouterr()
    assert minted not in captured.out
    assert minted not in captured.err


def test_ensure_cli_never_prints_the_minted_value(tmp_path, monkeypatch, capsys):
    """Same property one level up, at the sinks CodeQL actually flagged.

    Drives `main(--ensure ...)` for real over all four blocking keys and asserts
    no minted value appears on stdout or stderr -- covering the `_info` sink
    (line 93), the `_warn` sink (line 89) and the plain prints around them.
    """
    keys = (
        "SECRET_KEY_BASE",
        "VAULT_ENC_KEY",
        "LOGFLARE_PUBLIC_ACCESS_TOKEN",
        "LOGFLARE_PRIVATE_ACCESS_TOKEN",
    )
    env = _write(tmp_path / "env.shared", "")
    monkeypatch.setattr(be, "ENV_SHARED_PATH", env)

    argv = []
    for key in keys:
        argv += ["--ensure", key]
    rc = be.main(argv + ["--registry", str(REGISTRY)])
    assert rc == 0

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    for key in keys:
        minted = be.read_env_value(key, env)
        assert minted, f"{key} was not minted, so this assertion would be vacuous"
        assert minted not in combined, f"{key}'s value reached the log"
        # The name is expected in the log -- that is the whole report.
        assert key in combined
