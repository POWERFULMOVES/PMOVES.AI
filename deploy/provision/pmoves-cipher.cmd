@echo off
REM pmoves-cipher.cmd -- double-click / run to launch pmoves-cipher with
REM pmoves/env.shared loaded. Wraps the .ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pmoves-cipher.ps1" %*
