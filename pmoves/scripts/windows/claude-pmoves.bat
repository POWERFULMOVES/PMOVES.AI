@echo off
rem claude-pmoves - Windows shim for the PMOVES Claude Code launcher
rem Usage: claude-pmoves [agent-name] [claude-args...]  (default: delivery-agent)
rem A leading flag (e.g. -r, --resume) implies the default agent.
rem No repo dependency: pure pass-through to the claude CLI.
setlocal
set "first=%~1"
set "prefix=%first:~0,1%"
if "%prefix%"=="-" goto flag
if "%first%"=="" goto default
claude --agent %*
exit /b %ERRORLEVEL%
:flag
claude --agent delivery-agent %*
exit /b %ERRORLEVEL%
:default
claude --agent delivery-agent
exit /b %ERRORLEVEL%
