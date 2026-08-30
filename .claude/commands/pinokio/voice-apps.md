---
description: List all voice/TTS Pinokio apps with their states and API endpoints
---

# pinokio:voice-apps

Voice-specific Pinokio app discovery. Filters for TTS/voice/audio apps and shows their API endpoints for Flute-Gateway integration.

## Usage

```
/pinokio:voice-apps
```

## Implementation

```bash
python -c "
import json, subprocess
result = subprocess.run(
    ['D:/pinokio/bin/npm/pterm.cmd', 'search', ''],
    capture_output=True, text=True, encoding='utf-8', errors='replace'
)
d = json.loads(result.stdout)
apps = d.get('apps', [])

# Known voice apps (filter list)
voice_keywords = ('voice', 'tts', 'whisper', 'audio', 'speech', 'kokoro', 'f5',
                  'chatterbox', 'fish', 'vibevoice', 'voxcpm', 'higgs', 'qwen', 'luxtts',
                  'voicebox', 'voxforge', 'ultimate-tts')

def is_voice(app):
    text = ' '.join([
        app.get('name',''),
        app.get('title',''),
        app.get('description','') or ''
    ]).lower()
    return any(kw in text for kw in voice_keywords)

voice_apps = [a for a in apps if is_voice(a)]
running = [a for a in voice_apps if a.get('running')]
offline = [a for a in voice_apps if not a.get('running')]

print(f'Voice apps: {len(voice_apps)} ({len(running)} running)')
print()

for app in running:
    url = app.get('ready_url','') or ''
    print(f'  🟢 {app.get(\"title\",app[\"name\"])[:40]:42s} {url}')
    if app.get('description'):
        print(f'      {app[\"description\"][:80]}')

if offline:
    print()
    print(f'  Offline ({len(offline)}):')
    for app in offline:
        last = (app.get('last_launch_at','') or '')[:10] or 'never'
        print(f'    ⭕ [{last}] {app.get(\"title\",app[\"name\"])[:42]}')
"
```

## Known Voice Apps (Session 11 Inventory)

| App | API | Engines | Cloning | Streaming |
|-----|-----|---------|---------|-----------|
| **Voicebox** | FastAPI :17493 | 5 | ✅ | ✅ |
| **Ultimate-TTS-Studio SUP3R** | Gradio :7860 | 14 | ✅ (4 engines) | — |
| **VoxForge Pro** | Gradio | 2 | ✅ | — |
| **Qwen3-TTS** | Gradio | 1 | ✅ | — |
| **VibeVoice Realtime** | WebSocket | 1 | — | ✅ |

## Related

- `/voice:status` — health check for Flute-Gateway + TTS backends
- `/tts:test-engine <engine>` — test via Flute-Gateway production HTTP
- `pmoves/docs/TAC/TAC_VOICE_PRODUCTION.md` — full voice pipeline review
