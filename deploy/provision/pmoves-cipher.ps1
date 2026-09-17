<#
pmoves-cipher.ps1 — PowerShell twin of deploy/provision/pmoves-cipher.sh.

Mirrors the bash launcher: source env.shared if it exists, locate the
canonical pmoves Python via pm-python.ps1 (when available; otherwise
fall back to pwsh's natural python), then exec cipher_cli.py.

USAGE:  pmoves-cipher <subcommand> [args...]
         (or invoke the .cmd wrapper for double-clickable Explorer launch)

Subcommands: register | verify | decode | encode | bundle | health
See cipher_cli.py --help for the full grammar.

Provenance: PowerShell twin of deploy/provision/pmoves-cipher.sh. The
.sh launcher does the same thing via pm-python.sh; the .ps1 twin mirrors
the shape used by every other PMOVES .ps1 launcher (see claude-pmoves.ps1
+ crush-pmoves.ps1).
#>
$ErrorActionPreference = 'Stop'

# Resolve repo root (mirror the .sh walk).
$ps1 = $MyInvocation.MyCommand.Path
if ($ps1 -eq '') { $ps1 = $PSCommandPath }
$scriptDir = Split-Path -Parent $ps1
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..\..')).Path

# Source env.shared if it exists. Same .pm.-style sanitization as the .sh
# launcher: ALIAS lines like `KEY=${OTHER_VAR}` get expanded, while literal
# ${...} that point at unset vars are passed through (claude-pmoves does
# the same FAIL-CLOSED treatment in its env-loading block).
$envFile = if ($env:PMOVES_ENV_SHARED) { $env:PMOVES_ENV_SHARED } else { Join-Path $repoRoot 'pmoves\env.shared' }
if (Test-Path $envFile) {
    $vars = [ordered]@{}
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*$') { continue }
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        $val = ($line.Substring($eq + 1) -replace '\r$', '')
        if ($key) { $vars[$key] = $val }
    }
    # One-pass ${{...}} expansion against the map.
    for ($pass = 0; $pass -lt 5; $pass++) {
        $changed = $false
        foreach ($k in @($vars.Keys)) {
            $curKey = $k
            $resolved = [regex]::Replace($vars[$k], '\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}', {
                param($m)
                $name = $m.Groups[1].Value
                $repl = $null
                if ($name -ne $curKey -and $vars.Contains($name) -and $vars[$name] -ne '') { $repl = $vars[$name] }
                elseif ($name -ne $curKey) {
                    $envv = [Environment]::GetEnvironmentVariable($name)
                    if ($envv) { $repl = $envv }
                }
                if ($null -ne $repl) { $repl }
                elseif ($m.Groups[2].Success) { $m.Groups[2].Value }
                else { '' }
            })
            if ($resolved -ne $vars[$k]) { $vars[$k] = $resolved; $changed = $true }
        }
        if (-not $changed) { break }
    }
    foreach ($k in $vars.Keys) {
        [Environment]::SetEnvironmentVariable($k, $vars[$k], 'Process')
    }
    Write-Host "[pmoves-cipher] loaded $($vars.Count) vars from $envFile"
} else {
    Write-Warning "[pmoves-cipher] $envFile not found -- running without env.shared."
}

# Python interpreter discovery. Prefer the venv that's already on this repo,
# then fall back to python on PATH. We don't gate on a Microsoft-Store stub
# the way pm-python.sh does (no pwsh equivalent ladder in this repo yet);
# that's a follow-up if the Store stub ever sneaks in.
$candidatePaths = @(
    (Join-Path $repoRoot 'pmoves\.venv-pmoves\Scripts\python.exe'),
    (Join-Path $repoRoot 'pmoves\.venv-pmoves\bin\python'),
    'python',
    'python3',
    'py -3'
)
$python = $null
foreach ($cand in $candidatePaths) {
    $parts = $cand -split ' '
    $exe = $parts[0]
    if (Test-Path $exe) {
        $python = $cand
        break
    }
}
if (-not $python) {
    Write-Host "[pmoves-cipher] ERROR: no usable python interpreter." -ForegroundColor Red
    Write-Host "[pmoves-cipher]        Tried: $($candidatePaths -join ', ')"
    exit 1
}

$cli = Join-Path $repoRoot 'pmoves\tools\cipher_cli.py'
if (-not (Test-Path $cli)) {
    Write-Host "[pmoves-cipher] ERROR: $cli not found." -ForegroundColor Red
    exit 1
}

[Environment]::SetEnvironmentVariable('PMOVES_LAUNCHER_SESSION', 'pmoves-cipher.ps1', 'Process')

# Invoke python with the cli + forwarded args. Quoting preserved by pwsh.
$parts = $python -split ' '
$exe = $parts[0]
$exeArgs = @()
if ($parts.Count -gt 1) { $exeArgs = $parts[1..($parts.Count - 1)] }
& $exe @exeArgs $cli @args
exit $LASTEXITCODE
