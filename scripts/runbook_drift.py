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
  v3 fix: the file probe resolved a missing path with `git grep -l` — a CONTENT
      search — so it cited files that merely MENTIONED the basename as if they
      were the file. 47 of 57 UNDECIDED file_path claims had a file of that exact
      name sitting in the tree. Resolution is now by NAME over the git tree
      listing (and a bounded working-tree walk), and the evidence names the file
      that actually matched.
  v3 fix 2: name resolution must respect the SHAPE of the claim. A bare
      basename (`agent_registry.yaml`) may match any file of that name; a PATH
      claim (`PMOVES-Archon/README.md`) may only match a path ENDING that way.
      Matching a path claim on its basename let 210 unrelated README.md files
      satisfy it. A path claim that points INTO a submodule, or that is
      git-ignored, is UNDECIDED — absence proves nothing for either.

No AI model calls — the harness IS the intelligence. Read-only vs repo and network.
"""
import argparse, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

# The checkout this script lives in. RUNBOOK_DRIFT_ROOT points it at another
# tree (the A0 sidecar runs it against /a0/usr/projects/pmoves_ai).
# Resolved so a relative override is pinned once, not re-read against the CWD.
ROOT = Path(os.environ.get("RUNBOOK_DRIFT_ROOT") or Path(__file__).resolve().parents[1]).resolve()
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

# ---- name resolution (NAME queries, never content greps) ------------------
# The file probe must answer "is there a file with THIS NAME?" with a name
# query. `git grep -l <string>` answers a different question -- "which files
# mention this string?" -- and citing those as the artifact is a lie.
_NAME_INDEX_CACHE = {}

def _origin_main_paths():
    """Every file path recorded on origin/main (a tree listing, not a search).

    Paths come back relative to the probed root, the same frame the claim was
    written in and the same frame the `exists:` evidence uses.
    """
    if "origin/main" not in _NAME_INDEX_CACHE:
        rc, out, _ = sh("git ls-tree -r --name-only origin/main", timeout=60)
        paths = out.splitlines() if rc == 0 else []
        _NAME_INDEX_CACHE["origin/main"] = paths
    return _NAME_INDEX_CACHE["origin/main"]

def _working_tree_paths():
    """Every file path in the working tree, bounded; git index first, walk as fallback."""
    if "worktree" not in _NAME_INDEX_CACHE:
        paths = []
        rc, out, _ = sh("git ls-files --cached --others --exclude-standard", timeout=60)
        if rc == 0 and out:
            paths = out.splitlines()
        else:
            # Not a git checkout (or git failed): walk the tree, skipping .git.
            skip = {".git", "node_modules", "__pycache__", ".venv", "venv",
                    ".mypy_cache", ".pytest_cache"}
            for dirpath, dirnames, filenames in os.walk(ROOT):
                dirnames[:] = [d for d in dirnames if d not in skip]
                for fn in filenames:
                    full = Path(dirpath) / fn
                    try:
                        paths.append(str(full.relative_to(ROOT)).replace(os.sep, "/"))
                    except ValueError:
                        continue
        _NAME_INDEX_CACHE["worktree"] = paths
    return _NAME_INDEX_CACHE["worktree"]

def _paths_named(paths, rel):
    """Paths whose FILE NAME equals the claim's basename, case-insensitively.

    Case-folding matches the repo's own convention: fork names are
    case-insensitive-unique (PMOVES-pinokio vs pmoves-pinokio), the same
    reason pmoves/tools/fork_registry_ratchet.py keys on .casefold().

    Only for a BARE basename claim: the claim did not name a directory, so
    any file of that name is a candidate.
    """
    basename = rel.rsplit("/", 1)[-1]
    target = basename.casefold()
    return [p for p in paths if p.rsplit("/", 1)[-1].casefold() == target]

def _paths_ending(paths, rel):
    """Paths whose TAIL is exactly the claim path (on a directory boundary).

    A claim that names a directory is a PATH claim, not a basename claim.
    `PMOVES-Archon/README.md` is only satisfied by a path ending in
    `/PMOVES-Archon/README.md` -- never by one of the 210 unrelated
    `README.md` files elsewhere in the tree. Matching a path claim on its
    basename alone is the same category error as the content grep: it
    answers a different question and cites an artefact the claim never
    named.
    """
    target = rel.casefold()
    return [p for p in paths
            if p.casefold() == target or p.casefold().endswith("/" + target)]

def _submodule_paths():
    """Submodule PATHS from .gitmodules.

    A claim whose FIRST path component is a submodule path points into
    ANOTHER repository. The parent tree records a gitlink, not the
    submodule's files, so their absence here proves nothing.
    """
    if "submodules" not in _NAME_INDEX_CACHE:
        paths = set()
        gm = ROOT / ".gitmodules"
        if gm.exists():
            try:
                for raw in gm.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = raw.strip()
                    if line.startswith("path") and "=" in line:
                        _, _, val = line.partition("=")
                        val = val.strip().rstrip("/")
                        if val:
                            paths.add(val)
            except OSError:
                pass
        _NAME_INDEX_CACHE["submodules"] = paths
    return _NAME_INDEX_CACHE["submodules"]

def _is_gitignored(rel):
    """True / False / None(unknown) for whether `rel` is excluded by .gitignore.

    A git-ignored path is a LOCAL artifact: it is absent from the tree by
    design, so its absence says nothing about whether the doc is wrong.
    `None` means the question could not be answered (git failed), which is
    not the same as "not ignored".
    """
    rc, _, _ = sh(f'git check-ignore -q -- "{rel}"', timeout=20)
    if rc == 0:
        return True
    if rc == 1:
        return False
    return None  # git error: cannot decide

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
            # Forward slashes: a claim NEVER contains a backslash (RE_PATH
            # admits only [a-zA-Z0-9_./-]), so the evidence must speak the same
            # frame as the claim it answers.
            shown = str(p.relative_to(ROOT)).replace(os.sep, "/")
            return "VERIFIED", f"exists: {shown}"
    if on_origin_main(f"git show origin/main:{rel} -- >/dev/null 2>&1 || git cat-file -e origin/main:{rel}"):
        return "UNDECIDED", (f"as-written path missing locally but exists on origin/main "
                             f"({rel}) — stale local checkout, not doc drift (v3)")
    claim = rel.replace("\\", "/").strip("/")
    if not claim or "/" not in claim:
        # A BARE basename: the claim named no directory, so any file of that
        # name is a candidate. (The old probe ran `git grep -l --fixed-strings
        # <basename>`, a CONTENT query, and cited the first file that merely
        # MENTIONED the name -- 47 of 57 UNDECIDED file_path claims had a file
        # of that exact name in the tree.)
        for paths, source in ((_origin_main_paths(), "origin/main"),
                               (_working_tree_paths(), "working tree")):
            hits = _paths_named(paths, claim)
            if hits:
                if len(hits) == 1:
                    return "VERIFIED", f"exists as {hits[0]} (name match on {source})"
                # Several files share the name: name them (up to 3), and say how
                # many, rather than silently picking one.
                shown = hits[:3]
                return "VERIFIED", (f"exists as {', '.join(shown)} "
                                    f"(name match on {source}; "
                                    f"{len(hits)} files share this basename)")
        return "DRIFTED", "path not found in working tree or origin/main"

    # A PATH claim: the directory is part of the claim, so it must be matched
    # on the PATH. Matching it on the basename alone would let
    # `PMOVES-Archon/README.md` be satisfied by any of the 210 unrelated
    # README.md files in the tree — a VERIFIED verdict citing an artefact the
    # claim never named.
    for paths, source in ((_origin_main_paths(), "origin/main"),
                           (_working_tree_paths(), "working tree")):
        hits = _paths_ending(paths, claim)
        if hits:
            if len(hits) == 1:
                return "VERIFIED", f"exists as {hits[0]} (path match on {source})"
            shown = hits[:3]
            return "VERIFIED", (f"exists as {', '.join(shown)} "
                                f"(path match on {source}; "
                                f"{len(hits)} files end with this path)")
    # No path match. Before calling it drift, ask the two questions that make
    # absence meaningless: does the claim point INTO a submodule, and is the
    # path a git-ignored local artifact?
    head = claim.split("/", 1)[0]
    if head in _submodule_paths():
        return "UNDECIDED", (f"path points into the '{head}' submodule — its files live in "
                             f"another repository, so absence here proves nothing ({claim})")
    ignored = _is_gitignored(claim)
    if ignored is True:
        return "UNDECIDED", (f"path is git-ignored ({claim}) — a local artifact that is absent "
                             "from the tree by design, so absence proves nothing")
    if ignored is None:
        return "UNDECIDED", f"could not determine git-ignore status for {claim}"
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

# ---- local decision-model classifier (Jev family, PRIMARY when present) ----
# Brand + vision (operator directive 2026-10-15): Jev decision models are the
# PRIMARY intent classifier. Frozen-weight, local, CUDA-first (CPU fallback), zero API keys. OPEN JEV FAMILY.
# Architecture (decoded from ONNX signature): multiple-choice scoring head —
# input_ids [num_candidates, seq_len], cand_end_pos [num_candidates], OUT
# logits [num_candidates]. All options scored in ONE pass, softmax over candidates.
# Prompt shape = calibrated trio ([STATE]/[Q]/[OPT]) from the 3/3 @ 129ms baseline.
# temperatures.json: choice calibration is SOFT (soft-CE ~0.97) — near-uniform is
# expected for ambiguous inputs; confidence < 0.5 => UNDECIDED (never guesses).
# --no-jev opts out; missing runtime/model => heuristics fallback, announced in stdout.
# JEV_MODEL_PATH lets a node keep the 1 GB model off the checkout (SPARK: 4TB drive).
JEV_MODEL = Path(os.environ.get("JEV_MODEL_PATH")
                 or ROOT / "research/models/agentjev/agentjev_0.6b_int8.onnx")
JEV_LABELS = ["DRAFT", "RUNBOOK", "HISTORICAL"]
JEV_OPTIONS = [
    "DRAFT - planned or proposal document referencing artifacts that may not exist yet",
    "RUNBOOK - operational instructions with checkable claims about the current tree",
    "HISTORICAL - past-tense record of completed, destroyed, or superseded work",
]

def _load_jev():
    """Load AgentJev ONNX MC-scoring session + tokenizer, or None with announced reason."""
    try:
        import onnxruntime
        from tokenizers import Tokenizer
        if not JEV_MODEL.exists():
            print(json.dumps({"note": "jev model file absent, heuristics fallback"}))
            return None
        tok = Tokenizer.from_file(str(JEV_MODEL.parent / "tokenizer.json"))
        so = onnxruntime.SessionOptions()
        so.intra_op_num_threads = 2  # sidecar CPU friendly
        _avail = onnxruntime.get_available_providers()
        _prov = [x for x in ("CUDAExecutionProvider", "CPUExecutionProvider") if x in _avail]
        sess = onnxruntime.InferenceSession(str(JEV_MODEL), so, providers=_prov)
        return sess, tok
    except Exception as e:
        print(json.dumps({"note": "jev unavailable, heuristics fallback", "reason": str(e)[:120]}))
        return None

def jev_classify_doc(sess, tok, text, source="doc"):
    """Score DRAFT/RUNBOOK/HISTORICAL as candidates in one pass (MC head); <0.5 => UNDECIDED."""
    try:
        import numpy as np
        sample = " ".join(text.split()[:140])[:1100]
        prompt = (f"[STATE] {source}: {sample}\n"
                  f"[Q] Which document class is this?\n"
                  f"[OPT] A. {JEV_OPTIONS[0]}\n"
                  f"[OPT] B. {JEV_OPTIONS[1]}\n"
                  f"[OPT] C. {JEV_OPTIONS[2]}\n"
                  f"Answer:")
        rows, ends = [], []
        for opt in JEV_OPTIONS:
            ids = tok.encode(prompt + " " + opt).ids[-384:]
            rows.append(ids); ends.append(len(ids) - 1)
        L = max(len(r) for r in rows)
        ii = [[0] * (L - len(r)) + r for r in rows]
        am = [[0] * (L - len(r)) + [1] * len(r) for r in rows]
        out = sess.run(None, {"input_ids": ii, "attention_mask": am, "cand_end_pos": ends})
        lg = np.array(out[0] if isinstance(out, list) else out).flatten()
        e = np.exp(lg - lg.max()); probs = e / e.sum()
        best = int(np.argmax(probs))
        if probs[best] < 0.5:
            return "UNDECIDED"  # fail-closed: soft-calibrated abstention
        return JEV_LABELS[best]
    except Exception:
        return "UNDECIDED"

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
    ap.add_argument("--no-jev", action="store_true",
                    help="disable the local AgentJev intent classifier (heuristic fallback)")
    args = ap.parse_args()
    jev = None if args.no_jev else _load_jev()
    globs = [g.strip() for g in args.globs.split(",") if g.strip()]
    records, files_scanned, register_skipped = [], 0, 0
    for pattern in globs:
        for f in sorted(ROOT.glob(pattern)):
            if f.name.startswith("AGNOTE4482PHI"):
                register_skipped += 1
                continue  # the register is append-only history, not claims (v3)
            files_scanned += 1
            rel = str(f.relative_to(ROOT))
            dc = doc_class(rel)
            text = f.read_text(errors="replace")
            if jev is not None:
                # The model replaces the heuristic only when it commits; an
                # abstention must not erase what the filename already says.
                jdc = jev_classify_doc(jev[0], jev[1], text)
                if jdc != "UNDECIDED":
                    dc = jdc
            for c in extract_claims(text, rel):
                verdict, evidence = PROBES[c["kind"]](c["value"])
                records.append({
                    "source": rel, "doc_class": dc, "kind": c["kind"],
                    "claim": c["value"], "line": c["line"],
                    "verdict": verdict, "evidence": evidence,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })
    if files_scanned == 0:
        # An empty scan is not a clean audit: say so and fail.
        msg = f"runbook_drift: globs {globs} matched no auditable files under {ROOT}"
        if register_skipped:
            msg += f" ({register_skipped} AGNOTE4482PHI register file(s) matched and skipped)"
        print(msg, file=sys.stderr)
        sys.exit(2)
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
