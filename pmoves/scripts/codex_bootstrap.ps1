param(
  [switch]$IncludeDocs
)

$ErrorActionPreference = 'Stop'

function Have($n){ return [bool](Get-Command $n -ErrorAction SilentlyContinue) }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BootstrapTool = Join-Path $RepoRoot 'tools/bootstrap_light_env.py'
$Installer = Join-Path $RepoRoot 'scripts/install_all_requirements.ps1'
$VenvPython = Join-Path $RepoRoot '.venv-pmoves\Scripts\python.exe'

Write-Host "== PMOVES Codex Bootstrap ==" -ForegroundColor Cyan
Write-Host "CWD: $((Get-Location).Path)"
Write-Host "Repo root: $RepoRoot"
Write-Host "Bootstrap tool: $BootstrapTool"
Write-Host "Install script: $Installer"

# 1) Create/check pmoves/.venv-pmoves and install lite prerequisites (uv-first)
if (-not (Test-Path $BootstrapTool)) {
  Write-Error "Bootstrap tool not found at $BootstrapTool"
  exit 1
}
Push-Location $RepoRoot
try {
  if (Have 'py') { & py -3 tools/bootstrap_light_env.py --strict-tools }
  else { & python tools/bootstrap_light_env.py --strict-tools }
}
finally {
  Pop-Location
}

# 2) Install Python deps across services/tools into the venv interpreter
if (-not (Test-Path $Installer)) {
  Write-Error "Install script not found at $Installer"
  exit 1
}

Push-Location $RepoRoot
try {
  if ($IncludeDocs) { & $Installer -CondaEnvName '' -PythonExe $VenvPython -IncludeDocs }
  else { & $Installer -CondaEnvName '' -PythonExe $VenvPython }
}
finally {
  Pop-Location
}

Write-Host "Bootstrap complete." -ForegroundColor Green

