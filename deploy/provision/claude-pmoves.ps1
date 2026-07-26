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
    # Normalize the roster before handing it to Claude (Codex #2243):
    #   P2 - drop servers whose key starts with "_" (disabled-in-name-only, e.g.
    #        `_pmoves-cipher-legacy-python-wrapper`; `_disabled` is metadata, not a
    #        real off-switch, so Claude would otherwise launch the broken dupe).
    #   P3 - rewrite repo-relative ("./...") command/arg paths to absolute $root
    #        paths so `uv --directory ./pmoves-nats-mcp` launches from any CWD.
    $useRoster = $roster
    try {
        $cfg = Get-Content -Raw $roster | ConvertFrom-Json
        function Resolve-RelPath($p) {
            if ($p -is [string] -and $p.StartsWith('./')) { Join-Path $root ($p.Substring(2)) } else { $p }
        }
        $clean = [ordered]@{}
        foreach ($prop in $cfg.mcpServers.PSObject.Properties) {
            if ($prop.Name.StartsWith('_')) { continue }   # disabled-in-name-only
            $s = $prop.Value
            if (($s.PSObject.Properties.Name -contains 'command') -and ($s.command -is [string])) {
                $s.command = Resolve-RelPath $s.command
            }
            if (($s.PSObject.Properties.Name -contains 'args') -and $s.args) {
                $s.args = @($s.args | ForEach-Object { Resolve-RelPath $_ })
            }
            $clean[$prop.Name] = $s
        }
        $cfg.mcpServers = [pscustomobject]$clean
        $resolved = Join-Path $env:TEMP 'claude-pmoves-mcp-roster.json'
        $cfg | ConvertTo-Json -Depth 32 | Set-Content -Encoding UTF8 $resolved
        $useRoster = $resolved
    } catch {
        Write-Warning "[claude-pmoves] could not normalize roster ($($_.Exception.Message)); using raw $roster"
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
