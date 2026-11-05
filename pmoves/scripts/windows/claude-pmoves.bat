@echo off
rem claude-pmoves - Windows shim for the PMOVES Claude Code launcher.
rem
rem Routes through deploy\provision\claude-pmoves.cmd (-> claude-pmoves.ps1),
rem NOT the raw `claude` CLI. That launcher is what loads pmoves\env.shared and
rem passes --mcp-config with the repository's explicit MCP roster; invoking
rem `claude` directly leaves every credential-dependent MCP server dark while
rem still appearing to launch normally.
rem
rem Usage: claude-pmoves [agent-name] [claude-args...]   (default: no agent)
rem
rem A DELEGATE, NOT A SECOND LAUNCHER. Until 2026-11-04 this file also chose the
rem agent, resolved the node identity and built its own identity prompt, then
rem called claude-pmoves.ps1, which did the last two again. Measured on Z890
rem with a stub claude: identity resolved twice and claude received TWO
rem --append-system-prompt blocks, only one carrying the cipher carry. Every
rem rule now lives once, in claude-pmoves.ps1 (agent selection in
rem pmoves\scripts\pm-agent-select.ps1). Add nothing here but the hand-off;
rem pmoves\tests\test_node_identity.py holds that line.
setlocal
rem REPO ROOT -- baked at install time by pmoves\tools\install_tools.py, but
rem PMOVES_LAUNCHER_ROOT wins when set. The installed shim in ~/.local/bin is a
rem DELEGATE that sets that variable and calls THIS file, so the tracked
rem template is what actually runs; a frozen copy cannot be fixed (Z890 ran one
rem that called raw `claude` for a month, 2026-08-15 on).
rem
rem TWO PLAIN `set`s and no parenthesised blocks anywhere: cmd.exe expands %VAR%
rem while PARSING a block, so a root containing `)` -- C:\Program Files (x86) --
rem would close it early.
set "REPO_ROOT=__PMOVES_REPO_ROOT__"
if defined PMOVES_LAUNCHER_ROOT set "REPO_ROOT=%PMOVES_LAUNCHER_ROOT%"
set "LAUNCHER=%REPO_ROOT%\deploy\provision\claude-pmoves.cmd"
if not exist "%LAUNCHER%" goto missing
call "%LAUNCHER%" %*
exit /b %ERRORLEVEL%

:missing
echo [claude-pmoves] canonical launcher missing: %LAUNCHER% 1>&2
echo [claude-pmoves] refusing to fall back to raw `claude` - it would start with no 1>&2
echo [claude-pmoves] env.shared and no MCP roster, which is worse than not starting. 1>&2
exit /b 1
