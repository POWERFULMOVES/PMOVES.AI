#!/usr/bin/env python3
"""Deterministic triage of a Playwright CI failure log against the current UI source.

Phase 1 of lane test/e2e-reconcile-open-jev. No model is involved: every field in
the output is derived mechanically from (a) the CI job log, (b) the per-test
``error-context.md`` ARIA snapshots in the ``playwright-screenshots`` artifact,
and (c) grep over the current ``pmoves/ui/{app,components,lib,hooks}`` source.

Usage (from pmoves/ui):
    gh run view --job <E2E_JOB_ID> --log > e2e.log
    gh run download <RUN_ID> -n playwright-screenshots -D art
    python3 scripts/e2e_reconcile_triage.py --log e2e.log --artifacts art \
        --run-id <RUN_ID> --job-id <E2E_JOB_ID> --out e2e/RECONCILE-2026-09-28.json

Exit codes: 0 wrote output, 3 could not measure (log unparseable / count mismatch).
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

UI_ROOT = Path(__file__).resolve().parent.parent
SRC_DIRS = ("app", "components", "lib", "hooks")
SRC_EXT = {".ts", ".tsx", ".js", ".jsx"}

LOG_PREFIX = re.compile(r"^[^\t]*\t[^\t]*\t\d{4}-\d\d-\d\dT[0-9:.]+Z ?")
ANSI = re.compile(r"(\x1b|\^\[)\[[0-9;]*m")
HEADER = re.compile(r"^\s+(\d+)\) \[chromium\] › (e2e/[^:]+):(\d+):(\d+) › (.+?)\s*─*\s*$")
SUMMARY = re.compile(r"^\s+\d+ failed\s*$")
REDACT = [
    (re.compile(r"(eyJ[A-Za-z0-9_-]{8,})\.[A-Za-z0-9_.-]+"), "<redacted-jwt>"),
    (re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1<redacted>@"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), lambda m: m.group(0) if m.group(0).startswith("127.") else "<ip>"),
]

BACKEND_RE = re.compile(
    r"ECONNREFUSED|ERR_CONNECTION|net::ERR_|fetch failed|Failed to fetch|connection refused"
    r"|status(?: code)?:? ?5\d\d|:54321|kong|SUPABASE_[A-Z_]+ (?:and [A-Z_]+ )?(?:are|is) required"
    r"|waitForResponse",
    re.I,
)
ASSERTION_MATCHERS = re.compile(r"\.(toBe|toEqual|toContain|toHaveValue|toHaveCount|toBeFocused|toHaveText|toBeGreaterThan\w*|toBeTruthy|toBeFalsy)\(")


def redact(s: str) -> str:
    for pat, rep in REDACT:
        s = pat.sub(rep, s)
    return s


def clean_log(raw: str) -> list[str]:
    return [ANSI.sub("", LOG_PREFIX.sub("", ln)) for ln in raw.splitlines()]


def parse_blocks(lines: list[str]) -> list[dict]:
    blocks, cur = [], None
    for ln in lines:
        m = HEADER.match(ln)
        if m:
            if cur:
                blocks.append(cur)
            cur = {"n": int(m.group(1)), "spec": m.group(2), "line": int(m.group(3)),
                   "title_path": m.group(5).strip(), "body": []}
            continue
        if cur and SUMMARY.match(ln):
            blocks.append(cur)
            cur = None
            break
        if cur is not None:
            cur["body"].append(ln)
    if cur:
        blocks.append(cur)
    return blocks


def analyse_block(b: dict) -> dict:
    body = b["body"]
    text = "\n".join(body)
    errors = [ln.strip() for ln in body if re.match(r"^\s+(Error: |Test timeout of )", ln)]
    locator = None
    for ln in body:
        m = re.match(r"^\s+Locator: (.*)$", ln)
        if m:
            locator = m.group(1).strip()
            break
    if not locator:
        for ln in body:
            m = re.match(r"^\s+- waiting for (.*?)\s*$", ln)
            if m:
                locator = m.group(1).strip()
                break
    expected = next((re.sub(r"^\s+Expected[^:]*: ", "", ln).strip() for ln in body if re.match(r"^\s+Expected", ln)), None)
    received = next((re.sub(r"^\s+Received[^:]*: ", "", ln).strip() for ln in body if re.match(r"^\s+Received", ln)), None)
    fail_src = next((re.sub(r"^\s+>\s*\d+ \|\s?", "", ln).strip() for ln in body if re.match(r"^\s+>\s*\d+ \|", ln)), None)
    fail_line = next((int(m.group(1)) for ln in body for m in [re.match(r"^\s+>\s*(\d+) \|", ln)] if m), None)
    art = None
    for ln in body:
        m = re.search(r"test-results/([^/\s]+)/", ln)
        if m:
            art = m.group(1)
            break
    strict = [ln.strip() for ln in body if re.match(r"^\s+\d+\) <", ln)]

    primary = next((e for e in errors if e.startswith("Error:")), errors[0] if errors else "")
    # --- mechanical class (error block only; snapshot evidence is recorded separately)
    api_status = None
    if re.search(r"\.status\(\)", text) and received and re.fullmatch(r"\d{3}", received.strip()):
        api_status = int(received.strip())
    elif re.search(r"\.status\(\)", text) and expected and re.fullmatch(r"\d{3}", expected.strip()):
        api_status = int(expected.strip())  # toContain(res.status()) puts the status in "Expected value"
    if BACKEND_RE.search(text) or (api_status is not None and (api_status >= 500 or api_status == 404)):
        cls = "BACKEND"
    elif "strict mode violation" in text or "element(s) not found" in text or (
        re.search(r"(page|locator)\.(click|fill|selectOption|getAttribute|check|press|hover|type|textContent|inputValue): Test timeout", text)
        and re.search(r"- waiting for (locator|getBy)", text)
    ):
        cls = "SELECTOR"
    elif ASSERTION_MATCHERS.search(primary) or (expected is not None and received is not None):
        cls = "ASSERTION"
    else:
        cls = "OTHER"
    return {
        "n": b["n"], "spec": b["spec"], "line": b["line"], "title_path": b["title_path"],
        "class": cls, "error": redact(primary), "all_errors": [redact(e) for e in errors],
        "locator": redact(locator) if locator else None, "expected": expected, "received": received,
        "failing_source": fail_src, "failing_line": fail_line, "strict_matches": strict,
        "artifact_dir": art, "api_status": api_status,
        "api_path": next((m.group(1) for m in re.finditer(r"request\.get\(['\"`]([^'\"`]+)", text)), None),
    }


# ------------------------------------------------------------------ snapshot evidence
def snapshot_signals(snap: str | None) -> dict:
    if snap is None:
        return {"snapshot": "absent"}
    alerts = [a.strip().strip('"') for a in re.findall(r'- alert(?: \[[^\]]*\])*: (.+)', snap)]
    headings = re.findall(r'- heading "([^"]+)"', snap)
    sig = {
        "snapshot": "present",
        "alerts": [redact(a) for a in alerts][:5],
        "headings": headings[:8],
        "is_404": bool(re.search(r'heading "404"|This page could not be found', snap)),
        "fetch_failed": bool(re.search(r"Failed to fetch|fetch failed|ECONNREFUSED|NetworkError", snap, re.I)),
        "runtime_error": bool(re.search(r"Unhandled Runtime Error|Application error|Something went wrong", snap, re.I)),
        "loading_state": bool(re.search(r'\bLoading\b', snap)),
        "chars": len(snap),
    }
    return sig


# ------------------------------------------------------------------ source index
def load_source() -> dict[str, list[str]]:
    out = {}
    for d in SRC_DIRS:
        for p in (UI_ROOT / d).rglob("*"):
            if p.suffix in SRC_EXT and p.is_file() and "__tests__" not in p.parts and ".test." not in p.name:
                try:
                    out[str(p.relative_to(UI_ROOT))] = p.read_text(errors="replace").splitlines()
                except OSError:
                    pass
    return out


STRLIT = re.compile(r"""'([^'\\]{1,200})'|"([^"\\]{1,200})"|`([^`\\]{1,200})`|>([^<>{}]{1,200})<""")


def text_view(ln: str) -> str:
    """String literals + JSX text of a source line: what a user could actually see."""
    parts = [next(g for g in m.groups() if g is not None) for m in STRLIT.finditer(ln)]
    stripped = ln.strip()
    # a bare JSX text line (no code punctuation) counts as visible text
    if stripped and not re.search(r"[=;(){}<>]|^(import|export|const|let|return|//|\*)", stripped):
        parts.append(stripped)
    return " | ".join(parts)


def grep_src(src: dict, pattern: re.Pattern, limit: int = 3, visible: bool = False) -> list[str]:
    hits = []
    for f, lines in src.items():
        for i, ln in enumerate(lines, 1):
            if pattern.search(text_view(ln) if visible else ln):
                hits.append(f"{f}:{i}")
                if len(hits) >= limit:
                    return hits
    return hits


def js_regex_to_py(s: str) -> re.Pattern | None:
    m = re.match(r"^/(.*)/([a-z]*)$", s)
    if not m:
        return None
    flags = re.I if "i" in m.group(2) else 0
    try:
        return re.compile(m.group(1), flags)
    except re.error:
        return None


def selector_terms(locator: str) -> list[dict]:
    """Split a Playwright locator string into searchable terms."""
    terms = []
    for m in re.finditer(r"""data-testid[=*^$~]*["']([^"']+)["']|getByTestId\(['"]([^'"]+)['"]\)""", locator):
        terms.append({"kind": "testid", "value": m.group(1) or m.group(2)})
    for m in re.finditer(r"getByRole\('(\w+)'(?:,\s*\{\s*name:\s*(/[^/]+/[a-z]*|'[^']*'|\"[^\"]*\"))?", locator):
        name = m.group(2)
        terms.append({"kind": "role", "role": m.group(1), "value": name.strip("'\"") if name else None,
                      "regex": bool(name and name.startswith("/"))})
    for m in re.finditer(r"getBy(Text|Placeholder|Label|Title|AltText)\((/[^/]+/[a-z]*|'[^']*'|\"[^\"]*\")", locator):
        v = m.group(2)
        terms.append({"kind": m.group(1).lower(), "value": v.strip("'\""), "regex": v.startswith("/")})
    for m in re.finditer(r"""(?:has-text|text)[=(]["']?([^"')]+)["']?\)?""", locator):
        terms.append({"kind": "text", "value": m.group(1), "regex": False})
    for m in re.finditer(r"""\[(placeholder|aria-label|name|type)[*^$~]?=["']([^"']+)["']\]""", locator):
        terms.append({"kind": m.group(1), "value": m.group(2), "regex": False})
    if not terms:
        for q in re.findall(r"""locator\((['"])(.+?)\1\)""", locator):
            css = q[1]
            for m in re.finditer(r"#([A-Za-z][\w-]+)", css):
                terms.append({"kind": "css-id", "value": m.group(1), "regex": False})
            for m in re.finditer(r"\.([a-z][\w-]{3,})", css):
                terms.append({"kind": "css-class", "value": m.group(1), "regex": False})
    return terms


ALL_TESTIDS_RE = re.compile(r"""data-testid=\{?[`"']([^`"'}]+)[`"']""")


def check_term(t: dict, src: dict, snap: str | None, testid_universe: list[str]) -> dict:
    v = t.get("value")
    res = dict(t)
    if v is None and t["kind"] == "role":
        role = t["role"]
        native = {"status": r"<output\b", "heading": r"<h[1-6]\b", "button": r"<button\b", "textbox": r"<(input|textarea)\b",
                  "combobox": r"<select\b", "link": r"<(a|Link)\b", "dialog": r"<dialog\b", "list": r"<(ul|ol)\b",
                  "listitem": r"<li\b", "table": r"<table\b", "checkbox": r"type=[\"']checkbox", "progressbar": r"<progress\b"}
        pat = re.compile(r"""role=[{]?["'`]""" + re.escape(role) + r"""["'`]""" + (("|" + native[role]) if role in native else ""))
        hits = grep_src(src, pat)
        res.update(source="found" if hits else "missing", source_hits=hits)
        if snap is not None:
            res["snapshot"] = "rendered" if re.search(r"- " + re.escape(role) + r"\b", snap) else "not-rendered"
        return res
    if v is None:
        res.update(source="n/a", snapshot="n/a")
        return res
    if t.get("regex"):
        pat = js_regex_to_py(v) or re.compile(re.escape(v), re.I)
    elif t["kind"] == "testid":
        pat = re.compile(r"""(?:data-testid|testId|testid)["']?\s*[=:]\s*\{?\s*[`"']""" + re.escape(v) + r"""[`"']""")
    else:
        pat = re.compile(re.escape(v), re.I)
    hits = grep_src(src, pat, visible=t["kind"] not in ("testid", "css-id", "css-class"))
    res["source"] = "found" if hits else "missing"
    res["source_hits"] = hits
    if not hits:
        if t["kind"] == "testid":
            cands = difflib.get_close_matches(v, testid_universe, n=2, cutoff=0.6)
            # dynamic testids built with template literals: data-testid={`foo-${id}`}
            dyn = [u for u in testid_universe if "${" in u and v.startswith(u.split("${")[0]) and u.split("${")[0]]
            cands = cands + [d for d in dyn if d not in cands]
        else:
            cands = []
            words = [w for w in re.findall(r"[A-Za-z]{4,}", v)]
            for w in words[:2]:
                h = grep_src(src, re.compile(re.escape(w), re.I), limit=2, visible=True)
                cands.extend(f"{w}@{x}" for x in h)
        if cands:
            res["source"] = "renamed-candidate"
            res["candidates"] = [c if "@" in c or ":" in c else f"{c}@" + ",".join(grep_src(src, re.compile(re.escape(c.split('${')[0])), 1)) for c in cands][:3]
    if snap is not None and t["kind"] in ("role", "text", "placeholder", "label"):
        if t["kind"] == "role":
            rows = re.findall(r"- " + re.escape(t["role"]) + r' "([^"]*)"', snap)
            res["snapshot"] = "rendered" if any(pat.search(r) for r in rows) else "not-rendered"
            if res["snapshot"] == "not-rendered" and rows:
                res["snapshot_same_role"] = rows[:4]
        else:
            res["snapshot"] = "rendered" if pat.search(snap) else "not-rendered"
    return res


# ------------------------------------------------------------------ git dates
def git_date(path: str) -> str | None:
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", path], cwd=UI_ROOT,
                             capture_output=True, text=True, check=False).stdout.strip()
        return out or None
    except OSError:
        return None


def page_under_test(spec_text: str, test_line: int) -> str | None:
    """Nearest preceding page.goto(...) (the test body or its beforeEach)."""
    lines = spec_text.splitlines()
    gotos = [(i + 1, m.group(1)) for i, ln in enumerate(lines)
             for m in [re.search(r"goto\(\s*[`'\"](?:\$\{base\})?([^`'\"]+)[`'\"]", ln)] if m]
    before = [g for g in gotos if g[0] <= test_line + 40]
    # prefer a goto inside the test body (after its first line), else the last one before it
    inside = [g for g in gotos if test_line <= g[0] <= test_line + 40]
    pick = inside[0] if inside else (before[-1] if before else (gotos[0] if gotos else None))
    return pick[1] if pick else None


def route_to_dir(route: str) -> str | None:
    route = route.split("?")[0].rstrip("/")
    route = re.sub(r"\$\{[^}]+\}", "[slug]", route)
    base = UI_ROOT / "app"
    if not route:
        return "app/page.tsx"
    parts = route.strip("/").split("/")
    cur = base
    for p in parts:
        nxt = cur / p
        if nxt.is_dir():
            cur = nxt
            continue
        dyn = [d for d in cur.iterdir() if d.is_dir() and d.name.startswith("[")]
        groups = [d for d in cur.iterdir() if d.is_dir() and d.name.startswith("(") and (d / p).is_dir()]
        if groups:
            cur = groups[0] / p
        elif dyn:
            cur = dyn[0]
        else:
            return None
    return str(cur.relative_to(UI_ROOT))


def decide(row: dict) -> tuple[str, str, str]:
    """(stale y/n/unknown, proposed_action, reason) — deterministic rules, documented in the MD."""
    sig = row["snapshot_signals"]
    terms = row["selector_checks"]
    cls = row["class"]
    if row["page_dir"] is None:
        return "y", "update-to-current", "route under test has no app/ directory (page removed or renamed)"
    if sig.get("is_404"):
        return "y", "update-to-current", "page rendered Next.js 404 — route/slug no longer exists"
    if cls == "BACKEND":
        return "n", "tag-backend", "test itself requires a live backend (env/network precondition)"
    if row.get("api_status") == 401 and row.get("api_route_has_401"):
        return "y", "update-to-current", (f"{row.get('api_path')} now returns 401 (auth gate in {row.get('api_route_file')}, "
                                         f"last touched {row.get('api_route_last_commit')}); spec predates it")
    heading_miss = [t for t in terms if t.get("kind") == "role" and t.get("role") == "heading"
                    and t.get("snapshot") == "not-rendered" and t.get("snapshot_same_role")]
    if heading_miss:
        return "y", "update-to-current", ("rendered page headings " + str(heading_miss[0]["snapshot_same_role"])
                                         + " do not match " + str(heading_miss[0]["value"]))
    if cls == "OTHER":
        return "unknown", "real-regression-investigate" if not sig.get("fetch_failed") else "mock-backend", "unclassified failure"
    missing = [t for t in terms if t.get("source") == "missing"]
    renamed = [t for t in terms if t.get("source") == "renamed-candidate"]
    found = [t for t in terms if t.get("source") == "found"]
    not_rendered_but_found = [t for t in found if t.get("snapshot") == "not-rendered"]
    if cls == "SELECTOR" and row["strict_matches"]:
        return "y", "update-to-current", "strict-mode violation: selector too broad for the current page"
    if missing and not found:
        return "y", "update-to-current", "selector/text absent from all current UI source"
    if renamed and not found:
        return "y", "update-to-current", "selector absent; near-match exists in source (renamed candidate)"
    if found and sig.get("fetch_failed"):
        return "n", "mock-backend", "selector exists in source; page shows fetch failure (backend absent in CI)"
    if found and not_rendered_but_found:
        return "unknown", "mock-backend", "selector exists in source but was not rendered; data-dependent render suspected"
    if cls == "ASSERTION":
        if sig.get("fetch_failed"):
            return "n", "mock-backend", "value mismatch on a page whose data fetch failed"
        return "unknown", "real-regression-investigate", "value mismatch with no backend signal on the page"
    if found:
        return "unknown", "mock-backend" if sig.get("fetch_failed") or sig.get("loading_state") else "real-regression-investigate", \
            "selector exists in source; render condition not determined from snapshot"
    return "unknown", "real-regression-investigate", "no selector term extracted"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    lines = clean_log(Path(a.log).read_text(errors="replace"))
    summary_failed = next((int(m.group(1)) for ln in lines for m in [re.match(r"^\s+(\d+) failed\s*$", ln)] if m), None)
    summary_passed = next((int(m.group(1)) for ln in lines for m in [re.match(r"^\s+(\d+) passed", ln)] if m), None)
    blocks = parse_blocks(lines)
    if summary_failed is None or len(blocks) != summary_failed:
        print(f"COULD-NOT-MEASURE: parsed {len(blocks)} blocks vs summary {summary_failed}", file=sys.stderr)
        return 3

    src = load_source()
    testid_universe = sorted({m.group(1) for ls in src.values() for ln in ls for m in ALL_TESTIDS_RE.finditer(ln)})
    spec_cache: dict[str, str] = {}
    rows = []
    art_root = Path(a.artifacts)
    for b in blocks:
        r = analyse_block(b)
        snap = None
        if r["artifact_dir"]:
            p = art_root / r["artifact_dir"] / "error-context.md"
            if p.exists():
                snap = p.read_text(errors="replace")
        r["snapshot_signals"] = snapshot_signals(snap)
        r["selector_checks"] = [check_term(t, src, snap, testid_universe) for t in selector_terms(r["locator"] or "")]
        # expected text of assertion failures is also a staleness term
        if r["class"] == "ASSERTION" and r["expected"] and re.match(r'^["/]', r["expected"]) and len(r["expected"].strip('"')) >= 3:
            ev = r["expected"]
            t = {"kind": "expected-text", "value": ev.strip('"'), "regex": ev.startswith("/")}
            r["selector_checks"].append(check_term(t, src, snap, testid_universe))
        spec_path = f"{b['spec']}"
        spec_cache.setdefault(spec_path, (UI_ROOT / spec_path).read_text())
        route = page_under_test(spec_cache[spec_path], b["line"])
        r["route"] = route
        r["page_dir"] = route_to_dir(route) if route else None
        r["spec_last_commit"] = git_date(spec_path)
        r["page_last_commit"] = git_date(r["page_dir"]) if r["page_dir"] else None
        if r["api_status"] is not None:
            if not r["api_path"]:
                body = "\n".join(spec_cache[spec_path].splitlines()[b["line"] - 1:b["line"] + 12])
                m = re.search(r"request\.get\(['\"`]([^'\"`]+)", body)
                r["api_path"] = m.group(1) if m else None
            if r["api_path"]:
                rf = UI_ROOT / "app" / r["api_path"].lstrip("/") / "route.ts"
                if rf.exists():
                    rel = str(rf.relative_to(UI_ROOT))
                    r["api_route_file"] = rel
                    r["api_route_has_401"] = "status: 401" in rf.read_text()
                    r["api_route_last_commit"] = git_date(rel)
        r["stale"], r["proposed_action"], r["reason"] = decide(r)
        rows.append(r)

    out = {
        "schema": "pmoves.e2e_reconcile.v1",
        "lane": "test/e2e-reconcile-open-jev",
        "phase": 1,
        "source_run": {"run_id": a.run_id, "job_id": a.job_id, "failed": summary_failed, "passed": summary_passed},
        "source_tree": subprocess.run(["git", "rev-parse", "HEAD"], cwd=UI_ROOT, capture_output=True, text=True).stdout.strip(),
        "failures": rows,
    }
    Path(a.out).write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {len(rows)} rows -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
