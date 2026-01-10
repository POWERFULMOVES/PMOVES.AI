param(
  [string]$CondaEnvName = "PMOVES.AI",
  [switch]$IncludeDocs
)

$ErrorActionPreference = 'Stop'

function Have($name){ Get-Command $name -ErrorAction SilentlyContinue | Out-Null }

Write-Host "Scanning for requirements.txt files..." -ForegroundColor Cyan
$roots = @('services','tools')
if ($IncludeDocs) { $roots += 'docs' }
$reqs = @()
foreach ($r in $roots) {
  if (Test-Path $r) {
    $reqs += Get-ChildItem -Path $r -Recurse -Filter requirements.txt -File | ForEach-Object { $_.FullName }
  }
}
if ($reqs.Count -eq 0) { Write-Host "No requirements.txt files found under $roots" -ForegroundColor Yellow; exit 0 }

# If a conda env name is provided and conda exists, try to use conda run
$useCondaRun = $false
if ($CondaEnvName) {
  try {
    & conda run -n $CondaEnvName python -V 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) { $useCondaRun = $true }
  } catch { $useCondaRun = $false }
}

# Prefer uv/pip in current shell only if NOT using conda run
$pipCmd = $null
if (-not $useCondaRun) {
  if (Have 'uv') { $pipCmd = { uv pip install -r $args[0] } }
  elseif (Have 'pip') { $pipCmd = { python -m pip install -r $args[0] } }
  elseif (Have 'python') { $pipCmd = { python -m pip install -r $args[0] } }
  else { throw 'pip or uv is required but not found' }
}

foreach ($req in $reqs) {
  Write-Host ("Installing deps from: {0}" -f $req) -ForegroundColor Green
  if ($useCondaRun) {
    if (Have 'uv') { & conda run -n $CondaEnvName uv pip install -r $req }
    else { & conda run -n $CondaEnvName python -m pip install -r $req }
  } else {
    & $pipCmd.Invoke($req)
  }
}

Write-Host "All requirements installed." -ForegroundColor Green
