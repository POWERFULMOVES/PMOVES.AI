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
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not (Test-Path $normalizer)) {
        $why = "the normalizer is missing: $normalizer"
    } elseif (-not $py) {
        $why = 'no usable python interpreter (tried python, then python3)'
    } else {
        try {
            # The tool prints the path it wrote on stdout; warnings go to stderr
            # and pass through to the console.
            $out = & $py.Source $normalizer $roster '--root' $root '--label' 'claude-pmoves'
            if ($LASTEXITCODE -ne 0) {
                $why = "the normalizer exited $LASTEXITCODE under '$($py.Source)' (its own stderr is above)"
            } elseif (-not $out) {
                $why = 'the normalizer exited 0 but printed no roster path - nothing was written'
            } else {
                $useRoster = ([string](@($out)[-1])).Trim()
                $resolvedOk = $true
            }
        } catch {
            $why = "the normalizer could not be run under '$($py.Source)': $($_.Exception.Message)"
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
        if (Select-String -Path $roster -SimpleMatch '${' -Quiet) {
            Write-Warning ('[claude-pmoves] LOST: ' + $roster + ' still contains ${VAR} references;')
            Write-Warning '[claude-pmoves]       they are sent LITERALLY, so those MCP servers cannot authenticate.'
            if (-not $env:PMOVES_ALLOW_RAW_ROSTER) {
                Write-Warning '[claude-pmoves] Refusing to start a session whose MCP credentials are placeholders.'
                Write-Warning '[claude-pmoves] Fix: install python, or run make -C pmoves preflight.'
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
