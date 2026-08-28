# claude-pmoves.ps1 — launch Claude Code with pmoves/env.shared loaded so the MCP
# servers in .claude/mcp.json get their creds (Windows twin of claude-pmoves.sh).
# See that file's header for the why. env.shared is the single source of truth,
# kept fresh by `make -C pmoves secrets-runtime-hydrate`.
#
# Usage:  powershell -ExecutionPolicy Bypass -File deploy\provision\claude-pmoves.ps1  [args]
#   (or double-click / run claude-pmoves.cmd, which calls this)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envf = if ($env:PMOVES_ENV_SHARED) { $env:PMOVES_ENV_SHARED } else { Join-Path $root 'pmoves\env.shared' }

if (Test-Path $envf) {
    # Blocklist: vars that control Claude SDK/session behavior and should NEVER be
    # sourced by the launcher. These are user's personal billing/config, not fleet MCP creds.
    # Sourcing them forces API billing (ANTHROPIC_API_KEY) or clobbers session state.
    $blocklist = @(
        'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL'
        'CLAUDECODE', 'CLAUDE_CODE_*', 'CLAUDE_SESSION_*'
    ) -replace '\*', '.*'

    # Pass 1: read KEY=VALUE verbatim into an ordered map, skipping blocklisted keys.
    # Values are NOT set into the environment yet — env.shared has ALIAS lines like
    # SUPABASE_SERVICE_ROLE_KEY=${SERVICE_ROLE_KEY}; exporting them verbatim leaks
    # the literal "${SERVICE_ROLE_KEY}" into the MCP --apiKey, starting an
    # alias-backed MCP unauthorized even though the canonical key is present
    # (Codex #1987 P2). Mirror pmoves/scripts/with-env.sh: resolve first.
    $vars = [ordered]@{}
    foreach ($line in Get-Content -LiteralPath $envf) {
        if ($line -match '^\s*#') { continue }        # comment
        if ($line -match '^\s*$') { continue }        # blank
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        # Skip blocklisted keys (these control Claude SDK/session, not MCP)
        $blocked = $false
        foreach ($pat in $blocklist) { if ($key -match "^$pat$") { $blocked = $true; break } }
        if ($blocked) { continue }
        $val = ($line.Substring($eq + 1) -replace '\r$','')
        if ($key) { $vars[$key] = $val }
    }
    # Pass 2: expand ${VAR} and ${VAR:-default} against the map (mirrors the shell
    # `source` in claude-pmoves.sh). Bounded iteration resolves chained aliases;
    # stops early once a pass makes no substitution. A reference resolves to another
    # key only when that key is itself fully resolved; a self-reference
    # (KEY=${KEY:-default}, the compose self-default idiom) skips the var branch and
    # falls to the default, exactly as the shell's `:-` does.
    for ($pass = 0; $pass -lt 5; $pass++) {
        $changed = $false
        foreach ($k in @($vars.Keys)) {
            $curKey = $k
            $resolved = [regex]::Replace($vars[$k], '\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}', {
                param($m)
                $name = $m.Groups[1].Value
                $repl = $null
                if ($name -ne $curKey) {
                    if ($vars.Contains($name) -and $vars[$name] -ne '' -and $vars[$name] -notmatch '\$\{') {
                        $repl = $vars[$name]                                  # another resolved key
                    } else {
                        $envv = [Environment]::GetEnvironmentVariable($name)  # real process env (parity with shell source)
                        if ($envv) { $repl = $envv }
                    }
                }
                if ($null -ne $repl) { $repl }
                elseif ($m.Groups[2].Success) { $m.Groups[2].Value }         # ${VAR:-default}
                else { '' }                                                  # unset, no default
            })
            if ($resolved -ne $vars[$k]) { $vars[$k] = $resolved; $changed = $true }
        }
        if (-not $changed) { break }
    }
    $n = 0
    foreach ($k in $vars.Keys) { [Environment]::SetEnvironmentVariable($k, $vars[$k], 'Process'); $n++ }
    Write-Host "[claude-pmoves] loaded $n vars from $envf"
} else {
    Write-Warning "[claude-pmoves] $envf not found - MCP creds may be missing. Run: make -C pmoves ensure-env-shared"
}

# ---------------------------------------------------------------------------
# Interpreter discovery — the Windows half of pmoves/scripts/pm-python.sh.
#
# This block exists because the FAIL-CLOSED gate below was mirrored from the
# POSIX twin and the discovery it gates on was not. The ps1 tried exactly
# `Get-Command python` then `Get-Command python3`, and on a stock Windows 10/11
# node BOTH resolve to the Microsoft Store app-execution alias in
# %LOCALAPPDATA%\Microsoft\WindowsApps. Get-Command SUCCEEDS on that alias, so
# the "no interpreter" branch never fired, the normalizer never ran, and the
# gate refused a node that had previously warned and launched — via an override
# ($env:PMOVES_PYTHON) this file did not read and a remedy (`make -C pmoves
# preflight`) whose output (pmoves\.venv-pmoves) it did not look in.
#
# PRESENCE IS NOT RUNNABILITY. That is the whole lesson: the stub is present.
# So every candidate is RUN before it is accepted, exactly as pm-python.sh does.
# ---------------------------------------------------------------------------

function Test-PmovesPythonRuns {
    <#
      Runs `<argv> -c 'pass'` — a no-op for any real interpreter, non-zero for
      anything that is not one. This is what rejects the Store stub, which
      answers with "Python was not found; run without arguments to install from
      the Microsoft Store" and a non-zero code.

      pm-python.sh probes with `-c ''`. An EMPTY argument is not safely passable
      to a native command from Windows PowerShell 5.1 (it can be dropped, which
      would turn the probe into `python -c` and reject a GOOD interpreter — the
      same class of silent misjudgement this whole change is about), so the
      no-op is spelled `pass`. Same semantics, no quoting hazard.
    #>
    param([string[]]$Argv)
    # Function-scoped: a candidate that is not an interpreter is EXPECTED to
    # fail, and under the script's 'Stop' preference that failure (or a native
    # non-zero exit, under $PSNativeCommandUseErrorActionPreference on PS 7.4+)
    # would terminate the launcher instead of advancing the ladder.
    $ErrorActionPreference = 'SilentlyContinue'
    $PSNativeCommandUseErrorActionPreference = $false
    if (-not $Argv -or $Argv.Count -eq 0) { return $false }
    $exe  = $Argv[0]
    $rest = if ($Argv.Count -gt 1) { $Argv[1..($Argv.Count - 1)] } else { @() }
    $global:LASTEXITCODE = 1
    try { & $exe @rest -c 'pass' *> $null } catch { return $false }
    return ($LASTEXITCODE -eq 0)
}

function Get-PmovesPythonArgv {
    <#
      Returns a string[] argv vector for a python that RUNS, or $null.
      Same rungs as pm-python.sh; `py -3` is tried before `python3` because on
      Windows `python3` is the Store alias and `py` is the real launcher that
      ships with every python.org install — probing the launcher first avoids
      the stub's console message in the common case. Both are probed either
      way, so the order changes noise, not the outcome.
    #>
    param([Parameter(Mandatory)][string]$Root)

    # 0. Operator pin always wins. Space-separated so multi-word vectors like
    #    `py -3` work, but a path is tried VERBATIM first: the Windows default
    #    install path is C:\Program Files\Python313\python.exe, and splitting
    #    that on whitespace would make the pin the launcher advertises as its
    #    own remedy fail on the platform's default layout.
    if ($env:PMOVES_PYTHON) {
        $verbatim = $env:PMOVES_PYTHON.Trim()
        if ($verbatim -and (Test-Path -LiteralPath $verbatim -PathType Leaf) -and
            (Test-PmovesPythonRuns @($verbatim))) {
            return , @($verbatim)
        }
        $pin = @($env:PMOVES_PYTHON -split '\s+' | Where-Object { $_ -ne '' })
        if ($pin.Count -gt 0 -and (Test-PmovesPythonRuns $pin)) { return , $pin }
        # An explicit pin that does not run is an ERROR, not a hint. Falling
        # through to a guess is how `PMOVES_PYTHON=" "` became "python3 is
        # missing" on the POSIX side.
        return $null
    }

    # 1. The canonical venv — what `make -C pmoves preflight` provisions, and
    #    therefore what the refusal below is allowed to name as a remedy.
    foreach ($c in @(
            (Join-Path $Root 'pmoves\.venv-pmoves\Scripts\python.exe'),
            (Join-Path $Root 'pmoves\.venv-pmoves\bin\python'))) {
        if ((Test-Path -LiteralPath $c -PathType Leaf) -and (Test-PmovesPythonRuns @($c))) {
            return , @($c)
        }
    }

    # 2. Platform launchers. Written out rather than looped for the same reason
    #    pm-python.sh writes its branches out: `py -3` is two words and
    #    `python3` is one, and no array-flattening rule should be load-bearing
    #    in the code that decides whether this node can start a session.
    if (Test-PmovesPythonRuns @('py', '-3')) { return , @('py', '-3') }
    if (Test-PmovesPythonRuns @('python3'))  { return , @('python3') }
    if (Test-PmovesPythonRuns @('python'))   { return , @('python') }
    return $null
}

function Test-PmovesRosterHasBarePlaceholder {
    <#
      Does this roster hold a reference that would be SENT as literal text?

      Not the same question as "does the file contain the characters ${". Two
      cases where it is not:
        * `${VAR:-default}` is the documented REMEDY, not the disease — an
          unset var expands to the default, and .claude/mcp.json uses exactly
          this for the cipher bearer today.
        * `${...}` inside a `_`-prefixed key is Claude-ignored metadata. The
          tracked roster's own `_note` quotes "uses the unexpanded ${VAR} text
          as-is" verbatim, so a whole-file match refuses a fully-expanded node.

      So: a BARE ${IDENT} on a line that is not a `_`-prefixed key. Kept in step
      with the same predicate in deploy/provision/claude-pmoves.sh.
    #>
    param([Parameter(Mandatory)][string]$Path)
    $ErrorActionPreference = 'SilentlyContinue'
    foreach ($line in (Get-Content -LiteralPath $Path)) {
        if ($line -match '^\s*"_[^"]*"\s*:') { continue }
        if ($line -match '\$\{[A-Za-z_][A-Za-z0-9_]*\}') { return $true }
    }
    return $false
}

# Hand off to claude with any passed args.
# Claude Code only reads `.mcp.json` at the repo root (project scope),
# `~/.claude.json` (user/local), or an explicit `--mcp-config` — it does NOT read
# `.claude/mcp.json`. Without this flag every server defined there stays dark and
# the vars loaded above have nothing to resolve into (Unix twin: claude-pmoves.sh).
# NOT --strict-mcp-config: merge, so the per-node `.mcp.json` written by
# `make -C pmoves mcp-toolkit-connect` stays live alongside the tracked roster.
$roster = Join-Path $root '.claude\mcp.json'
if (Test-Path $roster) {
    # Normalize the roster before handing it to Claude. The transform used to be
    # inline here AND, separately, as a heredoc in claude-pmoves.sh -- two copies
    # that drifted: the POSIX one grew ${VAR} resolution and this one did not, so
    # a Windows node still got `http://${TS_Z890}:8105/mcp/sse` handed over as a
    # literal hostname. Z890 is itself a Windows node, so the blind launcher was
    # the one running on the machine the URL names.
    #
    # Both now call the same platform-neutral tool (P2 drop `_` keys, P3 absolute
    # ./ paths, P4 expand ${VAR}, P5 drop unresolvable urls / warn on degraded
    # creds). When it cannot run, the block below names WHICH of the four causes
    # it was and refuses if the raw roster would leave credentials as literal
    # ${VAR} text -- see the gate for why that is not the fail-open call the
    # identity resolver makes.
    # Kept deliberately in step with the POSIX twin (deploy/provision/claude-pmoves.sh).
    # The comment above records what happened last time these two drifted: the
    # POSIX one grew ${VAR} resolution and this one did not, and the blind
    # launcher was the one running on the machine the URL names. The same
    # applies to the FAILURE path, which is why the diagnosis and the
    # fail-closed gate below are mirrored rather than left as "warn and go".
    $useRoster = $roster
    $resolvedOk = $false
    $why = ''
    $normalizer = Join-Path $root 'pmoves\tools\mcp_roster_normalize.py'
    $pyArgv = Get-PmovesPythonArgv -Root $root
    if (-not (Test-Path $normalizer)) {
        $why = "the normalizer is missing: $normalizer"
    } elseif (-not $pyArgv) {
        # Names every rung, because the operator's next command depends on
        # knowing what was already searched. 'tried python, then python3' sent
        # them to install a python the launcher may well have had.
        $why = "no usable python interpreter (tried `$env:PMOVES_PYTHON, $root\pmoves\.venv-pmoves, py -3, python3, python; each candidate was RUN, so a Microsoft Store stub counts as absent)"
    } else {
        $pyShown = ($pyArgv -join ' ')
        $pyExe   = $pyArgv[0]
        $pyPre   = if ($pyArgv.Count -gt 1) { $pyArgv[1..($pyArgv.Count - 1)] } else { @() }
        try {
            # The tool prints the path it wrote on stdout; warnings go to stderr
            # and pass through to the console.
            $out = & $pyExe @pyPre $normalizer $roster '--root' $root '--label' 'claude-pmoves'
            if ($LASTEXITCODE -ne 0) {
                $why = "the normalizer exited $LASTEXITCODE under '$pyShown' (its own stderr is above)"
            } elseif (-not $out) {
                $why = 'the normalizer exited 0 but printed no roster path - nothing was written'
            } else {
                $useRoster = ([string](@($out)[-1])).Trim()
                $resolvedOk = $true
            }
        } catch {
            $why = "the normalizer could not be run under '$pyShown': $($_.Exception.Message)"
        }
    }

    if (-not $resolvedOk) {
        # FAIL CLOSED when the raw roster would carry literal ${VAR}s. Claude
        # Code's documented response to an unresolvable reference is to warn and
        # then use the unexpanded text AS THE VALUE, so the bearer header goes
        # out as the string 'Bearer ${CIPHER_API_TOKEN}' and a cross-node url as
        # the hostname '${TS_Z890}'. Those servers load, look configured, and
        # never authenticate -- and nothing inside the session can tell that
        # apart from "the service is down".
        Write-Warning "[claude-pmoves] could not normalize the MCP roster."
        Write-Warning "[claude-pmoves] cause: $why"
        if (Test-PmovesRosterHasBarePlaceholder -Path $roster) {
            Write-Warning ('[claude-pmoves] LOST: ' + $roster + ' still contains bare ${VAR} references;')
            Write-Warning '[claude-pmoves]       they are sent LITERALLY, so those MCP servers cannot authenticate.'
            if (-not $env:PMOVES_ALLOW_RAW_ROSTER) {
                Write-Warning '[claude-pmoves] Refusing to start a session whose MCP credentials are placeholders.'
                # Every remedy below is reachable from the path actually taken:
                # the venv preflight writes is now rung 1 of the ladder, and
                # PMOVES_PYTHON is rung 0. Naming a fix the launcher cannot act
                # on leaves the operator refused after following instructions.
                Write-Warning '[claude-pmoves] Fix one of:'
                Write-Warning '[claude-pmoves]   make -C pmoves preflight       # provisions pmoves\.venv-pmoves, which is searched'
                Write-Warning '[claude-pmoves]   $env:PMOVES_PYTHON=''C:\Path\To\python.exe''   # pin an interpreter explicitly'
                Write-Warning '[claude-pmoves]   (a Microsoft Store python.exe stub does not count - it is present but does not run)'
                Write-Warning '[claude-pmoves] Or accept a credential-less session on purpose, this once:'
                Write-Warning '[claude-pmoves]   $env:PMOVES_ALLOW_RAW_ROSTER=1; <your usual command>'
                exit 1
            }
            Write-Warning '[claude-pmoves] PMOVES_ALLOW_RAW_ROSTER is set - launching anyway.'
        } else {
            # Nothing left to expand: the raw file authenticates exactly as the
            # normalized one would, so refusing here would be a lock with
            # nothing behind it. Say what IS lost and start.
            Write-Warning "[claude-pmoves] launching with the RAW roster $roster; credentials are intact."
            Write-Warning '[claude-pmoves] No bare ${VAR} references remain (a ${VAR:-default} sends its default).'
            Write-Warning "[claude-pmoves] Lost: '_'-prefixed disabled duplicates are not dropped, and ./ paths stay relative to your CWD."
        }
    }
    # `--mcp-config=<file>` (the `=` form): `--mcp-config` is variadic
    # (`<configs...>`), so the space form would swallow a trailing positional
    # prompt as another config value (Codex #2243 P1).
    & claude "--mcp-config=$useRoster" @args
} else {
    Write-Warning "[claude-pmoves] $roster not found - PMOVES MCP servers will not load."
    & claude @args
}
exit $LASTEXITCODE
