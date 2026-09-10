---
description: List all installed Pinokio apps with running state
---

# pinokio:app-list

List every installed Pinokio app with its running state, grouped by status.

## Usage

```
/pinokio:app-list [--running-only] [--filter <substring>]
```

## Implementation

```bash
# Pinokio root is a PER-NODE value (C: here, D: on other nodes), so derive it.
# pinokio-root.sh exits 1 when it had to guess -- see .claude/scripts/pinokio-root.sh
PTERM="$(bash .claude/scripts/pinokio-root.sh --exe)"
"$PTERM" search "" 2>&1 | python -c "
import sys, json
d = json.load(sys.stdin)
apps = d.get('apps', [])
running = [a for a in apps if a.get('running')]
offline = [a for a in apps if not a.get('running')]

print(f'Total apps: {len(apps)} ({len(running)} running, {len(offline)} offline)')
print()

if running:
    print(f'=== RUNNING ({len(running)}) ===')
    for app in sorted(running, key=lambda a: a.get('name','')):
        state = app.get('state','?')
        ready = '✓' if app.get('ready') else '⏳'
        url = app.get('ready_url','') or ''
        title = app.get('title', app.get('name',''))[:40]
        print(f'  {ready} [{state:10}] {title:42s} {url}')

if offline:
    print()
    print(f'=== OFFLINE ({len(offline)}) — top 20 by last launch ===')
    offline.sort(key=lambda a: a.get('last_launch_at','') or '', reverse=True)
    for app in offline[:20]:
        last = (app.get('last_launch_at','') or '')[:10] or 'never'
        count = app.get('launch_count_total', 0)
        title = app.get('title', app.get('name',''))[:40]
        print(f'    [{last}] {title:42s} ({count} launches)')
"
```

## Notes

- Empty search query returns all installed apps
- Running apps appear first, sorted by name
- Offline apps sorted by last launch date (most recently used first)
- `pterm search` reads from local Pinokio registry; no network calls

## Related

- `/pinokio:app-search <query>` — targeted search
- `/pinokio:app-start <app_id>` — launch an app
- `/pinokio:app-stop <app_id>` — stop an app
