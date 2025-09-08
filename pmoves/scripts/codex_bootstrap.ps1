param(
  [string]$CondaEnvName = "PMOVES.AI",
  [switch]$IncludeDocs
)

$ErrorActionPreference = 'Continue'

function Have($n){ Get-Command $n -ErrorAction SilentlyContinue | Out-Null }

Write-Host "== PMOVES Codex Bootstrap ==" -ForegroundColor Cyan
Write-Host "CWD: $((Get-Location).Path)"

# 1) Install GNU Make via Chocolatey if available and missing
if (-not (Have 'make')) {
  if (Have 'choco') {
    Write-Host "Installing GNU Make via Chocolatey..." -ForegroundColor Yellow
    try { choco install make -y } catch { Write-Warning "Chocolatey install failed. Try running an elevated shell: choco install make -y" }
  } else {
    Write-Warning "Chocolatey not found. Install from https://chocolatey.org/install then run: choco install make -y"
  }
} else { Write-Host "make already present." -ForegroundColor Green }

# Optional: jq for Makefile smoke tests
if (-not (Have 'jq')) { Write-Host "jq not found. Recommended for 'make smoke' targets." -ForegroundColor DarkYellow }

# 2) Ensure Conda env exists or create from environment.yml
$condaOk = $false
if (Have 'conda') {
  try { $null = & conda --version; $condaOk = $true } catch {}
}

if ($condaOk) {
  $exists = $false
  try { & conda env list | Select-String -SimpleMatch " $CondaEnvName " | Out-Null; if ($LASTEXITCODE -eq 0) { $exists = $true } } catch {}
  if (-not $exists) {
    if (Test-Path 'environment.yml') {
      Write-Host "Creating conda env '$CondaEnvName' from environment.yml..." -ForegroundColor Yellow
      try { conda env create -f environment.yml -n $CondaEnvName } catch { Write-Warning "conda env create failed. You can try: conda env create -f environment.yml -n $CondaEnvName" }
    } else {
      Write-Warning "environment.yml not found; skipping conda env creation."
    }
  } else {
    Write-Host "Conda env '$CondaEnvName' already exists." -ForegroundColor Green
  }
} else {
  Write-Warning "Conda not detected. Using system Python for dependency installation."
}

# 3) Install Python deps across services/tools
if ($IncludeDocs) { ./scripts/install_all_requirements.ps1 -CondaEnvName $CondaEnvName -IncludeDocs }
else { ./scripts/install_all_requirements.ps1 -CondaEnvName $CondaEnvName }

Write-Host "Bootstrap complete." -ForegroundColor Green

