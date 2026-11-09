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
    # newline="\n" keeps output deterministic across platforms (Windows text
    # mode would otherwise emit CRLF and churn the committed artifacts).
    out = REPO_ROOT / f"website/tenant-template/data/{tenant_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(page), encoding="utf-8", newline="\n")
    # Also save the canonical composed artifact under tests/fixtures
    canon = REPO_ROOT / f"pmoves/tools/compose/tests/fixtures/{tenant_id}.composed.json"
    canon.write_text(to_json(page), encoding="utf-8", newline="\n")

    print(f"\n[{tenant_id}] composed: {len(page['messages'])} messages")
    print(f"  components in: {len(cfg['components'])}")
    component_types = [m["component"] for m in page["messages"] if m["type"] == "createComponent"]
    for c, n in sorted(Counter(component_types).items()):
        print(f"    {c}: {n}")
    print(f"  written: {out}")


# Tenants this composer knows how to build: tenant_id -> fixture filename.
KNOWN_TENANTS = {
    "fordham-hill": "fordham-hill.json",
    "sint-maarten": "sint-maarten.json",
}


if __name__ == "__main__":
    # Optional argv: a single tenant id to compose. With no argv, compose all
    # known tenants (the original behavior).
    requested = sys.argv[1] if len(sys.argv) > 1 else None
    if requested is None:
        for tenant_id, fixture in KNOWN_TENANTS.items():
            compose_tenant(tenant_id, fixture)
    elif requested in KNOWN_TENANTS:
        compose_tenant(requested, KNOWN_TENANTS[requested])
    else:
        sys.exit(
            f"unknown tenant {requested!r}; known: {sorted(KNOWN_TENANTS)}"
        )
