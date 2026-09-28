"""tests/test_branch_protection_sync_policy.py

Executes the SHIPPED "Apply standard branch protection" run block of
.github/workflows/branch-protection-sync.yml against a stubbed `gh` that
models GitHub's measured PUT semantics: a field the body OMITS keeps its
existing value.

Why this exists (2026-09-23): policy() omitted require_last_push_approval
while a separate intended() set it false. The dry run therefore predicted
"reviews.require_last_push_approval: true -> false", the live PUT (run
35898033986) returned 2xx, and read-back showed 40 hardened branches still at
true -- which BLOCKS every solo-operator merge even at 0 required reviews.
Nothing in the workflow looked at the result of its own write.

The pre-existing tests in test_branch_protection_workflows.py grep the YAML.
Grep could not have caught this: every string was present, just in the wrong
function. So these tests RUN the block.

Groups:
    P. PolicyBodyTests     -- the PUT body sends every owned field, false
    D. DryEqualsLiveTests  -- the dry-run prediction equals the PUT body's
                              effect, and the prediction comes true
    R. ReadBackTests       -- a field that does not land is FAILED (exit 1)
                              and named; an unseen read-back is exit 3
    C. PositiveControl     -- the pre-fix workflow, through the same harness,
                              omits last_push and leaves it true while
                              reporting success (read via `git show`, never by
                              reverting the worktree)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF_REL = ".github/workflows/branch-protection-sync.yml"
WF = ROOT / WF_REL
STEP = "Apply standard branch protection"
# Last commit on main that touched the workflow BEFORE this fix.
PRE_FIX_SHA = "00f9f30d0"

HAVE_TOOLS = bool(shutil.which("jq")) and bool(shutil.which("bash"))

# ---------------------------------------------------------------------------
# Stub gh: GET returns the stored protection; PUT merges the body into it with
# GitHub's keep-omitted-field semantics and records the exact body sent.
# STUB_IGNORE=reviews.<field>,<field> models GitHub silently not applying a
# field (the read-back must catch it). STUB_READBACK_FAIL=1 makes every GET
# after a PUT fail (could-not-measure).
# ---------------------------------------------------------------------------
STUB_GH = textwrap.dedent(r'''
    #!/usr/bin/env python3
    import json, os, re, sys
    state = os.environ["STUB_STATE"]
    args = sys.argv[1:]
    if not args or args[0] != "api":
        sys.stderr.write("stub gh: unsupported %r\n" % args); sys.exit(2)
    method = "GET"
    if "-X" in args:
        method = args[args.index("-X") + 1]
    path = [a for a in args[1:] if a.startswith("repos/")][0]
    m = re.fullmatch(r"repos/([^/]+)/([^/]+)/branches/(.+)/protection", path)
    if not m:
        sys.stderr.write("stub gh: unsupported path %s\n" % path); sys.exit(2)
    repo, branch = m.group(2), m.group(3)
    f = os.path.join(state, repo + "@" + branch.replace("/", "%") + ".json")
    marker = f + ".put"
    if method == "GET":
        if os.environ.get("STUB_READBACK_FAIL") == "1" and os.path.exists(marker):
            sys.stderr.write("gh: Server Error (HTTP 502)\n"); sys.exit(1)
        if not os.path.exists(f):
            sys.stderr.write("gh: Branch not protected (HTTP 404)\n"); sys.exit(1)
        sys.stdout.write(open(f).read()); sys.exit(0)
    if method != "PUT":
        sys.stderr.write("stub gh: unsupported method %s\n" % method); sys.exit(2)
    body = json.load(sys.stdin)
    with open(os.path.join(state, "puts.jsonl"), "a") as log:
        log.write(json.dumps({"repo": repo, "branch": branch, "body": body}) + "\n")
    ignore = {x for x in os.environ.get("STUB_IGNORE", "").split(",") if x}
    cur = json.load(open(f)) if os.path.exists(f) else {}
    for k, v in body.items():
        if k in ignore:
            continue
        if k in ("required_status_checks", "restrictions"):
            if v is None:
                cur.pop(k, None)
            else:
                cur[k] = v
        elif k == "required_pull_request_reviews":
            if v is None:
                cur.pop(k, None)
                continue
            merged = dict(cur.get(k) or {})   # omitted sub-fields are KEPT
            for j, jv in v.items():
                if "reviews." + j not in ignore:
                    merged[j] = jv
            cur[k] = merged
        else:
            cur[k] = {"enabled": v}
    json.dump(cur, open(f, "w"))
    open(marker, "w").close()
    sys.stdout.write(json.dumps(cur)); sys.exit(0)
''').lstrip()


def _measured_hardened(contexts=None):
    """GET-shape protection matching the 2026-09-23 measurement of a hardened
    fork branch: reviews=0, conv=true, last_push=TRUE."""
    p = {
        "enforce_admins": {"enabled": False},
        "required_pull_request_reviews": {
            "required_approving_review_count": 0,
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "require_last_push_approval": True,
        },
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": True},
        "required_linear_history": {"enabled": False},
        "lock_branch": {"enabled": False},
        "block_creations": {"enabled": False},
        "allow_fork_syncing": {"enabled": False},
    }
    if contexts is not None:
        p["required_status_checks"] = {"strict": True, "contexts": contexts,
                                       "checks": [{"context": c, "app_id": None} for c in contexts]}
    return p


FIXTURE = {
    ("PMOVES-Agent-Zero", "PMOVES.AI-Edition-Hardened"): _measured_hardened(["ci / test"]),
    ("PMOVES-Archon", "PMOVES.AI-Edition-Hardened"): _measured_hardened(),
    ("PMOVES-DoX", "PMOVES.AI-Edition-Hardened/x"): _measured_hardened([]),
}


def _run_block(text: str) -> str:
    doc = yaml.safe_load(text)
    for step in doc["jobs"]["protect"]["steps"]:
        if step.get("name") == STEP:
            return step["run"]
    raise AssertionError(f"step {STEP!r} not found")


def _function(block: str, name: str) -> str:
    m = re.search(rf"^( *){re.escape(name)}\(\) \{{\n.*?^\1\}}\n", block, re.S | re.M)
    if not m:
        raise AssertionError(f"function {name}() not found in run block")
    return textwrap.dedent(m.group(0))


class Harness:
    def __init__(self, workflow_text: str):
        self.block = _run_block(workflow_text)
        self.tmp = Path(tempfile.mkdtemp(prefix="bpsync-"))
        self.bin = self.tmp / "bin"
        self.state = self.tmp / "state"
        self.bin.mkdir()
        self.state.mkdir()
        gh = self.bin / "gh"
        gh.write_text(STUB_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        (self.tmp / "step.sh").write_text(self.block)
        rows = "".join(f"{r}\t{b}\n" for (r, b) in FIXTURE)
        (self.tmp / "forks.tsv").write_text(rows)
        for (r, b), prot in FIXTURE.items():
            (self.state / f"{r}@{b.replace('/', '%')}.json").write_text(json.dumps(prot))

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run(self, dry: bool, **extra_env) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update({
            "PATH": f"{self.bin}:{os.environ.get('PATH', '')}",
            "STUB_STATE": str(self.state),
            "GH_TOKEN": "stub",
            "DRY_RUN": "true" if dry else "false",
            "ONLY_UNPROTECTED": "false",
            "REQUIRED_REVIEWS": "0",
            "OWNER": "POWERFULMOVES",
            "GITHUB_STEP_SUMMARY": str(self.tmp / "summary.md"),
        })
        env.update(extra_env)
        # Actions' default shell for run: bash --noprofile --norc -eo pipefail
        return subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "step.sh"],
                              cwd=self.tmp, env=env, capture_output=True, text=True, timeout=120)

    def puts(self):
        f = self.state / "puts.jsonl"
        if not f.exists():
            return []
        return [json.loads(line) for line in f.read_text().splitlines() if line.strip()]

    def stored(self, repo, branch):
        return json.loads((self.state / f"{repo}@{branch.replace('/', '%')}.json").read_text())

    def bash_fn(self, script: str, stdin: str = "") -> str:
        """Run the shipped policy()/normalize() definitions plus `script`."""
        prelude = _function(self.block, "policy") + _function(self.block, "normalize")
        out = subprocess.run(["bash", "-c", prelude + script], input=stdin, text=True,
                             capture_output=True, env={**os.environ, "REQUIRED_REVIEWS": "0"},
                             timeout=30)
        if out.returncode != 0:
            raise AssertionError(out.stderr)
        return out.stdout.strip()

    def normalize(self, prot: dict) -> dict:
        return json.loads(self.bash_fn("normalize", json.dumps(prot)))


def _flat_diff(a: dict, b: dict) -> set:
    """Field names that differ, reviews sub-fields named individually --
    the same naming the workflow's fielddiff() emits."""
    out = set()
    for k in set(a) | set(b):
        av, bv = a.get(k), b.get(k)
        if k == "required_pull_request_reviews" and isinstance(av, dict) and isinstance(bv, dict):
            out |= {f"reviews.{j}" for j in set(av) | set(bv) if av.get(j) != bv.get(j)}
        elif av != bv:
            out.add(k)
    return out


def _would_change(stdout: str) -> dict:
    """repo@branch -> set(fields) from the dry run's `~ ... WOULD change [...]` lines."""
    got = {}
    for m in re.finditer(r"^  ~ (\S+): .*? -> WOULD change \[([^\]]*)\]", stdout, re.M):
        got[m.group(1)] = set(filter(None, m.group(2).split(",")))
    for m in re.finditer(r"^  \. (\S+): .* -> no change", stdout, re.M):
        got[m.group(1)] = set()
    return got


@unittest.skipUnless(HAVE_TOOLS, "needs bash + jq")
class _Base(unittest.TestCase):
    workflow_text = None

    def setUp(self):
        self.h = Harness(self.workflow_text or WF.read_text(encoding="utf-8"))
        self.addCleanup(self.h.cleanup)


class PolicyBodyTests(_Base):
    def test_P1_put_body_sends_last_push_false_and_code_owner_false(self):
        r = self.h.run(dry=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        puts = self.h.puts()
        self.assertEqual(len(puts), len(FIXTURE), r.stdout)
        for p in puts:
            rpr = p["body"]["required_pull_request_reviews"]
            self.assertIn("require_last_push_approval", rpr, "omitted => GitHub keeps true")
            self.assertIs(rpr["require_last_push_approval"], False)
            self.assertIs(rpr["require_code_owner_reviews"], False)
            self.assertIs(p["body"]["lock_branch"], False)
            self.assertIs(p["body"]["block_creations"], False)

    def test_P2_policy_keys_equal_normalize_keys(self):
        """No owned field may be predicted-but-not-written or written-but-unverified."""
        body = json.loads(self.h.bash_fn("policy null"))
        norm = self.h.normalize({"required_pull_request_reviews": {}})
        self.assertEqual(set(body), set(norm))
        self.assertEqual(set(body["required_pull_request_reviews"]),
                         set(norm["required_pull_request_reviews"]))

    def test_P3_no_separate_intended_shape(self):
        self.assertNotRegex(self.h.block, r"^\s*intended\(\)\s*\{", "intended() must not come back")
        self.assertIn('printf \'%s\' "$want" | gh api -X PUT', self.h.block,
                      "the live PUT must send the same $want the dry run diffed")

    def test_P4_preserves_existing_required_checks(self):
        self.h.run(dry=False)
        by_repo = {p["repo"]: p["body"] for p in self.h.puts()}
        self.assertEqual(by_repo["PMOVES-Agent-Zero"]["required_status_checks"],
                         {"strict": True, "contexts": ["ci / test"]})
        self.assertIsNone(by_repo["PMOVES-Archon"]["required_status_checks"])


class DryEqualsLiveTests(_Base):
    def test_D1_dry_run_predicts_exactly_last_push_on_measured_state(self):
        r = self.h.run(dry=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        pred = _would_change(r.stdout)
        self.assertEqual(len(pred), len(FIXTURE), r.stdout)
        for rb, fields in pred.items():
            self.assertEqual(fields, {"reviews.require_last_push_approval"}, rb)
        self.assertEqual(self.h.puts(), [], "a dry run must never PUT")

    def test_D2_dry_run_diff_equals_put_body_and_comes_true(self):
        dry = self.h.run(dry=True)
        pred = _would_change(dry.stdout)
        live = self.h.run(dry=False)
        self.assertEqual(live.returncode, 0, live.stdout + live.stderr)
        for p in self.h.puts():
            rb = f"{p['repo']}@{p['branch']}"
            before = self.h.normalize(FIXTURE[(p["repo"], p["branch"])])
            self.assertEqual(pred[rb], _flat_diff(before, p["body"]),
                             f"{rb}: dry run predicted something other than what the PUT body changes")
            after = self.h.normalize(self.h.stored(p["repo"], p["branch"]))
            self.assertEqual(after, p["body"], f"{rb}: the write did not realise the prediction")
        self.assertIn("applied=3 skipped=0 failed=0 unreadable=0", live.stdout)

    def test_D3_second_dry_run_after_live_is_all_no_change(self):
        self.h.run(dry=False)
        r = self.h.run(dry=True)
        self.assertIn("would_change=0 no_change=3", r.stdout)

    def test_D4_unprotected_branch_gets_the_same_body(self):
        (self.h.tmp / "forks.tsv").write_text("PMOVES-Naked\tmain\n")
        r = self.h.run(dry=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body = self.h.puts()[0]["body"]
        self.assertIs(body["required_pull_request_reviews"]["require_last_push_approval"], False)
        self.assertEqual(self.h.normalize(self.h.stored("PMOVES-Naked", "main")), body)


class ReadBackTests(_Base):
    def test_R1_field_that_does_not_land_is_failed_and_named(self):
        r = self.h.run(dry=False, STUB_IGNORE="reviews.require_last_push_approval")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("reviews.require_last_push_approval=false->true", r.stdout)
        self.assertIn("applied=0 skipped=0 failed=3 unreadable=0", r.stdout)
        self.assertIn("::error title=branch-protection-sync: read-back mismatch::", r.stdout)

    def test_R2_top_level_field_that_does_not_land_is_failed(self):
        r = self.h.run(dry=False, STUB_IGNORE="required_conversation_resolution")
        # the fixture already has conv=true, so ignoring it is NOT a mismatch...
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # ...but ignoring a field whose value must change is.
        h2 = Harness(self.workflow_text or WF.read_text(encoding="utf-8"))
        self.addCleanup(h2.cleanup)
        (h2.tmp / "forks.tsv").write_text("PMOVES-Naked\tmain\n")
        r2 = h2.run(dry=False, STUB_IGNORE="required_conversation_resolution")
        self.assertEqual(r2.returncode, 1, r2.stdout + r2.stderr)
        self.assertIn("required_conversation_resolution=true->false", r2.stdout)

    def test_R3_unreadable_read_back_is_could_not_measure_not_applied(self):
        r = self.h.run(dry=False, STUB_READBACK_FAIL="1")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("applied=0 skipped=0 failed=0 unreadable=3", r.stdout)
        self.assertIn("written, result unverified", r.stdout)


def _pre_fix_text():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "show", f"{PRE_FIX_SHA}:{WF_REL}"],
                              capture_output=True, text=True, check=True, timeout=30).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


_PRE = _pre_fix_text()


@unittest.skipUnless(_PRE, f"pre-fix commit {PRE_FIX_SHA} not in this clone (shallow checkout)")
class PositiveControl(_Base):
    """The same harness against the pre-fix workflow reproduces the defect."""
    workflow_text = _PRE

    def test_C1_pre_fix_put_body_omits_last_push(self):
        r = self.h.run(dry=False)
        self.assertEqual(r.returncode, 0, "pre-fix run reported success")
        for p in self.h.puts():
            self.assertNotIn("require_last_push_approval", p["body"]["required_pull_request_reviews"])

    def test_C2_pre_fix_dry_run_predicts_a_change_the_write_never_makes(self):
        dry = self.h.run(dry=True)
        for rb, fields in _would_change(dry.stdout).items():
            self.assertIn("reviews.require_last_push_approval", fields, rb)
        self.h.run(dry=False)
        for (repo, branch) in FIXTURE:
            rpr = self.h.stored(repo, branch)["required_pull_request_reviews"]
            self.assertIs(rpr["require_last_push_approval"], True,
                          "keep-omitted-field semantics: last_push survives the pre-fix PUT")
        again = self.h.run(dry=True)
        self.assertIn("would_change=3", again.stdout, "pre-fix never converges")


if __name__ == "__main__":
    unittest.main()
