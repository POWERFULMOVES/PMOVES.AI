# crush-pmoves.ps1 — launch Charm Crush with pmoves/env.shared loaded so the MCP
# servers in ~/.config/crush/crush.json get their creds (Windows twin of
# crush-pmoves.sh). See that file's header for the why. env.shared is the single
# source of truth, kept fresh by `make -C pmoves secrets-runtime-hydrate`.
#
# Unlike claude-pmoves.ps1, there is NO --mcp-config handoff: Crush reads its own
# ~/.config/crush/crush.json for MCP servers, so this launcher only has to resolve
# env.shared into the process env, then exec crush.
#
# Usage:  powershell -ExecutionPolicy Bypass -File deploy\provision\crush-pmoves.ps1  [args]
#   (or run crush-pmoves.cmd, which calls this)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envf = if ($env:PMOVES_ENV_SHARED) { $env:PMOVES_ENV_SHARED } else { Join-Path $root 'pmoves\env.shared' }

if (Test-Path $envf) {
    # Blocklist mirrors crush-pmoves.sh: vars that control Crush SDK/session/billing
    # and must NEVER be sourced by the launcher. Sourcing ANTHROPIC_API_KEY (or
    # OPENAI_API_KEY) forces direct API billing even when the user wants the Z.AI
    # Coding Plan path; CRUSH_* are Crush's own session/config, not fleet MCP creds.
    $blocklist = @(
        'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL'
        'CRUSH_*', 'OPENAI_API_KEY'
    ) -replace '\*', '.*'

    # Pass 1: read KEY=VALUE verbatim into an ordered map, skipping blocklisted keys.
    # Values are NOT set into the environment yet — env.shared has ALIAS lines like
    # SUPABASE_SERVICE_ROLE_KEY=${SERVICE_ROLE_KEY}; exporting them verbatim leaks
    # the literal "${SERVICE_ROLE_KEY}" into the MCP creds, starting an alias-backed
    # MCP unauthorized even though the canonical key is present. Mirror
    # pmoves/scripts/with-env.sh + claude-pmoves.ps1: resolve first.
    $vars = [ordered]@{}
    foreach ($line in Get-Content -LiteralPath $envf) {
        if ($line -match '^\s*#') { continue }        # comment
        if ($line -match '^\s*$') { continue }        # blank
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        $blocked = $false
        foreach ($pat in $blocklist) { if ($key -match "^$pat$") { $blocked = $true; break } }
        if ($blocked) { continue }
        $val = ($line.Substring($eq + 1) -replace '\r$','')
        if ($key) { $vars[$key] = $val }
    }
    # Pass 2: expand ${VAR} and ${VAR:-default} against the map (mirrors the shell
    # `source` in crush-pmoves.sh). Bounded iteration resolves chained aliases;
    # stops early once a pass makes no substitution. A self-reference
    # (KEY=${KEY:-default}) skips the var branch and falls to the default.
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
    Write-Host "[crush-pmoves] loaded $n vars from $envf"
} else {
    Write-Warning "[crush-pmoves] $envf not found - MCP creds may be missing. Run: make -C pmoves ensure-env-shared"
}

# Hand off to crush with any passed args. Crush reads ~/.config/crush/crush.json
# for its MCP servers; the vars loaded above resolve the ${...} refs in that file.
& crush @args
exit $LASTEXITCODE
