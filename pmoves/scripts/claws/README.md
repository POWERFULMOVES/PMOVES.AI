# PMOVES Claws — Windows Node Setup (Non-Developer)

These scripts set up a Windows PC to join the PMOVES fleet. They're designed for users who **don't know PowerShell** — every step is a double-click and a click of **Yes**.

## How it works

For each task there is a `.cmd` file you can double-click:

1. Windows asks for permission (the **User Account Control** popup) — click **Yes**
2. A black window opens and does the work
3. When it says **Done. Press Enter to close.** press **Enter**

The output is also saved to a log file under `%TEMP%` so you don't need to copy text out of the window. The log path is printed at the end.

## Tasks

| What I want to do | Double-click this file | Run order |
|---|---|---|
| Let this PC accept SSH connections from PMOVES | `enable-ssh-elevated.cmd` | First |
| Lock SSH down to key-only (no passwords) | `harden-ssh-elevated.cmd` | After Enable, only if at least one key is installed |

## Tips

- Run `enable-ssh-elevated.cmd` **before** `harden-ssh-elevated.cmd`. The harden script refuses to run if no keys are installed (it would lock you out).
- Run `harden-ssh-elevated.cmd` from a window directly on **this PC** (or a remote-desktop session). Don't run it while you're already connected over SSH — restarting the SSH service drops the connection mid-way.
- Re-running either file is safe. They both skip work that has already been done.

## Logs

Each script writes its output to `%TEMP%\pmoves-<script-name>.log`. Examples:

- `%TEMP%\pmoves-enable-ssh-windows.log`
- `%TEMP%\pmoves-harden-ssh-windows.log`

To open the folder, paste `%TEMP%` into the Windows Run dialog (**Win+R**).

## For developers / contributors

`_elevate.cmd` is the generic elevation library used by both `.cmd` wrappers — it builds a tiny `.ps1` in `%TEMP%`, then uses `Start-Process -Verb RunAs` to UAC-elevate. The wrapper scripts are one-liners that forward arguments via `%*`.

Adding a new one-click admin task:

1. Add your `.ps1` to this folder (e.g., `rotate-tokens-windows.ps1`)
2. Add a `<task>-elevated.cmd` wrapper that does `@call "%~dp0_elevate.cmd" <task>-windows.ps1 %*`
3. Add an entry to this README and to `.claude/agents/windows-claw-operator.md`

If you want the agent to drive the new task, also document the expected log markers in the agent's verification section so it can confirm success without copy-paste from the user.
