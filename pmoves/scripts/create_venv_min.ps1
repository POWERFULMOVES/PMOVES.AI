Param()

$ErrorActionPreference = 'Stop'

function Have($n){ Get-Command $n -ErrorAction SilentlyContinue | Out-Null }

if (-not (Have 'py') -and -not (Have 'python')) {
  Write-Error 'Python not found. Install Python 3.11+ from https://www.python.org/downloads/windows/'
  exit 1
}

$python = if (Have 'py') { 'py -3' } else { 'python' }

if (-not (Test-Path '.venv')) {
  Write-Host 'Creating .venv (Python virtual environment)...' -ForegroundColor Yellow
  iex "$python -m venv .venv"
} else {
  Write-Host '.venv already exists; reusing.' -ForegroundColor Green
}

. .\\.venv\\Scripts\\Activate.ps1
python -m pip install -U pip
python -m pip install -r pmoves/tools/requirements-minimal.txt
Write-Host 'Done. Activate later with: .\\.venv\\Scripts\\Activate.ps1' -ForegroundColor Green

