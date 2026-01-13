param(
  [string]$BaseDir = 'integrations-workspace',
  [string]$Branch = 'chore/pmoves-net+ghcr',
  [switch]$DryRun
)

$repos = @(
  @{ dir = Join-Path $BaseDir 'Pmoves-Health-wger';    url = 'https://github.com/POWERFULMOVES/Pmoves-Health-wger' },
  @{ dir = Join-Path $BaseDir 'PMOVES-Firefly-iii';    url = 'https://github.com/POWERFULMOVES/pmoves-firefly-iii' },
  @{ dir = Join-Path $BaseDir 'Pmoves-open-notebook';  url = 'https://github.com/POWERFULMOVES/Pmoves-open-notebook' },
  @{ dir = Join-Path $BaseDir 'PMOVES-jellyfin';       url = 'https://github.com/POWERFULMOVES/PMOVES-jellyfin' }
)

$prTitle = 'chore: PMOVES integration — pmoves-net compose + GHCR publish'

foreach ($r in $repos) {
  if (-not (Test-Path $r.dir)) { Write-Warning "Missing repo path: $($r.dir)"; continue }
  Push-Location $r.dir
  try {
    if ($DryRun) {
      Write-Host "[DRY] git push -u origin $Branch" -ForegroundColor Yellow
    } else {
      git push -u origin $Branch
    }
  } catch {
    Write-Warning "Push failed for $($r.dir): $($_.Exception.Message)"
  }
  try {
    if (Get-Command gh -ErrorAction SilentlyContinue) {
      if ($DryRun) {
        Write-Host "[DRY] gh pr create --title $prTitle --body-file README_PRSUMMARY.md --base main --head $Branch" -ForegroundColor Yellow
      } else {
        gh pr create --title $prTitle --body-file README_PRSUMMARY.md --base main --head $Branch
      }
    } else {
      Write-Host "Open PR manually:" -ForegroundColor Yellow
      Write-Host ("{0}/compare/{1}?expand=1" -f $r.url, $Branch)
    }
  } finally {
    Pop-Location
  }
}

