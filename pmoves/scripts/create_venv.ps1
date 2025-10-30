Param(
  [switch]$IncludeDocs
)

$ErrorActionPreference = 'Stop'

function Have($n){ Get-Command $n -ErrorAction SilentlyContinue | Out-Null }

if (-not (Have 'py') -and -not (Have 'python')) {
  Write-Error 'Python not found. Install Python 3.11+ from https://www.python.org/downloads/windows/'
  exit 1
}

# Prefer the Windows launcher
$python = if (Have 'py') { 'py -3' } else { 'python' }

if (-not (Test-Path '.venv')) {
  Write-Host 'Creating .venv (Python virtual environment)...' -ForegroundColor Yellow
  iex "$python -m venv .venv"
} else {
  Write-Host '.venv already exists; reusing.' -ForegroundColor Green
}

$activate = Join-Path '.venv' 'Scripts' 'Activate.ps1'
if (-not (Test-Path $activate)) {
  Write-Error 'Activation script not found (.venv\Scripts\Activate.ps1)'
  exit 1
}

Write-Host 'Activating venv and upgrading pip...' -ForegroundColor Yellow
. $activate
python -m pip install -U pip

Write-Host 'Installing requirements across services/tools...' -ForegroundColor Yellow
if ($IncludeDocs) {
  ./pmoves/scripts/install_all_requirements.ps1 -CondaEnvName '' -IncludeDocs
} else {
  ./pmoves/scripts/install_all_requirements.ps1 -CondaEnvName ''
}

Write-Host 'Done. Activate later with: .\\.venv\\Scripts\\Activate.ps1' -ForegroundColor Green

