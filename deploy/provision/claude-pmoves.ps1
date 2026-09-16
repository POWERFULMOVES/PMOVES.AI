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

# --- MAVIS SDK ENV STRIP ----------------------------------------------------
# The Mavis SDK's `env` block in `~/.claude/settings.json` injects
# ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_MODEL, MCP_TIMEOUT,
# API_TIMEOUT_MS, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC, ... into every
# Claude Code session's process env.  That env block is inherited by the
# shell that runs `claude-pmoves.ps1`, and would otherwise be inherited by
# the launched `claude` -- overriding the operator's own Claude Code settings
# (their Anthropic API endpoint, their model picker).
#
# The strip checks each Mavis SDK var against claude's NEEDS list
# (ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN + ANTHROPIC_API_KEY) and:
#   * keeps the ones claude consumes
#   * preserves the others under PMOVES_MAVIS_SDK_<NAME> for inspection
#   * unsets the originals
#   * emits one WARN line summarizing what was caught
#
# Mirrors deploy/provision/claude-pmoves.sh:42-66.  Both twins source the
# shared helper at pmoves/scripts/mavis_sdk_env.{sh,ps1} and call the
# per-platform strip function with the same registry keys.
# ----------------------------------------------------------------------------
$mavis_helper = Join-Path $root 'pmoves\scripts\mavis_sdk_env.ps1'
if (Test-Path $mavis_helper) {
    . $mavis_helper
    Strip-MavisSdkEnvFor -CliName 'claude'
} else {
    Write-Warning "[claude-pmoves] mavis_sdk_env.ps1 not found at $mavis_helper -- Mavis SDK env may bleed into the launched session."
}

if (Test-Path $envf) {
    # Blocklist: vars that control Claude SDK/session behavior and should NEVER be
    # sourced by the launcher. These are user's personal billing/config, not fleet MCP creds.
    # Sourcing them forces API billing (ANTHROPIC_API_KEY) or clobbers session state.
    #
    # Kept in step with deploy/provision/claude-pmoves.sh -- the bash twin
    # has the same names but uses `CLAUDE_CODE_.+` regex anchor; the
    # PowerShell twin's `-replace '\*','.*'` produces `CLAUDE_CODE_.*`.
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
    $script:launcherSession = "claude-pmoves.ps1 ($n vars)"
} else {
    Write-Warning "[claude-pmoves] $envf not found - MCP creds may be missing. Run: make -C pmoves ensure-env-shared"
    $script:launcherSession = 'claude-pmoves.ps1 (env file NOT FOUND)'
}

# Leave a marker in the process environment so "did this session come through
# the launcher" is ANSWERABLE from inside the session. Mirrors the export in
# claude-pmoves.sh; see the comment there for why launcher-check cannot answer
# it. Set on BOTH branches -- "loaded 0 vars" and "never ran" are different
# faults with different remedies, and a bare boolean would merge them.
[Environment]::SetEnvironmentVariable('PMOVES_LAUNCHER_SESSION', $script:launcherSession, 'Process')

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
# WHICH ROSTER: origin/main, not whatever branch this checkout sits on.
#
# The roster is FLEET configuration, not branch content, and binding it to the
# working tree made the toolset depend on a checkout's branch. Measured
# 2026-08-30 on the 4090: the repo root sat on a wip snapshot branch and the
# launcher loaded 14 servers where origin/main has 19 -- five missing, including
# `pmoves-cipher-local`, the loopback entry that needs no bearer. The visible
# symptom was `pmoves-cipher / failed` and a 401, which reads as a credential
# problem and was a checkout problem. Nothing reported the shortfall; you would
# have had to know 19 was the number.
#
# So: prefer origin/main's copy. Fall back to the tree when git cannot answer,
# and SAY WHICH in either case -- a launcher that silently picks a source is how
# this happened.
#   PMOVES_ROSTER_FROM_TREE=1  use the working tree (editing the roster itself)
# ---------------------------------------------------------------------------
# TAILNET NODE ADDRESSES -- the second thing the POSIX twin does and this file
# did not, with a measurable cost on this node.
#
# .claude/mcp.json addresses two MCP servers by tailnet name:
#     pmoves-cipher  -> ${TS_Z890}
#     agent-zero     -> ${TS_Z890}
# deploy/provision/claude-pmoves.sh sources pmoves/scripts/tailscale-node-ips.sh
# to resolve those. This file never did, so on Windows TS_Z890 stayed unset and
# the roster normalizer DROPPED both servers. Measured on Z890 2026-09-16, from
# this launcher's own output:
#     [claude-pmoves] WARN: dropping MCP server 'pmoves-cipher'
#                     unset variable(s): TS_Z890
# The bash helper's header already recorded this exact drift shipping here --
# "the same roster resolved under Crush and stayed literal under Claude" -- and
# the Windows half was the half left open.
#
# PORTED, NOT SHELLED OUT: invoking the .sh would need a bash on PATH, and a
# launcher that silently depends on Git Bash to reach its own memory service is
# the same class of hidden dependency. The mapping is small and lives beside its
# twin; test-launcher-root-resolution.sh is the existing pattern for keeping
# paired launchers honest.
#
# Addresses are 100.64/10 CGNAT and MUST stay runtime-derived -- the helper's
# header says baking one in would leak topology into a public tree and rot on
# re-registration. Nothing is hardcoded here.
#
# An already-set value WINS, matching _pm_ts_set: an operator pin beats the
# tailnet. Best-effort throughout -- no tailscale CLI just means unset, and the
# normalizer's existing drop-with-a-warning path still applies.
# ---------------------------------------------------------------------------
if (Get-Command tailscale -ErrorAction SilentlyContinue) {
    # Prefix match for b850 (`pmoves-b850-*`), exact for the rest -- same shape
    # as the case statement in tailscale-node-ips.sh.
    $tsExact = @{
        'pmoves-z890'   = 'TS_Z890'
        'pmoves-5090'   = 'TS_5090'
        'pmoves-4090'   = 'TS_4090'
        'pmoves-spark'  = 'TS_SPARK'
        'pmoves-kvm4-1' = 'TS_KVM4_1'
        'pmoves-kvm4-2' = 'TS_KVM4_2'
        'pmoves-kvm2'   = 'TS_KVM2'
    }
    try {
        foreach ($line in @(tailscale status 2>$null)) {
            $f = -split $line
            if ($f.Count -lt 2) { continue }
            $ip = $f[0]; $host_ = $f[1]
            $var = $null
            if ($tsExact.ContainsKey($host_)) { $var = $tsExact[$host_] }
            elseif ($host_ -like 'pmoves-b850-*') { $var = 'TS_B850' }
            if (-not $var) { continue }
            # already set wins
            if ([Environment]::GetEnvironmentVariable($var)) { continue }
            [Environment]::SetEnvironmentVariable($var, $ip, 'Process')
        }
    } catch {
        Write-Warning '[claude-pmoves] tailnet addresses: tailscale status failed; cross-node MCP servers may be dropped.'
    }
}
# ---------------------------------------------------------------------------
# NODE IDENTITY -- the Windows half of a binding that only ever ran on POSIX.
#
# pmoves/scripts/claude-pmoves.sh resolves the node's registered identity and
# injects it with --append-system-prompt, carrying this comment: "Exported
# variables do not reach the model's context; an appended system prompt does.
# This is the difference between the identity existing and the identity
# working." That is correct, and on this node it never ran: Windows enters
# through claude-pmoves.cmd -> this file, which had no identity logic at all.
#
# Measured on Z890 2026-09-16 inside a session launched the Windows way:
#   PMOVES_RESOLVED_IDENTITY=UNSET   PMOVES_NODE_IDENTITY=UNSET
# while the resolver, run by hand on the same node, answers immediately:
#   PMOVES_NODE='z890'  PMOVES_RESOLVED_IDENTITY='claude_z890'
#   WHY: node z890 via hostname=PMOVES-Z890; identity via node-vocabulary.yaml
#
# So the identity was never missing -- it was never ASKED FOR. A session that
# must rediscover who it is will sometimes guess, and the register already
# carries 49 distinct author strings for roughly a dozen identities
# (identity_vocabulary.yaml). Every one of those began as a session nobody told.
#
# FAIL-OPEN, deliberately, matching the POSIX twin: "an identity is a
# convenience; losing it must not cost you the session." Every failure warns
# and launches.
# ---------------------------------------------------------------------------
$identityArgs = @()
$identTool = Join-Path $root 'pmoves\tools\node_identity.py'
if (Test-Path -LiteralPath $identTool) {
    $identPy = Get-PmovesPythonArgv -Root $root
    if (-not $identPy) {
        Write-Warning '[claude-pmoves] node identity: no usable python; launching without it.'
    } else {
        # Same settings.local.json read as the POSIX twin: the resolver runs
        # BEFORE the harness loads that file, so a node whose hostname collides
        # with a vocabulary entry resolves to nothing unless PMOVES_NODE_ID is
        # read from the same block that declares it. A shell value still wins.
        if (-not $env:PMOVES_NODE_ID) {
            $slPath = Join-Path $root '.claude\settings.local.json'
            if (Test-Path -LiteralPath $slPath) {
                try {
                    $cfg = Get-Content -LiteralPath $slPath -Raw | ConvertFrom-Json
                    $envProp = $cfg.PSObject.Properties['env']
                    if ($envProp) {
                        $sid = $envProp.Value.PMOVES_NODE_ID
                        if ($sid) { $env:PMOVES_NODE_ID = $sid }
                    }
                } catch { }   # a malformed settings file must not cost the session
            }
        }
        $identArgv = @($identTool, '--harness', 'claude-code', '--shell')
        if ($identPy.Count -gt 1) { $identArgv = @($identPy[1..($identPy.Count - 1)]) + $identArgv }
        $identOut = & $identPy[0] @identArgv 2>$null
        if ($LASTEXITCODE -eq 0 -and $identOut) {
            # The tool emits shell assignments (KEY='value'); PARSE them rather
            # than eval. PowerShell has no eval of shell syntax, and inventing
            # one would mean running tool output as code for no gain.
            $ident = @{}
            foreach ($line in @($identOut)) {
                if ($line -match "^([A-Z_]+)='(.*)'$") { $ident[$Matches[1]] = $Matches[2] }
            }
            $nodeName  = $ident['PMOVES_NODE']
            $nodeIdent = $ident['PMOVES_RESOLVED_IDENTITY']
            if ($nodeIdent) {
                $env:PMOVES_NODE = $nodeName
                # PMOVES_NODE_IDENTITY is the operator's INPUT override and the
                # name the resolver READS; PMOVES_RESOLVED_IDENTITY is its
                # ANSWER. Export both, as the POSIX twin does, so a tool reading
                # either spelling sees the same value.
                $env:PMOVES_NODE_IDENTITY = $nodeIdent
                $env:PMOVES_RESOLVED_IDENTITY = $nodeIdent
                Write-Host "[claude-pmoves] node=$nodeName identity=$nodeIdent"
                # ---------------------------------------------------------
                # IDENTITY CARRY -- does cipher record these memories as THIS
                # agent? Resolution without the carry is the half-wired state
                # pmoves/tests/scripts/test_launcher_carry_parity.py exists to
                # block, and it blocked this change until the carry landed.
                #
                # pm-cipher-identity.sh is the shared fragment for the eight
                # shell launchers; its own header names "the deploy/provision
                # delegates and their .ps1/.cmd twins" as needing this, and the
                # parity test records that a .ps1 "cannot source a bash
                # fragment". So the CONTRACT is mirrored, not the code: same
                # tool, same verdict fields, same doctrine.
                #
                # ALWAYS LOUD, per that fragment: every path prints a line.
                # Silence on a skip is indistinguishable from a healthy carry,
                # which is the defect the fragment was written to end.
                # ---------------------------------------------------------
                $carryLine = ''
                $carryTool = Join-Path $root 'pmoves/tools/cipher_identity.py'
                if (-not (Test-Path -LiteralPath $carryTool)) {
                    $carryLine = "cipher carry: unmeasurable (no $carryTool)"
                } else {
                    $carryArgv = @($carryTool, '--agent', $nodeIdent, '--shell')
                    if ($identPy.Count -gt 1) { $carryArgv = @($identPy[1..($identPy.Count - 1)]) + $carryArgv }
                    $carryOut = & $identPy[0] @carryArgv 2>$null
                    # EXIT CODE IS A VERDICT, NOT SUCCESS/FAILURE. The tool
                    # documents: 0 carry intact | 1 carry GAP (bootstrap /
                    # advisory / uncarded) | 2 usage error | 3 nothing to
                    # measure. 1 is a MEASUREMENT -- and on this node it is the
                    # normal one, since the session has no CIPHER_API_TOKEN.
                    # Treating it as failure would report "unmeasurable" while
                    # holding a perfectly good verdict, which is the same
                    # conflation of "found something" with "broke" that the
                    # exit-code doctrine exists to prevent.
                    $carryExit = $LASTEXITCODE
                    if ($carryExit -ge 2 -or -not $carryOut) {
                        $carryLine = "cipher carry: unmeasurable (cipher_identity.py exit=$carryExit)"
                    } else {
                        $c = @{}
                        foreach ($line in @($carryOut)) {
                            if ($line -match "^(PMOVES_CIPHER_[A-Z_]+)=(.*)$") {
                                # shlex.quote output: strip one layer of single quotes
                                $v = $Matches[2]
                                if ($v.StartsWith("'") -and $v.EndsWith("'") -and $v.Length -ge 2) {
                                    $v = $v.Substring(1, $v.Length - 2).Replace("'''", "'")
                                }
                                $c[$Matches[1]] = $v
                            }
                        }
                        $mode   = $c['PMOVES_CIPHER_MODE']
                        $carded = $c['PMOVES_CIPHER_CARDED']
                        $eff    = $c['PMOVES_CIPHER_EFFECTIVE_ID']
                        $landsAs = if ($eff) { $eff } else { 'advisory / self-declared' }
                        $carryLine = "cipher carry: mode=$mode card=$carded writes-land-as=$landsAs"
                        if ($carded -ne 'yes' -or $mode -eq 'unknown') {
                            $carryLine += " -- why: $($c['PMOVES_CIPHER_WHY'])"
                        }
                    }
                }
                Write-Host "[claude-pmoves] $carryLine"

                $identityArgs = @('--append-system-prompt', "You are running on PMOVES node '$nodeName'. Your registered identity in pmoves/config/agent_registry.yaml is '$nodeIdent'. Disclose it at session start rather than rediscovering it, and file claim-register rows under it. Cipher memory carry for this session -- $carryLine.")
            } else {
                $w = $ident['PMOVES_IDENTITY_WHY']
                if (-not $w) { $w = 'no reason given' }
                Write-Warning "[claude-pmoves] node identity unresolved: $w"
            }
        } else {
            Write-Warning '[claude-pmoves] node identity: resolver failed; launching without it.'
        }
    }
}
$roster = Join-Path $root '.claude\mcp.json'
$rosterSource = 'working tree'
if (-not $env:PMOVES_ROSTER_FROM_TREE) {
    # PER-LAUNCH name, not a fixed one. Mirrors claude-pmoves.sh; see the
    # comment there. A fixed name is shared by every concurrent session on the
    # node, so a later launch overwrites the file an earlier one still points
    # at -- and PMOVES_MCP_ROSTER now makes something read it after launch.
    $mainRoster = Join-Path ([System.IO.Path]::GetTempPath()) `
        ('pmoves-roster-origin-main.' + [System.IO.Path]::GetRandomFileName() + '.json')
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
    & git -C $root fetch --quiet origin main 2>$null | Out-Null
    $blob = & git -C $root show origin/main:.claude/mcp.json 2>$null
    $ErrorActionPreference = $prev
    if ($LASTEXITCODE -eq 0 -and $blob) {
        # BOM-LESS. Windows PowerShell 5.1's `-Encoding UTF8` writes EF BB BF,
        # and mcp_roster_normalize.py reads with a plain open()+json.load()
        # (:322) which rejects a BOM outright:
        #     JSONDecodeError: Expecting value: line 1 column 1 (char 0)
        # The roster carries bare ${VAR}s, so a failed normalize takes the
        # fail-closed path and REFUSES TO LAUNCH. Every successful origin/main
        # lookup would have broken the default Windows launcher -- the platform
        # the shipped .cmd targets. Caught in review; verified by writing a file
        # both ways and reading it back.
        [System.IO.File]::WriteAllText(
            $mainRoster, ($blob -join "`n"), (New-Object System.Text.UTF8Encoding($false)))
        $roster = $mainRoster
        $rosterSource = 'origin/main'
    } else {
        Write-Warning "[claude-pmoves] could not read the roster from origin/main; using the working tree."
        Write-Warning "[claude-pmoves]   (offline, or origin/main not fetched -- servers may differ from the fleet's)"
    }
}
# Tell the session which roster it got, and from where. Mirrors the export in
# claude-pmoves.sh -- see the comment there for why this is the RAW roster and
# not the normalized copy handed to Claude.
[Environment]::SetEnvironmentVariable('PMOVES_MCP_ROSTER', $roster, 'Process')
[Environment]::SetEnvironmentVariable('PMOVES_MCP_ROSTER_SOURCE', $rosterSource, 'Process')

if (Test-Path $roster) {
    Write-Host ("[claude-pmoves] MCP roster source: " + $rosterSource)
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
    # Same two couplings to the normalizer's sweep as the POSIX twin, and one
    # Windows-specific note:
    #
    #  1. The path must appear on the launched process's command line, because
    #     that is what the sweep's liveness check reads. On Windows there is no
    #     /proc, so it asks Get-CimInstance Win32_Process for CommandLine; every
    #     failure of that query (absent powershell, refused WMI, timeout,
    #     non-zero exit) is treated as UNDETERMINABLE and keeps every file.
    #     A leaked token file is recoverable; a session stripped of its servers
    #     is not.
    #  2. No `--out-dir` here either. XDG_RUNTIME_DIR does not exist on Windows,
    #     so the tool falls back to the temp dir -- which on Windows is already
    #     per-user (%LOCALAPPDATA%\Temp), not world-writable. Do not invent an
    #     XDG path here to compensate.
    #
    # `--mcp-config=<file>` (the `=` form): `--mcp-config` is variadic
    # (`<configs...>`), so the space form would swallow a trailing positional
    # prompt as another config value (Codex #2243 P1).
    & claude "--mcp-config=$useRoster" @identityArgs @args
} else {
    Write-Warning "[claude-pmoves] $roster not found - PMOVES MCP servers will not load."
    & claude @identityArgs @args
}
exit $LASTEXITCODE
