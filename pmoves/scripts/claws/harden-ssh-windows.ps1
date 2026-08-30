# harden-ssh-windows.ps1 — Apply baseline sshd hardening on Windows OpenSSH Server
# Usage: .\harden-ssh-windows.ps1 [-DryRun]
#
# Run as Administrator on the target Windows machine, AFTER enable-ssh-windows.ps1
# has installed authorized keys. Hardening disables password fallback, so a
# missing key in administrators_authorized_keys means lockout.
#
# Pairs with: enable-ssh-windows.ps1 (install/start/inject keys).
# Linux equivalent: pmoves/scripts/hostinger-kvm-setup.sh hardening section.
#
# Idempotent: editing existing values, appending only when missing.

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$configPath = "$env:ProgramData\ssh\sshd_config"

Write-Host "=== PMOVES SSH Hardening for Windows ===" -ForegroundColor Cyan
if (-not (Test-Path $configPath)) {
    throw "sshd_config not found at $configPath — run enable-ssh-windows.ps1 first."
}

# Pre-flight: require at least one parseable key in administrators_authorized_keys.
# Hardening sets PasswordAuthentication no, so a file that exists but holds only
# comments/whitespace would still produce a permanent lockout. Gate on the
# parsed key count, not on file presence or non-whitespace content.
$authKeysPath = "$env:ProgramData\ssh\administrators_authorized_keys"
if (-not (Test-Path $authKeysPath)) {
    throw "Refusing to harden: $authKeysPath missing. Run enable-ssh-windows.ps1 first to install keys."
}
$keyCount = (Get-Content $authKeysPath | Where-Object { $_ -match '^\s*ssh-' }).Count
if ($keyCount -lt 1) {
    throw "Refusing to harden: $authKeysPath contains zero parseable 'ssh-*' key lines. Run enable-ssh-windows.ps1 first."
}
Write-Host "[pre] Found $keyCount authorized key(s) in administrators_authorized_keys"

# Hardening directives. Reasoning per line:
#   PasswordAuthentication no       — key-only auth; no brute-force surface
#   PermitRootLogin prohibit-password — local Administrator login key-only
#   MaxAuthTries 3                  — limit auth attempts per connection
#   PubkeyAuthentication yes        — explicit (defaults vary by OpenSSH version)
$directives = [ordered]@{
    'PasswordAuthentication' = 'no'
    'PermitRootLogin'        = 'prohibit-password'
    'MaxAuthTries'           = '3'
    'PubkeyAuthentication'   = 'yes'
}

$lines = Get-Content $configPath
$changed = $false

foreach ($key in $directives.Keys) {
    $value = $directives[$key]
    $desired = "$key $value"
    # Match active or commented form: optional leading "#" + whitespace, then
    # the directive name (case-insensitive), then anything to EOL.
    $pattern = "^\s*#?\s*$([regex]::Escape($key))\s+.*$"
    $matched = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) {
            if ($lines[$i] -ne $desired) {
                Write-Host "  [edit] $($lines[$i].Trim())  ->  $desired"
                $lines[$i] = $desired
                $changed = $true
            } else {
                Write-Host "  [keep] $desired"
            }
            $matched = $true
            break
        }
    }
    if (-not $matched) {
        Write-Host "  [add ] $desired"
        $lines += $desired
        $changed = $true
    }
}

if ($DryRun) {
    Write-Host ""
    Write-Host "=== DryRun: no changes written ===" -ForegroundColor Yellow
    return
}

if ($changed) {
    # Backup once per run (timestamped) before writing.
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = "$configPath.bak.$stamp"
    Copy-Item $configPath $backup
    Write-Host "  Backup: $backup"
    Set-Content -Path $configPath -Value $lines -Encoding ASCII
    Write-Host "  Wrote: $configPath"

    Write-Host "Restarting sshd..."
    Restart-Service sshd
    Write-Host "  sshd restarted."
} else {
    Write-Host "  No changes needed (already hardened)."
}

Write-Host ""
Write-Host "=== SSH Hardening Complete ===" -ForegroundColor Green
Select-String -Path $configPath -Pattern '^\s*(PasswordAuthentication|PermitRootLogin|MaxAuthTries|PubkeyAuthentication)\b' |
    ForEach-Object { Write-Host "  $($_.Line.Trim())" }
Write-Host ""
