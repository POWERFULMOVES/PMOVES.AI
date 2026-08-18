@echo off
rem kimi-pmoves - Windows shim; delegates to the canonical bash script
rem (script checks .kimi/config.toml + mcp.json before launching kimi)
rem Repo root baked at install time; Git Bash probed before PATH (WSL stub shadows it).
setlocal
set "REPO_ROOT=__PMOVES_REPO_ROOT__"
set "BASH="
if exist "%ProgramFiles%\Git\bin\bash.exe" set "BASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined BASH if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "BASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined BASH set "BASH=bash"
pushd "%REPO_ROOT%"
"%BASH%" pmoves/scripts/kimi-pmoves.sh %*
set "EC=%ERRORLEVEL%"
popd
exit /b %EC%
