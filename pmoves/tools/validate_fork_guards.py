#!/usr/bin/env python3
"""No self-hosted job may be reachable from a fork's pull request without a guard.

Why this is a gate and not a convention
---------------------------------------
Six workflows already guard this, in THREE mutually incompatible spellings:

    github.event.pull_request.head.repo.full_name == github.repository
        -- claude-code-review.yml, kilocode-review.yml
    github.event_name != 'pull_request'
        -- integrations-ghcr.yml, self-hosted-builds.yml,
           self-hosted-builds-hardened.yml
    github.event_name != 'pull_request' || ...head.repo.fork == false
        -- branch-trail-emit.yml

Not one of them asserted the invariant. So the seventh case -- submodule-smoke.yml,
whose `smoke-test` job runs on `[self-hosted, Linux, X64, ai-lab]`, a label its own
comment says "spans b850 (X64) and spark (ARM64)" -- shipped with no fork test at
all, gated only by a `upstream-update` PR label. `pull_request` (not
`pull_request_target`) checks out the PR's OWN code, so a maintainer applying a
label whose name implies "submodule bump" would have executed untrusted fork code
on physical fleet hardware, with a write-default token and non-ephemeral runners.

A convention protects only the files whoever wrote it remembered. That is why the
seventh case was invisible, and why an eighth would reopen it. This file is the
thing that checks.

Why it parses YAML instead of grepping
--------------------------------------
`grep -l self-hosted .github/workflows/*.yml` matches 22 files. Parsing `runs-on`
per job finds 30 self-hosted jobs in 14 files. The difference is comments, prose,
and runner-label discussion -- a grep hit proves a STRING IS PRESENT, not WHICH
KEY OWNS IT. A grep-based version of this gate would be a check that cannot do
what its name implies, which is the defect class this file exists to close.

What counts as reachable
------------------------
A self-hosted job is fork-reachable when its workflow triggers on `pull_request`
or `pull_request_target`. Everything else -- push, schedule, workflow_dispatch,
create, delete -- cannot be initiated by a fork, so those jobs are reported as
NOT-REACHABLE rather than silently skipped: "I checked and it is out of reach" and
"I did not look" are different claims.

`workflow_call` is followed. A reusable workflow with a self-hosted job is
reachable if any CALLER is pull_request-triggered. Currently zero such callers
exist; the traversal is here so the eighth case cannot arrive through that door.

What counts as a guard
----------------------
Guards are evaluated as BOOLEAN STRUCTURE, not substrings. `A || B` guards only if
BOTH disjuncts guard; `A && B` guards if EITHER conjunct guards. So

    github.event_name != 'pull_request' || contains(labels, 'gpu-build')

is correctly NOT a guard, even though its first half is one -- a substring matcher
would have passed it.

Recognised guard atoms:
    github.event_name != '<every fork-reachable trigger this workflow has>'
    github.event_name == '<some event that is not fork-reachable>'
    github.event.pull_request.head.repo.full_name == github.repository  (either order)
    github.event.pull_request.head.repo.fork == false  /  != true  /  !<that>
    github.event.pull_request.head.repo.id == github.repository_id      (either order)

Deliberately NOT accepted, because they read like guards and are not:
    github.repository_owner == '<owner>'   -- identical on a fork PR; the base
                                              repo owns the context, not the head
    github.actor == '<someone>'            -- a different control entirely, and
                                              useless against the actual threat
                                              here, which is a TRUSTED maintainer
                                              labelling an untrusted fork PR

A guard on an upstream job propagates through `needs`: when the guarded job is
skipped, its dependents skip too. That propagation is cut when the dependent's own
`if` calls a status function (always/cancelled/failure/success), because those run
the job even when a dependency was skipped.

No opt-out marker
-----------------
Sibling gates in this tree (validate_runner_labels.py) offer a declared opt-out so
they do not cry wolf. This one does not, on purpose. The whole surface is 30
self-hosted jobs of which 5 are fork-reachable; an escape hatch nothing needs today
is just a pre-built hole for tomorrow. If a legitimate exception ever appears, add
its spelling to GUARD_ATOMS in a reviewed PR -- which is the conversation that
should happen anyway.

Usage
-----
    python pmoves/tools/validate_fork_guards.py            # report + exit 1 on findings
    python pmoves/tools/validate_fork_guards.py --quiet    # findings only
    python pmoves/tools/validate_fork_guards.py --workflows <dir>

Exit codes
----------
    0  every fork-reachable self-hosted job is guarded
    1  at least one is not (or could not be verified)
    3  could not measure -- the workflow directory is missing or unreadable

3, not 2: argparse already owns 2, and so does "the interpreter failed to start".
A caller that treated 2 as a finding could not tell a finding from a dead tool.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# Triggers a fork can initiate against this repository. `pull_request` runs the
# fork's OWN code and is the exposure this gate exists for. `pull_request_target`
# runs base code but with full secrets, and on non-ephemeral self-hosted hardware
# that is still a fork-influenced execution -- included so the door is shut before
# someone walks through it. Zero self-hosted jobs use it today.
FORK_TRIGGERS = frozenset({"pull_request", "pull_request_target"})

# Status functions that make a job run even when a dependency was SKIPPED, which
# is precisely how an upstream guard stops propagating.
STATUS_FUNCS = re.compile(r"\b(always|cancelled|failure|success)\s*\(")

# Atoms that, on their own, imply "this is not a fork's pull request".
# Matched against a whitespace-stripped, single-quote-normalised form.
GUARD_ATOMS = (
    re.compile(r"github\.event\.pull_request\.head\.repo\.full_name==github\.repository"),
    re.compile(r"github\.repository==github\.event\.pull_request\.head\.repo\.full_name"),
    re.compile(r"github\.event\.pull_request\.head\.repo\.id==github\.repository_id"),
    re.compile(r"github\.repository_id==github\.event\.pull_request\.head\.repo\.id"),
    re.compile(r"github\.event\.pull_request\.head\.repo\.fork==false"),
    re.compile(r"false==github\.event\.pull_request\.head\.repo\.fork"),
    re.compile(r"github\.event\.pull_request\.head\.repo\.fork!=true"),
    re.compile(r"^!github\.event\.pull_request\.head\.repo\.fork$"),
)

_EVENT_NE = re.compile(r"github\.event_name!='([a-z_]+)'")
_EVENT_EQ = re.compile(r"github\.event_name=='([a-z_]+)'")


# --------------------------------------------------------------------------- #
# expression structure
# --------------------------------------------------------------------------- #
def _normalise(cond) -> str:
    """Strip the ${{ }} wrapper, unify quotes, and remove whitespace.

    Whitespace removal is what lets one regex match `a == b`, `a==b` and the
    multi-line folded form YAML hands back for a `>`-style condition.
    """
    if isinstance(cond, bool):
        return "true" if cond else "false"
    text = str(cond).strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2]
    text = text.replace('"', "'")
    return re.sub(r"\s+", "", text)


def _split_top_level(expr: str, op: str) -> list[str]:
    """Split on `op` at paren depth 0, ignoring operators inside string literals.

    Splitting with str.split would break `contains(a, 'x || y')` and would treat
    a parenthesised sub-expression as top level -- both of which turn a non-guard
    into an apparent guard.
    """
    parts: list[str] = []
    depth = 0
    in_str = False
    buf: list[str] = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if in_str:
            buf.append(ch)
            if ch == "'":
                in_str = False
            i += 1
            continue
        if ch == "'":
            in_str = True
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and expr.startswith(op, i):
            parts.append("".join(buf))
            buf = []
            i += len(op)
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [p for p in (s.strip() for s in parts) if p]


def _strip_outer_parens(atom: str) -> str:
    while atom.startswith("(") and atom.endswith(")"):
        inner = atom[1:-1]
        if _split_top_level(inner, ")") and inner.count("(") == inner.count(")"):
            atom = inner
        else:
            break
    return atom


def _atom_guards(atom: str, fork_triggers: frozenset[str]) -> bool:
    """Does this single atom imply 'not a fork pull request'?"""
    atom = _strip_outer_parens(atom)
    if any(p.search(atom) for p in GUARD_ATOMS):
        return True
    # `event_name == 'push'` guards when push is not a fork-reachable trigger.
    eq = _EVENT_EQ.findall(atom)
    if eq and not (set(eq) & fork_triggers):
        return True
    return False


def _conjunction_guards(conj: str, fork_triggers: frozenset[str]) -> bool:
    """A conjunction guards if ANY conjunct does -- or if its `!=` atoms,
    taken together, exclude every fork-reachable trigger the workflow has."""
    atoms = _split_top_level(conj, "&&")
    if any(_atom_guards(a, fork_triggers) for a in atoms):
        return True
    excluded = {e for a in atoms for e in _EVENT_NE.findall(_strip_outer_parens(a))}
    return bool(fork_triggers) and fork_triggers <= excluded


def condition_guards(cond, fork_triggers: frozenset[str]) -> bool:
    """A condition guards iff EVERY top-level disjunct guards."""
    if cond is None:
        return False
    expr = _normalise(cond)
    if not expr:
        return False
    disjuncts = _split_top_level(expr, "||")
    return bool(disjuncts) and all(
        _conjunction_guards(d, fork_triggers) for d in disjuncts
    )


# --------------------------------------------------------------------------- #
# workflow model
# --------------------------------------------------------------------------- #
def _triggers(doc: dict) -> list[str]:
    """`on:` parses as the boolean True under YAML 1.1, which is why this is not
    a plain doc.get("on")."""
    on = doc.get("on", doc.get(True))
    if isinstance(on, dict):
        return [str(k) for k in on]
    if isinstance(on, str):
        return [on]
    if isinstance(on, list):
        return [str(x) for x in on]
    return []


def _runs_on_labels(runs_on) -> list[str] | None:
    """Normalise every runs-on spelling into a label list. None when absent
    (a job that only `uses:` a reusable workflow has no runs-on of its own)."""
    if runs_on is None:
        return None
    if isinstance(runs_on, str):
        return [runs_on.strip()]
    if isinstance(runs_on, list):
        return [str(x).strip() for x in runs_on if str(x).strip()]
    if isinstance(runs_on, dict):  # {group:, labels:}
        out: list[str] = []
        group = runs_on.get("group")
        if group:
            out.append(f"group:{group}")
        labels = runs_on.get("labels")
        if isinstance(labels, list):
            out += [str(x).strip() for x in labels]
        elif isinstance(labels, str):
            out.append(labels.strip())
        return out
    return [str(runs_on)]


def _is_disabled(job: dict) -> bool:
    """A job whose `if` is a LEADING literal false cannot run, so its runs-on is
    not a finding. `github.x == false` is a real predicate, not a disable."""
    cond = job.get("if")
    if cond is False:
        return True
    if not isinstance(cond, str):
        return False
    return re.match(r"^\s*\$?\{?\{?\s*false\s*(&&|\}|$)", cond) is not None


def _job_line(text: str, job: str) -> int:
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith(f"  {job}:"):
            return i
    return 0


def _needs(job: dict) -> list[str]:
    n = job.get("needs")
    if isinstance(n, str):
        return [n]
    if isinstance(n, list):
        return [str(x) for x in n]
    return []


def _guarded(job_name: str, jobs: dict, fork_triggers: frozenset[str],
             seen: frozenset[str] = frozenset()) -> bool:
    """Guarded directly, or transitively via a guarded `needs` dependency."""
    if job_name in seen:
        return False
    job = jobs.get(job_name)
    if not isinstance(job, dict):
        return False
    if condition_guards(job.get("if"), fork_triggers):
        return True
    own = job.get("if")
    if isinstance(own, str) and STATUS_FUNCS.search(own):
        # Runs even when a dependency was skipped, so no upstream guard reaches it.
        return False
    return any(
        _guarded(dep, jobs, fork_triggers, seen | {job_name})
        for dep in _needs(job)
    )


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #
def analyse(workflows: Path):
    """Returns (findings, guarded, unreachable, unparseable, total_self_hosted)."""
    parsed: dict[str, dict] = {}
    texts: dict[str, str] = {}
    unparseable: list[str] = []

    for wf in sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml")):
        text = wf.read_text(encoding="utf-8", errors="replace")
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            unparseable.append(f"{wf.name}: unparseable ({str(exc)[:80]})")
            continue
        if isinstance(doc, dict):
            parsed[wf.name] = doc
            texts[wf.name] = text

    # Which reusable workflows are invoked from a fork-reachable caller?
    called_from_fork: set[str] = set()
    for name, doc in parsed.items():
        if not set(_triggers(doc)) & FORK_TRIGGERS:
            continue
        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job in jobs.values():
            if isinstance(job, dict) and isinstance(job.get("uses"), str):
                called_from_fork.add(Path(job["uses"].split("@")[0]).name)

    findings: list[str] = []
    guarded: list[str] = []
    unreachable: list[str] = []
    total_self_hosted = 0

    for name, doc in parsed.items():
        triggers = set(_triggers(doc))
        fork_triggers = frozenset(triggers & FORK_TRIGGERS)
        via_call = "workflow_call" in triggers and name in called_from_fork
        if via_call and not fork_triggers:
            # Reachability is the caller's; the guard spellings are the same.
            fork_triggers = frozenset({"pull_request"})

        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            continue

        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            labels = _runs_on_labels(job.get("runs-on"))
            if labels is None or not any("self-hosted" in l for l in labels):
                continue
            total_self_hosted += 1
            where = f"{name}:{_job_line(texts[name], str(job_name))} ({job_name})"

            if _is_disabled(job):
                unreachable.append(f"{where}: job is disabled (`if: false`)")
                continue
            if not fork_triggers:
                unreachable.append(
                    f"{where}: not fork-reachable — triggers {sorted(triggers)}"
                )
                continue
            if _guarded(str(job_name), jobs, fork_triggers):
                guarded.append(f"{where}: guarded")
                continue
            findings.append(
                f"{where}: runs on {labels} and is reachable from a FORK "
                f"pull request with no fork guard"
                + (" (reached via workflow_call)" if via_call else "")
                + f" — if: {job.get('if')!r}"
            )

    return findings, guarded, unreachable, unparseable, total_self_hosted


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workflows", default=str(WORKFLOWS),
                    help="workflow directory to scan")
    ap.add_argument("--quiet", action="store_true",
                    help="print findings only, not the guarded/unreachable inventory")
    args = ap.parse_args(argv)

    workflows = Path(args.workflows)
    if not workflows.is_dir():
        print(f"COULD-NOT-MEASURE: {workflows} is not a directory", file=sys.stderr)
        return 3

    findings, guarded, unreachable, unparseable, total = analyse(workflows)

    # Checked BEFORE the empty-tree return: a workflow the gate cannot read is a
    # hole in coverage at any sample size, and it must be NAMED. Ordering this
    # after the total==0 return meant a tree whose only workflow was unparseable
    # reported "found nothing to check" and never said which file it choked on.
    if unparseable:
        for f in sorted(unparseable):
            print(f"UNPARSEABLE:  {f}")
        print(f"\n{len(unparseable)} workflow(s) could not be parsed, so their "
              f"self-hosted jobs were never examined.")
        return 1

    if total == 0:
        # An empty result reads the same whether the input was clean or absent.
        print(f"COULD-NOT-MEASURE: no self-hosted job found under {workflows} — "
              f"a zero here means the scan found nothing to check, not that "
              f"everything passed", file=sys.stderr)
        return 3

    if not args.quiet:
        for g in sorted(guarded):
            print(f"GUARDED:      {g}")
        for u in sorted(unreachable):
            print(f"NOT-REACHABLE: {u}")

    for f in sorted(findings):
        print(f"UNGUARDED:    {f}")

    # Both input sizes beside the result: a bare "0 findings" cannot distinguish
    # a clean tree from a scan that read nothing.
    print(
        f"\n{total} self-hosted job(s) examined: "
        f"{len(guarded)} guarded, {len(unreachable)} not fork-reachable, "
        f"{len(findings)} UNGUARDED."
    )

    if findings:
        print(
            "\n::error::A self-hosted job is reachable from a fork's pull request "
            "without a fork guard. Fork PR code would execute on fleet hardware. "
            "Add one of: "
            "`github.event.pull_request.head.repo.full_name == github.repository` "
            "or `github.event_name != 'pull_request'` to the job's `if`."
        )
        return 1

    print("OK: every fork-reachable self-hosted job has a fork guard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
