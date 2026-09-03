---
description: Stop a running Pinokio app gracefully
---

# pinokio:app-stop

Gracefully stop a running Pinokio app via `pterm stop`. Verifies the app transitions to offline state.

## Usage

```
/pinokio:app-stop <app_id>
```

**Arguments:**
- `app_id` — Pinokio app identifier

## Implementation

```bash
# Pinokio root is a PER-NODE value (C: here, D: on other nodes), so derive it.
# pinokio-root.sh exits 1 when it had to guess -- see .claude/scripts/pinokio-root.sh
PTERM="$(bash .claude/scripts/pinokio-root.sh)/bin/npm/pterm.cmd"
APP_ID="{{args.app_id}}"

# Stop command
"$PTERM" stop "$APP_ID" 2>&1 | head -5

# Verify transition to offline
sleep 2
"$PTERM" search "$APP_ID" 2>&1 | python -c "
import sys, json
d = json.load(sys.stdin)
for app in d.get('apps', []):
    if app.get('name') == '$APP_ID':
        state = app.get('state','?')
        running = app.get('running', False)
        print(f'State: {state}, Running: {running}')
        sys.exit(0 if not running else 1)
print(f'App not found: $APP_ID')
sys.exit(1)
"
```

## Notes

- Pinokio's stop is cooperative — the launcher script's daemon loop receives SIGTERM
- CUDA models are unloaded from VRAM during shutdown
- Stopping a TTS app that Flute-Gateway depends on will cause 502s downstream — stop in dependency order

## Related

- `/pinokio:app-start` — launch apps
- `/voice:status` — check if voice providers remain available after stop
