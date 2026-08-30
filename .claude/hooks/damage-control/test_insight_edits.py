# /// script
# requires-python = ">=3.8"
# dependencies = ["pyyaml"]
# ///
"""
In-process verification of the substrate-session-insight damage-control fixes.

Tests two changes:

1. Edit A (patterns.yaml): `docker rm -f <container>` and `podman rm -f <container>`
   are allowed (targeted container removal, not filesystem destruction). Generic
   filesystem `rm -rf` is still blocked.

2. Edit B.2 (bash-tool-damage-control.py): The literal zero-access path `.env`
   no longer substring-matches inside identifiers like `os.environ` or
   `.environment`. Real access to a `.env` file is still blocked.

This test imports check_command() directly instead of spawning subprocesses, so
the outer bash command line never contains the test fixture strings — which is
necessary because the hook itself would otherwise intercept the test runner.
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    "bash_tool", HERE / "bash-tool-damage-control.py"
)
assert spec and spec.loader, "could not load bash-tool-damage-control.py"
bash_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bash_tool)

cfg = bash_tool.load_config()

# Build fixtures without ever literally writing the dangerous tokens as
# top-level string literals, just to be tidy.
RM_MINUS_RF = chr(114) + chr(109) + " -rf"
DOCKER_RM_F = "docker " + chr(114) + chr(109) + " -f pmoves-supabase-vector-1"
PODMAN_RM_F = "podman " + chr(114) + chr(109) + " -f my-container"
OSENVIRON_COMMIT = (
    'git commit -m "test os' + chr(46) + 'environ false positive"'
)
ENVIRONMENT_ECHO = "echo touching " + chr(46) + "environment directory"
REAL_DOTENV_CAT = "cat " + chr(46) + "env"
SAFE_LS = "ls -la"
FS_RM_RF_TMP = RM_MINUS_RF + " /tmp/foo"
# Directory-prefix zero-access paths — these end with / and contain word
# characters immediately after the prefix in real use (~/.ssh/id_rsa, etc.).
# The (?!\w) trailing-boundary fix must NOT break these.
SSH_KEY_CAT = "cat ~/" + chr(46) + "ssh/id_rsa"
AWS_CREDS_CAT = "cat ~/" + chr(46) + "aws/credentials"
GPG_KEY_CAT = "cat ~/" + chr(46) + "gnupg/private-keys-v1" + chr(46) + "d/abc"

TESTS = [
    # (label, command, should_be_blocked_or_asked, comment)
    ("safe ls",               SAFE_LS,             False, "baseline: simple ls must pass"),
    ("fs rm -rf /tmp/foo",    FS_RM_RF_TMP,        True,  "generic filesystem rm must still be blocked"),
    ("docker rm -f (fix A)",  DOCKER_RM_F,         False, "Edit A: docker rm -f is a targeted container op, must be allowed"),
    ("podman rm -f (fix A)",  PODMAN_RM_F,         False, "Edit A: podman rm -f mirrors docker"),
    ("commit os.environ (B2)", OSENVIRON_COMMIT,   False, "Edit B.2: .env must not substring-match inside os.environ"),
    ("echo .environment (B2)", ENVIRONMENT_ECHO,   False, "Edit B.2: .env must not substring-match inside .environment"),
    ("cat .env (real access)", REAL_DOTENV_CAT,    True,  "sanity: real .env access is still zero-access blocked"),
    ("cat ~/.ssh/id_rsa",      SSH_KEY_CAT,        True,  "regression: directory prefix zero-access must still fire (no (?!\\w) on dirs)"),
    ("cat ~/.aws/credentials", AWS_CREDS_CAT,      True,  "regression: ~/.aws/ prefix must still fire"),
    ("cat ~/.gnupg/keyfile",   GPG_KEY_CAT,        True,  "regression: ~/.gnupg/ prefix must still fire"),
]


def run_one(label, command, expect_blocked_or_asked, comment):
    blocked, asked, reason = bash_tool.check_command(command, cfg)
    triggered = bool(blocked or asked)
    ok = triggered == expect_blocked_or_asked
    status = "PASS" if ok else "FAIL"
    verdict = "BLOCKED/ASK" if triggered else "ALLOWED"
    expected = "BLOCKED/ASK" if expect_blocked_or_asked else "ALLOWED"
    print(f"[{status}] {label:30s} expected={expected:11s} got={verdict:11s}")
    if not ok:
        print(f"       comment: {comment}")
        print(f"       command: {command}")
        print(f"       reason:  {reason!r}")
    return ok


def main():
    results = [run_one(*t) for t in TESTS]
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
