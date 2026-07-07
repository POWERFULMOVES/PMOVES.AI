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
    $n = 0
    foreach ($line in Get-Content -LiteralPath $envf) {
        if ($line -match '^\s*#') { continue }        # comment
        if ($line -match '^\s*$') { continue }        # blank
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1)               # value verbatim (no trim)
        if ($key) { [Environment]::SetEnvironmentVariable($key, $val, 'Process'); $n++ }
    }
    Write-Host "[claude-pmoves] loaded $n vars from $envf"
} else {
    Write-Warning "[claude-pmoves] $envf not found - MCP creds may be missing. Run: make -C pmoves ensure-env-shared"
}

# Hand off to claude with any passed args
& claude @args
exit $LASTEXITCODE
