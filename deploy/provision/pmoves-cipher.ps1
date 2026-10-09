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

# Source env.shared — same narrow posture as the .sh twin: ONLY the keys
# listed in PMOVES_CIPHER_REQUIRED_KEYS (default: CIPHER_API_TOKEN) are
# loaded into the process env. Sourcing the whole file would leak
# ANTHROPIC_* / CLAUDE_CODE_* keys into every child of this launcher when it
# is invoked from a CI step or a hook script, which is the documented class
# of bug; the cipher CLI needs the cipher bearer and nothing else. Aliases
# like `KEY=${OTHER_VAR}` are expanded only against allow-listed, loaded
# keys (+ the process env for self-reference); a reference to a key outside
# the allow-list is left as literal ${...} text, exactly like the .sh
# loader's semantics.
$requiredKeys = if ($env:PMOVES_CIPHER_REQUIRED_KEYS) { @($env:PMOVES_CIPHER_REQUIRED_KEYS -split '\s+' | Where-Object { $_ }) } else { @('CIPHER_API_TOKEN') }
$vars = [ordered]@{}
$envFile = if ($env:PMOVES_ENV_SHARED) { $env:PMOVES_ENV_SHARED } else { Join-Path $repoRoot 'pmoves\env.shared' }
if (Test-Path $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*$') { continue }
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        $val = ($line.Substring($eq + 1) -replace '\r$', '')
        if (-not $key) { continue }
        if ($requiredKeys -notcontains $key) { continue }  # allow-list gate (mirrors pmoves-cipher.sh)
        $vars[$key] = $val
    }
    # One-pass ${...} expansion against the allow-listed map (+ process env).
    for ($pass = 0; $pass -lt 5; $pass++) {
        $changed = $false
        foreach ($k in @($vars.Keys)) {
            $curKey = $k
            $resolved = [regex]::Replace($vars[$k], '\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}', {
                param($m)
                $name = $m.Groups[1].Value
                $repl = $null
                if ($requiredKeys -contains $name) {
                    if ($name -ne $curKey -and $vars.Contains($name) -and $vars[$name] -ne '') {
                        $repl = $vars[$name]
                    } else {
                        # Self-reference or not-yet-loaded alias: fall back to
                        # the process env (mirrors the .sh ${!name} indirect
                        # expansion, which reads the already-exported env).
                        $envv = [Environment]::GetEnvironmentVariable($name)
                        if ($envv) { $repl = $envv }
                    }
                }
                if ($null -ne $repl) { $repl }
                elseif ($m.Groups[2].Success) { $m.Groups[2].Value }
                else { $m.Value }   # outside the allow-list: keep literal ${...}
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
# then fall back to python on PATH (Get-Command resolves PATH/PATHEXT;
# Test-Path cannot see bare commands like 'python' or 'py'). We don't gate
# on a Microsoft-Store stub the way pm-python.sh does (no pwsh equivalent
# ladder in this repo yet); that's a follow-up if the Store stub ever sneaks in.
$candidatePaths = @(
    (Join-Path $repoRoot 'pmoves\.venv-pmoves\Scripts\python.exe'),
    (Join-Path $repoRoot 'pmoves\.venv-pmoves\bin\python'),
    'python',
    'python3',
    'py -3'
)
$pythonExe = $null
$pythonArgs = @()
foreach ($cand in $candidatePaths) {
    $parts = $cand -split ' '
    $exe = $parts[0]
    $candArgs = @()
    if ($parts.Count -gt 1) { $candArgs = $parts[1..($parts.Count - 1)] }
    if ($exe -match '[\\/]') {
        # Path candidate (venv python) -- Test-Path is correct here.
        if (Test-Path -LiteralPath $exe) { $pythonExe = $exe; $pythonArgs = $candArgs; break }
    } else {
        # Bare command -- resolve via PATH/PATHEXT, not Test-Path.
        $resolved = Get-Command -Name $exe -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($resolved) { $pythonExe = $resolved.Source; $pythonArgs = $candArgs; break }
    }
}
if (-not $pythonExe) {
    Write-Host "[pmoves-cipher] ERROR: no usable python interpreter." -ForegroundColor Red
    Write-Host "[pmoves-cipher]        Tried: $($candidatePaths -join ', ')"
    exit 1
}

$cli = Join-Path $repoRoot 'pmoves\tools\cipher_cli.py'
if (-not (Test-Path $cli)) {
    Write-Host "[pmoves-cipher] ERROR: $cli not found." -ForegroundColor Red
    exit 1
}

[Environment]::SetEnvironmentVariable('PMOVES_LAUNCHER_SESSION', "pmoves-cipher.ps1 (loaded $($vars.Count) vars)", 'Process')

# Invoke python with the cli + forwarded args. Quoting preserved by pwsh.
& $pythonExe @pythonArgs $cli @args
exit $LASTEXITCODE
