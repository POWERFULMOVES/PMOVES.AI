---
name: pmoves-living-docs-refresh
description: Detect stale living docs via `make -C pmoves docs-reconcile-check` and emit a per-doc regeneration recipe from `pmoves/configs/living_docs_registry.yaml`.
disable-model-invocation: false
user-invocable: false
---

# pmoves-living-docs-refresh

Wraps the canonical `make -C pmoves docs-reconcile-check` target so a worker can quickly see **which** living documents are stale and **how** each one is regenerated (per `pmoves/configs/living_docs_registry.yaml`).

## When to invoke

- Before opening a PR that lands a new architectural milestone
- After a Wave merge that touches `pmoves/docs/`
- When `merge-gate.yml` flags a docs-reconcile failure
- During `/docs:reconcile` follow-through

## How to run

```bash
bash .claude/skills/pmoves-living-docs-refresh/scripts/refresh.sh
```

The script:

1. Invokes `make -C pmoves docs-reconcile-check` and captures stdout+stderr.
2. Parses the registry yaml (`pmoves/configs/living_docs_registry.yaml`) — prefers PyYAML if available, falls back to a grep-based mini-parser otherwise.
3. For each entry the Make target reported stale, prints:
   ```
   [STALE] <doc_path> last-refreshed=<date> source=<generator-command-or-source-file>
   ```
4. Exits with the make target's exit code so this can be piped into CI.

## Output

```
[STALE] pmoves/docs/CHIT_INTEGRATION_STATUS.md last-refreshed=2026-04-12 source=scripts/audit_chit_services.py
[STALE] pmoves/docs/AGENTS/AGNOTE4482_SITREP.md last-refreshed=2026-05-10 source=manual:sitrep-author
exit_code=1
```

## Citations

- `pmoves/configs/living_docs_registry.yaml` — registry of tracked documents
- `pmoves/Makefile` § docs-reconcile-check
- `.claude/PATTERNS.md` § Living-docs freshness
