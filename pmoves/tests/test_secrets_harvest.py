"""Tests for tools/secrets_harvest.py — the guard in front of the funnel's mint.

WHY THIS EXISTS
---------------
``make secrets-funnel`` calls ``secrets-ensure-generated`` unconditionally, and
that step mints every key in ``SECRETS_ENSURE_KEYS`` whose env.shared slot is
absent or empty. On a node in the recovery state this PR describes -- env.shared
has lost the value but a RUNNING container still holds it -- the mint is not a
bootstrap. It is a silent replacement of live cryptographic material, and
``secrets-funnel-sync`` materializes it into the tier files on the very next
line. A later pooler recreation then receives a different ``VAULT_ENC_KEY`` and
can no longer decrypt existing tenant credentials, nor the yt OAuth cookies the
same key protects. Documentation cannot guard a step that fires automatically.

The classifier answers ONE question, and it is not "is this node new?" --
it is "does any running container or persisted volume hold state encrypted
under the old value?". Three answers, three behaviours:

  STATE 1  no holder, no state volume      -> MINT (correct, not degraded)
  STATE 2  a running container holds it    -> HARVEST (never mint over it)
  STATE 3  no holder, state volume present -> REFUSE (harvest impossible AND
                                               minting destructive)

State 3 must fail CLOSED. A mint that destroys tenant credentials is the worst
outcome available here, so an unnecessary refusal is strictly preferable to an
unnecessary mint.

No test in this file executes docker. Every probe is a fake.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[1] / "tools" / "secrets_harvest.py"
_spec = importlib.util.spec_from_file_location("secrets_harvest_under_test", _MOD_PATH)
sh = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = sh
_spec.loader.exec_module(sh)

REGISTRY = Path(__file__).resolve().parents[1] / "bootstrap" / "registry.json"

# Values below are TEST FIXTURES invented for these tests. They are not, and must
# never be, real material: the tool's contract is that it never prints a value,
# so a test that needed a real one would be testing the wrong thing.
FAKE_HEX32 = "0123456789abcdef0123456789abcdef"
FAKE_HEX32_OTHER = "fedcba9876543210fedcba9876543210"
FAKE_URLSAFE64 = "A" * 64


class FakeProbe:
    """Stands in for the host-side docker probe.

    Mirrors the real probe's interface exactly: container envs are a mapping of
    container name -> {KEY: VALUE}, volumes are bare names. Nothing execs into a
    container; the real probe reads ``docker inspect`` on the host, same as this
    returns canned data.
    """

    def __init__(self, containers=None, volumes=(), available=True):
        self._containers = dict(containers or {})
        self._volumes = list(volumes)
        self._available = available

    def available(self) -> bool:
        return self._available

    def container_envs(self):
        return dict(self._containers)

    def volumes(self):
        return list(self._volumes)


def _env(tmp_path, text="OTHER=keep\n") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "env.shared"
    p.write_text(text, encoding="utf-8")
    return p


def _plan(env, probe, keys=("VAULT_ENC_KEY",), **kw):
    return sh.build_plan(
        list(keys), env_path=env, probe=probe, registry_path=str(REGISTRY), **kw
    )


def _for(plan, key):
    return next(d for d in plan if d.key == key)


# ---------------------------------------------------------------------------
# STATE 1 — virgin node. Must still bootstrap, unchanged.
# ---------------------------------------------------------------------------


def test_state1_no_holder_no_volume_defers_to_mint(tmp_path):
    env = _env(tmp_path)
    plan = _plan(env, FakeProbe(containers={}, volumes=["portainer_data"]))
    d = _for(plan, "VAULT_ENC_KEY")
    assert d.state == sh.STATE_MINT
    assert d.action == "mint"
    # The guard writes NOTHING in state 1 — bootstrap_env --ensure does the mint,
    # so the existing minting path stays the only minting path.
    assert sh.apply_plan(plan, env_path=env) == []
    assert sh.read_env_value("VAULT_ENC_KEY", env) is None


def test_state1_docker_absent_entirely_defers_to_mint(tmp_path):
    """No docker at all (CI, a fresh laptop) is state 1, not an error."""
    env = _env(tmp_path)
    plan = _plan(env, FakeProbe(available=False))
    assert _for(plan, "VAULT_ENC_KEY").state == sh.STATE_MINT


def test_state1_unrelated_volumes_do_not_trigger_refusal(tmp_path):
    """Only volumes that actually hold state keyed by the secret count."""
    env = _env(tmp_path)
    probe = FakeProbe(
        volumes=["pmoves_qdrant-data", "pmoves_n8n-data", "monitoring_loki-data"]
    )
    assert _for(_plan(env, probe), "VAULT_ENC_KEY").state == sh.STATE_MINT


# ---------------------------------------------------------------------------
# STATE 2 — a running container holds it. Harvest, never mint.
# ---------------------------------------------------------------------------


def test_state2_harvests_the_live_value_byte_for_byte(tmp_path):
    env = _env(tmp_path)
    probe = FakeProbe(
        containers={"pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": FAKE_HEX32}},
        volumes=["pmoves_supabase-db-data"],
    )
    plan = _plan(env, probe)
    d = _for(plan, "VAULT_ENC_KEY")
    assert d.state == sh.STATE_HARVEST
    assert d.action == "harvest"
    assert d.holders == ("pmoves-supabase-pooler-1",)

    assert sh.apply_plan(plan, env_path=env) == ["VAULT_ENC_KEY"]
    assert sh.read_env_value("VAULT_ENC_KEY", env) == FAKE_HEX32
    assert sh.read_env_value("OTHER", env) == "keep"


def test_state2_beats_a_present_state_volume(tmp_path):
    """A holder outranks the volume signal: harvest is possible, so harvest."""
    env = _env(tmp_path)
    probe = FakeProbe(
        containers={"pmoves-supabase-analytics-1": {"VAULT_ENC_KEY": FAKE_HEX32}},
        volumes=["pmoves_supabase-db-data"],
    )
    assert _for(_plan(env, probe), "VAULT_ENC_KEY").state == sh.STATE_HARVEST


def test_state2_unanimous_across_many_holders_is_still_a_harvest(tmp_path):
    env = _env(tmp_path)
    probe = FakeProbe(
        containers={
            "pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": FAKE_HEX32},
            "pmoves-supabase-analytics-1": {"VAULT_ENC_KEY": FAKE_HEX32},
            "pmoves-yt-cookie-writer-1": {"VAULT_ENC_KEY": FAKE_HEX32},
        }
    )
    d = _for(_plan(env, probe), "VAULT_ENC_KEY")
    assert d.state == sh.STATE_HARVEST
    assert len(d.holders) == 3


def test_state2_disagreement_refuses_rather_than_guessing(tmp_path):
    """Two live values means we cannot know which one the volumes are keyed to."""
    env = _env(tmp_path)
    probe = FakeProbe(
        containers={
            "pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": FAKE_HEX32},
            "pmoves-supabase-analytics-1": {"VAULT_ENC_KEY": FAKE_HEX32_OTHER},
        }
    )
    d = _for(_plan(env, probe), "VAULT_ENC_KEY")
    assert d.state == sh.STATE_REFUSE
    assert "disagree" in d.reason.lower()
    assert "pmoves-supabase-pooler-1" in d.detail
    assert "pmoves-supabase-analytics-1" in d.detail


def test_state2_placeholder_holder_is_not_a_holder(tmp_path):
    """A container carrying `changeme` holds nothing worth preserving."""
    env = _env(tmp_path)
    probe = FakeProbe(
        containers={"pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": "changeme"}}
    )
    assert _for(_plan(env, probe), "VAULT_ENC_KEY").state == sh.STATE_MINT


def test_state2_harvest_is_idempotent(tmp_path):
    """Second pass sees the slot filled and does nothing at all."""
    env = _env(tmp_path)
    probe = FakeProbe(
        containers={"pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": FAKE_HEX32}}
    )
    sh.apply_plan(_plan(env, probe), env_path=env)
    before = env.read_text(encoding="utf-8")

    plan2 = _plan(env, probe)
    assert _for(plan2, "VAULT_ENC_KEY").state == sh.STATE_SATISFIED
    assert sh.apply_plan(plan2, env_path=env) == []
    assert env.read_text(encoding="utf-8") == before


def test_state2_shape_mismatch_still_harvests_but_warns(tmp_path):
    """A live value that fails its registry spec is still the fleet's value.

    Refusing on shape would brick recovery on exactly the node that needs it
    (the 4090's urlsafe-instead-of-hex VAULT_ENC_KEY). Desync is the greater
    hazard than a malformed-but-agreed value, so harvest and say so.
    """
    env = _env(tmp_path)
    probe = FakeProbe(
        containers={"pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": "not-hex-" * 5}}
    )
    d = _for(_plan(env, probe), "VAULT_ENC_KEY")
    assert d.state == sh.STATE_HARVEST
    assert d.shape_ok is False
    assert "registry" in (d.warning or "").lower()


# ---------------------------------------------------------------------------
# STATE 3 — the dangerous middle. Harvest impossible AND minting destructive.
# ---------------------------------------------------------------------------


def test_state3_volume_without_holder_refuses(tmp_path):
    env = _env(tmp_path)
    probe = FakeProbe(containers={}, volumes=["pmoves_supabase-db-data"])
    d = _for(_plan(env, probe), "VAULT_ENC_KEY")
    assert d.state == sh.STATE_REFUSE
    assert d.action == "refuse"


def test_state3_message_names_the_volume_and_the_key(tmp_path):
    """An operator must be able to act on the refusal without reading the source."""
    env = _env(tmp_path)
    probe = FakeProbe(containers={}, volumes=["pmoves_supabase-db-data"])
    d = _for(_plan(env, probe), "VAULT_ENC_KEY")
    assert "VAULT_ENC_KEY" in d.detail
    assert "pmoves_supabase-db-data" in d.detail
    # and it must say what to DO, not merely that it stopped
    assert "SECRETS_HARVEST_ACK_DESTRUCTIVE" in d.detail


def test_state3_writes_nothing_at_all(tmp_path):
    env = _env(tmp_path)
    before = env.read_text(encoding="utf-8")
    probe = FakeProbe(containers={}, volumes=["pmoves_supabase-db-data"])
    plan = _plan(env, probe)
    assert sh.apply_plan(plan, env_path=env) == []
    assert env.read_text(encoding="utf-8") == before


def test_state3_refusal_is_not_partial(tmp_path):
    """One refusal aborts the whole batch — no key is written.

    A partial apply is the sequencing trap in miniature: some keys correct, some
    minted, and `compose config` green over the top of the damage.
    """
    env = _env(tmp_path)
    probe = FakeProbe(
        containers={"pmoves-supabase-pooler-1": {"SECRET_KEY_BASE": FAKE_URLSAFE64}},
        volumes=["pmoves_supabase-db-data"],
    )
    plan = _plan(env, probe, keys=("SECRET_KEY_BASE", "VAULT_ENC_KEY"))
    assert _for(plan, "SECRET_KEY_BASE").state == sh.STATE_HARVEST
    assert _for(plan, "VAULT_ENC_KEY").state == sh.STATE_REFUSE

    written = sh.apply_plan(plan, env_path=env)
    assert written == []
    assert sh.read_env_value("SECRET_KEY_BASE", env) is None


def test_state3_ack_is_per_key_not_a_blanket_switch(tmp_path):
    """The escape hatch must name the key, because a blanket `=1` gets pasted."""
    env = _env(tmp_path)
    probe = FakeProbe(containers={}, volumes=["pmoves_supabase-db-data"])

    acked = _plan(
        env,
        probe,
        keys=("SECRET_KEY_BASE", "VAULT_ENC_KEY"),
        ack_destructive={"VAULT_ENC_KEY"},
    )
    assert _for(acked, "VAULT_ENC_KEY").state == sh.STATE_MINT
    assert _for(acked, "SECRET_KEY_BASE").state == sh.STATE_REFUSE

    assert sh.parse_ack("1") == set()
    assert sh.parse_ack("true") == set()
    assert sh.parse_ack("VAULT_ENC_KEY,SECRET_KEY_BASE") == {
        "VAULT_ENC_KEY",
        "SECRET_KEY_BASE",
    }


# ---------------------------------------------------------------------------
# Already-satisfied — the guard must agree with ensure_secret's own predicate.
# ---------------------------------------------------------------------------


def test_a_set_slot_is_never_touched_even_when_it_disagrees_with_the_fleet(tmp_path):
    """The guard fills empty slots. It is not a reconciler and must not rotate."""
    env = _env(tmp_path, "VAULT_ENC_KEY=%s\n" % FAKE_HEX32_OTHER)
    probe = FakeProbe(
        containers={"pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": FAKE_HEX32}}
    )
    plan = _plan(env, probe)
    assert _for(plan, "VAULT_ENC_KEY").state == sh.STATE_SATISFIED
    assert sh.apply_plan(plan, env_path=env) == []
    assert sh.read_env_value("VAULT_ENC_KEY", env) == FAKE_HEX32_OTHER


def test_empty_slot_is_unsatisfied_matching_ensure_secret(tmp_path):
    """`KEY=` is what ensure_secret treats as absent; the guard must agree, or a
    slot exists that the guard skips and the mint then fills."""
    env = _env(tmp_path, "VAULT_ENC_KEY=\n")
    probe = FakeProbe(
        containers={"pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": FAKE_HEX32}}
    )
    assert _for(_plan(env, probe), "VAULT_ENC_KEY").state == sh.STATE_HARVEST


# ---------------------------------------------------------------------------
# Exit codes and the no-value-anywhere contract.
# ---------------------------------------------------------------------------


def test_main_exit_codes(tmp_path, monkeypatch):
    env = _env(tmp_path / "a")

    monkeypatch.setattr(sh, "DockerProbe", lambda: FakeProbe(volumes=[]))
    assert sh.main(["--key", "VAULT_ENC_KEY", "--env-file", str(env)]) == 0
    assert sh.read_env_value("VAULT_ENC_KEY", env) is None

    monkeypatch.setattr(
        sh,
        "DockerProbe",
        lambda: FakeProbe(
            containers={"pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": FAKE_HEX32}}
        ),
    )
    assert sh.main(["--key", "VAULT_ENC_KEY", "--env-file", str(env)]) == 0
    assert sh.read_env_value("VAULT_ENC_KEY", env) == FAKE_HEX32

    env2 = _env(tmp_path / "b")
    monkeypatch.setattr(
        sh, "DockerProbe", lambda: FakeProbe(volumes=["pmoves_supabase-db-data"])
    )
    assert sh.main(["--key", "VAULT_ENC_KEY", "--env-file", str(env2)]) == 3


def test_no_output_path_ever_renders_a_value(tmp_path, monkeypatch, capsys):
    """The whole point of harvesting host-side is that the value stays unseen.

    A tool that prints `VAULT_ENC_KEY=<live>` into a make log has moved the
    secret from a container's environment into everyone's scrollback.
    """
    env = _env(tmp_path)
    monkeypatch.setattr(
        sh,
        "DockerProbe",
        lambda: FakeProbe(
            containers={
                "pmoves-supabase-pooler-1": {
                    "VAULT_ENC_KEY": FAKE_HEX32,
                    "SECRET_KEY_BASE": FAKE_URLSAFE64,
                }
            }
        ),
    )
    rc = sh.main(
        ["--key", "VAULT_ENC_KEY", "--key", "SECRET_KEY_BASE", "--env-file", str(env)]
    )
    assert rc == 0
    out = capsys.readouterr()
    blob = out.out + out.err
    assert FAKE_HEX32 not in blob
    assert FAKE_URLSAFE64 not in blob
    # not even a masked prefix — runtime_secrets_hydrate's `abcd...wxyz` style
    # leaks 8 characters into the same log.
    assert FAKE_HEX32[:4] not in blob
    assert "VAULT_ENC_KEY" in blob  # the NAME is the whole report


def test_refusal_message_carries_no_value(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path)
    monkeypatch.setattr(
        sh,
        "DockerProbe",
        lambda: FakeProbe(
            containers={
                "pmoves-supabase-pooler-1": {"VAULT_ENC_KEY": FAKE_HEX32},
                "pmoves-supabase-analytics-1": {"VAULT_ENC_KEY": FAKE_HEX32_OTHER},
            }
        ),
    )
    assert sh.main(["--key", "VAULT_ENC_KEY", "--env-file", str(env)]) == 3
    out = capsys.readouterr()
    blob = out.out + out.err
    assert FAKE_HEX32 not in blob
    assert FAKE_HEX32_OTHER not in blob
    assert "pmoves-supabase-pooler-1" in blob
    assert "pmoves-supabase-analytics-1" in blob


def test_unknown_key_has_no_spec_and_is_left_to_mint(tmp_path):
    """A key with no declared holders/volumes cannot be classified as state 3.

    Inventing a refusal for a key we know nothing about would block the funnel
    on every node for no measured reason.
    """
    env = _env(tmp_path)
    probe = FakeProbe(volumes=["pmoves_supabase-db-data"])
    d = _for(_plan(env, probe, keys=("SOME_UNRELATED_KEY",)), "SOME_UNRELATED_KEY")
    assert d.state == sh.STATE_MINT


# ---------------------------------------------------------------------------
# Wiring — a guard that is not in front of the mint is not a guard.
# ---------------------------------------------------------------------------

MK = Path(__file__).resolve().parents[1] / "mk" / "codex.mk"


def _ensure_generated_recipe() -> str:
    """The recipe body of secrets-ensure-generated, comments stripped."""
    lines = MK.read_text(encoding="utf-8").split("\n")
    start = next(
        i for i, l in enumerate(lines) if l.startswith("secrets-ensure-generated:")
    )
    body = []
    for line in lines[start + 1 :]:
        if line and not line.startswith("\t"):
            break
        if line.startswith("\t@#"):
            continue
        body.append(line)
    return "\n".join(body)


def test_the_guard_runs_before_the_mint():
    recipe = _ensure_generated_recipe()
    guard = recipe.index("tools/secrets_harvest.py")
    mint = recipe.index("scripts/bootstrap_env.py")
    assert guard < mint, "the harvest guard must precede the mint, not follow it"


def test_a_refusal_stops_the_funnel_rather_than_warning():
    """`&&`, not `;`. With `;` the mint runs anyway and the refusal is noise."""
    recipe = _ensure_generated_recipe()
    between = recipe[
        recipe.index("tools/secrets_harvest.py") : recipe.index(
            "scripts/bootstrap_env.py"
        )
    ]
    assert "&&" in between
    assert ";" not in between.split("&&")[0]


def test_the_guard_examines_exactly_the_keys_the_mint_would_write():
    """A key in SECRETS_ENSURE_KEYS but not passed to the guard is unguarded."""
    recipe = _ensure_generated_recipe()
    assert recipe.count("$(foreach k,$(SECRETS_ENSURE_KEYS),--key $(k))") == 1
    assert recipe.count("$(foreach k,$(SECRETS_ENSURE_KEYS),--ensure $(k))") == 1


def test_empty_key_list_still_mints_nothing():
    """The pre-existing EOFError guard must survive the rewiring."""
    recipe = _ensure_generated_recipe()
    assert 'if [ -z "$(strip $(SECRETS_ENSURE_KEYS))" ]' in recipe
