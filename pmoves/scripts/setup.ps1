# PMOVES Windows Quick Setup (PowerShell 7+)
# - Runs interactive env setup, then preflight check.
#
# Usage examples (from pmoves/):
#   pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
#   pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -NonInteractive -Defaults
#   pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -From doppler

param(
  [switch]$NonInteractive,
  [switch]$Defaults,
  [ValidateSet('none','doppler','infisical','1password','sops')]
  [string]$From = 'none',
  [switch]$Quick
)

$ErrorActionPreference = 'Stop'

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location ..  # pmoves/

Write-Host "== PMOVES Windows Quick Setup ==" -ForegroundColor Cyan

$setupArgs = @()
if ($NonInteractive) { $setupArgs += '-NonInteractive' }
if ($Defaults) { $setupArgs += '-Defaults' }
if ($From -and $From -ne 'none') { $setupArgs += @('-From', $From) }

Write-Host "[1/2] Env setup..." -ForegroundColor Yellow
& pwsh -NoProfile -File scripts/env_setup.ps1 @setupArgs

Write-Host "[2/2] Preflight check..." -ForegroundColor Yellow
$checkArgs = @()
if ($Quick) { $checkArgs += '-Quick' }
& pwsh -NoProfile -File scripts/env_check.ps1 @checkArgs

Write-Host "All done." -ForegroundColor Green

Pop-Location
