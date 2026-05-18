---
name: pterm
description: >
  Pinokio pterm CLI wrappers: clipboard read/write, desktop notifications,
  file/folder picker (native dialog), script testing via pterm start,
  and cross-platform system operations from Claude Code sessions.
  Requires Pinokio installed at D:\pinokio and pterm in PATH.
---

# pterm — Pinokio Terminal CLI

Wraps the Pinokio `pterm` CLI for use from Claude Code sessions. Provides
cross-platform access to system clipboard, desktop notifications, native
file pickers, and Pinokio script execution — bridging Claude Code with
the Pinokio launcher ecosystem.

## Prerequisites

```bash
# Verify pterm is available
pterm --version || echo "pterm not in PATH — add D:\pinokio\bin to PATH"
```

## Clipboard

```bash
# Read from clipboard
pterm clipboard read

# Write to clipboard
echo "content to copy" | pterm clipboard write

# Example: copy a file path to clipboard
pterm clipboard write "C:\Users\DARKXSIDE\Documents\POWERFULMOVES"
```

## Desktop Notifications

```bash
# Send a notification
pterm push "PMOVES session complete" --title "Claude Code"

# Notify when a long task finishes
make -C pmoves fleet-status && pterm push "Fleet status OK" --title "PMOVES"
```

## File/Folder Picker (Native Dialog)

```bash
# Open a file picker — returns selected path
SELECTED=$(pterm filepicker)
echo "Selected: $SELECTED"

# Open a folder picker
FOLDER=$(pterm filepicker --folder)

# Use in a script
FILE=$(pterm filepicker --filter "*.yaml") && cat "$FILE"
```

## Script Testing

```bash
# Test a Pinokio launcher script
pterm start "D:\pinokio\api\pmoves-pbnj\start.js"

# Test install script
pterm start "D:\pinokio\api\pmoves-pbnj\install.js"

# Check if script is running
pterm running "D:\pinokio\api\pmoves-pbnj\start.js" && echo "Running" || echo "Stopped"
```

## VSCode Integration

The `.vscode/tasks.json` includes pterm tasks. Run via VSCode's task runner
(`Ctrl+Shift+P` → "Run Task"):

| Task | pterm command |
|------|---------------|
| Notify: Fleet OK | `pterm push "Fleet OK"` |
| Pick config file | `pterm filepicker --filter "*.yaml"` |
| Copy branch to clipboard | `git branch --show-current \| pterm clipboard write` |

## Pinokio App Management

```bash
# List installed Pinokio apps
pterm list

# Open a Pinokio app
pterm open "pmoves-pbnj"

# Get app status
pterm status "pmoves-pbnj"
```

## Notes

- `pterm` is the Pinokio terminal CLI — distinct from the Python `pterm` terminal library
- Pinokio installs pterm at `D:\pinokio\bin\pterm.exe` on Windows
- All pterm commands are cross-platform: Windows, Mac, Linux
- File picker uses native OS dialogs (Windows Explorer on Windows)
- Notifications use the OS notification system (Windows toast notifications)
- See PTERM documentation at `D:\pinokio\prototype\PTERM.md` for full API
- See `gepeto` and `pinokio` skills for Pinokio AI coding and app discovery
