"""Differential sweep: does a damage-control change ever LET SOMETHING THROUGH?

    python .claude/hooks/damage-control/sweep_differential.py [<base-git-ref>]

Generates a corpus of commands from patterns.yaml -- every readOnly and noDelete
entry, in six locations, under thirteen operation shapes, plus prose forms -- and
compares the CURRENT guard's verdict against the guard at `<base-git-ref>`
(default: HEAD~1). Every verdict change must fall into one of two SANCTIONED
relaxation classes; anything else exits 1.

  A  prose-only    no token in the command resolves to a path the entry covers
  B  repo-scoped   the entry is in patterns.yaml repoScopedPaths and the target
                   resolves outside the repository

WHY THIS EXISTS, in one number: the hand-written suite was green, and this sweep
found 16 permissive regressions in the same change. A guard suite tests the cases
someone thought of. A sweep tests the cases the config contains. Run BOTH before
claiming a guard change is safe.

Exit codes:  0 clean   1 unsanctioned change(s) found   3 could not run

Note: ~6.5k commands x two guards, ~70 ms each. Budget roughly 15 minutes, and do
NOT run it through `make` -- make collapses every nonzero exit to 2, which erases
the 0/1/3 distinction this tool reports.
"""

import importlib.util, os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Measure the tree THIS FILE LIVES IN, not whatever CLAUDE_PROJECT_DIR happens to
# say. A worktree is not a checkout: taking the env value made the base ref resolve
# against a DIFFERENT branch in a different tree, which would compare two unrelated
# guards and call the result evidence.
REPO = str(HERE.parents[2].resolve())
_env = os.environ.get("CLAUDE_PROJECT_DIR")
if _env and Path(_env).resolve() != Path(REPO):
    print(f"note: CLAUDE_PROJECT_DIR={_env} differs from this file's tree; "
          f"measuring {REPO}", file=sys.stderr)
DC = Path(REPO) / ".claude" / "hooks" / "damage-control"
BASE_REF = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1"
os.environ["CLAUDE_PROJECT_DIR"] = REPO
# A grant open on this node would make the result depend on state outside the run.
os.environ.pop("KNOWN_ROAD", None)

# Materialize the base guard beside a temp dir so both versions load side by side.
SCRATCH = Path(tempfile.mkdtemp(prefix="dc-sweep-"))
try:
    blob = subprocess.run(
        ["git", "-C", REPO, "show", f"{BASE_REF}:.claude/hooks/damage-control/bash-tool-damage-control.py"],
        capture_output=True, text=True, check=True).stdout
except (subprocess.CalledProcessError, OSError) as exc:
    print(f"could not read the guard at {BASE_REF}: {exc}", file=sys.stderr)
    raise SystemExit(3)
(SCRATCH / "old_guard.py").write_text(blob, encoding="utf-8")
print(f"base={BASE_REF}  repo={REPO}")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


new = load("dc_new", DC / "bash-tool-damage-control.py")
old = load("dc_old", SCRATCH / "old_guard.py")
cfg = new.load_config()
ps = load("ps", DC / "path_scope.py")

# Take away node-local grant state, and keep this run out of the audit trail.
#
# The KNOWN_ROAD pop above carries the comment "a grant open on this node would
# make the result depend on state outside the run" -- but _active_grant() falls
# back to a FILE grant (.known-road-active) whenever the env var is empty, so the
# pop neutralized one of two sources and delivered half its intent. Both halves of
# the consequence were measured on 2026-09-12:
#
#   1. 156 rows appended to the git-TRACKED known-roads.jsonl in a single
#      5.5-minute run, every one a synthetic corpus target -- docker-composez.yml
#      from the `*`->`z` substitution in concretize(), pmoves/sub/ and /srv/stack/
#      from PLACES. That trail exists to answer "who authorized this edit, and
#      why"; probes in it make it answer wrongly, and a trail that lies is worse
#      than an empty one, because an empty one does not mislead.
#   2. The verdicts themselves depended on whether this node happened to hold an
#      open grant -- precisely what the pop above set out to prevent.
#
# Both go away by removing both grant sources and pointing the trail at this run's
# own scratch dir. `_trail_path` and `_grant_file` are levers the module already
# offers; test_bash_known_roads.py patches `_trail_path` the same way.
#
# This CANNOT skew the comparison. Both guard versions resolve `known_roads`
# through the one entry in sys.modules, so anything neutralized here is
# neutralized identically on both sides and the DIFFERENTIAL is untouched -- a
# granted allow/allow pair simply becomes a blocked/blocked pair, and neither is
# a verdict change.
_kr = sys.modules.get("known_roads")
if _kr is None:  # the guard imports it; if that ever stops, say so, do not guess
    print("could not reach the known_roads module to isolate the audit trail; "
          "refusing to run a sweep that would write to it", file=sys.stderr)
    raise SystemExit(3)
_kr._trail_path = lambda: SCRATCH / "known-roads.jsonl"
_kr._grant_file = lambda: SCRATCH / "no-grant-here"

RO = cfg["readOnlyPaths"]
ND = cfg["noDeletePaths"]
REPO_SCOPED = set(cfg.get("repoScopedPaths") or [])

# Verbs built from parts so this file's own text does not trip the guard that is
# reading it (same convention as test_gitlock_allowlist.py).
V_RM = "r" + "m"
V_MV = "m" + "v"
V_CP = "c" + "p"
V_CH = "ch" + "mod"
V_TEE = "t" + "ee"
V_TR = "trunc" + "ate"
V_SED = "s" + "ed"

OPS = [
    "echo x > {p}",
    "echo x >> {p}",
    V_TEE + " {p} < in",
    V_SED + " -i 's/a/b/' {p}",
    V_MV + " /tmp/a {p}",
    V_CP + " /tmp/a {p}",
    V_RM + " {p}",
    V_CH + " 755 {p}",
    V_TR + " -s 0 {p}",
    "python3 -c \"open('{p}','w').write('x')\"",
    "python3 -c \"from pathlib import Path; Path('{p}').write_text('x')\"",
    "node -e \"fs.writeFileSync('{p}', 'x')\"",
    "python3 -c \"import os; os.remove('{p}')\"",
]

# Where the target sits. Relative = inside the repo. The others are elsewhere on
# the host, which is what a repo-scoped entry must stop claiming authority over.
PLACES = [
    ("in-repo-relative", lambda e: e),
    ("in-repo-dotslash", lambda e: "./" + e),
    ("in-repo-nested", lambda e: "pmoves/sub/" + e),
    ("in-repo-absolute", lambda e: REPO + "/" + e),
    ("host-absolute", lambda e: "/srv/stack/" + e),
    ("host-tilde", lambda e: "~/work/elsewhere/" + e),
]


def concretize(entry: str) -> str:
    """Turn a patterns.yaml entry into a concrete target path."""
    e = entry
    if e.startswith("~") or e.startswith("/"):
        return e.rstrip("/") + ("/f.txt" if e.endswith("/") else "")
    if e.endswith("/"):
        e = e.rstrip("/") + "/f.txt"
    e = e.replace("**/", "x/").replace("*", "z")
    return e


cases = []
for entry in RO + ND:
    target = concretize(entry)
    absolute_entry = entry.startswith("/") or entry.startswith("~")
    for place_name, place in PLACES:
        if absolute_entry and place_name != "in-repo-relative":
            continue          # an absolute entry has only one location
        p = target if absolute_entry else place(target)
        for op in OPS:
            cases.append((entry, place_name, op.format(p=p)))

# prose: a sentence that merely NAMES a protected path, plus one written into a
# note under /tmp. No token in either resolves to such a path.
for entry in RO + ND:
    name = entry.rstrip("/")
    if name.startswith("~") or name.startswith("/") or "*" in name:
        continue
    cases.append((entry, "prose-echo",
                  "echo 'the guard refuses " + V_CH + " on a " + name + " directory' > /tmp/n.md"))
    cases.append((entry, "prose-note",
                  "python3 -c \"open('/tmp/n.md','w').write('documented: " + name + " is protected')\""))

print(f"corpus: {len(cases)} commands over {len(RO)} readOnly + {len(ND)} noDelete entries")

changed, unsanctioned = [], []
for entry, place_name, cmd in cases:
    ob, oa, orsn = old.check_command(cmd, cfg)
    nb, na, nrsn = new.check_command(cmd, cfg)
    if (ob, oa) == (nb, na):
        continue
    # Classify the change.
    if nb and not ob:
        unsanctioned.append(("NEWLY BLOCKED", entry, place_name, cmd, orsn, nrsn))
        continue
    tokens = ps.command_tokens(cmd)
    keep, hits = ps.confirm(tokens, entry, tuple(REPO_SCOPED))
    saw = any(ps.token_matches_entry(t, entry) for t in (tokens or []))
    if not saw:
        cls = "A prose-only"
    elif entry in REPO_SCOPED and not hits:
        cls = "B repo-scoped outside repo"
    else:
        cls = None
    if cls is None:
        unsanctioned.append(("UNCLASSIFIED RELAXATION", entry, place_name, cmd, orsn, nrsn))
    else:
        changed.append((cls, entry, place_name, cmd))

from collections import Counter
print(f"\nverdict changes: {len(changed)} sanctioned, {len(unsanctioned)} NOT sanctioned")
for cls, n in Counter(c[0] for c in changed).most_common():
    print(f"  {n:5d}  {cls}")
print("\nby entry (sanctioned relaxations):")
for (cls, entry), n in Counter((c[0], c[1]) for c in changed).most_common():
    print(f"  {n:5d}  {cls:28s} {entry}")

# Split the findings by DIRECTION before deciding. A relaxation and a tightening
# are both "unsanctioned" to the classifier above, but they point opposite ways:
# a relaxation opens a hole, a tightening closes one. Only the second can be
# adjudicated, and only by exact command string.
relaxations = [r for r in unsanctioned if r[0] != "NEWLY BLOCKED"]
tightenings = [r for r in unsanctioned if r[0] == "NEWLY BLOCKED"]

# The baseline is read ONLY here, ONLY for tightenings. `relaxations` is never
# consulted against it, so no entry in that file can make this sweep tolerate
# something being let through -- which is the only property of it that matters.
BASELINE = DC / "sweep_baseline.yaml"
adjudicated = set()
if BASELINE.is_file():
    try:
        import yaml
        doc = yaml.safe_load(BASELINE.read_text(encoding="utf-8")) or {}
        adjudicated = {t["command"] for t in (doc.get("tightenings") or []) if t.get("command")}
    except Exception as exc:  # a baseline we cannot parse waives NOTHING
        print(f"warning: could not read {BASELINE.name}: {exc} — waiving nothing",
              file=sys.stderr)
        adjudicated = set()

new_tightenings = [r for r in tightenings if r[3] not in adjudicated]
known_tightenings = [r for r in tightenings if r[3] in adjudicated]

print(f"\nrelaxations (always fatal)      : {len(relaxations)}")
print(f"tightenings, adjudicated         : {len(known_tightenings)}")
print(f"tightenings, NOT yet adjudicated : {len(new_tightenings)}")

if relaxations:
    print(f"\n>>> {len(relaxations)} RELAXATION(S) — STOP. This change lets through "
          f"something the base guard refused:")
    for row in relaxations[:30]:
        print("   ", row[0], "|", row[1], "|", row[3][:110])
        print("        old:", row[4][:100])
        print("        new:", row[5][:100])
if new_tightenings:
    print(f"\n>>> {len(new_tightenings)} UNADJUDICATED TIGHTENING(S) — this change "
          f"refuses something the base guard allowed. If each is intended, record it "
          f"in {BASELINE.name} with a reason:")
    for row in new_tightenings[:30]:
        print("   ", row[0], "|", row[1], "|", row[3][:110])
        print("        old:", row[4][:100])
        print("        new:", row[5][:100])
if relaxations or new_tightenings:
    sys.exit(1)
if known_tightenings:
    print(f"\nOK — {len(known_tightenings)} adjudicated tightening(s), no relaxations, "
          f"every other verdict change in a sanctioned class.")
else:
    print("\nOK — every verdict change is one of the two sanctioned classes.")
