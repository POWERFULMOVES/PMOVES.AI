"""The trail annotations classify the rows they claim, and edit none of them.

Run: python .claude/hooks/damage-control/test_trail_states.py

Three things are asserted, in descending order of how much damage getting them
wrong would do:

  1. INTEGRITY. The committed blob is a byte PREFIX of the trail on disk. The
     whole point of marking rather than removing is that the evidence survives;
     a test that only counted states would pass just as happily over a trail
     somebody had quietly rewritten. Prefix and not equality, because the trail
     is APPEND-ONLY BY DESIGN and a granted operation is supposed to add to it --
     an equality check would go red the first time the mechanism worked.
  2. THE MEASURED SPLIT. 156 synthetic / 11 genuine-stale-reason / 83 current.
     The 11 are real authorized work and must not be tarred with the 156.
  3. STALENESS FAILS LOUD. Feed the classifier an annotation whose expect_count
     no longer matches and it must report COULD-NOT-MEASURE (exit 3) instead of
     re-labelling rows its author never looked at.

Exit: 0 all assertions held - 1 a check failed
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

failures = []


def check(label, condition, detail=""):
    print(("ok   " if condition else "FAIL ") + label)
    if not condition:
        if detail:
            print("       " + str(detail).replace("\n", "\n       "))
        failures.append(label)


spec = importlib.util.spec_from_file_location("trail_states", HERE / "trail_states.py")
ts = importlib.util.module_from_spec(spec)
sys.modules["trail_states"] = ts
spec.loader.exec_module(ts)

TRAIL = HERE / "known-roads.jsonl"
REL = TRAIL.relative_to(REPO).as_posix()

# 1. integrity ---------------------------------------------------------------
committed = subprocess.run(
    ["git", "-C", str(REPO), "show", "HEAD:" + REL],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if committed.returncode != 0:
    check("the trail can be read out of git", False,
          committed.stderr.decode("utf-8", "replace"))
else:
    on_disk = TRAIL.read_bytes()
    check("no committed trail byte was edited or removed (append-only)",
          on_disk.startswith(committed.stdout),
          "disk=%d bytes, HEAD=%d bytes" % (len(on_disk), len(committed.stdout)))

# 2. the measured split -------------------------------------------------------
trail = ts._read(TRAIL)
annotations = ts._read(ts.ANNOTATIONS)
check("the trail parses", trail is not None)
check("the annotations parse", annotations is not None)

if trail is not None and annotations is not None:
    states, problems = ts.classify(trail, annotations)
    tally = {}
    for state in states:
        tally[state] = tally.get(state, 0) + 1
    check("no classification problems", not problems, problems)
    # 250 rows when this was measured. Growth is expected and fine; the two
    # annotated sets are fixed sets of historical rows and must not move.
    check("at least the 250 rows measured on 2026-09-12", len(trail) >= 250, len(trail))
    check("156 synthetic-corpus", tally.get("synthetic-corpus") == 156, tally)
    check("11 genuine-stale-reason", tally.get("genuine-stale-reason") == 11, tally)
    check("every other row is current",
          tally.get("current") == len(trail) - 167, tally)
    check("167 rows carry reason pr:2656 in total",
          sum(1 for r in trail if r.get("reason") == "pr:2656") == 167)

    # The distinction the marking exists to preserve, restated as evidence:
    # the synthetic targets do not exist, the genuine one does.
    synthetic = [r for i, r in enumerate(trail) if states[i] == "synthetic-corpus"]
    genuine = [r for i, r in enumerate(trail) if states[i] == "genuine-stale-reason"]
    check("every synthetic target is absent from disk",
          all(not Path(r["file"]).exists() for r in synthetic),
          [r["file"] for r in synthetic if Path(r["file"]).exists()][:3])
    check("every genuine target is present on disk",
          all(Path(r["file"]).exists() for r in genuine),
          [r["file"] for r in genuine if not Path(r["file"]).exists()][:3])
    check("the genuine rows are Edit/Write, never the sweep's Bash",
          {r["tool"] for r in genuine} <= {"Edit", "Write"},
          sorted({r["tool"] for r in genuine}))

# 3. staleness fails loud ------------------------------------------------------
if trail is not None:
    drifted = json.loads(json.dumps(annotations[0]))
    drifted["expect_count"] = drifted["expect_count"] + 1
    states, problems = ts.classify(trail, [drifted])
    check("a drifted expect_count is reported, not absorbed", bool(problems), problems)
    check("and no row is relabelled on the strength of it",
          all(state == ts.DEFAULT_STATE for state in states),
          sorted(set(states)))

    empty_selector = {"state": "bogus", "select": {}, "expect_count": 0}
    states, problems = ts.classify(trail, [empty_selector])
    check("an empty selector labels nothing",
          all(state == ts.DEFAULT_STATE for state in states),
          sorted(set(states)))

print()
if failures:
    print("FAIL: %d check(s) failed: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("PASS: the split is 156/11/83 and no trail row was touched.")
