"""Classify every row in known-roads.jsonl WITHOUT touching a single one.

    python .claude/hooks/damage-control/trail_states.py [--json]

WHY ADDITIVE AND NOT A CLEANUP
------------------------------
The trail is append-only and it is evidence. 167 of its 250 rows carry the reason
`pr:2656`, and they are two completely different things:

  156  a synthetic sweep corpus, written in one 5.5-minute window on 2026-09-12
       against 13 paths that do not exist, because the sweep inherited a file
       grant it thought it had neutralized;
   11  genuine edits to a real compose file on 2026-08-21, made while PR #2656
       was open, under a grant that was live and correct at the time.

Deleting the 156 would destroy the evidence of how they got there. Deleting or
rewriting the 11 would erase real authorized work and blame it for the 156. So
nothing is edited: annotations live in their own file and are joined at read
time, and a row nobody annotated is `current`.

STALENESS IS AN ERROR, NOT A SHRUG
----------------------------------
Every annotation declares `expect_count`. If the trail grows a row the annotation
now also selects, or loses one, the count stops matching and this exits 3 --
COULD-NOT-MEASURE -- instead of quietly re-labelling rows the author never saw.
An annotation is a claim about a specific set of rows, and a claim that can drift
without complaint is the defect this repository keeps finding.

Exit: 0 classified cleanly · 3 could not classify (missing/unparseable input,
or an annotation whose count no longer matches)
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRAIL = HERE / "known-roads.jsonl"
ANNOTATIONS = HERE / "known-roads-annotations.jsonl"

DEFAULT_STATE = "current"


def _read(path):
    """[rows] or None. None means COULD-NOT-MEASURE -- never an empty list."""
    if not path.is_file():
        return None
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError as exc:
            print("%s:%d is not JSON: %s" % (path.name, number, exc),
                  file=sys.stderr)
            return None
    return rows


def selects(annotation, row):
    """Does `annotation` cover `row`? Every declared key must match.

    `date` matches the UTC date prefix of `ts`; every other key is exact. A
    selector with no keys matches nothing -- an annotation that accidentally
    labels the whole trail is worse than one that labels none of it.
    """
    selector = annotation.get("select") or {}
    if not selector:
        return False
    for key, want in selector.items():
        if key == "date":
            if not str(row.get("ts", "")).startswith(want):
                return False
        elif row.get(key) != want:
            return False
    return True


def classify(trail, annotations):
    """(states, problems). states[i] is the state of trail[i]."""
    states = [DEFAULT_STATE] * len(trail)
    problems = []
    for annotation in annotations:
        state = annotation.get("state")
        if not state:
            problems.append("an annotation declares no state: %r" % (annotation,))
            continue
        hits = [i for i, row in enumerate(trail) if selects(annotation, row)]
        expected = annotation.get("expect_count")
        if expected is not None and len(hits) != expected:
            problems.append(
                "annotation %r selects %d row(s), expect_count says %d — the "
                "trail moved under it; re-measure before trusting either number"
                % (state, len(hits), expected))
            continue
        for i in hits:
            if states[i] != DEFAULT_STATE and states[i] != state:
                problems.append(
                    "row %d is claimed by both %r and %r" % (i, states[i], state))
            states[i] = state
    return states, problems


def main():
    trail = _read(TRAIL)
    if trail is None:
        print("COULD-NOT-MEASURE: %s is missing or unreadable" % TRAIL.name)
        return 3
    annotations = _read(ANNOTATIONS)
    if annotations is None:
        print("COULD-NOT-MEASURE: %s is missing or unreadable — every row would "
              "read as %r, which is exactly the wrong answer" % (ANNOTATIONS.name, DEFAULT_STATE))
        return 3

    states, problems = classify(trail, annotations)
    counts = Counter(states)

    if "--json" in sys.argv:
        print(json.dumps({
            "trail_rows": len(trail),
            "annotations": len(annotations),
            "counts": dict(counts),
            "problems": problems,
            "states": states,
        }, indent=2, sort_keys=True))
    else:
        print("trail rows : %d  (%s)" % (len(trail), TRAIL.name))
        print("annotations: %d  (%s)" % (len(annotations), ANNOTATIONS.name))
        for state, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print("  %5d  %s" % (n, state))
        for annotation in annotations:
            print("\n%s (%d rows, annotated %s by %s)"
                  % (annotation.get("state"), annotation.get("expect_count", -1),
                     annotation.get("annotated", "?"), annotation.get("by", "?")))
            print("  select: %s" % json.dumps(annotation.get("select") or {}, sort_keys=True))
            print("  why   : %s" % annotation.get("why", ""))

    if problems:
        print("\nCOULD-NOT-MEASURE:", file=sys.stderr)
        for problem in problems:
            print("  " + problem, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
