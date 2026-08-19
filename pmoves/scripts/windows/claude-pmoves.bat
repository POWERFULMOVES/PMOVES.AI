@echo off
rem claude-pmoves - Windows shim for the PMOVES Claude Code launcher.
rem
rem Routes through deploy\provision\claude-pmoves.cmd (-> claude-pmoves.ps1),
rem NOT the raw `claude` CLI. That launcher is what loads pmoves\env.shared and
rem passes --mcp-config with the repository's explicit MCP roster; invoking
rem `claude` directly leaves every credential-dependent MCP server dark while
rem still appearing to launch normally.
rem
rem Repo root is baked in at install time by pmoves\tools\install_tools.py.
rem Agent selection is preserved: the .ps1 forwards @args straight to claude.
rem
rem Usage: claude-pmoves [agent-name] [claude-args...]   (default: delivery-agent)
rem A leading flag (e.g. -r, --resume) implies the default agent.
setlocal
set "REPO_ROOT=__PMOVES_REPO_ROOT__"
set "LAUNCHER=%REPO_ROOT%\deploy\provision\claude-pmoves.cmd"
if not exist "%LAUNCHER%" (
  echo [claude-pmoves] canonical launcher missing: %LAUNCHER% 1>&2
  echo [claude-pmoves] refusing to fall back to raw `claude` - it would start with no 1>&2
  echo [claude-pmoves] env.shared and no MCP roster, which is worse than not starting. 1>&2
  exit /b 1
)
set "first=%~1"
set "prefix=%first:~0,1%"
if "%prefix%"=="-" goto flag
if "%first%"=="" goto default
call "%LAUNCHER%" --agent %*
exit /b %ERRORLEVEL%
:flag
call "%LAUNCHER%" --agent delivery-agent %*
exit /b %ERRORLEVEL%
:default
call "%LAUNCHER%" --agent delivery-agent
exit /b %ERRORLEVEL%
