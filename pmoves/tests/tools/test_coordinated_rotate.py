"""coordinated_rotate: discovery, preflight refusals, plan order, and the
execute -> verify -> AUTO-ROLLBACK path, driven against STUB docker/compose/make.

Nothing here touches the live stack. The stubs are tiny python scripts written
into tmp_path with their state file path baked in, because the tool runs every
subprocess in a CLEAN env (so a stub cannot be steered by environment variables
either -- the same property that protects the real run from a polluted shell).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import coordinated_rotate as cr  # noqa: E402

# The fixture password is a COMMON WORD that also appears in unrelated values
# (network names, a database name) -- the real leaked NATS default has that shape,
# and a substring matcher links half the stack to it.
OLD = "stack"
LIVE_JWT = "live-jwt-secret-0123456789abcdef0123456789"
DEAD_JWT = "dead-jwt-secret-fedcba9876543210fedcba9876"


def mint(secret: str, role: str) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    head, body = enc({"alg": "HS256", "typ": "JWT"}), enc({"role": role, "iss": "test"})
    sig = hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
    return f"{head}.{body}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"


GOOD_SERVICE = mint(LIVE_JWT, "service_role")
DEAD_SERVICE = mint(DEAD_JWT, "service_role")


def stack_template(service_key: str = GOOD_SERVICE) -> dict:
    """{P} is replaced by the CURRENT secret by the stub compose (and the tests)."""
    common = {"NATS_PASSWORD": "{P}", "NATS_URL": "nats://nats:{P}@nats:4222",
              "PMOVES_NETWORKS": "stack_app,stack_bus", "SUPABASE_JWT_SECRET": LIVE_JWT,
              "SUPABASE_SERVICE_ROLE_KEY": service_key}
    rendered = {
        "nats": {"image": "nats:2.11.8-alpine", "command": ["-js", "--user", "nats", "--pass", "{P}"],
                 "environment": dict(common)},
        "bus-client": {"image": "bus-client:1", "depends_on": {"nats": {}, "dep-client": {}},
                       "environment": dict(common)},
        "dep-client": {"image": "dep-client:1", "environment": {**common, "P7_NATS_URL": "nats://nats:{P}@nats:4222"}},
        "agent-zero": {"image": "a0:1", "environment": dict(common)},
        "archon": {"image": "archon:1", "environment": dict(common)},
        "inheritor": {"image": "inheritor:1", "environment": {**common, "POSTGRES_DB": "stack"}},
        "json-holder": {"image": "jh:1", "environment": {
            "A0_SET_mcp_servers": '{"nats":{"url":"nats://nats:{P}@nats:4222"}}', "SUPABASE_JWT_SECRET": LIVE_JWT}},
        "unrelated": {"image": "u:1", "environment": {"POSTGRES_DB": "stack", "PMOVES_NETWORKS": "stack_app"}},
        "supabase-gotrue": {"image": "gotrue:1", "environment": {"GOTRUE_JWT_SECRET": LIVE_JWT}},
    }
    noint = {name: {"image": spec["image"], "environment": {}} for name, spec in rendered.items()}
    noint["nats"]["command"] = ["-js", "--user", "${NATS_USER:-nats}", "--pass", "${NATS_PASSWORD:-x}"]
    noint["bus-client"]["environment"] = {"NATS_URL": "${NATS_URL}"}
    noint["dep-client"]["environment"] = {"P7_NATS_URL": "nats://${NATS_USER}:${NATS_PASSWORD}@nats:4222"}
    noint["archon"]["environment"] = {"NATS_URL": "${NATS_URL}"}
    noint["bus-client"]["image"] = "${BUS_IMAGE:-bus-client:1}"
    return {"rendered": rendered, "noint": noint}


STUB_COMPOSE = r'''#!{py}
import json, sys
state = json.load(open({state!r}))
tpl = state["template"]["noint" if "--no-interpolate" in sys.argv else "rendered"]
text = json.dumps(tpl).replace("{{P}}", state["secret"])
for k, v in state.get("gate_extra", {{}}).items():
    if state.get("residue") or state["secret"] != state["original"]:
        text = text.replace(k, v)
print(json.dumps({{"services": json.loads(text)}}))
'''

STUB_DOCKER = r'''#!{py}
import json, sys
state = json.load(open({state!r}))
a = sys.argv[1:]
if a[0] == "ps":
    for (proj, svc), c in ((tuple(k.split("/")), v) for k, v in state["containers"].items()):
        print(f"{{c['id']}}|{{proj}}|{{svc}}")
elif a[0] == "inspect":
    for c in state["containers"].values():
        if c["id"] == a[1]:
            st = {{"Running": True}}
            if c["health"] != "none":
                st["Health"] = {{"Status": c["health"]}}
            print(json.dumps([{{"Config": {{"Env": c["env"]}}, "State": st, "NetworkSettings": {{"Networks": {{}}}}}}]))
            sys.exit(0)
    sys.exit(1)
elif a[:2] == ["image", "inspect"]:
    sys.exit(0 if a[2] in state["images_present"] else 1)
elif a[:2] == ["manifest", "inspect"]:
    sys.exit(0 if a[2] in state.get("images_pullable", []) else 1)
'''

STUB_MAKE = r'''#!{py}
import json, os, sys, hashlib
path = {state!r}
state = json.load(open(path))
args = [x for x in sys.argv[1:] if x not in ("-C", "--no-print-directory") and not x.startswith("/")]
val = os.environ.get("PMOVES_ROTATE_VALUE", "")
state["calls"].append({{"argv": args, "value_class": hashlib.sha256(val.encode()).hexdigest()[:4] if val else ""}})
if args[0] == "secrets-rotate":
    name = args[1].split("=", 1)[1]
    if name == "NATS_PASSWORD":
        state["secret"] = val
    if state.get("residue_on_rotate"):
        state["residue"] = True  # the funnel dropped something that restoring the value will not bring back
    if state.get("fail_rotate_on") == name:
        json.dump(state, open(path, "w")); sys.exit(2)
targets = []
if args[0] == "recreate-svc":
    targets = [args[1].split("=", 1)[1]]
elif args[0] == "up-a0-archon-scoped":
    targets = args[1].split("=", 1)[1].split()
for svc in targets:
    c = state["containers"]["pmoves/" + svc]
    state["n"] += 1
    c["id"] = f"new{{state['n']}}"
    bad = state.get("break_on_new_secret") and state["secret"] != state["original"]
    c["health"] = "unhealthy" if (bad and svc in state["break_on_new_secret"]) else "healthy"
    c["env"] = [e for e in c["env"] if not e.startswith("NATS")] + [f"NATS_PASSWORD={{state['secret']}}"]
json.dump(state, open(path, "w"))
'''


class Harness:
    def __init__(self, tmp: Path, *, template=None, running=None, images=None, drift=None, health=None):
        self.tmp = tmp
        self.state_path = tmp / "state.json"
        template = template or stack_template()
        running = running or ["nats", "bus-client", "dep-client", "agent-zero", "archon", "inheritor",
                              "json-holder", "unrelated", "supabase-gotrue"]
        rendered = json.loads(json.dumps(template["rendered"]).replace("{P}", OLD))
        containers = {}
        for i, svc in enumerate(running):
            env = [f"{k}={v}" for k, v in rendered[svc]["environment"].items()]
            for k, v in (drift or {}).get(svc, {}).items():
                env = [e for e in env if not e.startswith(k + "=")] + [f"{k}={v}"]
            containers[f"pmoves/{svc}"] = {"id": f"old{i}", "env": env, "health": (health or {}).get(svc, "healthy")}
        state = {"template": template, "secret": OLD, "original": OLD, "containers": containers, "calls": [],
                 "n": 0, "images_present": images if images is not None else
                 [s["image"] for s in template["rendered"].values()]}
        self.write(state)
        for name, src in (("fakecompose", STUB_COMPOSE), ("fakedocker", STUB_DOCKER), ("fakemake", STUB_MAKE)):
            p = tmp / name
            p.write_text(src.format(py=sys.executable, state=str(self.state_path)))
            p.chmod(0o755)
        (tmp / "manifest.yaml").write_text(textwrap.dedent("""\
            entries:
              - source: {type: cgp, label: NATS_PASSWORD}
              - source: {type: cgp, label: NATS_URL}
        """))
        (tmp / "roads.yaml").write_text(textwrap.dedent("""\
            roads:
              default: {main: "recreate-svc SVC={service}"}
              overrides:
                - {stack: main, services: [agent-zero, archon], target: 'up-a0-archon-scoped SERVICES="{services}"'}
            probes: {}
        """))

    def write(self, state):
        self.state_path.write_text(json.dumps(state))

    def state(self):
        return json.loads(self.state_path.read_text())

    def mutate(self, fn):
        s = self.state()
        fn(s)
        self.write(s)

    def run(self, *extra, execute=False):
        argv = ["--key", "NATS_PASSWORD", "--stack", f"main={self.tmp / 'fakecompose'} -p pmoves",
                "--docker", str(self.tmp / "fakedocker"), "--make", str(self.tmp / "fakemake"),
                "--config", str(self.tmp / "roads.yaml"), "--manifest", str(self.tmp / "manifest.yaml"),
                "--state-dir", str(self.tmp / "rotstate"), "--node", "testnode", "--root", str(self.tmp),
                "--verify-timeout", "0", "--poll", "0", "--json", str(self.tmp / "verdict.json"), *extra]
        if execute:
            argv += ["--execute", "--confirm", "ROTATE NATS_PASSWORD @ testnode"]
        code = cr.main(argv)
        return code, json.loads((self.tmp / "verdict.json").read_text())


ACK = ["--ack-drift", "inheritor,unrelated"]


# ----------------------------------------------------------------- discovery
def test_discovery_finds_url_embedded_creds_and_derives_roles(tmp_path, capsys):
    h = Harness(tmp_path)
    code, v = h.run(*ACK)
    d = v["discovery"]
    assert d["rotate_labels"] == ["NATS_PASSWORD", "NATS_URL"], "NATS_URL carries the secret in userinfo"
    assert d["derived_keys"] == ["A0_SET_mcp_servers", "P7_NATS_URL"], "URL-embedded, incl. inside JSON"
    roles = d["consumers"]
    assert "server" in roles["main/nats"]
    assert "declared" in roles["main/bus-client"]
    assert "declared" in roles["main/dep-client"], "P7_NATS_URL built from ${NATS_PASSWORD}"
    assert roles["main/inheritor"] == ["carrier"]
    assert roles["main/json-holder"] == ["carrier"]


def test_common_word_secret_does_not_link_unrelated_values(tmp_path):
    """Production change that makes this fail: going back to substring matching.
    The secret 'stack' is inside PMOVES_NETWORKS and equals POSTGRES_DB."""
    h = Harness(tmp_path)
    _, v = h.run(*ACK)
    assert "PMOVES_NETWORKS" not in v["discovery"]["derived_keys"]
    assert "main/unrelated" not in v["discovery"]["consumers"]


def test_replace_secret_touches_only_userinfo():
    assert cr.replace_secret("nats://nats:stack@stack-host:4222/stack", "stack", "N3w") == \
        "nats://nats:N3w@stack-host:4222/stack"
    assert cr.replace_secret("stack", "stack", "N3w") == "N3w"
    assert cr.replace_secret("stack_app", "stack", "N3w") == "stack_app"


# ----------------------------------------------------------------- plan
def test_dry_run_plans_server_first_dependency_order_and_batches_roads(tmp_path):
    h = Harness(tmp_path)
    code, v = h.run(*ACK)
    assert code == cr.EXIT_OK, v.get("refusals")
    targets = [" ".join(p["target"]) for p in v["plan"]]
    assert targets[0] == "recreate-svc SVC=nats"
    assert targets.index("recreate-svc SVC=dep-client") < targets.index("recreate-svc SVC=bus-client")
    assert "up-a0-archon-scoped SERVICES=agent-zero archon" not in targets  # agent-zero is only a carrier
    assert "up-a0-archon-scoped SERVICES=archon" in targets
    assert not any("inheritor" in t or "json-holder" in t for t in targets), "carriers are not recreated"
    assert h.state()["calls"] == [], "dry-run must not invoke make at all"


def test_include_opts_a_carrier_into_the_set(tmp_path):
    h = Harness(tmp_path)
    _, v = h.run(*ACK, "--include", "agent-zero")
    assert "up-a0-archon-scoped SERVICES=agent-zero archon" in [" ".join(p["target"]) for p in v["plan"]]


# ----------------------------------------------------------------- preflight refusals
def test_refuses_on_unacknowledged_non_target_drift(tmp_path):
    h = Harness(tmp_path, drift={"bus-client": {"OPENAI_API_KEY": "old"}})
    h.mutate(lambda s: s["template"]["rendered"]["bus-client"]["environment"].update(OPENAI_API_KEY="new"))
    code, v = h.run(*ACK)
    assert code == cr.EXIT_FINDINGS
    assert any(c == "drift" and "bus-client" in d and "OPENAI_API_KEY" in d for c, d in v["refusals"])
    code, _ = h.run("--ack-drift", "inheritor,unrelated,bus-client")
    assert code == cr.EXIT_OK


def test_target_keys_are_not_drift(tmp_path):
    """NATS_URL differing only in the secret is the rotation itself, not drift."""
    h = Harness(tmp_path)
    code, v = h.run(*ACK)
    assert not [d for c, d in v["refusals"] if c == "drift"]


def test_refuses_absent_unpullable_image_and_names_the_pin_var(tmp_path):
    h = Harness(tmp_path, images=["nats:2.11.8-alpine", "dep-client:1", "archon:1", "gotrue:1"])
    code, v = h.run(*ACK)
    assert code == cr.EXIT_FINDINGS
    msg = [d for c, d in v["refusals"] if c == "image" and "bus-client" in d][0]
    assert "BUS_IMAGE" in msg
    code, v = h.run(*ACK, "--pin", "bus-client=dep-client:1")
    assert not [d for c, d in v["refusals"] if c == "image" and "bus-client" in d]


def test_refuses_supabase_key_the_running_stack_cannot_verify(tmp_path):
    h = Harness(tmp_path, template=stack_template(service_key=DEAD_SERVICE))
    code, v = h.run(*ACK)
    assert code == cr.EXIT_FINDINGS
    sb = [d for c, d in v["refusals"] if c == "supabase"]
    assert sb and all("supabase-key-reconcile" in d for d in sb)
    assert LIVE_JWT not in json.dumps(v) and DEAD_SERVICE not in json.dumps(v), "never print a value"


def test_refuses_wrong_confirm_and_never_mints(tmp_path):
    h = Harness(tmp_path)
    code = cr.main(["--key", "NATS_PASSWORD", "--stack", f"main={tmp_path / 'fakecompose'} -p pmoves",
                    "--docker", str(tmp_path / "fakedocker"), "--make", str(tmp_path / "fakemake"),
                    "--config", str(tmp_path / "roads.yaml"), "--manifest", str(tmp_path / "manifest.yaml"),
                    "--node", "testnode", "--root", str(tmp_path), *ACK, "--execute", "--confirm", "yes"])
    assert code == cr.EXIT_FINDINGS
    assert h.state()["calls"] == []


# ----------------------------------------------------------------- execute / rollback
def _calls(h):
    return [(" ".join(c["argv"]), c["value_class"]) for c in h.state()["calls"]]


def test_execute_rotates_recreates_in_order_and_records(tmp_path, capsys):
    h = Harness(tmp_path)
    code, v = h.run(*ACK, execute=True)
    assert code == cr.EXIT_OK, v.get("log")
    calls = _calls(h)
    assert [c for c, _ in calls[:2]] == ["secrets-rotate KEY=NATS_PASSWORD", "secrets-rotate KEY=NATS_URL"]
    recreates = [c for c, _ in calls if not c.startswith(("secrets-rotate", "register-note", "sign-trail"))]
    assert recreates[0] == "recreate-svc SVC=nats"
    assert calls[-2][0].startswith("register-note") and calls[-1][0] == "sign-trail"
    new = h.state()["secret"]
    out = capsys.readouterr().out + json.dumps(v)
    assert new != OLD and new not in out and f":{new}@" not in out, "the minted value is never printed"
    assert not list((tmp_path / "rotstate").iterdir()), "state file removed after success"


def test_verify_failure_auto_rolls_back_same_set(tmp_path):
    h = Harness(tmp_path)
    h.mutate(lambda s: s.update(break_on_new_secret=["bus-client"]))
    code, v = h.run(*ACK, execute=True)
    assert code == cr.EXIT_FINDINGS and v["outcome"] == "rolled-back", v.get("log")
    calls = _calls(h)
    rotates = [(c, k) for c, k in calls if c.startswith("secrets-rotate")]
    old_class = hashlib.sha256(OLD.encode()).hexdigest()[:4]
    assert [c for c, _ in rotates] == ["secrets-rotate KEY=NATS_PASSWORD", "secrets-rotate KEY=NATS_URL"] * 2
    assert rotates[2][1] == old_class, "rollback restores the saved OLD value"
    recreates = [c for c, _ in calls if not c.startswith(("secrets-rotate", "register-note", "sign-trail"))]
    half = len(recreates) // 2
    assert recreates[:half] == recreates[half:], "rollback recreates exactly the same set, same order"
    assert h.state()["secret"] == OLD
    assert any("VERIFY" in line and "bus-client" in line for line in v["log"])
    assert "rolled-back" in [c for c, _ in calls if c.startswith("register-note")][0]


def test_post_funnel_gate_rolls_back_before_any_recreate(tmp_path):
    """The funnel changed a key it was not asked to: no container may be touched."""
    h = Harness(tmp_path)
    h.mutate(lambda s: s.update(gate_extra={"stack_app,stack_bus": "stack_app"}))
    code, v = h.run(*ACK, execute=True)
    assert code == cr.EXIT_FINDINGS and v["outcome"] == "rolled-back", v.get("log")
    calls = [c for c, _ in _calls(h)]
    assert not [c for c in calls if c.startswith(("recreate-svc", "up-a0"))], "no container touched"
    assert any("GATE" in line and "PMOVES_NETWORKS" in line for line in v["log"])
    assert h.state()["secret"] == OLD


def test_residue_after_restore_demands_a_human(tmp_path):
    """Prod-only key loss shape: restoring the value does not restore the dropped key.
    Production change that makes this fail: rollback declaring success without re-gating."""
    h = Harness(tmp_path)
    h.mutate(lambda s: s.update(gate_extra={"stack_app,stack_bus": "stack_app"}, residue_on_rotate=True))
    code, v = h.run(*ACK, execute=True)
    assert code == cr.EXIT_ROLLBACK_FAILED and v["outcome"] == "rollback-INCOMPLETE"
    assert any(p.name.startswith("NATS_PASSWORD-") for p in (tmp_path / "rotstate").iterdir()), \
        "restore values are KEPT for the human"
    assert oct((tmp_path / "rotstate").stat().st_mode)[-3:] == "700"


def test_mint_failure_restores_without_recreate(tmp_path):
    h = Harness(tmp_path)
    h.mutate(lambda s: s.update(fail_rotate_on="NATS_URL"))
    code, v = h.run(*ACK, execute=True)
    calls = [c for c, _ in _calls(h)]
    assert not [c for c in calls if c.startswith(("recreate-svc", "up-a0"))]
    assert v["outcome"] in ("rolled-back", "rollback-FAILED", "rollback-INCOMPLETE")


def test_make_road_declares_the_tool_and_dry_run_default():
    mk = (TOOLS.parent / "mk" / "codex.mk").read_text()
    block = mk[mk.index("secret-rotate-coordinated:"):mk.index("supabase-key-reconcile:")]
    assert "tools/coordinated_rotate.py" in block
    assert "$(if $(filter 0,$(DRY_RUN)),--execute" in block, "execute only on an explicit DRY_RUN=0"
