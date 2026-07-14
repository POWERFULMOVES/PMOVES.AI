"""In-process verification of the `topic` Known-Road domain.

Run: python .claude/hooks/damage-control/test_topic_domain.py
Asserts the `topic` domain opens ONLY pmoves/contracts/topics.json (the NATS
subject registry) and nothing else — schema files stay with the schema domain,
bare filenames and non-contract paths stay closed.
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

# (normalized_forward_slash_path, expect_is_topic_target)
cases = [
    ("pmoves/contracts/topics.json", True),                       # the registry -> OPEN
    ("d:/pmoves.ai/pmoves-kr-topic/pmoves/contracts/topics.json", True),  # absolute worktree path
    ("pmoves-dox/pmoves/contracts/topics.json", True),            # pmoves-owned sibling tree
    ("pmoves/contracts/schemas/geometry/publish.gate.v1.schema.json", False),  # schema domain, not topic
    ("topics.json", False),                                       # bare filename, no contracts segment
    ("pmoves/config/topics.json", False),                         # not under contracts/
    ("contracts/topics.json", False),                             # not a pmoves-owned tree
    ("pmoves/contracts/topics.json.bak", False),                  # only the exact registry file
]

failures = []
for path, expected in cases:
    got = k._is_topic_target(path.lower())
    if got != expected:
        failures.append(f"_is_topic_target({path!r}) = {got}, expected {expected}")

# domain is registered and discoverable
if "topic" not in k.DOMAIN_PATTERNS:
    failures.append("'topic' missing from DOMAIN_PATTERNS")
if "topic" not in k.known_road_domains():
    failures.append("'topic' missing from known_road_domains()")

if failures:
    print("FAIL: topic-domain checks")
    for f in failures:
        print("  -", f)
    sys.exit(1)

print(f"OK: topic-domain — {len(cases)} path cases + registration checks passed")
