@echo off
REM crush-pmoves.cmd — double-click / run to launch Charm Crush with pmoves/env.shared
REM loaded so the MCP servers in ~/.config/crush/crush.json get their creds. Wraps the .ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crush-pmoves.ps1" %*
