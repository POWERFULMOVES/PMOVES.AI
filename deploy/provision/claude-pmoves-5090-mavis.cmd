@echo off
REM claude-pmoves-5090-mavis.cmd -- Windows wrapper. Calls the .ps1 twin.
REM See claude-pmoves-5090-mavis.sh for the WHY.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0claude-pmoves-5090-mavis.ps1" %*