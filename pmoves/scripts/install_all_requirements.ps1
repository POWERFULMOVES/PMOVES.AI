param(
  [string]$CondaEnvName = "PMOVES.AI",
  [string]$PythonExe = "",
  [switch]$Strict,
  [switch]$IncludeDocs
)

$ErrorActionPreference = 'Stop'

function Have($name){ return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

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

# If a venv python is provided, install directly into that interpreter.
# Otherwise, if a conda env name is provided and conda exists, use conda run.
$useCondaRun = $false
if (-not $PythonExe -and $CondaEnvName) {
  try {
    & conda run -n $CondaEnvName python -V 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) { $useCondaRun = $true }
  } catch { $useCondaRun = $false }
}

# Prefer uv/pip in current shell only if NOT using explicit Python or conda run
$pipCmd = $null
if (-not $PythonExe -and -not $useCondaRun) {
  if (Have 'uv') { $pipCmd = { uv pip install -r $args[0] } }
  elseif (Have 'pip') { $pipCmd = { python -m pip install -r $args[0] } }
  elseif (Have 'python') { $pipCmd = { python -m pip install -r $args[0] } }
  else { throw 'pip or uv is required but not found' }
}

$failed = @()
foreach ($req in $reqs) {
  Write-Host ("Installing deps from: {0}" -f $req) -ForegroundColor Green
  try {
    if ($PythonExe) {
      if (Have 'uv') { & uv pip install --python $PythonExe -r $req }
      else { & $PythonExe -m pip install -r $req }
    } elseif ($useCondaRun) {
      if (Have 'uv') { & conda run -n $CondaEnvName uv pip install -r $req }
      else { & conda run -n $CondaEnvName python -m pip install -r $req }
    } else {
      & $pipCmd.Invoke($req)
    }
    if ($LASTEXITCODE -ne 0) {
      throw "installer exited with code $LASTEXITCODE"
    }
  } catch {
    Write-Warning ("Install failed for {0}: {1}" -f $req, $_.Exception.Message)
    $failed += $req
  }
}

if ($failed.Count -gt 0) {
  $summary = ("Dependency installation failed for {0} requirements file(s)." -f $failed.Count)
  if ($Strict) {
    throw $summary
  }
  Write-Warning $summary
  Write-Warning "Use -Strict to fail immediately in CI/gated flows."
}

Write-Host "All requirements installed." -ForegroundColor Green
