"""In-process verification of the `dockerfile` Known-Road domain.

Run: python .claude/hooks/damage-control/test_dockerfile_domain.py
Asserts the `dockerfile` domain opens ONLY Dockerfile / Dockerfile.* /
.dockerignore basenames inside a PMOVES-owned tree — service source and other
build-context files stay closed (a dockerfile grant must not unlock them).
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("known_roads", HERE / "known_roads.py")
assert spec and spec.loader, "could not load known_roads.py"
k = importlib.util.module_from_spec(spec)
sys.modules["known_roads"] = k
spec.loader.exec_module(k)

# (normalized_forward_slash_path, expect_is_dockerfile_target)
cases = [
    ("pmoves/services/media-video/Dockerfile", True),             # service Dockerfile -> OPEN
    ("pmoves/services/hirag/Dockerfile.gpu", True),               # Dockerfile.* variant -> OPEN
    ("pmoves/services/media-audio/.dockerignore", True),          # build-context ignore -> OPEN
    ("pmoves-cipher/Dockerfile", True),                           # pmoves- prefixed sibling tree -> OPEN
    ("d:/pmoves.ai/pmoves-kr-fix/pmoves/services/x/Dockerfile", True),  # absolute worktree path
    ("pmoves/services/media-video/server.py", False),             # service SOURCE stays closed
    ("pmoves/services/media-video/requirements.txt", False),      # build-context file stays closed
    ("pmoves/docker/runner/Dockerfile", True),                    # non-services Dockerfile in pmoves tree
    ("services/foo/Dockerfile", False),                           # not a pmoves-owned tree
    ("Dockerfile", False),                                        # bare filename, no pmoves segment
    ("pmoves/services/x/Dockerfile.bak/config.yaml", False),      # Dockerfile.* must be the basename
]

failures = []
for path, expected in cases:
    got = k._is_dockerfile_target(path.lower())
    if got != expected:
        failures.append(f"_is_dockerfile_target({path!r}) = {got}, expected {expected}")

if failures:
    print("FAIL")
    for f in failures:
        print(" ", f)
    sys.exit(1)

print(f"OK — {len(cases)} dockerfile-domain cases pass")
