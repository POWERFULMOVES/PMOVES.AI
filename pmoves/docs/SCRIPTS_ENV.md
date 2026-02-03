# Scripts Env Loader

To prevent env “whack‑a‑mole”, use a single loader for all local scripts:

- File: `pmoves/scripts/with-env.sh`
- Layering order:
  1. `pmoves/env.shared.generated` (generated defaults)
  2. `pmoves/env.shared` (project defaults and secrets)
  3. `pmoves/.env.generated` (runtime‑generated values)
  4. `pmoves/.env.local` (developer overrides)

The loader:
- Trims stray spaces around `=` (e.g., `KEY= value` → `KEY=value`).
- Safely quotes values (handles spaces/JSON/`!`).
- Exports all keys into the current shell.

Usage in scripts (bash):

```
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/pmoves/scripts/with-env.sh"
```

Existing helper scripts have been updated to use this loader (UI realtime smoke, Jellyfin smoke). Prefer this include pattern for any new scripts.

