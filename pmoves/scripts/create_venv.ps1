Param(
  [switch]$IncludeDocs
)

$ErrorActionPreference = 'Stop'

function Have($n){ return [bool](Get-Command $n -ErrorAction SilentlyContinue) }

if (-not (Have 'py') -and -not (Have 'python')) {
  Write-Error 'Python not found. Install Python 3.11+ from https://www.python.org/downloads/windows/'
  exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PmovesRoot = Split-Path -Parent $ScriptDir
$VenvDir = Join-Path $PmovesRoot '.venv-pmoves'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

# Prefer the Windows launcher
$python = if (Have 'py') { 'py -3' } else { 'python' }

if (-not (Test-Path $VenvDir)) {
  Write-Host "Creating $VenvDir (Python virtual environment)..." -ForegroundColor Yellow
  if (Have 'uv') {
    & uv venv $VenvDir
  } else {
    iex "$python -m venv `"$VenvDir`""
  }
} else {
  Write-Host "$VenvDir already exists; reusing." -ForegroundColor Green
}

$activate = Join-Path $VenvDir 'Scripts\Activate.ps1'
if (-not (Test-Path $activate) -or -not (Test-Path $VenvPython)) {
  Write-Error "Virtual environment is incomplete at $VenvDir"
  exit 1
}

Write-Host 'Installing requirements across services/tools...' -ForegroundColor Yellow
Push-Location $PmovesRoot
try {
  if ($IncludeDocs) {
    & "$ScriptDir/install_all_requirements.ps1" -CondaEnvName '' -PythonExe $VenvPython -IncludeDocs
  } else {
    & "$ScriptDir/install_all_requirements.ps1" -CondaEnvName '' -PythonExe $VenvPython
  }
}
finally {
  Pop-Location
}

Write-Host "Done. Activate later with: $activate" -ForegroundColor Green

