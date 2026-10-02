"""End-to-end: the Bash guard cannot be used to self-grant, and a protected
glob reaches a protected file at ANY depth.

    python .claude/hooks/damage-control/test_self_grant_and_depth.py [--ref <git-ref>]

With no argument the guard files BESIDE THIS FILE are tested. With --ref, the
guard, its helpers and patterns.yaml are materialized from that git ref instead
-- that is how the failing-before evidence was produced, against a throwaway
copy, without reverting any worktree:

    python .claude/hooks/damage-control/test_self_grant_and_depth.py --ref origin/main

WHAT WAS MEASURED ON origin/main (2026-09-23), and what each group pins
------------------------------------------------------------------------
 G1  SELF-GRANT. `.known-road-active` authorizes every readOnly bypass. The Bash
     guard refused only the BARE name: the entry is the glob `*.known-road-active`,
     `glob_to_regex` maps `*` to `[^\\s/]*`, and the write templates put the glob
     straight after the verb, so `> .claude/hooks/damage-control/<grant>` (any
     directory prefix, `./`, absolute), `touch`, `tee`, `cp`, `ln`, `dd of=` ...
     all exited 0. The Write and Edit guards refuse; Bash was the open door. The
     grant is git-IGNORED, so the PostToolUse effect check cannot see it either.
     The grant-state cache (PR #3174) decides whether a pr:/issue: grant is still
     live, so forging it revives a dead grant: same protection.
 G2  DEPTH. None of the 17 glob readOnly entries reached a nested path, and
     `**/Dockerfile` reached exactly one level. Literal entries had the same
     shape for the verb-adjacent templates (`>`, `>>`, cp/mv destination).
 G3  TEE. `tee`'s write template carried `(?!.*-a)`, which rejects any command
     containing the two bytes `-a` ANYWHERE -- `x-api.json`, `road-active` --
     rather than the `-a` FLAG.
 G4  OPAQUE VERBS UNDER AN UNRELATED GRANT. `active_grant()` says SOME grant is
     open, not that it covers this write, so `tar -x` ran silently under an
     operator's `dockerfile:` grant (live trail row 2026-09-24T00:24:01Z).

ISOLATION. Every case runs the REAL hook entry point as a subprocess against a
throwaway copy of the guard inside a temp project, with CLAUDE_PROJECT_DIR
pointed at that temp project and KNOWN_ROAD stripped unless a case sets it. No
case writes a grant file anywhere; the one granted case uses the env var and a
handoff brief that exists only in the temp project. The real tree's trail row
count and grant-file presence are asserted unchanged at the end.

Fixture strings are assembled from parts so this file's own text cannot trip a
guard that reads it.
"""
import importlib.util
import json
import os
import random
import time
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAL_TREE = HERE.parents[2]
REL_DC = ".claude/hooks/damage-control"

GRANT = ".known-road" + "-active"
CACHE = ".grant-state" + "-cache.json"
V_TEE = "t" + "ee"
V_SED = "s" + "ed"
V_CP = "c" + "p"
V_MV = "m" + "v"
V_TR = "trunc" + "ate"
V_LN = "l" + "n"
V_INST = "inst" + "all"
V_TOUCH = "tou" + "ch"
V_TAR = "t" + "ar"


def materialize(ref):
    """A temp project holding the guard under test. Returns its root."""
    root = Path(tempfile.mkdtemp(prefix="dc-selfgrant-"))
    dst = root / REL_DC
    dst.mkdir(parents=True)
    if ref is None:
        for f in HERE.iterdir():
            if f.suffix in (".py", ".yaml") and f.is_file():
                shutil.copy2(f, dst / f.name)
    else:
        listing = subprocess.run(
            ["git", "-C", str(REAL_TREE), "ls-tree", "--name-only", f"{ref}:{REL_DC}"],
            capture_output=True, text=True, check=True).stdout.split()
        for name in listing:
            if not (name.endswith(".py") or name.endswith(".yaml")):
                continue
            blob = subprocess.run(
                ["git", "-C", str(REAL_TREE), "show", f"{ref}:{REL_DC}/{name}"],
                capture_output=True, check=True).stdout
            (dst / name).write_bytes(blob)
    # A handoff brief for the ONE granted case -- it exists only in this temp tree.
    (root / "pmoves/docs/handoffs").mkdir(parents=True)
    (root / "pmoves/docs/handoffs/selfgrant-test.md").write_text("fixture\n")
    return root


def run_guard(root, command, road=None):
    """(verdict, detail) from the real hook entry point: block | ask | allow."""
    env = {k: v for k, v in os.environ.items() if k != "KNOWN_ROAD"}
    env["CLAUDE_PROJECT_DIR"] = str(root)
    if road:
        env["KNOWN_ROAD"] = road
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        [sys.executable, str(root / REL_DC / "bash-tool-damage-control.py")],
        input=payload, capture_output=True, text=True, cwd=str(root), env=env,
        timeout=60)
    if proc.returncode == 2:
        return "block", proc.stderr.strip()
    if proc.returncode != 0:
        return f"crash(rc={proc.returncode})", proc.stderr.strip()[-300:]
    out = proc.stdout.strip()
    if out:
        try:
            decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
        except (ValueError, KeyError):
            return "crash(bad-json)", out[:300]
        return decision, out
    return "allow", ""


def trail_rows(root):
    p = root / REL_DC / "known-roads.jsonl"
    return len(p.read_text().splitlines()) if p.is_file() else 0


def cases(root):
    """(group, label, command, road, expected verdicts)."""
    out = []
    D = REL_DC + "/"
    for name in (GRANT, CACHE):
        for prefix in ("", "./", D, "./" + D, str(root) + "/" + D, "sub/dir/"):
            p = prefix + name
            forms = [
                f"echo x > {p}",
                f"echo x >> {p}",
                f"echo x >{p}",
                f"echo x >| {p}",
                f"printf x > \"{p}\"",
                f"printf x > '{p}'",
                f": > {p}",
                f"cat /tmp/g > {p}",
                f"{V_TOUCH} {p}",
                f"{V_TEE} {p} < /dev/null",
                f"{V_TEE} -a {p} < /dev/null",
                f"echo x | {V_TEE} {p}",
                f"{V_CP} /tmp/g {p}",
                f"{V_MV} /tmp/g {p}",
                f"{V_INST} -m 600 /tmp/g {p}",
                f"{V_LN} -s /tmp/g {p}",
                f"rsync /tmp/g {p}",
                f"{V_SED} -i 's/a/b/' {p}",
                f"perl -pi -e 's/a/b/' {p}",
                f"{V_TR} -s 0 {p}",
                f"dd if=/tmp/g of={p}",
                f"chmod 600 {p}",
                f"python3 -c \"open('{p}','w').write('x')\"",
                f"python3 -c \"from pathlib import Path; Path('{p}').write_text('x')\"",
                f"node -e \"require('fs').writeFileSync('{p}', 'x')\"",
                f"f={p}; echo x > \"$f\"",
                f"cd /tmp && echo x > {p}",
            ]
            for cmd in forms:
                out.append(("G1", f"{name} via {prefix or '(bare)'}", cmd, None, {"block"}))
    # Name split across an expansion, and the grant name as a SOURCE into a dir.
    out.append(("G1", "split name", f"echo x > {D}.known-road-$(echo active)", None, {"block"}))
    out.append(("G1", "glob in target", f"echo x > {D}.known-road-act*", None, {"block"}))
    out.append(("G1", "grant as cp source", f"{V_CP} /tmp/{GRANT} {D}", None, {"block"}))
    out.append(("G1", "unbalanced quote", f"echo x > '{D}{GRANT}", None, {"block"}))
    out.append(("G1", "under an open grant", f"echo x > {D}{GRANT}",
                "compose:handoff:selfgrant-test.md", {"block"}))

    # Controls: the sanctioned read road and ordinary reads must stay open.
    for cmd in (
        "python3 .claude/skills/known-roads/roads.py status",
        f"cat {D}known-roads.jsonl",
        f"wc -l {D}known-roads.jsonl",
        f"ls -la {D}",
        f"cat {D}{GRANT}",
        f"ls -la {D}{GRANT} {D}{CACHE}",
        f"test -f {D}{GRANT}",
        f"grep -c . {D}known-roads.jsonl",
        "echo hello > /tmp/selfgrant-control.txt",
        "git commit -F - <<'EOF'\nfix: document " + D + GRANT + "\nEOF",
    ):
        out.append(("G1-control", "read stays open", cmd, None, {"allow"}))

    # G2: depth. Every target below is a real protected file at depth > 1.
    deep = [
        "a/b/poetry.lock",
        "a/b/x.lock",
        "/srv/a/b/app.min.js",
        "a/b/app.min.css",
        "a/b/app.bundle.js",
        "a/b/app.chunk.js",
        "a/b/c/Dockerfile",
        "./a/b/c/Dockerfile",
        "a/b/Dockerfile.prod",
        "a/b/.dockerignore",
        "a/b/package-lock.json",
        "pmoves/services/foo/config/a.yml",
        "./pmoves/services/foo/config/a.yml",
        str(root) + "/pmoves/services/foo/config/a.yml",
        str(root) + "/pmoves/docker-compose.gpu.yml",
        str(root) + "/pmoves/contracts/schemas/z.schema.json",
        "./pmoves/contracts/schemas/z.schema.json",
        str(root) + "/deploy/provision/x-pmoves.sh",
        "./pmoves/scripts/claude-pmoves",
        str(root) + "/.claude/context/x.md",
    ]
    for t in deep:
        for cmd in (f"echo x > {t}", f"echo x >> {t}", f"echo x > \"{t}\"",
                    f"{V_CP} /tmp/a {t}", f"{V_MV} /tmp/a {t}",
                    f"echo x | {V_TEE} {t}"):
            out.append(("G2", t, cmd, None, {"block"}))
    # Anchoring: a name that merely STARTS like a protected file is not one.
    for t in ("a/b/Dockerfile_notes.txt", "a/b/poetry.lock.md", "a/b/notes.txt",
              "a/b/app.min.jsx"):
        out.append(("G2-control", t, f"echo x > {t}", None, {"allow"}))
    out.append(("G2-control", "prose", "echo 'see a/b/poetry.lock' > /tmp/n.txt", None, {"allow"}))
    out.append(("G2-control", "read", "cat a/b/poetry.lock", None, {"allow"}))

    # G3: tee's -a is a FLAG, not a substring.
    out.append(("G3", "-a inside a path", f"echo x | {V_TEE} pmoves/contracts/schemas/x-api.schema.json",
                None, {"block"}))
    out.append(("G3", "-a inside a path (lock)", f"echo x | {V_TEE} a-b/x-api/poetry.lock", None, {"block"}))

    # G4: an open grant for one domain does not silently cover an opaque write.
    road = "dockerfile:handoff:selfgrant-test.md"
    out.append(("G4", "tar -x under unrelated grant", f"{V_TAR} -xf /tmp/a.tar", road, {"ask"}))
    out.append(("G4", "git apply under grant", "git apply /tmp/x.patch", road, {"ask"}))
    out.append(("G4", "rsync under grant", "rsync -a /tmp/src/ ./", road, {"ask"}))
    out.append(("G4-control", "tar -x, no grant", f"{V_TAR} -xf /tmp/a.tar", None, {"ask"}))
    out.append(("G4-control", "tar -t, under grant", f"{V_TAR} -tf /tmp/a.tar", road, {"allow"}))
    return out


def in_process_checks(root):
    """G5: the matcher itself must never raise and must stay fast.

    Until the fail-closed entry-point wrapper (#3174) lands, ANY exception in the
    Bash guard is a non-blocking rc=1 -- the command it should refuse runs. So
    this does not rely on a wrapper: it calls check_command directly on hostile
    input and treats an exception as a failure. Also re-asserts that malformed
    commands naming the grant state or a nested protected file are BLOCKED.
    """
    failures = []
    os.environ["CLAUDE_PROJECT_DIR"] = str(root)
    os.environ.pop("KNOWN_ROAD", None)
    sys.path.insert(0, str(root / REL_DC))
    spec = importlib.util.spec_from_file_location("dc_g5", root / REL_DC / "bash-tool-damage-control.py")
    dc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dc)
    kr = sys.modules["known_roads"]
    kr._trail_path = lambda: root / "g5-trail.jsonl"
    kr._grant_file = lambda: root / "g5-no-grant"
    cfg = dc.load_config()

    def verdict(cmd):
        b, a, _ = dc.check_command(cmd, cfg)
        return "block" if b else ("ask" if a else "allow")

    D = REL_DC + "/"
    malformed = [
        f"echo x > '{D}{GRANT}",
        f"echo x > \"{D}{CACHE}",
        f"{V_TOUCH} \"{D}{GRANT}",
        "echo x > 'a/b/poetry.lock",
        f"{V_CP} /tmp/a \"a/b/c/Dockerfile",
        "echo x > \"$(cat 'a/b/x.lock",
    ]
    for cmd in malformed:
        try:
            got = verdict(cmd)
        except Exception as exc:  # noqa: BLE001 -- the point is to catch it
            got = f"RAISED {exc!r}"
        if got != "block":
            failures.append(("G5 malformed", cmd, got))

    # Hostile sizes for every template this change added or widened. The 22 s
    # stall this file's neighbours guard against came from stacked greedy scans.
    big = [
        V_CP + " " + "a/" * 2500 + " x",
        V_TOUCH + " " + "a " * 2500,
        V_SED + " " + "-e x " * 1000 + " f",
        "perl " + "-w " * 1500 + " f",
        V_LN + " " + "-s " * 1500 + " x",
        "sudo " + V_INST + " " + "-m " * 1500 + " x",
        "echo > " + "a/" * 2500,
        "echo x | " + V_TEE + " " + "x-a " * 1200,
        "dd " + "if=x " * 1000,
        "cat > /tmp/n.md <<'EOF'\n" + ("see > a/b/c and cp x y/z/ then touch q\n" * 130) + "EOF",
        "echo " + "known-road " * 600,
    ]
    for cmd in big:
        t0 = time.perf_counter()
        try:
            verdict(cmd)
            err = ""
        except Exception as exc:  # noqa: BLE001
            err = repr(exc)
        dt = time.perf_counter() - t0
        if err or dt > 2.0:
            failures.append(("G5 size", cmd[:60], err or f"{dt:.2f}s (limit 2.0s)"))

    # Random shell-ish input: the matcher must return a verdict, never raise.
    rng = random.Random(3176)
    alphabet = ["echo", "x", ">", ">>", ">|", "|", ";", "&&", "'", '"', "$(", ")", "`",
                "\n", "\t", "\\", "-a", "-i", "of=", V_TEE, V_TOUCH, V_CP, V_MV, V_LN,
                V_INST, V_SED, "perl", "dd", "a/b/", "./", "/", "**", "*", "?", "[",
                "poetry.lock", "Dockerfile", GRANT, CACHE, "known-road-", D, "<<'EOF'",
                "EOF", "~", "pmoves/services/", "config/", "{", "}", "=", "#"]
    raised = 0
    for _ in range(3000):
        cmd = " ".join(rng.choice(alphabet) for _ in range(rng.randint(1, 18)))
        try:
            verdict(cmd)
        except Exception as exc:  # noqa: BLE001
            raised += 1
            if raised <= 5:
                failures.append(("G5 fuzz", cmd[:80], repr(exc)))
    trail = root / "g5-trail.jsonl"
    if trail.exists():
        failures.append(("G5", "in-process run recorded a Known Road use", trail.read_text()[:200]))
    return failures


def main(argv):
    ref = None
    if len(argv) >= 2 and argv[0] == "--ref":
        ref = argv[1]
    real_trail = REAL_TREE / REL_DC / "known-roads.jsonl"
    real_rows_before = trail_rows(REAL_TREE)
    real_grant_before = (REAL_TREE / REL_DC / GRANT).exists()
    real_cache_before = (REAL_TREE / REL_DC / CACHE).exists()

    root = materialize(ref)
    print(f"== self-grant / depth / tee / opaque -- guard from {ref or 'working tree'} ==")
    print(f"temp project: {root}")
    results = {}
    failures = []
    try:
        for group, label, cmd, road, want in cases(root):
            rows_before = trail_rows(root)
            verdict, detail = run_guard(root, cmd, road)
            rows_after = trail_rows(root)
            ok = verdict in want
            # An opaque write that was ASKED must not have been recorded as granted.
            if group == "G4" and rows_after != rows_before:
                ok = False
                detail = f"trail grew {rows_before}->{rows_after} :: {detail}"
            results.setdefault(group, [0, 0])
            results[group][0 if ok else 1] += 1
            if not ok:
                failures.append((group, label, cmd, sorted(want), verdict, detail))
            # The temp project must never gain a grant file.
            if (root / REL_DC / GRANT).exists() or (root / REL_DC / CACHE).exists():
                failures.append((group, label, cmd, ["no grant file"], "grant file appeared", ""))
        g5 = in_process_checks(root)
        results["G5"] = [0 if g5 else 1, len(g5)]
        for group, cmd, got in g5:
            failures.append((group, "in-process", cmd, ["block / no raise / fast"], str(got), ""))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    for group in sorted(results):
        ok, bad = results[group]
        print(f"  {group:12s} pass={ok:4d} fail={bad:4d}")
    for group, label, cmd, want, verdict, detail in failures[:400]:
        print(f"  FAIL [{group}] {label}: want {want} got {verdict}")
        print(f"       cmd: {cmd[:160]!r}")
        if detail and verdict.startswith("crash"):
            print(f"       detail: {detail[:200]}")

    real_rows_after = trail_rows(REAL_TREE)
    same_grant = (REAL_TREE / REL_DC / GRANT).exists() == real_grant_before
    same_cache = (REAL_TREE / REL_DC / CACHE).exists() == real_cache_before
    print(f"real trail rows: before={real_rows_before} after={real_rows_after} ({real_trail})")
    if real_rows_after != real_rows_before or not same_grant or not same_cache:
        print("FAIL — the run touched the real tree's trail or grant state")
        return 1
    total = sum(a + b for a, b in results.values())
    if failures:
        print(f"FAIL — {len(failures)} of {total} cases")
        return 1
    print(f"PASS — all {total} cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
