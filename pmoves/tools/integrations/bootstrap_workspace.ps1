param(
  [string]$BaseDir = 'integrations-workspace',
  [string]$WgerUrl = 'https://github.com/POWERFULMOVES/Pmoves-Health-wger.git',
  [string]$FireflyUrl = 'https://github.com/POWERFULMOVES/pmoves-firefly-iii.git',
  [string]$OpenNotebookUrl = 'https://github.com/POWERFULMOVES/Pmoves-open-notebook.git',
  [string]$JellyfinUrl = 'https://github.com/POWERFULMOVES/PMOVES-jellyfin.git'
)

$ScriptRoot = (Resolve-Path $PSScriptRoot).Path
$ApplyKit = Join-Path $ScriptRoot 'apply_pr_kit.ps1'

New-Item -ItemType Directory -Force -Path $BaseDir | Out-Null
Set-Location $BaseDir

function Clone-IfMissing($Url, $Dir) {
  if (Test-Path (Join-Path $Dir '.git')) {
    Write-Host "✔ Repo exists: $Dir"
  } else {
    Write-Host "→ Cloning $Url into $Dir"
    git clone $Url $Dir | Out-Null
  }
}

Clone-IfMissing $WgerUrl 'Pmoves-Health-wger'
Clone-IfMissing $FireflyUrl 'PMOVES-Firefly-iii'
Clone-IfMissing $OpenNotebookUrl 'Pmoves-open-notebook'
Clone-IfMissing $JellyfinUrl 'PMOVES-jellyfin'

Write-Host "`n→ Applying PR kits" -ForegroundColor Cyan
& $ApplyKit -Kit 'wger' -Repo (Resolve-Path 'Pmoves-Health-wger').Path
& $ApplyKit -Kit 'firefly' -Repo (Resolve-Path 'PMOVES-Firefly-iii').Path
& $ApplyKit -Kit 'open-notebook' -Repo (Resolve-Path 'Pmoves-open-notebook').Path
& $ApplyKit -Kit 'jellyfin' -Repo (Resolve-Path 'PMOVES-jellyfin').Path

@"

All branches created: chore/pmoves-net+ghcr
Next steps (run in each repo folder):
  git push -u origin chore/pmoves-net+ghcr
  Open a PR on GitHub (title: "chore: PMOVES integration — pmoves-net compose + GHCR publish")

After merges, in PMOVES repo run:
  make -C pmoves up-external

"@

