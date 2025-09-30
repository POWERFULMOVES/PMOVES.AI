Param(
  [switch]$Force
)

$ErrorActionPreference = 'Continue'

function Have($n){ Get-Command $n -ErrorAction SilentlyContinue | Out-Null }
function Is-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Host "== PMOVES Windows Bootstrap ==" -ForegroundColor Cyan
Write-Host ("CWD: {0}" -f (Get-Location).Path)

$packages = @('python','git','make','jq')

if (-not (Have 'choco')) {
  Write-Warning "Chocolatey not found. Install from https://chocolatey.org/install (Admin PowerShell) then re-run this script."
  exit 1
}

$isAdmin = Is-Admin
if (-not $isAdmin) {
  Write-Warning "This script installs system packages via Chocolatey and should be run in an elevated PowerShell (Run as Administrator)."
  if (-not $Force) { exit 2 }
}

foreach ($pkg in $packages) {
  try {
    $installed = choco list --local-only | Select-String -Pattern ("^" + [regex]::Escape($pkg) + " ")
    if (-not $installed) {
      Write-Host ("Installing {0} via Chocolatey..." -f $pkg) -ForegroundColor Yellow
      choco install $pkg -y
    } else {
      Write-Host ("{0} already installed." -f $pkg) -ForegroundColor Green
    }
  } catch {
    Write-Warning ("Failed to process package {0}: {1}" -f $pkg, $_.Exception.Message)
  }
}

Write-Host "Bootstrap complete. Recommended next steps:" -ForegroundColor Green
Write-Host "- Close and reopen PowerShell to refresh PATH"
Write-Host "- Create venv: pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/create_venv.ps1"
Write-Host "- Or full setup: make setup"

