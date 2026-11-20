"""In-process verification that a tool's OWN output flag is a write.

Run: python .claude/hooks/damage-control/test_output_flag_writes.py

Measured 2026-10-01: `uv pip compile ... -o pmoves/services/<svc>/requirements.lock`
overwrote a readOnly lockfile and nothing refused it. Every other write template
keys on a shell verb (>, tee, sed -i, cp); a generator's `-o` uses none of them.

Asserts BOTH directions: each output-flag shape aimed at a protected path blocks,
at the bare name and at depth, and the same tools aimed at an unprotected path --
or with no output flag at all -- stay allowed.

Fixtures are assembled from split parts so this file's own text cannot trip the
guard that reads it.
"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR") or HERE.parents[2])
os.environ["CLAUDE_PROJECT_DIR"] = str(REPO)
os.environ.pop("KNOWN_ROAD", None)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


dc = _load("dc", HERE / "bash-tool-damage-control.py")
cfg = dc.load_config()

KR = sys.modules.get("known_roads")
if KR is not None:
    import tempfile
    KR._grant_file = lambda: Path(tempfile.mkdtemp(prefix="kr-none-")) / ".known-road-active"

LOCK = "requirements" + ".lo" + "ck"
NESTED = "pmoves/services/graph-linker/" + LOCK
COMPILE = "uv pip compile requirements.in"

CASES = [
    # (want_blocked, label, command)
    (True, "uv pip compile -o <nested lock>", f"{COMPILE} -o {NESTED}"),
    (True, "uv pip compile -o <bare lock> after cd",
     f"cd pmoves/services/graph-linker && {COMPILE} -o {LOCK}"),
    (True, "--output-file <nested lock>", f"{COMPILE} --output-file {NESTED}"),
    (True, "--output-file=<nested lock>", f"{COMPILE} --output-file={NESTED}"),
    (True, "-o \"<quoted nested lock>\"", f'{COMPILE} -o "{NESTED}"'),
    (True, "pip-compile -o <lock> before its input", f"pip-compile -o {NESTED} requirements.in"),
    (True, "uv export -o <lock>", f"uv export -o {NESTED}"),
    (True, "the incident shape, verbatim but split",
     f"uv pip compile pmoves/services/graph-linker/requirements.txt --generate-hashes "
     f"--python-version 3.11 -o {NESTED} -q"),
    (False, "uv lock (the package manager's own road)", "uv lock"),
    (False, "-o to an unprotected scratch path", f"{COMPILE} -o /tmp/out.txt"),
    (False, "a protected name that is not the flag's value",
     f"{COMPILE} -o /tmp/out.txt && cat {NESTED}"),
    (False, "-o fused inside another word", f"echo foo-o {LOCK}x"),
]


def main() -> int:
    failures = 0
    for want, label, command in CASES:
        blocked, _ask, reason = dc.check_command(command, cfg)
        ok = blocked == want
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] blocked={blocked!s:5} want={want!s:5} {label}")
        if not ok:
            print(f"          cmd={command}")
            print(f"          reason={reason!r}")
    if failures:
        print(f"\nFAIL — {failures} of {len(CASES)} case(s) failed.")
        return 1
    print(f"\nPASS — all {len(CASES)} cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
