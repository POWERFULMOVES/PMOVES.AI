"""One-off: compose Fordham Hill + Sint Maarten fixtures into tenant page JSON."""
import sys
import json
import pathlib
from collections import Counter

# Resolve paths relative to repo root (not relative to this file's location)
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from compose import compose_tenant_page, to_json  # noqa: E402


def compose_tenant(tenant_id, fixture_filename):
    cfg = json.loads(
        (REPO_ROOT / f"pmoves/tools/compose/tests/fixtures/{fixture_filename}").read_text(encoding="utf-8")
    )
    page = compose_tenant_page(cfg)
    out = REPO_ROOT / f"website/tenant-template/data/{tenant_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(page), encoding="utf-8")
    # Also save the canonical composed artifact under tests/fixtures
    canon = REPO_ROOT / f"pmoves/tools/compose/tests/fixtures/{tenant_id}.composed.json"
    canon.write_text(to_json(page), encoding="utf-8")

    print(f"\n[{tenant_id}] composed: {len(page['messages'])} messages")
    print(f"  components in: {len(cfg['components'])}")
    component_types = [m["component"] for m in page["messages"] if m["type"] == "createComponent"]
    for c, n in sorted(Counter(component_types).items()):
        print(f"    {c}: {n}")
    print(f"  written: {out}")


if __name__ == "__main__":
    compose_tenant("fordham-hill", "fordham-hill.json")
    compose_tenant("sint-maarten", "sint-maarten.json")
