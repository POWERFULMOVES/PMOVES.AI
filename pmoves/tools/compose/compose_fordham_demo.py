"""One-off: compose the Fordham Hill fixture into a tenant page JSON."""
import sys
import json
import pathlib
from collections import Counter

# Resolve paths relative to repo root (not relative to this file's location)
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from compose import compose_tenant_page, to_json  # noqa: E402

cfg = json.loads(
    (REPO_ROOT / "pmoves/tools/compose/tests/fixtures/fordham-hill.json").read_text(encoding="utf-8")
)
page = compose_tenant_page(cfg)

outputs = [
    REPO_ROOT / "website/tenant-template/data/fordham-hill.json",
    REPO_ROOT / "pmoves/tools/compose/tests/fixtures/fordham-hill.composed.json",
]
for out in outputs:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(page), encoding="utf-8")

print(f"composed: {len(page['messages'])} messages")
print(f"  components in: {len(cfg['components'])}")
component_types = [m["component"] for m in page["messages"] if m["type"] == "createComponent"]
for c, n in sorted(Counter(component_types).items()):
    print(f"    {c}: {n}")
print(f"\nwritten: {outputs[0]}")
