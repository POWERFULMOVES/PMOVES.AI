#!/usr/bin/env python3
"""Report commits that reached a protected branch without a pull request.

WHY THIS EXISTS
---------------
`main` is protected with `required approvals: 1` and `strict: true`, but
`enforce_admins: false` and the `[ main ]` ruleset grants `RepositoryRole`
a bypass of mode `always`. Admin-role actors therefore push straight to
`main`, and nothing records that they did.

Measured 2026-08-26 over the last 200 commits: 13 direct pushes -- 9 by
Agent Zero, 2 by POWERFULMOVES, 2 by Mavis.

MOST OF THOSE ARE FINE AND MUST STAY FINE. Eleven were `docs(agnote)`
updates to the coordination ledger. A claim register that needs PR latency
to record a claim defeats the Village Rule it enforces, so the ledger keeps
its bypass. This tool therefore does NOT flag direct pushes as such.

It flags direct pushes that touch something OTHER than the ledger. One did:
`1b98d01a3` rewrote 173 lines of `pmoves/tensorzero/config/tensorzero.toml`
-- live model routing -- with no PR, no review, and no required check.

DETECTIVE, NOT PREVENTIVE. A ruleset cannot scope a bypass by path, so this
cannot be enforced at push time without removing the ledger exception. It
reports after the fact instead, which is the honest thing a gate can do here
rather than pretending to prevent what it cannot.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

#: Paths a bypassing actor may write without review. Deliberately narrow:
#: the coordination ledger, and nothing else.
LEDGER_PREFIXES = ("pmoves/docs/AGENTS/",)


def _gh(args: list[str]) -> str:
    """Call gh, returning stdout. Empty string on failure -- a network fault
    must not be reported as 'no associated PR', which would invent findings."""
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True, encoding="utf-8"
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


def has_associated_pr(repo: str, sha: str) -> bool:
    """Whether GitHub associates this commit with a pull request.

    Asked of the API rather than inferred from the commit subject. A squash
    merge happens to append '(#N)', but that is a formatting convention an
    author can reproduce by hand -- keying on it would let anyone opt out of
    this audit by typing a PR number into a direct push.
    """
    out = _gh(["api", f"repos/{repo}/commits/{sha}/pulls",
               "-H", "Accept: application/vnd.github+json"])
    return bool(json.loads(out or "[]"))


def changed_paths(sha: str) -> list[str]:
    out = subprocess.run(
        ["git", "show", "--pretty=", "--name-only", sha],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def is_merge_commit(sha: str) -> bool:
    out = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", sha],
        capture_output=True, text=True, encoding="utf-8",
    ).stdout.split()
    return len(out) > 2


def audit(repo: str, rev_range: str) -> list[dict]:
    """Commits in `rev_range` that landed with no PR and touched non-ledger paths."""
    shas = subprocess.run(
        ["git", "rev-list", rev_range],
        capture_output=True, text=True, encoding="utf-8",
    ).stdout.split()

    findings: list[dict] = []
    for sha in shas:
        if is_merge_commit(sha):
            continue
        if has_associated_pr(repo, sha):
            continue
        paths = changed_paths(sha)
        outside = [p for p in paths if not p.startswith(LEDGER_PREFIXES)]
        if not outside:
            continue  # ledger-only: the sanctioned exception
        meta = subprocess.run(
            ["git", "show", "-s", "--format=%an|%ad|%s", "--date=short", sha],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout.strip().split("|", 2)
        findings.append({
            "sha": sha,
            "author": meta[0] if meta else "?",
            "date": meta[1] if len(meta) > 1 else "?",
            "subject": meta[2] if len(meta) > 2 else "?",
            "files_outside_ledger": sorted(outside)[:20],
            "files_outside_ledger_count": len(outside),
        })
    return findings


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default="POWERFULMOVES/PMOVES.AI")
    ap.add_argument("--range", dest="rev_range", default="HEAD~50..HEAD",
                    help="git rev-list range to audit (default: HEAD~50..HEAD)")
    ap.add_argument("--json-out", help="write findings JSON here; '-' for stdout")
    args = ap.parse_args(argv)

    try:
        findings = audit(args.repo, args.rev_range)
    except RuntimeError as exc:
        # Fail LOUDLY on an API fault. Reporting "no findings" because the
        # network was down is precisely the silent-green failure this repo
        # keeps hitting.
        print(f"unreviewed-push-audit: could not complete: {exc}", file=sys.stderr)
        return 2

    if args.json_out:
        payload = json.dumps(findings, indent=2)
        if args.json_out == "-":
            print(payload)
        else:
            with open(args.json_out, "w", encoding="utf-8") as handle:
                handle.write(payload + "\n")

    if not findings:
        print(f"No unreviewed non-ledger commits in {args.rev_range}.")
        return 0

    print(f"{len(findings)} commit(s) reached the branch with no pull request "
          f"and changed files outside {LEDGER_PREFIXES[0]}:\n")
    for f in findings:
        print(f"  {f['sha'][:9]}  {f['date']}  {f['author']}")
        print(f"      {f['subject'][:88]}")
        print(f"      {f['files_outside_ledger_count']} file(s) outside the ledger:")
        for p in f["files_outside_ledger"]:
            print(f"        - {p}")
        print()
    print("These bypassed required review and every required check. Review them "
          "retroactively, or narrow the ruleset bypass.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
