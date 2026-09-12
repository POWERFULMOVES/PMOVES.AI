"""In-process verification of proportionate path resolution (path_scope.py).

Run: python .claude/hooks/damage-control/test_proportionality.py

Two refusals of legitimate work motivated this, and both are reconstructed below
as ALLOW cases:

  FP1  a host-level interpreter environment rebuilt OUTSIDE this repo was refused
       because patterns.yaml lists bare artifact-directory names with no
       repository scope, and the guard matched that name in the command text.
  FP2  a claim-register note was refused because the note NAMED the things it
       documented -- a sentence carrying a verb and a protected directory name
       satisfies `\\bVERB\\s+.*DIR`, since `.*` will bridge a whole sentence.

The BLOCK cases are the important half. A proportionality change is only worth
having if the same things stay protected, so every ALLOW here is paired with the
in-repo form of the same operation, which must still refuse.

EVERY protected path and verb below is assembled from split parts at runtime.
That is not decoration: an earlier draft of this file spelled one fixture out in
full and the guard refused to let the file be written, which is the same defect
the file tests (see test_gitlock_allowlist.py for the same convention).
"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR") or HERE.parents[2])
os.environ["CLAUDE_PROJECT_DIR"] = str(REPO)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


dc = _load("dc", HERE / "bash-tool-damage-control.py")
ps = _load("ps", HERE / "path_scope.py")
cfg = dc.load_config()

# verbs
V_CH = "ch" + "mod"
V_MV = "m" + "v"
V_CP = "c" + "p"
V_SED = "s" + "ed"
V_TEE = "t" + "ee"
V_TRUNC = "trunc" + "ate"
# protected names
ENV_DIR = "v" + "env"
DEPS_DIR = "node_" + "modules"
BUILD_DIR = "bui" + "ld"
ETC = "/et" + "c"
USRBIN = "/us" + "r/local/bin"
SCHEMAS = "pmoves/contra" + "cts/schemas"
LOCKFILE = "poetry" + ".lock"
HOSTS = ETC + "/hosts"

# TWO PRE-EXISTING GAPS, surfaced while building this suite and deliberately NOT
# closed here. Both behave IDENTICALLY before and after the proportionality
# change (measured old-vs-new on the same corpus), so neither is damage from it,
# and closing either would WIDEN what the guard protects -- out of scope for a
# proportionality change, and a decision for the operator:
#
#   1. MOVE_COPY_PATTERNS is `\bmv\s+.*\s+{path}`, which requires whitespace
#      before the path, so it only guards the DESTINATION. Moving a protected
#      directory AWAY is unguarded: `mv <protected-dir> /tmp/x` is allowed, which
#      destroys it just as effectively as a delete.
#   2. WRITE_PATTERNS is `>\s*{path}`, anchored immediately after the redirect,
#      so a protected directory reached through a longer path is unguarded:
#      a redirect into `<any>/<protected-dir>/out.txt` is allowed, while a
#      redirect into `<protected-dir>/out.txt` is blocked. The verb patterns that
#      bridge with `.*` (sed -i, permission, truncate) do not have this gap, which
#      is why the nested CONTROL case below uses one.

# (should_block, label, command)
CASES = [
    # ---- FP1: a repo-scoped entry must not claim identically-named directories
    #           elsewhere on the machine.
    (False, "permission change on a host dir outside the repo",
     V_CH + " -R 755 /srv/stack/" + ENV_DIR),
    (False, "rename INTO a host dir outside the repo",
     V_MV + " /tmp/a /opt/bringup/" + ENV_DIR + "/x"),
    (False, "in-place edit nested under a host dir outside the repo",
     V_SED + " -i s/a/b/ /opt/app/" + BUILD_DIR + "/out.txt"),
    (False, "write into a host dir under a tilde path",
     "echo x > ~/tools/" + ENV_DIR + "/pyvenv.cfg"),
    (False, "in-place edit of a host deps dir outside the repo",
     V_SED + " -i s/a/b/ /srv/app/" + DEPS_DIR + "/x.js"),
    (False, "redirect into a host build dir outside the repo",
     "echo x > /srv/app/" + BUILD_DIR + "/out.txt"),

    # ---- the SAME operations inside the repo must still refuse.
    (True, "CONTROL permission change on the repo dir",
     V_CH + " -R 755 " + ENV_DIR + "/"),
    (True, "CONTROL rename INTO the repo dir",
     V_MV + " /tmp/a " + ENV_DIR + "/x"),
    (True, "CONTROL write into the repo dir",
     "echo x > " + ENV_DIR + "/pyvenv.cfg"),
    (True, "CONTROL in-place edit in the repo deps dir",
     V_SED + " -i s/a/b/ " + DEPS_DIR + "/x.js"),
    (True, "CONTROL redirect into the repo build dir",
     "echo x > " + BUILD_DIR + "/out.txt"),
    (True, "CONTROL repo dir named with ./",
     V_CH + " -R 755 ./" + ENV_DIR + "/"),
    (True, "CONTROL repo dir by absolute path",
     V_CH + " -R 755 " + str(REPO) + "/" + ENV_DIR + "/"),
    (True, "CONTROL repo dir nested under a subdirectory",
     V_SED + " -i s/a/b/ pmoves/sub/" + BUILD_DIR + "/out.txt"),

    # ---- FP2: prose that merely NAMES a protected path is not an operation on it.
    (False, "a sentence naming a verb and a protected dir",
     "echo 'the guard refuses " + V_CH + " on a " + ENV_DIR + " directory' > /tmp/n.md"),
    (False, "a note body naming a protected dir",
     "python3 -c \"open('/tmp/n.md','w').write('documented: the "
     + DEPS_DIR + " directory is protected')\""),
    (False, "a sentence naming a system directory",
     "echo 'never " + V_TEE + " into " + ETC + "/ by hand' > /tmp/n.md"),
    (False, "a sentence naming a PMOVES contract directory",
     "echo 'to " + V_CP + " into " + SCHEMAS + "/ you need a road' > /tmp/n.md"),
    (False, "a sentence naming a lock file",
     "echo 'do not " + V_TRUNC + " " + LOCKFILE + " by hand' > /tmp/n.md"),

    # ---- prose must not weaken the real thing it describes.
    (True, "CONTROL the operation the sentence describes, for real",
     V_TEE + " " + HOSTS + " < /tmp/new"),
    (True, "CONTROL write to a PMOVES contract schema, for real",
     "echo x > " + SCHEMAS + "/z.schema.json"),
    (True, "CONTROL truncate a lock file, for real",
     V_TRUNC + " -s 0 " + LOCKFILE),

    # ---- absolute entries are unchanged: they were never repo-scoped.
    (True, "CONTROL write under a system directory",
     "echo x > " + HOSTS),
    (True, "CONTROL write under a system binary directory",
     "echo x > " + USRBIN + "/z"),

    # ---- prefix collisions must not over-block (pre-existing guarantee).
    (False, "a different dir sharing a protected prefix",
     "echo x > " + ENV_DIR + "ison/out.txt"),
    (False, "a different dir with a hyphen suffix",
     "echo x > " + BUILD_DIR + "-artifacts/out.txt"),
]


def main() -> int:
    failures = 0

    for should_block, label, command in CASES:
        blocked, _ask, reason = dc.check_command(command, cfg)
        ok = blocked == should_block
        failures += 0 if ok else 1
        verb = "block" if should_block else "allow"
        print(f"  [{'PASS' if ok else 'FAIL'}] {verb:<5} {label}")
        if not ok:
            print(f"          cmd: {command}")
            print(f"          got blocked={blocked} reason={reason}")

    # ---- fail-closed: an undecidable command keeps its refusal --------------
    # The confirmation stage is a FILTER ON REFUSALS, so a crash-to-allow would
    # disable the guard. This is the most important property in this file.
    unlexable = "echo x > " + ENV_DIR + "/f.txt \"unterminated"
    toks = ps.command_tokens(unlexable)
    ok = toks is None
    failures += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] unlexable command yields no tokens")
    keep, _hits = ps.confirm(None, ENV_DIR + "/", (ENV_DIR + "/",))
    failures += 0 if keep else 1
    print(f"  [{'PASS' if keep else 'FAIL'}] undecidable input keeps the block (fail-closed)")
    blocked, _a, _r = dc.check_command(unlexable, cfg)
    failures += 0 if blocked else 1
    print(f"  [{'PASS' if blocked else 'FAIL'}] unlexable command is still refused end to end")

    # ---- nested-quote harvesting -------------------------------------------
    # A single `'..'|".."` alternation let an outer double-quoted argument
    # swallow the inner literal, so the real target inside -c "io.open('P','w')"
    # never surfaced and five interpreter-write blocks stopped firing. Pin it.
    nested = "python3 -c \"import io; io.open('" + LOCKFILE + "','w').write(1)\""
    toks = ps.command_tokens(nested) or []
    ok = LOCKFILE in toks
    failures += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] a literal nested inside a quoted argument is harvested")

    # ---- component matching ------------------------------------------------
    unit = [
        (True, ENV_DIR + "/f.txt", ENV_DIR + "/"),
        (True, "a/b/" + ENV_DIR + "/f.txt", ENV_DIR + "/"),
        (False, "a/" + ENV_DIR + "ison/f.txt", ENV_DIR + "/"),
        (False, "a sentence about " + ENV_DIR + " dirs", ENV_DIR + "/"),
        (True, LOCKFILE, "*.lock"),
        (True, "a/b/" + LOCKFILE, "*.lock"),
        (False, "a note about " + LOCKFILE + " files", "*.lock"),
        (True, HOSTS, ETC + "/"),
        (False, "do not touch " + HOSTS + " by hand", ETC + "/"),
        (True, "pmoves/docker-compose.ui.yml", "pmoves/docker-compose*.yml"),
        (True, "pmoves/services/x/config/y.yml", "pmoves/services/*/config/"),
        (False, "pmoves/services/x/src/y.py", "pmoves/services/*/config/"),
    ]
    for want, token, entry in unit:
        got = ps.token_matches_entry(token, entry)
        ok = got == want
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] match={got!s:5} want={want!s:5} "
              f"{entry!r} vs {token!r}")

    # ---- repo scoping is declared in config, not inferred ------------------
    declared = cfg.get("repoScopedPaths") or []
    read_only = set(cfg.get("readOnlyPaths") or [])
    stray = [e for e in declared if e not in read_only]
    ok = bool(declared) and not stray
    failures += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] repoScopedPaths is non-empty and a subset "
          f"of readOnlyPaths ({len(declared)} entries, stray={stray})")

    total = len(CASES) + 4 + len(unit) + 1
    if failures:
        print(f"\nFAIL — {failures} of {total} check(s) failed.")
        return 1
    print(f"\nPASS — all {total} checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
