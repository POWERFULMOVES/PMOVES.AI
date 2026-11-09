"""The sweep's baseline must be able to waive a TIGHTENING and never a RELAXATION.

Run: python .claude/hooks/damage-control/test_sweep_baseline.py

WHY THIS EXISTS
---------------
sweep_differential.py grew a baseline file so that an intended tightening does not
leave the gate red forever -- a permanently red gate is an ignored gate, which is
the same failure as no gate. But a waiver mechanism next to a security check is
exactly the shape that later starts swallowing the findings that matter. This
repo's recurring defect is a check that cannot fail correctly; a baseline that
could waive a relaxation would be a new instance of it.

So the asymmetry is pinned here, structurally:

  * the baseline set is applied ONLY to the tightening list;
  * no statement that mentions the baseline set also mentions the relaxation list;
  * a non-empty relaxation list still reaches sys.exit(1).

WHAT THIS CANNOT PROVE
----------------------
This reads the module's SYNTAX TREE; it does not execute the sweep, because the
sweep is a top-level script that builds a ~6.5k-command corpus and loads two guard
versions, which takes minutes. So this proves the baseline is WIRED to the right
list, not that the classifier upstream labels every case correctly -- the sweep's
own run is what proves that, and CI runs it on every guard change. Stated plainly
rather than implied, because a structural test that is read as end-to-end is worse
than no test.
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SWEEP = HERE / "sweep_differential.py"
BASELINE = HERE / "sweep_baseline.yaml"

failures = []


def check(ok, label):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


print("== sweep baseline asymmetry ==")
if not SWEEP.is_file():
    print(f"FAIL — {SWEEP} is missing; the sweep is the thing under test")
    sys.exit(1)

tree = ast.parse(SWEEP.read_text(encoding="utf-8"))
names_per_stmt = []
for node in ast.walk(tree):
    if isinstance(node, (ast.Assign, ast.If, ast.Expr, ast.AugAssign)):
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        names_per_stmt.append((node, names))

all_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
check("adjudicated" in all_names, "the sweep reads a baseline set at all (`adjudicated`)")
check("relaxations" in all_names, "the sweep separates a `relaxations` list")
check("tightenings" in all_names, "the sweep separates a `tightenings` list")

# THE LOAD-BEARING ASSERTION. If any single statement mentions both the baseline
# set and the relaxation list, a relaxation could be filtered by the baseline.
both = [
    ast.dump(node)[:90]
    for node, names in names_per_stmt
    if "adjudicated" in names and "relaxations" in names
]
check(not both, "NO statement mentions both the baseline set and the relaxation list")
for d in both:
    print("        offending:", d)

# The baseline filter must iterate the TIGHTENING list, not the relaxation list or
# the raw finding list.
filtered_over = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "new_tightenings" for t in node.targets
    ):
        for comp in ast.walk(node):
            if isinstance(comp, ast.comprehension) and isinstance(comp.iter, ast.Name):
                filtered_over.append(comp.iter.id)
check(filtered_over == ["tightenings"],
      f"the baseline filter iterates the tightening list (got {filtered_over or 'nothing'})")

# A non-empty relaxation list must still be able to fail the run.
exits = [
    node for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "exit"
]
exit_ones = [c for c in exits if c.args and isinstance(c.args[0], ast.Constant) and c.args[0].value == 1]
check(bool(exit_ones), "the sweep can still exit 1")

guards_exit = []
for node in ast.walk(tree):
    if isinstance(node, ast.If):
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        if "relaxations" in names and any(
            isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "exit"
            for c in ast.walk(node)
        ):
            guards_exit.append(True)
check(bool(guards_exit), "a non-empty relaxation list reaches sys.exit(1)")

# The baseline itself must parse and must not smuggle in a wildcard.
if BASELINE.is_file():
    try:
        import yaml
        doc = yaml.safe_load(BASELINE.read_text(encoding="utf-8")) or {}
        rows = doc.get("tightenings") or []
        check(all(r.get("command") for r in rows), "every baseline row names an exact command")
        check(all(r.get("reason") for r in rows), "every baseline row carries a reason")
        # An entry matched by substring or glob could broaden past what was reviewed.
        check(not any("*" in r.get("command", "") for r in rows),
              "no baseline command contains a glob character")
        print(f"  [info] {len(rows)} adjudicated tightening(s) on file")
    except Exception as exc:
        check(False, f"the baseline parses ({exc})")
else:
    print("  [info] no baseline file present — nothing is waived, which is a valid state")

if failures:
    print(f"\nFAIL — {len(failures)} check(s) failed.")
    sys.exit(1)
print("\nPASS — a tightening can be adjudicated; a relaxation cannot.")
