#!/usr/bin/env python3
"""Derive the phase-2 dispositions of the e2e reconcile ground truth FROM THE SPECS.

Phase 2 of lane test/e2e-reconcile-open-jev. ``e2e_reconcile_triage.py`` (phase 1) wrote
one row per CI failure. This script decides what became of each row by reading the
current specs, so the ground truth can be regenerated instead of hand-edited:

  * test inventory, tags and fixme annotations: ``playwright test --list --reporter=json``
  * fixme reason: the ``// fixme: ...`` comment block directly above each ``test.fixme(``
  * renames: a ``// renamed-from: <old title>`` comment directly above the test
  * deletions: a ``// Removed <date> (...): '<old title>'`` comment in the spec
  * default-run counts: a Playwright JSON report of ``npm run test:e2e``

Per row it sets ``phase2a_disposition`` (updated-to-current | fixme | tagged-backend |
deleted), ``phase2a_issue``, and adds ``phase2a_reason_category`` (unwired |
behaviour-mismatch | bug | not-built), ``phase2a_reason`` and ``phase2a_current``. Phase-1
keys are never touched. The earlier hand-written phase-2a value, where it said more than
"fixme", is kept once as ``phase2a_prior`` (history only; the derived fields supersede it). It then re-renders the "Phase 2" section of the markdown twin.

Usage (from pmoves/ui):
    CI=1 PLAYWRIGHT_JSON_OUTPUT_NAME=run.json npx playwright test --grep-invert @backend \
        --reporter=line,json; echo $? > run.rc
    python3 scripts/e2e_reconcile_dispositions.py --json e2e/RECONCILE-2026-09-28.json \
        --md e2e/RECONCILE-2026-09-28.md --run-report run.json --run-rc "$(cat run.rc)"

Exit codes: 0 wrote output, 3 could not measure (list failed, unmatched row, fixme with
no classifiable reason, report unreadable). Nothing is written on exit 3.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_reconcile_triage import redact  # noqa: E402  (same REDACT rules as phase 1)

UI_ROOT = Path(__file__).resolve().parent.parent
PHASE2_HEADING = "## Phase 2: dispositions derived from the specs"
LEGACY_HEADING = "## Phase 2a: dispositions (2026-09-28)"
DERIVED = {"updated-to-current", "fixme", "tagged-backend", "deleted"}

CATEGORIES = [  # first match wins
    ("bug", re.compile(r"REAL UI BUG|\bbug\b", re.I)),
    ("unwired", re.compile(r"\bunwired\b", re.I)),
    ("behaviour-mismatch", re.compile(r"behaviou?r mismatch", re.I)),
    ("not-built", re.compile(r"NOT BUILT", re.I)),
]
RENAMED = re.compile(r"^\s*//\s*renamed-from:\s*(.+?)\s*$")
REMOVED = re.compile(r"//\s*Removed [^:]*:\s*'([^']+)'")
ISSUE = re.compile(r"#(\d{3,5})\b")

NEVER_IN_UI_SOURCE_NOTE = (
    "`never-in-ui-source` (phase 1, `selector_checks[].ui_history`) means the TESTID/TEXT STRING the "
    "spec looked for was absent from UI source on every ref. It does NOT mean the feature was absent: "
    "most of those features were built and rendered under other selectors, and phase 2 updated those "
    "specs to the real selectors."
)


class CouldNotMeasure(Exception):
    pass


def playwright_list(list_json: str | None) -> dict:
    if list_json:
        return json.loads(Path(list_json).read_text())
    try:
        p = subprocess.run(["npx", "playwright", "test", "--list", "--reporter=json"],
                           cwd=UI_ROOT, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CouldNotMeasure(f"playwright --list failed to run: {e}") from e
    if p.returncode != 0:
        raise CouldNotMeasure(f"playwright --list rc={p.returncode}: {redact(p.stderr[-500:])}")
    return json.loads(p.stdout)


def inventory(listing: dict) -> list[dict]:
    """Every test as {file, line, path, title, tags, fixme}."""
    out: list[dict] = []

    def walk(suite: dict, path: list[str]) -> None:
        for sp in suite.get("specs", []):
            anns = [a.get("type") for t in sp.get("tests", []) for a in t.get("annotations", [])]
            out.append({"file": "e2e/" + sp["file"], "line": sp["line"], "path": path, "title": sp["title"],
                        "tags": sp.get("tags", []), "fixme": "fixme" in anns})
        for child in suite.get("suites", []):
            title = child.get("title", "")
            walk(child, path + ([title] if title and not title.endswith(".ts") else []))

    for s in listing.get("suites", []):
        walk(s, [])
    if not out:
        raise CouldNotMeasure("playwright --list returned no tests")
    return out


def comment_block_above(lines: list[str], line_no: int) -> list[str]:
    """The contiguous // comment lines directly above 1-based line_no."""
    block: list[str] = []
    i = line_no - 2
    while i >= 0 and lines[i].strip().startswith("//"):
        block.insert(0, lines[i])
        i -= 1
    return block


def fixme_reason(lines: list[str], line_no: int, where: str) -> tuple[str, str, int | None]:
    block = comment_block_above(lines, line_no)
    start = next((k for k, ln in enumerate(block) if "fixme:" in ln), None)
    if start is None:
        raise CouldNotMeasure(f"{where}: test.fixme has no '// fixme:' reason comment above it")
    text = " ".join(re.sub(r"^\s*//\s?", "", ln).strip() for ln in block[start:])
    text = re.sub(r"^fixme:\s*", "", text)
    cat = next((c for c, pat in CATEGORIES if pat.search(text)), None)
    if cat is None:
        raise CouldNotMeasure(f"{where}: fixme reason is not classifiable: {text[:120]!r}")
    m = ISSUE.search(text)
    return cat, redact(text), int(m.group(1)) if m else None


def annotate_tests(tests: list[dict]) -> None:
    cache: dict[str, list[str]] = {}
    for t in tests:
        f = t["file"]
        if f not in cache:
            try:
                cache[f] = (UI_ROOT / f).read_text().splitlines()
            except OSError as e:
                raise CouldNotMeasure(f"cannot read {f}: {e}") from e
        lines = cache[f]
        t["renamed_from"] = [m.group(1) for ln in comment_block_above(lines, t["line"])
                             if (m := RENAMED.match(ln))]
        t["reason"] = fixme_reason(lines, t["line"], f"{f}:{t['line']}") if t["fixme"] else None


def match_row(row: dict, tests: list[dict], removed: dict[str, set[str]]) -> dict | None:
    spec = row["spec"]
    parts = row["title_path"].split(" › ")
    title, path = parts[-1], parts[:-1]
    cands = [t for t in tests if t["file"] == spec and (t["title"] == title or title in t["renamed_from"])]
    if len(cands) > 1:
        cands = [t for t in cands if t["path"] == path]
    if len(cands) == 1:
        return cands[0]
    if not cands and title in removed.get(spec, set()):
        return None
    raise CouldNotMeasure(f"row {row['n']} ({spec} › {title}): {len(cands)} matching tests")


def disposition(t: dict | None) -> tuple[str, str | None, str | None, int | None]:
    if t is None:
        return "deleted", None, None, None
    if "@backend" in t["tags"] or "backend" in t["tags"]:
        return "tagged-backend", None, None, None
    if t["fixme"]:
        cat, text, issue = t["reason"]
        return "fixme", cat, text, issue
    return "updated-to-current", None, None, None


def read_run(report: str, rc: str | None) -> dict:
    try:
        stats = json.loads(Path(report).read_text())["stats"]
    except (OSError, ValueError, KeyError) as e:
        raise CouldNotMeasure(f"run report unreadable: {e}") from e
    return {
        "command": "CI=1 npx playwright test --grep-invert @backend (== npm run test:e2e, no backend)",
        "total": stats["expected"] + stats["skipped"] + stats["unexpected"] + stats.get("flaky", 0),
        "passed": stats["expected"],
        "skipped": stats["skipped"],
        "failed": stats["unexpected"],
        "flaky": stats.get("flaky", 0),
        "rc": int(rc) if rc not in (None, "") else None,
    }


def derive(doc: dict, tests: list[dict], run: dict | None) -> dict:
    removed: dict[str, set[str]] = {}
    for f in {t["file"] for t in tests} | {r["spec"] for r in doc["failures"]}:
        p = UI_ROOT / f
        if p.exists():
            removed[f] = set(REMOVED.findall(p.read_text()))

    for row in doc["failures"]:
        t = match_row(row, tests, removed)
        disp, cat, text, issue = disposition(t)
        prior = row.get("phase2a_disposition")
        if "phase2a_prior" not in row and prior not in DERIVED and prior not in (None, "fixme"):
            row["phase2a_prior"] = prior  # hand-written phase-2a value, history only
        row["phase2a_disposition"] = disp
        row["phase2a_issue"] = issue
        row["phase2a_reason_category"] = cat
        row["phase2a_reason"] = text
        row["phase2a_current"] = None if t is None else {
            "where": f"{t['file']}:{t['line']}", "describe": " › ".join(t["path"]), "title": t["title"],
            "renamed": t["title"] != row["title_path"].split(" › ")[-1]}

    default = [t for t in tests if "backend" not in t["tags"] and "@backend" not in t["tags"]]
    fixmes = [t for t in default if t["fixme"]]
    rows = doc["failures"]
    p2 = doc.setdefault("phase2a", {})
    p2["derived_by"] = "pmoves/ui/scripts/e2e_reconcile_dispositions.py"
    p2["annotations"] = {"never-in-ui-source": NEVER_IN_UI_SOURCE_NOTE}
    p2["row_dispositions"] = dict(Counter(r["phase2a_disposition"] for r in rows).most_common())
    p2["row_fixme_categories"] = dict(Counter(r["phase2a_reason_category"] for r in rows
                                              if r["phase2a_reason_category"]).most_common())
    p2["suite"] = {
        "tests": len(tests),
        "backend_tagged": len(tests) - len(default),
        "default_run_tests": len(default),
        "fixme": len(fixmes),
        "fixme_categories": dict(Counter(t["reason"][0] for t in fixmes).most_common()),
        "issues_referenced": sorted({t["reason"][2] for t in fixmes if t["reason"][2]}),
        "fixme_tests": [{"where": f"{t['file']}:{t['line']}", "title": t["title"], "category": t["reason"][0],
                         "issue": t["reason"][2], "reason": t["reason"][1]} for t in fixmes],
    }
    if run is not None:
        p2["local_default_run"] = run
    return doc


def _cell(x) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def render_phase2(doc: dict) -> str:
    p2, rows, suite = doc["phase2a"], doc["failures"], doc["phase2a"]["suite"]
    run = p2.get("local_default_run", {})
    L = [PHASE2_HEADING, "",
         "Generated by `pmoves/ui/scripts/e2e_reconcile_dispositions.py` from the specs themselves: the test "
         "inventory from `playwright test --list`, each fixme's reason from the `// fixme:` comment above it, "
         "renames from `// renamed-from:` comments, and the counts from a JSON report of the default run. "
         "Do not hand-edit this section; rerun the script. The JSON twin carries the same fields per row "
         "(`phase2a_disposition`, `phase2a_issue`, `phase2a_reason_category`, `phase2a_reason`, "
         "`phase2a_current`); phase-1 keys are unchanged. `phase2a_prior` keeps the earlier hand-written "
         "phase-2a value as history only; where it disagrees, the derived fields are the truth (e.g. the "
         "notebook/health success-shape tests: their 401 checks are new sibling tests, and the original "
         "titles now run only under `@backend`).", "",
         f"**Annotation.** {NEVER_IN_UI_SOURCE_NOTE}", "",
         "### What became of the 120 CI failures", "", "| disposition | n |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in p2["row_dispositions"].items()]
    L += ["", "Fixme reasons among those rows:", "", "| category | n |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in p2["row_fixme_categories"].items()]
    L += ["", "### Whole suite", "",
          f"- {suite['tests']} tests; {suite['backend_tagged']} tagged `@backend` (excluded from `npm run test:e2e`, "
          f"run with `npm run test:e2e:backend` against a live stack + `E2E_AUTH_TOKEN`); "
          f"{suite['default_run_tests']} in the default run.",
          f"- {suite['fixme']} `test.fixme` in the default run: "
          + ", ".join(f"{k} {v}" for k, v in suite["fixme_categories"].items())
          + ". Issues referenced: " + ", ".join(f"#{i}" for i in suite["issues_referenced"]) + "."]
    if run:
        L.append(f"- Default run ({_cell(run['command'])}): **{run['passed']} passed / {run['skipped']} skipped / "
                 f"{run['failed']} failed**" + (f", flaky {run['flaky']}" if run.get("flaky") else "")
                 + (f", rc {run['rc']}" if run.get("rc") is not None else "") + f", of {run['total']}. "
                 f"Skipped = the {suite['fixme']} fixme tests below"
                 + (f" plus {run['skipped'] - suite['fixme']} runtime `test.skip` (not a fixme; see the run report)"
                    if run["skipped"] > suite["fixme"] else "")
                 + "; the @backend tests are not in this run.")
    L += ["", "### Every fixme in the default run", "", "| where | test | category | issue | reason |",
          "|---|---|---|---|---|"]
    for f in suite["fixme_tests"]:
        L.append(f"| {f['where'].replace('e2e/', '')} | {_cell(f['title'])} | {f['category']} | "
                 f"{'#' + str(f['issue']) if f['issue'] else ''} | {_cell(f['reason'])} |")
    L += ["", "### Per row", "", "| # | phase-1 test | disposition | category | issue | now |", "|---|---|---|---|---|---|"]
    for r in rows:
        cur = r["phase2a_current"]
        now = "" if cur is None else cur["where"].replace("e2e/", "") + (
            f" (renamed: {_cell(cur['title'])})" if cur["renamed"] else "")
        L.append(f"| {r['n']} | {_cell(r['title_path'].split(' › ')[-1])} | {r['phase2a_disposition']} | "
                 f"{r['phase2a_reason_category'] or ''} | {'#' + str(r['phase2a_issue']) if r['phase2a_issue'] else ''} | {now} |")
    return "\n".join(L) + "\n"


def splice_md(md: str, section: str) -> str:
    for heading in (PHASE2_HEADING, LEGACY_HEADING):
        i = md.find(heading)
        if i != -1:
            return md[:i] + section
    return md.rstrip("\n") + "\n\n" + section


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="phase-1 ground truth JSON (updated in place)")
    ap.add_argument("--md", help="markdown twin; its Phase 2 section is re-rendered")
    ap.add_argument("--list-json", help="saved `playwright test --list --reporter=json` output (default: run it)")
    ap.add_argument("--run-report", help="Playwright JSON report of the default run")
    ap.add_argument("--run-rc", help="exit code of that run")
    a = ap.parse_args()
    try:
        doc = json.loads(Path(a.json).read_text())
        if doc.get("schema") != "pmoves.e2e_reconcile.v1":
            raise CouldNotMeasure(f"unexpected schema {doc.get('schema')!r}")
        tests = inventory(playwright_list(a.list_json))
        annotate_tests(tests)
        run = read_run(a.run_report, a.run_rc) if a.run_report else None
        doc = derive(doc, tests, run)
        md = splice_md(Path(a.md).read_text(), render_phase2(doc)) if a.md else None
    except CouldNotMeasure as e:
        print(f"COULD-NOT-MEASURE: {e}", file=sys.stderr)
        return 3
    Path(a.json).write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {a.json}")
    if md is not None:
        Path(a.md).write_text(md)
        print(f"wrote {a.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
