Param()

$ErrorActionPreference = 'Stop'

function Have($n){ return [bool](Get-Command $n -ErrorAction SilentlyContinue) }

if (-not (Have 'py') -and -not (Have 'python')) {
  Write-Error 'Python not found. Install Python 3.11+ from https://www.python.org/downloads/windows/'
  exit 1
}

$python = if (Have 'py') { 'py -3' } else { 'python' }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PmovesRoot = Split-Path -Parent $ScriptDir
$VenvDir = Join-Path $PmovesRoot '.venv-pmoves'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$ReqFile = Join-Path $PmovesRoot 'tools\requirements-lite.txt'

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

if (Have 'uv') {
  & uv pip install --python $VenvPython -r $ReqFile
} else {
  & $VenvPython -m pip install -r $ReqFile
}
Write-Host "Done. Activate later with: $VenvDir\Scripts\Activate.ps1" -ForegroundColor Green

