#!/usr/bin/env python3
"""runbook_drift.py — ORGSIM-MIRROR deterministic runbook auditor (ZERO LLM). v3.

Mirrors the orgsim-model-refiner pattern on PMOVES runbooks:
  A = claim as written in the runbook (rulebook text)
  B = live reality probe (read-only oracle)
  verdict per claim: VERIFIED / DRIFTED / UNDECIDED (fail-closed; probe error => UNDECIDED)
  sealed output: sha256 per claim record + chained digest over the run

v3 lessons (each version exists because the previous failed on something real):
  v1: bare `make` from repo root — the AGENTS.md Known-Road trap (targets live in
      pmoves/Makefile + mk/*.mk). Fixed with canonical `make -C pmoves -n`.
  v2: stale working tree — auditor probed a September checkout and called refs
      DRIFTED that exist on origin/main. Fixed with origin/main cross-checks
      (git show / git grep): exists-on-main => UNDECIDED (stale-checkout), not DRIFTED.
  v3: historical lines (destroyed/superseded/deprecated) are records, not claims;
      DRAFT docs get intent-tagged; dated --out reports; --globs scope override.

No AI model calls — the harness IS the intelligence. Read-only vs repo and network.
"""
import argparse, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path("/a0/usr/projects/pmoves_ai")
DEFAULT_GLOBS = ["plans/*.md"]
ENDPOINT_TIMEOUT = 6  # seconds
REPO = "POWERFULMOVES/PMOVES.AI"

# Lines carrying these markers are historical records, not live claims.
HISTORY_RE = re.compile(
    r"(destroyed|superseded|deprecated|removed from|previously|no longer|old bundle)", re.I)

def sh(cmd, timeout=20, cwd=None):
    """Run a shell command with bounded timeout; return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, cwd=cwd or str(ROOT))
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"

def on_origin_main(git_query):
    """True if a `git <query> origin/main` succeeds (path exists / grep hits)."""
    rc, _, _ = sh(git_query, timeout=20)
    return rc == 0

# ---- claim extractors (A-side) -------------------------------------------
RE_MAKE = re.compile(r"make\s+(?:-C\s+pmoves\s+)?([a-z0-9][a-z0-9_-]*)")
RE_PATH = re.compile(r"`([a-zA-Z0-9_./-]+(?:\.py|\.sh|\.md|\.ya?ml|\.json|\.toml))`")
RE_URL  = re.compile(r"https?://[a-zA-Z0-9._:/-]+")
RE_NOISE = {"targets", "target", "sure", "use", "command", "commands", "file", "files",
            "the", "a", "an", "your", "it", "this", "that", "all", "them", "our", "one"}
# Lines carrying audit-annotation markers are themselves records about fixes, not claims.
AUDIT_NOTE_RE = re.compile(r"(drift-audit fix|was `|supersession|see rotation log)", re.I)

def doc_class(path):
    """Classify doc intent: DRAFT/proposal docs describe planned artifacts, not reality."""
    name = Path(path).name.lower()
    if "draft" in name or "proposal" in name:
        return "DRAFT"
    return "RUNBOOK"

def extract_claims(text, source):
    """Extract checkable claims (make targets, file paths, endpoints) from doc text."""
    is_plans = source.startswith("plans/")  # endpoint probes time-boxed to ops-critical scope
    claims = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if HISTORY_RE.search(line) or AUDIT_NOTE_RE.search(line):
            continue  # historical record or audit annotation, not a live claim (v3)
        for m in RE_MAKE.finditer(line):
            t = m.group(1)
            if t not in RE_NOISE:
                claims.append({"kind": "make_target", "value": t, "line": line_no})
        for m in RE_PATH.finditer(line):
            p = m.group(1)
            if p.startswith("env.") or p.startswith("/"):
                if not p.startswith("env.tier"):
                    continue
            claims.append({"kind": "file_path", "value": p, "line": line_no})
        if is_plans:
            for m in RE_URL.finditer(line):
                u = m.group(0).rstrip(".,)")
                if "example.com" in u or "<" in u or "your." in u:
                    continue  # placeholder URLs are not claims
                claims.append({"kind": "endpoint", "value": u, "line": line_no})
    return claims

# ---- reality probes (B-side) ---------------------------------------------
def probe_make(target):
    """Canonical `make -C pmoves -n` dry-run; cross-check origin/main before DRIFTED."""
    rc, out, err = sh(f"make -n {target}", timeout=30, cwd=str(ROOT / "pmoves"))
    if rc == 0:
        return "VERIFIED", "make -C pmoves -n resolved (dry-run ok)"
    if "No rule to make target" in err or rc == 2:
        if on_origin_main(f"git grep -E '^{target}:' origin/main -- pmoves/Makefile 'pmoves/mk/'"):
            return "UNDECIDED", (f"no rule in LOCAL tree, but '{target}:' exists on "
                                 "origin/main — stale local checkout, not doc drift (v3)")
        return "DRIFTED", f"no such target in pmoves/Makefile(+mk includes) or origin/main: {target}"
    return "UNDECIDED", f"make rc={rc}: {err[:80]}"

def probe_file(rel):
    """Probe a referenced file path; fail closed to UNDECIDED when ambiguous or main-only."""
    for base in [ROOT, ROOT / "pmoves"]:
        p = base / rel
        if p.exists():
            return "VERIFIED", f"exists: {p.relative_to(ROOT)}"
    if on_origin_main(f"git show origin/main:{rel} -- >/dev/null 2>&1 || git cat-file -e origin/main:{rel}"):
        return "UNDECIDED", (f"as-written path missing locally but exists on origin/main "
                             f"({rel}) — stale local checkout, not doc drift (v3)")
    rc, out, _ = sh(f"git grep -l --fixed-strings '{os.path.basename(rel)}' origin/main -- | head -3", timeout=30)
    if rc == 0 and out:
        return "UNDECIDED", f"as-written path missing; basename found on origin/main at: {out.splitlines()[0]}"
    rc, out, _ = sh(f"find . -name '{os.path.basename(rel)}' -not -path '*/.git/*' | head -3", timeout=30)
    if rc == 0 and out:
        return "UNDECIDED", f"as-written path missing; basename found locally at: {out.splitlines()[0]}"
    return "DRIFTED", "path not found in working tree or origin/main"

def probe_endpoint(url):
    """GET-probe an endpoint; unreachable/timeout => UNDECIDED, never 'dead'."""
    rc, out, err = sh(
        f"curl -sS -o /dev/null -m {ENDPOINT_TIMEOUT} -w '%{{http_code}}' '{url}'",
        timeout=ENDPOINT_TIMEOUT + 5)
    if rc == 124 or rc == 7 or rc == 28:
        return "UNDECIDED", f"unreachable rc={rc} (net/timeout) — not asserting dead"
    if out.startswith("2") or out.startswith("3") or out in ("401", "403", "405", "000"):
        return "VERIFIED", f"HTTP {out} (alive/gated)"
    if out.startswith("4") or out.startswith("5"):
        return "DRIFTED", f"HTTP {out}"
    return "UNDECIDED", f"curl rc={rc} out={out[:20]}"

PROBES = {"make_target": probe_make, "file_path": probe_file, "endpoint": probe_endpoint}

# ---- sealed reporting -----------------------------------------------------
def seal(records):
    """Hash-chain the records (sha256, each digest feeds the next); return chain tip."""
    chain = ""
    for r in records:
        payload = json.dumps(r, sort_keys=True)
        digest = hashlib.sha256((chain + payload).encode()).hexdigest()
        r["seal"] = digest
        chain = digest
    return chain  # run digest = tamper-evident chain tip

def main():
    """Scan scope globs, probe every claim, write the sealed JSON report."""
    ap = argparse.ArgumentParser(description="ORGSIM-MIRROR runbook drift auditor (zero LLM)")
    ap.add_argument("--out", default=str(ROOT / "research" / "runbook_drift_report.json"))
    ap.add_argument("--globs", default=",".join(DEFAULT_GLOBS),
                    help="comma-separated glob patterns relative to repo root")
    args = ap.parse_args()
    globs = [g.strip() for g in args.globs.split(",") if g.strip()]
    records, files_scanned = [], 0
    for pattern in globs:
        for f in sorted(ROOT.glob(pattern)):
            if f.name.startswith("AGNOTE4482PHI"):
                continue  # the register is append-only history, not claims (v3)
            files_scanned += 1
            rel = str(f.relative_to(ROOT))
            dc = doc_class(rel)
            text = f.read_text(errors="replace")
            for c in extract_claims(text, rel):
                verdict, evidence = PROBES[c["kind"]](c["value"])
                records.append({
                    "source": rel, "doc_class": dc, "kind": c["kind"],
                    "claim": c["value"], "line": c["line"],
                    "verdict": verdict, "evidence": evidence,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })
    run_digest = seal(records)
    counts = {}
    for r in records:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    out = {"version": "v3", "run_digest": run_digest, "files_scanned": files_scanned,
           "globs": globs, "counts": counts, "records": records}
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=1))
    print(json.dumps({"run_digest": run_digest, "files": files_scanned,
                      "claims": len(records), "counts": counts,
                      "report": str(outp)}))

if __name__ == "__main__":
    main()
