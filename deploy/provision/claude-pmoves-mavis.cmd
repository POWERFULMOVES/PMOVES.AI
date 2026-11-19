@echo off
REM claude-pmoves-mavis.cmd -- Windows wrapper for the .ps1 twin.
REM See claude-pmoves-mavis.sh for the WHY.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0claude-pmoves-mavis.ps1" %*