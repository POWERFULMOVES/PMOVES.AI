param(
  [string]$GlancerRepoUrl = $env:GLANCER_REPO_URL,
  [string]$GlancerRef = $env:GLANCER_REF,
  [string]$GlancerImage = $env:GLANCER_IMAGE
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$patchFile = Join-Path $scriptDir "patches\glancer.diff"
$pmovesDir = Join-Path $repoRoot "pmoves"
$glancerDir = Join-Path $pmovesDir "services\glancer"

if (-not $GlancerRepoUrl) { $GlancerRepoUrl = "https://github.com/POWERFULMOVES/Glancer.git" }
if (-not $GlancerRef) { $GlancerRef = "main" }
if (-not $GlancerImage) { $GlancerImage = "pmoves-glancer:local" }

if (-not (Test-Path $pmovesDir)) {
  throw "pmoves directory not found at $pmovesDir"
}

if (-not (Test-Path $patchFile)) {
  throw "Missing patch file at $patchFile"
}

$gitArgs = @('-C', $repoRoot, 'apply', '--check', $patchFile)
$applyNeeded = $true
try {
  & git @gitArgs *> $null
} catch {
  $applyNeeded = $false
}
if ($applyNeeded) {
  & git -C $repoRoot apply $patchFile
  Write-Host "Applied Glancer compose/env patch."
} else {
  Write-Warning "Glancer patch already applied or conflicts detected; skipping git apply."
}

if (-not (Test-Path $glancerDir)) {
  Write-Host "Cloning Glancer into $glancerDir (ref: $GlancerRef)…"
  & git clone --depth 1 --branch $GlancerRef $GlancerRepoUrl $glancerDir
} else {
  Write-Host "Refreshing existing Glancer checkout at $glancerDir…"
  Push-Location $glancerDir
  try {
    & git fetch --depth 1 origin $GlancerRef
    & git checkout $GlancerRef
    & git pull --ff-only
  } finally {
    Pop-Location
  }
}

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
  Write-Host "Building Glancer image: $GlancerImage"
  try {
    & docker build -t $GlancerImage $glancerDir
    Write-Host "Glancer image built as $GlancerImage"
  } catch {
    Write-Warning "Docker build failed. Check that $glancerDir contains a valid Dockerfile."
  }
} else {
  Write-Warning "Docker not available; skipping Glancer build."
}
