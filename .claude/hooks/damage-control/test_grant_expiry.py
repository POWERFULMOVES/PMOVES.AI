"""A Known Road grant expires with the job it was issued for.

Run: python .claude/hooks/damage-control/test_grant_expiry.py

THE DEFECT (measured 2026-09-23)
--------------------------------
known_roads.py called a reason "provable" when it matched a regex. Nothing ever
asked whether the PR it named was still open, so a grant outlived its job
indefinitely: `compose:pr:3101` stayed in .known-road-active after PR #3101 merged
on 2026-09-20 and silently authorised compose edits made for PR #3143. The trail
rows for that work name the wrong PR.

WHAT THIS PROVES
----------------
Every liveness outcome, with the network seam (`_gh_api_raw`) replaced by fixtures:
no test here reaches GitHub. The seam is the RAW API body, not a parsed verdict, so
the malformed-response cases exercise the real parser.

POSITIVE CONTROL. The stale-merged-PR case is also run against the pre-fix
known_roads.py, loaded from git at PRE_FIX (never by reverting this tree). It must
ALLOW there -- otherwise the refusal asserted here would prove nothing about the
fix. In a shallow clone that lacks the blob, the control reports SKIPPED by name.

Paths are assembled from parts at runtime so this file's own text cannot trip the
guard that reads it.

Exit: 0 all checks held · 1 a check failed
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
os.environ["CLAUDE_PROJECT_DIR"] = str(TREE)
os.environ.pop("KNOWN_ROAD", None)
sys.path.insert(0, str(HERE))

import known_roads as KR  # noqa: E402  -- the SAME instance the hooks import

# The commit this fix is based on: the last known_roads.py without liveness.
PRE_FIX = "f347ade1572d68bc0baf0084e1027cd79395e975"

_TMP = Path(tempfile.mkdtemp(prefix="kr-expiry-"))
_TRAIL = _TMP / "known-roads.jsonl"
_GRANT = _TMP / ".known-road-active"
_CACHE = _TMP / ".grant-state-cache.json"
KR._trail_path = lambda: _TRAIL
KR._grant_file = lambda: _GRANT
KR._cache_path = lambda: _CACHE

COMPOSE = "pmoves/docker-" + "compose.yml"
SCHEMA = "pmoves/contra" + "cts/schemas/z.schema.json"

CALLS = []


def body(number, state, merged=None, merged_at=None, closed_at=None, pr=True):
    doc = {"number": number, "state": state, "closed_at": closed_at}
    if pr:
        doc.update(merged=merged, merged_at=merged_at)
    return json.dumps(doc)


def serve(responses):
    """Install a fixture API: path-suffix -> raw body, or an Exception to raise."""
    def fake(api_path):
        CALLS.append(api_path)
        for suffix, resp in responses.items():
            if api_path.endswith(suffix):
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise KR.GrantUnverifiable("fixture has no response for " + api_path)
    KR._gh_api_raw = fake


def reset(grant_env=None, grant_file=None, file_age=0.0):
    CALLS.clear()
    for p in (_TRAIL, _GRANT, _CACHE):
        if p.exists():
            p.unlink()
    if grant_env is None:
        os.environ.pop("KNOWN_ROAD", None)
    else:
        os.environ["KNOWN_ROAD"] = grant_env
    if grant_file is not None:
        _GRANT.write_text(grant_file + "\n", encoding="utf-8")
        t = time.time() - file_age
        os.utime(_GRANT, (t, t))


def rows():
    if not _TRAIL.is_file():
        return []
    return [json.loads(x) for x in _TRAIL.read_text(encoding="utf-8").splitlines() if x.strip()]


failures = []
checks = 0


def check(label, cond, detail=""):
    global checks
    checks += 1
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        failures.append(label)
        if detail != "":
            print("         " + repr(detail)[:400])


def evaluate(path=COMPOSE):
    return KR.evaluate_known_road("Edit", path, path)


OPEN_PR = body(3200, "open", merged=False)
MERGED_PR = body(3101, "closed", merged=True, merged_at="2026-09-20T15:05:08Z",
                 closed_at="2026-09-20T15:05:08Z")
CLOSED_PR = body(3102, "closed", merged=False, closed_at="2026-09-21T10:00:00Z")
OPEN_ISSUE = body(42, "open", pr=False)
CLOSED_ISSUE = body(43, "closed", closed_at="2026-09-01T00:00:00Z", pr=False)
FIXTURES = {"/pulls/3200": OPEN_PR, "/pulls/3101": MERGED_PR, "/pulls/3102": CLOSED_PR,
            "/issues/42": OPEN_ISSUE, "/issues/43": CLOSED_ISSUE}


def main():
    serve(FIXTURES)

    print("-- referent state --")
    reset(grant_env="compose:pr:3200")
    ok, detail = evaluate()
    r = rows()
    check("an OPEN pr grant allows", ok, detail)
    check("... and records grant_state=open, grant_source=env",
          len(r) == 1 and (r[0].get("grant_state"), r[0].get("grant_source")) == ("open", "env"), r)
    check("... after asking the canonical repo's pulls endpoint",
          CALLS == ["repos/POWERFULMOVES/PMOVES.AI/pulls/3200"], CALLS)

    reset(grant_env="compose:pr:3101")
    ok, detail = evaluate()
    check("a MERGED pr grant refuses", not ok and detail, detail)
    check("... naming the PR, its state and its merge time",
          all(s in detail for s in ("#3101", "MERGED", "2026-09-20T15:05:08Z")), detail)
    check("... and telling the operator to clear or replace the grant",
          "Clear" in detail and ".known-road-active" in detail, detail)
    check("... and records nothing", rows() == [], rows())

    reset(grant_env="compose:pr:3102")
    ok, detail = evaluate()
    check("a CLOSED (unmerged) pr grant refuses", not ok and "CLOSED" in detail, detail)

    reset(grant_env="compose:issue:42")
    ok, detail = evaluate()
    check("an OPEN issue grant allows, via the issues endpoint",
          ok and CALLS == ["repos/POWERFULMOVES/PMOVES.AI/issues/42"], (ok, detail, CALLS))
    reset(grant_env="compose:issue:43")
    ok, detail = evaluate()
    check("a CLOSED issue grant refuses", not ok and "issue #43" in detail, detail)

    print("-- cannot verify: fail closed --")
    serve({"/pulls/3200": KR.GrantUnverifiable("gh api exited 1: HTTP 502")})
    reset(grant_env="compose:pr:3200")
    ok, detail = evaluate()
    check("an unverifiable grant refuses", not ok, detail)
    check("... with the distinct 'grant not verifiable' message and the cause",
          "grant not verifiable" in detail and "HTTP 502" in detail, detail)
    check("... naming the offline override", KR.OFFLINE_SUFFIX in detail, detail)

    # The REAL seam, from a fresh copy of the module (KR's is replaced), with gh
    # unreachable: no network is touched because there is no binary to run.
    old_path = os.environ.get("PATH", "")
    spec = importlib.util.spec_from_file_location("kr_pristine", HERE / "known_roads.py")
    pristine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pristine)
    try:
        os.environ["PATH"] = str(_TMP / "no-bin-here")
        try:
            pristine._gh_api_raw("repos/x/y/pulls/1")
            got = "no exception"
        except pristine.GrantUnverifiable as exc:
            got = str(exc)
    finally:
        os.environ["PATH"] = old_path
    check("the real seam with no gh on PATH raises GrantUnverifiable",
          got == "gh CLI not found on PATH", got)

    print("-- malformed API responses refuse --")
    bad = {
        "not JSON": "<html>login</html>",
        "not an object": "[1, 2]",
        "wrong number": body(9999, "open", merged=False),
        "missing state": json.dumps({"number": 3200, "merged": False}),
        "unknown state": body(3200, "draft", merged=False),
        "merged not a bool": body(3200, "closed", merged="yes"),
        "open AND merged": body(3200, "open", merged=True),
    }
    for label, raw in bad.items():
        serve({"/pulls/3200": raw})
        reset(grant_env="compose:pr:3200")
        ok, detail = evaluate()
        check("malformed (%s) refuses as unverifiable" % label,
              not ok and "malformed API response" in detail, detail)
    check("... and no malformed response was cached", not _CACHE.exists())

    print("-- offline override --")
    serve(FIXTURES)
    reset(grant_env="compose:pr:3101" + KR.OFFLINE_SUFFIX)
    ok, detail = evaluate()
    r = rows()
    check("!offline allows without any lookup", ok and CALLS == [], (ok, detail, CALLS))
    check("... records grant_state=offline-override",
          len(r) == 1 and r[0].get("grant_state") == "offline-override", r)
    check("... and records the BARE reason, so rows still group by pr",
          len(r) == 1 and r[0].get("reason") == "pr:3101", r)
    reset(grant_env="compose:handoff:x.md" + KR.OFFLINE_SUFFIX)
    ok, detail = evaluate()
    check("!offline on a handoff reason refuses (nothing to skip)",
          not ok and "applies only to pr:/issue:" in detail, detail)
    reset(grant_file="compose:pr:3200" + KR.OFFLINE_SUFFIX,
          file_age=KR.GRANT_MAX_AGE_SECONDS + 3600)
    ok, detail = evaluate()
    check("!offline never lifts the age limit", not ok and "old" in detail, detail)

    print("-- age limit (file grant) --")
    reset(grant_file="compose:pr:3200", file_age=60)
    ok, detail = evaluate()
    r = rows()
    check("a fresh file grant on an open PR allows", ok, detail)
    check("... and records grant_source=file",
          len(r) == 1 and r[0].get("grant_source") == "file", r)
    reset(grant_file="compose:pr:3200", file_age=KR.GRANT_MAX_AGE_SECONDS + 60)
    ok, detail = evaluate()
    check("a file grant past the age limit refuses EVEN THOUGH the PR is open",
          not ok and "old (limit 24h)" in detail, detail)
    check("... without spending an API call", CALLS == [], CALLS)
    reset(grant_file="compose:pr:3200", file_age=-(KR.GRANT_FUTURE_SKEW_SECONDS + 3600))
    ok, detail = evaluate()
    check("a future-dated grant file refuses (it would never age out)",
          not ok and "future" in detail, detail)

    print("-- cache --")
    serve(FIXTURES)
    reset(grant_env="compose:pr:3200")
    evaluate()
    evaluate()
    check("a cache hit avoids the second lookup", len(CALLS) == 1, CALLS)
    doc = json.loads(_CACHE.read_text(encoding="utf-8"))
    key = "POWERFULMOVES/PMOVES.AI#pr:3200"
    doc[key]["checked"] = time.time() - KR.STATE_CACHE_TTL_SECONDS - 1
    _CACHE.write_text(json.dumps(doc), encoding="utf-8")
    evaluate()
    check("an entry older than the TTL is re-checked", len(CALLS) == 2, CALLS)

    reset(grant_env="compose:pr:3101")
    _CACHE.write_text(json.dumps({"POWERFULMOVES/PMOVES.AI#pr:3101":
                                  {"state": "open", "checked": time.time() + 3600}}),
                      encoding="utf-8")
    ok, detail = evaluate()
    check("a future-dated 'open' cache entry is ignored, and the merge is seen",
          not ok and CALLS == ["repos/POWERFULMOVES/PMOVES.AI/pulls/3101"], (detail, CALLS))

    serve({"/pulls/3200": KR.GrantUnverifiable("timed out")})
    reset(grant_env="compose:pr:3200")
    evaluate()
    serve(FIXTURES)
    ok, _ = evaluate()
    check("a FAILED lookup is not cached: the next call asks again and allows",
          ok and len(CALLS) == 2, CALLS)

    print("-- the lookup only runs when the grant is relevant --")
    reset(grant_env="compose:pr:3200")
    ok, detail = evaluate(SCHEMA)
    check("a compose grant consulted for a schema path makes NO API call",
          (ok, detail) == (False, "") and CALLS == [], (ok, detail, CALLS))
    reset()
    ok, detail = evaluate()
    check("no grant at all makes no API call", (ok, detail) == (False, "") and CALLS == [],
          CALLS)

    print("-- handoff briefs must be tracked by git --")
    repo = _TMP / "repo"
    (repo / "pmoves" / "docs" / "handoffs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    brief = repo / "pmoves" / "docs" / "handoffs" / "brief.md"
    brief.write_text("# brief\n", encoding="utf-8")
    os.environ["CLAUDE_PROJECT_DIR"] = str(repo)
    try:
        reset(grant_env="compose:handoff:brief.md")
        ok, detail = evaluate()
        check("an UNTRACKED brief refuses", not ok and "not tracked by git" in detail, detail)
        subprocess.run(["git", "-C", str(repo), "add", "--", str(brief)], check=True)
        ok, detail = evaluate()
        r = rows()
        check("the same brief once `git add`ed allows", ok, detail)
        check("... recording grant_state=handoff-present",
              len(r) == 1 and r[0].get("grant_state") == "handoff-present", r)
        check("... with no API call", CALLS == [], CALLS)
    finally:
        os.environ["CLAUDE_PROJECT_DIR"] = str(TREE)

    print("-- the Bash guard's opaque-verb tripwire --")
    spec = importlib.util.spec_from_file_location("dc_expiry", HERE / "bash-tool-damage-control.py")
    dc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dc)
    cfg = dc.load_config()
    verbs = cfg.get("opaqueWriteVerbs") or []
    opaque = "git " + "apply change.diff"
    serve(FIXTURES)
    reset(grant_env="compose:pr:3101")
    blocked, ask, reason = dc.check_command(opaque, cfg)
    if verbs:
        check("a void grant does not silence the tripwire (it still asks)",
              ask and not blocked, (blocked, ask, reason))
        check("... and the prompt says the grant is NOT honoured and why",
              "NOT honoured" in reason and "MERGED" in reason, reason)
        reset(grant_env="compose:pr:3200")
        blocked, ask, reason = dc.check_command(opaque, cfg)
        r = rows()
        check("a live grant passes the tripwire and records its state",
              not blocked and not ask and len(r) == 1
              and r[0].get("grant_state") == "open", (blocked, ask, r))
    else:
        check("patterns.yaml still declares opaqueWriteVerbs", False, "none found")

    print("-- the cache has the grant file's protection (and its known gap) --")
    reset()
    cache_name = ".grant-state-" + "cache.json"
    blocked, _ask, reason = dc.check_command("echo '{}' > " + cache_name, cfg)
    check("a Bash write to the cache by bare name is blocked", blocked, reason)
    spec = importlib.util.spec_from_file_location("wr_expiry", HERE / "write-tool-damage-control.py")
    wr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wr)
    wr_blocked, wr_reason, _wr_ask = wr.check_path(str(HERE / cache_name), wr.load_config())
    check("the Write guard refuses the cache by full path", wr_blocked, wr_reason)
    # KNOWN GAP (patterns.yaml, beside the entry): a basename glob does not reach a
    # directory-prefixed target in the Bash guard. Measured and printed, NOT
    # asserted -- the grant file has the same gap, and closing it is a separate
    # guard change. When that lands, turn this into an assertion.
    cache_rel = ".claude/hooks/damage-" + "control/" + cache_name
    gap_blocked, _a, _r = dc.check_command("echo '{}' > " + cache_rel, cfg)
    print("  info  directory-prefixed Bash write to the cache blocked=%s "
          "(known gap when False)" % gap_blocked)

    print("-- POSITIVE CONTROL: the pre-fix guard honours the stale grant --")
    blob = subprocess.run(
        ["git", "-C", str(TREE), "show", PRE_FIX + ":.claude/hooks/damage-control/known_roads.py"],
        capture_output=True, text=True)
    if blob.returncode != 0:
        print("  SKIPPED  positive control: pre-fix blob %s is not in this clone "
              "(shallow checkout?) -- the control was NOT measured here" % PRE_FIX[:9])
    else:
        old_file = _TMP / "known_roads_prefix.py"
        old_file.write_text(blob.stdout, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("known_roads_prefix", old_file)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        old._trail_path = lambda: _TMP / "prefix-trail.jsonl"
        old._grant_file = lambda: _TMP / "prefix-no-grant"
        reset(grant_env="compose:pr:3101")
        old_ok, old_detail = old.evaluate_known_road("Edit", COMPOSE, COMPOSE)
        check("control: PRE-FIX guard ALLOWS the merged-PR grant (the bug)", old_ok, old_detail)
        serve(FIXTURES)
        new_ok, new_detail = evaluate()
        check("control: the fixed guard refuses the SAME grant on the SAME path",
              not new_ok and "MERGED" in new_detail, new_detail)

    os.environ.pop("KNOWN_ROAD", None)
    print()
    if failures:
        print("FAIL: %d of %d checks failed." % (len(failures), checks))
        return 1
    print("PASS — all %d checks." % checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
