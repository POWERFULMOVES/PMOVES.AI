#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Helper to bring a Windows host onto the Tailnet with preferred flags.
.DESCRIPTION
    Reads an auth key from either the TAILSCALE_AUTHKEY environment variable
    or a local tailscale_authkey.txt file that lives alongside this script.
    Run this as an administrator after installing Tailscale so the machine
    immediately joins the Tailnet with the expected tags and routing options.
#>

[CmdletBinding()]
param()

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$authKey = $null

$envAuthKey = $env:TAILSCALE_AUTHKEY
if (-not [string]::IsNullOrWhiteSpace($envAuthKey)) {
    $authKey = $envAuthKey.Trim()
}

if (-not $authKey) {
    $authKeyPath = Join-Path $scriptDir 'tailscale_authkey.txt'
    if (Test-Path $authKeyPath) {
        $authKey = (Get-Content $authKeyPath -ErrorAction Stop | Select-Object -First 1).Trim()
    }
}

$tailscaleArgs = @('--ssh', '--accept-routes', '--advertise-tags=tag:lab')
if ($authKey) {
    $tailscaleArgs += "--authkey=$authKey"
}

try {
    $tailscaleCli = Get-Command 'tailscale.exe' -ErrorAction Stop
}
catch {
    throw "tailscale.exe is not in PATH. Install Tailscale first or reopen a new PowerShell session."
}

$tailscalePath = $tailscaleCli.Source

Write-Host "Executing $tailscalePath up $($tailscaleArgs -join ' ')" -ForegroundColor Cyan
try {
    & $tailscalePath up @tailscaleArgs
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "tailscale.exe exited with code $exitCode"
    }
    Write-Host 'Tailnet join command completed.' -ForegroundColor Green
}
catch {
    Write-Error "tailscale.exe up failed: $($_.Exception.Message)"
    throw
}
