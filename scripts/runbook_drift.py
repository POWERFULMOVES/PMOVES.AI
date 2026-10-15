#!/usr/bin/env python3
"""runbook_drift.py — ORGSIM-MIRROR deterministic runbook auditor (ZERO LLM).

Mirrors the orgsim-model-refiner pattern on PMOVES runbooks:
  A = claim as written in the runbook (rulebook text)
  B = live reality probe (read-only oracle)
  verdict per claim: VERIFIED / DRIFTED / UNDECIDED (fail-closed; probe error => UNDECIDED)
  sealed output: sha256 per claim record + chained digest over the run

No AI model calls — the harness IS the intelligence (per the Aragon pattern:
core learner makes no LLM calls). Read-only against the repo and network.
"""
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path("/a0/usr/projects/pmoves_ai")
SCOPE_GLOBS = ["plans/*.md"]
ENDPOINT_TIMEOUT = 6  # seconds

def sh(cmd, timeout=20, cwd=None):
    """Run a shell command with bounded timeout; return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, cwd=cwd or str(ROOT))
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"

# ---- claim extractors (A-side) -------------------------------------------
RE_MAKE = re.compile(r"make\s+(?:-C\s+pmoves\s+)?([a-z0-9][a-z0-9_-]*)")
RE_PATH = re.compile(r"`([a-zA-Z0-9_./-]+(?:\.py|\.sh|\.md|\.ya?ml|\.json|\.toml))`")
RE_URL  = re.compile(r"https?://[a-zA-Z0-9._:/-]+")
RE_NOISE = {"targets", "target", "sure", "use", "command", "commands", "file", "files"}

def extract_claims(text):
    """Extract checkable claims (make targets, file paths, endpoints) from doc text."""
    claims = []
    for m in RE_MAKE.finditer(text):
        t = m.group(1)
        if t not in RE_NOISE:
            claims.append({"kind": "make_target", "value": t})
    for m in RE_PATH.finditer(text):
        p = m.group(1)
        if p.startswith("env.") or p.startswith("/"):  # env files + abs paths skipped
            if not p.startswith("env.tier"):
                continue
        claims.append({"kind": "file_path", "value": p})
    for m in RE_URL.finditer(text):
        u = m.group(0).rstrip(".,)")
        if "example.com" in u or "<" in u or "your." in u:
            continue  # placeholder URLs are not claims
        claims.append({"kind": "endpoint", "value": u})
    return claims

# ---- reality probes (B-side) ---------------------------------------------
def probe_make(target):
    """Probe a make target via canonical `make -C pmoves -n` dry-run (Known Road)."""
    # canonical road: targets live in pmoves/Makefile + pmoves/mk/*.mk (AGENTS.md Known Roads:
    # root-Makefile greps miss them; secrets-funnel was duplicated twice by agents who skipped this)
    rc, out, err = sh(f"make -n {target}", timeout=30, cwd=str(ROOT / "pmoves"))
    if rc == 0:
        return "VERIFIED", "make -C pmoves -n resolved (dry-run ok)"
    if "No rule to make target" in err or rc == 2:
        return "DRIFTED", f"no such target in pmoves/Makefile(+mk includes): {target}"
    return "UNDECIDED", f"make rc={rc}: {err[:80]}"

def probe_file(rel):
    """Probe a referenced file path; fail closed to UNDECIDED when found elsewhere."""
    # candidates: repo-root relative, pmoves/ relative
    for base in [ROOT, ROOT / "pmoves"]:
        p = base / rel
        if p.exists():
            return "VERIFIED", f"exists: {p.relative_to(ROOT)}"
    rc, out, _ = sh(f"find . -name '{os.path.basename(rel)}' -not -path '*/.git/*' | head -3", timeout=30)
    if rc == 0 and out:
        # fail-closed: the file exists somewhere but NOT where a reader would look.
        # That is a real hazard, but whether the RUNBOOK or our base assumption is wrong
        # is not decidable by probe => UNDECIDED, never a confident DRIFT call.
        return "UNDECIDED", f"as-written path missing; basename found at: {out.splitlines()[0]}"
    return "DRIFTED", "path not found anywhere in tree"

def probe_endpoint(url):
    """GET-probe an endpoint; unreachable/timeout => UNDECIDED, never 'dead'."""
    rc, out, err = sh(
        f"curl -sS -o /dev/null -m {ENDPOINT_TIMEOUT} -w '%{{http_code}}' '{url}'",
        timeout=ENDPOINT_TIMEOUT + 5)
    if rc == 124 or rc == 7 or rc == 28:
        return "UNDECIDED", f"unreachable rc={rc} (net/timeout) — not asserting dead"
    if out.startswith("2") or out.startswith("3") or out in ("401", "403", "405", "000"):
        # 401/403/405 = endpoint alive, auth/method-gated; 000 w/ rc 0 = odd but responded
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
    """Scan SCOPE_GLOBS, probe every claim, write the sealed JSON report."""
    records, files_scanned = [], 0
    for pattern in SCOPE_GLOBS:
        for f in sorted(ROOT.glob(pattern)):
            files_scanned += 1
            text = f.read_text(errors="replace")
            for c in extract_claims(text):
                verdict, evidence = PROBES[c["kind"]](c["value"])
                records.append({
                    "source": str(f.relative_to(ROOT)), "kind": c["kind"],
                    "claim": c["value"], "verdict": verdict, "evidence": evidence,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })
    run_digest = seal(records)
    counts = {}
    for r in records:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    out = {"run_digest": run_digest, "files_scanned": files_scanned,
           "counts": counts, "records": records}
    outp = ROOT / "research" / "runbook_drift_report.json"
    outp.write_text(json.dumps(out, indent=1))
    print(json.dumps({"run_digest": run_digest, "files": files_scanned,
                      "claims": len(records), "counts": counts,
                      "report": str(outp)}))

if __name__ == "__main__":
    main()
