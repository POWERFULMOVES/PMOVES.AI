"""invidious_keys_preflight + brand_defaults: usable Invidious keys before compose runs.

Compose interpolates every service, profile or not, so once the compose files
declare ``${INVIDIOUS_*_KEY:?}`` a node without the keys loses every stack goal.
The preflight runs in front of those goals and must (a) fix what it safely can,
(b) never make a node worse than compose alone, (c) never print a value.
Fixture keys are INVENTED.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]
REGISTRY = str(PMOVES / "bootstrap" / "registry.json")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


pf = _load("invidious_keys_preflight_under_test", PMOVES / "tools" / "invidious_keys_preflight.py")
bd = _load("brand_defaults_invidious_under_test", PMOVES / "tools" / "brand_defaults.py")
import pmoves.tools._secrets_common as common  # noqa: E402

COMPANION_RE = re.compile(r"[A-Za-z0-9]{16}")
LIVE_COMPANION = "a1b2c3d4e5f60718"
LIVE_HMAC = "f" * 40
PUBLISHED = "0123456789abcdef"


class Probe:
    def __init__(self, containers=None):
        self._c = containers or {}

    def available(self):
        return True

    def container_envs(self):
        return dict(self._c)

    def volumes(self):
        return []


@pytest.fixture(autouse=True)
def _no_shell_exports(monkeypatch):
    for key in pf.KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def published(monkeypatch):
    table = {k: set(v) for k, v in common.KNOWN_PUBLIC_SECRET_DIGESTS.items()}
    table.setdefault(len(PUBLISHED), set()).add(common.known_public_digest(PUBLISHED))
    monkeypatch.setattr(common, "KNOWN_PUBLIC_SECRET_DIGESTS", {k: frozenset(v) for k, v in table.items()})


def _env(tmp_path, text):
    p = tmp_path / ("env." + "shared")
    p.write_text(text, encoding="utf-8")
    return p


def _read(env, key):
    return pf._be.read_env_value(key, env)


def _usable(env):
    values = {k: _read(env, k) for k in pf.KEYS}
    return all(pf.problem(k, values[k], values) is None for k in pf.KEYS)


def test_mints_both_when_absent(tmp_path, capsys):
    env = _env(tmp_path, "OTHER=keep\n")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    assert _usable(env)
    assert COMPANION_RE.fullmatch(_read(env, "INVIDIOUS_COMPANION_KEY"))
    assert _read(env, "OTHER") == "keep"
    out = capsys.readouterr().out
    for k in pf.KEYS:
        assert _read(env, k) not in out


def test_recovers_a_live_private_value_instead_of_minting(tmp_path):
    env = _env(tmp_path, "OTHER=keep\n")
    probe = Probe({"pmoves-invidious-1": {"INVIDIOUS_COMPANION_KEY": LIVE_COMPANION}})
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=probe) == 0
    assert _read(env, "INVIDIOUS_COMPANION_KEY") == LIVE_COMPANION


def test_private_valid_values_are_untouched(tmp_path):
    text = f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n"
    env = _env(tmp_path, text)
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    assert env.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("bad", ["ab-def_123456789", "short", "a" * 64])
def test_vendor_invalid_companion_is_rotated(tmp_path, bad):
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={bad}\n")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    assert COMPANION_RE.fullmatch(_read(env, "INVIDIOUS_COMPANION_KEY"))
    assert _read(env, "INVIDIOUS_HMAC_KEY") == LIVE_HMAC


def test_published_value_is_rotated(tmp_path, published):
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={PUBLISHED}\n")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    assert _read(env, "INVIDIOUS_COMPANION_KEY") != PUBLISHED
    assert _usable(env)


def test_hmac_equal_to_companion_is_rotated(tmp_path):
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_COMPANION}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    assert _read(env, "INVIDIOUS_COMPANION_KEY") == LIVE_COMPANION
    assert _read(env, "INVIDIOUS_HMAC_KEY") != LIVE_COMPANION


def test_absent_env_file_is_not_created(tmp_path):
    """Creating it would stop ensure-env-shared seeding the template."""
    env = tmp_path / ("env." + "shared")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    assert not env.exists()


def test_check_mode_never_writes(tmp_path):
    env = _env(tmp_path, "OTHER=keep\n")
    assert pf.run(env, mode="check", registry=REGISTRY, probe=Probe()) == 1
    assert env.read_text(encoding="utf-8") == "OTHER=keep\n"


def test_empty_shell_export_blocks(tmp_path, monkeypatch):
    """Compose fails ${VAR:?} on an empty export no matter what env files say."""
    monkeypatch.setenv("INVIDIOUS_HMAC_KEY", "")
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 1


def test_non_empty_bad_export_only_warns(tmp_path, monkeypatch, capsys):
    """Compose accepts it; only Invidious is affected, so the stack must not block."""
    monkeypatch.setenv("INVIDIOUS_COMPANION_KEY", "has-dash_1234567")
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    out = capsys.readouterr().out
    assert "WARNING" in out and "has-dash_1234567" not in out


def _goals(text, var):
    return text.split(f"{var} := $(filter ", 1)[1].split(",", 1)[0].split()


def test_makefile_modes_match_what_each_goal_recreates():
    text = (PMOVES / "Makefile").read_text(encoding="utf-8")
    assert "INVIDIOUS_KEYS_FIX_GOALS := $(filter up-invidious,$(MAKECMDGOALS))" in text
    mint = text.split("INVIDIOUS_KEYS_MINT_GOALS := $(filter-out up-invidious,$(filter ", 1)[1].split(",", 1)[0].split()
    gate = _goals(text, "INVIDIOUS_KEYS_GATE_GOALS")
    for goal in ("up", "up-%", "update", "recreate-%", "rebuild-%", "restart-%", "overlay-up-full", "overlay-up-ui"):
        assert goal in mint and goal not in gate
    for goal in ("ps", "ps-%", "logs-%", "down", "down-%", "stop-%", "overlay-down"):
        assert goal in gate and goal not in mint
    for goal in ("secrets-%", "test", "overlay-up-bus", "compose-split-check"):
        assert goal not in mint and goal not in gate
    assert "$(INVIDIOUS_KEYS_FIX_GOALS): invidious-keys-preflight" in text
    assert "$(INVIDIOUS_KEYS_MINT_GOALS): invidious-keys-mint" in text
    assert "$(INVIDIOUS_KEYS_GATE_GOALS): invidious-keys-gate" in text
    recipe = lambda name: text.split(f"\n{name}:", 1)[1].split("\n\n", 1)[0]
    assert "invidious_keys_preflight.py --gate" in recipe("invidious-keys-gate")
    assert "invidious_keys_preflight.py --mint" in recipe("invidious-keys-mint")
    # ensure-env-shared defaults to read-only; only the funnel opts into fix.
    assert "ENSURE_ENV_INVIDIOUS_KEYS ?= gate" in text
    assert recipe("ensure-env-shared").count("--invidious-keys $(ENSURE_ENV_INVIDIOUS_KEYS)") == 3
    codex = (PMOVES / "mk" / "codex.mk").read_text(encoding="utf-8")
    assert "secrets-ensure-generated: ENSURE_ENV_INVIDIOUS_KEYS := fix" in codex


def test_ensure_env_shared_default_is_read_only_and_never_blocks(tmp_path, published):
    """ensure-env-shared is a prerequisite of read-only goals (auth-check,
    a0-model-sync-check, cf-pages-status, pmoves-ai-status): it must neither
    rotate under running containers nor fail over keys those goals never use."""
    import subprocess

    text = "OTHER=keep\nINVIDIOUS_HMAC_KEY=short\nINVIDIOUS_COMPANION_KEY=ab-def_123456789\n"
    for body in (text, "OTHER=keep\n"):  # invalid keys; missing keys
        env = _env(tmp_path, body)
        template = tmp_path / "template.example"
        template.write_text("", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(PMOVES / "tools" / "ensure_env_shared.py"),
             "--env-file", str(env), "--template", str(template)],
            capture_output=True, text=True, env=_hermetic_env(),
        )
        assert r.returncode == 0, r.stdout + r.stderr
        after = env.read_text(encoding="utf-8")
        for key in pf.KEYS:  # brand_defaults may add its own keys; ours are untouched
            assert [l for l in after.splitlines() if l.startswith(key + "=")] == [
                l for l in body.splitlines() if l.startswith(key + "=")
            ]


def test_mint_mode_writes_absent_keys_and_never_rotates(tmp_path, published):
    env = _env(tmp_path, "OTHER=keep\n")
    assert pf.run(env, mode="mint", registry=REGISTRY, probe=Probe()) == 0
    assert _usable(env)
    text = f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={PUBLISHED}\n"
    env = _env(tmp_path, text)
    assert pf.run(env, mode="mint", registry=REGISTRY, probe=Probe()) == 0
    assert env.read_text(encoding="utf-8") == text  # published, but this goal does not recreate Invidious


def test_main_catch_all_is_exit_3_with_a_closed_message(tmp_path, monkeypatch, capsys):
    secret = "a1b2c3d4e5f60718"

    def boom(*a, **k):
        raise RuntimeError("leaks " + secret)

    monkeypatch.setattr(pf, "run", boom)
    assert pf.main(["--env-file", str(tmp_path / "x")]) == 3
    out = capsys.readouterr()
    assert secret not in out.out + out.err and "Traceback" not in out.out + out.err
    assert "COULD-NOT-MEASURE" in out.out


@pytest.mark.parametrize(
    "text",
    [
        "OTHER=keep\n",  # missing -> fatal, still no write
        f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY=ab-def_123456789\n",  # invalid
        f"INVIDIOUS_HMAC_KEY={LIVE_COMPANION}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n",  # reused
        f"INVIDIOUS_HMAC_KEY=short\nINVIDIOUS_COMPANION_KEY={PUBLISHED}\n",  # short + published
    ],
)
def test_gate_mode_leaves_env_byte_identical(tmp_path, published, text):
    """Read-only goals must not rotate under running containers (silent drift)."""
    env = _env(tmp_path, text)
    before = env.read_bytes()
    pf.run(env, mode="gate", registry=REGISTRY, probe=Probe())
    assert env.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(common.TEMP_PREFIX)] == []


def test_gate_mode_through_the_cli_entrypoint_never_writes(tmp_path, published):
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY=short\nINVIDIOUS_COMPANION_KEY={PUBLISHED}\n")
    before = env.read_bytes()
    assert pf.main(["--gate", "--env-file", str(env), "--registry", REGISTRY]) == 0
    assert env.read_bytes() == before


def test_gate_exit_semantics(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, "OTHER=keep\n")
    assert pf.run(env, mode="gate") == 1  # compose will refuse
    monkeypatch.setenv("INVIDIOUS_HMAC_KEY", LIVE_HMAC)
    monkeypatch.setenv("INVIDIOUS_COMPANION_KEY", LIVE_COMPANION)
    assert pf.run(env, mode="gate") == 0  # exports satisfy compose
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY=ab-def_123456789\n")
    monkeypatch.delenv("INVIDIOUS_HMAC_KEY")
    monkeypatch.delenv("INVIDIOUS_COMPANION_KEY")
    assert pf.run(env, mode="gate") == 0  # invalid but present: warn, do not block
    assert "WARNING" in capsys.readouterr().out


def test_exec_exports_keys_without_printing(tmp_path, capfd):
    import subprocess

    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    probe = 'import os,sys; sys.exit(0 if os.environ.get("INVIDIOUS_COMPANION_KEY") == "%s" else 7)' % LIVE_COMPANION
    r = subprocess.run(
        [sys.executable, str(PMOVES / "tools" / "invidious_keys_preflight.py"), "--gate",
         "--env-file", str(env), "--exec", "--", sys.executable, "-c", probe],
        capture_output=True, text=True, env=_hermetic_env(),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert LIVE_COMPANION not in r.stdout + r.stderr and LIVE_HMAC not in r.stdout + r.stderr


def test_exec_stops_before_the_command_when_compose_would_refuse(tmp_path):
    import subprocess

    env = _env(tmp_path, "OTHER=keep\n")
    marker = tmp_path / "ran"
    r = subprocess.run(
        [sys.executable, str(PMOVES / "tools" / "invidious_keys_preflight.py"), "--gate",
         "--env-file", str(env), "--exec", "--", "touch", str(marker)],
        capture_output=True, text=True, env=_hermetic_env(),
    )
    assert r.returncode == 1 and not marker.exists()


def test_fix_and_ensure_env_shared_serialize_under_make_j(tmp_path):
    """Run ensure_env_shared.py (brand_defaults + preflight) and the goal's own
    preflight concurrently, repeatedly. Without the shared lock one rewrite can
    drop the other's: a key line vanishes or appears twice."""
    import subprocess

    for round_ in range(12):  # unlocked control: 4 of 25 rounds corrupt
        d = tmp_path / f"r{round_}"
        d.mkdir()
        env = _env(d, "OTHER=keep\n")
        template = d / "template.example"
        template.write_text("", encoding="utf-8")
        procs = [
            subprocess.Popen(
                [sys.executable, str(PMOVES / "tools" / "ensure_env_shared.py"),
                 "--env-file", str(env), "--template", str(template)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_hermetic_env(),
            )
        ] + [
            subprocess.Popen(
                [sys.executable, str(PMOVES / "tools" / "invidious_keys_preflight.py"), "--env-file", str(env)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_hermetic_env(),
            )
            for _ in range(2)
        ]
        assert [p.wait(timeout=120) for p in procs] == [0, 0, 0]
        text = env.read_text(encoding="utf-8")
        for key in pf.KEYS:
            assert text.count(f"\n{key}=") + text.startswith(f"{key}=") == 1, f"{key} lines != 1 in round {round_}"
        assert "OTHER=keep" in text
        assert _usable(env)


def test_lock_excludes_a_second_holder(tmp_path):
    import subprocess

    env = _env(tmp_path, "OTHER=keep\n")
    code = (
        "import sys, time; sys.path.insert(0, %r)\n"
        "from pmoves.tools._secrets_common import env_write_lock\n"
        "with env_write_lock(%r):\n    print('got', flush=True)\n" % (str(PMOVES.parent), str(env))
    )
    with common.env_write_lock(env):
        child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True,
                                 env={k: v for k, v in __import__("os").environ.items() if k != common.ENV_WRITE_LOCK_HELD})
        with pytest.raises(subprocess.TimeoutExpired):
            child.communicate(timeout=1.5)  # blocked while we hold it
    out, _ = child.communicate(timeout=30)
    assert out.strip() == "got"


# ---------------------------------------------------------------------------
# One owner. brand_defaults used to mint these with token_urlsafe (~40% of
# companion keys carried '-'/'_' and the companion refused to start), and its
# value then satisfied --ensure, so the registry generator never ran.
# ---------------------------------------------------------------------------


def test_preflight_rejects_placeholders_and_short_hmacs(tmp_path):
    env = _env(tmp_path, "INVIDIOUS_HMAC_KEY=localhack\nINVIDIOUS_COMPANION_KEY=your_companion_key_here\n")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    assert _usable(env)
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={'s' * 20}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    assert len(_read(env, "INVIDIOUS_HMAC_KEY")) == 64


def test_brand_defaults_no_longer_owns_the_invidious_keys():
    assert "INVIDIOUS_HMAC_KEY" not in bd.DEFAULTS
    assert "INVIDIOUS_COMPANION_KEY" not in bd.DEFAULTS
    src = (PMOVES / "tools" / "brand_defaults.py").read_text(encoding="utf-8")
    assert '_set_kv(text, "INVIDIOUS_' not in src


TEMPLATE = (
    "OTHER=keep\n"
    # What a node carries today: the 16-char token_urlsafe brand_defaults wrote
    # (with a '-', which the companion rejects) and a 32-char urlsafe HMAC.
    "INVIDIOUS_COMPANION_KEY=ab-def_123456789\n"
    "INVIDIOUS_HMAC_KEY=AbCdEfGhIjKlMnOpQrStUvWxYz012345\n"
)


def _real_ensure_env_shared(tmp_path, text, mode="fix"):
    """Run the REAL ensure-env-shared step: ensure_env_shared.py -> brand_defaults -> preflight.

    mode "fix" is what the funnel's secrets-ensure-generated passes; the default
    for every other caller is "gate" (read-only)."""
    import subprocess

    env = _env(tmp_path, text)
    template = tmp_path / "template.example"
    template.write_text("", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(PMOVES / "tools" / "ensure_env_shared.py"),
         "--env-file", str(env), "--template", str(template), "--invidious-keys", mode],
        capture_output=True, text=True, env=_hermetic_env(),
    )
    return env, r


def _hermetic_env():
    """No INVIDIOUS_* exports, and NO DOCKER.

    The real preflight harvests a live key from any running container. On a
    developer node that would copy a real secret into the test's tmp file (and
    into an assertion message) -- observed once while writing this test. Point
    the docker CLI at a socket that does not exist so the probe sees no holders.
    """
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith(("INVIDIOUS_", "DOCKER_"))}
    env["DOCKER_HOST"] = "unix:///nonexistent/pmoves-test-no-docker.sock"
    return env


def test_funnel_path_repairs_a_dashed_companion_and_keeps_a_valid_hmac(tmp_path):
    """secrets-ensure-generated = ensure-env-shared prerequisite, then harvest + --ensure."""
    env, r = _real_ensure_env_shared(tmp_path, TEMPLATE)
    assert r.returncode == 0, r.stdout + r.stderr
    companion = _read(env, "INVIDIOUS_COMPANION_KEY") or ""
    repaired = bool(COMPANION_RE.fullmatch(companion)) and companion != "ab-def_123456789"
    assert repaired, "dashed companion key was not repaired"
    assert _read(env, "INVIDIOUS_HMAC_KEY") == "AbCdEfGhIjKlMnOpQrStUvWxYz012345"  # valid: kept
    assert "ab-def_123456789" not in r.stdout + r.stderr and companion not in r.stdout + r.stderr
    # The rest of the funnel step: harvest, then --ensure. Both now see a valid slot.
    plan = pf._sh.build_plan(list(pf.KEYS), env_path=env, probe=Probe(), registry_path=REGISTRY)
    assert {d.state for d in plan} == {pf._sh.STATE_SATISFIED}
    for key in pf.KEYS:
        assert pf._be.ensure_secret(key, env_path=env, registry_path=REGISTRY) == (False, "already set")
    assert _usable(env)


def test_funnel_path_mints_registry_format_on_a_virgin_node(tmp_path):
    env, r = _real_ensure_env_shared(tmp_path, "OTHER=keep\n")
    assert r.returncode == 0, r.stdout + r.stderr
    # Booleans only: never let pytest introspect a key into the failure output.
    minted_companion = bool(re.fullmatch(r"[A-Za-z0-9]{16}", _read(env, "INVIDIOUS_COMPANION_KEY") or ""))
    minted_hmac = bool(re.fullmatch(r"[0-9a-f]{64}", _read(env, "INVIDIOUS_HMAC_KEY") or ""))
    assert minted_companion, "companion key is not the registry's random_alnum 16"
    assert minted_hmac, "HMAC key is not the registry's random_hex 64"


def test_funnel_path_rotates_a_published_value(tmp_path, monkeypatch):
    """Published digests are patched in-process only, so drive the preflight directly."""
    table = {k: set(v) for k, v in common.KNOWN_PUBLIC_SECRET_DIGESTS.items()}
    table.setdefault(len(PUBLISHED), set()).add(common.known_public_digest(PUBLISHED))
    monkeypatch.setattr(common, "KNOWN_PUBLIC_SECRET_DIGESTS", {k: frozenset(v) for k, v in table.items()})
    env = _env(tmp_path, f"INVIDIOUS_COMPANION_KEY={PUBLISHED}\nINVIDIOUS_HMAC_KEY={LIVE_HMAC}\n")
    assert pf.run(env, mode="fix", registry=REGISTRY, probe=Probe()) == 0
    assert _read(env, "INVIDIOUS_COMPANION_KEY") != PUBLISHED


# ---------------------------------------------------------------------------
# Atomic env writes (review P2a)
# ---------------------------------------------------------------------------


def test_crash_between_write_and_replace_leaves_original_intact(tmp_path, monkeypatch):
    env = _env(tmp_path, f"OTHER=keep\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    before = env.read_bytes()
    env.chmod(0o640)

    def crash(src, dst):
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(common.os, "replace", crash)
    with pytest.raises(OSError):
        pf._be.rotate_secret("INVIDIOUS_COMPANION_KEY", gen_type="random_hex", length=16, env_path=env)
    assert env.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(common.TEMP_PREFIX)] == []


def test_atomic_write_preserves_mode_and_replaces_whole_file(tmp_path):
    env = _env(tmp_path, "OTHER=keep\n")
    env.chmod(0o640)
    ino = env.stat().st_ino
    pf._be.rotate_secret("INVIDIOUS_COMPANION_KEY", gen_type="random_hex", length=16, env_path=env)
    assert (env.stat().st_mode & 0o777) == 0o640
    assert env.stat().st_ino != ino  # replaced, not truncated in place
    assert _read(env, "OTHER") == "keep"


def test_readers_take_the_lock_shared_and_writers_wait(tmp_path):
    import subprocess

    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    clean = {k: v for k, v in __import__("os").environ.items() if k != common.ENV_WRITE_LOCK_HELD}
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "from pmoves.tools._secrets_common import env_write_lock\n"
        "with env_write_lock(%r, shared=%s):\n    print('got', flush=True)\n"
    )
    with common.env_write_lock(env, shared=True):
        reader = subprocess.run([sys.executable, "-c", code % (str(PMOVES.parent), str(env), True)],
                                capture_output=True, text=True, env=clean, timeout=30)
        assert reader.stdout.strip() == "got"  # a second reader is not blocked
        writer = subprocess.Popen([sys.executable, "-c", code % (str(PMOVES.parent), str(env), False)],
                                  stdout=subprocess.PIPE, text=True, env=clean)
        with pytest.raises(subprocess.TimeoutExpired):
            writer.communicate(timeout=1.5)  # a writer waits for the reader
    out, _ = writer.communicate(timeout=30)
    assert out.strip() == "got"



def test_preflight_keeps_existing_valid_hex_companion_key(tmp_path):
    """Moving the generator to random_alnum must not rotate a working hex key."""
    text = f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY=0123456789abcdee\n"
    env = _env(tmp_path, text)
    for mode in ("fix", "mint", "gate", "check"):
        assert pf.run(env, mode=mode, registry=REGISTRY, probe=Probe()) == 0
        assert env.read_text(encoding="utf-8") == text


# ---------------------------------------------------------------------------
# env.shared file mode (review issuecomment-6551214777)
# ---------------------------------------------------------------------------


def _run_ensure(tmp_path, env, template_text=None, umask=0o022):
    import subprocess

    template = tmp_path / "template.example"
    if template_text is not None:
        template.write_text(template_text, encoding="utf-8")
    args = [sys.executable, str(PMOVES / "tools" / "ensure_env_shared.py"),
            "--env-file", str(env), "--template", str(template)]
    old = __import__("os").umask(umask)
    try:
        return subprocess.run(args, capture_output=True, text=True, env=_hermetic_env())
    finally:
        __import__("os").umask(old)


@pytest.mark.parametrize("template_text", ["OTHER=keep\n", None])
def test_new_env_file_is_created_0600_under_a_permissive_umask(tmp_path, template_text):
    env = tmp_path / ("env." + "shared")
    r = _run_ensure(tmp_path, env, template_text, umask=0o000)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (env.stat().st_mode & 0o777) == 0o600
    if template_text:
        assert "OTHER=keep" in env.read_text(encoding="utf-8")


def test_existing_loose_env_file_is_reported_not_chmodded(tmp_path):
    env = _env(tmp_path, "OTHER=keep\nSOME_TOKEN=do-not-print-me\n")
    env.chmod(0o644)
    r = _run_ensure(tmp_path, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (env.stat().st_mode & 0o777) == 0o644  # never chmod-ed
    assert f"{env} is mode 0644" in r.stdout
    assert "do-not-print-me" not in r.stdout + r.stderr


def test_existing_private_env_file_is_not_reported(tmp_path):
    env = _env(tmp_path, "OTHER=keep\n")
    env.chmod(0o600)
    r = _run_ensure(tmp_path, env)
    assert r.returncode == 0
    assert "readable beyond its owner" not in r.stdout
    assert (env.stat().st_mode & 0o777) == 0o600
