---
name: pterm
description: >
  Pinokio pterm CLI wrappers: clipboard read/write, desktop notifications,
  file/folder picker (native dialog), script testing via pterm start,
  and system operations from Claude Code sessions on Windows.
  Requires Pinokio installed and pterm in PATH.
---

# pterm — Pinokio Terminal CLI (Windows)

Wraps the Pinokio `pterm` CLI for use from Claude Code sessions on Windows.
Provides access to system clipboard, desktop notifications, native file pickers,
and Pinokio script execution — bridging Claude Code with the Pinokio launcher.

> **Platform scope**: pterm is a Windows-native tool bundled with Pinokio.
> macOS/Linux support may vary — verify `pterm --version` before use.

## Prerequisites

```powershell
# Verify pterm is available (add Pinokio bin to PATH if not found)
pterm --version
```

## Clipboard

```powershell
# Read from clipboard
pterm clipboard read

# Write to clipboard
pterm clipboard write "content to copy"

# Example: copy a file path to clipboard
pterm clipboard write "C:\Users\$env:USERNAME\Documents\POWERFULMOVES"
```

## Desktop Notifications

```powershell
# Send a notification
pterm push "PMOVES session complete" --title "Claude Code"

# Notify when a long task finishes
make -C pmoves fleet-status; if ($?) { pterm push "Fleet status OK" --title "PMOVES" }
```

## File/Folder Picker (Native Dialog)

```powershell
# Open a file picker — returns selected path
$selected = pterm filepicker
Write-Host "Selected: $selected"

# Open a folder picker
$folder = pterm filepicker --folder

# Use in a script
$file = pterm filepicker --filter "*.yaml"
if ($file) { Get-Content $file }
```

## Script Testing

```powershell
# Test a Pinokio launcher script (adjust path to your install location)
pterm start "$env:LOCALAPPDATA\Pinokio\api\pmoves-pbnj\start.js"

# Check if script is running
pterm running "$env:LOCALAPPDATA\Pinokio\api\pmoves-pbnj\start.js"
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

```powershell
# List installed Pinokio apps
pterm list

# Open a Pinokio app
pterm open "pmoves-pbnj"

# Get app status
pterm status "pmoves-pbnj"
```

## Notes

- `pterm` is the Pinokio terminal CLI — distinct from the Python `pterm` terminal library
- Pinokio installs pterm in its `bin` directory — ensure this is on your PATH
- File picker uses native OS dialogs (Windows Explorer)
- Notifications use the OS notification system (Windows toast notifications)
- See Pinokio documentation for full pterm API reference
- See `gepeto` and `pinokio` skills for Pinokio AI coding and app discovery
