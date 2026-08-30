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
rem Usage: claude-pmoves [agent-name] [claude-args...]   (default: node-steward)
rem A leading flag (e.g. -r, --resume) implies the default agent.
rem
rem DEFAULT_AGENT is spelled out below rather than inherited: this shim routes
rem through deploy\provision\claude-pmoves.cmd, which has no default-agent logic
rem of its own -- the fallback lives in pmoves\scripts\claude-pmoves.sh, which
rem Windows never executes. Omitting it here would pass NO agent at all.
rem Keep this value in step with DEFAULT_AGENT in that script.
setlocal
set "REPO_ROOT=__PMOVES_REPO_ROOT__"
set "LAUNCHER=%REPO_ROOT%\deploy\provision\claude-pmoves.cmd"
set "DEFAULT_AGENT=node-steward"
if not exist "%LAUNCHER%" (
  echo [claude-pmoves] canonical launcher missing: %LAUNCHER% 1>&2
  echo [claude-pmoves] refusing to fall back to raw `claude` - it would start with no 1>&2
  echo [claude-pmoves] env.shared and no MCP roster, which is worse than not starting. 1>&2
  exit /b 1
)
rem NODE IDENTITY -- the same binding pmoves\scripts\claude-pmoves.sh does, and
rem it has to be here too for the same reason DEFAULT_AGENT is duplicated above:
rem Windows never executes that script. The 4090 -- the node the identity work
rem was built FOR -- launches through this file, so an identity wired only into
rem the .sh would have been correct, tested, and unreachable on the one machine
rem that needed it.
rem
rem --format cmd, not --shell: cmd.exe has no `eval` and would take the POSIX
rem single quotes literally, setting PMOVES_NODE to the five characters '4090'.
rem
rem FAIL-OPEN, LOUDLY, exactly as the .sh does. `2^>nul` hides the tool's own
rem stderr, never the reason -- that arrives as PMOVES_IDENTITY_WHY and is
rem echoed below. Keep in step with claude-pmoves.sh; the parity test in
rem pmoves\tests\test_node_identity.py fails if one grows the call and the other
rem does not.
rem NO PARENTHESISED if/else BLOCKS BELOW, deliberately. The tool's reason
rem strings contain literal `(` and `)` -- e.g. "declared (node-vocabulary.yaml:
rem 4090.default_identity.claude-code) but is not in agent_registry.yaml" -- and
rem cmd.exe expands %VAR% while PARSING a block, so the first `)` in the value
rem closes the block early. Measured: the first draft of this file died with
rem "but was unexpected at this time." before reaching the launcher. goto-based
rem flow has no block to close.
rem PMOVES_NODE_IDENTITY is NOT cleared here: it is the operator's input
rem override, and the resolver reads it from the environment. Clearing it first
rem destroyed the override before the tool could honour it -- caught by running
rem this file, not by reading it. The tool answers under PMOVES_RESOLVED_IDENTITY.
set "PMOVES_NODE="
set "PMOVES_RESOLVED_IDENTITY="
set "PMOVES_IDENTITY_WHY="
set "IDENT_ARGS="
set "IDENT_TOOL=%REPO_ROOT%\pmoves\tools\node_identity.py"
if not exist "%IDENT_TOOL%" goto ident_absent
rem Parity with claude-pmoves.sh: this launcher runs before the harness loads
rem .claude\settings.local.json, so a collision-hostname node (the 5090,
rem POWERFULMOVES -> powerfulmoves org entry) needs PMOVES_NODE_ID from that
rem env block to bind. A shell env value already set still wins.
if not defined PMOVES_NODE_ID (
  for /f "usebackq delims=" %%I in (`python -c "import json;print((json.load(open(r'%REPO_ROOT%\.claude\settings.local.json')).get('env') or {}).get('PMOVES_NODE_ID',''))" 2^>nul`) do set "PMOVES_NODE_ID=%%I"
)
for /f "usebackq tokens=1,* delims==" %%A in (
  `python "%IDENT_TOOL%" --harness claude-code --format cmd 2^>nul`
) do set "%%A=%%B"
if defined PMOVES_RESOLVED_IDENTITY goto ident_bound
if defined PMOVES_IDENTITY_WHY goto ident_why
:ident_absent
echo [claude-pmoves] node identity: resolver did not run; launching without it. 1>&2
goto ident_done
:ident_why
rem Quoted: the reason contains parentheses that would otherwise be parsed.
echo "[claude-pmoves] identity unresolved: %PMOVES_IDENTITY_WHY%" 1>&2
goto ident_done
:ident_bound
echo [claude-pmoves] node=%PMOVES_NODE% identity=%PMOVES_RESOLVED_IDENTITY% agent=%DEFAULT_AGENT% 1>&2
set "IDENT_ARGS=--append-system-prompt "You are running on PMOVES node '%PMOVES_NODE%'. Your registered identity in pmoves/config/agent_registry.yaml is '%PMOVES_RESOLVED_IDENTITY%'. Disclose it at session start rather than rediscovering it.""
:ident_done

set "first=%~1"
set "prefix=%first:~0,1%"
if "%prefix%"=="-" goto flag
if "%first%"=="" goto default
call "%LAUNCHER%" --agent %* %IDENT_ARGS%
exit /b %ERRORLEVEL%
:flag
call "%LAUNCHER%" --agent %DEFAULT_AGENT% %* %IDENT_ARGS%
exit /b %ERRORLEVEL%
:default
call "%LAUNCHER%" --agent %DEFAULT_AGENT% %IDENT_ARGS%
exit /b %ERRORLEVEL%
