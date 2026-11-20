"""supabase_key_reconcile: converge key SOURCES onto the running Supabase, never
the reverse; idempotent; gate + restore. Also the two composed-road changes it
needs (merge_shared_to_tiers --only, secrets-rotate CLEAR=1).

Fixture shape mirrors B850 on 2026-10-02: the live stack verifies with LIVE, and
env.tier-supabase carries a whole DEAD family. env.tier-ui blanks
SUPABASE_SERVICE_ROLE_KEY and is last in the chain, so Kong's
${SUPABASE_SERVICE_ROLE_KEY:-${SERVICE_ROLE_KEY}} falls through to the DEAD
service key. A plain kong recreate would therefore have removed the only working
service-role consumer.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import supabase_key_reconcile as skr  # noqa: E402
from merge_shared_to_tiers import sync_keys  # noqa: E402
from test_coordinated_rotate import LIVE_JWT, DEAD_JWT, mint  # noqa: E402

LIVE_SVC, LIVE_ANON = mint(LIVE_JWT, "service_role"), mint(LIVE_JWT, "anon")
DEAD_SVC, DEAD_ANON = mint(DEAD_JWT, "service_role"), mint(DEAD_JWT, "anon")
CHAIN = ["env.shared", "env.tier-supabase", "env.tier-api", "env.tier-worker", "env.tier-ui"]

STUB_COMPOSE = r'''#!{py}
import json, sys
from pathlib import Path
root = Path({root!r})
def read(p):
    out = {{}}
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); out[k.strip()] = v.strip()
    return out
I = {{}}
for f in {chain!r}:
    I.update(read(root / f))  # --env-file chain: last wins
def pick(*names):
    for n in names:
        if I.get(n):
            return I[n]
    return ""
supa_file = {{**read(root / "env.shared"), **read(root / "env.tier-supabase")}}
client_file = {{**read(root / "env.shared"), **read(root / "env.tier-worker")}}
svcs = {{
  "supabase-gotrue": {{"environment": {{**supa_file, "GOTRUE_JWT_SECRET": pick("SUPABASE_JWT_SECRET", "JWT_SECRET")}}}},
  "supabase-postgrest": {{"environment": {{**supa_file, "PGRST_JWT_SECRET": pick("SUPABASE_JWT_SECRET", "JWT_SECRET")}}}},
  "supabase-kong": {{"environment": {{**supa_file, "SUPABASE_SERVICE_KEY": pick("SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY"),
                                      "SUPABASE_ANON_KEY": pick("ANON_KEY", "SUPABASE_ANON_KEY")}}}},
  "worker": {{"environment": {{**client_file, "OPENAI_API_KEY": "unrelated"}}}},
}}
print(json.dumps({{"services": svcs}}))
'''

STUB_DOCKER = r'''#!{py}
import json, sys
state = json.load(open({state!r}))
a = sys.argv[1:]
if a[0] == "ps":
    for svc, c in state["containers"].items():
        print(f"{{c['id']}}|pmoves|{{svc}}")
elif a[0] == "inspect":
    for c in state["containers"].values():
        if c["id"] == a[1]:
            print(json.dumps([{{"Config": {{"Env": c["env"]}}, "State": {{"Running": True}}}}])); sys.exit(0)
    sys.exit(1)
'''

STUB_MAKE = r'''#!{py}
import json, os, subprocess, sys
from pathlib import Path
root = Path({root!r}); path = {state!r}
state = json.load(open(path))
args = [x for x in sys.argv[1:] if x not in ("-C", "--no-print-directory") and not x.startswith("/")]
state["calls"].append(" ".join(args))
if args[0] == "secrets-rotate":
    name = args[1].split("=", 1)[1]
    value = "" if "CLEAR=1" in args else os.environ["PMOVES_ROTATE_VALUE"]
    p = root / "env.shared"
    lines = [l for l in p.read_text().splitlines() if not l.startswith(name + "=")] + [f"{{name}}={{value}}"]
    p.write_text("\n".join(lines) + "\n")
elif args[0] == "env-tiers-sync-keys":
    names = args[1].split("=", 1)[1].split(",")
    cmd = [sys.executable, {merge!r}, "--root", str(root)] + [x for n in names for x in ("--only", n)]
    subprocess.run(cmd, check=True, capture_output=True)
    if state.get("sabotage"):
        t = root / "env.tier-api"; t.write_text(t.read_text() + "SUPABASE_JWT_SECRET=" + state["sabotage"] + "\n")
json.dump(state, open(path, "w"))
'''


def build(tmp: Path, *, sabotage: str = ""):
    files = {
        "env.shared": {"JWT_SECRET": DEAD_JWT, "SUPABASE_JWT_SECRET": LIVE_JWT, "SUPABASE_SERVICE_ROLE_KEY": LIVE_SVC,
                       "SUPABASE_SERVICE_KEY": LIVE_SVC, "SERVICE_ROLE_KEY": DEAD_SVC, "SUPABASE_ANON_KEY": LIVE_ANON,
                       "ANON_KEY": DEAD_ANON, "SUPABASE_PUBLISHABLE_KEY": "", "SUPABASE_SECRET_KEY": DEAD_SVC},
        "env.tier-supabase": {"JWT_SECRET": DEAD_JWT, "SUPABASE_JWT_SECRET": DEAD_JWT, "ANON_KEY": DEAD_ANON,
                              "SERVICE_ROLE_KEY": DEAD_SVC, "SUPABASE_SERVICE_ROLE_KEY": DEAD_SVC},
        "env.tier-api": {"SUPABASE_JWT_SECRET": LIVE_JWT},
        "env.tier-worker": {"SUPABASE_SERVICE_ROLE_KEY": LIVE_SVC},
        "env.tier-ui": {"SUPABASE_SERVICE_ROLE_KEY": "", "SUPABASE_ANON_KEY": "", "OTHER": "keep"},
    }
    for name, kv in files.items():
        (tmp / name).write_text("# comment kept\n" + "".join(f"{k}={v}\n" for k, v in kv.items()))
    state = {"calls": [], "sabotage": sabotage, "containers": {
        "supabase-gotrue": {"id": "g1", "env": [f"GOTRUE_JWT_SECRET={LIVE_JWT}"]},
        "supabase-postgrest": {"id": "p1", "env": [f"PGRST_JWT_SECRET={LIVE_JWT}"]},
        "supabase-kong": {"id": "k1", "env": [f"SUPABASE_SERVICE_KEY={LIVE_SVC}", f"SUPABASE_ANON_KEY={DEAD_ANON}"]},
    }}
    (tmp / "state.json").write_text(json.dumps(state))
    fmt = dict(py=sys.executable, root=str(tmp), state=str(tmp / "state.json"), chain=CHAIN,
               merge=str(TOOLS / "merge_shared_to_tiers.py"))
    for name, src in (("fakecompose", STUB_COMPOSE), ("fakedocker", STUB_DOCKER), ("fakemake", STUB_MAKE)):
        (tmp / name).write_text(src.format(**fmt))
        (tmp / name).chmod(0o755)


def run(tmp: Path, *extra):
    code = skr.main(["--stack", f"main={tmp / 'fakecompose'} -p pmoves", "--root", str(tmp),
                     "--docker", str(tmp / "fakedocker"), "--make", str(tmp / "fakemake"),
                     "--state-dir", str(tmp / "st"), "--node", "testnode", "--json", str(tmp / "v.json"), *extra])
    return code, json.loads((tmp / "v.json").read_text())


def env(tmp: Path, name: str) -> dict:
    return skr.read_env(tmp / name)


EXEC = ["--execute", "--confirm", "RECONCILE SUPABASE KEYS @ testnode"]


def test_dry_run_plans_relabel_onto_live_and_touches_nothing(tmp_path, capsys):
    build(tmp_path)
    before = {n: (tmp_path / n).read_text() for n in CHAIN}
    code, v = run(tmp_path)
    assert code == 0
    plan = v["plan"]["env_shared"]
    assert set(plan) == {"JWT_SECRET", "SERVICE_ROLE_KEY", "ANON_KEY", "SUPABASE_SECRET_KEY"}
    assert plan["SUPABASE_SECRET_KEY"].endswith("CLEAR"), "a dead JWT in the opaque slot is cleared"
    assert any("env.tier-ui:SUPABASE_SERVICE_ROLE_KEY" in d for d in v["plan"]["tier_drift"])
    assert {n: (tmp_path / n).read_text() for n in CHAIN} == before
    assert json.loads((tmp_path / "state.json").read_text())["calls"] == []
    out = capsys.readouterr().out
    assert LIVE_JWT not in out and LIVE_SVC not in out and DEAD_SVC not in out


def test_execute_converges_then_is_idempotent(tmp_path):
    build(tmp_path)
    code, v = run(tmp_path, *EXEC)
    assert code == 0, v
    shared = env(tmp_path, "env.shared")
    assert shared["JWT_SECRET"] == LIVE_JWT and shared["SERVICE_ROLE_KEY"] == LIVE_SVC
    assert shared["SUPABASE_SECRET_KEY"] == ""
    sup = env(tmp_path, "env.tier-supabase")
    assert sup["SUPABASE_JWT_SECRET"] == LIVE_JWT and sup["SERVICE_ROLE_KEY"] == LIVE_SVC
    assert env(tmp_path, "env.tier-ui")["SUPABASE_SERVICE_ROLE_KEY"] == LIVE_SVC
    assert env(tmp_path, "env.tier-ui")["OTHER"] == "keep"
    assert "# comment kept" in (tmp_path / "env.tier-ui").read_text(), "surgical, not a rewrite"
    calls = json.loads((tmp_path / "state.json").read_text())["calls"]
    assert not [c for c in calls if c.startswith("recreate-svc")], "no container recreated by default"
    code, v = run(tmp_path)
    assert code == 0 and v["plan"]["env_shared"] == {} and v["plan"]["tier_drift"] == []


def test_gate_refuses_a_change_to_the_live_jwt_secret_and_restores(tmp_path):
    """Production change that makes this fail: dropping the gate's check that no
    Supabase service's effective JWT secret moves (it would log every user out)."""
    build(tmp_path, sabotage=DEAD_JWT)
    before = {n: env(tmp_path, n) for n in CHAIN}
    code, v = run(tmp_path, *EXEC)
    assert code == 1 and v["outcome"] == "rolled-back"
    assert any("GOTRUE_JWT_SECRET" in line and "logged out" in line for line in v["log"])
    for n in CHAIN:
        after = env(tmp_path, n)
        for k in skr.ALL_NAMES:
            assert after.get(k, "") == before[n].get(k, ""), f"{n}:{k} not restored"


def test_never_proposes_changing_the_live_secret(tmp_path):
    build(tmp_path)
    _, v = run(tmp_path)
    assert "SUPABASE_JWT_SECRET" not in v["plan"]["env_shared"]


def test_merge_only_is_surgical_and_copies_empty(tmp_path):
    p = tmp_path / "env.tier-x"
    p.write_text("# head\nA=1\nB=2\nA=dup\nC=3\n")
    changes = sync_keys(p, {"A": "9", "C": ""})
    assert p.read_text() == "# head\nA=9\nB=2\nC=\n"
    assert {c[0] for c in changes} == {"A", "C"}


def test_merge_only_flag_is_new_failing_before(tmp_path):
    """Failing-before control without touching the worktree: origin/main's
    merge_shared_to_tiers has no --only, so the road it backs could not exist."""
    old = subprocess.run(["git", "show", "origin/main:pmoves/tools/merge_shared_to_tiers.py"],
                         cwd=TOOLS, capture_output=True, text=True)
    if old.returncode != 0:
        import pytest
        pytest.skip("origin/main not available")
    (tmp_path / "old.py").write_text(old.stdout)
    (tmp_path / "env.shared").write_text("A=1\n")
    r = subprocess.run([sys.executable, str(tmp_path / "old.py"), "--root", str(tmp_path), "--only", "A"],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "unrecognized arguments" in r.stderr


def test_secrets_rotate_clear_rides_the_same_road():
    mk = (TOOLS.parent / "mk" / "codex.mk").read_text()
    block = mk[mk.index("secrets-rotate: ##"):mk.index("@CHIT_EXPORT_FORCE=1 $(MAKE) --no-print-directory chit-export")]
    assert '$(if $(filter 1,$(CLEAR)),--clear "$(KEY)",--rotate "$(KEY)"' in block
