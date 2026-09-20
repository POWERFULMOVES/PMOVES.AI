@echo off
rem kilo-pmoves - Windows shim; delegates to the canonical bash script
rem (script resolves the per-node opencode config from the first arg)
rem Repo root baked at install time; Git Bash probed before PATH (WSL stub shadows it).
setlocal
rem REPO ROOT -- baked at install time, but PMOVES_LAUNCHER_ROOT wins when set.
rem The installed shim in ~/.local/bin is a DELEGATE that sets that variable and
rem calls THIS file, so the tracked template is what actually runs. Windows used
rem to get a frozen COPY instead, and a copy cannot be fixed: Z890 ran a shim
rem from 2026-08-15 that called raw `claude --agent delivery-agent` -- no
rem env.shared, no MCP roster, no node identity -- for a month, because nothing
rem re-ran the installer and nothing reported the drift. Unix already avoided
rem this with an exec-delegate (see UNIX_DELEGATE in pmoves/tools/install_tools.py);
rem this is the missing Windows half.
rem
rem TWO PLAIN `set`s, NOT an if/else block: cmd.exe expands %VAR% while PARSING
rem a parenthesised block, so a root containing `)` -- C:\Program Files (x86) --
rem would close the block early. Same trap the identity reason strings hit below.
set "REPO_ROOT=__PMOVES_REPO_ROOT__"
if defined PMOVES_LAUNCHER_ROOT set "REPO_ROOT=%PMOVES_LAUNCHER_ROOT%"
set "BASH="
if exist "%ProgramFiles%\Git\bin\bash.exe" set "BASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined BASH if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "BASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined BASH set "BASH=bash"
pushd "%REPO_ROOT%"
"%BASH%" pmoves/scripts/kilo-pmoves.sh %*
set "EC=%ERRORLEVEL%"
popd
exit /b %EC%
