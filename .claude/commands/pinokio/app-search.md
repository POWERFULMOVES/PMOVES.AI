---
description: Search installed and available Pinokio apps via pterm CLI
---

# pinokio:app-search

Search the local Pinokio installation for apps matching a query. Uses `pterm search` with JSON output parsing and filtering by state (ready/running/offline).

## Usage

```
/pinokio:app-search <query>
```

**Arguments:**
- `query` — Search term (e.g., `voice`, `tts`, `diffusion`, `comfyui`)

## Implementation

```bash
# Pinokio root is a PER-NODE value (C: here, D: on other nodes), so derive it.
# pinokio-root.sh exits 1 when it had to guess -- see .claude/scripts/pinokio-root.sh
PTERM="$(bash .claude/scripts/pinokio-root.sh --exe)"
# Base search (JSON output)
"$PTERM" search "{{args.query}}" 2>&1 | python -c "
import sys, json
d = json.load(sys.stdin)
apps = d.get('apps', [])
print(f'Query: \"{d.get(\"q\",\"?\")}\" — found {len(apps)} apps')
print()
# Sort by running state first
apps.sort(key=lambda a: (not a.get('running',False), not a.get('ready',False), -a.get('adjusted_score',0)))
for app in apps[:20]:
    state = 'RUNNING' if app.get('running') else 'offline'
    ready = '✓' if app.get('ready') else ' '
    url = app.get('ready_url','') or ''
    title = app.get('title', app.get('name',''))[:40]
    desc = (app.get('description','') or '')[:70]
    print(f'  [{state:7}] {ready} {title:42s} {url}')
    if desc:
        print(f'            {desc}')
"
```

## Notes

- On Windows, always use `"$PTERM"` (the `.cmd` shim), not bare `pterm`
- Output is JSON; parse with `.get('apps',[])`
- State priorities: `running=True` > `ready=True` > `score descending`
- Registry search (remote): `pterm registry search <query>` — separate command

## Related

- `/pinokio:app-start <app_id>` — launch an installed app
- `/pinokio:app-stop <app_id>` — gracefully stop a running app
- `/voice:status` — check voice-specific Pinokio apps
