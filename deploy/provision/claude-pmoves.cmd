@echo off
REM claude-pmoves.cmd — double-click / run to launch Claude Code with pmoves/env.shared
REM loaded so the MCP servers get their creds (all 200+ tools online). Wraps the .ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0claude-pmoves.ps1" %*
