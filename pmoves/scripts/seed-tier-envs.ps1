# PMOVES Tier Environment Files Seeder (PowerShell 7+)
#
# Creates tier env files from their .example counterparts.
# This is the 6-tier hardened architecture replacement for legacy .env setup.
#
# Usage:
#   pwsh -File scripts\seed-tier-envs.ps1          # interactive prompts
#   pwsh -File scripts\seed-tier-envs.ps1 -Yes     # non-interactive; create all from examples
#   pwsh -File scripts\seed-tier-envs.ps1 -Force   # overwrite existing files
#
# Tier Files (created in pmoves/ folder):
#   - env.tier-data   (postgres, minio, qdrant, neo4j, meilisearch)
#   - env.tier-api    (postgrest, presign, retrieval-eval)
#   - env.tier-llm    (all LLM provider API keys)
#   - env.tier-media  (ffmepg-whisper, media analyzers, youtube)
#   - env.tier-agent  (agent-zero, archon, deepresearch, supaserch)
#   - env.tier-ui     (frontends: pmoves-ui, wger, firefly, open-notebook, jellyfin)
#   - env.tier-worker (extract-worker, langextract, notebook-sync)

[CmdletBinding()]
param(
  [switch]$Force,
  [switch]$Yes,
  [switch]$Verbose
)

$ErrorActionPreference = 'Continue'

# Script location: pmoves/scripts/seed-tier-envs.ps1
# We need to work in the pmoves folder
$ScriptRoot = $PSScriptRoot
if (-not $ScriptRoot) { $ScriptRoot = '.' }
Set-Location (Split-Path -Parent $ScriptRoot)

# All tier env files (in order of loading)
$Tiers = @(
  'data'
  'api'
  'llm'
  'media'
  'agent'
  'worker'
  'ui'
)

Write-Host "== PMOVES Tier Environment Seeder (PowerShell) =="
Write-Host "Working directory: $(Get-Location)"
Write-Host ""

$created = 0
$skipped = 0
$errors = 0

foreach ($tier in $Tiers) {
  $exampleFile = "env.tier-$tier.example"
  $targetFile = "env.tier-$tier"

  if (-not (Test-Path $exampleFile)) {
    Write-Host "❌ ERROR: $exampleFile not found" -ForegroundColor Red
    $errors++
    continue
  }

  if (Test-Path $targetFile) {
    if ($Force) {
      if ($Verbose) {
        Write-Host "📝 Overwriting $targetFile (force mode)" -ForegroundColor Yellow
      }
    } else {
      Write-Host "⏭️  Skipping $targetFile (already exists)"
      $skipped++
      continue
    }
  }

  # Interactive prompt for non-Yes mode
  if (-not $Yes) {
    $response = Read-Host "Create $targetFile from $exampleFile? [Y/n]"
    if ($response -and $response -ne 'Y' -and $response -ne 'y') {
      Write-Host "⏭️  Skipping $targetFile"
      $skipped++
      continue
    }
  }

  # Copy the example file
  try {
    Copy-Item -Path $exampleFile -Destination $targetFile -Force
    Write-Host "✓ Created $targetFile" -ForegroundColor Green
    $created++
  } catch {
    Write-Host "❌ ERROR: Failed to create $targetFile - $_" -ForegroundColor Red
    $errors++
  }
}

Write-Host ""
Write-Host "=== Summary ==="
Write-Host "Created: $created"
Write-Host "Skipped: $skipped"
Write-Host "Errors:  $errors"

if ($created -gt 0) {
  Write-Host ""
  Write-Host "📝 Next steps:"
  Write-Host "  1. Edit the tier env files with your actual values"
  Write-Host "  2. Run: .\scripts\with-env.ps1   # Load environment variables"
  Write-Host "  3. Run: make up                   # Start services (via WSL/Git Bash)"
}

if ($errors -gt 0) {
  exit 1
}
