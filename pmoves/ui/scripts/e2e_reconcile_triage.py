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
    alerts = []
    lines = snap.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*)- alert\b[^:]*(?::\s*(.*))?$", ln)
        if not m:
            continue
        if m.group(2):
            alerts.append(m.group(2).strip().strip('"'))
            continue
        ind = len(m.group(1))
        kids = []
        for nxt in lines[i + 1:i + 6]:
            if len(nxt) - len(nxt.lstrip()) <= ind:
                break
            km = re.search(r"\]: (.+)$|^\s*- text: (.+)$", nxt)
            if km and "button" not in nxt:
                kids.append((km.group(1) or km.group(2)).strip().strip('"'))
        if kids:
            alerts.append(" / ".join(kids))
    headings = re.findall(r'- heading "([^"]+)"', snap)
    sig = {
        "snapshot": "present",
        "alerts": [redact(a) for a in alerts][:5],
        "headings": headings[:8],
        "is_404": bool(re.search(r'heading "404"|This page could not be found', snap)),
        "fetch_failed": bool(re.search(r"Failed to fetch|fetch failed|ECONNREFUSED|NetworkError", snap, re.I)),
        # backend-absent markers observed in CI snapshots: an alert carrying an auth/network error,
        # or a connection-status badge reading "error" beside the page heading
        "backend_signal": bool(re.search(r"Failed to fetch|fetch failed|ECONNREFUSED|NetworkError|Invalid JWT|JWT|Unauthori[sz]ed|not configured", " ".join(alerts), re.I)
                               or re.search(r'Failed to fetch|- generic \[ref=e\d+\]: error$', snap, re.M)),
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
    hits = grep_src(src, pat, visible=t["kind"] not in ("testid", "css-id", "css-class", "js-global"))
    res["source"] = "found" if hits else "missing"
    res["source_hits"] = hits
    if not hits:
        if t["kind"] == "testid":
            cands = difflib.get_close_matches(v, testid_universe, n=2, cutoff=0.6)
            # dynamic testids built with template literals: data-testid={`foo-${id}`}
            dyn = [u for u in testid_universe if "${" in u and v.startswith(u.split("${")[0]) and u.split("${")[0]]
            cands = cands + [d for d in dyn if d not in cands]
            # same token used as a plain id/name/htmlFor: the element exists, the spec targets the wrong attribute
            idhits = grep_src(src, re.compile(r"""\b(?:id|name|htmlFor)=\{?["'`]""" + re.escape(v) + r"""["'`]"""), limit=2)
            cands = [f"id/name={v}@{h}" for h in idhits] + cands
        elif t["kind"] in ("js-global", "css-id", "css-class"):
            cands = []
        else:
            cands = []
            words = [w for w in re.findall(r"[A-Za-z]{4,}", v)]
            for w in words[:2]:
                h = grep_src(src, re.compile(re.escape(w), re.I), limit=2, visible=True)
                cands.extend(f"{w}@{x}" for x in h)
        if cands:
            res["source"] = "renamed-candidate"
            res["candidates"] = [c if "@" in c or ":" in c else f"{c}@" + ",".join(grep_src(src, re.compile(re.escape(c.split('${')[0])), 1)) for c in cands][:3]
    if res["source"] != "found" and t["kind"] in ("testid", "text", "placeholder", "label", "css-id", "js-global") and v and not t.get("regex"):
        res["ui_history"] = ui_history(v, t["kind"])
    if snap is not None and t["kind"] in ("role", "text", "placeholder", "label"):
        if t["kind"] == "role":
            rows = re.findall(r"- " + re.escape(t["role"]) + r' "([^"]*)"', snap)
            res["snapshot"] = "rendered" if any(pat.search(r) for r in rows) else "not-rendered"
            if res["snapshot"] == "not-rendered" and rows:
                res["snapshot_same_role"] = rows[:4]
        else:
            res["snapshot"] = "rendered" if pat.search(snap) else "not-rendered"
    return res


_HIST: dict[str, str] = {}


def ui_history(term: str, kind: str = "text") -> str:
    """Did this term EVER exist in UI source on any ref? Distinguishes drift from never-implemented."""
    key = f"{kind}:{term}"
    if key not in _HIST:
        # testids: match the attribute, not any string that happens to equal it (e.g. an API path)
        sel = ["-G", r"testid.{0,8}" + re.escape(term)] if kind == "testid" else ["-S", term]
        out = subprocess.run(["git", "log", "--all", "--format=%h %cs", *sel, "--", *SRC_DIRS],
                             cwd=UI_ROOT, capture_output=True, text=True, check=False).stdout.split("\n")
        out = [o for o in out if o.strip()]
        _HIST[key] = "never-in-ui-source" if not out else f"removed-or-moved (last change {out[0]}; first {out[-1]})"
    return _HIST[key]


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


# Agent inspection (B850-CLAUDE, 2026-09-28): rows the mechanical rules could not settle, each
# with the source evidence read by hand. Applied as a separate layer; mechanical_* fields are kept.
INSPECTION = {
    ("e2e/chat.spec.ts", "provides access to model selection"): (
        "y", "update-to-current",
        "chat page renders an unnamed AGENT selector <select> (app/dashboard/chat/page.tsx:339; options Agent Zero/"
        "Archon/...) and no model combobox or settings button; the controls are static, so the JWT alert is not the cause"),
    ("e2e/chat.spec.ts", "allows Shift+Enter for new lines without sending"): (
        "y", "update-to-current",
        "message field is a single-line <input id=chatMessage> (app/dashboard/chat/page.tsx:350), which cannot hold a "
        "newline; git log --all -S'<textarea' -- app/dashboard/chat is empty, so it was never multi-line"),
    ("e2e/chat.spec.ts", "clears input after sending"): (
        "n", "mock-backend",
        "by design the input is cleared only when send succeeds (app/dashboard/chat/page.tsx:220-222 'Only clear input "
        "after successful send'); /api/chat/send fails without Supabase"),
    ("e2e/services-health.spec.ts", "displays service endpoint information"): (
        "y", "update-to-current",
        "service page is a server component rendering the markdown Service Guide (no client fetch); the first <code> "
        "is the slug ('agent-zero'), the spec assumes it is a URL"),
    ("e2e/services-health.spec.ts", "shows service-specific metrics"): (
        "y", "update-to-current",
        "page renders the markdown Service Guide branch; the <dl> the spec looks for exists only in CatalogFallback "
        "(app/dashboard/services/[service]/page.tsx:61); no backend involved"),
    ("e2e/services-health.spec.ts", "Hi-RAG v2"): (
        "y", "update-to-current",
        "slug 'hirag-v2' is not in lib/services.ts or lib/serviceCatalog.ts (404); nearest current slug is "
        "'hi-rag-gateway-v2' (lib/serviceCatalog.ts:514)"),
}


def inspection_for(row: dict):
    for (spec, needle), val in INSPECTION.items():
        if row["spec"] == spec and needle in row["title_path"]:
            return val
    return None


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
    if cls == "OTHER" and any(t.get("kind") == "js-global" and t.get("source") == "missing" for t in terms):
        g = next(t for t in terms if t.get("kind") == "js-global")
        return "y", "update-to-current", f"waits for window.{g['value']}, absent from current source ({g.get('ui_history')})"
    if cls == "OTHER":
        return "unknown", "real-regression-investigate" if not sig.get("backend_signal") else "mock-backend", "unclassified failure"
    missing = [t for t in terms if t.get("source") == "missing"]
    renamed = [t for t in terms if t.get("source") == "renamed-candidate"]
    found = [t for t in terms if t.get("source") == "found"]
    not_rendered_but_found = [t for t in found if t.get("snapshot") == "not-rendered"]
    if terms and all(t.get("test_data") for t in terms):
        if sig.get("backend_signal"):
            return "n", "mock-backend", "waits for spec-typed test data to round-trip; page shows backend-absent signal " + str(sig.get("alerts"))
        return "unknown", "mock-backend", "waits for spec-typed test data to round-trip through a backend"
    if cls == "SELECTOR" and row["strict_matches"]:
        return "y", "update-to-current", "strict-mode violation: selector too broad for the current page"
    if missing and not found:
        return "y", "update-to-current", "selector/text absent from all current UI source"
    if renamed and not found:
        return "y", "update-to-current", "selector absent; near-match exists in source (renamed candidate)"
    if found and sig.get("backend_signal"):
        return "n", "mock-backend", "selector exists in source; page shows backend-absent signal " + str(sig.get("alerts"))
    if found and not_rendered_but_found:
        return "unknown", "mock-backend", "selector exists in source but was not rendered; data-dependent render suspected"
    if cls == "ASSERTION":
        if sig.get("backend_signal"):
            return "n", "mock-backend", "value mismatch on a page showing a backend-absent signal " + str(sig.get("alerts"))
        return "unknown", "real-regression-investigate", "value mismatch with no backend signal on the page"
    if found:
        return "unknown", "mock-backend" if sig.get("backend_signal") or sig.get("loading_state") else "real-regression-investigate", \
            "selector exists in source; render condition not determined from snapshot"
    return "unknown", "real-regression-investigate", "no selector term extracted"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", help="also render the ground-truth table as markdown")
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
        spec_path = f"{b['spec']}"
        spec_cache.setdefault(spec_path, (UI_ROOT / spec_path).read_text())
        spec_lines = spec_cache[spec_path].splitlines()
        body_txt = "\n".join(spec_lines[max(0, b["line"] - 1):b["line"] + 40])
        # strings the test itself types/defines are test data, not UI copy: never a staleness term
        test_data = set(re.findall(r"""(?:fill|type)\(\s*['"`]([^'"`]+)['"`]""", body_txt)) | \
            set(re.findall(r"""const \w+\s*=\s*['"`]([^'"`]+)['"`]""", body_txt))
        terms = selector_terms(r["locator"] or "")
        for g in re.findall(r"\(window as any\)\.(\w+)|window\.(__\w+)", r["failing_source"] or ""):
            terms.append({"kind": "js-global", "value": g[0] or g[1], "regex": False})
        checks = []
        for t in terms:
            if t.get("value") in test_data:
                checks.append(dict(t, source="n/a (test data typed by the spec)", test_data=True))
            else:
                checks.append(check_term(t, src, snap, testid_universe))
        r["selector_checks"] = checks
        # expected text of assertion failures is also a staleness term
        if r["class"] == "ASSERTION" and r["expected"] and re.match(r'^["/]', r["expected"]) and len(r["expected"].strip('"')) >= 3:
            ev = r["expected"]
            t = {"kind": "expected-text", "value": ev.strip('"'), "regex": ev.startswith("/")}
            r["selector_checks"].append(check_term(t, src, snap, testid_universe))
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
                rf = UI_ROOT / "app" / r["api_path"].split("?")[0].lstrip("/") / "route.ts"
                if rf.exists():
                    rel = str(rf.relative_to(UI_ROOT))
                    r["api_route_file"] = rel
                    body = rf.read_text()
                    m = re.search(r"from ['\"](\.{1,2}/[^'\"]+/route)['\"]", body)
                    if m:  # thin alias re-exporting another handler
                        tgt = (rf.parent / (m.group(1) + ".ts")).resolve()
                        if tgt.exists():
                            body += tgt.read_text()
                            r["api_route_file"] = f"{rel} -> {tgt.relative_to(UI_ROOT)}"
                    r["api_route_has_401"] = "status: 401" in body
                    r["api_route_last_commit"] = git_date(rel)
        r["stale"], r["proposed_action"], r["reason"] = decide(r)
        r["mechanical_stale"], r["mechanical_action"] = r["stale"], r["proposed_action"]
        insp = inspection_for(r)
        r["inspection"] = None
        if insp:
            r["stale"], r["proposed_action"], r["inspection"] = insp
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
    if a.md:
        Path(a.md).write_text(render_md(out))
        print(f"wrote {a.md}")
    return 0


def _cell(x) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def render_md(out: dict) -> str:
    from collections import Counter
    F = out["failures"]
    L = [f"# E2E reconcile — phase 1 ground truth ({len(F)} failures)", "",
         f"Source: UI Tests run {out['source_run']['run_id']}, job {out['source_run']['job_id']} "
         f"({out['source_run']['failed']} failed / {out['source_run']['passed']} passed). Judged against tree "
         f"`{out['source_tree'][:10]}`. Generated by `pmoves/ui/scripts/e2e_reconcile_triage.py`; machine-readable twin: "
         "`RECONCILE-2026-09-28.json` (schema `pmoves.e2e_reconcile.v1`).", "",
         "`class` is mechanical from the error text only. `stale`/`action` come from deterministic rules over the "
         "ARIA snapshot + current source + git history; rows marked (I) were settled by agent inspection, with the "
         "mechanical verdict kept in the JSON as `mechanical_stale`/`mechanical_action`.", "",
         "## Counts per class", "", "| class | n |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in Counter(r["class"] for r in F).most_common()]
    L += ["", "## Counts per stale / action", "", "| stale | action | n |", "|---|---|---|"]
    L += [f"| {k[0]} | {k[1]} | {v} |" for k, v in Counter((r["stale"], r["proposed_action"]) for r in F).most_common()]
    hist = Counter(t.get("ui_history", "")[:18] for r in F for t in r["selector_checks"] if t.get("ui_history"))
    L += ["", f"Missing selector terms checked against UI-source history on all refs: {dict(hist)}", ""]
    L += ["## Counts per spec", "", "| spec | failed | SELECTOR | ASSERTION | BACKEND | OTHER | stale y | stale n |",
          "|---|---|---|---|---|---|---|---|"]
    for spec in sorted({r["spec"] for r in F}):
        R = [r for r in F if r["spec"] == spec]
        c = Counter(r["class"] for r in R)
        L.append(f"| {spec} | {len(R)} | {c['SELECTOR']} | {c['ASSERTION']} | {c['BACKEND']} | {c['OTHER']} | "
                 f"{sum(r['stale'] == 'y' for r in R)} | {sum(r['stale'] == 'n' for r in R)} |")
    L += ["", "## Ground truth", "", "| # | spec:line | test | class | evidence | stale | action |", "|---|---|---|---|---|---|---|"]
    for r in F:
        ev = []
        for t in r["selector_checks"][:2]:
            e = f"{t.get('kind')} `{t.get('value') or t.get('role')}` src={t.get('source')}"
            if t.get("snapshot"):
                e += f" dom={t['snapshot']}"
            if t.get("ui_history"):
                e += f" hist={t['ui_history'].split(' (')[0]}"
            if t.get("candidates"):
                e += f" cand={t['candidates'][0]}"
            ev.append(e)
        why = r["inspection"] or r["reason"]
        mark = " (I)" if r["inspection"] else ""
        L.append(f"| {r['n']} | {r['spec'].replace('e2e/', '')}:{r['line']} | {_cell(r['title_path'].split(' › ')[-1])} | "
                 f"{r['class']} | {_cell('; '.join(ev) or r['error'][:90])} — {_cell(why)} | {r['stale']}{mark} | {r['proposed_action']} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
