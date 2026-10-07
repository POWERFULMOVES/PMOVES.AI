#!/usr/bin/env python3
"""Report work stranded off `main`, as a ratchet.

Why this exists
---------------
Work can be stranded off `main` in two shapes no other gate sees: commits on a
pushed branch that no open PR carries and that never reached main (after a
merged PR, behind PRs closed unmerged, or never proposed), and commits on a
local branch that were never pushed at all. Measured 2026-10-07 with this tool:
47 branches on origin hold 92 commits whose change applies cleanly to main and
is not there (baselined in pmoves/config/orphan_branch_baseline.json).

The two cases that prompted it are, instructively, NOT orphans -- triage
showed both landed, which is why most of this file is about not crying wolf:

  * `origin/fix/consolidate-archon`: `rev-list main..` says 15 commits after
    PR #2127 merged, follow-up #2208 closed unmerged. The content landed in
    PR #2275, a squash of a DIFFERENT branch (#2208 closed 6s later as
    superseded). Five of its commits replay onto main as no-ops (LANDED); the
    rest conflict because main moved on (UNCERTAIN, not counted).
  * `feat/showtime-updater` (z890, upstream `[gone]`): its tip IS PR #1905's
    merged head. Squash-merged, remote branch deleted -- not unpushed.

The hard half is NOT finding commits absent from `main`; `git rev-list
main..branch` does that. It is NOT flagging the hundreds of branches whose
content DID land through a squash merge. A squash merge leaves every one of the
branch's commits unreachable from `main`, so ancestry lies. The rules here:

  * `git cherry <main> <branch>`: a commit marked `-` is already on main by
    PATCH (cherry-picked, rebased, or a one-commit squash). Never an orphan.
  * If the branch has a MERGED PR, the latest merged PR's head (H, from
    `headRefOid`) is what landed. Only commits that are also `+` in
    `git cherry H <branch>` -- i.e. not in H and not patch-equal to anything in
    H -- are orphans. A squash-merged branch whose head IS H therefore has zero.
  * A branch with an OPEN PR is in flight, not stranded. Not a finding.
  * No merged PR: every `+` commit is a candidate -- CLOSED_UNMERGED if PRs
    were closed, NO_PR if none was ever opened.
  * CONTENT TEST, last and decisive: a squash merge of a DIFFERENT branch
    defeats both rules above (PR #2275 swallowed fix/consolidate-archon). Each
    candidate C is replayed onto main with `git merge-tree --write-tree
    --merge-base=C^ main C`. A no-op result (tree == main's tree) means C's
    content is on main: LANDED. A clean apply that changes the tree is an
    ORPHAN. A conflict means main moved on and nothing is provable: UNCERTAIN,
    listed separately with a content-triage hint and NOT counted by the ratchet.

Two modes:

  remote  CI-safe. Every head on the remote (`git ls-remote --heads`, the live
          list -- stale remote-tracking refs would report deleted branches).
          PR facts from ONE bulk `gh pr list --state all` call.
  local   Node-side. Every local branch plus detached-HEAD worktrees: commits
          reachable from no live remote head, not on main by patch, and not in
          the branch's merged PR head. Kinds: NO_UPSTREAM, UPSTREAM_GONE,
          AHEAD_OF_UPSTREAM, DETACHED_WORKTREE.

READ-ONLY. It runs `git ls-remote`, `rev-list`, `rev-parse`, `cherry`, `log`,
`cat-file`, `diff`, `show`, `check-attr`, `merge-tree --write-tree`,
`for-each-ref`, `worktree list`, `fetch` (below) and `gh pr list`. It never
pushes, deletes, or rewrites anything, and moves no ref. Writes go to the
OBJECT STORE only: `merge-tree --write-tree` writes tree/blob objects, and when
a branch was force-pushed after its PR merged (so the merged head is reachable
from no branch) it fetches `refs/pull/N/head` with `--no-write-fetch-head`,
`--refmap=` (so a node whose config maps refs/pull/* never gets a tracking ref
updated), `--no-auto-gc`, and no destination. `--no-fetch-pr-heads` disables
the fetch.
Triage of what it finds is a human/agent act.

Ratchet (pmoves/config/orphan_branch_baseline.json)
---------------------------------------------------
  NEW        branch not in the baseline                     -> fail
  GROWTH     baselined, count went UP                        -> fail
  BASELINED  baselined, count unchanged                      -> pass
  SHRUNK     baselined, count went down                      -> pass, says lower it
  STALE      baselined, no longer an orphan (or gone)        -> pass, flagged:
                                                               remove the entry
  baseline entry with no non-empty `reason`                  -> fail

Stale entries PASS here, unlike compose_hardening_ratchet where they fail. The
difference is deliberate: that baseline describes a file in the PR's own tree,
so a stale entry is something the PR author can fix in the same PR. This one
describes REMOTE STATE that changes out-of-band -- another agent salvages a
branch and deletes it -- and failing on that would turn every unrelated run red
the moment someone does the cleanup this tool asks for. It is still reported
every run so the list shrinks.

`--write-baseline` re-records the current findings, KEEPS existing reasons, and
writes new entries with an EMPTY reason, which fails the next run until someone
writes why. That is the "adding needs a reason" half of the ratchet.

Run:   python pmoves/tools/orphan_branch_ratchet.py remote
       python pmoves/tools/orphan_branch_ratchet.py local
       python pmoves/tools/orphan_branch_ratchet.py remote --json
       python pmoves/tools/orphan_branch_ratchet.py remote --write-baseline

Exit (repo doctrine, see docker_host_policy_check.py):
       0 = clean (no new orphan, no growth, baseline valid)
       1 = findings (new orphan, growth, or a baseline entry without a reason)
       3 = COULD NOT MEASURE: gh missing/unauthenticated, remote unreachable,
           base commit not present locally, or a branch whose merged PR head is
           not in the local object store. NEVER conflate with 0.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "pmoves" / "config" / "orphan_branch_baseline.json"

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_CANNOT_MEASURE = 3

# One bulk call instead of one per branch (181 remote heads on 2026-10-07; the
# bulk call returned 3207 PRs in ~14s). If the result reaches the limit it may
# be truncated, and a truncated PR list makes merged branches look orphaned --
# so that is could-not-measure, not a guess.
PR_LIMIT = 20000
PR_FIELDS = "number,state,headRefName,headRefOid,mergedAt,closedAt,isCrossRepository"


class CouldNotMeasure(RuntimeError):
    pass


# --------------------------------------------------------------------------
# git plumbing (read-only)
# --------------------------------------------------------------------------


def _git(repo: Path, *args: str, stdin: str | None = None, check: bool = True) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise CouldNotMeasure(f"git not found: {exc}") from exc
    if check and proc.returncode != 0:
        raise CouldNotMeasure(f"git {' '.join(args[:3])} failed: {proc.stderr.strip()[:300]}")
    return proc.stdout


def _git_rc(repo: Path, *args: str) -> tuple[int, str]:
    """Like _git(check=False) but also returns the exit code."""
    try:
        proc = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError as exc:
        raise CouldNotMeasure(f"git not found: {exc}") from exc
    return proc.returncode, proc.stdout


def ls_remote_heads(repo: Path, remote: str) -> Dict[str, str]:
    out = _git(repo, "ls-remote", "--heads", remote)
    heads: Dict[str, str] = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith("refs/heads/"):
            heads[ref[len("refs/heads/"):]] = sha
    if not heads:
        raise CouldNotMeasure(f"`git ls-remote --heads {remote}` returned no heads")
    return heads


def present(repo: Path, shas: Iterable[str]) -> set[str]:
    """Which of these commits exist in the local object store."""
    shas = list(dict.fromkeys(shas))
    if not shas:
        return set()
    out = _git(repo, "cat-file", "--batch-check", stdin="\n".join(shas) + "\n")
    have = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "commit":
            have.add(parts[0])
    return have


def cherry_plus(repo: Path, upstream: str, head: str) -> List[str]:
    """Commits in `head` not in `upstream` and not patch-equal to one there."""
    out = _git(repo, "cherry", upstream, head)
    return [ln[2:].strip() for ln in out.splitlines() if ln.startswith("+ ")]


def rev_list(repo: Path, include: str, exclude: Sequence[str]) -> List[str]:
    revs = [include, *(f"^{x}" for x in exclude)]
    out = _git(repo, "rev-list", "--stdin", stdin="\n".join(revs) + "\n")
    return out.split()


def commit_meta(repo: Path, shas: Sequence[str]) -> List[dict]:
    if not shas:
        return []
    out = _git(
        repo,
        "log",
        "--no-walk=unsorted",
        "--stdin",
        "--format=%H%x1f%an%x1f%aI",
        stdin="\n".join(shas) + "\n",
    )
    meta = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            meta.append({"sha": parts[0], "author": parts[1], "date": parts[2]})
    return meta


# --------------------------------------------------------------------------
# PR lookup
# --------------------------------------------------------------------------


def load_prs_gh(repo: Path, gh: str) -> List[dict]:
    cmd = [gh, "pr", "list", "--state", "all", "--limit", str(PR_LIMIT), "--json", PR_FIELDS]
    try:
        proc = subprocess.run(
            cmd, cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise CouldNotMeasure(f"gh unavailable ({gh}): {exc}") from exc
    if proc.returncode != 0:
        raise CouldNotMeasure(f"`gh pr list` failed: {proc.stderr.strip()[:300]}")
    try:
        prs = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CouldNotMeasure(f"`gh pr list` returned non-JSON: {exc}") from exc
    if len(prs) >= PR_LIMIT:
        raise CouldNotMeasure(f"`gh pr list` hit --limit {PR_LIMIT}; PR list may be truncated")
    return prs


def load_prs_file(path: Path) -> List[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CouldNotMeasure(f"unreadable --prs-json {path}: {exc}") from exc


def index_prs(prs: Iterable[dict]) -> Dict[str, List[dict]]:
    """headRefName -> PRs from THIS repository (fork PRs can reuse a name)."""
    idx: Dict[str, List[dict]] = {}
    for pr in prs:
        if pr.get("isCrossRepository"):
            continue
        idx.setdefault(pr.get("headRefName", ""), []).append(pr)
    for lst in idx.values():
        lst.sort(key=lambda p: p.get("number", 0))
    return idx


def latest_merged(prs: List[dict]) -> Optional[dict]:
    merged = [p for p in prs if p.get("state") == "MERGED"]
    if not merged:
        return None
    return max(merged, key=lambda p: (p.get("mergedAt") or "", p.get("number", 0)))


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------


@dataclass
class Finding:
    branch: str
    kind: str
    commits: List[str]
    authors: List[str]
    first: str
    last: str
    prs: List[dict]
    recommendation: str
    worktree: Optional[str] = None
    status: str = "NEW"
    baseline_count: Optional[int] = None
    uncertain: List[str] = field(default_factory=list)
    landed: int = 0

    @property
    def count(self) -> int:
        return len(self.commits)

    def as_dict(self) -> dict:
        return {
            "branch": self.branch,
            "count": self.count,
            "kind": self.kind,
            "authors": self.authors,
            "first": self.first,
            "last": self.last,
            "prs": self.prs,
            "recommendation": self.recommendation,
            "worktree": self.worktree,
            "status": self.status,
            "baseline_count": self.baseline_count,
            "commits": self.commits,
            "uncertain": self.uncertain,
            "landed": self.landed,
        }


@dataclass
class Scan:
    mode: str
    scanned: int = 0
    findings: List[Finding] = field(default_factory=list)
    in_flight: List[str] = field(default_factory=list)
    unmeasured: List[dict] = field(default_factory=list)
    uncertain: List[dict] = field(default_factory=list)


def _recommend(kind: str, prs: List[dict], merged: Optional[dict], upstream: str, wt: Optional[str]) -> str:
    if kind == "POST_MERGE":
        return (
            f"commits made after PR #{merged['number']} merged change main and are on no "
            "open PR. Either stranded (open a follow-up PR or salvage onto a fresh branch) "
            "or deliberately superseded/declined (record that); delete only after triage."
        )
    if kind == "CLOSED_UNMERGED":
        return (
            f"every PR from this branch was closed unmerged (latest #{prs[-1]['number']}). "
            "Often a deliberate decline/supersede (record it); otherwise re-propose in a "
            "new PR. Delete the branch only after triage."
        )
    if kind == "NO_PR":
        return ("pushed but never proposed: open a PR, or record why this branch lives off "
                "main (scratch, superseded, or declined work also lands here).")
    if kind == "NO_UPSTREAM":
        return "never pushed -- this disk holds the only copy: push it and open a PR, or salvage it."
    if kind == "UPSTREAM_GONE":
        return (
            "remote branch deleted while these commits are neither on main nor in a merged "
            "PR head: push to a fresh branch and open a PR, or record why they are abandoned."
        )
    if kind == "AHEAD_OF_UPSTREAM":
        return f"commits not pushed to {upstream}: push them; no PR carries them yet."
    if kind == "DETACHED_WORKTREE":
        return f"detached HEAD in worktree {wt} holds commits on no branch: create a branch there before the worktree is removed."
    return "triage"


def _finding(repo: Path, branch: str, kind: str, commits: List[str], prs: List[dict],
             merged: Optional[dict], upstream: str = "", wt: Optional[str] = None) -> Finding:
    meta = commit_meta(repo, commits)
    authors = sorted({m["author"] for m in meta})
    dates = sorted(m["date"][:10] for m in meta)
    return Finding(
        branch=branch,
        kind=kind,
        commits=commits,
        authors=authors,
        first=dates[0] if dates else "",
        last=dates[-1] if dates else "",
        prs=[{"number": p["number"], "state": p["state"]} for p in prs],
        recommendation=_recommend(kind, prs, merged, upstream, wt),
        worktree=wt,
    )


UNCERTAIN_HINT = (
    "does not apply cleanly to main (main moved on), so neither landed nor provably "
    "orphaned: content-triage it (diff the commit's files against main)"
)


def classify_content(repo: Path, base_sha: str, commits: Sequence[str]) -> tuple[List[str], List[str], List[str]]:
    """Split candidates into (orphan, landed, uncertain) by CONTENT, not ancestry.

    `git cherry` only recognises a commit whose patch is reproduced one-for-one
    on main. A squash merge of a DIFFERENT branch defeats it -- measured on
    2026-10-07: PR #2275's single squash commit swallowed the content of
    origin/fix/consolidate-archon, so cherry and PR-head matching both called
    those commits orphans while their content was on main. So each surviving
    candidate C is replayed onto main in memory:

        git merge-tree --write-tree --merge-base=C^ <main> C

      exit 0, tree == main's tree  -> LANDED   (applying C changes nothing)
      exit 0, tree != main's tree  -> ORPHAN   (C's change is not on main)
                                      ...unless _union_already_on_main(), below
      exit 1 (conflict)            -> UNCERTAIN (main moved; cannot prove either)
      any other exit / root commit -> UNCERTAIN (merge-tree could not run)

    merge=union FILES. merge-tree honours .gitattributes, and the claim register
    (pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md) is `merge=union`. A commit that
    appends a row which is ALREADY on main -- landed through another PR at a
    different position -- therefore replays "cleanly" by duplicating the row,
    the tree differs, and it read as an ORPHAN. Review of PR #3306 measured 8
    such false orphans (e.g. f22eacbb5). `--attr-source=<empty tree>` is NOT the
    fix: it turns genuine appends (a37a08d47) into conflicts. Instead a clean,
    tree-changing replay is LANDED when every path C changes is merge=union and
    every line C adds is already present, verbatim, in main's copy of that path
    (and every line it removes is already absent there).

    merge-tree writes tree objects only; no ref, index or worktree is touched.
    """
    base_tree = _git(repo, "rev-parse", f"{base_sha}^{{tree}}").strip()
    orphan: List[str] = []
    landed: List[str] = []
    uncertain: List[str] = []
    for c in commits:
        rc, out = _git_rc(repo, "merge-tree", "--write-tree", f"--merge-base={c}^", base_sha, c)
        lines = out.splitlines()
        tree = lines[0].strip() if lines else ""
        clean = rc == 0 and len(lines) == 1 and len(tree) in (40, 64)
        if clean and tree == base_tree:
            landed.append(c)
        elif clean and _union_already_on_main(repo, base_sha, c):
            landed.append(c)
        elif clean:
            orphan.append(c)
        else:
            # rc 1 = conflict; anything else = merge-tree could not run (root
            # commit, missing parent, git error). Neither proves landed or not.
            uncertain.append(c)
    return orphan, landed, uncertain


def _union_already_on_main(repo: Path, base_sha: str, c: str) -> bool:
    """True when C touches only merge=union paths and its whole diff is
    already reflected in main: every added line present, every removed line
    absent. See classify_content for why (duplicated register rows)."""
    paths = [p for p in _git(repo, "diff", "--name-only", "--no-renames", f"{c}^", c).splitlines() if p]
    if not paths:
        return False
    for path in paths:
        rc, attr = _git_rc(repo, "check-attr", "--source", base_sha, "merge", "--", path)
        if rc != 0:
            rc, attr = _git_rc(repo, "check-attr", "merge", "--", path)
        if rc != 0 or not attr.strip().endswith(": merge: union"):
            return False
        rc, blob = _git_rc(repo, "show", f"{base_sha}:{path}")
        if rc != 0:
            return False
        on_main = {ln.rstrip("\r") for ln in blob.splitlines()}
        diff = _git(repo, "diff", "--no-color", "--no-renames", "--unified=0", f"{c}^", c, "--", path)
        for ln in diff.splitlines():
            if ln.startswith(("+++", "---")):
                continue
            if ln.startswith("+") and ln[1:].rstrip("\r") not in on_main:
                return False
            if ln.startswith("-") and ln[1:].rstrip("\r") in on_main:
                return False
    return True


def _record(repo: Path, scan: Scan, base_sha: str, name: str, kind: str, cand: List[str],
            prs: List[dict], merged: Optional[dict], upstream: str = "",
            wt: Optional[str] = None) -> None:
    orphan, landed, uncertain = classify_content(repo, base_sha, cand)
    if orphan:
        f = _finding(repo, name, kind, orphan, prs, merged, upstream, wt)
        f.uncertain = uncertain
        f.landed = len(landed)
        scan.findings.append(f)
    elif uncertain:
        scan.uncertain.append({
            "branch": name,
            "kind": kind,
            "count": len(uncertain),
            "landed": len(landed),
            "commits": uncertain,
            "prs": [{"number": p["number"], "state": p["state"]} for p in prs],
            "worktree": wt,
            "hint": UNCERTAIN_HINT,
        })


def fetch_pr_head(repo: Path, remote: str, number: int) -> None:
    """Bring a merged PR's head commit into the object store.

    Needed when a branch was force-pushed after its PR merged: the merged head
    is then reachable from no branch, so a normal fetch never brings it, and
    without it we cannot say which commits came after the merge. This writes
    OBJECTS only: `--no-write-fetch-head`, no refspec destination, and an
    empty `--refmap=` so a remote configured with a refs/pull/* fetch refspec
    still gets no tracking ref updated; `--no-auto-gc` keeps it from pruning.
    Failure is not raised here; the caller re-checks presence and reports
    could-not-measure.
    """
    _git(repo, "fetch", "--quiet", "--no-tags", "--no-write-fetch-head", "--refmap=",
         "--no-auto-gc", remote, f"refs/pull/{number}/head", check=False)


def _drop_merged_head(repo: Path, branch: str, sha: str, cand: List[str], prs: List[dict],
                      scan: Scan, remote: Optional[str] = None) -> Optional[tuple[List[str], Optional[dict]]]:
    """Remove commits that are in (or patch-equal to) the latest merged PR head.

    Returns None when the merged head is not in the local object store (after
    one `refs/pull/N/head` fetch when `remote` is given): we cannot tell which
    commits came after it, and guessing either way is a lie.
    """
    merged = latest_merged(prs)
    if merged is None:
        return cand, None
    head = merged.get("headRefOid") or ""
    if head not in present(repo, [head]) and remote:
        fetch_pr_head(repo, remote, merged["number"])
    if head not in present(repo, [head]):
        scan.unmeasured.append(
            {"branch": branch,
             "reason": f"merged PR #{merged['number']} head {head[:12]} not in the local "
                       f"object store (try `git fetch origin refs/pull/{merged['number']}/head`)"}
        )
        return None
    after = set(cherry_plus(repo, head, sha))
    return [c for c in cand if c in after], merged


def scan_remote(repo: Path, remote: str, base: str, prs_idx: Dict[str, List[dict]],
                exempt: Iterable[str], fetch_pr_heads: bool = True) -> tuple[Scan, str]:
    heads = ls_remote_heads(repo, remote)
    if base not in heads:
        raise CouldNotMeasure(f"base branch {base!r} is not a head on {remote}")
    base_sha = heads[base]
    have = present(repo, heads.values())
    if base_sha not in have:
        raise CouldNotMeasure(f"{remote}/{base} {base_sha[:12]} not in the local object store; fetch first")
    scan = Scan(mode="remote")
    skip = {base, *exempt}
    for name, sha in sorted(heads.items()):
        if name in skip:
            continue
        scan.scanned += 1
        if sha not in have:
            scan.unmeasured.append({"branch": name, "reason": f"head {sha[:12]} not fetched; run `git fetch {remote}`"})
            continue
        prs = prs_idx.get(name, [])
        if any(p.get("state") == "OPEN" for p in prs):
            scan.in_flight.append(name)
            continue
        cand = cherry_plus(repo, base_sha, sha)
        if not cand:
            continue
        res = _drop_merged_head(repo, name, sha, cand, prs, scan,
                                remote if fetch_pr_heads else None)
        if res is None:
            continue
        cand, merged = res
        if not cand:
            continue
        kind = "POST_MERGE" if merged else ("CLOSED_UNMERGED" if prs else "NO_PR")
        _record(repo, scan, base_sha, name, kind, cand, prs, merged)
    return scan, base_sha


def _worktrees(repo: Path) -> tuple[Dict[str, str], List[tuple[str, str]]]:
    """branch -> worktree path, and [(path, sha)] for detached HEADs."""
    out = _git(repo, "worktree", "list", "--porcelain")
    by_branch: Dict[str, str] = {}
    detached: List[tuple[str, str]] = []
    path = sha = ""
    for line in out.splitlines() + [""]:
        if line.startswith("worktree "):
            path, sha = line[len("worktree "):], ""
        elif line.startswith("HEAD "):
            sha = line[len("HEAD "):]
        elif line.startswith("branch refs/heads/"):
            by_branch[line[len("branch refs/heads/"):]] = path
        elif line == "detached" and sha:
            detached.append((path, sha))
    return by_branch, detached


def scan_local(repo: Path, remote: str, base: str,
               prs_idx: Dict[str, List[dict]], fetch_pr_heads: bool = True) -> tuple[Scan, str]:
    heads = ls_remote_heads(repo, remote)
    if base not in heads:
        raise CouldNotMeasure(f"base branch {base!r} is not a head on {remote}")
    base_sha = heads[base]
    have = present(repo, heads.values())
    if base_sha not in have:
        raise CouldNotMeasure(f"{remote}/{base} {base_sha[:12]} not in the local object store; fetch first")
    # A commit reachable from any LIVE remote head is pushed. A head we have
    # not fetched cannot be used as an exclusion (we do not have its history),
    # so if someone pushed ON TOP of our commit and we have not fetched, that
    # commit reads as unpushed -- a false positive, never a false negative.
    # Run `git fetch` first; the make target's help says so.
    pushed_tips = sorted(have)
    wt_by_branch, detached = _worktrees(repo)
    refs = _git(
        repo, "for-each-ref", "refs/heads",
        "--format=%(refname:short)%1f%(objectname)%1f%(upstream:short)%1f%(upstream:track)",
    )
    scan = Scan(mode="local")
    subjects: List[tuple[str, str, str, str, Optional[str]]] = []
    for line in refs.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        name, sha, upstream, track = parts
        subjects.append((name, sha, upstream, track, wt_by_branch.get(name)))
    for path, sha in detached:
        subjects.append((f"(detached) {path}", sha, "", "", path))

    for name, sha, upstream, track, wt in subjects:
        scan.scanned += 1
        # The branch's own live upstream counts as pushed even when it is on
        # another remote (e.g. a fork remote): those commits are not one-copy.
        own = [upstream] if upstream and "gone" not in track else []
        unpushed = rev_list(repo, sha, pushed_tips + own)
        if not unpushed:
            continue
        plus = set(cherry_plus(repo, base_sha, sha))
        cand = [c for c in reversed(unpushed) if c in plus]
        if not cand:
            continue
        detached_subject = name.startswith("(detached) ")
        prs = [] if detached_subject else prs_idx.get(name, [])
        res = _drop_merged_head(repo, name, sha, cand, prs, scan,
                                remote if fetch_pr_heads else None)
        if res is None:
            continue
        cand, merged = res
        if not cand:
            continue
        if detached_subject:
            kind = "DETACHED_WORKTREE"
        elif not upstream:
            kind = "NO_UPSTREAM"
        elif "gone" in track:
            kind = "UPSTREAM_GONE"
        else:
            kind = "AHEAD_OF_UPSTREAM"
        _record(repo, scan, base_sha, name, kind, cand, prs, merged, upstream, wt)
    return scan, base_sha


# --------------------------------------------------------------------------
# baseline
# --------------------------------------------------------------------------


def default_node() -> str:
    node = os.environ.get("PMOVES_NODE_ID") or socket.gethostname()
    node = node.strip().lower()
    return node[len("pmoves-"):] if node.startswith("pmoves-") else node


def read_baseline(path: Path) -> dict:
    if not path.exists():
        return {"remote": {}, "local": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CouldNotMeasure(f"unreadable baseline {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CouldNotMeasure(f"baseline {path} is not a JSON object")
    return data


def section(data: dict, mode: str, node: str) -> Dict[str, dict]:
    if mode == "remote":
        return data.setdefault("remote", {})
    return data.setdefault("local", {}).setdefault(node, {})


def validate_section(entries: Dict[str, dict], exempt: Dict[str, str]) -> List[str]:
    problems = []
    for name, entry in sorted(entries.items()):
        if not isinstance(entry, dict):
            problems.append(f"{name}: entry must be an object with count + reason")
            continue
        count = entry.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            problems.append(f"{name}: 'count' must be a positive integer, got {count!r}")
        if not str(entry.get("reason", "")).strip():
            problems.append(f"{name}: missing non-empty 'reason' -- say why this orphan is tolerated")
    for name, reason in sorted(exempt.items()):
        if not str(reason).strip():
            problems.append(f"_exempt.{name}: missing non-empty reason")
    return problems


def apply_baseline(scan: Scan, entries: Dict[str, dict]) -> List[str]:
    """Set each finding's status; return stale baseline entries."""
    seen = set()
    for f in scan.findings:
        entry = entries.get(f.branch)
        if not isinstance(entry, dict):
            f.status = "NEW"
            continue
        seen.add(f.branch)
        base_count = entry.get("count")
        f.baseline_count = base_count if isinstance(base_count, int) else None
        if f.baseline_count is None or f.count > f.baseline_count:
            f.status = "GROWTH"
        elif f.count < f.baseline_count:
            f.status = "SHRUNK"
        else:
            f.status = "BASELINED"
    unmeasured = {u["branch"] for u in scan.unmeasured}
    return sorted(b for b in entries if b not in seen and b not in unmeasured)


def write_baseline(path: Path, data: dict, mode: str, node: str, scan: Scan) -> None:
    old = section(data, mode, node)
    unmeasured = {u["branch"] for u in scan.unmeasured}
    new: Dict[str, dict] = {}
    for f in sorted(scan.findings, key=lambda f: f.branch):
        prev = old.get(f.branch) if isinstance(old.get(f.branch), dict) else {}
        new[f.branch] = {
            "count": f.count,
            "kind": f.kind,
            "head_window": f"{f.first}..{f.last}",
            "prs": [f"#{p['number']} {p['state']}" for p in f.prs],
            "reason": prev.get("reason", ""),
        }
    # An entry we could not measure this run is kept as-is, not dropped:
    # dropping it would let it come back as NEW with no memory of its reason.
    for b in unmeasured:
        if b in old and b not in new:
            new[b] = old[b]
    if mode == "remote":
        data["remote"] = new
    else:
        data.setdefault("local", {})[node] = new
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _print_human(scan: Scan, remote: str, base: str, node: str, stale: List[str],
                 problems: List[str], code: int) -> None:
    where = f"{remote} vs {base}" if scan.mode == "remote" else f"node {node}, vs {remote}/{base}"
    counts: Dict[str, int] = {}
    for f in scan.findings:
        counts[f.status] = counts.get(f.status, 0) + 1
    tally = ", ".join(f"{v} {k.lower()}" for k, v in sorted(counts.items())) or "none"
    print(f"orphan-branch ratchet ({scan.mode}, {where}): {scan.scanned} branch(es) scanned")
    print(f"  findings: {len(scan.findings)} ({tally}); uncertain: {len(scan.uncertain)}; "
          f"in flight (open PR): {len(scan.in_flight)}; unmeasured: {len(scan.unmeasured)}")
    for f in sorted(scan.findings, key=lambda f: (f.status not in ("NEW", "GROWTH"), f.branch)):
        prs = ", ".join(f"#{p['number']} {p['state']}" for p in f.prs) or "no PR"
        grow = f" (baseline {f.baseline_count})" if f.baseline_count is not None else ""
        print(f"  {f.status:<9} {f.branch}: {f.count} commit(s){grow} [{f.kind}] "
              f"authors: {', '.join(f.authors)}; {f.first}..{f.last}; PRs: {prs}")
        if f.worktree:
            print(f"            worktree: {f.worktree}")
        if f.uncertain or f.landed:
            print(f"            also: {f.landed} landed by content, {len(f.uncertain)} uncertain (not counted)")
        print(f"            -> {f.recommendation}")
        if f.status == "SHRUNK":
            print(f"            -> LOWER the baseline count for {f.branch} to {f.count}")
    for u in scan.uncertain:
        prs = ", ".join(f"#{p['number']} {p['state']}" for p in u["prs"]) or "no PR"
        print(f"  UNCERTAIN {u['branch']}: {u['count']} commit(s) [{u['kind']}] "
              f"({u['landed']} landed by content); PRs: {prs} -- not counted")
    if scan.uncertain:
        print(f"            -> {UNCERTAIN_HINT}")
    for u in scan.unmeasured:
        print(f"  UNMEASURED {u['branch']}: {u['reason']}")
    for b in stale:
        print(f"  STALE     {b}: baselined but no longer an orphan -- remove the entry")
    for p in problems:
        print(f"  BASELINE  {p}")
    verdict = {EXIT_CLEAN: "PASS", EXIT_FINDINGS: "FAIL (new orphan, growth, or unreasoned baseline entry)",
               EXIT_CANNOT_MEASURE: "COULD NOT MEASURE (not a pass)"}[code]
    print(f"  verdict: {verdict}")
    print("  (the ratchet compares per-branch COUNTS: a baselined branch that swaps "
          "one orphan commit for another at the same count still passes)")


def main(argv: Optional[List[str]] = None,
         pr_loader: Optional[Callable[[Path], List[dict]]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", choices=["remote", "local"])
    ap.add_argument("--repo", type=Path, default=REPO_ROOT, help="git repository to scan")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--base", default="main", help="trunk branch name on the remote")
    ap.add_argument("--baseline", type=Path, default=BASELINE)
    ap.add_argument("--node", default=None, help="local-mode baseline key (default: PMOVES_NODE_ID or hostname)")
    ap.add_argument("--gh", default="gh", help="gh executable for the PR lookup")
    ap.add_argument("--prs-json", type=Path, default=None,
                    help="read PRs from this JSON file (gh pr list --json shape) instead of calling gh")
    ap.add_argument("--no-fetch-pr-heads", action="store_true",
                    help="never fetch refs/pull/N/head for a merged head missing locally "
                         "(such branches are then reported UNMEASURED -> exit 3)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-baseline", action="store_true",
                    help="re-record current findings; keeps reasons, new entries get an empty reason")
    args = ap.parse_args(argv)
    node = args.node or default_node()
    repo = args.repo.resolve()

    try:
        data = read_baseline(args.baseline)
        exempt = data.get("_exempt") or {}
        if not isinstance(exempt, dict):
            raise CouldNotMeasure("baseline '_exempt' must be an object of branch -> reason")
        if args.prs_json is not None:
            prs = load_prs_file(args.prs_json)
        elif pr_loader is not None:
            prs = pr_loader(repo)
        else:
            prs = load_prs_gh(repo, args.gh)
        idx = index_prs(prs)
        if args.mode == "remote":
            scan, base_sha = scan_remote(repo, args.remote, args.base, idx, exempt,
                                         not args.no_fetch_pr_heads)
        else:
            scan, base_sha = scan_local(repo, args.remote, args.base, idx,
                                        not args.no_fetch_pr_heads)
    except CouldNotMeasure as exc:
        print(f"orphan-branch ratchet: COULD NOT MEASURE: {exc}", file=sys.stderr)
        if args.json:
            print(json.dumps({"mode": args.mode, "exit": EXIT_CANNOT_MEASURE, "error": str(exc)}))
        return EXIT_CANNOT_MEASURE

    if args.write_baseline:
        if scan.unmeasured:
            print("orphan-branch ratchet: refusing --write-baseline with unmeasured branches; "
                  "fetch and re-run", file=sys.stderr)
            return EXIT_CANNOT_MEASURE
        write_baseline(args.baseline, data, args.mode, node, scan)
        if args.json:
            print(json.dumps({"mode": args.mode, "written": str(args.baseline),
                              "entries": len(scan.findings), "exit": EXIT_CLEAN}))
            return EXIT_CLEAN
        print(f"Baseline written: {args.baseline} ({args.mode}"
              f"{'' if args.mode == 'remote' else ' ' + node}: {len(scan.findings)} entries)")
        return EXIT_CLEAN

    entries = section(data, args.mode, node)
    problems = validate_section(entries, exempt if args.mode == "remote" else {})
    stale = apply_baseline(scan, entries)
    failing = [f for f in scan.findings if f.status in ("NEW", "GROWTH")]
    if failing or problems:
        code = EXIT_FINDINGS
    elif scan.unmeasured:
        code = EXIT_CANNOT_MEASURE
    else:
        code = EXIT_CLEAN

    if args.json:
        print(json.dumps({
            "mode": args.mode,
            "remote": args.remote,
            "base": args.base,
            "base_sha": base_sha,
            "node": node if args.mode == "local" else None,
            "scanned": scan.scanned,
            "findings": [f.as_dict() for f in scan.findings],
            "in_flight": scan.in_flight,
            "uncertain": scan.uncertain,
            "unmeasured": scan.unmeasured,
            "stale": stale,
            "baseline_problems": problems,
            "exit": code,
        }, indent=2, ensure_ascii=False))
    else:
        _print_human(scan, args.remote, args.base, node, stale, problems, code)
    return code


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
