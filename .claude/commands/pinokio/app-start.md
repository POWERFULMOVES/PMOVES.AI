---
description: Start a Pinokio app via pterm with health polling
---

# pinokio:app-start

Launch a Pinokio app and wait for it to become ready. Uses `pterm start` with the app's default launcher script, then polls the ready URL until healthy.

## Usage

```
/pinokio:app-start <app_id> [timeout_seconds]
```

**Arguments:**
- `app_id` — Pinokio app identifier (e.g., `voicebox.pinokio.git`, `Ultimate-TTS-Studio-SUP3R-Edition-Pinokio.git`)
- `timeout_seconds` — Max wait time (default: 300 for large CUDA model loads)

## Implementation

```bash
# Pinokio root is a PER-NODE value (C: here, D: on other nodes), so derive it.
# pinokio-root.sh exits 1 when it had to guess -- see .claude/scripts/pinokio-root.sh
PTERM="$(bash .claude/scripts/pinokio-root.sh --exe)"
APP_ID="{{args.app_id}}"
TIMEOUT="{{args.timeout_seconds|default:300}}"

# Trigger launch (pterm run = equivalent to clicking "Run" in the UI)
"$PTERM" run "$APP_ID" 2>&1 | head -5

# Poll for ready state every 5s
for i in $(seq 1 $((TIMEOUT / 5))); do
  STATE=$("$PTERM" search "$APP_ID" 2>&1 | python -c "
import sys, json
d = json.load(sys.stdin)
for app in d.get('apps', []):
    if app.get('name') == '$APP_ID':
        print(f\"{app.get('state','?')}|{app.get('ready','false')}|{app.get('ready_url','') or ''}\")
        break
" 2>/dev/null)
  READY=$(echo "$STATE" | cut -d'|' -f2)
  URL=$(echo "$STATE" | cut -d'|' -f3)
  if [ "$READY" = "True" ] && [ -n "$URL" ]; then
    echo "READY: $URL (after ${i}*5s)"
    exit 0
  fi
  sleep 5
done
echo "TIMEOUT after ${TIMEOUT}s waiting for $APP_ID"
exit 1
```

## Notes

- CUDA model loads on first start can take 2-5 minutes (Ultimate-TTS-Studio loads 14 engines)
- Second+ starts are faster (models cached)
- `pterm run` triggers the default launcher (usually `start.js`)
- The ready_url is captured by the launcher's regex event handler (see gepeto-SKILL.md)

## Related

- `/pinokio:app-stop <app_id>` — graceful shutdown
- `/pinokio:app-search` — find the exact app_id
- `/voice:status` — after starting a TTS app, verify Flute-Gateway can reach it
