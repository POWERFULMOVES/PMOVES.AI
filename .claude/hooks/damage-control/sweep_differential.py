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

if unsanctioned:
    print(f"\n>>> {len(unsanctioned)} UNSANCTIONED CHANGE(S) — STOP:")
    for row in unsanctioned[:30]:
        print("   ", row[0], "|", row[1], "|", row[3][:110])
        print("        old:", row[4][:100])
        print("        new:", row[5][:100])
    sys.exit(1)
print("\nOK — every verdict change is one of the two sanctioned classes.")
